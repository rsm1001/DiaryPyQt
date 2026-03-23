"""
增强版数据库管理器，包含迁移功能
"""
import sqlite3
import os
import threading
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager
import json
import csv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedDatabaseManager:
    """增强版SQLite数据库管理器 - 包含完整的迁移和备份功能"""
    
    def __init__(self, db_path: str = "DiaryServer/diary_data/diary.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.RLock()
        
        # 确保目录存在
        self._ensure_directory()
        
        # 初始化数据库
        self._init_database()
        
        logger.info(f"EnhancedDatabaseManager初始化完成，数据库路径: {os.path.abspath(self.db_path)}")
    
    def _ensure_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None  # 自动提交模式
            )
            # 启用外键支持
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            # 设置行工厂
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_database(self):
        """初始化数据库表和索引"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建日记表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS diaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    view_count INTEGER DEFAULT 0
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_date ON diaries(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_view_count ON diaries(view_count)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_content ON diaries(content)')
            
            # 启用WAL模式以提高并发性能
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA synchronous=NORMAL')
            cursor.execute('PRAGMA cache_size=10000')
            cursor.execute('PRAGMA temp_store=memory')
            cursor.execute('PRAGMA mmap_size=30000000000')
            
            conn.commit()
            logger.info("数据库初始化完成")
    
    @contextmanager
    def _transaction(self):
        """事务上下文管理器"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN")
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"事务回滚: {e}")
            raise
    
    def _execute(
        self, 
        query: str, 
        params: Tuple = (), 
        fetch: Optional[str] = None
    ) -> Optional[Any]:
        """
        执行SQL查询
        
        Args:
            query: SQL语句
            params: 参数元组
            fetch: 获取类型 ('one', 'all', 'rowcount', None)
        
        Returns:
            查询结果
        """
        with self._lock:
            try:
                with self._transaction() as cursor:
                    cursor.execute(query, params)
                    
                    if fetch == 'one':
                        row = cursor.fetchone()
                        return dict(row) if row else None
                    elif fetch == 'all':
                        rows = cursor.fetchall()
                        return [dict(row) for row in rows]
                    elif fetch == 'rowcount':
                        return cursor.rowcount
                    else:
                        return cursor.lastrowid
                        
            except sqlite3.Error as e:
                logger.error(f"SQL执行错误: {e}, 查询: {query}, 参数: {params}")
                raise
    
    # ========================================================================
    # 日记CRUD操作
    # ========================================================================
    
    def add_diary(self, content: str) -> Optional[Dict[str, Any]]:
        """
        添加新日记
        
        Args:
            content: 日记内容
        
        Returns:
            新创建的日记字典
        """
        if not content or not content.strip():
            logger.warning("尝试添加空日记内容")
            return None
        
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        diary_id = self._execute(
            "INSERT INTO diaries (date, content, view_count) VALUES (?, ?, ?)",
            (date, content.strip(), 0)
        )
        
        if diary_id:
            logger.info(f"添加日记成功，ID: {diary_id}")
            return {
                'id': diary_id,
                'date': date,
                'content': content.strip(),
                'view_count': 0
            }
        return None
    
    def get_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取日记
        
        Args:
            diary_id: 日记ID
        
        Returns:
            日记字典或None
        """
        return self._execute(
            "SELECT * FROM diaries WHERE id = ?",
            (diary_id,),
            fetch='one'
        )
    
    def update_diary(self, diary_id: int, new_content: str) -> bool:
        """
        更新日记内容
        
        Args:
            diary_id: 日记ID
            new_content: 新内容
        
        Returns:
            是否更新成功
        """
        if not new_content or not new_content.strip():
            logger.warning("尝试更新为空内容")
            return False
        
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rowcount = self._execute(
            "UPDATE diaries SET content = ?, date = ? WHERE id = ?",
            (new_content.strip(), date, diary_id),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"更新日记成功，ID: {diary_id}")
            return True
        logger.warning(f"更新日记失败，ID: {diary_id} 不存在")
        return False
    
    def delete_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID删除日记
        
        Args:
            diary_id: 日记ID
        
        Returns:
            被删除的日记字典或None
        """
        # 先获取日记信息
        diary = self.get_diary_by_id(diary_id)
        if not diary:
            logger.warning(f"删除失败，日记不存在: {diary_id}")
            return None
        
        # 删除日记
        self._execute(
            "DELETE FROM diaries WHERE id = ?",
            (diary_id,)
        )
        
        logger.info(f"删除日记成功，ID: {diary_id}")
        return diary
    
    # ========================================================================
    # 查看次数操作
    # ========================================================================
    
    def increment_view_count(self, diary_id: int) -> Optional[int]:
        """
        增加日记查看次数
        
        Args:
            diary_id: 日记ID
        
        Returns:
            新的查看次数或None
        """
        # 使用RETURNING子句获取更新后的值（SQLite 3.35.0+）
        try:
            result = self._execute(
                "UPDATE diaries SET view_count = view_count + 1 WHERE id = ? RETURNING view_count",
                (diary_id,),
                fetch='one'
            )
            if result:
                logger.debug(f"增加查看次数，ID: {diary_id}, 新次数: {result['view_count']}")
                return result['view_count']
        except sqlite3.Error:
            # 如果RETURNING不支持，使用传统方式
            self._execute(
                "UPDATE diaries SET view_count = view_count + 1 WHERE id = ?",
                (diary_id,)
            )
            result = self._execute(
                "SELECT view_count FROM diaries WHERE id = ?",
                (diary_id,),
                fetch='one'
            )
            return result['view_count'] if result else None
        return None
    
    def decrease_view_count(self, diary_id: int, penalty: int = 1) -> bool:
        """
        减少日记查看次数
        
        Args:
            diary_id: 日记ID
            penalty: 减少的数量
        
        Returns:
            是否操作成功
        """
        rowcount = self._execute(
            "UPDATE diaries SET view_count = MAX(0, view_count - ?) WHERE id = ?",
            (penalty, diary_id),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"减少查看次数，ID: {diary_id}, 减少: {penalty}")
            return True
        return False
    
    # ========================================================================
    # 查询操作
    # ========================================================================
    
    def get_all_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有日记（按日期倒序）
        
        Args:
            limit: 限制数量
        
        Returns:
            日记列表
        """
        query = "SELECT * FROM diaries ORDER BY date DESC"
        params = ()
        
        if limit:
            query += " LIMIT ?"
            params = (limit,)
        
        return self._execute(query, params, fetch='all') or []
    
    def get_most_viewed_diaries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取查看次数最多的日记
        
        Args:
            limit: 限制数量
        
        Returns:
            日记列表
        """
        return self._execute(
            "SELECT * FROM diaries ORDER BY view_count DESC, date ASC LIMIT ?",
            (limit,),
            fetch='all'
        ) or []
    
    def get_least_viewed_diaries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取查看次数最少的日记
        
        Args:
            limit: 限制数量
        
        Returns:
            日记列表
        """
        return self._execute(
            "SELECT * FROM diaries ORDER BY view_count ASC, date DESC LIMIT ?",
            (limit,),
            fetch='all'
        ) or []
    
    def get_oldest_in_most_viewed(self, limit: int = 20) -> Optional[Dict[str, Any]]:
        """
        获取查看次数最多的日记中最久远的
        
        Args:
            limit: 查看次数最多的前N篇
        
        Returns:
            日记字典或None
        """
        return self._execute(
            """
            SELECT * FROM diaries 
            WHERE id IN (
                SELECT id FROM diaries 
                ORDER BY view_count DESC, date ASC 
                LIMIT ?
            )
            ORDER BY date ASC 
            LIMIT 1
            """,
            (limit,),
            fetch='one'
        )
    
    def get_random_diary(self, limit: int = None) -> Optional[Dict[str, Any]]:
        """
        随机获取一篇日记（基于权重概率选择，使用次数越少，被选中概率越大）
        使用改进的归一化方法，对全部日记进行计算（除非指定limit）
        
        Args:
            limit: 最多考虑的日记数量，None表示使用全部日记
        
        Returns:
            日记字典或None
        """
        import random
        import math
        from datetime import datetime
        
        # 获取日记数据
        if limit is None:
            # 获取全部日记，按日期升序排列
            diaries = self._execute(
                "SELECT * FROM diaries ORDER BY date ASC",
                fetch='all'
            )
        else:
            # 仅获取指定数量的日记
            diaries = self._execute(
                "SELECT * FROM diaries ORDER BY date ASC LIMIT ?",
                (limit,),
                fetch='all'
            )
        
        if not diaries:
            return None
        
        # 计算每个日记的权重
        weighted_diaries = []
        weights = []
        
        # 计算当前日期，用于计算时间权重
        now = datetime.now()
        
        # 计算各项的原始权重，但不立即归一化
        diary_details = []  # 存储日记和其原始权重，便于分析
        for diary in diaries:
            # 解析日期
            date = datetime.strptime(diary['date'], "%Y-%m-%d %H:%M:%S")
            
            # 计算距离今天的天数
            days_ago = (now - date).days
            
            # 原始时间权重：距离现在的天数（越久远，值越大）
            # 使用对数函数平滑时间差异
            time_weight_raw = math.log(days_ago + 1)  # 加1避免log(0)
            
            # 原始次数权重：使用次数越少，权重越大
            use_count = diary['view_count']
            # 使用更强的倒数函数，提高敏感度
            count_weight_raw = 1.0 / ((use_count + 1) ** 1.5)  # 使用1.5次幂，提高敏感度
            
            diary_details.append({
                'diary': diary,
                'time_weight_raw': time_weight_raw,
                'count_weight_raw': count_weight_raw,
                'days_ago': days_ago,
                'use_count': use_count
            })
        
        # 使用分位数归一化而不是最小-最大归一化
        # 按时间权重排序，分配分位数
        sorted_by_time = sorted(diary_details, key=lambda x: x['time_weight_raw'])
        n = len(sorted_by_time)
        for i, item in enumerate(sorted_by_time):
            # 分位数值在[0,1]区间
            item['time_weight_norm'] = i / (n - 1) if n > 1 else 0.5
        
        # 按次数权重排序，分配分位数
        # 注意：次数越少权重越高，所以我们要让使用次数少的获得更高的分位数
        sorted_by_count = sorted(diary_details, key=lambda x: x['use_count'])  # 按使用次数升序排列
        for i, item in enumerate(sorted_by_count):
            # 次数少的获得更高的分位数，使用 (n-1-i)/(n-1) 实现倒序
            item['count_weight_norm'] = (n - 1 - i) / (n - 1) if n > 1 else 0.5
        
        # 计算最终权重并准备选择
        for item in diary_details:
            # 权重加权求和（给次数权重更高的系数，突出使用次数少的重要性）
            alpha = 0.2  # 时间权重系数
            beta = 2.0   # 次数权重系数 (beta > alpha，突出次数权重重要性)
            
            final_weight = alpha * item['time_weight_norm'] + beta * item['count_weight_norm']
            weighted_diaries.append((item['diary'], final_weight))
            weights.append(final_weight)
        
        # 按权重进行加权随机选择
        if weights and sum(weights) > 0:
            # 根据权重随机选择一个
            selected_diary = random.choices([d[0] for d in weighted_diaries], weights=weights, k=1)[0]
            # 记录详细的权重分析
            weight_analysis = {d[0]['id']: round(d[1], 4) for d in weighted_diaries}
            logger.info(f"加权随机选择日记，ID: {selected_diary['id']}, 权重: {weight_analysis}")
            return selected_diary
        else:
            # 如果权重有问题，退回到随机选择
            selected = random.choice(diaries)
            logger.info(f"退回到随机选择日记，ID: {selected['id']}")
            return selected
    
    def search_by_keyword(self, keyword: str, limit: int = 18) -> List[Dict[str, Any]]:
        """
        根据关键词搜索日记
        
        Args:
            keyword: 搜索关键词
            limit: 限制数量
        
        Returns:
            日记列表
        """
        if not keyword or not keyword.strip():
            return []
        
        return self._execute(
            """
            SELECT * FROM diaries 
            WHERE content LIKE ? 
            ORDER BY view_count DESC, date DESC 
            LIMIT ?
            """,
            (f"%{keyword.strip().lower()}%", limit),
            fetch='all'
        ) or []
    
    # ========================================================================
    # 统计操作
    # ========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        # 基础统计
        stats = self._execute(
            """
            SELECT 
                COUNT(*) as total,
                COALESCE(SUM(view_count), 0) as total_views,
                COALESCE(AVG(view_count), 0) as avg_views,
                MAX(view_count) as max_views,
                MIN(view_count) as min_views
            FROM diaries
            """,
            fetch='one'
        )
        
        if not stats or stats['total'] == 0:
            return {
                'total': 0,
                'total_views': 0,
                'avg_views': 0,
                'most_viewed': None,
                'least_viewed': None
            }
        
        # 获取查看次数最多和最少的日记
        most_viewed = self._execute(
            "SELECT * FROM diaries WHERE view_count = ? ORDER BY date ASC LIMIT 1",
            (stats['max_views'],),
            fetch='one'
        )
        
        least_viewed = self._execute(
            "SELECT * FROM diaries WHERE view_count = ? ORDER BY date ASC LIMIT 1",
            (stats['min_views'],),
            fetch='one'
        )
        
        return {
            'total': stats['total'],
            'total_views': stats['total_views'],
            'avg_views': round(stats['avg_views'], 2),
            'most_viewed': most_viewed,
            'least_viewed': least_viewed
        }
    
    # ========================================================================
    # 数据迁移和备份功能
    # ========================================================================
    
    def migrate_from_json(self, json_file_path: str) -> int:
        """
        从JSON文件迁移数据到SQLite
        
        Args:
            json_file_path: JSON文件路径
        
        Returns:
            迁移的日记数量
        """
        if not os.path.exists(json_file_path):
            logger.warning(f"JSON文件不存在: {json_file_path}")
            return 0
        
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            if not json_data:
                return 0
            
            count = 0
            with self._transaction() as cursor:
                for diary in json_data:
                    try:
                        # 检查是否已存在相同ID的日记
                        cursor.execute("SELECT id FROM diaries WHERE id = ?", (diary.get('id'),))
                        existing = cursor.fetchone()
                        
                        if not existing:
                            # 插入新日记
                            cursor.execute(
                                """
                                INSERT INTO diaries (id, date, content, view_count) 
                                VALUES (?, ?, ?, ?)
                                """,
                                (diary.get('id'), diary.get('date'), 
                                 diary.get('content'), diary.get('view_count', 0))
                            )
                            if cursor.rowcount > 0:
                                count += 1
                        else:
                            # 如果存在，则更新
                            cursor.execute(
                                """
                                UPDATE diaries 
                                SET date = ?, content = ?, view_count = ? 
                                WHERE id = ?
                                """,
                                (diary.get('date'), diary.get('content'), 
                                 diary.get('view_count', 0), diary.get('id'))
                            )
                            if cursor.rowcount > 0:
                                count += 1
                    except sqlite3.Error as e:
                        logger.warning(f"迁移日记失败: {e}, 日记ID: {diary.get('id')}")
            
            logger.info(f"从JSON迁移了 {count} 篇日记")
            return count
            
        except Exception as e:
            logger.error(f"迁移数据时出错: {e}")
            return 0

    def migrate_from_csv(self, csv_file_path: str) -> int:
        """
        从CSV文件迁移数据到SQLite
        
        Args:
            csv_file_path: CSV文件路径
        
        Returns:
            迁移的日记数量
        """
        if not os.path.exists(csv_file_path):
            logger.warning(f"CSV文件不存在: {csv_file_path}")
            return 0
        
        try:
            count = 0
            with open(csv_file_path, 'r', encoding='utf-8', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                
                with self._transaction() as cursor:
                    for row in reader:
                        try:
                            # 检查是否已存在相同ID的日记
                            diary_id = int(row.get('id', 0)) if row.get('id', '').isdigit() else 0
                            
                            if diary_id > 0:
                                cursor.execute("SELECT id FROM diaries WHERE id = ?", (diary_id,))
                                existing = cursor.fetchone()
                                
                                if not existing:
                                    # 插入新日记
                                    cursor.execute(
                                        """
                                        INSERT INTO diaries (id, date, content, view_count) 
                                        VALUES (?, ?, ?, ?)
                                        """,
                                        (diary_id, 
                                         row.get('date', datetime.now().strftime("%Y-%m-%d %H:%M:%S")), 
                                         row.get('content', ''), 
                                         int(row.get('view_count', 0)))
                                    )
                                    if cursor.rowcount > 0:
                                        count += 1
                        except Exception as e:
                            logger.warning(f"迁移CSV行失败: {e}, 行数据: {row}")
            
            logger.info(f"从CSV迁移了 {count} 篇日记")
            return count
            
        except Exception as e:
            logger.error(f"迁移CSV数据时出错: {e}")
            return 0
    
    def export_to_json(self, json_file_path: str) -> bool:
        """
        导出数据到JSON文件
        
        Args:
            json_file_path: JSON文件路径
        
        Returns:
            是否导出成功
        """
        try:
            diaries = self.get_all_diaries()
            
            # 确保目录存在
            os.makedirs(os.path.dirname(json_file_path) or '.', exist_ok=True)
            
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(diaries, f, ensure_ascii=False, indent=2)
            
            logger.info(f"导出 {len(diaries)} 篇日记到 {json_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出数据时出错: {e}")
            return False
    
    def export_to_csv(self, csv_file_path: str) -> bool:
        """
        导出数据到CSV文件
        
        Args:
            csv_file_path: CSV文件路径
        
        Returns:
            是否导出成功
        """
        try:
            diaries = self.get_all_diaries()
            
            # 确保目录存在
            os.makedirs(os.path.dirname(csv_file_path) or '.', exist_ok=True)
            
            with open(csv_file_path, 'w', encoding='utf-8', newline='') as csvfile:
                fieldnames = ['id', 'date', 'content', 'view_count']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for diary in diaries:
                    writer.writerow(diary)
            
            logger.info(f"导出 {len(diaries)} 篇日记到 {csv_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出CSV数据时出错: {e}")
            return False

    def backup_database(self, backup_path: str) -> bool:
        """
        备份整个数据库
        
        Args:
            backup_path: 备份文件路径
        
        Returns:
            是否备份成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(backup_path) or '.', exist_ok=True)
            
            # 使用SQLite的备份API
            source_conn = self._get_connection()
            backup_conn = sqlite3.connect(backup_path)
            
            source_conn.backup(backup_conn)
            backup_conn.close()
            
            logger.info(f"数据库备份成功: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            return False

    def restore_database(self, backup_path: str) -> bool:
        """
        从备份恢复数据库
        
        Args:
            backup_path: 备份文件路径
        
        Returns:
            是否恢复成功
        """
        if not os.path.exists(backup_path):
            logger.error(f"备份文件不存在: {backup_path}")
            return False
        
        try:
            # 关闭当前连接
            self.close()
            
            # 复制备份文件到目标位置
            import shutil
            shutil.copy2(backup_path, self.db_path)
            
            # 重新初始化连接
            self._local.connection = None
            self._init_database()
            
            logger.info(f"数据库恢复成功: {backup_path} -> {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"数据库恢复失败: {e}")
            return False

    def validate_database_integrity(self) -> bool:
        """
        验证数据库完整性
        
        Returns:
            数据库是否完整有效
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 执行SQLite内置的完整性检查
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            
            is_valid = result[0].lower() == 'ok'
            logger.info(f"数据库完整性检查: {'通过' if is_valid else '失败'}")
            
            return is_valid
        except Exception as e:
            logger.error(f"数据库完整性检查出错: {e}")
            return False

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
            logger.info("数据库连接已关闭")


# 单例模式
_enhanced_db_manager = None


def get_enhanced_db_manager(db_path: str = "DiaryServer/diary_data/diary.db") -> EnhancedDatabaseManager:
    """获取增强版数据库管理器单例"""
    global _enhanced_db_manager
    if _enhanced_db_manager is None:
        _enhanced_db_manager = EnhancedDatabaseManager(db_path)
    return _enhanced_db_manager