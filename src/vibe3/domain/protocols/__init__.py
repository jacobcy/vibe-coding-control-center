"""Domain layer protocol definitions.

These protocols define interfaces for services that remain in the orchestra
adapter layer but are needed by domain layer components.

This enables the domain layer to depend on abstractions (protocols) rather
than concrete implementations, following the dependency inversion principle.
"""

from vibe3.domain.protocols.dispatch_protocols import (
    CapacityServiceProtocol,
    CheckServiceProtocol,
    DispatchHealthCheckProtocol,
    FlowContextResolverProtocol,
    FlowServiceProtocol,
    IssueCollectionServiceProtocol,
    IssueLoaderProtocol,
    LabelDispatchCallable,
    QueuePersistenceServiceProtocol,
    QueueSelectorProtocol,
)
from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol
from vibe3.domain.protocols.infra_protocols import (
    ConfigLoaderProtocol,
    ExceptionFactoryProtocol,
    GitClientProtocol,
)

__all__ = [
    "CapacityServiceProtocol",
    "CheckServiceProtocol",
    "ConfigLoaderProtocol",
    "DispatchHealthCheckProtocol",
    "ExceptionFactoryProtocol",
    "FlowContextResolverProtocol",
    "FlowServiceProtocol",
    "FlowManagerProtocol",
    "GitClientProtocol",
    "IssueCollectionServiceProtocol",
    "IssueLoaderProtocol",
    "LabelDispatchCallable",
    "QueuePersistenceServiceProtocol",
    "QueueSelectorProtocol",
]
