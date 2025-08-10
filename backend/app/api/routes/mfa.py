"""
Multi-Factor Authentication API endpoints.

This module provides endpoints for MFA setup, verification, and management.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.mfa import mfa_service
from app.core.rate_limiter import auth_rate_limit
from app.models import Message, User

logger = logging.getLogger(__name__)

router = APIRouter()


class MFASetupResponse(BaseModel):
    """Response model for MFA setup."""

    qr_code: str = Field(..., description="Base64 encoded QR code image")
    secret: str = Field(..., description="TOTP secret for manual entry")
    backup_codes: list[str] = Field(..., description="Backup recovery codes")
    message: str = Field(
        default="MFA setup initiated. Please verify with authenticator app"
    )


class MFAEnableRequest(BaseModel):
    """Request model for enabling MFA."""

    token: str = Field(
        ..., min_length=6, max_length=6, description="TOTP verification code"
    )


class MFAVerifyRequest(BaseModel):
    """Request model for MFA verification."""

    token: str = Field(
        ..., min_length=6, max_length=10, description="TOTP or backup code"
    )


class MFAStatusResponse(BaseModel):
    """Response model for MFA status."""

    enabled: bool
    backup_codes_remaining: int
    last_verification: str | None
    setup_at: str | None


class MFABackupCodesResponse(BaseModel):
    """Response model for backup codes."""

    backup_codes: list[str]
    message: str = Field(default="New backup codes generated. Store them securely.")


@router.post("/setup", response_model=MFASetupResponse)
async def setup_mfa(session: SessionDep, current_user: CurrentUser) -> MFASetupResponse:
    """
    Setup MFA for the current user.

    This endpoint generates:
    - TOTP secret
    - QR code for authenticator apps
    - Backup recovery codes

    The user must verify the setup with a valid TOTP token to enable MFA.
    """
    try:
        # Check if MFA is already enabled
        if current_user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is already enabled for this account",
            )

        # Setup MFA
        secret, backup_codes, qr_code = await mfa_service.setup_mfa(
            session, current_user
        )

        logger.info(f"MFA setup initiated for user {current_user.email}")

        return MFASetupResponse(
            qr_code=qr_code, secret=secret, backup_codes=backup_codes
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"MFA setup failed for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup MFA",
        )


@router.post("/enable", response_model=Message)
@auth_rate_limit
async def enable_mfa(
    request: MFAEnableRequest, session: SessionDep, current_user: CurrentUser
) -> Message:
    """
    Enable MFA after verifying the first TOTP token.

    This endpoint must be called after setup to activate MFA.
    Rate limited to prevent brute force attacks.
    """
    try:
        # Verify MFA is set up but not enabled
        if current_user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is already enabled"
            )

        if not current_user.totp_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA setup not completed",
            )

        # Enable MFA
        success = await mfa_service.enable_mfa(session, current_user, request.token)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid verification code",
            )

        logger.info(f"MFA enabled for user {current_user.email}")

        return Message(message="MFA has been successfully enabled")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable MFA for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable MFA",
        )


@router.post("/verify", response_model=Message)
@auth_rate_limit
async def verify_mfa(
    request: MFAVerifyRequest, session: SessionDep, current_user: CurrentUser
) -> Message:
    """
    Verify an MFA token (TOTP or backup code).

    This endpoint is used during login to verify the second factor.
    Rate limited to prevent brute force attacks.
    """
    try:
        # Check if MFA is enabled
        if not current_user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not enabled for this account",
            )

        # Verify token
        is_valid, token_type = await mfa_service.verify_mfa_token(
            session, current_user, request.token
        )

        if not is_valid:
            logger.warning(f"Invalid MFA token for user {current_user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid verification code",
            )

        logger.info(f"MFA verified for user {current_user.email} using {token_type}")

        # Return different message based on token type
        if token_type == "backup":
            remaining = (
                len(current_user.backup_codes) if current_user.backup_codes else 0
            )
            return Message(
                message=f"Verification successful using backup code. {remaining} backup codes remaining."
            )
        else:
            return Message(message="MFA verification successful")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA verification failed for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify MFA",
        )


@router.post("/disable", response_model=Message)
async def disable_mfa(
    token: Annotated[
        str,
        Body(
            ...,
            min_length=6,
            max_length=10,
            description="Current TOTP or backup code for verification",
        ),
    ],
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """
    Disable MFA for the current user.

    Requires verification with current TOTP or backup code for security.
    """
    try:
        # Check if MFA is enabled
        if not current_user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not enabled for this account",
            )

        # Verify current token before disabling
        is_valid, _ = await mfa_service.verify_mfa_token(session, current_user, token)

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid verification code",
            )

        # Disable MFA
        success = await mfa_service.disable_mfa(session, current_user)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to disable MFA",
            )

        logger.info(f"MFA disabled for user {current_user.email}")

        return Message(message="MFA has been successfully disabled")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable MFA for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable MFA",
        )


@router.get("/status", response_model=MFAStatusResponse)
async def get_mfa_status(current_user: CurrentUser) -> MFAStatusResponse:
    """
    Get MFA status for the current user.

    Returns information about MFA configuration and usage.
    """
    backup_codes_count = (
        len(current_user.backup_codes) if current_user.backup_codes else 0
    )

    return MFAStatusResponse(
        enabled=current_user.mfa_enabled,
        backup_codes_remaining=backup_codes_count,
        last_verification=str(current_user.last_mfa_verification)
        if current_user.last_mfa_verification
        else None,
        setup_at=str(current_user.mfa_setup_at) if current_user.mfa_setup_at else None,
    )


@router.post("/backup-codes/regenerate", response_model=MFABackupCodesResponse)
@auth_rate_limit
async def regenerate_backup_codes(
    token: Annotated[
        str,
        Body(
            ...,
            min_length=6,
            max_length=6,
            description="Current TOTP code for verification",
        ),
    ],
    session: SessionDep,
    current_user: CurrentUser,
) -> MFABackupCodesResponse:
    """
    Regenerate backup codes for the current user.

    This will invalidate all existing backup codes.
    Requires TOTP verification (backup codes cannot be used here).
    """
    try:
        # Check if MFA is enabled
        if not current_user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not enabled for this account",
            )

        # Verify TOTP (not backup codes for this operation)
        is_valid, token_type = await mfa_service.verify_mfa_token(
            session, current_user, token, allow_backup=False
        )

        if not is_valid or token_type != "totp":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code. Backup codes cannot be used for this operation.",
            )

        # Regenerate backup codes
        new_codes = await mfa_service.regenerate_backup_codes(session, current_user)

        logger.info(f"Backup codes regenerated for user {current_user.email}")

        return MFABackupCodesResponse(backup_codes=new_codes)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to regenerate backup codes for user {current_user.email}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate backup codes",
        )


@router.post("/admin/reset/{user_id}", response_model=Message)
async def admin_reset_mfa(
    user_id: str,
    session: SessionDep,
    current_superuser: Annotated[User, Depends(get_current_active_superuser)],
) -> Message:
    """
    Admin endpoint to reset MFA for a user.

    Only accessible by superusers for account recovery.
    """
    try:
        # Get target user
        from sqlmodel import select

        statement = select(User).where(User.id == user_id)
        target_user = session.exec(statement).first()

        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Disable MFA for the user
        if target_user.mfa_enabled:
            await mfa_service.disable_mfa(session, target_user)
            logger.warning(
                f"MFA reset for user {target_user.email} by admin {current_superuser.email}"
            )
            return Message(message=f"MFA has been reset for user {target_user.email}")
        else:
            return Message(message="MFA was not enabled for this user")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin MFA reset failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset MFA",
        )
