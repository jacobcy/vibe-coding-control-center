"""Human renderer tests for inspect base evidence."""

from typer.testing import CliRunner

from vibe3.commands.inspect_base_helpers import render_review_observation
from vibe3.models.inspect_evidence import ReviewObservation

runner = CliRunner()


def test_render_error_observation_does_not_claim_no_changes() -> None:
    observation = ReviewObservation(status="error")

    output = render_review_observation(observation)

    assert "Observation status: error" in output
    assert "No files changed" not in output
