"""垃圾桶两阶段提交的崩溃恢复服务。"""
import logging
from typing import Any, Callable, Dict, Optional

from .contracts import PendingOperation
from .pending_store import PendingOperationStore

logger = logging.getLogger(__name__)

ApplyCallback = Callable[[str, str, Optional[int], Optional[int], Dict[str, Any]], None]
CommitCallback = Callable[[str, str, Optional[int], Optional[int], Dict[str, Any]], None]


class PendingOperationRecovery:
    """根据两库状态推进未完成操作到稳定状态。"""

    def __init__(
        self,
        pending_store: PendingOperationStore,
        apply_to_main: ApplyCallback,
        commit_to_trash: CommitCallback,
    ):
        self._store = pending_store
        self._apply_to_main = apply_to_main
        self._commit_to_trash = commit_to_trash

    def recover(self) -> int:
        """扫描两库 pending 记录并恢复中断的跨库操作。"""
        main_by_id = {item.op_id: item for item in self._store.read_main()}
        trash_by_id = {item.op_id: item for item in self._store.read_trash()}
        recovered = 0

        for op_id in set(main_by_id) | set(trash_by_id):
            main_operation = main_by_id.get(op_id)
            trash_operation = trash_by_id.get(op_id)
            if self._recover_one(main_operation, trash_operation):
                recovered += 1
        return recovered

    def _recover_one(
        self,
        main_operation: Optional[PendingOperation],
        trash_operation: Optional[PendingOperation],
    ) -> bool:
        operation = main_operation or trash_operation
        if operation is None:
            return False

        if (
            main_operation
            and main_operation.state == 'committed'
            and (not trash_operation or trash_operation.state != 'committed')
        ):
            return self._replay_commit(main_operation, "主库已 committed")

        if (
            trash_operation
            and trash_operation.state == 'committed'
            and (not main_operation or main_operation.state != 'committed')
        ):
            # 阶段三的垃圾桶真实写与 committed 状态同事务提交；此处只补主库状态。
            self._store.mirror_to_main(trash_operation)
            self._log_info("补齐主库 committed 状态", operation.op_id)
            return True

        if (
            main_operation
            and main_operation.state == 'applied'
            and trash_operation
            and trash_operation.state == 'pending'
        ):
            # 阶段二的主库真实写与 applied 状态同事务提交；可安全推进阶段三。
            return self._replay_commit(main_operation, "主库已 applied")

        if (
            main_operation
            and trash_operation
            and main_operation.state == 'applied'
            and trash_operation.state == 'applied'
        ):
            return self._replay_commit(main_operation, "两库 applied")

        if (
            (not main_operation or main_operation.state == 'pending')
            and (not trash_operation or trash_operation.state == 'pending')
        ):
            self._store.cleanup(operation.op_id)
            self._log_info("2PC 阶段一 pending 清理", operation.op_id)
            return True

        if main_operation and not trash_operation:
            self._recover_missing_trash_operation(main_operation)
            self._log_info("补齐垃圾桶库并重放真实写", operation.op_id)
            return True

        if trash_operation and not main_operation:
            return self._recover_missing_main_operation(trash_operation)
        return False

    def _recover_missing_trash_operation(self, operation: PendingOperation) -> None:
        """以主库记录为准补齐缺失的垃圾桶侧操作。"""
        if operation.state == 'pending':
            self._apply(operation)
        self._commit(operation)

    def _recover_missing_main_operation(self, operation: PendingOperation) -> bool:
        """以垃圾桶库记录为准补齐主库侧操作。"""
        if operation.state == 'committed':
            self._store.mirror_to_main(operation)
            return False

        if operation.state in ('pending', 'applied'):
            self._apply(operation)
        if operation.state == 'applied':
            self._commit(operation)
        self._log_info("补齐主库并重放真实写", operation.op_id)
        return True

    def _replay_commit(self, operation: PendingOperation, reason: str) -> bool:
        try:
            self._commit(operation)
            self._log_info(f"2PC 阶段三重放：{reason}", operation.op_id)
            return True
        except Exception:
            logger.error(
                "2PC 恢复失败",
                extra={
                    "extra_data": {
                        "trace_id": operation.op_id,
                        "reason": reason,
                        "component": "pending_recovery",
                    }
                },
                exc_info=True,
            )
            return False

    def _apply(self, operation: PendingOperation) -> None:
        self._apply_to_main(
            operation.op_id,
            operation.op_type,
            operation.diary_id,
            operation.trash_id,
            operation.payload,
        )

    def _commit(self, operation: PendingOperation) -> None:
        self._commit_to_trash(
            operation.op_id,
            operation.op_type,
            operation.diary_id,
            operation.trash_id,
            operation.payload,
        )

    @staticmethod
    def _log_info(message: str, trace_id: str) -> None:
        logger.info(
            message,
            extra={"extra_data": {"trace_id": trace_id, "component": "pending_recovery"}},
        )
