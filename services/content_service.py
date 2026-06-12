"""
日记内容服务模块 - 负责处理日记的基本CRUD操作
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DiaryContentService:
    """日记内容服务类，负责处理日记的基本CRUD操作"""
    
    def __init__(self, db_manager):
        """
        初始化日记内容服务
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
    
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
        tokens = self.db_manager.compute_tokens(stripped)
        diary_id = self.db_manager._execute(
            "INSERT INTO diaries (date, content, view_count, tokens) VALUES (?, ?, ?, ?)",
            (date, stripped, 0, tokens)
        )
        
        if diary_id:
            logger.info(f"添加日记成功，ID: {diary_id}")
            return {
                'id': diary_id,
                'date': date,
                'content': stripped,
                'view_count': 0
            }
        return None
    
    def get_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取日记
        
        Args:
            diary_id: 日记ID
        
        Returns:
            日记字典或None
        """
        return self.db_manager._execute(
            "SELECT * FROM diaries WHERE id = ?",
            (diary_id,),
            fetch='one'
        )
    
    def update_diary(self, diary_id: int, new_content: str) -> bool:
        """
        更新日记内容
        
        Args:
            diary_id: 日记ID
            new_content: 新内容
        
        Returns:
            是否更新成功
        """
        if not new_content or not new_content.strip():
            logger.warning("尝试更新为空内容")
            return False
        
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stripped = new_content.strip()
        tokens = self.db_manager.compute_tokens(stripped)
        rowcount = self.db_manager._execute(
            "UPDATE diaries SET content = ?, date = ?, tokens = ? WHERE id = ?",
            (stripped, date, tokens, diary_id),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"更新日记成功，ID: {diary_id}")
            return True
        logger.warning(f"更新日记失败，ID: {diary_id} 不存在")
        return False
    
    def delete_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID删除日记
        
        Args:
            diary_id: 日记ID
        
        Returns:
            被删除的日记字典或None
        """
        # 先获取日记信息
        diary = self.get_diary_by_id(diary_id)
        if not diary:
            logger.warning(f"删除失败，日记不存在: {diary_id}")
            return None
        
        # 删除日记
        self.db_manager._execute(
            "DELETE FROM diaries WHERE id = ?",
            (diary_id,)
        )
        
        logger.info(f"删除日记成功，ID: {diary_id}")
        return diary
    
    def get_all_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有日记（按日期倒序）
        
        Args:
            limit: 限制数量
        
        Returns:
            日记列表
        """
        query = "SELECT * FROM diaries ORDER BY date DESC"
        params = ()
        
        if limit:
            query += " LIMIT ?"
            params = (limit,)
        
        return self.db_manager._execute(query, params, fetch='all') or []
    
    def get_diaries_with_limit(self, limit: int) -> List[Dict[str, Any]]:
        """
        获取指定数量的日记（按日期倒序）- 符合DatabaseManagerInterface协议
        
        Args:
            limit: 限制数量
        
        Returns:
            日记列表
        """
        return self.db_manager._execute(
            "SELECT * FROM diaries ORDER BY date DESC LIMIT ?",
            (limit,),
            fetch='all'
        ) or []

    def search_diaries_by_content(self, keyword: str) -> List[Dict[str, Any]]:
        """
        根据内容搜索日记
        
        Args:
            keyword: 搜索关键词
        
        Returns:
            匹配的日记列表
        """
        query = "SELECT * FROM diaries WHERE content LIKE ? ORDER BY date DESC"
        params = (f'%{keyword}%',)
        
        return self.db_manager._execute(query, params, fetch='all') or []
    
    def get_diaries_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        """
        根据日期获取日记（LIKE 查询，支持日期+时分秒）

        Args:
            date_str: 日期字符串，格式如 '2026-05-20'

        Returns:
            该日期的所有日记
        """
        query = "SELECT * FROM diaries WHERE date LIKE ? ORDER BY date DESC"
        params = (f'{date_str}%',)

        diaries = self.db_manager._execute(query, params, fetch='all') or []

        # 批量获取标签（避免 N+1 查询）
        diary_ids = [d['id'] for d in diaries]
        tags_map = self.db_manager.get_tags_for_diaries(diary_ids)
        for diary in diaries:
            diary['tags'] = tags_map.get(diary['id'], [])

        return diaries

    def get_diaries_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        根据日期范围获取日记
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            指定日期范围内的日记列表
        """
        query = "SELECT * FROM diaries WHERE date BETWEEN ? AND ? ORDER BY date DESC"
        params = (start_date, end_date)
        
        return self.db_manager._execute(query, params, fetch='all') or []
    
    def bulk_insert_diaries(self, diaries: List[Dict[str, str]]) -> int:
        """
        批量插入日记
        
        Args:
            diaries: 日记列表 [{'content': '...'}, ...]
        
        Returns:
            成功插入的日记数量
        """
        if not diaries:
            return 0
        
        inserted_count = 0
        for diary_data in diaries:
            if 'content' in diary_data:
                result = self.add_diary(diary_data['content'])
                if result:
                    inserted_count += 1
        
        logger.info(f"批量插入日记完成，共插入 {inserted_count} 条")
        return inserted_count
    
    def get_diary_count(self) -> int:
        """
        获取日记总数
        
        Returns:
            日记总数
        """
        result = self.db_manager._execute(
            "SELECT COUNT(*) as count FROM diaries",
            fetch='one'
        )
        return result['count'] if result else 0
    
    def get_all_diaries_with_tags(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有日记及其标签
        
        Args:
            limit: 限制数量
        
        Returns:
            包含标签的日记列表
        """
        query = """
        SELECT d.*, GROUP_CONCAT(t.name, ', ') as tag_names
        FROM diaries d
        LEFT JOIN diary_tags dt ON d.id = dt.diary_id
        LEFT JOIN tags t ON dt.tag_id = t.id
        GROUP BY d.id
        ORDER BY d.date DESC
        """
        params = ()
        
        if limit:
            query += " LIMIT ?"
            params = (limit,)
        
        diaries = self.db_manager._execute(query, params, fetch='all') or []

        # 批量获取标签（避免 N+1 查询）
        diary_ids = [d['id'] for d in diaries]
        tags_map = self.db_manager.get_tags_for_diaries(diary_ids)
        for diary in diaries:
            diary['tags'] = tags_map.get(diary['id'], [])

        return diaries