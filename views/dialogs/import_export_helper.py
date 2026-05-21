"""
导入导出对话框助手
"""
import logging
from PyQt6.QtWidgets import QFileDialog, QMessageBox

logger = logging.getLogger(__name__)


class ImportExportHelper:
    """导入导出操作辅助类"""

    @staticmethod
    def export_data(parent, controller):
        """导出数据到文件

        Args:
            parent: 父窗口
            controller: 日记控制器

        Returns:
            bool: 导出是否成功
        """
        file_path, _ = QFileDialog.getSaveFileName(
            parent, "导出数据", "", "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return False

        if controller.export_to_json(file_path):
            QMessageBox.information(parent, "成功", "数据导出成功")
            logger.info(f"导出数据: {file_path}")
            return True
        else:
            QMessageBox.critical(parent, "错误", "数据导出失败")
            logger.error(f"导出数据失败: {file_path}")
            return False

    @staticmethod
    def import_data(parent, controller, load_callback):
        """从文件导入数据

        Args:
            parent: 父窗口
            controller: 日记控制器
            load_callback: 加载完成后的回调函数

        Returns:
            int: 导入的日记数量，-1 表示用户取消
        """
        file_path, _ = QFileDialog.getOpenFileName(
            parent, "导入数据", "", "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return -1

        result = controller.migrate_from_json(file_path)
        QMessageBox.information(parent, "导入结果", f"成功导入 {result} 篇日记")
        logger.info(f"导入数据: {file_path}, 导入 {result} 篇")

        if load_callback:
            load_callback()

        return result


class ImportExportFactory:
    """导入导出工厂"""

    @staticmethod
    def create_export_handler(parent, controller):
        """创建导出处理器"""
        return lambda: ImportExportHelper.export_data(parent, controller)

    @staticmethod
    def create_import_handler(parent, controller, load_callback):
        """创建导入处理器"""
        return lambda: ImportExportHelper.import_data(parent, controller, load_callback)
