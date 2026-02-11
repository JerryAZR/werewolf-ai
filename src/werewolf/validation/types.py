"""Validation types shared across all validators."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ValidationSeverity(str, Enum):
    """Severity level of a validation violation."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationViolation(BaseModel):
    """A single rule violation detected during validation."""

    rule_id: str  # e.g., "M.1", "D.1"
    category: str  # e.g., "State Consistency", "Night Actions - Werewolf"
    message: str  # Human-readable description
    severity: ValidationSeverity = ValidationSeverity.ERROR
    context: Optional[dict] = None  # Additional context for debugging
    event_type: Optional[str] = None  # Event class name if applicable


class ValidationResult(BaseModel):
    """Result of a validation check."""

    is_valid: bool = True
    violations: list[ValidationViolation] = []

    def __bool__(self) -> bool:
        return self.is_valid

    def __add__(self, other: "ValidationResult") -> "ValidationResult":
        """Merge two validation results."""
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            violations=self.violations + other.violations
        )
