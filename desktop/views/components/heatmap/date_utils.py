"""
热力图日期工具

提供与 PyQt QDate 交互的纯函数：
- 周一/周日吸附：用于将任意日期对齐到 Mon-first 周界
- 月份标题本地化：中文 "2026 年 6 月"，英文 "Jun 2026"
- 当前语言判断：通过 i18n 模块判断是否中文，用于星期 / 月份表头切换

仅依赖 PyQt 的 QDate，与 i18n 通过 ``get_current_language`` 软耦合
（异常时默认中文，保证 UI 始终可用）。
"""
import logging
from typing import Optional

from PyQt6.QtCore import QDate

from i18n import get_current_language

logger = logging.getLogger(__name__)


def snap_to_monday(date: QDate) -> QDate:
    """向前回退到所在周的周一（PyQt dayOfWeek: 1=Mon..7=Sun）。"""
    return date.addDays(-(date.dayOfWeek() - 1))


def snap_to_sunday(date: QDate) -> QDate:
    """向后推进到所在周的周日。"""
    delta = (7 - date.dayOfWeek()) % 7
    return date.addDays(delta)


def is_chinese_locale() -> bool:
    """判断当前语言是否中文，用于星期 / 月份表头切换。"""
    try:
        return get_current_language() == 'zh_CN'
    except Exception as exc:  # i18n 未初始化时降级为中文
        logger.debug("i18n 不可用，回退中文：%s", exc)
        return True


def format_month_label(qdate: Optional[QDate]) -> str:
    """
    格式化月份标题：
    - 中文："2026 年 6 月"
    - 英文："Jun 2026"
    """
    if qdate is None or not qdate.isValid():
        return ""
    if is_chinese_locale():
        return f"{qdate.year()} 年 {qdate.month()} 月"
    en = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
    return f"{en[qdate.month() - 1]} {qdate.year()}"
