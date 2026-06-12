"""
垃圾桶服务工厂（Factory）

按"装配而非修改"原则，集中创建并装配垃圾桶所需的所有 sub-service：
- TrashConnectionPool
- TrashSchemaInitializer
- TrashSearchService
- TrashCapacityManager
- TrashTwoPhaseCommitCoordinator
- TrashRepository

使用方式：
    from models.repository.trash.factory import TrashServiceFactory

    factory = TrashServiceFactory(main_db, main_db_path)
    repository = factory.build()
    repository.init_schema()
"""
import logging

from .capacity import TrashCapacityManager
from .connection import TrashConnectionPool
from .repository import TrashRepository
from .schema import TrashSchemaInitializer
from .search import TrashSearchService
from .two_phase_commit import MainDbLike, TrashTwoPhaseCommitCoordinator

logger = logging.getLogger(__name__)


class TrashServiceFactory:
    """垃圾桶服务工厂"""

    def __init__(self, main_db: MainDbLike, main_db_path: str):
        self._main_db = main_db
        self._main_db_path = main_db_path

    def build(self) -> TrashRepository:
        """装配完整 TrashRepository（含全部 sub-service）"""
        pool = TrashConnectionPool(self._main_db_path)
        schema = TrashSchemaInitializer(pool)
        search = TrashSearchService(pool, schema)
        capacity = TrashCapacityManager(pool)
        two_pc = TrashTwoPhaseCommitCoordinator(pool, self._main_db)

        logger.info("垃圾桶服务工厂完成装配：main_db=%s", self._main_db_path)
        return TrashRepository(
            connection_pool=pool,
            schema=schema,
            search_service=search,
            capacity_manager=capacity,
            two_phase_commit=two_pc,
        )

    def build_connection_only(self) -> TrashConnectionPool:
        """仅创建连接池（用于单元测试等不需要全功能的场景）"""
        return TrashConnectionPool(self._main_db_path)
