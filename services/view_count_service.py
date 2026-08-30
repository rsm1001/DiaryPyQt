"""
查看次数服务模块 - 负责处理日记查看次数的相关功能
"""

from typing import Dict, Any, Optional, List
import sqlite3
import logging

logger = logging.getLogger(__name__)


class ViewCountService:
    """查看次数服务类，负责处理日记查看次数的相关功能"""
    
    def __init__(self, db_manager):
        """
        初始化查看次数服务
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
    
    def increment_view_count(self, diary_id: int) -> Optional[int]:
        """
        增加日记查看次数（view_log / view_count / all_time_max 三者同事务）

        三件事压在一个事务里：
        1. INSERT INTO view_log                —— 动作流（近 N 天明细）
        2. UPDATE diaries SET view_count = +1  —— 单点累计（权威）
        3. UPDATE app_config SET all_time_max_daily_views  —— 跨日汇总

        任意一步失败整体回滚，三者必然同生同灭。
        旧实现分四个独立 _execute（各自起 _transaction），崩溃/断电会留下
        view_log 与 view_count 永久不一致。

        Returns:
            新的查看次数或 None
        """
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        today = datetime.now().strftime('%Y-%m-%d')

        # 用 _transaction 一次包住三步；崩溃时全部回滚
        try:
            with self.db_manager._transaction() as cursor:
                # 先确认日记存在，避免为已删除的日记留下孤儿 view_log
                cursor.execute("SELECT id FROM diaries WHERE id = ?", (diary_id,))
                if cursor.fetchone() is None:
                    logger.warning("查看失败，日记不存在: %s", diary_id)
                    return None
                # 1) 记录查看日志
                cursor.execute(
                    "INSERT INTO view_log (diary_id, viewed_at) VALUES (?, ?)",
                    (diary_id, now)
                )

                # 2) 增加查看次数；用 RETURNING 取新值（SQLite 3.35+）
                try:
                    cursor.execute(
                        "UPDATE diaries SET view_count = view_count + 1, "
                        "last_viewed_at = ? WHERE id = ? RETURNING view_count",
                        (now, diary_id)
                    )
                    row = cursor.fetchone()
                    new_count = row['view_count'] if row else None
                except sqlite3.Error:
                    # 旧 SQLite 引擎不支持 RETURNING，回退 SELECT
                    cursor.execute(
                        "UPDATE diaries SET view_count = view_count + 1, "
                        "last_viewed_at = ? WHERE id = ?",
                        (now, diary_id)
                    )
                    cursor.execute(
                        "SELECT view_count FROM diaries WHERE id = ?",
                        (diary_id,)
                    )
                    sel_row = cursor.fetchone()
                    new_count = sel_row['view_count'] if sel_row else None

                # 3) 计算今日当前查看数（基于本事务内已插入的 view_log）
                cursor.execute(
                    "SELECT COUNT(*) as count FROM view_log "
                    "WHERE diary_id = ? AND date(viewed_at) = ?",
                    (diary_id, today)
                )
                today_row = cursor.fetchone()
                today_count = today_row['count'] if today_row else 0

                # 4) 更新历史最佳单日查看数（仅在当日首次被刷新时写）
                cursor.execute(
                    "SELECT value FROM app_config WHERE key = 'all_time_max_daily_views'"
                )
                max_row = cursor.fetchone()
                current_max = max_row['value'] if max_row else 0

                if today_count > current_max:
                    cursor.execute(
                        "INSERT OR REPLACE INTO app_config (key, value, updated_at) "
                        "VALUES ('all_time_max_daily_views', ?, ?)",
                        (today_count, now)
                    )
                    logger.info(
                        f"更新历史最佳单日查看数: {current_max} -> {today_count}"
                    )

                if new_count is not None:
                    logger.debug(
                        f"增加查看次数，ID: {diary_id}, 新次数: {new_count}"
                    )
                return new_count
        except sqlite3.Error:
            # 事务已在 _transaction 内回滚；重新抛出让上层感知
            raise
    
    def decrease_view_count(self, diary_id: int, penalty: int = 1) -> bool:
        """
        减少日记查看次数
        
        Args:
            diary_id: 日记ID
            penalty: 减少的数量
        
        Returns:
            是否操作成功
        """
        rowcount = self.db_manager._execute(
            "UPDATE diaries SET view_count = MAX(0, view_count - ?) WHERE id = ?",
            (penalty, diary_id),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"减少查看次数，ID: {diary_id}, 减少: {penalty}")
            return True
        return False
    
    def reset_view_count(self, diary_id: int) -> bool:
        """
        重置日记查看次数为0
        
        Args:
            diary_id: 日记ID
        
        Returns:
            是否重置成功
        """
        rowcount = self.db_manager._execute(
            "UPDATE diaries SET view_count = 0 WHERE id = ?",
            (diary_id,),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"重置查看次数，ID: {diary_id}")
            return True
        return False
    
    def batch_increment_view_counts(self, diary_ids: List[int]) -> int:
        """
        批量增加多篇日记的查看次数
        
        Args:
            diary_ids: 日记ID列表
        
        Returns:
            成功更新的记录数
        """
        if not diary_ids:
            return 0
            
        placeholders = ','.join(['?' for _ in diary_ids])
        query = f"UPDATE diaries SET view_count = view_count + 1 WHERE id IN ({placeholders})"
        
        rowcount = self.db_manager._execute(
            query,
            tuple(diary_ids),
            fetch='rowcount'
        )
        
        logger.info(f"批量增加查看次数，影响记录数: {rowcount}")
        return rowcount
    
    def get_total_view_count(self) -> int:
        """
        获取所有日记的总查看次数
        
        Returns:
            总查看次数
        """
        result = self.db_manager._execute(
            "SELECT SUM(view_count) as total_views FROM diaries",
            fetch='one'
        )
        
        return result['total_views'] if result and result['total_views'] else 0
    
    def get_highest_view_count(self) -> Optional[Dict[str, Any]]:
        """
        获取查看次数最高的日记
        
        Returns:
            查看次数最高的日记或None
        """
        return self.db_manager._execute(
            "SELECT * FROM diaries ORDER BY view_count DESC LIMIT 1",
            fetch='one'
        )
    
    def get_lowest_view_count(self) -> Optional[Dict[str, Any]]:
        """
        获取查看次数最低的日记
        
        Returns:
            查看次数最低的日记或None
        """
        return self.db_manager._execute(
            "SELECT * FROM diaries ORDER BY view_count ASC LIMIT 1",
            fetch='one'
        )
    
    def get_average_view_count(self) -> float:
        """
        获取平均查看次数
        
        Returns:
            平均查看次数
        """
        result = self.db_manager._execute(
            "SELECT AVG(view_count) as avg_views FROM diaries",
            fetch='one'
        )
        
        return result['avg_views'] if result and result['avg_views'] else 0.0
    
    def get_diaries_by_view_range(self, min_views: int, max_views: int) -> List[Dict[str, Any]]:
        """
        获取指定查看次数范围内的日记
        
        Args:
            min_views: 最小查看次数
            max_views: 最大查看次数
        
        Returns:
            符合条件的日记列表
        """
        return self.db_manager._execute(
            "SELECT * FROM diaries WHERE view_count >= ? AND view_count <= ? ORDER BY view_count DESC",
            (min_views, max_views),
            fetch='all'
        ) or []
    
    def cleanup_old_view_logs(self) -> int:
        """
        清理昨日与今日之外的查看日志

        view_log 现已降级为"近 N 天明细"——权威计数由 diaries.view_count 承担。
        本函数仅保留 2 天滚动窗口（昨天 + 今天），超过 48 小时的明细可安全删除。
        建议由定时任务在每日凌晨 00:01 调用一次，与"翻日"对齐。

        Returns:
            删除的记录数
        """
        from datetime import datetime, timedelta

        # 计算昨天的日期
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        yesterday_start = yesterday + ' 00:00:00'

        # 删除昨天之前的所有日志（使用范围查询替代 date() 函数，命中索引）
        rowcount = self.db_manager._execute(
            "DELETE FROM view_log WHERE viewed_at < ?",
            (yesterday_start,),
            fetch='rowcount'
        )

        if rowcount > 0:
            logger.info(f"清理旧查看日志，删除 {rowcount} 条记录（保留昨天和今天的记录）")

        return rowcount or 0