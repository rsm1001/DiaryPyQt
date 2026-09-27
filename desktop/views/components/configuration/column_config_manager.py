"""
列配置管理器
负责管理表格列的显示/隐藏、宽度、顺序等配置，支持 QSettings 持久化
"""
import json
import logging
from PyQt6.QtCore import QSettings
from i18n import _

logger = logging.getLogger(__name__)

# 列定义：ID、标题、默认宽度(像素)
DEFAULT_COLUMNS = [
    {'id': 'id',      'title': _('ID'),         'default_width': 50},
    {'id': 'date',    'title': _('日期'),       'default_width': 120},
    {'id': 'views',   'title': _('查看次数'),    'default_width': 70},
    {'id': 'tags',    'title': _('标签'),        'default_width': 100},
    {'id': 'preview', 'title': _('内容预览'),    'default_width': 250},
]


class ColumnConfigManager:
    """列配置管理器"""

    SETTINGS_KEY = "table_column_config"
    APP_NAME = "DiaryPyQt"
    ORG_NAME = "DiaryPyQt"

    def __init__(self):
        self.settings = QSettings(self.ORG_NAME, self.APP_NAME)
        self._config = self._load_or_default()

    def _load_or_default(self):
        """加载配置，失败则返回默认配置"""
        try:
            stored = self.settings.value(self.SETTINGS_KEY)
            if stored:
                config = json.loads(stored)
                # 验证配置完整性
                if self._validate_config(config):
                    logger.debug("列配置已从 QSettings 加载")
                    return config
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"列配置加载失败，使用默认配置: {e}")
        return self._get_default_config()

    def _validate_config(self, config):
        """验证配置完整性"""
        if not isinstance(config, list):
            return False
        # 检查是否有5列，且包含必要字段
        if len(config) != 5:
            return False
        required_fields = {'id', 'title', 'visible', 'width', 'order'}
        for col in config:
            if not isinstance(col, dict):
                return False
            if not required_fields.issubset(col.keys()):
                return False
        return True

    def _get_default_config(self):
        """获取默认列配置"""
        return [
            {'id': col['id'], 'title': col['title'], 'visible': True,
             'width': col['default_width'], 'order': i}
            for i, col in enumerate(DEFAULT_COLUMNS)
        ]

    def get_config(self):
        """获取当前列配置"""
        return self._config

    def get_visible_columns(self):
        """获取可见列配置，按 order 排序"""
        visible = [c for c in self._config if c['visible']]
        return sorted(visible, key=lambda x: x['order'])

    def get_headers(self):
        """获取当前可见列的表头列表（按顺序）"""
        visible = self.get_visible_columns()
        return [col['title'] for col in visible]

    def get_column_count(self):
        """获取可见列数量"""
        return len(self.get_visible_columns())

    def get_col_id_by_visual_index(self, visual_index):
        """根据视觉索引获取列 ID"""
        visible = self.get_visible_columns()
        if 0 <= visual_index < len(visible):
            return visible[visual_index]['id']
        return None

    def get_col_index_by_id(self, col_id):
        """根据列 ID 获取配置索引（配置列表中的索引，非视觉索引）"""
        for i, col in enumerate(self._config):
            if col['id'] == col_id:
                return i
        return None

    def get_col_width(self, col_id):
        """获取列宽度"""
        for col in self._config:
            if col['id'] == col_id:
                return col['width']
        return 100

    def is_column_visible(self, col_id):
        """判断列是否可见"""
        for col in self._config:
            if col['id'] == col_id:
                return col['visible']
        return True

    def set_column_visible(self, col_id, visible):
        """设置列可见性"""
        for col in self._config:
            if col['id'] == col_id:
                col['visible'] = visible
                logger.debug(f"设置列 {col_id} 可见性: {visible}")
                return True
        return False

    def set_column_width(self, col_id, width):
        """设置列宽度"""
        for col in self._config:
            if col['id'] == col_id:
                col['width'] = width
                return True
        return False

    def set_column_order(self, col_id, new_order):
        """设置列顺序"""
        # 获取当前 order 列表
        orders = [col['order'] for col in self._config]
        if new_order not in orders:
            return False

        # 重新分配 order：将 col_id 移到 new_order 位置，其他列顺序调整
        target_col = None
        for col in self._config:
            if col['id'] == col_id:
                target_col = col
                break
        if not target_col:
            return False

        old_order = target_col['order']
        if old_order == new_order:
            return True

        # 调整其他列的 order
        for col in self._config:
            if col['id'] == col_id:
                col['order'] = new_order
            else:
                if old_order < new_order:
                    # 向后移动：old_order < col['order'] <= new_order 的列减1
                    if old_order < col['order'] <= new_order:
                        col['order'] -= 1
                else:
                    # 向前移动：new_order <= col['order'] < old_order 的列加1
                    if new_order <= col['order'] < old_order:
                        col['order'] += 1

        logger.debug(f"列 {col_id} 从 order {old_order} 移动到 {new_order}")
        return True

    def update_config(self, new_config):
        """更新整个配置"""
        if self._validate_config(new_config):
            self._config = new_config
            return True
        return False

    def save(self):
        """保存配置到 QSettings"""
        try:
            self.settings.setValue(self.SETTINGS_KEY, json.dumps(self._config))
            self.settings.sync()
            logger.debug("列配置已保存到 QSettings")
            return True
        except Exception as e:
            logger.error(f"列配置保存失败: {e}")
            return False

    def reset_to_default(self):
        """重置为默认配置"""
        self._config = self._get_default_config()
        self.save()
        logger.info("列配置已重置为默认")
