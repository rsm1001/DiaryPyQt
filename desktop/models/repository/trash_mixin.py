"""
垃圾桶操作混入类（门面层）

本 Mixin 不再直接持有业务实现，而是将所有垃圾桶相关操作委托给
``TrashRepository``（见 ``models.repository.trash`` 子包）。

设计要点：
- 保留对外公共方法签名，确保调用方（EnhancedDatabaseManager / Controller / View）零修改
- TrashRepository 在首次使用时由 TrashServiceFactory 懒加载创建（线程安全）
- 与主库同目录的 trash_<basename>.db 文件路径由 TrashConnectionPool 负责推导
- 2PC 跨库事务由 TrashTwoPhaseCommitCoordinator 负责协调，本类仅做编排
"""
import logging
import threading
from typing import Any, Dict, List, Optional

from models.repository.trash import (
    MainDbLike,
    TrashRepository,
    TrashServiceFactory,
)

logger = logging.getLogger(__name__)


class TrashMixin:
    """垃圾桶操作混入类（门面层，委托给 TrashRepository）"""

    # ============================================================
    # 子类需提供的能力（由 ConnectionMixin / TagManagementMixin 满足）
    # ============================================================
    #
    #   - self.db_path
    #   - self._db_lock
    #   - self._transaction()
    #   - self._execute(query, params, fetch)
    #   - self.compute_tokens(content)
    #   - self.get_diary_by_id(diary_id)
    #   - self.get_tags_by_diary_id(diary_id)
    #   - self.get_tag_by_id(tag_id)
    #   - self.get_tag_by_name(name)
    #   - self.add_tag(name)

    # ============================================================
    # Repository 懒加载
    # ============================================================

    def _ensure_trash_repository(self) -> TrashRepository:
        """懒加载 TrashRepository（线程安全，只创建一次）"""
        # 使用 getattr + 默认值规避 EnhancedDatabaseManager.__getattr__ 严格兜底
        repo = getattr(self, "_trash_repository", None)
        if repo is not None:
            return repo

        # 兜底初始化：属性可能尚未声明（mixin 单独使用场景）
        if not hasattr(self, "_trash_repository_lock"):
            self._trash_repository_lock = threading.Lock()

        with self._trash_repository_lock:
            repo = getattr(self, "_trash_repository", None)
            if repo is None:
                factory = TrashServiceFactory(
                    main_db=self,  # type: ignore[arg-type]
                    main_db_path=self.db_path,
                )
                self._trash_repository = factory.build()
                repo = self._trash_repository
        return repo  # type: ignore[return-value]

    # ============================================================
    # 生命周期（由 EnhancedDatabaseManager.__init__ 显式调用）
    # ============================================================

    def _init_trash_database(self) -> None:
        """初始化垃圾桶数据库（建表 + FTS5 + PRAGMA）

        在 ``__init__`` 中按依赖顺序调用：必须在主库 _init_database 之后、_recover 之前。
        """
        # 触发懒加载以确保 repository 已创建
        self._ensure_trash_repository()
        self._trash_repository.init_schema()
        logger.info("垃圾桶数据库初始化流程结束（mixin 入口）")

    def _close_trash_pool(self) -> None:
        """关闭垃圾桶连接池（幂等）"""
        repo = getattr(self, "_trash_repository", None)
        if repo is not None:
            repo.close()
            self._trash_repository = None

    def _recover_pending_trash_ops(self) -> int:
        """启动恢复：扫描两库 pending_trash_ops，推进到稳定态"""
        repo = self._ensure_trash_repository()
        return repo.recover_pending_ops()

    # ============================================================
    # 兼容性：保留历史方法名，供外部显式调用
    # ============================================================

    def _init_trash_pool(self) -> None:
        """兼容旧接口：实际工作由 TrashServiceFactory 完成"""
        self._ensure_trash_repository()

    def _get_trash_connection(self):
        """兼容旧接口：返回垃圾桶连接（仅供诊断 / 测试）"""
        return self._ensure_trash_repository()._pool.connection

    @property
    def _trash_lock(self) -> threading.Lock:
        """兼容旧接口：返回垃圾桶连接锁"""
        return self._ensure_trash_repository()._pool.lock

    @property
    def _trash_fts5_available(self) -> bool:
        """兼容旧接口：FTS5 是否在当前 SQLite 构建中可用"""
        return self._ensure_trash_repository()._schema.fts5_available

    # ============================================================
    # 业务接口（委托给 TrashRepository）
    # ============================================================

    def move_to_trash(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """将日记移动到垃圾桶（2PC 软删除）"""
        repo = self._ensure_trash_repository()
        return repo.move_to_trash(self, diary_id)  # type: ignore[arg-type]

    def restore_from_trash(self, trash_id: int) -> Optional[Dict[str, Any]]:
        """从垃圾桶恢复日记（2PC）"""
        repo = self._ensure_trash_repository()
        return repo.restore_from_trash(self, trash_id)  # type: ignore[arg-type]

    def restore_from_trash_by_double_click(self, trash_id: int) -> Optional[Dict[str, Any]]:
        """双击恢复日记（别名方法，行为同 restore_from_trash）"""
        return self.restore_from_trash(trash_id)

    def get_all_trash_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有垃圾桶中的日记（按删除时间倒序）"""
        return self._ensure_trash_repository().get_all(limit)

    def get_trash_diary_by_id(self, trash_id: int) -> Optional[Dict[str, Any]]:
        """根据垃圾桶 ID 获取日记"""
        return self._ensure_trash_repository().get_by_id(trash_id)

    def search_trash_by_keyword(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """在垃圾桶中搜索日记（FTS5 优先 + LIKE 兜底）"""
        return self._ensure_trash_repository().search(keyword, limit)

    def get_trash_count(self) -> int:
        """获取垃圾桶中的日记数量"""
        return self._ensure_trash_repository().count()

    def permanently_delete_trash(self, trash_id: int) -> bool:
        """永久删除垃圾桶中的日记"""
        return self._ensure_trash_repository().permanently_delete(trash_id)

    def empty_trash(self) -> int:
        """清空整个垃圾桶"""
        return self._ensure_trash_repository().empty()

    def compute_trash_tokens(self, content: str) -> str:
        """对垃圾桶的日记内容算预分词串（FTS5 不可用时返回空）"""
        return self._ensure_trash_repository()._schema.compute_tokens(content)
