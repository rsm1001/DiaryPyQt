#!/usr/bin/env python3
"""Claude Code PostToolUse 风格守卫。"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

MAX_SOURCE_LINES = 500
MAX_SOURCE_FILES_PER_DIR = 10
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".vue"}
BACKEND_SUFFIXES = {".py"}
FRONTEND_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".vue"}
CONFIG_NAMES = {"config.py", "settings.py"}

ENDPOINT_RE = re.compile(
    r"(?i)(https?://|wss?://|localhost\b|127\.0\.0\.1\b|\b\d{1,3}(?:\.\d{1,3}){3}\b)"
)
PORT_RE = re.compile(r"(?i)\b(port|端口)\s*[:=]\s*['\"]?\d{2,5}['\"]?")
SENSITIVE_ASSIGN_RE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|auth[_-]?code|密钥|密码)\s*[:=]\s*['\"][^'\"]{6,}['\"]"
)
SQL_INTERPOLATION_RE = re.compile(
    r"\.execute\(\s*(?:f['\"]|['\"][^'\"]*(?:%|\+|\.format\())",
    re.DOTALL,
)
ENV_READ_RE = re.compile(
    r"(?:os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]|os\.environ(?:\.get)?\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]|os\.environ\[['\"]([A-Z][A-Z0-9_]*)['\"]\])"
)
PRINT_RE = re.compile(r"(?m)^\s*print\(")
API_FILE_RE = re.compile(r"(?i)(api|route|endpoint|handler)")
EXTERNAL_IMPORT_RE = re.compile(
    r"(?m)^\s*(?:import\s+(requests|httpx|aiohttp)\b|from\s+(requests|httpx|aiohttp)\s+import\s+)"
)
DB_DIRECT_RE = re.compile(r"\b(sqlite3|psycopg2?|pymysql|create_engine|Session\()\b")
STR_E_RESPONSE_RE = re.compile(
    r"(?s)(?:return|HTTPException|JSONResponse|jsonify|Response)\([^\n)]*str\(e\)"
)
FASTAPI_DECORATOR_RE = re.compile(r"(?m)^\s*@\w+\.(?:get|post|put|patch|delete)\(")

RULE_REMINDER = (
    "确认 14 条项目规范：配置不硬编码、日志带 request_id、API 薄层、"
    "DB 走 Repository、外部系统封装。"
)


def main() -> int:
    payload = _read_payload()
    paths = _extract_file_paths(payload) or _fallback_file_paths_from_session()
    notices = [_build_notice(_normalize_path(path)) for path in paths]

    if not notices:
        notices = ["Style guard notice: <unknown>\n- 未找到文件路径，跳过规则检查。"]

    _emit_notices(notices)
    return 0


def _read_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _extract_file_paths(payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"file_path", "filePath"} and isinstance(item, str):
                    paths.append(item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(payload)
    return list(dict.fromkeys(paths))


def _fallback_file_paths_from_session() -> list[str]:
    transcript_path = _session_transcript_path()
    if not transcript_path or not transcript_path.exists():
        return []

    try:
        lines = transcript_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    for line in reversed(lines[-200:]):
        paths = _file_paths_from_transcript_line(line)
        if paths:
            return paths
    return []


def _session_transcript_path() -> Path | None:
    configured = os.environ.get("STYLE_GUARD_TRANSCRIPT_PATH")
    if configured:
        return Path(configured)

    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session_id:
        return None

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("PWD")
    projects_dir = Path.home() / ".claude" / "projects"
    if project_dir:
        encoded = re.sub(r"[^A-Za-z0-9_.-]", "-", project_dir)
        candidate = projects_dir / encoded / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate

    matches = list(projects_dir.glob(f"*/{session_id}.jsonl"))
    return matches[0] if matches else None


def _file_paths_from_transcript_line(line: str) -> list[str]:
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return []

    if record.get("type") != "assistant":
        return []

    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []

    paths: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "tool_use" or item.get("name") not in {"Edit", "Write", "MultiEdit"}:
            continue
        tool_input = item.get("input")
        if isinstance(tool_input, dict):
            paths.extend(_extract_file_paths(tool_input))
    return list(dict.fromkeys(paths))


def _normalize_path(file_path: str) -> Path:
    normalized = file_path.replace("\\", "/")
    msys_match = re.match(r"^/([A-Za-z])/(.*)", normalized)
    if msys_match:
        return Path(f"{msys_match.group(1).upper()}:/{msys_match.group(2)}")

    path = Path(normalized)
    if path.is_absolute():
        return path

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return Path(project_dir) / path


def _build_notice(path: Path) -> str:
    display = _display_path(path)
    messages = _messages_for_path(path)
    return "Style guard notice: " + display + "\n" + "\n".join(f"- {message}" for message in messages)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _messages_for_path(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return ["文件不存在或不是普通文件，跳过规则检查。"]
    if not _is_project_source(path):
        return ["非源代码文件，跳过规则检查。"]
    return _check_file(path)


def _is_project_source(path: Path) -> bool:
    ignored = {"node_modules", "__pycache__", ".git", ".pytest_cache"}
    if ignored.intersection(path.parts):
        return False
    return path.suffix in SOURCE_SUFFIXES or path.name in {"CLAUDE.md", ".env", ".env.example"}


def _check_file(path: Path) -> list[str]:
    text = _read_text(path)
    messages = []
    line_count = _line_count(text)
    messages.append(f"文件行数: {line_count}/{MAX_SOURCE_LINES}")
    if line_count > MAX_SOURCE_LINES:
        messages.append("警告: 单个源代码文件超过 500 行；新增大块逻辑应拆分。")

    if path.suffix in SOURCE_SUFFIXES:
        source_count = _count_source_files(path.parent)
        messages.append(f"目录源文件数: {source_count}/{MAX_SOURCE_FILES_PER_DIR}")
        if source_count > MAX_SOURCE_FILES_PER_DIR:
            messages.append("警告: 单个文件夹源代码数量超过 10 个；新增模块优先建子目录。")
        _check_common_source(path, text, messages)

    if path.name == ".env":
        messages.append("提醒: .env 只放真实敏感配置；不要把真实值写入回复、日志或提交信息。")
        _check_env_file(text, messages)
    elif path.name == ".env.example":
        messages.append("提醒: .env.example 只能放示例值，禁止真实密钥、密码、token。")
        _check_env_example(text, messages)

    if path.suffix in BACKEND_SUFFIXES:
        _check_python(path, text, messages)
    if path.suffix in FRONTEND_SUFFIXES:
        _check_frontend(path, text, messages)

    messages.append(f"提醒: {RULE_REMINDER}")
    return messages


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _count_source_files(directory: Path) -> int:
    try:
        return sum(1 for child in directory.iterdir() if child.is_file() and child.suffix in SOURCE_SUFFIXES)
    except OSError:
        return 0


def _is_hook_script(path: Path) -> bool:
    return ".claude" in path.parts and "hooks" in path.parts


def _is_config_module(path: Path) -> bool:
    lower_parts = {part.lower() for part in path.parts}
    return "config" in lower_parts or path.name in CONFIG_NAMES


def _check_common_source(path: Path, text: str, messages: list[str]) -> None:
    if _is_hook_script(path):
        return
    if ENDPOINT_RE.search(text) or PORT_RE.search(text):
        if not _is_config_module(path):
            messages.append("警告: 发现疑似硬编码外部地址/IP/localhost/端口；应放入 config 或环境变量。")
    if SENSITIVE_ASSIGN_RE.search(text):
        messages.append("警告: 发现疑似硬编码密钥/密码/token；应放入 .env，并同步 .env.example 示例。")


def _check_python(path: Path, text: str, messages: list[str]) -> None:
    if PRINT_RE.search(text) and not _is_hook_script(path):
        messages.append("警告: Python 运行日志应使用 utils.logger，不使用 print()。")

    if SQL_INTERPOLATION_RE.search(text):
        messages.append("警告: 疑似 SQL 字符串拼接；必须使用参数化查询。")

    env_keys = sorted({key for match in ENV_READ_RE.findall(text) for key in match if key})
    if env_keys and not _is_config_module(path) and not _is_hook_script(path):
        messages.append(f"提醒: 环境变量读取应集中在 config/；发现 {', '.join(env_keys)}。")

    if _looks_like_api_handler(path, text):
        if EXTERNAL_IMPORT_RE.search(text):
            messages.append("提醒: API handler 不应直接调用第三方服务；外部调用放 service 或 adapter。")
        if DB_DIRECT_RE.search(text):
            messages.append("提醒: API handler 不应直接访问 DB；数据库访问放 Repository 层。")
        if STR_E_RESPONSE_RE.search(text):
            messages.append("提醒: 不要把 str(e) 直接返回前端；使用标准化错误响应。")
        if "logger" not in text:
            messages.append("提醒: API 关键操作应记录结构化日志，并包含 request_id。")


def _check_frontend(path: Path, text: str, messages: list[str]) -> None:
    if path.suffix == ".vue" and "<script setup lang=\"ts\">" not in text and "<script setup lang='ts'>" not in text:
        messages.append("提醒: Vue 组件优先使用 <script setup lang=\"ts\">。")
    if (ENDPOINT_RE.search(text) or PORT_RE.search(text)) and "services" not in {part.lower() for part in path.parts}:
        messages.append("提醒: 前端组件不应直接拼接服务地址；API 调用集中到 services 层。")


def _looks_like_api_handler(path: Path, text: str) -> bool:
    path_text = "/".join(path.parts)
    return bool(API_FILE_RE.search(path_text) or FASTAPI_DECORATOR_RE.search(text))


def _check_env_file(text: str, messages: list[str]) -> None:
    if "=" not in text:
        return
    messages.append("提醒: .env 可能包含真实敏感值；禁止提交或复制到回复中。")


def _check_env_example(text: str, messages: list[str]) -> None:
    risky_values = re.findall(
        r"(?im)^(?:[^#\n]*(?:PASSWORD|SECRET|TOKEN|API[_-]?KEY)[^=]*)=(?!\s*(?:example|demo|dummy|changeme|your_|<|$))\S+",
        text,
    )
    if risky_values:
        messages.append("警告: .env.example 疑似包含真实敏感值；只能保留示例值。")


def _emit_notices(notices: list[str]) -> None:
    message = "\n\n".join(notices)
    output = {
        "systemMessage": message,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        },
        "suppressOutput": False,
    }
    print(json.dumps(output, ensure_ascii=True))


if __name__ == "__main__":
    raise SystemExit(main())
