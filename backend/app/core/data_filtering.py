"""
Data Filtering Service

Implements row-level security and data filtering based on user permissions and scopes.
Ensures users only access data they are authorized to view or modify.

Security Features:
- Row-level security enforcement
- Department-based filtering
- Hierarchical data access
- Query modification for scoped access
- OWASP compliant implementation
"""

import logging
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import Session, SQLModel, or_, select

from app.core.rbac import PermissionService, SchedulingRole
from app.core.security_enhanced import AuditLogger

logger = logging.getLogger(__name__)
audit_logger = AuditLogger()


class DataAccessLevel(str, Enum):
    """
    Data access levels for filtering.

    OWASP Reference: A01:2021 - Broken Access Control
    """

    GLOBAL = "global"  # Access to all data
    DEPARTMENT = "department"  # Access to department data
    TEAM = "team"  # Access to team data
    PERSONAL = "personal"  # Access to own data only


class FilteringStrategy(str, Enum):
    """Strategies for applying data filters."""

    STRICT = "strict"  # Most restrictive access
    HIERARCHICAL = "hierarchical"  # Based on org hierarchy
    CUSTOM = "custom"  # Custom filtering rules


class DataFilteringService:
    """
    Service for applying data filtering based on user permissions.

    Security Features:
    - Automatic query filtering
    - Response data masking
    - Field-level security
    - Audit trail of data access
    """

    def __init__(self, session: Session):
        self.session = session
        self.permission_service = PermissionService(session)

    def get_user_data_level(
        self, user_id: UUID, role: SchedulingRole
    ) -> DataAccessLevel:
        """
        Determine user's data access level based on role.

        Security: Maps roles to appropriate data access levels.
        """
        # Admin roles have global access
        if role == SchedulingRole.SCHEDULING_ADMIN:
            return DataAccessLevel.GLOBAL

        # Supervisors have department-level access
        elif role == SchedulingRole.SUPERVISOR:
            return DataAccessLevel.DEPARTMENT

        # Planners have team-level access
        elif role == SchedulingRole.PLANNER:
            return DataAccessLevel.TEAM

        # Operators and viewers have personal access
        else:
            return DataAccessLevel.PERSONAL

    def filter_job_query(
        self,
        query: Any,
        user_id: UUID,
        role: SchedulingRole,
        scopes: dict[str, list[str]],
    ) -> Any:
        """
        Filter job query based on user's access rights.

        Security: Ensures users only see authorized jobs.
        """
        access_level = self.get_user_data_level(user_id, role)

        if access_level == DataAccessLevel.GLOBAL:
            # No filtering needed
            return query

        elif access_level == DataAccessLevel.DEPARTMENT:
            # Filter by department
            if "department" in scopes:
                departments = scopes["department"]
                # Assuming Job model has department field
                query = query.filter(Job.department.in_(departments))
            else:
                # No department scope defined, restrict to none
                query = query.filter(Job.id is None)

        elif access_level == DataAccessLevel.TEAM:
            # Filter by team or assigned jobs
            if "team" in scopes:
                teams = scopes["team"]
                query = query.filter(Job.team.in_(teams))
            elif "assigned_jobs" in scopes:
                job_ids = scopes["assigned_jobs"]
                query = query.filter(Job.id.in_(job_ids))
            else:
                # Restrict to jobs created by user
                query = query.filter(Job.created_by == user_id)

        elif access_level == DataAccessLevel.PERSONAL:
            # Only jobs assigned to or created by user
            query = query.filter(
                or_(Job.assigned_to == user_id, Job.created_by == user_id)
            )

        # Log data filtering
        audit_logger.log_security_event(
            event_type="DATA_FILTER_APPLIED",
            severity="INFO",
            description=f"Job query filtered for {access_level.value} access",
            user_id=user_id,
            details={
                "access_level": access_level.value,
                "role": role.value,
                "scopes": scopes,
            },
        )

        return query

    def filter_schedule_query(
        self,
        query: Any,
        user_id: UUID,
        role: SchedulingRole,
        scopes: dict[str, list[str]],
    ) -> Any:
        """
        Filter schedule query based on user's access rights.

        Security: Controls access to scheduling information.
        """
        access_level = self.get_user_data_level(user_id, role)

        if access_level == DataAccessLevel.GLOBAL:
            return query

        elif access_level == DataAccessLevel.DEPARTMENT:
            if "department" in scopes:
                departments = scopes["department"]
                # Filter schedules by department
                query = query.filter(Schedule.department.in_(departments))
            else:
                query = query.filter(Schedule.id is None)

        elif access_level == DataAccessLevel.TEAM:
            # Filter by visibility settings
            query = query.filter(
                or_(
                    Schedule.visibility == "public",
                    Schedule.created_by == user_id,
                    Schedule.shared_with.contains([user_id]),
                )
            )

        elif access_level == DataAccessLevel.PERSONAL:
            # Only schedules explicitly shared with user
            query = query.filter(
                or_(
                    Schedule.assigned_operators.contains([user_id]),
                    Schedule.created_by == user_id,
                )
            )

        return query

    def filter_operator_query(
        self,
        query: Any,
        user_id: UUID,
        role: SchedulingRole,
        scopes: dict[str, list[str]],
    ) -> Any:
        """
        Filter operator query based on user's access rights.

        Security: Protects operator personal information.
        """
        access_level = self.get_user_data_level(user_id, role)

        if access_level == DataAccessLevel.GLOBAL:
            return query

        elif access_level == DataAccessLevel.DEPARTMENT:
            if "department" in scopes:
                departments = scopes["department"]
                query = query.filter(Operator.department.in_(departments))
            else:
                # Only show self
                query = query.filter(Operator.id == user_id)

        elif access_level == DataAccessLevel.TEAM:
            if "team" in scopes:
                teams = scopes["team"]
                query = query.filter(Operator.team.in_(teams))
            else:
                query = query.filter(Operator.id == user_id)

        elif access_level == DataAccessLevel.PERSONAL:
            # Only see own profile
            query = query.filter(Operator.id == user_id)

        return query

    def filter_machine_query(
        self,
        query: Any,
        user_id: UUID,
        role: SchedulingRole,
        scopes: dict[str, list[str]],
    ) -> Any:
        """
        Filter machine query based on user's access rights.

        Security: Controls access to machine information.
        """
        access_level = self.get_user_data_level(user_id, role)

        if access_level in [DataAccessLevel.GLOBAL, DataAccessLevel.DEPARTMENT]:
            # Machines are generally visible at department level
            if "location" in scopes:
                locations = scopes["location"]
                query = query.filter(Machine.location.in_(locations))
            return query

        elif access_level == DataAccessLevel.TEAM:
            # Filter by machines the team can use
            if "authorized_machines" in scopes:
                machine_ids = scopes["authorized_machines"]
                query = query.filter(Machine.id.in_(machine_ids))
            else:
                # Show all non-restricted machines
                query = query.filter(not Machine.restricted)

        elif access_level == DataAccessLevel.PERSONAL:
            # Only machines operator is certified for
            if "certified_machines" in scopes:
                machine_ids = scopes["certified_machines"]
                query = query.filter(Machine.id.in_(machine_ids))
            else:
                query = query.filter(Machine.id is None)

        return query

    def mask_sensitive_fields(
        self,
        data: dict[str, Any],
        user_id: UUID,
        role: SchedulingRole,
        resource_type: str,
    ) -> dict[str, Any]:
        """
        Mask sensitive fields in response data.

        Security: Prevents exposure of sensitive information.
        """
        masked_data = data.copy()

        # Define sensitive fields per resource type
        sensitive_fields = {
            "operator": [
                "ssn",
                "salary",
                "home_address",
                "phone_number",
                "emergency_contact",
            ],
            "job": ["cost_estimate", "profit_margin", "customer_contact"],
            "machine": ["purchase_cost", "maintenance_cost", "vendor_contact"],
            "schedule": ["internal_notes", "cost_analysis"],
        }

        # Determine what fields to mask based on role
        if role not in [SchedulingRole.SCHEDULING_ADMIN, SchedulingRole.SUPERVISOR]:
            fields_to_mask = sensitive_fields.get(resource_type, [])

            for field in fields_to_mask:
                if field in masked_data:
                    # Replace with masked value
                    masked_data[field] = "***REDACTED***"

                    # Log field masking
                    logger.debug(
                        f"Masked field {field} for user {user_id} with role {role.value}"
                    )

        return masked_data

    def apply_field_level_security(
        self,
        model_instance: Any,
        user_id: UUID,
        role: SchedulingRole,
        operation: str = "read",
    ) -> Any:
        """
        Apply field-level security to model instances.

        Security: Granular control over field access.
        """
        # Define field access rules
        field_rules = {
            "Operator": {
                "read": {
                    SchedulingRole.OPERATOR: ["id", "name", "skills", "availability"],
                    SchedulingRole.PLANNER: [
                        "id",
                        "name",
                        "skills",
                        "availability",
                        "efficiency",
                    ],
                    SchedulingRole.SUPERVISOR: ["*"],  # All fields
                    SchedulingRole.SCHEDULING_ADMIN: ["*"],
                },
                "write": {
                    SchedulingRole.OPERATOR: ["availability", "skills"],
                    SchedulingRole.PLANNER: ["availability", "skills", "assignments"],
                    SchedulingRole.SUPERVISOR: ["*"],
                    SchedulingRole.SCHEDULING_ADMIN: ["*"],
                },
            },
            "Job": {
                "read": {
                    SchedulingRole.OPERATOR: [
                        "id",
                        "job_number",
                        "tasks",
                        "due_date",
                        "status",
                    ],
                    SchedulingRole.PLANNER: ["*"],
                    SchedulingRole.SUPERVISOR: ["*"],
                    SchedulingRole.SCHEDULING_ADMIN: ["*"],
                },
                "write": {
                    SchedulingRole.OPERATOR: ["status", "progress"],
                    SchedulingRole.PLANNER: ["*"],
                    SchedulingRole.SUPERVISOR: ["*"],
                    SchedulingRole.SCHEDULING_ADMIN: ["*"],
                },
            },
        }

        model_name = type(model_instance).__name__

        if model_name in field_rules and operation in field_rules[model_name]:
            allowed_fields = field_rules[model_name][operation].get(role, [])

            if "*" not in allowed_fields:
                # Create filtered instance with only allowed fields
                filtered_data = {}
                for field in allowed_fields:
                    if hasattr(model_instance, field):
                        filtered_data[field] = getattr(model_instance, field)

                # Return filtered version
                return type(model_instance)(**filtered_data)

        return model_instance

    def check_resource_ownership(
        self, resource_type: str, resource_id: UUID, user_id: UUID, operation: str
    ) -> bool:
        """
        Check if user owns or has access to a resource.

        Security: Verifies resource ownership before operations.
        """
        ownership_rules = {
            "job": {
                "read": lambda r, u: r.created_by == u
                or r.assigned_to == u
                or r.visibility == "public",
                "write": lambda r, u: r.created_by == u or r.assigned_to == u,
                "delete": lambda r, u: r.created_by == u,
            },
            "schedule": {
                "read": lambda r, u: r.created_by == u
                or u in r.shared_with
                or r.visibility == "public",
                "write": lambda r, u: r.created_by == u or u in r.editors,
                "delete": lambda r, u: r.created_by == u,
            },
            "task": {
                "read": lambda r, u: True,  # Tasks are generally readable
                "write": lambda r, u: r.assigned_to == u or r.job.created_by == u,
                "delete": lambda r, u: r.job.created_by == u,
            },
        }

        if (
            resource_type in ownership_rules
            and operation in ownership_rules[resource_type]
        ):
            # Get resource from database
            # This is a placeholder - actual implementation would fetch the resource
            resource = self._get_resource(resource_type, resource_id)

            if resource:
                check_func = ownership_rules[resource_type][operation]
                has_access = check_func(resource, user_id)

                if not has_access:
                    audit_logger.log_security_event(
                        event_type="OWNERSHIP_CHECK_FAILED",
                        severity="WARNING",
                        description=f"Ownership check failed for {resource_type}",
                        user_id=user_id,
                        details={
                            "resource_type": resource_type,
                            "resource_id": str(resource_id),
                            "operation": operation,
                        },
                    )

                return has_access

        return False

    def _get_resource(self, resource_type: str, resource_id: UUID) -> Any | None:
        """Get resource from database (placeholder)."""
        # This would be implemented with actual model queries
        return None

    def create_scoped_query(
        self,
        model: type[SQLModel],
        user_id: UUID,
        base_filters: dict[str, Any] | None = None,
    ) -> Any:
        """
        Create a pre-filtered query based on user's scopes.

        Security: Ensures all queries are properly scoped.
        """
        # Get user's role and scopes
        from app.models import User

        user = self.session.get(User, user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Get user's role (would need to be added to User model)
        role = getattr(user, "role", SchedulingRole.VIEWER)

        # Get data scopes
        scopes = self.permission_service.get_data_scopes(user_id)

        # Start with base query
        query = select(model)

        # Apply base filters if provided
        if base_filters:
            for field, value in base_filters.items():
                if hasattr(model, field):
                    query = query.filter(getattr(model, field) == value)

        # Apply model-specific filtering
        model_name = model.__name__

        if model_name == "Job":
            query = self.filter_job_query(query, user_id, role, scopes)
        elif model_name == "Schedule":
            query = self.filter_schedule_query(query, user_id, role, scopes)
        elif model_name == "Operator":
            query = self.filter_operator_query(query, user_id, role, scopes)
        elif model_name == "Machine":
            query = self.filter_machine_query(query, user_id, role, scopes)

        return query


class HierarchicalAccessControl:
    """
    Implements hierarchical access control for organizational structures.

    Security: Manages access based on organizational hierarchy.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_subordinate_departments(self, department: str) -> list[str]:
        """Get all subordinate departments in hierarchy."""
        # This would be implemented based on organizational structure
        # For now, return a placeholder
        subordinates = {
            "engineering": ["mechanical", "electrical", "software"],
            "production": ["assembly", "quality", "packaging"],
            "operations": ["engineering", "production", "maintenance"],
        }

        return subordinates.get(department, [])

    def get_accessible_resources(
        self, user_id: UUID, resource_type: str, include_subordinates: bool = True
    ) -> list[UUID]:
        """
        Get list of resource IDs user can access.

        Security: Pre-computes accessible resources for efficient filtering.
        """
        accessible_ids = []

        # Get user's department and role
        # This would fetch from database
        user_department = "engineering"  # Placeholder
        user_role = SchedulingRole.SUPERVISOR  # Placeholder

        if user_role == SchedulingRole.SCHEDULING_ADMIN:
            # Admin can access everything
            return []  # Empty list means no filtering

        # Get resources in user's department
        if resource_type == "operator":
            # Get operators in department
            stmt = select(Operator.id).filter(Operator.department == user_department)

            if include_subordinates:
                subordinate_depts = self.get_subordinate_departments(user_department)
                stmt = stmt.filter(
                    or_(
                        Operator.department == user_department,
                        Operator.department.in_(subordinate_depts),
                    )
                )

            result = self.session.exec(stmt)
            accessible_ids = list(result)

        return accessible_ids

    def check_hierarchical_access(
        self, user_id: UUID, target_user_id: UUID, operation: str
    ) -> bool:
        """
        Check if user has hierarchical access to target user.

        Security: Enforces organizational hierarchy in access control.
        """
        # Get both users' positions in hierarchy
        # This would be implemented based on org structure

        # For now, simple placeholder logic
        if user_id == target_user_id:
            return True  # Users can always access their own data

        # Check if user is supervisor of target
        # This would check actual reporting structure

        return False


# Placeholder models for type hints (would use actual models)
class Job(SQLModel):
    id: UUID
    job_number: str
    department: str
    team: str
    created_by: UUID
    assigned_to: UUID | None
    visibility: str


class Schedule(SQLModel):
    id: UUID
    department: str
    visibility: str
    created_by: UUID
    shared_with: list[UUID]
    assigned_operators: list[UUID]
    editors: list[UUID]


class Operator(SQLModel):
    id: UUID
    department: str
    team: str


class Machine(SQLModel):
    id: UUID
    location: str
    restricted: bool
