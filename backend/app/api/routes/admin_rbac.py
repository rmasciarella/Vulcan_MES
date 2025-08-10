"""
Admin RBAC API Routes

Provides administrative endpoints for managing roles, permissions, and access control.
These endpoints are restricted to administrators only.

Security Features:
- Admin-only access control
- Comprehensive audit logging
- Input validation and sanitization
- Secure role assignment workflow
- OWASP compliant implementation
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, validator
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.rbac import (
    SCHEDULING_ROLE_PERMISSIONS,
    DataScope,
    PermissionOverride,
    PermissionOverrideRequest,
    PermissionService,
    RoleAssignment,
    RoleAssignmentRequest,
    RoleManager,
    SchedulingPermission,
    SchedulingRole,
    UserPermissionsResponse,
    require_scheduling_permission,
)
from app.core.security_enhanced import AuditLogger, SecureInputValidator
from app.models import User

router = APIRouter(prefix="/admin/rbac", tags=["admin-rbac"])
audit_logger = AuditLogger()
validator = SecureInputValidator()


# Response Models
class RoleInfo(BaseModel):
    """Information about a role."""

    role: SchedulingRole
    description: str
    permissions: list[str]
    user_count: int


class RoleAssignmentResponse(BaseModel):
    """Response for role assignment."""

    id: UUID
    user_id: UUID
    user_email: str
    user_name: str | None
    role: SchedulingRole
    department: str | None
    assigned_by: UUID
    assigned_at: datetime
    expires_at: datetime | None
    is_active: bool
    notes: str | None


class PermissionOverrideResponse(BaseModel):
    """Response for permission override."""

    id: UUID
    user_id: UUID
    user_email: str
    permission: SchedulingPermission
    grant: bool
    reason: str
    approved_by: UUID
    created_at: datetime
    expires_at: datetime | None
    is_active: bool


class DataScopeResponse(BaseModel):
    """Response for data scope."""

    id: UUID
    user_id: UUID
    scope_type: str
    scope_value: str
    created_at: datetime
    created_by: UUID
    is_active: bool


class AuditLogEntry(BaseModel):
    """Audit log entry for RBAC operations."""

    timestamp: datetime
    event_type: str
    user_id: UUID | None
    target_user_id: UUID | None
    description: str
    details: dict[str, Any]
    ip_address: str | None


# Role Management Endpoints
@router.get("/roles", response_model=list[RoleInfo])
async def list_available_roles(
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.ROLE_MANAGE)
    ),
    session: SessionDep = None,
):
    """
    List all available roles and their permissions.

    Security: Requires ROLE_MANAGE permission.
    """
    roles_info = []

    for role in SchedulingRole:
        # Get permissions for role
        permissions = SCHEDULING_ROLE_PERMISSIONS.get(role, set())

        # Count users with this role
        user_count = session.exec(
            select(func.count(RoleAssignment.id)).where(
                RoleAssignment.role == role, RoleAssignment.is_active
            )
        ).one()

        # Get role description
        descriptions = {
            SchedulingRole.SCHEDULING_ADMIN: "Full system administration access",
            SchedulingRole.SUPERVISOR: "Department supervision and management",
            SchedulingRole.PLANNER: "Schedule planning and optimization",
            SchedulingRole.OPERATOR: "Task execution and status updates",
            SchedulingRole.VIEWER: "Read-only access to schedules",
            SchedulingRole.QUALITY_CONTROLLER: "Quality control and approvals",
            SchedulingRole.MAINTENANCE_TECH: "Machine maintenance scheduling",
        }

        roles_info.append(
            RoleInfo(
                role=role,
                description=descriptions.get(role, ""),
                permissions=[p.value for p in permissions],
                user_count=user_count,
            )
        )

    return roles_info


@router.post("/roles/assign", response_model=RoleAssignmentResponse)
async def assign_role_to_user(
    request: RoleAssignmentRequest,
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.ROLE_MANAGE)
    ),
    session: SessionDep = None,
    http_request: Request = None,
):
    """
    Assign a role to a user.

    Security:
    - Requires ROLE_MANAGE permission
    - Validates role assignments
    - Logs all assignments
    """
    # Validate input
    if request.notes and not validator.validate_pattern(request.notes, "safe_text"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid characters in notes",
        )

    # Check if target user exists
    target_user = session.get(User, request.user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Prevent self-assignment of admin roles
    if (
        request.user_id == current_user.id
        and request.role == SchedulingRole.SCHEDULING_ADMIN
    ):
        audit_logger.log_security_event(
            event_type="SELF_ADMIN_ASSIGNMENT_ATTEMPT",
            severity="HIGH",
            description="Attempted self-assignment of admin role",
            user_id=current_user.id,
            ip_address=http_request.client.host if http_request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot self-assign admin role",
        )

    # Use RoleManager to assign role
    role_manager = RoleManager(session)
    assignment = role_manager.assign_role(
        user_id=request.user_id,
        role=request.role,
        assigned_by=current_user.id,
        department=request.department,
        expires_at=request.expires_at,
        notes=request.notes,
    )

    session.add(assignment)
    session.commit()
    session.refresh(assignment)

    # Log role assignment
    audit_logger.log_security_event(
        event_type="ROLE_ASSIGNED",
        severity="INFO",
        description=f"Role {request.role.value} assigned to user {target_user.email}",
        user_id=current_user.id,
        ip_address=http_request.client.host if http_request.client else None,
        details={
            "target_user_id": str(request.user_id),
            "role": request.role.value,
            "department": request.department,
            "expires_at": request.expires_at.isoformat()
            if request.expires_at
            else None,
        },
    )

    return RoleAssignmentResponse(
        id=assignment.id,
        user_id=assignment.user_id,
        user_email=target_user.email,
        user_name=target_user.full_name,
        role=assignment.role,
        department=assignment.department,
        assigned_by=assignment.assigned_by,
        assigned_at=assignment.assigned_at,
        expires_at=assignment.expires_at,
        is_active=assignment.is_active,
        notes=assignment.notes,
    )


@router.delete("/roles/revoke/{assignment_id}")
async def revoke_role_assignment(
    assignment_id: UUID,
    reason: str = Body(..., min_length=10, max_length=500),
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.ROLE_MANAGE)
    ),
    session: SessionDep = None,
    request: Request = None,
):
    """
    Revoke a role assignment.

    Security:
    - Requires ROLE_MANAGE permission
    - Requires revocation reason
    - Maintains audit trail
    """
    # Get assignment
    assignment = session.get(RoleAssignment, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role assignment not found"
        )

    # Deactivate assignment
    assignment.is_active = False
    assignment.notes = f"Revoked by {current_user.id}: {reason}"

    session.add(assignment)
    session.commit()

    # Clear permission cache for user
    permission_service = PermissionService(session)
    permission_service.clear_cache(assignment.user_id)

    # Log revocation
    audit_logger.log_security_event(
        event_type="ROLE_REVOKED",
        severity="WARNING",
        description=f"Role {assignment.role.value} revoked from user",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details={
            "assignment_id": str(assignment_id),
            "target_user_id": str(assignment.user_id),
            "role": assignment.role.value,
            "reason": reason,
        },
    )

    return {"message": "Role assignment revoked successfully"}


@router.get("/roles/user/{user_id}", response_model=list[RoleAssignmentResponse])
async def get_user_roles(
    user_id: UUID,
    include_inactive: bool = Query(False, description="Include inactive assignments"),
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.ROLE_MANAGE)
    ),
    session: SessionDep = None,
):
    """
    Get all role assignments for a user.

    Security: Requires ROLE_MANAGE permission.
    """
    # Get user
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Build query
    stmt = select(RoleAssignment).where(RoleAssignment.user_id == user_id)

    if not include_inactive:
        stmt = stmt.where(RoleAssignment.is_active)
        # Check expiration
        now = datetime.utcnow()
        stmt = stmt.where(
            (RoleAssignment.expires_at is None) | (RoleAssignment.expires_at > now)
        )

    assignments = session.exec(stmt).all()

    return [
        RoleAssignmentResponse(
            id=a.id,
            user_id=a.user_id,
            user_email=user.email,
            user_name=user.full_name,
            role=a.role,
            department=a.department,
            assigned_by=a.assigned_by,
            assigned_at=a.assigned_at,
            expires_at=a.expires_at,
            is_active=a.is_active,
            notes=a.notes,
        )
        for a in assignments
    ]


# Permission Management Endpoints
@router.get("/permissions", response_model=list[str])
async def list_all_permissions(
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.PERMISSION_MANAGE)
    ),
):
    """
    List all available permissions.

    Security: Requires PERMISSION_MANAGE permission.
    """
    return [p.value for p in SchedulingPermission]


@router.post("/permissions/override", response_model=PermissionOverrideResponse)
async def create_permission_override(
    override_request: PermissionOverrideRequest,
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.PERMISSION_MANAGE)
    ),
    session: SessionDep = None,
    request: Request = None,
):
    """
    Create a permission override for a user.

    Security:
    - Requires PERMISSION_MANAGE permission
    - Validates override requests
    - Logs all overrides
    """
    # Validate reason
    if not validator.validate_pattern(override_request.reason, "safe_text"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid characters in reason",
        )

    # Check if target user exists
    target_user = session.get(User, override_request.user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Prevent granting admin permissions via override
    admin_permissions = [
        SchedulingPermission.ROLE_MANAGE,
        SchedulingPermission.PERMISSION_MANAGE,
        SchedulingPermission.SYSTEM_CONFIG,
    ]

    if override_request.permission in admin_permissions and override_request.grant:
        audit_logger.log_security_event(
            event_type="ADMIN_PERMISSION_OVERRIDE_ATTEMPT",
            severity="HIGH",
            description="Attempted to grant admin permission via override",
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            details={
                "target_user_id": str(override_request.user_id),
                "permission": override_request.permission.value,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot grant admin permissions via override. Use role assignment instead.",
        )

    # Create override
    override = PermissionOverride(
        user_id=override_request.user_id,
        permission=override_request.permission,
        grant=override_request.grant,
        reason=override_request.reason,
        approved_by=current_user.id,
        expires_at=override_request.expires_at,
        is_active=True,
    )

    session.add(override)
    session.commit()
    session.refresh(override)

    # Clear permission cache for user
    permission_service = PermissionService(session)
    permission_service.clear_cache(override.user_id)

    # Log override
    audit_logger.log_security_event(
        event_type="PERMISSION_OVERRIDE_CREATED",
        severity="WARNING",
        description=f"Permission override created for {target_user.email}",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details={
            "target_user_id": str(override_request.user_id),
            "permission": override_request.permission.value,
            "grant": override_request.grant,
            "reason": override_request.reason,
        },
    )

    return PermissionOverrideResponse(
        id=override.id,
        user_id=override.user_id,
        user_email=target_user.email,
        permission=override.permission,
        grant=override.grant,
        reason=override.reason,
        approved_by=override.approved_by,
        created_at=override.created_at,
        expires_at=override.expires_at,
        is_active=override.is_active,
    )


@router.get("/permissions/user/{user_id}", response_model=UserPermissionsResponse)
async def get_user_permissions(
    user_id: UUID,
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.PERMISSION_MANAGE)
    ),
    session: SessionDep = None,
):
    """
    Get all permissions for a user including role-based and overrides.

    Security: Requires PERMISSION_MANAGE permission.
    """
    # Check if user exists
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Get permissions
    permission_service = PermissionService(session)
    permissions = permission_service.get_user_permissions(user_id)

    # Get roles
    role_manager = RoleManager(session)
    roles = role_manager.get_user_roles(user_id)

    # Get data scopes
    data_scopes = permission_service.get_data_scopes(user_id)

    return UserPermissionsResponse(
        user_id=user_id,
        roles=[
            {
                "role": r.role.value,
                "department": r.department,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            }
            for r in roles
        ],
        permissions=[p.value for p in permissions],
        data_scopes=data_scopes,
        last_updated=datetime.utcnow(),
    )


# Data Scope Management
@router.post("/scopes", response_model=DataScopeResponse)
async def create_data_scope(
    user_id: UUID = Body(...),
    scope_type: str = Body(..., min_length=1, max_length=50),
    scope_value: str = Body(..., min_length=1, max_length=100),
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.PERMISSION_MANAGE)
    ),
    session: SessionDep = None,
    request: Request = None,
):
    """
    Create a data scope restriction for a user.

    Security:
    - Requires PERMISSION_MANAGE permission
    - Validates scope values
    - Logs all scope changes
    """
    # Validate inputs
    valid_scope_types = ["department", "location", "team", "job_type", "machine_group"]
    if scope_type not in valid_scope_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope type. Must be one of: {', '.join(valid_scope_types)}",
        )

    if not validator.validate_pattern(scope_value, "alphanumeric_dash"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid characters in scope value",
        )

    # Check if user exists
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Create scope
    scope = DataScope(
        user_id=user_id,
        scope_type=scope_type,
        scope_value=scope_value,
        created_by=current_user.id,
        is_active=True,
    )

    session.add(scope)
    session.commit()
    session.refresh(scope)

    # Log scope creation
    audit_logger.log_security_event(
        event_type="DATA_SCOPE_CREATED",
        severity="INFO",
        description=f"Data scope created for user {user.email}",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details={
            "target_user_id": str(user_id),
            "scope_type": scope_type,
            "scope_value": scope_value,
        },
    )

    return DataScopeResponse(
        id=scope.id,
        user_id=scope.user_id,
        scope_type=scope.scope_type,
        scope_value=scope.scope_value,
        created_at=scope.created_at,
        created_by=scope.created_by,
        is_active=scope.is_active,
    )


@router.get("/scopes/user/{user_id}", response_model=list[DataScopeResponse])
async def get_user_data_scopes(
    user_id: UUID,
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.PERMISSION_MANAGE)
    ),
    session: SessionDep = None,
):
    """
    Get all data scopes for a user.

    Security: Requires PERMISSION_MANAGE permission.
    """
    scopes = session.exec(
        select(DataScope).where(
            DataScope.user_id == user_id, DataScope.is_active
        )
    ).all()

    return [
        DataScopeResponse(
            id=s.id,
            user_id=s.user_id,
            scope_type=s.scope_type,
            scope_value=s.scope_value,
            created_at=s.created_at,
            created_by=s.created_by,
            is_active=s.is_active,
        )
        for s in scopes
    ]


# Audit Log Endpoints
@router.get("/audit/rbac", response_model=list[AuditLogEntry])
async def get_rbac_audit_logs(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    user_id: UUID | None = Query(None),
    event_type: str | None = Query(None),
    limit: int = Query(100, le=1000),
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.AUDIT_VIEW)
    ),
):
    """
    Get RBAC-related audit logs.

    Security: Requires AUDIT_VIEW permission.
    """
    # This would query actual audit log storage
    # For now, return placeholder
    return []


@router.get("/audit/access-violations", response_model=list[AuditLogEntry])
async def get_access_violations(
    hours: int = Query(24, description="Hours to look back"),
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.AUDIT_VIEW)
    ),
):
    """
    Get recent access violations and security events.

    Security: Requires AUDIT_VIEW permission.
    """
    # This would query actual security event logs
    # For now, return placeholder
    return []


# Statistics and Reporting
@router.get("/stats/permissions")
async def get_permission_statistics(
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.PERMISSION_MANAGE)
    ),
    session: SessionDep = None,
):
    """
    Get statistics about permission usage.

    Security: Requires PERMISSION_MANAGE permission.
    """
    # Count users per role
    role_counts = {}
    for role in SchedulingRole:
        count = session.exec(
            select(func.count(RoleAssignment.id)).where(
                RoleAssignment.role == role, RoleAssignment.is_active
            )
        ).one()
        role_counts[role.value] = count

    # Count permission overrides
    override_count = session.exec(
        select(func.count(PermissionOverride.id)).where(
            PermissionOverride.is_active
        )
    ).one()

    # Count data scopes
    scope_count = session.exec(
        select(func.count(DataScope.id)).where(DataScope.is_active)
    ).one()

    return {
        "role_distribution": role_counts,
        "total_users_with_roles": sum(role_counts.values()),
        "active_permission_overrides": override_count,
        "active_data_scopes": scope_count,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/cache/clear")
async def clear_permission_cache(
    user_id: UUID | None = Body(None, description="Clear cache for specific user"),
    current_user: CurrentUser = Depends(
        require_scheduling_permission(SchedulingPermission.SYSTEM_CONFIG)
    ),
    session: SessionDep = None,
):
    """
    Clear permission cache.

    Security: Requires SYSTEM_CONFIG permission.
    """
    permission_service = PermissionService(session)

    if user_id:
        permission_service.clear_cache(user_id)
        message = f"Cache cleared for user {user_id}"
    else:
        permission_service.clear_cache()
        message = "Permission cache cleared for all users"

    # Log cache clear
    audit_logger.log_security_event(
        event_type="CACHE_CLEARED",
        severity="INFO",
        description=message,
        user_id=current_user.id,
    )

    return {"message": message}
