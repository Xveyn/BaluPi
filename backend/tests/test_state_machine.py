"""Tests for NAS state machine — transitions, persistence, edge cases."""

import json
import tempfile
from pathlib import Path

import pytest

from app.services.nas_state_machine import NasState, NasStateMachine


@pytest.fixture
def state_dir(tmp_path):
    """Provide a temp directory for state persistence."""
    return str(tmp_path)


@pytest.fixture
def sm(state_dir):
    """Fresh state machine with temp storage."""
    return NasStateMachine(state_dir=state_dir)


class TestInitialState:
    def test_starts_unknown(self, sm):
        assert sm.state == NasState.UNKNOWN

    def test_has_timestamp(self, sm):
        assert sm.since is not None


class TestValidTransitions:
    def test_unknown_to_online(self, sm):
        assert sm.transition(NasState.ONLINE) is True
        assert sm.state == NasState.ONLINE

    def test_unknown_to_offline(self, sm):
        assert sm.transition(NasState.OFFLINE) is True
        assert sm.state == NasState.OFFLINE

    def test_offline_to_booting(self, sm):
        sm.transition(NasState.OFFLINE)
        assert sm.transition(NasState.BOOTING) is True
        assert sm.state == NasState.BOOTING

    def test_booting_to_online(self, sm):
        sm.transition(NasState.OFFLINE)
        sm.transition(NasState.BOOTING)
        assert sm.transition(NasState.ONLINE) is True
        assert sm.state == NasState.ONLINE

    def test_online_to_shutting_down(self, sm):
        sm.transition(NasState.ONLINE)
        assert sm.transition(NasState.SHUTTING_DOWN) is True
        assert sm.state == NasState.SHUTTING_DOWN

    def test_shutting_down_to_offline(self, sm):
        sm.transition(NasState.ONLINE)
        sm.transition(NasState.SHUTTING_DOWN)
        assert sm.transition(NasState.OFFLINE) is True
        assert sm.state == NasState.OFFLINE

    def test_same_state_noop(self, sm):
        sm.transition(NasState.ONLINE)
        assert sm.transition(NasState.ONLINE) is True
        assert sm.state == NasState.ONLINE


class TestInvalidTransitions:
    def test_unknown_to_booting(self, sm):
        assert sm.transition(NasState.BOOTING) is False
        assert sm.state == NasState.UNKNOWN

    def test_offline_to_shutting_down(self, sm):
        sm.transition(NasState.OFFLINE)
        assert sm.transition(NasState.SHUTTING_DOWN) is False
        assert sm.state == NasState.OFFLINE

    def test_booting_to_shutting_down(self, sm):
        sm.transition(NasState.OFFLINE)
        sm.transition(NasState.BOOTING)
        assert sm.transition(NasState.SHUTTING_DOWN) is False
        assert sm.state == NasState.BOOTING


class TestPersistence:
    def test_state_persisted_to_disk(self, sm, state_dir):
        sm.transition(NasState.ONLINE)
        state_file = Path(state_dir) / "handshake" / "nas_state.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["state"] == "online"

    def test_state_restored_from_disk(self, state_dir):
        sm1 = NasStateMachine(state_dir=state_dir)
        sm1.transition(NasState.ONLINE)

        sm2 = NasStateMachine(state_dir=state_dir)
        assert sm2.state == NasState.ONLINE

    def test_corrupt_state_file_resets(self, state_dir):
        state_dir_path = Path(state_dir) / "handshake"
        state_dir_path.mkdir(parents=True)
        (state_dir_path / "nas_state.json").write_text("invalid json")

        sm = NasStateMachine(state_dir=state_dir)
        assert sm.state == NasState.UNKNOWN


class TestForceState:
    def test_force_bypasses_validation(self, sm):
        sm.force_state(NasState.SHUTTING_DOWN)
        assert sm.state == NasState.SHUTTING_DOWN

    def test_to_dict(self, sm):
        sm.transition(NasState.ONLINE)
        d = sm.to_dict()
        assert d["state"] == "online"
        assert "since" in d
