"""
日记控制器
处理业务逻辑，连接模型和视图
"""
from typing import List, Dict, Optional
from ..models.database import get_db_manager
from ..models.diary import Diary


class DiaryController:
    """日记业务逻辑控制器"""
    
    def __init__(self, db_path: str = "DiaryServer/diary_data/diary.db"):
        self.db_manager = get_db_manager(db_path)
    
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
    
    def random_view_diary(self, limit: int = 20) -> Optional[Diary]:
        """随机获取一篇日记"""
        diary_dict = self.db_manager.get_random_diary(limit)
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
    
    def migrate_from_json(self, json_file_path: str) -> int:
        """从JSON文件迁移数据"""
        return self.db_manager.migrate_from_json(json_file_path)
    
    def export_to_json(self, json_file_path: str) -> bool:
        """导出数据到JSON文件"""
        return self.db_manager.export_to_json(json_file_path)