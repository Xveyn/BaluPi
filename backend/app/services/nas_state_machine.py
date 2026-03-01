"""NAS state machine with JSON persistence and transition validation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class NasState(str, Enum):
    UNKNOWN = "unknown"
    OFFLINE = "offline"
    BOOTING = "booting"
    ONLINE = "online"
    SHUTTING_DOWN = "shutting_down"


VALID_TRANSITIONS: dict[NasState, set[NasState]] = {
    NasState.UNKNOWN: {NasState.ONLINE, NasState.OFFLINE},
    NasState.OFFLINE: {NasState.BOOTING, NasState.ONLINE},
    NasState.BOOTING: {NasState.ONLINE, NasState.OFFLINE},
    NasState.ONLINE: {NasState.SHUTTING_DOWN, NasState.OFFLINE},
    NasState.SHUTTING_DOWN: {NasState.OFFLINE, NasState.ONLINE},
}


class NasStateMachine:
    """Tracks NAS lifecycle state with disk persistence."""

    def __init__(self, state_dir: str | None = None):
        self._state_dir = Path(state_dir or settings.data_dir) / "handshake"
        self._state_file = self._state_dir / "nas_state.json"
        self._state = NasState.UNKNOWN
        self._since = datetime.now(timezone.utc)
        self._load()

    @property
    def state(self) -> NasState:
        return self._state

    @property
    def since(self) -> datetime:
        return self._since

    def transition(self, new_state: NasState) -> bool:
        """Transition to new state. Returns True if valid, False if rejected."""
        if new_state == self._state:
            return True  # No-op

        valid = VALID_TRANSITIONS.get(self._state, set())
        if new_state not in valid:
            logger.warning(
                "Invalid NAS state transition: %s -> %s (valid: %s)",
                self._state, new_state, valid,
            )
            return False

        old_state = self._state
        self._state = new_state
        self._since = datetime.now(timezone.utc)
        self._save()

        logger.info("NAS state: %s -> %s", old_state, new_state)
        return True

    def force_state(self, new_state: NasState) -> None:
        """Force state without transition validation (for initialization)."""
        old_state = self._state
        self._state = new_state
        self._since = datetime.now(timezone.utc)
        self._save()
        logger.info("NAS state forced: %s -> %s", old_state, new_state)

    def to_dict(self) -> dict:
        return {
            "state": self._state.value,
            "since": self._since.isoformat(),
        }

    def _load(self) -> None:
        """Load state from disk."""
        if not self._state_file.exists():
            logger.info("No NAS state file found — starting as UNKNOWN")
            return

        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            self._state = NasState(data["state"])
            self._since = datetime.fromisoformat(data["since"])
            logger.info("Loaded NAS state: %s (since %s)", self._state, self._since)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to load NAS state, resetting: %s", e)
            self._state = NasState.UNKNOWN
            self._since = datetime.now(timezone.utc)

    def _save(self) -> None:
        """Persist state to disk."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "state": self._state.value,
            "since": self._since.isoformat(),
        }
        self._state_file.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
