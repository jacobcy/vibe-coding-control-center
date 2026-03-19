"""PR command helpers."""

from contextlib import contextmanager
from typing import Iterator


@contextmanager
def noop_context() -> Iterator[None]:
    """No-op context manager for trace=False cases."""
    yield
