"""
垃圾桶仓储（Repository）

组合各 sub-service，对外提供垃圾桶相关的统一业务接口（CRUD + 搜索 + 2PC + 容量管理）。

设计要点：
- 依赖倒置：所有 sub-service 通过构造器注入，便于单测 mock
- 主库协议（MainDbLike）：通过 duck-typing 注入主库能力，不依赖具体类型
- 2PC 协调：move / restore 走 TrashTwoPhaseCommitCoordinator 三阶段协议
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .capacity import TrashCapacityManager
from .connection import TrashConnectionPool
from .schema import TrashSchemaInitializer
from .search import TrashSearchService
from .two_phase_commit import MainDbLike, TrashTwoPhaseCommitCoordinator

logger = logging.getLogger(__name__)


class TrashRepository:
    """垃圾桶仓储：业务门面

    对外提供：
        - 初始化与生命周期（init / close）
        - 列表 / 计数 / 按 ID 查询
        - 搜索（FTS5 + LIKE 兜底）
        - 移动到垃圾桶（move_to_trash）
        - 从垃圾桶恢复（restore_from_trash）
        - 永久删除 / 清空
        - 启动恢复（recover_pending_ops）
    """

    def __init__(
        self,
        connection_pool: TrashConnectionPool,
        schema: TrashSchemaInitializer,
        search_service: TrashSearchService,
        capacity_manager: TrashCapacityManager,
        two_phase_commit: TrashTwoPhaseCommitCoordinator,
    ):
        self._pool = connection_pool
        self._schema = schema
        self._search = search_service
        self._capacity = capacity_manager
        self._two_pc = two_phase_commit

    # ------------------------------------------------------------------
    # 工厂辅助
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        main_db: MainDbLike,
        main_db_path: str,
    ) -> "TrashRepository":
        """标准工厂方法：装配全部 sub-service

        Args:
            main_db: 主库实例（duck-typed MainDbLike）
            main_db_path: 主库 db_path（用于定位垃圾桶 DB 文件）

        Returns:
            配置完成的 TrashRepository 实例
        """
        from .factory import TrashServiceFactory
        return TrashServiceFactory(main_db, main_db_path).build()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> str:
        """垃圾桶数据库文件路径（与连接池实际打开的文件同源）"""
        return self._pool.db_path

    def pending_op_counts(self) -> Dict[str, int]:
        """两库 pending_trash_ops 数量（供健康检查等外部只读使用）"""
        store = self._two_pc.pending_store
        return {'main': len(store.read_main()), 'trash': len(store.read_trash())}

    def init_schema(self) -> None:
        """初始化垃圾桶数据库 schema（建表 + FTS5 + PRAGMA）"""
        self._schema.initialize()

    def close(self) -> None:
        """关闭垃圾桶连接池（幂等）"""
        self._pool.close()

    def recover_pending_ops(self) -> int:
        """启动恢复：扫描两库 pending_trash_ops，推进到稳定态"""
        return self._two_pc.recover_pending_ops()

    # ------------------------------------------------------------------
    # 列表 / 计数 / 按 ID
    # ------------------------------------------------------------------

    def get_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有垃圾桶中的日记（按删除时间倒序）"""
        query = """
            SELECT td.*, GROUP_CONCAT(tt.name, ', ') as tag_names
            FROM trash_diaries td
            LEFT JOIN trash_tags tt ON td.id = tt.trash_diary_id
            GROUP BY td.id
            ORDER BY td.deleted_at DESC
        """
        if limit is not None:
            query += " LIMIT ?"
            return self._pool.execute(query, (limit,), fetch='all') or []
        return self._pool.execute(query, fetch='all') or []

    def get_by_id(self, trash_id: int) -> Optional[Dict[str, Any]]:
        """根据垃圾桶 ID 获取日记"""
        return self._pool.execute(
            "SELECT * FROM trash_diaries WHERE id = ?",
            (trash_id,),
            fetch='one',
        )

    def count(self) -> int:
        """获取垃圾桶中的日记数量"""
        result = self._pool.execute(
            "SELECT COUNT(*) as count FROM trash_diaries",
            fetch='one',
        )
        return result['count'] if result else 0

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------

    def search(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """在垃圾桶中搜索日记

        关键词为空 / 纯空白时回退到 get_all(limit)。
        """
        if not keyword or not keyword.strip():
            return self.get_all(limit)
        return self._search.search(keyword, limit)

    # ------------------------------------------------------------------
    # 移动 / 恢复
    # ------------------------------------------------------------------

    def move_to_trash(
        self,
        main_db: MainDbLike,
        diary_id: int,
        enforce_capacity: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """将日记移动到垃圾桶（2PC 软删除）

        Args:
            main_db: 主库实例（需实现 MainDbLike 协议）
            diary_id: 原日记 ID
            enforce_capacity: 是否触发容量淘汰

        Returns:
            移动结果信息（包含 trash_id, original_id, deleted_at, op_id）
            或 None（如果日记不存在）
        """
        diary = main_db.get_diary_by_id(diary_id)
        if not diary:
            logger.warning("移动到垃圾桶失败，日记不存在: %s", diary_id)
            return None

        tags = main_db.get_tags_by_diary_id(diary_id) \
            if hasattr(main_db, 'get_tags_by_diary_id') else []

        tokens = self._schema.compute_tokens(diary['content'])
        payload = self._build_move_payload(diary, tags, tokens)
        op_id = self._two_pc.new_op_id()

        with main_db._db_lock:
            try:
                self._two_pc.precommit(
                    op_id, 'move', diary_id, None, payload,
                )
                self._two_pc.apply_to_main(
                    op_id, 'move', diary_id, None, payload,
                )
                self._two_pc.commit_to_trash(
                    op_id, 'move', diary_id, None, payload,
                )
            except Exception as exc:
                logger.error("2PC move_to_trash 失败: %s", exc)
                self._two_pc.cleanup_pending_op(op_id)
                raise

        if enforce_capacity:
            self._enforce_capacity()

        new_trash = self._pool.execute(
            "SELECT id FROM trash_diaries WHERE original_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (diary_id,),
            fetch='one',
        )
        new_trash_id = new_trash['id'] if new_trash else None
        deleted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("日记 %s 已移动到垃圾桶，op_id: %s", diary_id, op_id)
        return {
            'trash_id': new_trash_id,
            'original_id': diary_id,
            'deleted_at': deleted_at,
            'op_id': op_id,
        }

    def restore_from_trash(
        self,
        main_db: MainDbLike,
        trash_id: int,
    ) -> Optional[Dict[str, Any]]:
        """从垃圾桶恢复日记（2PC）

        Returns:
            恢复出的日记字典或 None
        """
        trash_diary = self.get_by_id(trash_id)
        if not trash_diary:
            logger.warning("恢复失败，垃圾桶日记不存在: %s", trash_id)
            return None

        trash_tags = self._pool.execute(
            "SELECT * FROM trash_tags WHERE trash_diary_id = ?",
            (trash_id,),
            fetch='all',
        ) or []

        tokens = main_db.compute_tokens(trash_diary['content'])
        payload = self._build_restore_payload(trash_diary, trash_tags, tokens)
        op_id = self._two_pc.new_op_id()

        with main_db._db_lock:
            try:
                self._two_pc.precommit(
                    op_id, 'restore', trash_diary.get('original_id'),
                    trash_id, payload,
                )
                self._two_pc.apply_to_main(
                    op_id, 'restore', trash_diary.get('original_id'),
                    trash_id, payload,
                )
                self._two_pc.commit_to_trash(
                    op_id, 'restore', trash_diary.get('original_id'),
                    trash_id, payload,
                )
            except Exception as exc:
                logger.error("2PC restore_from_trash 失败: %s", exc)
                self._two_pc.cleanup_pending_op(op_id)
                raise

        new_diary = main_db._execute(
            "SELECT id FROM diaries WHERE date = ? AND content = ? "
            "ORDER BY id DESC LIMIT 1",
            (trash_diary['date'], trash_diary['content']),
            fetch='one',
        )
        if new_diary:
            logger.info(
                "日记已从垃圾桶恢复，op_id: %s, 新ID: %s",
                op_id, new_diary['id'],
            )
            return main_db.get_diary_by_id(new_diary['id'])
        return None

    # ------------------------------------------------------------------
    # 永久删除 / 清空
    # ------------------------------------------------------------------

    def permanently_delete(self, trash_id: int) -> bool:
        """永久删除垃圾桶中的日记"""
        rowcount = self._pool.execute(
            "DELETE FROM trash_diaries WHERE id = ?",
            (trash_id,),
            fetch='rowcount',
        )
        if rowcount > 0:
            logger.info("永久删除垃圾桶日记: %s", trash_id)
            return True
        return False

    def empty(self) -> int:
        """清空整个垃圾桶"""
        count = self.count()
        self._pool.execute("DELETE FROM trash_diaries", fetch='rowcount')
        logger.info("垃圾桶已清空，共删除 %d 篇日记", count)
        return count

    # ------------------------------------------------------------------
    # 容量管理
    # ------------------------------------------------------------------

    def _enforce_capacity(self) -> None:
        """强制执行垃圾桶容量限制（LRU 淘汰）"""
        from models.config.db_config import get_db_config
        max_size = get_db_config().get_trash_cache_size()
        self._capacity.enforce(max_size)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _build_move_payload(
        diary: Dict[str, Any],
        tags: List[Dict[str, Any]],
        tokens: str,
    ) -> Dict[str, Any]:
        return {
            'date': diary['date'],
            'content': diary['content'],
            'view_count': diary.get('view_count', 0),
            'last_viewed_at': diary.get('last_viewed_at'),
            'updated_at': diary.get('updated_at'),
            'tokens': tokens,
            'tags': [
                {'name': t['name'], 'original_tag_id': t['id']}
                for t in tags
            ],
        }

    @staticmethod
    def _build_restore_payload(
        trash_diary: Dict[str, Any],
        trash_tags: List[Dict[str, Any]],
        tokens: str,
    ) -> Dict[str, Any]:
        return {
            'date': trash_diary['date'],
            'content': trash_diary['content'],
            'view_count': trash_diary.get('view_count', 0),
            'last_viewed_at': trash_diary.get('last_viewed_at'),
            'updated_at': trash_diary.get('updated_at'),
            'tokens': tokens,
            'tags': [
                {
                    'name': t['name'],
                    'original_tag_id': t.get('original_tag_id'),
                }
                for t in trash_tags
            ],
        }
