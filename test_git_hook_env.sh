#!/bin/bash
echo "PWD: $PWD"
echo "GIT_DIR: ${GIT_DIR:-not set}"
echo "GIT_PREFIX: ${GIT_PREFIX:-not set}"
echo "Running test..."
uv run pytest tests/vibe3/integration/test_ci_parity.py::TestWorkingDirectoryIndependence::test_repo_root_detection_works_from_subdirectory -v --tb=short
