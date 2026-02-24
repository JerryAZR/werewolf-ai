"""Parsing utilities for LLM response extraction."""

import re


def extract_answer(raw_response: str) -> str:
    """Extract answer from LLM response, handling thinking wrappers.

    Priority:
    1. <answer>...</answer> wrapper (preferred)
    2. ANSWER: prefix
    3. Raw response (backward compatibility)

    Args:
        raw_response: The raw response string from the LLM

    Returns:
        The extracted answer string
    """
    # Try XML wrapper
    if match := re.search(
        r'<answer>(.*?)</answer>', raw_response, re.IGNORECASE | re.DOTALL
    ):
        return match.group(1).strip()

    # Try ANSWER: prefix
    if match := re.search(
        r'ANSWER:\s*(.+)', raw_response, re.IGNORECASE | re.DOTALL
    ):
        return match.group(1).strip()

    # Fallback: return raw response (backward compatibility)
    return raw_response.strip()
