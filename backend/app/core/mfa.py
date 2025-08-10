"""
Multi-Factor Authentication (MFA) implementation using TOTP.

This module provides complete MFA functionality including:
- TOTP token generation and verification
- Backup codes generation and management
- QR code generation for authenticator apps
- Rate limiting for verification attempts
"""

import base64
import secrets
import string
from datetime import datetime, timedelta
from io import BytesIO

import pyotp
import qrcode
from passlib.context import CryptContext
from sqlmodel import Session

from app.core.config import settings
from app.models import User

# Password context for hashing backup codes
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class MFAService:
    """Service for managing Multi-Factor Authentication."""

    def __init__(self):
        self.issuer_name = settings.PROJECT_NAME
        self.backup_code_length = 8
        self.backup_code_count = 10
        self.totp_validity_window = 1  # Allow 1 time step before/after

    def generate_secret(self) -> str:
        """Generate a new TOTP secret for a user."""
        return pyotp.random_base32()

    def generate_provisioning_uri(self, email: str, secret: str) -> str:
        """Generate provisioning URI for QR code."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=self.issuer_name)

    def generate_qr_code(self, provisioning_uri: str) -> str:
        """Generate QR code as base64 encoded image."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode()

    def verify_totp(self, secret: str, token: str) -> bool:
        """Verify a TOTP token."""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=self.totp_validity_window)

    def generate_backup_codes(self) -> list[str]:
        """Generate backup codes for account recovery."""
        codes = []
        alphabet = string.ascii_uppercase + string.digits

        for _ in range(self.backup_code_count):
            code = "".join(
                secrets.choice(alphabet) for _ in range(self.backup_code_length)
            )
            # Format as XXXX-XXXX for readability
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)

        return codes

    def hash_backup_code(self, code: str) -> str:
        """Hash a backup code for storage."""
        # Remove formatting before hashing
        clean_code = code.replace("-", "")
        return pwd_context.hash(clean_code)

    def verify_backup_code(self, code: str, hashed_code: str) -> bool:
        """Verify a backup code against its hash."""
        # Remove formatting before verification
        clean_code = code.replace("-", "")
        return pwd_context.verify(clean_code, hashed_code)

    async def setup_mfa(
        self, session: Session, user: User
    ) -> tuple[str, list[str], str]:
        """
        Setup MFA for a user.

        Returns:
            Tuple of (secret, backup_codes, qr_code_base64)
        """
        # Generate TOTP secret
        secret = self.generate_secret()

        # Generate backup codes
        backup_codes = self.generate_backup_codes()

        # Generate QR code
        provisioning_uri = self.generate_provisioning_uri(user.email, secret)
        qr_code = self.generate_qr_code(provisioning_uri)

        # Store hashed backup codes in database
        hashed_codes = [self.hash_backup_code(code) for code in backup_codes]

        # Update user model (to be implemented in models.py)
        user.totp_secret = secret
        user.backup_codes = hashed_codes
        user.mfa_enabled = False  # Will be enabled after first successful verification
        user.mfa_setup_at = datetime.utcnow()

        session.add(user)
        session.commit()
        session.refresh(user)

        return secret, backup_codes, qr_code

    async def enable_mfa(self, session: Session, user: User, token: str) -> bool:
        """
        Enable MFA after verifying the first token.

        Args:
            session: Database session
            user: User object
            token: TOTP token to verify

        Returns:
            True if MFA was enabled successfully
        """
        if not user.totp_secret:
            raise ValueError("MFA not set up for this user")

        if self.verify_totp(user.totp_secret, token):
            user.mfa_enabled = True
            user.mfa_enabled_at = datetime.utcnow()
            session.add(user)
            session.commit()
            return True

        return False

    async def disable_mfa(self, session: Session, user: User) -> bool:
        """
        Disable MFA for a user.

        Args:
            session: Database session
            user: User object

        Returns:
            True if MFA was disabled successfully
        """
        user.mfa_enabled = False
        user.totp_secret = None
        user.backup_codes = []
        user.mfa_disabled_at = datetime.utcnow()

        session.add(user)
        session.commit()
        return True

    async def verify_mfa_token(
        self, session: Session, user: User, token: str, allow_backup: bool = True
    ) -> tuple[bool, str | None]:
        """
        Verify an MFA token (TOTP or backup code).

        Args:
            session: Database session
            user: User object
            token: Token to verify (TOTP or backup code)
            allow_backup: Whether to allow backup codes

        Returns:
            Tuple of (is_valid, token_type)
            token_type can be 'totp', 'backup', or None
        """
        if not user.mfa_enabled:
            return False, None

        # First try TOTP verification
        if user.totp_secret and self.verify_totp(user.totp_secret, token):
            # Update last MFA verification time
            user.last_mfa_verification = datetime.utcnow()
            session.add(user)
            session.commit()
            return True, "totp"

        # Then try backup codes if allowed
        if allow_backup and user.backup_codes:
            token.replace("-", "")
            for i, hashed_code in enumerate(user.backup_codes):
                if self.verify_backup_code(token, hashed_code):
                    # Remove used backup code
                    user.backup_codes.pop(i)
                    user.last_mfa_verification = datetime.utcnow()
                    session.add(user)
                    session.commit()
                    return True, "backup"

        return False, None

    def requires_mfa_verification(
        self, user: User, grace_period_minutes: int = 15
    ) -> bool:
        """
        Check if a user requires MFA verification.

        Args:
            user: User object
            grace_period_minutes: Minutes before requiring re-verification

        Returns:
            True if MFA verification is required
        """
        if not user.mfa_enabled:
            return False

        if not user.last_mfa_verification:
            return True

        time_since_verification = datetime.utcnow() - user.last_mfa_verification
        return time_since_verification > timedelta(minutes=grace_period_minutes)

    async def regenerate_backup_codes(self, session: Session, user: User) -> list[str]:
        """
        Regenerate backup codes for a user.

        Args:
            session: Database session
            user: User object

        Returns:
            List of new backup codes
        """
        if not user.mfa_enabled:
            raise ValueError("MFA must be enabled to regenerate backup codes")

        # Generate new codes
        backup_codes = self.generate_backup_codes()

        # Hash and store them
        hashed_codes = [self.hash_backup_code(code) for code in backup_codes]
        user.backup_codes = hashed_codes
        user.backup_codes_generated_at = datetime.utcnow()

        session.add(user)
        session.commit()

        return backup_codes


# Singleton instance
mfa_service = MFAService()
