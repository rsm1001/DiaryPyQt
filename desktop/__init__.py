"""迁移后的 PyQt 包；旧模块暂保留原有绝对导入路径。"""
import sys
from pathlib import Path

_desktop_root = str(Path(__file__).resolve().parent)
if _desktop_root not in sys.path:
    sys.path.insert(0, _desktop_root)
