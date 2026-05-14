#!/usr/bin/env python
"""Test to check if pytest changes working directory."""
import os
import pytest

def test_cwd_check(tmp_path):
    """Check what the current working directory is during test execution."""
    print(f"\ntmp_path: {tmp_path}")
    print(f"cwd: {os.getcwd()}")
    print(f"tmp_path == cwd: {tmp_path == os.getcwd()}")
    print(f"tmp_path in cwd: {str(tmp_path) in os.getcwd()}")
