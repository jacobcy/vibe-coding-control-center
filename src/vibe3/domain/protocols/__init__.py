"""Domain layer protocol definitions.

These protocols define interfaces for services that remain in the orchestra
adapter layer but are needed by domain layer components.

This enables the domain layer to depend on abstractions (protocols) rather
than concrete implementations, following the dependency inversion principle.
"""

from vibe3.domain.protocols.core_protocols import (
    ExecutionCoordinatorProtocol,
    RoleFactoryProtocol,
)
from vibe3.domain.protocols.core_protocols import (
    FlowServiceProtocol as CoreFlowServiceProtocol,
)
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
    TriggerableRoleDefinitionProtocol,
)
from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol
from vibe3.domain.protocols.infra_protocols import (
    ConfigLoaderProtocol,
    GitClientProtocol,
)
from vibe3.domain.protocols.orchestra_protocols import (
    AppendGovernanceEventProtocol,
    FailedGateProtocol,
    OrchestraEventLogProtocol,
)

__all__ = [
    "AppendGovernanceEventProtocol",
    "CapacityServiceProtocol",
    "CheckServiceProtocol",
    "ConfigLoaderProtocol",
    "CoreFlowServiceProtocol",
    "DispatchHealthCheckProtocol",
    "ExecutionCoordinatorProtocol",
    "FailedGateProtocol",
    "FlowContextResolverProtocol",
    "FlowServiceProtocol",
    "FlowManagerProtocol",
    "GitClientProtocol",
    "IssueCollectionServiceProtocol",
    "IssueLoaderProtocol",
    "LabelDispatchCallable",
    "OrchestraEventLogProtocol",
    "QueuePersistenceServiceProtocol",
    "QueueSelectorProtocol",
    "RoleFactoryProtocol",
    "TriggerableRoleDefinitionProtocol",
]
