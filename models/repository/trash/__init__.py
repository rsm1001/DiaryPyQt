"""
垃圾桶领域子包

本子包按职责垂直拆分：
- connection          : 垃圾桶数据库连接池与事务
- schema              : 垃圾桶数据库 Schema 初始化（含 FTS5）
- search              : 垃圾桶搜索服务（FTS5 + LIKE 兜底）
- capacity            : 垃圾桶容量（LRU 淘汰）管理
- two_phase_commit    : 垃圾桶 2PC 跨库事务协调器
- factory             : 装配工厂（Factory Pattern）
- repository          : 仓储门面（Repository Pattern）

使用示例（典型装配流程）：

    from models.repository.trash import TrashServiceFactory

    factory = TrashServiceFactory(main_db, db_path)
    repository = factory.build()
    repository.init_schema()              # 初始化 Schema
    repository.recover_pending_ops()       # 启动恢复（如有）
    # ... 业务调用
    repository.close()

外部仍可通过 ``TrashMixin``（见 ``models/repository/trash_mixin.py``）以
混入类方式访问全部接口，保持向后兼容。
"""
from .capacity import TrashCapacityManager
from .connection import TrashConnectionPool
from .factory import TrashServiceFactory
from .repository import TrashRepository
from .schema import TrashSchemaInitializer
from .search import TrashSearchService
from .two_phase_commit import (
    MainDbLike,
    TrashTwoPhaseCommitCoordinator,
)

__all__ = [
    "TrashConnectionPool",
    "TrashSchemaInitializer",
    "TrashSearchService",
    "TrashCapacityManager",
    "TrashTwoPhaseCommitCoordinator",
    "TrashRepository",
    "TrashServiceFactory",
    "MainDbLike",
]
