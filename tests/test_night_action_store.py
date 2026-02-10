"""Tests for NightActionStore component."""

import pytest
from werewolf.engine.night_action_store import NightActionStore, NightActionSnapshot


class TestNightActionStore:
    """Tests for NightActionStore functionality."""

    def test_default_initialization(self) -> None:
        """Test that default values are correctly initialized."""
        store = NightActionStore()

        # Persistent state defaults
        assert store.antidote_used is False
        assert store.poison_used is False
        assert store.guard_prev_target is None

        # Ephemeral state defaults
        assert store.kill_target is None
        assert store.antidote_target is None
        assert store.poison_target is None
        assert store.guard_target is None

    def test_snapshot_returns_persistent_state(self) -> None:
        """Test that snapshot() returns only persistent state."""
        store = NightActionStore(
            antidote_used=True,
            poison_used=True,
            guard_prev_target=5,
            kill_target=3,
            antidote_target=2,
            poison_target=7,
            guard_target=1,
        )

        snapshot = store.snapshot()

        # Snapshot should contain persistent state
        assert snapshot.antidote_used is True
        assert snapshot.poison_used is True
        assert snapshot.guard_prev_target == 5

        # Snapshot should NOT contain ephemeral state
        assert not hasattr(snapshot, "kill_target")
        assert not hasattr(snapshot, "antidote_target")
        assert not hasattr(snapshot, "poison_target")
        assert not hasattr(snapshot, "guard_target")

    def test_from_snapshot_creates_store(self) -> None:
        """Test that from_snapshot() creates a store with snapshot values."""
        snapshot = NightActionSnapshot(
            antidote_used=True,
            poison_used=False,
            guard_prev_target=8,
        )

        store = NightActionStore.from_snapshot(snapshot)

        # Persistent state should match snapshot
        assert store.antidote_used is True
        assert store.poison_used is False
        assert store.guard_prev_target == 8

        # Ephemeral targets should all be None
        assert store.kill_target is None
        assert store.antidote_target is None
        assert store.poison_target is None
        assert store.guard_target is None

    def test_snapshot_restore_cycle(self) -> None:
        """Test complete snapshot/restore cycle."""
        # Create initial store with some state
        store = NightActionStore(
            antidote_used=True,
            poison_used=False,
            guard_prev_target=4,
            kill_target=2,
            antidote_target=3,
            poison_target=1,
            guard_target=6,
        )

        # Take snapshot
        snapshot = store.snapshot()

        # Simulate new night - clear ephemeral targets
        store.reset_for_new_night()

        # Verify ephemeral targets are cleared
        assert store.kill_target is None
        assert store.antidote_target is None
        assert store.poison_target is None
        assert store.guard_target is None

        # Persistent state should still be available
        assert store.antidote_used is True
        assert store.poison_used is False
        assert store.guard_prev_target == 4

        # Create new store from snapshot
        new_store = NightActionStore.from_snapshot(snapshot)

        # Verify persistent state is restored
        assert new_store.antidote_used is True
        assert new_store.poison_used is False
        assert new_store.guard_prev_target == 4

        # Verify all targets are None
        assert new_store.kill_target is None
        assert new_store.antidote_target is None
        assert new_store.poison_target is None
        assert new_store.guard_target is None

    def test_reset_for_new_night_clears_targets(self) -> None:
        """Test that reset_for_new_night() clears ephemeral targets."""
        store = NightActionStore(
            kill_target=3,
            antidote_target=2,
            poison_target=7,
            guard_target=1,
        )

        store.reset_for_new_night()

        assert store.kill_target is None
        assert store.antidote_target is None
        assert store.poison_target is None
        assert store.guard_target is None

    def test_reset_for_new_night_preserves_usage_flags(self) -> None:
        """Test that reset_for_new_night() preserves persistent state."""
        store = NightActionStore(
            antidote_used=True,
            poison_used=True,
            guard_prev_target=5,
        )

        store.reset_for_new_night()

        assert store.antidote_used is True
        assert store.poison_used is True
        assert store.guard_prev_target == 5

    def test_model_serialization(self) -> None:
        """Test that models can be serialized and deserialized."""
        store = NightActionStore(
            antidote_used=True,
            poison_used=False,
            guard_prev_target=9,
            kill_target=3,
            antidote_target=4,
            poison_target=None,
            guard_target=1,
        )

        # Should be serializable to JSON
        json_str = store.model_dump_json()
        restored = NightActionStore.model_validate_json(json_str)

        assert restored.antidote_used is True
        assert restored.poison_used is False
        assert restored.guard_prev_target == 9
        assert restored.kill_target == 3
        assert restored.antidote_target == 4
        assert restored.poison_target is None
        assert restored.guard_target == 1

    def test_snapshot_serialization(self) -> None:
        """Test that NightActionSnapshot can be serialized."""
        snapshot = NightActionSnapshot(
            antidote_used=True,
            poison_used=True,
            guard_prev_target=7,
        )

        json_str = snapshot.model_dump_json()
        restored = NightActionSnapshot.model_validate_json(json_str)

        assert restored.antidote_used is True
        assert restored.poison_used is True
        assert restored.guard_prev_target == 7
