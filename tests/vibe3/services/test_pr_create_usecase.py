"""Tests for PRCreateUsecase dependency injection behavior."""

from unittest.mock import MagicMock

from vibe3.services.pr_create_usecase import PRCreateUsecase


def test_pr_create_usecase_preserves_falsey_injected_dependencies() -> None:
    """Injected usecase collaborators should be preserved even if they are falsey."""
    flow_service = MagicMock()
    flow_service.__bool__.return_value = False
    base_resolver = MagicMock()
    base_resolver.__bool__.return_value = False

    usecase = PRCreateUsecase(
        flow_service=flow_service,
        base_resolver=base_resolver,
    )

    assert usecase._flow_service is flow_service
    assert usecase._base_resolver is base_resolver
