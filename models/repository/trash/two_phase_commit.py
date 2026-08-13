"""垃圾桶两阶段提交协调器。"""
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Union

from .connection import TrashConnectionPool
from .transactions.contracts import MainDbLike, PendingOperation, deserialize_payload, serialize_payload
from .transactions.handlers import TrashOperationHandlerFactory
from .transactions.pending_store import PendingOperationStore
from .transactions.recovery import PendingOperationRecovery

logger = logging.getLogger(__name__)


class TrashTwoPhaseCommitCoordinator:
    """编排 move / restore 的三阶段跨库事务。"""

    VALID_OP_TYPES = TrashOperationHandlerFactory.VALID_OP_TYPES

    def __init__(
        self,
        connection_pool: TrashConnectionPool,
        main_db: MainDbLike,
    ):
        self._main_db = main_db
        self._pending_store = PendingOperationStore(connection_pool, main_db)
        self._handler_factory = TrashOperationHandlerFactory(main_db, self._now)
        self._recovery = PendingOperationRecovery(
            self._pending_store,
            self.apply_to_main,
            self.commit_to_trash,
        )

    def precommit(
        self,
        op_id: str,
        op_type: str,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        """阶段一：在主库和垃圾桶库创建 pending 操作记录。"""
        self._validate_op_type(op_type)
        timestamp = self._now()
        operation = PendingOperation(
            op_id=op_id,
            op_type=op_type,
            diary_id=diary_id,
            trash_id=trash_id,
            payload=payload,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._run_phase("precommit", operation, self._pending_store.create)

    def apply_to_main(
        self,
        op_id: str,
        op_type: str,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        """阶段二：执行主库真实写入并同步 applied 状态。"""
        operation = self._operation_from_arguments(op_id, op_type, diary_id, trash_id, payload)

        def execute() -> None:
            handler = self._handler_factory.create(operation.op_type)
            updated_at = self._now()
            self._pending_store.apply_main_phase(
                lambda cursor: handler.apply_to_main(
                    cursor,
                    operation.diary_id,
                    operation.trash_id,
                    operation.payload,
                ),
                operation.op_id,
                updated_at,
            )
            self._pending_store.mark_trash_applied(operation.op_id, updated_at)

        self._run_phase("apply", operation, execute)

    def commit_to_trash(
        self,
        op_id: str,
        op_type: str,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        """阶段三：执行垃圾桶库真实写入并同步 committed 状态。"""
        operation = self._operation_from_arguments(op_id, op_type, diary_id, trash_id, payload)

        def execute() -> None:
            handler = self._handler_factory.create(operation.op_type)
            updated_at = self._now()
            self._pending_store.commit_trash_phase(
                lambda cursor: handler.apply_to_trash(
                    cursor,
                    operation.diary_id,
                    operation.trash_id,
                    operation.payload,
                ),
                operation.op_id,
                updated_at,
            )
            self._pending_store.mark_main_committed(operation.op_id, updated_at)

        self._run_phase("commit", operation, execute)

    def recover_pending_ops(self) -> int:
        """启动时恢复两库状态不一致的未完成操作。"""
        try:
            recovered = self._recovery.recover()
        except Exception:
            logger.error(
                "垃圾桶 2PC 恢复流程失败",
                extra={"extra_data": {"trace_id": "recovery", "component": "two_phase_commit"}},
                exc_info=True,
            )
            raise
        logger.info(
            "垃圾桶 2PC 恢复完成",
            extra={
                "extra_data": {
                    "trace_id": "recovery",
                    "component": "two_phase_commit",
                    "recovered_count": recovered,
                }
            },
        )
        return recovered

    def cleanup_pending_op(self, op_id: str) -> None:
        """兼容既有调用：清理指定操作的两库 pending 记录。"""
        self._pending_store.cleanup(op_id)

    def mirror_pending_to_trash(self, main_row: Dict[str, Any]) -> None:
        """兼容既有调用：仅镜像 pending 元数据到垃圾桶库。"""
        self._pending_store.mirror_to_trash(PendingOperation.from_row(main_row))

    def mirror_pending_to_main(self, trash_row: Dict[str, Any]) -> None:
        """兼容既有调用：仅镜像 pending 元数据到主库。"""
        self._pending_store.mirror_to_main(PendingOperation.from_row(trash_row))

    @staticmethod
    def new_op_id() -> str:
        """生成全局唯一的操作追踪 ID。"""
        return str(uuid.uuid4())

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _serialize_payload(payload: Dict[str, Any]) -> str:
        """兼容既有内部调用的载荷序列化方法。"""
        return serialize_payload(payload)

    @staticmethod
    def _deserialize_payload(raw: Any) -> Dict[str, Any]:
        """兼容既有内部调用的载荷反序列化方法。"""
        return deserialize_payload(raw)

    def _validate_op_type(self, op_type: str) -> None:
        if op_type not in self.VALID_OP_TYPES:
            raise ValueError(f"未知 op_type: {op_type!r}")

    def _operation_from_arguments(
        self,
        op_id: str,
        op_type: str,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> PendingOperation:
        self._validate_op_type(op_type)
        return PendingOperation(op_id, op_type, diary_id, trash_id, payload)

    def _run_phase(
        self,
        phase: str,
        operation: PendingOperation,
        callback: Union[Callable[[], None], Callable[[PendingOperation], None]],
    ) -> None:
        self._log_phase("开始", phase, operation)
        try:
            if phase == "precommit":
                callback(operation)
            else:
                callback()
        except Exception:
            logger.error(
                "垃圾桶 2PC 阶段失败",
                extra={
                    "extra_data": {
                        "trace_id": operation.op_id,
                        "phase": phase,
                        "op_type": operation.op_type,
                        "component": "two_phase_commit",
                    }
                },
                exc_info=True,
            )
            raise
        self._log_phase("完成", phase, operation)

    @staticmethod
    def _log_phase(action: str, phase: str, operation: PendingOperation) -> None:
        logger.info(
            f"垃圾桶 2PC 阶段{action}",
            extra={
                "extra_data": {
                    "trace_id": operation.op_id,
                    "phase": phase,
                    "op_type": operation.op_type,
                    "diary_id": operation.diary_id,
                    "trash_id": operation.trash_id,
                    "component": "two_phase_commit",
                }
            },
        )


__all__ = ["MainDbLike", "TrashTwoPhaseCommitCoordinator"]
