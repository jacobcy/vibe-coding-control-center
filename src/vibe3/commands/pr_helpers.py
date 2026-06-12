"""PR command helpers."""

from vibe3.services import BaseResolutionUsecase


def build_base_resolution_usecase() -> BaseResolutionUsecase:
    """Construct shared base resolver for PR/review commands."""
    return BaseResolutionUsecase()
