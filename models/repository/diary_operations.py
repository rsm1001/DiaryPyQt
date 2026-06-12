"""
日记基础操作模块 - 从EnhancedDatabaseManager解耦而来
"""
import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DiaryOperationsMixin:
    """日记基础操作混入类"""

    def add_diary(self, content: str) -> Optional[Dict[str, Any]]:
        """
        添加新日记

        Args:
            content: 日记内容

        Returns:
            新创建的日记字典
        """
        if not content or not content.strip():
            logger.warning("尝试添加空日记内容")
            return None

        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stripped = content.strip()
        tokens = self.compute_tokens(stripped)
        # updated_at 初值与 date 相同（创建即"最新"），后续编辑才推进
        query = "INSERT INTO diaries (date, content, tokens, updated_at) VALUES (?, ?, ?, ?)"
        diary_id = self._execute(query, (date, stripped, tokens, date))

        if diary_id:
            logger.info(f"新增日记成功，ID: {diary_id}")
            return self.get_diary_by_id(diary_id)
        return None

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