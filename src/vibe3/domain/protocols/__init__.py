"""Domain layer protocol definitions.

These protocols define interfaces for services that remain in the orchestra
adapter layer but are needed by domain layer components.

This enables the domain layer to depend on abstractions (protocols) rather
than concrete implementations, following the dependency inversion principle.
"""

from vibe3.domain.protocols.dispatch_protocols import (
    DispatchHealthCheckProtocol,
    IssueCollectionServiceProtocol,
    QueuePersistenceServiceProtocol,
)

__all__ = [
    "DispatchHealthCheckProtocol",
    "IssueCollectionServiceProtocol",
    "QueuePersistenceServiceProtocol",
]
