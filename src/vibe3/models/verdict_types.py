"""Verdict type definitions for handoff chain.

This module contains the core verdict type definition that is shared
between models and services layers, breaking the circular dependency.
"""

from typing import Literal

VerdictValue = Literal["PASS", "MINOR", "MAJOR", "BLOCK", "REFUSE", "UNKNOWN"]
