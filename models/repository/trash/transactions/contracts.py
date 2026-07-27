"""垃圾桶两阶段提交的共享协议与数据传输对象。"""
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple


class MainDbLike(Protocol):
    """主库向垃圾桶事务暴露的最小能力集合。"""

    @property
    def db_path(self) -> str: ...

    @property
    def _db_lock(self) -> Any: ...

    def _transaction(self): ...

    def _execute(
        self,
        query: str,
        params: Tuple = (),
        fetch: Optional[str] = None,
    ) -> Optional[Any]: ...

    def compute_tokens(self, content: str) -> str: ...

    def get_tag_by_id(self, tag_id: int) -> Optional[Dict[str, Any]]: ...

    def get_tag_by_name(self, name: str) -> Optional[Dict[str, Any]]: ...

    def add_tag(self, name: str) -> Optional[Dict[str, Any]]: ...

    def get_tags_by_diary_id(self, diary_id: int) -> List[Dict[str, Any]]: ...

    def get_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]: ...


@dataclass(frozen=True)
class PendingOperation:
    """跨库操作的 DTO，避免仓储层暴露数据库行。"""

    op_id: str
    op_type: str
    diary_id: Optional[int]
    trash_id: Optional[int]
    payload: Dict[str, Any]
    state: str = 'pending'
    created_at: str = ''
    updated_at: str = ''

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "PendingOperation":
        """将数据库记录转换为事务 DTO。"""
        return cls(
            op_id=row['op_id'],
            op_type=row['op_type'],
            diary_id=row.get('diary_id'),
            trash_id=row.get('trash_id'),
            payload=deserialize_payload(row['payload']),
            state=row.get('state', 'pending'),
            created_at=row.get('created_at') or '',
            updated_at=row.get('updated_at') or '',
        )

    def to_database_values(self) -> Tuple[Any, ...]:
        """生成 pending_trash_ops 的参数化写入值。"""
        return (
            self.op_id,
            self.op_type,
            self.diary_id,
            self.trash_id,
            serialize_payload(self.payload),
            self.state,
            self.created_at,
            self.updated_at,
        )


def serialize_payload(payload: Dict[str, Any]) -> str:
    """序列化可恢复的业务载荷。"""
    return json.dumps(payload, ensure_ascii=False, default=str)


def deserialize_payload(raw: Any) -> Dict[str, Any]:
    """兼容读取 SQLite 文本值和测试中的字典值。"""
    return json.loads(raw) if isinstance(raw, str) else raw
