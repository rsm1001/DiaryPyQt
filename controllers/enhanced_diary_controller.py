"""
日记控制器 - 增强版
使用增强版数据库管理器，支持完整的迁移和备份功能
"""
from typing import List, Dict, Optional
from models.enhanced_database import get_enhanced_db_manager
from models.entities.diary import Diary


class EnhancedDiaryController:
    """增强版日记业务逻辑控制器"""
    
    def __init__(self, db_path: str = None):
        self.db_manager = get_enhanced_db_manager(db_path)
    
    def add_diary(self, content: str) -> Optional[Diary]:
        """添加新日记"""
        diary_dict = self.db_manager.add_diary(content)
        if diary_dict:
            return Diary.from_dict(diary_dict)
        return None
    
    def get_diary_by_id(self, diary_id: int) -> Optional[Diary]:
        """根据ID获取日记"""
        diary_dict = self.db_manager.get_diary_by_id(diary_id)
        if diary_dict:
            return Diary.from_dict(diary_dict)
        return None
    
    def update_diary(self, diary_id: int, new_content: str) -> bool:
        """更新日记内容"""
        return self.db_manager.update_diary(diary_id, new_content)
    
    def delete_diary_by_id(self, diary_id: int) -> Optional[Diary]:
        """根据ID删除日记"""
        diary_dict = self.db_manager.delete_diary_by_id(diary_id)
        if diary_dict:
            return Diary.from_dict(diary_dict)
        return None
    
    def get_all_diaries(self, limit: Optional[int] = None) -> List[Diary]:
        """获取所有日记"""
        diaries_dicts = self.db_manager.get_all_diaries(limit)
        return [Diary.from_dict(d) for d in diaries_dicts]
    
    def increment_view_count(self, diary_id: int) -> Optional[int]:
        """增加日记查看次数"""
        return self.db_manager.increment_view_count(diary_id)
    
    def decrease_view_count(self, diary_id: int, penalty: int = 1) -> bool:
        """减少日记查看次数"""
        return self.db_manager.decrease_view_count(diary_id, penalty)
    
    def get_most_viewed_diaries(self, limit: int = 20) -> List[Diary]:
        """获取查看次数最多的日记"""
        diaries_dicts = self.db_manager.get_most_viewed_diaries(limit)
        return [Diary.from_dict(d) for d in diaries_dicts]
    
    def get_least_viewed_diaries(self, limit: int = 20) -> List[Diary]:
        """获取查看次数最少的日记"""
        diaries_dicts = self.db_manager.get_least_viewed_diaries(limit)
        return [Diary.from_dict(d) for d in diaries_dicts]
    
    def get_oldest_in_most_viewed(self, limit: int = 20) -> Optional[Dict]:
        """获取查看次数最多的日记中最久远的"""
        return self.db_manager.get_oldest_in_most_viewed(limit)
    
    def random_view_diary(self, limit: int = None) -> Optional[Diary]:
        """随机获取一篇日记"""
        diary_dict = self.db_manager.get_random_diary(limit)
        if diary_dict:
            return Diary.from_dict(diary_dict)
        return None

    def get_diary_for_deletion(self, limit: int = None) -> Optional[Diary]:
        """获取一篇适合删除的日记（时间久远且查看次数多）"""
        diary_dict = self.db_manager.get_diary_for_deletion(limit)
        if diary_dict:
            return Diary.from_dict(diary_dict)
        return None
    
    def search_by_keyword(self, keyword: str, limit: int = 18) -> List[Diary]:
        """根据关键词搜索日记"""
        diaries_dicts = self.db_manager.search_by_keyword(keyword, limit)
        return [Diary.from_dict(d) for d in diaries_dicts]
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return self.db_manager.get_statistics()
    
    def get_daily_stats(self) -> Dict:
        """获取每日统计信息（昨日查看总数 + 历史最佳）"""
        return self.db_manager.get_daily_stats()
    
    def get_today_total_views(self) -> int:
        """获取今日查看总数（实时）"""
        return self.db_manager.statistics_service.get_today_total_views()
    
    def migrate_from_json(self, json_file_path: str) -> int:
        """从JSON文件迁移数据"""
        return self.db_manager.migrate_from_json(json_file_path)
    
    def migrate_from_csv(self, csv_file_path: str) -> int:
        """从CSV文件迁移数据"""
        return self.db_manager.migrate_from_csv(csv_file_path)
    
    def export_to_json(self, json_file_path: str) -> bool:
        """导出数据到JSON文件"""
        return self.db_manager.export_to_json(json_file_path)
    
    def export_to_csv(self, csv_file_path: str) -> bool:
        """导出数据到CSV文件"""
        return self.db_manager.export_to_csv(csv_file_path)
    
    def backup_database(self, backup_path: str) -> bool:
        """备份数据库"""
        return self.db_manager.backup_database(backup_path)
    
    def restore_database(self, backup_path: str) -> bool:
        """从备份恢复数据库"""
        return self.db_manager.restore_database(backup_path)
    
    def get_diary_with_tags_by_id(self, diary_id: int) -> Optional[Diary]:
        """获取日记及其所有标签"""
        diary_dict = self.db_manager.get_diary_with_tags_by_id(diary_id)
        if diary_dict:
            return Diary.from_dict(diary_dict)
        return None

    def get_all_diaries_with_tags(self, limit: Optional[int] = None) -> List[Diary]:
        """获取所有日记及其标签"""
        diaries_dicts = self.db_manager.get_all_diaries_with_tags(limit)
        return [Diary.from_dict(d) for d in diaries_dicts]
    
    # ========================================================================
    # 标签操作
    # ========================================================================
    
    def add_tag(self, name: str) -> Optional[Dict]:
        """添加新标签"""
        return self.db_manager.add_tag(name)
    
    def get_tag_by_id(self, tag_id: int) -> Optional[Dict]:
        """根据ID获取标签"""
        return self.db_manager.get_tag_by_id(tag_id)
    
    def get_tag_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取标签"""
        return self.db_manager.get_tag_by_name(name)
    
    def get_all_tags(self) -> List[Dict]:
        """获取所有标签"""
        return self.db_manager.get_all_tags()
    
    def update_tag(self, tag_id: int, new_name: str) -> bool:
        """更新标签名称"""
        return self.db_manager.update_tag(tag_id, new_name)
    
    def delete_tag_by_id(self, tag_id: int) -> bool:
        """删除标签（仅在未被使用的前提下）"""
        return self.db_manager.delete_tag_by_id(tag_id)
    
    def get_unused_tags(self) -> List[Dict]:
        """获取未被使用的标签"""
        return self.db_manager.get_unused_tags()
    
    # ========================================================================
    # 日记-标签关联操作
    # ========================================================================
    
    def add_diary_tag(self, diary_id: int, tag_id: int) -> bool:
        """为日记添加标签"""
        return self.db_manager.add_diary_tag(diary_id, tag_id)
    
    def remove_diary_tag(self, diary_id: int, tag_id: int) -> bool:
        """移除日记的特定标签"""
        return self.db_manager.remove_diary_tag(diary_id, tag_id)
    
    def get_tags_by_diary_id(self, diary_id: int) -> List[Dict]:
        """获取某篇日记的所有标签"""
        return self.db_manager.get_tags_by_diary_id(diary_id)
    
    def get_diaries_by_tag_id(self, tag_id: int) -> List[Diary]:
        """获取标记了特定标签的所有日记"""
        diaries_dicts = self.db_manager.get_diaries_by_tag_id(tag_id)
        return [Diary.from_dict(d) for d in diaries_dicts]
    
    def assign_tags_to_diary(self, diary_id: int, tag_ids: List[int]) -> bool:
        """为日记分配一组标签（替换原有标签）"""
        return self.db_manager.assign_tags_to_diary(diary_id, tag_ids)

    def batch_delete_diaries(self, diary_ids: List[int]) -> Dict[str, int]:
        """批量移动日记到垃圾桶

        Args:
            diary_ids: 日记ID列表

        Returns:
            包含 succeeded 和 failed 数量的字典
        """
        succeeded = 0
        failed = 0
        for diary_id in diary_ids:
            try:
                if self.delete_diary_by_id(diary_id):
                    succeeded += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        return {'succeeded': succeeded, 'failed': failed}

    def batch_assign_tags(self, diary_ids: List[int], tag_ids: List[int]) -> Dict[str, int]:
        """批量为日记分配标签

        Args:
            diary_ids: 日记ID列表
            tag_ids: 标签ID列表

        Returns:
            包含 succeeded 和 failed 数量的字典
        """
        succeeded = 0
        failed = 0
        for diary_id in diary_ids:
            try:
                if self.assign_tags_to_diary(diary_id, tag_ids):
                    succeeded += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        return {'succeeded': succeeded, 'failed': failed}
    
    def cleanup_old_view_logs(self) -> int:
        """清理昨日与今日之外的所有查看日志"""
        return self.db_manager.view_count_service.cleanup_old_view_logs()
    
    # ========================================================================
    # 垃圾桶操作
    # ========================================================================
    
    def move_to_trash(self, diary_id: int) -> Optional[Dict]:
        """将日记移动到垃圾桶（软删除）"""
        return self.db_manager.move_to_trash(diary_id)
    
    def restore_from_trash(self, trash_id: int) -> Optional[Diary]:
        """从垃圾桶恢复日记"""
        diary_dict = self.db_manager.restore_from_trash(trash_id)
        if diary_dict:
            return Diary.from_dict(diary_dict)
        return None
    
    def get_all_trash_diaries(self, limit: Optional[int] = None) -> List[Dict]:
        """获取所有垃圾桶中的日记"""
        return self.db_manager.get_all_trash_diaries(limit)
    
    def search_trash_by_keyword(self, keyword: str, limit: int = 100) -> List[Dict]:
        """在垃圾桶中搜索日记"""
        return self.db_manager.search_trash_by_keyword(keyword, limit)
    
    def get_trash_count(self) -> int:
        """获取垃圾桶中的日记数量"""
        return self.db_manager.get_trash_count()
    
    def permanently_delete_trash(self, trash_id: int) -> bool:
        """永久删除垃圾桶中的日记"""
        return self.db_manager.permanently_delete_trash(trash_id)
    
    def empty_trash(self) -> int:
        """清空整个垃圾桶"""
        return self.db_manager.empty_trash()