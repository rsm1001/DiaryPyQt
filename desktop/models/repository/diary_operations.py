"""
日记基础操作模块 - 从EnhancedDatabaseManager解耦而来
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DiaryOperationsMixin:
    """日记基础操作混入类"""

    def add_diary(self, content: str) -> Optional[Dict[str, Any]]:
        """添加新日记（不带标签，委托给原子创建方法）。"""
        return self.add_diary_with_tags(content, [])

    @staticmethod
    def _missing_tag_id(cursor, tag_ids: List[int]) -> Optional[int]:
        """返回第一个不存在的标签ID；全部存在时返回 None。"""
        for tag_id in tag_ids:
            if cursor.execute(
                "SELECT id FROM tags WHERE id = ?", (tag_id,)
            ).fetchone() is None:
                return tag_id
        return None

    @staticmethod
    def _bind_tags(cursor, diary_id: int, tag_ids: List[int]) -> None:
        """在当前事务内为日记写入标签绑定。"""
        for tag_id in tag_ids:
            cursor.execute(
                "INSERT INTO diary_tags (diary_id, tag_id) VALUES (?, ?)",
                (diary_id, tag_id),
            )

    def add_diary_with_tags(self, content: str, tag_ids: List[int]) -> Optional[Dict[str, Any]]:
        """原子创建日记并绑定标签；标签不存在时不写入任何数据，返回 None。"""
        if not content or not content.strip():
            logger.warning("尝试添加空日记内容")
            return None
        unique_tag_ids = list(dict.fromkeys(tag_ids or []))
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stripped = content.strip()
        tokens = self.compute_tokens(stripped)
        with self._lock:
            with self._transaction() as cursor:
                missing = self._missing_tag_id(cursor, unique_tag_ids)
                if missing is not None:
                    logger.warning("新增日记失败，标签不存在: %s", missing)
                    return None
                cursor.execute(
                    "INSERT INTO diaries (date, content, tokens, updated_at) VALUES (?, ?, ?, ?)",
                    (date, stripped, tokens, date),
                )
                diary_id = cursor.lastrowid
                self._bind_tags(cursor, diary_id, unique_tag_ids)
        if not diary_id:
            return None
        logger.info("新增日记成功，ID: %s", diary_id)
        return self.get_diary_by_id(diary_id)

    def update_diary_with_tags(self, diary_id: int, content: str, tag_ids: List[int]) -> bool:
        """原子更新日记内容并替换标签；标签不存在时不写入任何数据，返回 False。"""
        if not content or not content.strip():
            return False
        unique_tag_ids = list(dict.fromkeys(tag_ids or []))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stripped = content.strip()
        tokens = self.compute_tokens(stripped)
        with self._lock:
            with self._transaction() as cursor:
                missing = self._missing_tag_id(cursor, unique_tag_ids)
                if missing is not None:
                    logger.warning("更新日记失败，标签不存在: %s", missing)
                    return False
                cursor.execute(
                    "UPDATE diaries SET content = ?, tokens = ?, updated_at = ? WHERE id = ?",
                    (stripped, tokens, now, diary_id),
                )
                if cursor.rowcount == 0:
                    return False
                cursor.execute("DELETE FROM diary_tags WHERE diary_id = ?", (diary_id,))
                self._bind_tags(cursor, diary_id, unique_tag_ids)
        return True

    def get_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取日记

        Args:
            diary_id: 日记ID

        Returns:
            日记字典或None
        """
        query = "SELECT * FROM diaries WHERE id = ?"
        return self._execute(query, (diary_id,), fetch='one')

    def update_diary(self, diary_id: int, new_content: str) -> bool:
        """
        更新日记内容（仅修改 content / tokens / updated_at，不动 date）

        date 是"创建时间"语义，写入后永不变；updated_at 记录"最近编辑时间"。

        Args:
            diary_id: 日记ID
            new_content: 新内容

        Returns:
            是否更新成功
        """
        if not new_content or not new_content.strip():
            logger.warning("尝试更新为空内容")
            return False

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stripped = new_content.strip()
        tokens = self.compute_tokens(stripped)
        # 关键：date 不在 SET 列表中；只推进 updated_at
        rowcount = self._execute(
            "UPDATE diaries SET content = ?, tokens = ?, updated_at = ? WHERE id = ?",
            (stripped, tokens, now, diary_id),
            fetch='rowcount'
        )

        if rowcount > 0:
            logger.info(f"更新日记成功，ID: {diary_id}")
            return True
        logger.warning(f"更新日记失败，ID: {diary_id} 不存在")
        return False

    def delete_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID删除日记（移动到垃圾桶）

        Args:
            diary_id: 日记ID

        Returns:
            移动结果信息或None
        """
        # 先获取日记信息
        diary = self.get_diary_by_id(diary_id)
        if not diary:
            logger.warning(f"删除失败，日记不存在: {diary_id}")
            return None

        # 移动到垃圾桶（软删除）
        result = self.move_to_trash(diary_id)

        if result:
            logger.info(f"删除日记成功，ID: {diary_id}，垃圾桶ID: {result.get('trash_id')}")
            return result
        return None

    def get_all_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有日记（按日期倒序）

        Args:
            limit: 限制数量

        Returns:
            日记列表
        """
        if limit is not None:
            query = "SELECT * FROM diaries ORDER BY date DESC LIMIT ?"
            return self._execute(query, (limit,), fetch='all') or []
        else:
            query = "SELECT * FROM diaries ORDER BY date DESC"
            return self._execute(query, fetch='all') or []