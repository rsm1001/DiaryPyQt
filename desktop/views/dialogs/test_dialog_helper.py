"""
测试运行对话框助手
"""
import logging
from PyQt6.QtWidgets import QMessageBox

from i18n import _

logger = logging.getLogger(__name__)


class TestDialogHelper:
    """测试对话框辅助类"""

    @staticmethod
    def confirm_run_tests(parent) -> bool:
        """确认是否运行测试

        Args:
            parent: 父窗口

        Returns:
            bool: 用户是否确认运行测试
        """
        reply = QMessageBox.question(
            parent, _("运行测试"),
            _("确定要运行所有单元测试吗？这可能需要一些时间。"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    @staticmethod
    def show_test_result(parent, returncode: int, output: str):
        """显示测试结果

        Args:
            parent: 父窗口
            returncode: 测试进程的返回码
            output: 测试输出内容
        """
        summary_line = TestDialogHelper._extract_summary(output)

        if returncode == 0:
            QMessageBox.information(parent, _("测试结果"), _("所有测试通过！") + f"\n\n{summary_line}")
            logger.info("测试全部通过")
        else:
            error_lines = output.split("\n")
            error_output = "\n".join(error_lines[-100:])
            QMessageBox.critical(parent, _("测试失败"),
                _("有测试用例失败！") + f"\n\n{summary_line}\n\n{error_output[:2000]}")
            logger.error(f"测试失败: {summary_line}")

    @staticmethod
    def _extract_summary(output: str) -> str:
        """从测试输出中提取摘要信息"""
        lines = output.split("\n")
        for line in lines:
            if "passed" in line or "failed" in line or "error" in line:
                if "==" in line or "passed" in line:
                    return line.strip()
        return ""


class TestDialogFactory:
    """测试对话框工厂"""

    @staticmethod
    def create_test_result_handler(parent):
        """创建测试结果处理器

        Args:
            parent: 父窗口

        Returns:
            callable: 处理测试结果的函数
        """
        return lambda returncode, output: TestDialogHelper.show_test_result(parent, returncode, output)
