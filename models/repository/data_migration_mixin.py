"""
数据迁移模块 - 从DatabaseManager中解耦出来的数据迁移功能
"""
import json
import os
import logging
from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataMigrationMixin:
    """数据迁移混入类，提供数据导入导出功能"""
    
    @abstractmethod
    def _execute(self, query: str, params: tuple = (), fetch: Optional[str] = None) -> Optional[Any]:
        """执行SQL查询的抽象方法"""
        pass
    
    @abstractmethod
    def get_all_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有日记的抽象方法"""
        pass
    
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
                        cursor.execute(
                            """
                            INSERT OR IGNORE INTO diaries (id, date, content, view_count) 
                            VALUES (?, ?, ?, ?)
                            """,
                            (diary.get('id'), diary.get('date'), 
                             diary.get('content'), diary.get('view_count', 0))
                        )
                        if cursor.rowcount > 0:
                            count += 1
                    except Exception as e:
                        logger.warning(f"迁移日记失败: {e}")

            logger.info(f"从JSON迁移了 {count} 篇日记")
            return count

        except Exception as e:
            logger.error(f"迁移数据时出错: {e}")
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

    def migrate_from_csv(self, csv_file_path: str) -> int:
        """
        从CSV文件迁移数据到SQLite
        
        Args:
            csv_file_path: CSV文件路径
        
        Returns:
            迁移的日记数量
        """
        import csv
        
        if not os.path.exists(csv_file_path):
            logger.warning(f"CSV文件不存在: {csv_file_path}")
            return 0

        try:
            count = 0
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                with self._transaction() as cursor:
                    for row in reader:
                        try:
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO diaries (date, content, view_count) 
                                VALUES (?, ?, ?)
                                """,
                                (
                                    row.get('date', ''),
                                    row.get('content', ''),
                                    int(row.get('view_count', 0) or 0)
                                )
                            )
                            if cursor.rowcount > 0:
                                count += 1
                        except Exception as e:
                            logger.warning(f"迁移CSV日记失败: {e}")

            logger.info(f"从CSV迁移了 {count} 篇日记")
            return count

        except Exception as e:
            logger.error(f"迁移CSV数据时出错: {e}")
            return 0

    def export_to_csv(self, csv_file_path: str) -> bool:
        """
        导出数据到CSV文件
        
        Args:
            csv_file_path: CSV文件路径
        
        Returns:
            是否导出成功
        """
        import csv
        
        try:
            diaries = self.get_all_diaries()

            # 确保目录存在
            os.makedirs(os.path.dirname(csv_file_path) or '.', exist_ok=True)

            with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
                if diaries:
                    writer = csv.DictWriter(f, fieldnames=diaries[0].keys())
                    writer.writeheader()
                    writer.writerows(diaries)

            logger.info(f"导出 {len(diaries)} 篇日记到 {csv_file_path}")
            return True

        except Exception as e:
            logger.error(f"导出CSV数据时出错: {e}")
            return False