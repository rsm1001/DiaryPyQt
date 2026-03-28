"""
标签管理器模块
负责处理日记系统的标签相关功能
"""
import sqlite3
import os
import threading
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager


class TagManager:
    """标签管理器 - 专门处理标签相关的CRUD操作"""
    
    def __init__(self, db_manager):
        """
        初始化标签管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def add_tag(self, name: str) -> Optional[Dict[str, Any]]:
        """
        添加新标签
        
        Args:
            name: 标签名称
        
        Returns:
            新创建的标签字典或None
        """
        if not name or not name.strip():
            self.logger.warning("尝试添加空标签名")
            return None
            
        try:
            tag_id = self.db_manager._execute(
                "INSERT INTO tags (name) VALUES (?)",
                (name.strip(),)
            )
            
            if tag_id:
                self.logger.info(f"添加标签成功，ID: {tag_id}, 名称: {name}")
                return {
                    'id': tag_id,
                    'name': name.strip(),
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            return None
        except sqlite3.IntegrityError:
            self.logger.warning(f"标签已存在: {name}")
            return None
    
    def get_tag_by_id(self, tag_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取标签
        
        Args:
            tag_id: 标签ID
        
        Returns:
            标签字典或None
        """
        return self.db_manager._execute(
            "SELECT * FROM tags WHERE id = ?",
            (tag_id,),
            fetch='one'
        )
    
    def get_tag_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取标签
        
        Args:
            name: 标签名
        
        Returns:
            标签字典或None
        """
        return self.db_manager._execute(
            "SELECT * FROM tags WHERE name = ?",
            (name,),
            fetch='one'
        )
    
    def get_all_tags(self) -> List[Dict[str, Any]]:
        """
        获取所有标签
        
        Returns:
            标签列表
        """
        return self.db_manager._execute(
            "SELECT * FROM tags ORDER BY name ASC",
            fetch='all'
        ) or []
    
    def update_tag(self, tag_id: int, new_name: str) -> bool:
        """
        更新标签名称
        
        Args:
            tag_id: 标签ID
            new_name: 新名称
        
        Returns:
            是否更新成功
        """
        if not new_name or not new_name.strip():
            self.logger.warning("尝试更新为空标签名")
            return False
            
        try:
            rowcount = self.db_manager._execute(
                "UPDATE tags SET name = ? WHERE id = ?",
                (new_name.strip(), tag_id),
                fetch='rowcount'
            )
            
            if rowcount > 0:
                self.logger.info(f"更新标签成功，ID: {tag_id}")
                return True
            self.logger.warning(f"更新标签失败，ID: {tag_id} 不存在")
            return False
        except sqlite3.IntegrityError:
            self.logger.warning(f"标签名已存在: {new_name}")
            return False
    
    def delete_tag_by_id(self, tag_id: int) -> bool:
        """
        根据ID删除标签（仅在没有日记使用该标签的前提下）
        
        Args:
            tag_id: 标签ID
        
        Returns:
            是否删除成功
        """
        # 检查是否有日记关联到此标签
        usage = self.db_manager._execute(
            "SELECT COUNT(*) as count FROM diary_tags WHERE tag_id = ?",
            (tag_id,),
            fetch='one'
        )
        
        if usage and usage['count'] > 0:
            self.logger.warning(f"删除标签失败，标签ID: {tag_id} 正被 {usage['count']} 篇日记使用")
            return False
        
        # 删除标签
        rowcount = self.db_manager._execute(
            "DELETE FROM tags WHERE id = ?",
            (tag_id,),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            self.logger.info(f"删除标签成功，ID: {tag_id}")
            return True
        self.logger.warning(f"删除标签失败，ID: {tag_id} 不存在")
        return False
    
    def get_unused_tags(self) -> List[Dict[str, Any]]:
        """
        获取未被使用的标签（没有日记关联的标签）
        
        Returns:
            未被使用的标签列表
        """
        return self.db_manager._execute(
            """
            SELECT t.* 
            FROM tags t 
            LEFT JOIN diary_tags dt ON t.id = dt.tag_id 
            WHERE dt.tag_id IS NULL
            ORDER BY t.name ASC
            """,
            fetch='all'
        ) or []
    
    # ========================================================================
    # 日记-标签关联操作
    # ========================================================================
    
    def add_diary_tag(self, diary_id: int, tag_id: int) -> bool:
        """
        为日记添加标签
        
        Args:
            diary_id: 日记ID
            tag_id: 标签ID
        
        Returns:
            是否添加成功
        """
        # 首先检查日记和标签是否存在
        diary = self.db_manager.get_diary_by_id(diary_id)
        tag = self.get_tag_by_id(tag_id)
        
        if not diary or not tag:
            self.logger.warning(f"日记或标签不存在: diary_id={diary_id}, tag_id={tag_id}")
            return False
        
        try:
            self.db_manager._execute(
                "INSERT INTO diary_tags (diary_id, tag_id) VALUES (?, ?)",
                (diary_id, tag_id)
            )
            self.logger.info(f"日记-标签关联成功，diary_id: {diary_id}, tag_id: {tag_id}")
            return True
        except sqlite3.IntegrityError:
            self.logger.warning(f"日记-标签关联已存在: diary_id={diary_id}, tag_id={tag_id}")
            return False
    
    def remove_diary_tag(self, diary_id: int, tag_id: int) -> bool:
        """
        移除日记的特定标签
        
        Args:
            diary_id: 日记ID
            tag_id: 标签ID
        
        Returns:
            是否移除成功
        """
        rowcount = self.db_manager._execute(
            "DELETE FROM diary_tags WHERE diary_id = ? AND tag_id = ?",
            (diary_id, tag_id),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            self.logger.info(f"移除日记-标签关联成功，diary_id: {diary_id}, tag_id: {tag_id}")
            return True
        self.logger.info(f"日记-标签关联不存在，无需移除，diary_id: {diary_id}, tag_id: {tag_id}")
        return False
    
    def get_tags_by_diary_id(self, diary_id: int) -> List[Dict[str, Any]]:
        """
        获取某篇日记的所有标签
        
        Args:
            diary_id: 日记ID
        
        Returns:
            标签列表
        """
        return self.db_manager._execute(
            """
            SELECT t.* 
            FROM tags t 
            INNER JOIN diary_tags dt ON t.id = dt.tag_id 
            WHERE dt.diary_id = ?
            ORDER BY t.name ASC
            """,
            (diary_id,),
            fetch='all'
        ) or []
    
    def get_diaries_by_tag_id(self, tag_id: int) -> List[Dict[str, Any]]:
        """
        获取标记了特定标签的所有日记
        
        Args:
            tag_id: 标签ID
        
        Returns:
            日记列表
        """
        return self.db_manager._execute(
            """
            SELECT d.* 
            FROM diaries d 
            INNER JOIN diary_tags dt ON d.id = dt.diary_id 
            WHERE dt.tag_id = ?
            ORDER BY d.date DESC
            """,
            (tag_id,),
            fetch='all'
        ) or []
    
    def assign_tags_to_diary(self, diary_id: int, tag_ids: List[int]) -> bool:
        """
        为日记分配一组标签（替换原有标签）
        
        Args:
            diary_id: 日记ID
            tag_ids: 标签ID列表
        
        Returns:
            是否分配成功
        """
        # 检查日记是否存在
        if not self.db_manager.get_diary_by_id(diary_id):
            self.logger.warning(f"日记不存在: {diary_id}")
            return False
        
        # 先移除该日记的所有标签
        self.db_manager._execute(
            "DELETE FROM diary_tags WHERE diary_id = ?",
            (diary_id,)
        )
        
        # 添加新的标签关联
        success = True
        for tag_id in tag_ids:
            if not self.add_diary_tag(diary_id, tag_id):
                success = False
        
        if success:
            self.logger.info(f"为日记分配标签成功，diary_id: {diary_id}, tag_ids: {tag_ids}")
        else:
            self.logger.warning(f"为日记分配标签部分失败，diary_id: {diary_id}, tag_ids: {tag_ids}")
        
        return success