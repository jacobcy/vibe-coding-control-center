from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService
from vibe3.roles.manager import MANAGER_ROLE


def test_manager_does_not_dispatch_when_live_session_exists(monkeypatch) -> None:
    service = StateLabelDispatchService(
        OrchestraConfig(),
        role_def=MANAGER_ROLE,
    )

    monkeypatch.setattr(service, "_has_live_dispatch", lambda issue_number: True)

    assert service._should_dispatch(340, flow_state={}) is False
