"""桌面端日记服务 HTTP 适配器。"""
import base64
import json
import logging
from typing import Any, Dict, List, Optional
from urllib import error, request
from urllib.parse import urlsplit
from uuid import uuid4

from desktop.config.settings import get_sync_settings

logger = logging.getLogger(__name__)


class RemoteApiError(RuntimeError):
    """服务端请求失败；向界面隐藏内部错误细节。"""

    def __init__(self, message: str, status_code: int = 0, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class DiaryServerClient:
    """通过日记 API 访问服务端，不直接读写服务器数据库。"""

    def __init__(self, base_url: str, timeout: float = 15.0, password: str = ""):
        if password and urlsplit(base_url).scheme != "https":
            raise ValueError("连接密码只能通过 HTTPS 发送")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.password = password

    @classmethod
    def from_environment(cls) -> "DiaryServerClient":
        """只在启用远程连接时读取桌面端配置。"""
        settings = get_sync_settings()
        return cls(settings.base_url, settings.timeout, settings.password)

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        request_id = str(uuid4())
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Accept": "application/json", "X-Request-ID": request_id}
        if self.password:
            credentials = base64.b64encode(f"diary:{self.password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {credentials}"
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            http_request = request.Request(self.base_url + path, data=body, headers=headers, method=method)
            with request.urlopen(http_request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            logger.info("日记服务请求完成", extra={"request_id": request_id, "method": method, "path": path})
            return result
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                details = json.loads(raw)
            except ValueError:
                details = {}
            logger.warning("日记服务返回错误", extra={"request_id": request_id, "status": exc.code, "path": path})
            raise RemoteApiError(f"日记服务请求失败：HTTP {exc.code}", exc.code, details) from exc
        except (error.URLError, TimeoutError) as exc:
            logger.warning("日记服务网络不可用", extra={"request_id": request_id, "path": path})
            raise RemoteApiError("无法连接日记服务") from exc

    def list_diaries(self, offset: int, limit: int = 100) -> Dict[str, Any]:
        """读取完整日记列表用于首次映射，不能仅依赖增量日志。"""
        return self._request("GET", f"/api/v1/diaries?offset={offset}&limit={limit}")

    def list_all_diaries(self) -> List[Dict[str, Any]]:
        """逐页读取完整列表，重复 ID 表示分页不稳定，必须拒绝映射。"""
        items = []
        seen = set()
        while True:
            batch = self.list_diaries(len(items)).get("items", [])
            for diary in batch:
                if diary["id"] in seen:
                    raise ValueError("服务器分页重复，无法安全建立映射")
                seen.add(diary["id"])
            items.extend(batch)
            if len(batch) < 100:
                return items
    def pull(self, cursor: int) -> Dict[str, Any]:
        return self._request("GET", f"/api/v1/sync/pull?cursor={cursor}")

    def push(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._request("POST", "/api/v1/sync/push", {"operations": operations})
