"""Validation tests for versioned inspect evidence models."""

import pytest
from pydantic import ValidationError

from vibe3.models import SourceRange


def test_source_range_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError):
        SourceRange(start_line=5, end_line=4)
