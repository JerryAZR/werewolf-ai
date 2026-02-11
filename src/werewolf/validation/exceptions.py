"""Validation exceptions."""

from typing import List
from .types import ValidationViolation


class ValidationError(Exception):
    """Raised when one or more validation violations are detected.

    This exception is used for fail-fast behavior during development/testing.
    Production uses NoOpValidator which never raises.
    """

    def __init__(self, violations: List[ValidationViolation]):
        self.violations = violations
        count = len(violations)
        error_violations = sum(1 for v in violations if v.severity.value == "error")
        msg = f"Validation failed with {count} violation(s) ({error_violations} errors)"
        super().__init__(msg)

    def __str__(self) -> str:
        if not self.violations:
            return "ValidationError(no violations)"
        lines = [f"ValidationError({len(self.violations)} violations):"]
        for v in self.violations:
            lines.append(f"  [{v.severity.value.upper()}] {v.rule_id}: {v.message}")
        return "\n".join(lines)
