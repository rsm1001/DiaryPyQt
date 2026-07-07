"""
日记操作对话框助手
"""
import logging
from PyQt6.QtWidgets import QMessageBox

from i18n import _

logger = logging.getLogger(__name__)


class DiaryActionHelper:
    """日记操作对话框辅助类"""

    @staticmethod
    def confirm_delete(parent, diary) -> bool:
        """确认删除对话框

        Args:
            parent: 父窗口
            diary: 日记对象

        Returns:
            bool: 用户是否确认删除
        """
        reply = QMessageBox.question(
            parent, _("确认删除"),
            f"{_('确定要删除日记 ID:')}{diary.id} {_('吗？')}\n\n{_('内容:')} {diary.content[:50]}...",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    @staticmethod
    def confirm_random_delete(parent, diary) -> str:
        """确认随机删除对话框

        Args:
            parent: 父窗口
            diary: 日记对象

        Returns:
            str: 'yes' 确认删除, 'next' 下一个, 'cancel' 取消
        """
        content_preview = diary.content[:200]
        if len(diary.content) > 200:
            content_preview += "..."

        message = (f"{_('即将随机删除一篇日记：')}\n\n"
                  f"ID: {diary.id}\n"
                  f"{_('日期:')} {diary.date}\n"
                  f"{_('查看次数:')} {diary.view_count}\n\n"
                  f"{_('内容:')}\n{content_preview}\n\n"
                  f"{_('确定要删除这条日记吗？')}")

        yes_btn = QMessageBox.StandardButton.Yes
        cancel_btn = QMessageBox.StandardButton.Cancel

        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(_("确认删除"))
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)
        yes_button = msg_box.addButton(_("是"), QMessageBox.ButtonRole.YesRole)
        next_button = msg_box.addButton(_("下一个"), QMessageBox.ButtonRole.NoRole)
        msg_box.addButton(_("取消"), QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(next_button)

        reply = msg_box.exec()
        clicked = msg_box.clickedButton()
        if clicked == yes_button:
            return 'yes'
        elif clicked == next_button:
            return 'next'
        return 'cancel'

    @staticmethod
    def confirm_batch_delete(parent, count: int) -> bool:
        """确认批量删除对话框

        Args:
            parent: 父窗口
            count: 要删除的数量

        Returns:
            bool: 用户是否确认删除
        """
        reply = QMessageBox.question(
            parent, _("确认批量删除"),
            f"{_('确定要删除这')} {count} {_('篇日记吗？')}\n\n{_('此操作不可恢复。')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    @staticmethod
    def show_no_diary(parent, message: str = None):
        """显示无日记提示"""
        QMessageBox.information(parent, _("提示"), message if message else _("当前没有日记"))

    @staticmethod
    def show_no_selection(parent, message: str = None):
        """显示未选择提示"""
        QMessageBox.warning(parent, _("警告"), message if message else _("请先选择一篇日记"))

    @staticmethod
    def show_delete_success(parent, diary_id: int):
        """显示删除成功提示"""
        QMessageBox.information(parent, _("成功"), f"{_('日记 ID:')}{diary_id} {_('已删除')}")

    @staticmethod
    def show_batch_result(parent, succeeded: int, failed: int, operation: str = None):
        """显示批量操作结果"""
        QMessageBox.information(parent, _("完成"),
            f"{_('成功')}{operation if operation else ''} {succeeded} {_('篇，失败')} {failed} {_('篇')}")


class AboutDialog:
    """关于对话框"""

    @staticmethod
    def show(parent):
        """显示关于对话框"""
        QMessageBox.about(
            parent, _("关于"),
            f"{_('日记管理系统')} PyQt{_('版本')}\n\n{_('版本:')} 1.0\n{_('作者:')} Assistant\n\n{_('基于PyQt6开发的现代化日记管理系统。')}"
        )
