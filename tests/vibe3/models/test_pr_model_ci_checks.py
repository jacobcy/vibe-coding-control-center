"""Tests for CICheck model and PRResponse.ci_checks field."""

from vibe3.models.pr import CICheck, PRResponse, PRState


class TestCICheckModel:
    """Test suite for CICheck model."""

    def test_ci_check_creation(self) -> None:
        """Test CICheck model instantiation."""
        check = CICheck(
            name="Test Check",
            state="SUCCESS",
            bucket="pass",
            link="https://github.com/test/repo/actions/runs/123",
        )

        assert check.name == "Test Check"
        assert check.state == "SUCCESS"
        assert check.bucket == "pass"
        assert check.link == "https://github.com/test/repo/actions/runs/123"

    def test_ci_check_serialization(self) -> None:
        """Test CICheck model serialization."""
        check = CICheck(
            name="Build",
            state="FAILURE",
            bucket="fail",
            link="https://github.com/test/repo/actions/runs/456",
        )

        data = check.model_dump()
        assert data == {
            "name": "Build",
            "state": "FAILURE",
            "bucket": "fail",
            "link": "https://github.com/test/repo/actions/runs/456",
        }


class TestPRResponseCIChecks:
    """Test suite for PRResponse.ci_checks field."""

    def test_pr_response_default_ci_checks_empty(self) -> None:
        """Test that ci_checks defaults to empty list."""
        pr = PRResponse(
            number=123,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="feature",
            base_branch="main",
            url="https://github.com/test/repo/pull/123",
        )

        assert pr.ci_checks == []

    def test_pr_response_with_ci_checks(self) -> None:
        """Test PRResponse with ci_checks field."""
        checks = [
            CICheck(
                name="Build",
                state="SUCCESS",
                bucket="pass",
                link="https://github.com/test/repo/actions/runs/1",
            ),
            CICheck(
                name="Test",
                state="FAILURE",
                bucket="fail",
                link="https://github.com/test/repo/actions/runs/2",
            ),
        ]

        pr = PRResponse(
            number=123,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="feature",
            base_branch="main",
            url="https://github.com/test/repo/pull/123",
            ci_checks=checks,
        )

        assert len(pr.ci_checks) == 2
        assert pr.ci_checks[0].name == "Build"
        assert pr.ci_checks[0].bucket == "pass"
        assert pr.ci_checks[1].name == "Test"
        assert pr.ci_checks[1].bucket == "fail"

    def test_pr_response_ci_checks_serialization(self) -> None:
        """Test that ci_checks is properly serialized in model_dump()."""
        checks = [
            CICheck(
                name="Lint",
                state="SUCCESS",
                bucket="pass",
                link="https://github.com/test/repo/actions/runs/3",
            )
        ]

        pr = PRResponse(
            number=456,
            title="Another PR",
            state=PRState.OPEN,
            head_branch="feature",
            base_branch="main",
            url="https://github.com/test/repo/pull/456",
            ci_checks=checks,
        )

        data = pr.model_dump()
        assert "ci_checks" in data
        assert len(data["ci_checks"]) == 1
        assert data["ci_checks"][0]["name"] == "Lint"
        assert data["ci_checks"][0]["bucket"] == "pass"
