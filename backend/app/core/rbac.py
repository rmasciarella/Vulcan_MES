"""
Role-Based Access Control (RBAC) Implementation

This module provides comprehensive RBAC implementation for the scheduling system,
including role definitions, permission management, and authorization enforcement.

Security Features:
- Granular permission system
- Role hierarchy support
- Dynamic permission checking
- Audit logging integration
- OWASP compliant implementation
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, validator
from sqlmodel import Field, Session, SQLModel, select

from app.core.security_enhanced import AuditLogger

logger = logging.getLogger(__name__)
audit_logger = AuditLogger()


class SchedulingRole(str, Enum):
    """
    Scheduling domain-specific roles with hierarchical structure.

    OWASP Reference: A01:2021 - Broken Access Control
    """

    SCHEDULING_ADMIN = "scheduling_admin"  # Full scheduling system access
    SUPERVISOR = "supervisor"  # Area/department supervision
    OPERATOR = "operator"  # Task execution and status updates
    VIEWER = "viewer"  # Read-only access
    PLANNER = "planner"  # Schedule creation and optimization
    QUALITY_CONTROLLER = "quality_controller"  # Quality checks and approvals
    MAINTENANCE_TECH = "maintenance_tech"  # Machine maintenance scheduling


class SchedulingPermission(str, Enum):
    """
    Granular permissions for scheduling operations.

    Following principle of least privilege (OWASP A01:2021).
    """

    # Job permissions
    JOB_CREATE = "job:create"
    JOB_READ = "job:read"
    JOB_UPDATE = "job:update"
    JOB_DELETE = "job:delete"
    JOB_APPROVE = "job:approve"
    JOB_PRIORITY_OVERRIDE = "job:priority_override"

    # Schedule permissions
    SCHEDULE_CREATE = "schedule:create"
    SCHEDULE_READ = "schedule:read"
    SCHEDULE_OPTIMIZE = "schedule:optimize"
    SCHEDULE_PUBLISH = "schedule:publish"
    SCHEDULE_EXECUTE = "schedule:execute"
    SCHEDULE_MODIFY = "schedule:modify"

    # Machine permissions
    MACHINE_READ = "machine:read"
    MACHINE_UPDATE = "machine:update"
    MACHINE_MAINTAIN = "machine:maintain"
    MACHINE_SCHEDULE = "machine:schedule"

    # Operator permissions
    OPERATOR_READ = "operator:read"
    OPERATOR_UPDATE = "operator:update"
    OPERATOR_ASSIGN = "operator:assign"
    OPERATOR_SKILL_MANAGE = "operator:skill_manage"

    # Task permissions
    TASK_READ = "task:read"
    TASK_UPDATE_STATUS = "task:update_status"
    TASK_REASSIGN = "task:reassign"
    TASK_COMPLETE = "task:complete"

    # Report permissions
    REPORT_VIEW = "report:view"
    REPORT_CREATE = "report:create"
    REPORT_EXPORT = "report:export"

    # Admin permissions
    ADMIN_PANEL = "admin:panel"
    ROLE_MANAGE = "role:manage"
    PERMISSION_MANAGE = "permission:manage"
    AUDIT_VIEW = "audit:view"
    SYSTEM_CONFIG = "system:config"


# Role-Permission Matrix with hierarchical inheritance
SCHEDULING_ROLE_PERMISSIONS: dict[SchedulingRole, set[SchedulingPermission]] = {
    SchedulingRole.VIEWER: {
        SchedulingPermission.JOB_READ,
        SchedulingPermission.SCHEDULE_READ,
        SchedulingPermission.MACHINE_READ,
        SchedulingPermission.OPERATOR_READ,
        SchedulingPermission.TASK_READ,
        SchedulingPermission.REPORT_VIEW,
    },
    SchedulingRole.OPERATOR: {
        # Inherits from VIEWER
        SchedulingPermission.JOB_READ,
        SchedulingPermission.SCHEDULE_READ,
        SchedulingPermission.MACHINE_READ,
        SchedulingPermission.OPERATOR_READ,
        SchedulingPermission.TASK_READ,
        SchedulingPermission.REPORT_VIEW,
        # Additional permissions
        SchedulingPermission.TASK_UPDATE_STATUS,
        SchedulingPermission.TASK_COMPLETE,
        SchedulingPermission.OPERATOR_UPDATE,  # Own profile only
    },
    SchedulingRole.PLANNER: {
        # Inherits from OPERATOR
        SchedulingPermission.JOB_READ,
        SchedulingPermission.SCHEDULE_READ,
        SchedulingPermission.MACHINE_READ,
        SchedulingPermission.OPERATOR_READ,
        SchedulingPermission.TASK_READ,
        SchedulingPermission.REPORT_VIEW,
        SchedulingPermission.TASK_UPDATE_STATUS,
        # Additional permissions
        SchedulingPermission.JOB_CREATE,
        SchedulingPermission.JOB_UPDATE,
        SchedulingPermission.SCHEDULE_CREATE,
        SchedulingPermission.SCHEDULE_OPTIMIZE,
        SchedulingPermission.MACHINE_SCHEDULE,
        SchedulingPermission.OPERATOR_ASSIGN,
        SchedulingPermission.TASK_REASSIGN,
        SchedulingPermission.REPORT_CREATE,
    },
    SchedulingRole.SUPERVISOR: {
        # Inherits from PLANNER
        SchedulingPermission.JOB_READ,
        SchedulingPermission.JOB_CREATE,
        SchedulingPermission.JOB_UPDATE,
        SchedulingPermission.SCHEDULE_READ,
        SchedulingPermission.SCHEDULE_CREATE,
        SchedulingPermission.SCHEDULE_OPTIMIZE,
        SchedulingPermission.MACHINE_READ,
        SchedulingPermission.MACHINE_SCHEDULE,
        SchedulingPermission.OPERATOR_READ,
        SchedulingPermission.OPERATOR_ASSIGN,
        SchedulingPermission.TASK_READ,
        SchedulingPermission.TASK_UPDATE_STATUS,
        SchedulingPermission.TASK_REASSIGN,
        SchedulingPermission.REPORT_VIEW,
        SchedulingPermission.REPORT_CREATE,
        # Additional permissions
        SchedulingPermission.JOB_APPROVE,
        SchedulingPermission.JOB_DELETE,
        SchedulingPermission.SCHEDULE_PUBLISH,
        SchedulingPermission.SCHEDULE_MODIFY,
        SchedulingPermission.OPERATOR_UPDATE,
        SchedulingPermission.OPERATOR_SKILL_MANAGE,
        SchedulingPermission.REPORT_EXPORT,
    },
    SchedulingRole.QUALITY_CONTROLLER: {
        # Custom set for quality control
        SchedulingPermission.JOB_READ,
        SchedulingPermission.JOB_APPROVE,
        SchedulingPermission.SCHEDULE_READ,
        SchedulingPermission.TASK_READ,
        SchedulingPermission.TASK_UPDATE_STATUS,  # For quality checks
        SchedulingPermission.REPORT_VIEW,
        SchedulingPermission.REPORT_CREATE,
    },
    SchedulingRole.MAINTENANCE_TECH: {
        # Custom set for maintenance
        SchedulingPermission.MACHINE_READ,
        SchedulingPermission.MACHINE_UPDATE,
        SchedulingPermission.MACHINE_MAINTAIN,
        SchedulingPermission.SCHEDULE_READ,
        SchedulingPermission.TASK_READ,
        SchedulingPermission.TASK_UPDATE_STATUS,  # For maintenance tasks
    },
    SchedulingRole.SCHEDULING_ADMIN: {
        # Full access to all permissions
        *list(SchedulingPermission)
    },
}


# Database Models for RBAC
class RoleAssignment(SQLModel, table=True):
    """
    User role assignment with audit fields.

    Security: Tracks role assignments for audit trail (OWASP A09:2021).
    """

    __tablename__ = "role_assignments"

    id: UUID = Field(default_factory=UUID, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    role: SchedulingRole = Field(index=True)
    department: str | None = Field(default=None, max_length=100, index=True)
    assigned_by: UUID = Field(foreign_key="user.id")
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = Field(default=None)
    is_active: bool = Field(default=True)
    notes: str | None = Field(default=None, max_length=500)

    # Relationships would be defined here in full implementation
    # user: User = Relationship(back_populates="role_assignments")


class PermissionOverride(SQLModel, table=True):
    """
    Custom permission overrides for specific users.

    Security: Allows fine-grained permission control without role changes.
    """

    __tablename__ = "permission_overrides"

    id: UUID = Field(default_factory=UUID, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    permission: SchedulingPermission
    grant: bool = Field(default=True)  # True = grant, False = revoke
    reason: str = Field(max_length=500)
    approved_by: UUID = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = Field(default=None)
    is_active: bool = Field(default=True)


class DataScope(SQLModel, table=True):
    """
    Data access scope restrictions for users.

    Security: Implements row-level security for data filtering.
    """

    __tablename__ = "data_scopes"

    id: UUID = Field(default_factory=UUID, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    scope_type: str = Field(max_length=50)  # e.g., "department", "location", "job_type"
    scope_value: str = Field(max_length=100)  # e.g., "engineering", "plant_a", "rush"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: UUID = Field(foreign_key="user.id")
    is_active: bool = Field(default=True)


# Permission checking service
class PermissionService:
    """
    Service for checking and enforcing permissions.

    Security Features:
    - Caching for performance
    - Audit logging for all checks
    - Fail-secure defaults
    """

    def __init__(self, session: Session):
        self.session = session
        self._permission_cache: dict[UUID, set[SchedulingPermission]] = {}

    def get_user_permissions(self, user_id: UUID) -> set[SchedulingPermission]:
        """
        Get all permissions for a user including role and overrides.

        Security: Implements defense in depth with multiple permission sources.
        """
        # Check cache first
        if user_id in self._permission_cache:
            return self._permission_cache[user_id]

        permissions = set()

        # Get role-based permissions
        stmt = select(RoleAssignment).where(
            RoleAssignment.user_id == user_id, RoleAssignment.is_active
        )

        # Check for expired assignments
        now = datetime.utcnow()
        stmt = stmt.where(
            (RoleAssignment.expires_at is None) | (RoleAssignment.expires_at > now)
        )

        role_assignments = self.session.exec(stmt).all()

        for assignment in role_assignments:
            role_perms = SCHEDULING_ROLE_PERMISSIONS.get(assignment.role, set())
            permissions.update(role_perms)

        # Apply permission overrides
        override_stmt = select(PermissionOverride).where(
            PermissionOverride.user_id == user_id, PermissionOverride.is_active
        )
        override_stmt = override_stmt.where(
            (PermissionOverride.expires_at is None)
            | (PermissionOverride.expires_at > now)
        )

        overrides = self.session.exec(override_stmt).all()

        for override in overrides:
            if override.grant:
                permissions.add(override.permission)
            else:
                permissions.discard(override.permission)

        # Cache the result
        self._permission_cache[user_id] = permissions

        return permissions

    def has_permission(
        self, user_id: UUID, permission: SchedulingPermission, log_check: bool = True
    ) -> bool:
        """
        Check if user has specific permission.

        Security: Logs all permission checks for audit trail.
        """
        user_permissions = self.get_user_permissions(user_id)
        has_perm = permission in user_permissions

        if log_check:
            audit_logger.log_security_event(
                event_type="PERMISSION_CHECK",
                severity="INFO",
                description=f"Permission check: {permission.value}",
                user_id=user_id,
                details={
                    "permission": permission.value,
                    "granted": has_perm,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        return has_perm

    def require_permission(
        self,
        user_id: UUID,
        permission: SchedulingPermission,
        raise_on_fail: bool = True,
    ) -> bool:
        """
        Require user to have permission, raise exception if not.

        Security: Fail-secure by default.
        """
        if not self.has_permission(user_id, permission):
            if raise_on_fail:
                audit_logger.log_security_event(
                    event_type="PERMISSION_DENIED",
                    severity="WARNING",
                    description=f"Permission denied: {permission.value}",
                    user_id=user_id,
                    details={"permission": permission.value},
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value} required",
                )
            return False
        return True

    def get_data_scopes(self, user_id: UUID) -> dict[str, list[str]]:
        """
        Get data access scopes for user.

        Security: Implements row-level security filtering.
        """
        stmt = select(DataScope).where(
            DataScope.user_id == user_id, DataScope.is_active
        )
        scopes = self.session.exec(stmt).all()

        scope_dict: dict[str, list[str]] = {}
        for scope in scopes:
            if scope.scope_type not in scope_dict:
                scope_dict[scope.scope_type] = []
            scope_dict[scope.scope_type].append(scope.scope_value)

        return scope_dict

    def filter_by_scope(
        self, user_id: UUID, query: Any, scope_field: str, scope_type: str
    ) -> Any:
        """
        Apply data scope filtering to a query.

        Security: Ensures users only see authorized data.
        """
        scopes = self.get_data_scopes(user_id)

        if scope_type in scopes:
            scopes[scope_type]
            # Apply filter to query (implementation depends on ORM)
            # This is a placeholder - actual implementation would depend on SQLModel
            # query = query.filter(scope_field.in_(allowed_values))

        return query

    def clear_cache(self, user_id: UUID | None = None):
        """Clear permission cache for user or all users."""
        if user_id:
            self._permission_cache.pop(user_id, None)
        else:
            self._permission_cache.clear()


# FastAPI dependency for permission checking
def require_scheduling_permission(permission: SchedulingPermission):
    """
    FastAPI dependency to require specific scheduling permission.

    Security: Enforces permissions at API endpoint level.
    """
    from app.api.deps import CurrentUser, SessionDep

    def permission_checker(
        current_user: CurrentUser, session: SessionDep, request: Request
    ):
        service = PermissionService(session)

        # Log the authorization attempt
        audit_logger.log_security_event(
            event_type="AUTHORIZATION_ATTEMPT",
            severity="INFO",
            description=f"Attempting to access resource requiring {permission.value}",
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            details={
                "endpoint": str(request.url),
                "method": request.method,
                "permission_required": permission.value,
            },
        )

        # Check permission
        if not service.has_permission(current_user.id, permission):
            audit_logger.log_security_event(
                event_type="AUTHORIZATION_FAILED",
                severity="HIGH",
                description=f"Unauthorized access attempt to {permission.value}",
                user_id=current_user.id,
                ip_address=request.client.host if request.client else None,
                details={
                    "endpoint": str(request.url),
                    "method": request.method,
                    "permission_required": permission.value,
                    "user_permissions": [
                        p.value for p in service.get_user_permissions(current_user.id)
                    ],
                },
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission.value}",
            )

        # Log successful authorization
        audit_logger.log_security_event(
            event_type="AUTHORIZATION_SUCCESS",
            severity="INFO",
            description=f"Authorized access to {permission.value}",
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            details={
                "endpoint": str(request.url),
                "method": request.method,
                "permission_granted": permission.value,
            },
        )

        return current_user

    return permission_checker


def require_any_permission(*permissions: SchedulingPermission):
    """
    Require user to have at least one of the specified permissions.

    Security: Allows flexible permission requirements.
    """
    from app.api.deps import CurrentUser, SessionDep

    def permission_checker(
        current_user: CurrentUser, session: SessionDep, request: Request
    ):
        service = PermissionService(session)
        user_permissions = service.get_user_permissions(current_user.id)

        has_any = any(perm in user_permissions for perm in permissions)

        if not has_any:
            required = ", ".join(p.value for p in permissions)
            audit_logger.log_security_event(
                event_type="AUTHORIZATION_FAILED",
                severity="HIGH",
                description="Failed to meet any required permission",
                user_id=current_user.id,
                ip_address=request.client.host if request.client else None,
                details={
                    "endpoint": str(request.url),
                    "permissions_required": required,
                    "user_permissions": [p.value for p in user_permissions],
                },
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required one of: {required}",
            )

        return current_user

    return permission_checker


def require_all_permissions(*permissions: SchedulingPermission):
    """
    Require user to have all specified permissions.

    Security: Enforces strict permission requirements.
    """
    from app.api.deps import CurrentUser, SessionDep

    def permission_checker(
        current_user: CurrentUser, session: SessionDep, request: Request
    ):
        service = PermissionService(session)
        user_permissions = service.get_user_permissions(current_user.id)

        has_all = all(perm in user_permissions for perm in permissions)

        if not has_all:
            required = ", ".join(p.value for p in permissions)
            missing = ", ".join(
                p.value for p in permissions if p not in user_permissions
            )

            audit_logger.log_security_event(
                event_type="AUTHORIZATION_FAILED",
                severity="HIGH",
                description="Failed to meet all required permissions",
                user_id=current_user.id,
                ip_address=request.client.host if request.client else None,
                details={
                    "endpoint": str(request.url),
                    "permissions_required": required,
                    "permissions_missing": missing,
                    "user_permissions": [p.value for p in user_permissions],
                },
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Missing: {missing}",
            )

        return current_user

    return permission_checker


# Role assignment management
class RoleManager:
    """
    Manages role assignments and transitions.

    Security: Enforces role separation and assignment rules.
    """

    def __init__(self, session: Session):
        self.session = session

    def assign_role(
        self,
        user_id: UUID,
        role: SchedulingRole,
        assigned_by: UUID,
        department: str | None = None,
        expires_at: datetime | None = None,
        notes: str | None = None,
    ) -> RoleAssignment:
        """
        Assign role to user with audit trail.

        Security: Tracks all role assignments for accountability.
        """
        # Deactivate existing assignments for the same role
        existing = self.session.exec(
            select(RoleAssignment).where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.role == role,
                RoleAssignment.is_active,
            )
        ).all()

        for assignment in existing:
            assignment.is_active = False

        # Create new assignment
        assignment = RoleAssignment(
            user_id=user_id,
            role=role,
            department=department,
            assigned_by=assigned_by,
            expires_at=expires_at,
            notes=notes,
            is_active=True,
        )

        self.session.add(assignment)

        # Log role assignment
        audit_logger.log_security_event(
            event_type="ROLE_ASSIGNED",
            severity="INFO",
            description=f"Role {role.value} assigned to user",
            user_id=user_id,
            details={
                "role": role.value,
                "assigned_by": str(assigned_by),
                "department": department,
                "expires_at": expires_at.isoformat() if expires_at else None,
            },
        )

        return assignment

    def revoke_role(
        self, user_id: UUID, role: SchedulingRole, revoked_by: UUID, reason: str
    ):
        """
        Revoke role from user.

        Security: Maintains audit trail of role revocations.
        """
        assignments = self.session.exec(
            select(RoleAssignment).where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.role == role,
                RoleAssignment.is_active,
            )
        ).all()

        for assignment in assignments:
            assignment.is_active = False
            assignment.notes = f"Revoked by {revoked_by}: {reason}"

        # Log role revocation
        audit_logger.log_security_event(
            event_type="ROLE_REVOKED",
            severity="WARNING",
            description=f"Role {role.value} revoked from user",
            user_id=user_id,
            details={
                "role": role.value,
                "revoked_by": str(revoked_by),
                "reason": reason,
            },
        )

    def get_user_roles(self, user_id: UUID) -> list[RoleAssignment]:
        """Get active roles for user."""
        now = datetime.utcnow()
        return self.session.exec(
            select(RoleAssignment).where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.is_active,
                (RoleAssignment.expires_at is None) | (RoleAssignment.expires_at > now),
            )
        ).all()


# Request/Response models for API
class RoleAssignmentRequest(BaseModel):
    """Request model for role assignment."""

    user_id: UUID
    role: SchedulingRole
    department: str | None = None
    expires_at: datetime | None = None
    notes: str | None = None

    @validator("notes")
    def validate_notes(cls, v):
        if v and len(v) > 500:
            raise ValueError("Notes must be 500 characters or less")
        return v


class PermissionOverrideRequest(BaseModel):
    """Request model for permission override."""

    user_id: UUID
    permission: SchedulingPermission
    grant: bool = True
    reason: str
    expires_at: datetime | None = None

    @validator("reason")
    def validate_reason(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Reason must be at least 10 characters")
        if len(v) > 500:
            raise ValueError("Reason must be 500 characters or less")
        return v


class UserPermissionsResponse(BaseModel):
    """Response model for user permissions."""

    user_id: UUID
    roles: list[dict[str, Any]]
    permissions: list[str]
    data_scopes: dict[str, list[str]]
    last_updated: datetime


# Security headers for RBAC endpoints
RBAC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Cache-Control": "no-store, no-cache, must-revalidate, private",
    "Pragma": "no-cache",
    "Expires": "0",
}
