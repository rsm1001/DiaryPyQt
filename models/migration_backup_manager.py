"""数据导入、导出、备份、恢复与完整性检查。"""
import csv
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


class MigrationBackupManager:
    """统一处理数据迁移和数据库快照。"""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _trash_db_path(self) -> str:
        # 路径以仓储实际打开的垃圾桶文件为准，避免命名规则变更时备份/校验错文件
        return self.db_manager._ensure_trash_repository().db_path

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalise_tags(value: Any) -> Optional[List[str]]:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = [item.strip() for item in value.split(',')]
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            name = item.get('name') if isinstance(item, dict) else item
            if name and str(name).strip() and str(name).strip() not in result:
                result.append(str(name).strip())
        return result

    def _normalise_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        content = str(record.get('content') or '').strip()
        if not content:
            return None
        date = str(record.get('date') or self._now()).strip()
        return {
            'id': self._safe_int(record.get('id'), 0) or None,
            'date': date,
            'content': content,
            'view_count': self._safe_int(record.get('view_count'), 0),
            'last_viewed_at': record.get('last_viewed_at'),
            'updated_at': record.get('updated_at') or date,
            'tags': self._normalise_tags(record.get('tags', record.get('tag_names'))),
        }

    def _apply_tags(self, cursor: sqlite3.Cursor, diary_id: int, tags: List[str]) -> None:
        cursor.execute("DELETE FROM diary_tags WHERE diary_id = ?", (diary_id,))
        for name in tags:
            cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
            row = cursor.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            if row:
                cursor.execute(
                    "INSERT OR IGNORE INTO diary_tags (diary_id, tag_id) VALUES (?, ?)",
                    (diary_id, row[0]),
                )

    def _insert_record_if_new(self, cursor: sqlite3.Cursor, raw_record: Dict[str, Any]) -> bool:
        """仅当记录携带有效且不存在的 id 时插入。

        导入定位为"补齐缺失条目"的合并操作：
        - id 已存在：跳过，绝不覆盖当前内容 / 查看数 / 标签
        - id 缺失或非法：跳过，避免重复导入同一文件时产生重复行
        """
        record = self._normalise_record(raw_record)
        if record is None:
            return False
        diary_id = record['id']
        if not diary_id:
            logger.warning("跳过缺失有效id的导入记录: date=%s", record['date'])
            return False
        if cursor.execute(
            "SELECT id FROM diaries WHERE id = ?", (diary_id,)
        ).fetchone():
            return False
        tokens = self.db_manager.compute_tokens(record['content'])
        cursor.execute(
            "INSERT INTO diaries (id, date, content, view_count, last_viewed_at, tokens, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                diary_id, record['date'], record['content'], record['view_count'],
                record['last_viewed_at'], tokens, record['updated_at'],
            ),
        )
        if record['tags'] is not None:
            self._apply_tags(cursor, diary_id, record['tags'])
        return True

    def _migrate_records(self, records: Iterable[Dict[str, Any]]) -> int:
        count = 0
        try:
            with self.db_manager._transaction() as cursor:
                for raw_record in records:
                    try:
                        if self._insert_record_if_new(cursor, raw_record):
                            count += 1
                    except (sqlite3.Error, TypeError, ValueError) as exc:
                        logger.warning("跳过无效导入记录: %s", exc)
            return count
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            logger.error("导入失败: %s", exc, exc_info=True)
            return 0

    def migrate_from_json(self, json_file_path: str) -> int:
        if not os.path.isfile(json_file_path):
            logger.warning("JSON文件不存在: %s", json_file_path)
            return 0
        try:
            with open(json_file_path, 'r', encoding='utf-8') as source:
                records = json.load(source)
            if not isinstance(records, list):
                return 0
            count = self._migrate_records(records)
            logger.info("JSON导入完成: count=%d", count)
            return count
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("读取JSON失败: %s", exc, exc_info=True)
            return 0

    def migrate_from_csv(self, csv_file_path: str) -> int:
        if not os.path.isfile(csv_file_path):
            logger.warning("CSV文件不存在: %s", csv_file_path)
            return 0
        try:
            with open(csv_file_path, 'r', encoding='utf-8', newline='') as source:
                records = list(csv.DictReader(source))
            count = self._migrate_records(records)
            logger.info("CSV导入完成: count=%d", count)
            return count
        except (OSError, csv.Error) as exc:
            logger.error("读取CSV失败: %s", exc, exc_info=True)
            return 0

    def export_to_json(self, json_file_path: str) -> bool:
        try:
            os.makedirs(os.path.dirname(json_file_path) or '.', exist_ok=True)
            with open(json_file_path, 'w', encoding='utf-8') as target:
                json.dump(self.db_manager.get_all_diaries(), target, ensure_ascii=False, indent=2)
            return True
        except (OSError, TypeError, ValueError) as exc:
            logger.error("JSON导出失败: %s", exc, exc_info=True)
            return False

    def export_to_csv(self, csv_file_path: str) -> bool:
        fields = [
            'id', 'date', 'content', 'view_count',
            'last_viewed_at', 'updated_at', 'tags',
        ]
        try:
            os.makedirs(os.path.dirname(csv_file_path) or '.', exist_ok=True)
            with open(csv_file_path, 'w', encoding='utf-8', newline='') as target:
                writer = csv.DictWriter(target, fieldnames=fields, extrasaction='ignore')
                writer.writeheader()
                for diary in self.db_manager.get_all_diaries():
                    row = {key: diary.get(key) for key in fields}
                    row['tags'] = json.dumps(diary.get('tags') or [], ensure_ascii=False)
                    writer.writerow(row)
            return True
        except (OSError, csv.Error, TypeError, ValueError) as exc:
            logger.error("CSV导出失败: %s", exc, exc_info=True)
            return False

    @staticmethod
    def _sha256(file_path: str) -> str:
        digest = hashlib.sha256()
        with open(file_path, 'rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _valid_sqlite(file_path: str) -> bool:
        if not os.path.isfile(file_path):
            return False
        connection = None
        try:
            connection = sqlite3.connect(file_path)
            integrity = connection.execute('PRAGMA integrity_check').fetchone()
            foreign_keys = connection.execute('PRAGMA foreign_key_check').fetchall()
            return bool(integrity and str(integrity[0]).lower() == 'ok' and not foreign_keys)
        except (OSError, sqlite3.Error):
            return False
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _sqlite_backup(source, destination_path: str) -> None:
        destination = sqlite3.connect(destination_path)
        try:
            source.backup(destination)
        finally:
            destination.close()

    def backup_database(self, backup_path: str) -> bool:
        main_path = os.path.abspath(self.db_manager.db_path)
        trash_path = os.path.abspath(self._trash_db_path())
        target_path = os.path.abspath(backup_path)
        if target_path in {main_path, trash_path}:
            return False
        try:
            os.makedirs(os.path.dirname(target_path) or '.', exist_ok=True)
            with tempfile.TemporaryDirectory() as temp_dir:
                main_copy = os.path.join(temp_dir, 'main.db')
                trash_copy = os.path.join(temp_dir, 'trash.db')
                with self.db_manager._db_lock:
                    self._sqlite_backup(self.db_manager._get_write_connection(), main_copy)
                    repository = self.db_manager._ensure_trash_repository()
                    with repository._pool.lock:
                        self._sqlite_backup(repository._pool.connection, trash_copy)
                if not self._valid_sqlite(main_copy) or not self._valid_sqlite(trash_copy):
                    return False
                manifest = {
                    'format': 'diarypyqt-snapshot', 'version': 1,
                    'main_sha256': self._sha256(main_copy),
                    'trash_sha256': self._sha256(trash_copy),
                }
                with zipfile.ZipFile(target_path, 'w', zipfile.ZIP_DEFLATED) as archive:
                    archive.write(main_copy, 'main.db')
                    archive.write(trash_copy, 'trash.db')
                    archive.writestr('manifest.json', json.dumps(manifest, indent=2))
            return True
        except (OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
            logger.error("数据库备份失败: %s", exc, exc_info=True)
            return False

    @staticmethod
    def _replace_file(source_path: str, target_path: str) -> None:
        temporary = f'{target_path}.restore.tmp'
        try:
            shutil.copy2(source_path, temporary)
            os.replace(temporary, target_path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

    def _reopen_manager(self) -> None:
        """close() 之后重建连接池与全部服务；恢复的成功与失败路径都必须走到这里。"""
        self.db_manager._init_database()
        self.db_manager._init_trash_database()
        self.db_manager._recover_pending_trash_ops()
        self.db_manager._init_services()

    def restore_database(self, backup_path: str) -> bool:
        source_path = os.path.abspath(backup_path)
        main_path = os.path.abspath(self.db_manager.db_path)
        trash_path = os.path.abspath(self._trash_db_path())
        if not os.path.isfile(source_path) or source_path in {main_path, trash_path}:
            return False
        closed = False
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                main_copy = os.path.join(temp_dir, 'main.db')
                trash_copy = os.path.join(temp_dir, 'trash.db')
                has_trash = False
                if zipfile.is_zipfile(source_path):
                    with zipfile.ZipFile(source_path) as archive:
                        manifest = json.loads(archive.read('manifest.json'))
                        archive.extract('main.db', temp_dir)
                        if 'trash.db' in archive.namelist():
                            archive.extract('trash.db', temp_dir)
                            has_trash = True
                    if manifest.get('main_sha256') != self._sha256(main_copy):
                        return False
                    if has_trash and manifest.get('trash_sha256') != self._sha256(trash_copy):
                        return False
                else:
                    shutil.copy2(source_path, main_copy)
                if not self._valid_sqlite(main_copy) or (has_trash and not self._valid_sqlite(trash_copy)):
                    return False
                self.db_manager.close()
                closed = True
                self._replace_file(main_copy, main_path)
                if has_trash:
                    self._replace_file(trash_copy, trash_path)
                self._reopen_manager()
            return True
        except (OSError, ValueError, KeyError, sqlite3.Error, zipfile.BadZipFile) as exc:
            logger.error("数据库恢复失败: %s", exc, exc_info=True)
            if closed:
                # 替换文件阶段失败后不能让管理器停留在已关闭状态，
                # 否则后续任意调用与重试都会命中被置空的服务属性
                try:
                    self._reopen_manager()
                except (OSError, sqlite3.Error) as reopen_exc:
                    logger.error("恢复失败后重开数据库失败: %s", reopen_exc, exc_info=True)
            return False

    def validate_database_integrity(self) -> bool:
        main_path = os.path.abspath(self.db_manager.db_path)
        trash_path = os.path.abspath(self._trash_db_path())
        result = self._valid_sqlite(main_path) and self._valid_sqlite(trash_path)
        logger.info("数据库完整性检查: %s", result)
        return result