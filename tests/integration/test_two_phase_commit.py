"""2PC 协调器与崩溃恢复测试。"""
from unittest.mock import MagicMock
import pytest
from models.repository.trash.transactions.contracts import PendingOperation
from models.repository.trash.transactions.recovery import PendingOperationRecovery
from models.repository.trash.two_phase_commit import TrashTwoPhaseCommitCoordinator
from models.repository.trash.transactions import pending_store as pending_store_module

@pytest.fixture
def coordinator(mocker):
    pool = MagicMock(name="pool")
    main = MagicMock(name="main")
    main.db_path = "/tmp/main.db"
    obj = TrashTwoPhaseCommitCoordinator(pool, main)
    obj._pending_store = mocker.MagicMock(name="pending_store")
    obj._recovery = mocker.MagicMock(name="recovery")
    mocker.patch.object(obj, "_now", return_value="2026-08-13 10:00:00")
    return obj

def op(state="pending", op_type="move"):
    return PendingOperation("op-1", op_type, 1, None, {"content": "内容"}, state,
                            "2026-08-13 09:00:00", "2026-08-13 09:00:00")

class TestCoordinatorPhases:
    def test_precommit_builds_pending_operation(self, coordinator):
        coordinator.precommit("op-1", "move", 1, None, {"content": "内容"})
        created = coordinator._pending_store.create.call_args.args[0]
        assert created.op_id == "op-1"
        assert created.state == "pending"
        assert created.payload == {"content": "内容"}

    def test_invalid_operation_type_is_rejected(self, coordinator):
        with pytest.raises(ValueError, match="未知 op_type"):
            coordinator.precommit("op-1", "invalid", 1, None, {})
        coordinator._pending_store.create.assert_not_called()

    def test_apply_and_commit_update_mirrored_states(self, coordinator, mocker):
        handler = mocker.MagicMock()
        mocker.patch.object(coordinator._handler_factory, "create", return_value=handler)
        coordinator._pending_store.apply_main_phase.side_effect = lambda callback, *_: callback(MagicMock())
        coordinator._pending_store.commit_trash_phase.side_effect = lambda callback, *_: callback(MagicMock())
        coordinator.apply_to_main("op-1", "move", 1, None, {"content": "??"})
        coordinator.commit_to_trash("op-1", "move", 1, None, {"content": "??"})
        handler.apply_to_main.assert_called_once()
        handler.apply_to_trash.assert_called_once()
        coordinator._pending_store.mark_trash_applied.assert_called_once_with("op-1", "2026-08-13 10:00:00")
        coordinator._pending_store.mark_main_committed.assert_called_once_with("op-1", "2026-08-13 10:00:00")

    def test_apply_failure_does_not_mark_trash_applied(self, coordinator, mocker):
        handler = mocker.MagicMock()
        handler.apply_to_main.side_effect = RuntimeError("模拟崩溃")
        mocker.patch.object(coordinator._handler_factory, "create", return_value=handler)
        def invoke(callback, *_):
            callback(MagicMock())
        coordinator._pending_store.apply_main_phase.side_effect = invoke
        with pytest.raises(RuntimeError, match="模拟崩溃"):
            coordinator.apply_to_main("op-1", "move", 1, None, {})
        coordinator._pending_store.mark_trash_applied.assert_not_called()

    def test_serialization_and_compatibility_helpers(self, coordinator):
        payload = {"中文": "值"}
        assert coordinator._deserialize_payload(coordinator._serialize_payload(payload)) == payload
        coordinator.cleanup_pending_op("op-1")
        coordinator.mirror_pending_to_trash({"op_id": "op-1", "op_type": "move", "diary_id": 1,
                                             "trash_id": None, "payload": coordinator._serialize_payload(payload)})
        coordinator._pending_store.cleanup.assert_called_once_with("op-1")
        coordinator._pending_store.mirror_to_trash.assert_called_once()

class TestPendingOperationRecovery:
    @pytest.mark.parametrize("main_state,trash_state,expected", [
        ("committed", "applied", "commit"),
        ("applied", "pending", "commit"),
        ("applied", "applied", "commit"),
    ])
    def test_replays_incomplete_commit(self, mocker, main_state, trash_state, expected):
        store = mocker.MagicMock()
        store.read_main.return_value = [op(main_state)]
        store.read_trash.return_value = [op(trash_state)]
        commit = mocker.MagicMock()
        recovery = PendingOperationRecovery(store, mocker.MagicMock(), commit)
        assert recovery.recover() == 1
        commit.assert_called_once()

    def test_committed_trash_mirrors_main(self, mocker):
        store = mocker.MagicMock()
        store.read_main.return_value = []
        store.read_trash.return_value = [op("committed")]
        recovery = PendingOperationRecovery(store, mocker.MagicMock(), mocker.MagicMock())
        assert recovery.recover() == 1
        store.mirror_to_main.assert_called_once()

    def test_both_pending_are_cleaned(self, mocker):
        store = mocker.MagicMock()
        store.read_main.return_value = [op()]
        store.read_trash.return_value = [op()]
        recovery = PendingOperationRecovery(store, mocker.MagicMock(), mocker.MagicMock())
        assert recovery.recover() == 1
        store.cleanup.assert_called_once_with("op-1")

    def test_missing_trash_replays_apply_and_commit(self, mocker):
        store = mocker.MagicMock()
        store.read_main.return_value = [op("applied")]
        store.read_trash.return_value = []
        apply_main, commit = mocker.MagicMock(), mocker.MagicMock()
        recovery = PendingOperationRecovery(store, apply_main, commit)
        assert recovery.recover() == 1
        apply_main.assert_not_called()
        commit.assert_called_once()

    def test_commit_failure_is_not_counted(self, mocker):
        store = mocker.MagicMock()
        store.read_main.return_value = [op("committed")]
        store.read_trash.return_value = []
        commit = mocker.MagicMock(side_effect=RuntimeError("仍不可用"))
        recovery = PendingOperationRecovery(store, mocker.MagicMock(), commit)
        assert recovery.recover() == 0

class TestCoordinatorRecovery:
    def test_delegates_recovery_and_propagates_errors(self, coordinator):
        coordinator._recovery.recover.return_value = 2
        assert coordinator.recover_pending_ops() == 2
        coordinator._recovery.recover.side_effect = RuntimeError("恢复失败")
        with pytest.raises(RuntimeError, match="恢复失败"):
            coordinator.recover_pending_ops()
