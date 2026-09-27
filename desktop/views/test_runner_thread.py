"""
测试运行线程模块
"""
import subprocess
import logging
import sys
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class TestRunnerThread(QThread):
    """后台测试运行线程"""

    test_finished = pyqtSignal(int, str)

    def __init__(self, tests_dir: str, python_executable: str = None):
        """初始化测试运行线程

        Args:
            tests_dir: 测试目录路径
            python_executable: Python 解释器路径，默认使用 sys.executable
        """
        super().__init__()
        self.tests_dir = tests_dir
        self.python_executable = python_executable or sys.executable
        logger.debug(f"TestRunnerThread 初始化: tests_dir={tests_dir}")

    def run(self):
        """在线程中执行测试"""
        logger.info("开始运行测试")
        try:
            result = subprocess.run(
                [self.python_executable, "-m", "pytest", self.tests_dir, "-v", "--tb=short", "-q"],
                capture_output=True,
                text=True,
                timeout=300
            )
            self.test_finished.emit(result.returncode, result.stdout + result.stderr)
            logger.info(f"测试完成: returncode={result.returncode}")
        except subprocess.TimeoutExpired:
            logger.error("测试运行超时（5分钟）")
            self.test_finished.emit(-1, "测试运行超时（5分钟）")
        except Exception as e:
            logger.error(f"运行测试时出错: {str(e)}")
            self.test_finished.emit(-2, f"运行测试时出错：\n{str(e)}")


class TestRunnerFactory:
    """测试运行器工厂"""

    @staticmethod
    def create_runner(tests_dir: str, python_executable: str = None) -> TestRunnerThread:
        """创建测试运行器

        Args:
            tests_dir: 测试目录路径
            python_executable: Python 解释器路径

        Returns:
            TestRunnerThread 实例
        """
        logger.debug(f"创建 TestRunner: {tests_dir}")
        return TestRunnerThread(tests_dir, python_executable)
