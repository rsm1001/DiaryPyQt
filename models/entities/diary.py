"""
日记数据模型
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Diary:
    """
    日记数据模型
    """
    id: Optional[int] = None
    date: Optional[str] = None
    content: str = ""
    view_count: int = 0
    last_viewed_at: Optional[str] = None
    tags: list = None  # 新增标签列表字段
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建Diary实例"""
        return cls(
            id=data.get('id'),
            date=data.get('date'),
            content=data.get('content', ''),
            view_count=data.get('view_count', 0),
            last_viewed_at=data.get('last_viewed_at'),
            tags=data.get('tags', [])  # 新增标签处理
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'date': self.date,
            'content': self.content,
            'view_count': self.view_count,
            'last_viewed_at': self.last_viewed_at,
            'tags': self.tags  # 新增标签字段
        }