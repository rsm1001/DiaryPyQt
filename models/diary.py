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
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建Diary实例"""
        return cls(
            id=data.get('id'),
            date=data.get('date'),
            content=data.get('content', ''),
            view_count=data.get('view_count', 0)
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'date': self.date,
            'content': self.content,
            'view_count': self.view_count
        }