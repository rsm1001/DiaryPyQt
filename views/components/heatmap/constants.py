"""
热力图常量与色阶

集中管理：
- 浅色 / 深色主题下的 5 级色阶（与项目强调色 #4dabf7 / #339af0 保持一致）
- 浅色 / 深色主题下的背景色与文本色
- 中英文星期表头
- 单元格尺寸、步长等布局常量
- count -> level 的纯函数映射

本模块不依赖 PyQt，可在无 GUI 环境下被复用与单测。
"""
from dataclasses import dataclass
from typing import Dict, Final


# ---------------------------------------------------------------------------
# 浅色 / 深色色阶
# ---------------------------------------------------------------------------
LEVELS_LIGHT: Final[Dict[int, str]] = {
    0: '#ebedf0',
    1: '#d0ebff',
    2: '#74c0fc',
    3: '#339af0',
    4: '#1971c2',
}

LEVELS_DARK: Final[Dict[int, str]] = {
    0: '#2b2b2b',
    1: '#1c3a5e',
    2: '#2a5a8a',
    3: '#3a8edb',
    4: '#74c0fc',
}

BG_LIGHT: Final[str] = '#f8f9fa'
BG_DARK: Final[str] = '#1e1e1e'
TEXT_LIGHT: Final[str] = '#495057'
TEXT_DARK: Final[str] = '#dcdcdc'

DAY_LABELS_CN: Final[tuple] = ('一', '二', '三', '四', '五', '六', '日')
DAY_LABELS_EN: Final[tuple] = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


@dataclass(frozen=True)
class HeatmapLayout:
    """热力图布局常量集合（用 dataclass 方便整体传递与未来扩展）。"""
    cell_size: int = 12
    cell_padding: int = 2
    stride: int = 14
    top_label_height: int = 20
    outer_padding: int = 6
    # 自适应模式下 cell 尺寸的上下界（与 280px 侧栏下 QCalendarWidget 列宽对齐）
    min_stride: int = 12
    max_stride: int = 35
    min_cell_size: int = 8
    # 启用日期角标显示的最小 cell 尺寸
    day_number_cell_threshold: int = 24


DEFAULT_LAYOUT: Final[HeatmapLayout] = HeatmapLayout()


def level_for_count(count: int) -> int:
    """
    根据日记数量返回 0-4 的色阶等级。

    阈值划分（保持与历史观感一致）：
    - 0       -> 0
    - 1       -> 1
    - 2..3    -> 2
    - 4..6    -> 3
    - >=7     -> 4
    """
    if count <= 0:
        return 0
    if count == 1:
        return 1
    if count <= 3:
        return 2
    if count <= 6:
        return 3
    return 4
