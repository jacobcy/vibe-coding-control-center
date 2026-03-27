"""PR command helpers."""

from contextlib import contextmanager
from typing import Iterator

from vibe3.services.base_resolution_usecase import BaseResolutionUsecase


@contextmanager
def noop_context() -> Iterator[None]:
    """No-op context manager for trace=False cases."""
    yield


def build_base_resolution_usecase() -> BaseResolutionUsecase:
    """Construct shared base resolver for PR/review commands."""
    return BaseResolutionUsecase()
