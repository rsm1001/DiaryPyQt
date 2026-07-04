"""
随机查看标签筛选管理器
负责随机查看时的标签过滤状态持久化，支持 QSettings 存储
"""
import json
import logging
from PyQt6.QtCore import QSettings
from typing import List

logger = logging.getLogger(__name__)


class RandomViewFilterManager:
    """随机查看标签筛选管理器"""

    SETTINGS_KEY = "random_view_tag_filter"
    APP_NAME = "DiaryPyQt"
    ORG_NAME = "DiaryPyQt"

    def __init__(self):
        self.settings = QSettings(self.ORG_NAME, self.APP_NAME)
        self._selected_tag_ids: List[int] = self._load()

    def _load(self) -> List[int]:
        """从 QSettings 加载已保存的标签筛选状态"""
        try:
            stored = self.settings.value(self.SETTINGS_KEY)
            if stored:
                tag_ids = json.loads(stored)
                if isinstance(tag_ids, list):
                    logger.debug("随机查看筛选标签已加载: %s", tag_ids)
                    return tag_ids
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"随机查看筛选标签加载失败，使用空列表: {e}")
        return []

    def get_selected_tag_ids(self) -> List[int]:
        """获取当前选中的标签ID列表"""
        return self._selected_tag_ids.copy()

    def set_selected_tag_ids(self, tag_ids: List[int]) -> None:
        """设置选中的标签ID列表"""
        self._selected_tag_ids = list(tag_ids)
        self.save()

    def clear(self) -> None:
        """清除筛选状态"""
        self._selected_tag_ids = []
        self.save()
        logger.debug("随机查看筛选标签已清除")

    def is_filter_active(self) -> bool:
        """判断是否有激活的标签筛选"""
        return len(self._selected_tag_ids) > 0

    def save(self) -> None:
        """保存筛选状态到 QSettings"""
        try:
            self.settings.setValue(self.SETTINGS_KEY, json.dumps(self._selected_tag_ids))
            self.settings.sync()
            logger.debug("随机查看筛选标签已保存: %s", self._selected_tag_ids)
        except Exception as e:
            logger.error(f"随机查看筛选标签保存失败: {e}")
