"""
数据迁移和备份管理器
用于处理数据库的导入导出、备份恢复和完整性验证功能
"""

import json
import csv
import os
import sqlite3
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class MigrationBackupManager:
    """数据迁移和备份管理器"""
    
    def __init__(self, db_manager):
        """
        初始化迁移备份管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager

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
            with self.db_manager._transaction() as cursor:
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
                
                with self.db_manager._transaction() as cursor:
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
            diaries = self.db_manager.get_all_diaries()
            
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
            diaries = self.db_manager.get_all_diaries()
            
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
            source_conn = self.db_manager._get_connection()
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
            self.db_manager.close()
            
            # 复制备份文件到目标位置
            shutil.copy2(backup_path, self.db_manager.db_path)
            
            # 重新初始化连接
            self.db_manager._init_database()
            
            logger.info(f"数据库恢复成功: {backup_path} -> {self.db_manager.db_path}")
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
            conn = self.db_manager._get_connection()
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