"""
Centralized validation configuration for domain entities.

Defines validation rules, constraints, and configuration settings used
across the scheduling domain. This provides a single source of truth
for validation parameters and business rules.
"""

import re
from datetime import timedelta
from decimal import Decimal
from re import Pattern
from typing import Any

# Field Length Constraints
FIELD_LENGTHS = {
    "job_number": {"min": 3, "max": 50},
    "customer_name": {"min": 1, "max": 100},
    "part_number": {"min": 1, "max": 50},
    "notes": {"min": 0, "max": 1000},
    "quality_notes": {"min": 0, "max": 500},
    "created_by": {"min": 0, "max": 100},
    "machine_code": {"min": 3, "max": 20},
    "machine_name": {"min": 1, "max": 100},
    "employee_id": {"min": 3, "max": 20},
    "first_name": {"min": 1, "max": 50},
    "last_name": {"min": 1, "max": 50},
    "email": {"min": 5, "max": 254},  # RFC 5322 standard
    "phone": {"min": 10, "max": 15},
}

# Numeric Range Constraints
NUMERIC_RANGES = {
    "task_sequence": {"min": 1, "max": 100},
    "current_operation_sequence": {"min": 0, "max": 100},
    "priority_level": {"min": 1, "max": 10},
    "quantity": {"min": 1, "max": 999999},
    "duration_minutes": {"min": 0, "max": 10080},  # Max 1 week
    "delay_minutes": {"min": 0, "max": 100800},  # Max 10 weeks
    "rework_count": {"min": 0, "max": 99},
    "efficiency_factor": {"min": Decimal("0.1"), "max": Decimal("2.0")},
}

# Pattern Validation Rules
VALIDATION_PATTERNS = {
    "job_number": re.compile(r"^[A-Z0-9_-]{3,50}$"),
    "machine_code": re.compile(r"^[A-Z0-9_-]{3,20}$"),
    "employee_id": re.compile(r"^[A-Z0-9_-]{3,20}$"),
    "part_number": re.compile(r"^[A-Z0-9_-]{1,50}$"),
    "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
    "phone_digits": re.compile(r"^[0-9]{10,11}$"),
    "alphanumeric_with_spaces": re.compile(r"^[A-Za-z0-9\s\-_\.]{1,}$"),
}

# Time Constraints
TIME_CONSTRAINTS = {
    "max_future_due_date": timedelta(days=365 * 2),  # 2 years max
    "min_future_due_date": timedelta(hours=1),  # At least 1 hour in future
    "max_task_duration": timedelta(hours=168),  # 1 week max
    "min_task_duration": timedelta(minutes=1),  # 1 minute min
    "max_setup_duration": timedelta(hours=24),  # 1 day max
    "skill_expiry_warning_days": 30,  # Warn 30 days before expiry
    "max_working_hours_per_day": timedelta(hours=16),  # 16 hours max per day
    "min_working_hours_per_day": timedelta(hours=1),  # 1 hour min per day
}

# Business Rules Configuration
BUSINESS_RULES = {
    "job_rules": {
        "require_due_date_in_future": True,
        "require_job_number_unique": True,
        "allow_job_modification_when_complete": False,
        "require_customer_for_external_jobs": False,
        "max_tasks_per_job": 100,
    },
    "task_rules": {
        "require_unique_sequence_per_job": True,
        "allow_concurrent_tasks_same_machine": False,
        "require_precedence_order": True,
        "allow_task_modification_in_progress": False,
        "max_operator_assignments": 5,
        "require_machine_for_production_tasks": False,
    },
    "machine_rules": {
        "require_machine_code_unique": True,
        "allow_overlapping_maintenance": False,
        "require_operator_for_manual_machines": True,
        "max_concurrent_tasks": 1,
        "require_capability_for_assignment": True,
    },
    "operator_rules": {
        "require_employee_id_unique": True,
        "allow_overlapping_assignments": False,
        "require_skill_certification": True,
        "max_concurrent_assignments": 3,
        "require_active_status_for_assignment": True,
    },
    "scheduling_rules": {
        "enforce_business_hours": True,
        "allow_weekend_scheduling": False,
        "require_buffer_between_tasks": True,
        "buffer_minutes": 15,
        "max_schedule_horizon_days": 90,
        "allow_resource_overbooking": False,
    },
}

# Error Message Templates
ERROR_MESSAGES = {
    "required_field": "{field_name} is required",
    "invalid_length": "{field_name} must be between {min_length} and {max_length} characters",
    "invalid_range": "{field_name} must be between {min_value} and {max_value}",
    "invalid_format": "{field_name} has invalid format",
    "invalid_email": "Invalid email address format",
    "invalid_phone": "Invalid phone number format",
    "duplicate_value": "{field_name} '{value}' already exists",
    "invalid_reference": "Referenced {entity_type} does not exist",
    "invalid_date_range": "End date must be after start date",
    "date_not_future": "Date must be in the future",
    "invalid_status_transition": "Cannot transition from {from_status} to {to_status}",
    "resource_conflict": "Resource conflict detected",
    "precedence_violation": "Task precedence constraint violated",
    "business_hours_violation": "Operation outside business hours not allowed",
    "capacity_exceeded": "Resource capacity exceeded",
}


# Validation Severity Levels
class ValidationSeverity:
    """Validation severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Critical Validation Rules (cannot be bypassed)
CRITICAL_VALIDATIONS = {
    "job_number_required",
    "due_date_required",
    "due_date_in_future",
    "task_sequence_required",
    "task_sequence_range",
    "machine_code_required",
    "machine_code_unique",
    "employee_id_required",
    "employee_id_unique",
    "no_resource_double_booking",
    "valid_foreign_key_references",
}

# Warning-level Validations (can be bypassed with approval)
WARNING_VALIDATIONS = {
    "efficiency_factor_unusual",
    "long_task_duration",
    "weekend_scheduling",
    "overtime_scheduling",
    "skill_certification_expiring",
    "high_work_in_progress",
}

# Sanitization Configuration
SANITIZATION_CONFIG = {
    "text_fields": {
        "strip_whitespace": True,
        "remove_control_chars": True,
        "normalize_unicode": True,
        "max_length_truncate": False,  # Fail instead of truncate
    },
    "code_fields": {
        "convert_to_uppercase": True,
        "strip_whitespace": True,
        "allow_chars": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    },
    "email_fields": {"convert_to_lowercase": True, "strip_whitespace": True},
    "phone_fields": {
        "strip_non_digits": True,
        "format_standard": False,  # Keep as digits only
    },
}

# Validation Rule Sets
VALIDATION_RULE_SETS = {
    "job_creation": [
        "job_number_required",
        "job_number_format",
        "job_number_unique",
        "due_date_required",
        "due_date_in_future",
        "quantity_positive",
        "customer_name_format",
        "part_number_format",
    ],
    "job_update": [
        "job_number_format",
        "due_date_in_future",
        "quantity_positive",
        "status_transition_valid",
        "planned_dates_consistent",
    ],
    "task_creation": [
        "task_sequence_required",
        "task_sequence_range",
        "task_sequence_unique_per_job",
        "job_reference_valid",
        "operation_reference_valid",
        "duration_positive",
        "machine_reference_valid",
    ],
    "task_scheduling": [
        "planned_time_range_valid",
        "no_resource_conflicts",
        "precedence_constraints",
        "business_hours_compliance",
        "capacity_constraints",
    ],
    "machine_creation": [
        "machine_code_required",
        "machine_code_format",
        "machine_code_unique",
        "machine_name_required",
        "efficiency_factor_range",
        "production_zone_reference_valid",
    ],
    "operator_creation": [
        "employee_id_required",
        "employee_id_format",
        "employee_id_unique",
        "first_name_required",
        "last_name_required",
        "email_format",
        "phone_format",
        "working_hours_valid",
    ],
}

# Custom Validation Functions Configuration
CUSTOM_VALIDATORS = {
    "scheduling_domain": {
        "job_number_format": "SchedulingValidators.validate_job_number_format",
        "task_sequence": "SchedulingValidators.validate_task_sequence",
        "efficiency_factor": "SchedulingValidators.validate_efficiency_factor",
        "duration_minutes": "SchedulingValidators.validate_duration_minutes",
    },
    "business_rules": {
        "future_date": "BusinessRuleValidators.validate_future_date",
        "date_range": "BusinessRuleValidators.validate_date_range",
        "positive_number": "BusinessRuleValidators.validate_positive_number",
        "value_range": "BusinessRuleValidators.validate_range",
    },
    "data_sanitization": {
        "sanitize_string": "DataSanitizer.sanitize_string",
        "sanitize_code": "DataSanitizer.sanitize_code",
        "sanitize_email": "DataSanitizer.sanitize_email",
        "sanitize_phone": "DataSanitizer.sanitize_phone",
    },
}

# Environment-specific Configuration
ENVIRONMENT_CONFIGS = {
    "development": {
        "strict_validation": False,
        "allow_test_data": True,
        "bypass_warnings": True,
        "detailed_errors": True,
    },
    "testing": {
        "strict_validation": True,
        "allow_test_data": True,
        "bypass_warnings": False,
        "detailed_errors": True,
    },
    "staging": {
        "strict_validation": True,
        "allow_test_data": False,
        "bypass_warnings": False,
        "detailed_errors": True,
    },
    "production": {
        "strict_validation": True,
        "allow_test_data": False,
        "bypass_warnings": False,
        "detailed_errors": False,  # Hide sensitive details in production
    },
}


def get_field_length_constraint(field_name: str) -> dict[str, int]:
    """Get length constraints for a field."""
    return FIELD_LENGTHS.get(field_name, {"min": 0, "max": 255})


def get_numeric_range_constraint(field_name: str) -> dict[str, Any]:
    """Get numeric range constraints for a field."""
    return NUMERIC_RANGES.get(field_name, {"min": 0, "max": None})


def get_validation_pattern(field_type: str) -> Pattern[str]:
    """Get validation pattern for a field type."""
    return VALIDATION_PATTERNS.get(field_type)


def is_critical_validation(rule_name: str) -> bool:
    """Check if a validation rule is critical."""
    return rule_name in CRITICAL_VALIDATIONS


def is_warning_validation(rule_name: str) -> bool:
    """Check if a validation rule is warning-level."""
    return rule_name in WARNING_VALIDATIONS


def get_validation_rules(rule_set_name: str) -> list[str]:
    """Get validation rules for a specific rule set."""
    return VALIDATION_RULE_SETS.get(rule_set_name, [])


def get_error_message(message_key: str, **kwargs) -> str:
    """Get formatted error message."""
    template = ERROR_MESSAGES.get(message_key, "Validation error occurred")
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def get_business_rule(category: str, rule_name: str) -> Any:
    """Get a specific business rule value."""
    return BUSINESS_RULES.get(category, {}).get(rule_name)


def should_enforce_business_hours() -> bool:
    """Check if business hours should be enforced."""
    return get_business_rule("scheduling_rules", "enforce_business_hours")


def get_max_concurrent_tasks() -> int:
    """Get maximum concurrent tasks per machine."""
    return get_business_rule("machine_rules", "max_concurrent_tasks")


def get_skill_expiry_warning_days() -> int:
    """Get number of days before skill expiry to warn."""
    return TIME_CONSTRAINTS["skill_expiry_warning_days"]


def get_environment_config(env: str = "production") -> dict[str, Any]:
    """Get environment-specific configuration."""
    return ENVIRONMENT_CONFIGS.get(env, ENVIRONMENT_CONFIGS["production"])
