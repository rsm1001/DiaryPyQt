"""兼容旧启动方式；PyQt 实际入口已迁至 desktop/main.py。"""
from desktop.main import main


if __name__ == "__main__":
    raise SystemExit(main())
