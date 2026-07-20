"""
日记动作处理器：负责日记条目的查看、新建、编辑、删除与批量操作。

将原 MainWindow 中所有与单条/批量日记相关的操作集中到该类，
以事件回调（由 MainWindow 注册）形式提供入口，MainWindow 仅保留
薄薄的委托方法。
"""
import logging
from typing import Optional

from PyQt6.QtWidgets import QDialog

from i18n import _
from utils.formatters import format_tags_html
from views.dialogs.diary_action_helper import DiaryActionHelper
from views.dialogs.diary_dialogs import DiaryEditDialog, DiaryViewDialog
from views.dialogs.batch_tag_dialog import BatchTagDialog

logger = logging.getLogger(__name__)


class DiaryActions:
    """日记相关动作的统一处理入口"""

    def __init__(self, window):
        # 通过引用 MainWindow 解耦，但只调用其对外暴露的薄方法
        self._window = window
        logger.debug("DiaryActions 初始化完成")

    # ------------------------------------------------------------------
    # 表格点击
    # ------------------------------------------------------------------
    def on_table_clicked(self, index) -> None:
        """表格点击：更新详情面板并累加查看次数"""
        diary = self._window.table_manager.get_selected_diary(index)
        if not diary:
            return
        tags_html = format_tags_html(diary.tags if hasattr(diary, "tags") else [])
        self._window.detail_panel.update_content(diary, tags_html)
        self._window.controller.increment_view_count(diary.id)
        self._window.load_data()
        logger.info("查看日记: id=%s", diary.id)

    # ------------------------------------------------------------------
    # 单条操作
    # ------------------------------------------------------------------
    def new_diary(self) -> None:
        """新建日记"""
        dialog = DiaryEditDialog(self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        content = dialog.get_content()
        if not content.strip():
            return
        diary = self._window.controller.add_diary(content)
        selected_tag_ids = dialog.get_selected_tag_ids()
        if diary and selected_tag_ids:
            self._window.controller.assign_tags_to_diary(
                diary.id, selected_tag_ids
            )
        self._window.load_data()
        logger.info("新建日记完成")

    def random_view(self) -> None:
        """随机查看日记"""
        tag_ids = self._window.random_filter_manager.get_selected_tag_ids()
        diary = self._window.controller.random_view_diary(tag_ids=tag_ids)
        if not diary:
            DiaryActionHelper.show_no_diary(self._window)
            return
        new_count = self._window.controller.increment_view_count(diary.id)
        if new_count is not None:
            diary.view_count = new_count
        dialog = DiaryViewDialog(diary, self._window, readonly=True, tag_ids=tag_ids)
        dialog.exec()
        self._window.load_data()
        logger.info("随机查看日记: id=%s", diary.id)

    def random_delete(self) -> None:
        """随机删除日记"""
        while True:
            diary = self._window.controller.get_diary_for_deletion()
            if not diary:
                DiaryActionHelper.show_no_diary(self._window, "没有可删除的日记")
                return
            result = DiaryActionHelper.confirm_random_delete(self._window, diary)
            if result == 'yes':
                self._window.controller.delete_diary_by_id(diary.id)
                self._window.load_data()
                DiaryActionHelper.show_delete_success(self._window, diary.id)
                logger.info("删除日记: id=%s", diary.id)
                return
            elif result == 'cancel':
                return
            # result == 'next': 继续循环获取下一条

    def search_diary(self) -> None:
        """搜索日记"""
        from views.search_dialog import SearchDialog  # 延迟导入避免循环

        dialog = SearchDialog(self._window.controller, self._window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._window.load_data()

    # ------------------------------------------------------------------
    # 选中行操作
    # ------------------------------------------------------------------
    def view_selected(self) -> None:
        """查看选中日记"""
        diary = self._get_single_selected_diary()
        if not diary:
            return
        dialog = DiaryViewDialog(diary, self._window, readonly=True)
        dialog.exec()
        self._window.controller.increment_view_count(diary.id)
        self._window.load_data()

    def edit_selected(self) -> None:
        """编辑选中日记"""
        diary = self._get_single_selected_diary()
        if not diary:
            return
        dialog = DiaryEditDialog(self._window, diary)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        content = dialog.get_content()
        if not content.strip():
            return
        self._window.controller.update_diary(diary.id, content)
        self._window.controller.assign_tags_to_diary(
            diary.id, dialog.get_selected_tag_ids()
        )
        self._window.load_data()

    def delete_selected(self) -> None:
        """删除选中日记"""
        diary = self._get_single_selected_diary()
        if not diary:
            return
        if not DiaryActionHelper.confirm_delete(self._window, diary):
            return
        self._window.controller.delete_diary_by_id(diary.id)
        self._window.load_data()
        DiaryActionHelper.show_delete_success(self._window, diary.id)

    # ------------------------------------------------------------------
    # 批量操作
    # ------------------------------------------------------------------
    def batch_delete_selected(self) -> None:
        """批量删除"""
        diaries = self._get_multi_selected_diaries()
        if not diaries:
            return
        if not DiaryActionHelper.confirm_batch_delete(self._window, len(diaries)):
            return
        result = self._window.controller.batch_delete_diaries(
            [d.id for d in diaries]
        )
        self._window.load_data()
        DiaryActionHelper.show_batch_result(
            self._window, result["succeeded"], result["failed"], "删除"
        )

    def batch_tag_selected(self) -> None:
        """批量打标签"""
        diaries = self._get_multi_selected_diaries()
        if not diaries:
            return
        dialog = BatchTagDialog(self._window.controller, diaries, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected_tag_ids = dialog.get_selected_tag_ids()
        if selected_tag_ids is None:
            return
        result = self._window.controller.batch_assign_tags(
            [d.id for d in diaries], list(selected_tag_ids)
        )
        self._window.load_data()
        DiaryActionHelper.show_batch_result(
            self._window, result["succeeded"], result["failed"], "更新"
        )

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _get_single_selected_diary(self):
        """获取单选日记；无选或多选时统一给出提示并返回 None"""
        selected = self._window.table_manager.get_selected_rows()
        if not selected:
            DiaryActionHelper.show_no_selection(self._window)
            return None
        return self._window.table_manager.get_selected_diary(selected[0])

    def _get_multi_selected_diaries(self) -> list:
        """获取多选日记列表"""
        selected = self._window.table_manager.get_selected_rows()
        if not selected:
            return []
        return self._window.model.get_selected_diaries(selected) or []