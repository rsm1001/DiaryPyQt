#!/usr/bin/env python3
"""Claude Code PostToolUse 风格守卫。"""
from __future__ import annotations

import ast
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

ENDPOINT_RE = re.compile(
    r"(?i)(https?://|wss?://|localhost\b|127\.0\.0\.1\b|\b\d{1,3}(?:\.\d{1,3}){3}\b)"
)
SENSITIVE_ASSIGN_RE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|auth[_-]?code)\s*[:=]\s*['\"][^'\"]{6,}['\"]"
)
OS_GETENV_RE = re.compile(r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]")
IMPORT_REQUESTS_RE = re.compile(r"^\s*import\s+requests\b|^\s*from\s+requests\s+import\s+", re.MULTILINE)
API_HANDLER_RE = re.compile(r"^\s*(async\s+def|def)\s+\w+\(", re.MULTILINE)
HTTP_EXCEPTION_STR_E_RE = re.compile(r"HTTPException\([^\)]*detail\s*=\s*str\(e\)", re.DOTALL)
LINE_ISSUE_RE = re.compile(r"^(警告|提醒): 第 (\d+) 行(.+)$")
PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$", re.MULTILINE)

RULE_REMINDER = (
    "确认 14 条项目规范：配置不硬编码、日志带 request_id、API 薄层、"
    "DB 走 Repository、外部系统封装。"
)

HARD_VIOLATION_MARKERS = (
    "发现疑似硬编码外部地址/IP/localhost",
    "疑似硬编码密钥/密码/token",
    "Python 运行日志应使用 utils.logger",
    "疑似 SQL 字符串拼接",
    "不要把 str(e) 直接返回前端",
)


def main() -> int:
    payload = _read_payload()
    file_paths = _extract_file_paths(payload) or _fallback_file_paths_from_session()
    if not file_paths:
        if payload:
            _emit_notices([_build_notice(Path("<unknown>"), [_payload_summary(payload)])])
        return 0

    notices = []
    seen_paths: set[str] = set()
    for file_path in file_paths:
        path = _normalize_path(file_path, payload.get("cwd"))
        path_key = _path_key(path)
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)
        notices.append(_build_notice(path, _messages_for_path(path)))

    _emit_notices(notices)
    return 0


def _read_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _extract_file_paths(payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"file_path", "filePath"} and isinstance(item, str):
                    paths.append(item)
                elif key == "command" and isinstance(item, str):
                    paths.extend(match.group(1) for match in PATCH_FILE_RE.finditer(item))
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
        file_paths = _file_paths_from_transcript_line(line)
        if file_paths:
            return file_paths
    return []


def _session_transcript_path() -> Path | None:
    configured = os.environ.get("STYLE_GUARD_TRANSCRIPT_PATH")
    if configured:
        return Path(configured)

    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session_id:
        return None

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("PWD")
    if project_dir:
        encoded = re.sub(r"[^A-Za-z0-9_.-]", "-", project_dir)
        candidate = Path.home() / ".claude" / "projects" / encoded / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate

    matches = list((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"))
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


def _payload_summary(payload: dict[str, Any]) -> str:
    keys = ", ".join(sorted(payload.keys())) if payload else "empty"
    return f"未找到文件路径，跳过规则检查。payload keys={keys}"


def _normalize_path(file_path: str, session_cwd: Any = None) -> Path:
    normalized = file_path.replace("\\", "/")

    msys_match = re.match(r"^/([A-Za-z])/(.*)", normalized)
    if msys_match:
        return Path(f"{msys_match.group(1).upper()}:/{msys_match.group(2)}")

    drive_match = re.match(r"^([A-Za-z]):/(.*)", normalized)
    if drive_match:
        return Path(normalized)

    if isinstance(session_cwd, str) and session_cwd:
        candidate = Path(session_cwd) / normalized
        if candidate.exists():
            return candidate

    project_dir = os.environ.get("STYLE_GUARD_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        candidate = Path(project_dir) / normalized
        if candidate.exists():
            return candidate

    return Path(file_path)


def _path_key(path: Path) -> str:
    try:
        return str(path.resolve()).casefold()
    except OSError:
        return str(path).casefold()


def _is_project_source(path: Path) -> bool:
    if "node_modules" in path.parts or "__pycache__" in path.parts:
        return False
    if path.name == "CLAUDE.md":
        return True
    if path.suffix in SOURCE_SUFFIXES:
        return True
    if path.name in {".env", ".env.example"}:
        return True
    return False


def _messages_for_path(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return ["文件不存在或不是普通文件，跳过规则检查。"]
    if not _is_project_source(path):
        return ["非源代码文件，跳过规则检查。"]
    return _check_file(path)


def _check_file(path: Path) -> list[str]:
    messages: list[str] = []
    if not path.exists() or not path.is_file():
        return messages

    text = _read_text(path)
    line_count = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    messages.append(f"文件行数: {line_count}/{MAX_SOURCE_LINES}")
    if line_count > MAX_SOURCE_LINES:
        messages.append("警告: 单个源代码文件超过 500 行；新增大块逻辑应拆分。")

    if path.suffix in SOURCE_SUFFIXES:
        source_count = _count_source_files(path.parent)
        messages.append(f"目录源文件数: {source_count}/{MAX_SOURCE_FILES_PER_DIR}")
        if source_count > MAX_SOURCE_FILES_PER_DIR:
            messages.append("警告: 单个文件夹源代码数量超过 10 个；请重新按分类新建文件夹，并移动文件。")

    if path.name == ".env":
        messages.append("提醒: .env 只放真实敏感配置；不要把真实值写入回复、日志或提交信息。")

    if path.name == ".env.example":
        messages.append("提醒: .env.example 只能放示例值，禁止真实密钥、密码、token。")

    if path.suffix in SOURCE_SUFFIXES:
        _check_common_source(path, text, messages)
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


def _count_source_files(directory: Path) -> int:
    try:
        return sum(
            1
            for child in directory.iterdir()
            if child.is_file() and child.suffix in SOURCE_SUFFIXES
        )
    except OSError:
        return 0


def _is_hook_script(path: Path) -> bool:
    return ".claude" in path.parts and "hooks" in path.parts


def _check_common_source(path: Path, text: str, messages: list[str]) -> None:
    if ENDPOINT_RE.search(text) and "config" not in path.parts and not _is_hook_script(path):
        messages.append("警告: 发现疑似硬编码外部地址/IP/localhost；应放入 config 或环境变量。")

    if SENSITIVE_ASSIGN_RE.search(text):
        messages.append("警告: 发现疑似硬编码密钥/密码/token；应放入 .env，并同步 .env.example 示例。")


def _sql_messages(text: str) -> list[str]:
    """识别 SQL 语句中直接拼入的值，允许动态 ? 占位符。"""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    messages = []
    placeholders = _question_mark_placeholders(tree)
    user_controlled = _user_controlled_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_execute_call(node) or not node.args:
            continue
        level = _sql_expression_level(node.args[0], placeholders, user_controlled)
        if level == "block":
            messages.append(
                f"警告: 第 {node.lineno} 行疑似 SQL 字符串拼接；必须使用参数化查询。"
            )
        elif level == "review":
            messages.append(
                f"提醒: 第 {node.lineno} 行包含动态 SQL 标识符；必须确认使用白名单。"
            )
    return messages


def _is_execute_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr in {"execute", "executemany"}


def _question_mark_placeholders(tree: ast.AST) -> set[str]:
    placeholders = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if not isinstance(node.value.func, ast.Attribute) or node.value.func.attr != "join":
            continue
        if not node.value.args or not isinstance(node.value.args[0], ast.GeneratorExp):
            continue
        generator = node.value.args[0]
        if not isinstance(generator.elt, ast.Constant) or generator.elt.value != "?":
            continue
        placeholders.update(
            target.id for target in node.targets if isinstance(target, ast.Name)
        )
    return placeholders


def _user_controlled_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        if not _is_request_derived_expression(node.value):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def _sql_expression_level(
    expression: ast.AST, placeholders: set[str], user_controlled: set[str]
) -> str | None:
    if isinstance(expression, (ast.Constant, ast.Str)):
        return None
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, (ast.Add, ast.Mod)):
        return "block"
    if not isinstance(expression, ast.JoinedStr):
        return "review"
    expressions = [
        value.value for value in expression.values if isinstance(value, ast.FormattedValue)
    ]
    if all(isinstance(value, ast.Name) and value.id in placeholders for value in expressions):
        return None
    if any(
        (isinstance(value, ast.Name) and value.id in user_controlled)
        or _is_request_derived_expression(value)
        for value in expressions
    ):
        return "block"
    return "review"


def _is_request_derived_expression(expression: ast.AST) -> bool:
    """识别直接从 request 读取、但尚未赋值给局部变量的表达式。"""
    if isinstance(expression, ast.Name):
        return expression.id in {"request", "websocket"}
    if isinstance(expression, (ast.Attribute, ast.Subscript)):
        return _is_request_derived_expression(expression.value)
    if isinstance(expression, ast.Call):
        return (
            _is_request_derived_expression(expression.func)
            or any(_is_request_derived_expression(arg) for arg in expression.args)
            or any(
                _is_request_derived_expression(keyword.value)
                for keyword in expression.keywords
            )
        )
    return any(
        _is_request_derived_expression(child)
        for child in ast.iter_child_nodes(expression)
    )


def _check_python(path: Path, text: str, messages: list[str]) -> None:
    if "print(" in text and not _is_hook_script(path):
        messages.append("警告: Python 运行日志应使用 utils.logger，不使用 print()。")

    messages.extend(_sql_messages(text))

    env_keys = OS_GETENV_RE.findall(text)
    if env_keys and "config" not in path.parts:
        joined = ", ".join(sorted(set(env_keys)))
        messages.append(f"提醒: 环境变量读取应集中在 backend/python/config/；发现 {joined}。")

    if "api" in path.parts and IMPORT_REQUESTS_RE.search(text):
        messages.append("提醒: API handler 不应直接调用外部服务；外部调用放 services/external 或 adapter。")

    if "api" in path.parts and "sqlite3" in text:
        messages.append("提醒: API handler 不应直接访问数据库；数据库访问放 Repository/db 层。")

    if "api" in path.parts and HTTP_EXCEPTION_STR_E_RE.search(text):
        messages.append("提醒: 不要把 str(e) 直接返回前端；使用标准化错误响应。")

    if "api" in path.parts and API_HANDLER_RE.search(text) and "logger" not in text:
        messages.append("提醒: API 关键操作应记录结构化日志，复用 utils.logger request_id。")


def _check_frontend(path: Path, text: str, messages: list[str]) -> None:
    if path.suffix == ".vue" and "<script setup lang=\"ts\">" not in text and "<script setup lang='ts'>" not in text:
        messages.append("提醒: Vue 组件优先使用 <script setup lang=\"ts\">。")

    if ENDPOINT_RE.search(text) and "config" not in path.parts and "services" not in path.parts:
        messages.append("提醒: 前端组件不应直接拼接服务地址；API 调用集中到 src/services/api/。")


def _build_notice(path: Path, messages: list[str]) -> str:
    try:
        display = path.relative_to(Path.cwd())
    except ValueError:
        display = path

    notice = "Style guard notice: " + str(display)
    for message in _compact_messages(messages):
        notice += f"\n- {message}"
    return notice


def _compact_messages(messages: list[str]) -> list[str]:
    """按问题正文合并同一文件中的行号，并去除重复的无行号提示。"""
    line_groups: dict[tuple[str, str], list[str]] = {}
    for message in messages:
        match = LINE_ISSUE_RE.match(message)
        if match:
            key = (match.group(1), match.group(3))
            line_groups.setdefault(key, []).append(match.group(2))

    compacted = []
    emitted_line_groups = set()
    emitted_messages = set()
    for message in messages:
        match = LINE_ISSUE_RE.match(message)
        if match:
            key = (match.group(1), match.group(3))
            if key in emitted_line_groups:
                continue
            emitted_line_groups.add(key)
            lines = "、".join(dict.fromkeys(line_groups[key]))
            compacted.append(f"{key[0]}: 第 {lines} 行{key[1]}")
            continue
        if message not in emitted_messages:
            emitted_messages.add(message)
            compacted.append(message)
    return compacted


def _emit_notices(notices: list[str]) -> None:
    message = "\n\n".join(notices)
    output = {
        "systemMessage": message,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": _build_context_summary(notices),
        },
        "suppressOutput": False,
    }
    if _has_hard_violation(notices):
        output["continue"] = False
        output["stopReason"] = "style_guard 发现硬违规，必须先修复"
    print(json.dumps(output, ensure_ascii=True))


def _build_context_summary(notices: list[str]) -> str:
    warnings = []
    for notice in notices:
        lines = notice.splitlines()
        path = lines[0][len("Style guard notice: ") :] if lines and lines[0].startswith("Style guard notice: ") else "<unknown>"
        warning_lines = [line[2:] if line.startswith("- ") else line for line in lines[1:] if line.startswith("- 警告:")]
        if warning_lines:
            warnings.append(f"{path}: {'；'.join(warning_lines)}")

    if not warnings:
        return "Style guard context: 已运行，无警告或硬违规。"
    return "Style guard context: 存在需处理项：\n" + "\n".join(f"- {warning}" for warning in warnings)


def _has_hard_violation(notices: list[str]) -> bool:
    return any(
        marker in notice
        for notice in notices
        for marker in HARD_VIOLATION_MARKERS
    )


if __name__ == "__main__":
    raise SystemExit(main())
