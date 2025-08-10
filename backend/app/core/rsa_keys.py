"""
RSA Key Management for JWT Authentication

This module handles generation, storage, and rotation of RSA keys
for secure JWT authentication using RS256 algorithm.
"""

import logging
import os
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)


class RSAKeyManager:
    """Manages RSA keys for JWT authentication."""

    def __init__(self, keys_dir: Path | None = None):
        """Initialize RSA key manager.

        Args:
            keys_dir: Directory to store keys. Defaults to app/core/keys/
        """
        if keys_dir is None:
            keys_dir = Path(__file__).parent / "keys"
        self.keys_dir = keys_dir
        self.keys_dir.mkdir(exist_ok=True, mode=0o700)  # Secure directory permissions

        self.private_key_path = self.keys_dir / "jwt_private.pem"
        self.public_key_path = self.keys_dir / "jwt_public.pem"

        # Key rotation paths
        self.old_public_key_path = self.keys_dir / "jwt_public_old.pem"

    def generate_keys(self, key_size: int = 4096) -> tuple[bytes, bytes]:
        """Generate new RSA key pair.

        Args:
            key_size: Size of RSA key in bits (minimum 2048, recommended 4096)

        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        if key_size < 2048:
            raise ValueError("RSA key size must be at least 2048 bits for security")

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=key_size, backend=default_backend()
        )

        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),  # Consider encryption for production
        )

        # Get public key
        public_key = private_key.public_key()

        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return private_pem, public_pem

    def save_keys(self, private_pem: bytes, public_pem: bytes) -> None:
        """Save RSA keys to files with secure permissions.

        Args:
            private_pem: Private key in PEM format
            public_pem: Public key in PEM format
        """
        # Save private key with restricted permissions
        self.private_key_path.write_bytes(private_pem)
        os.chmod(self.private_key_path, 0o600)  # Read/write for owner only

        # Save public key (readable by all)
        self.public_key_path.write_bytes(public_pem)
        os.chmod(self.public_key_path, 0o644)  # Read for all, write for owner

        logger.info("RSA keys saved successfully")

    def load_keys(self) -> tuple[bytes, bytes]:
        """Load RSA keys from files.

        Returns:
            Tuple of (private_key_pem, public_key_pem)

        Raises:
            FileNotFoundError: If key files don't exist
        """
        if not self.private_key_path.exists() or not self.public_key_path.exists():
            raise FileNotFoundError("RSA keys not found. Generate them first.")

        private_pem = self.private_key_path.read_bytes()
        public_pem = self.public_key_path.read_bytes()

        return private_pem, public_pem

    def rotate_keys(self) -> tuple[bytes, bytes]:
        """Rotate RSA keys for enhanced security.

        Keeps old public key for verifying existing tokens.

        Returns:
            Tuple of new (private_key_pem, public_key_pem)
        """
        # Backup current public key for verifying old tokens
        if self.public_key_path.exists():
            current_public = self.public_key_path.read_bytes()
            self.old_public_key_path.write_bytes(current_public)
            os.chmod(self.old_public_key_path, 0o644)
            logger.info("Backed up old public key for token verification")

        # Generate new keys
        private_pem, public_pem = self.generate_keys()

        # Save new keys
        self.save_keys(private_pem, public_pem)

        logger.info("RSA keys rotated successfully")
        return private_pem, public_pem

    def get_or_create_keys(self) -> tuple[bytes, bytes]:
        """Get existing keys or create new ones if they don't exist.

        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        try:
            return self.load_keys()
        except FileNotFoundError:
            logger.info("RSA keys not found. Generating new keys...")
            private_pem, public_pem = self.generate_keys()
            self.save_keys(private_pem, public_pem)
            return private_pem, public_pem

    def get_public_keys_for_verification(self) -> list[bytes]:
        """Get all public keys for token verification.

        Returns current and old public keys to handle key rotation gracefully.

        Returns:
            List of public keys in PEM format
        """
        keys = []

        # Add current public key
        if self.public_key_path.exists():
            keys.append(self.public_key_path.read_bytes())

        # Add old public key if exists (for key rotation)
        if self.old_public_key_path.exists():
            keys.append(self.old_public_key_path.read_bytes())

        return keys


# Global instance
rsa_key_manager = RSAKeyManager()
