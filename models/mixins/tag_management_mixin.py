"""
标签管理混合类，用于EnhancedDatabaseManager
将所有标签相关的功能从主数据库管理器中解耦出来
"""
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class TagManagementMixin:
    """标签管理混合类，提供日记-标签相关的操作功能"""
    
    # 这些方法依赖于主类中已实现的方法
    # 不需要在这里重新定义
    pass
    
    def add_tag(self, name: str) -> Optional[Dict[str, Any]]:
        """
        添加新标签
        
        Args:
            name: 标签名称
        
        Returns:
            新创建的标签字典或None
        """
        if not name or not name.strip():
            logger.warning("尝试添加空标签名称")
            return None
            
        tag_id = self._execute(
            "INSERT OR IGNORE INTO tags (name) VALUES (?)",
            (name.strip(),)
        )
        
        if tag_id:
            logger.info(f"添加标签成功，ID: {tag_id}")
            return {
                'id': tag_id,
                'name': name.strip(),
                'created_at': None  # 在实际插入时会自动生成
            }
        
        # 如果插入失败，检查是否是因为唯一约束导致的
        existing_tag = self._execute(
            "SELECT * FROM tags WHERE name = ?",
            (name.strip(),),
            fetch='one'
        )
        if existing_tag:
            logger.info(f"标签已存在: {name.strip()}")
            return dict(existing_tag)
        
        return None
    
    def get_tag_by_id(self, tag_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取标签
        
        Args:
            tag_id: 标签ID
        
        Returns:
            标签字典或None
        """
        return self._execute(
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
        if not name or not name.strip():
            return None
        
        return self._execute(
            "SELECT * FROM tags WHERE name = ?",
            (name.strip(),),
            fetch='one'
        )
    
    def get_all_tags(self) -> List[Dict[str, Any]]:
        """
        获取所有标签
        
        Returns:
            标签列表
        """
        return self._execute(
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
            logger.warning("尝试更新为空标签名称")
            return False
        
        rowcount = self._execute(
            "UPDATE tags SET name = ? WHERE id = ?",
            (new_name.strip(), tag_id),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"更新标签成功，ID: {tag_id}")
            return True
        logger.warning(f"更新标签失败，ID: {tag_id} 不存在")
        return False
    
    def delete_tag_by_id(self, tag_id: int) -> bool:
        """
        根据ID删除标签（仅在没有日记使用该标签的前提下）
        
        Args:
            tag_id: 标签ID
        
        Returns:
            是否删除成功
        """
        # 检查该标签是否被任何日记使用
        used_diary = self._execute(
            "SELECT diary_id FROM diary_tags WHERE tag_id = ? LIMIT 1",
            (tag_id,),
            fetch='one'
        )
        
        if used_diary:
            logger.warning(f"标签 {tag_id} 正被日记使用，无法删除")
            return False
        
        rowcount = self._execute(
            "DELETE FROM tags WHERE id = ?",
            (tag_id,),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"删除标签成功，ID: {tag_id}")
            return True
        logger.warning(f"删除标签失败，ID: {tag_id} 不存在")
        return False
    
    def get_unused_tags(self) -> List[Dict[str, Any]]:
        """
        获取未被使用的标签（没有日记关联的标签）
        
        Returns:
            未被使用的标签列表
        """
        return self._execute(
            """
            SELECT t.* 
            FROM tags t
            LEFT JOIN diary_tags dt ON t.id = dt.tag_id
            WHERE dt.tag_id IS NULL
            ORDER BY t.name ASC
            """,
            fetch='all'
        ) or []
    
    def add_diary_tag(self, diary_id: int, tag_id: int) -> bool:
        """
        为日记添加标签
        
        Args:
            diary_id: 日记ID
            tag_id: 标签ID
        
        Returns:
            是否添加成功
        """
        # 检查日记是否存在
        diary = self.get_diary_by_id(diary_id)
        if not diary:
            logger.warning(f"日记不存在: {diary_id}")
            return False
        
        # 检查标签是否存在
        tag = self.get_tag_by_id(tag_id)
        if not tag:
            logger.warning(f"标签不存在: {tag_id}")
            return False
        
        try:
            self._execute(
                "INSERT INTO diary_tags (diary_id, tag_id) VALUES (?, ?)",
                (diary_id, tag_id)
            )
            logger.info(f"为日记 {diary_id} 添加标签 {tag_id} 成功")
            return True
        except Exception as e:
            logger.error(f"为日记 {diary_id} 添加标签 {tag_id} 失败: {e}")
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
        rowcount = self._execute(
            "DELETE FROM diary_tags WHERE diary_id = ? AND tag_id = ?",
            (diary_id, tag_id),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"移除日记 {diary_id} 的标签 {tag_id} 成功")
            return True
        logger.info(f"日记 {diary_id} 没有关联的标签 {tag_id}")
        return False
    
    def get_tags_by_diary_id(self, diary_id: int) -> List[Dict[str, Any]]:
        """
        获取某篇日记的所有标签
        
        Args:
            diary_id: 日记ID
        
        Returns:
            标签列表
        """
        # 检查日记是否存在
        diary = self.get_diary_by_id(diary_id)
        if not diary:
            logger.warning(f"日记不存在: {diary_id}")
            return []
        
        return self._execute(
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
        # 检查标签是否存在
        tag = self.get_tag_by_id(tag_id)
        if not tag:
            logger.warning(f"标签不存在: {tag_id}")
            return []
        
        return self._execute(
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
        diary = self.get_diary_by_id(diary_id)
        if not diary:
            logger.warning(f"日记不存在: {diary_id}")
            return False
        
        # 检查所有标签是否存在
        for tag_id in tag_ids:
            tag = self.get_tag_by_id(tag_id)
            if not tag:
                logger.warning(f"标签不存在: {tag_id}")
                return False
        
        try:
            # 删除现有标签关联
            self._execute(
                "DELETE FROM diary_tags WHERE diary_id = ?",
                (diary_id,)
            )
            
            # 添加新标签关联
            if tag_ids:
                for tag_id in tag_ids:
                    self._execute(
                        "INSERT OR IGNORE INTO diary_tags (diary_id, tag_id) VALUES (?, ?)",
                        (diary_id, tag_id)
                    )
            
            logger.info(f"为日记 {diary_id} 分配 {len(tag_ids)} 个标签成功")
            return True
        except Exception as e:
            logger.error(f"为日记 {diary_id} 分配标签失败: {e}")
            return False