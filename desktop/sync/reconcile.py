"""以日期、正文和标签的唯一组合建立桌面与服务器日记的候选映射。"""
from collections import defaultdict
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class MappingPlan:
    """仅记录明确一对一的配对，歧义和未匹配项不得自动写入。"""

    matches: Dict[str, Dict[str, Any]]
    local_only: List[str]
    remote_only: List[str]
    ambiguous: List[str]

    @property
    def complete(self) -> bool:
        return not (self.local_only or self.remote_only or self.ambiguous)


def canonical_payload(diary: Dict[str, Any]) -> Dict[str, Any]:
    """三端统一使用日期、正文和标签名称作为同步内容。"""
    tags = diary.get("tags") or []
    names = [tag.get("name", "") if isinstance(tag, dict) else tag for tag in tags]
    return {
        "date": str(diary.get("date", ""))[:10],
        "content": str(diary.get("content", "")).strip(),
        "tags": sorted({str(name).strip() for name in names if str(name).strip()}),
    }


def payload_digest(diary: Dict[str, Any]) -> str:
    """日期和标签变更也必须触发同步，不能只比较正文哈希。"""
    payload = json.dumps(canonical_payload(diary), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _identity_key(diary: Dict[str, Any]) -> tuple:
    payload = canonical_payload(diary)
    return payload["date"], payload["content"], tuple(payload["tags"])


def plan_mapping(local: List[Dict[str, Any]], remote: List[Dict[str, Any]]) -> MappingPlan:
    """重复的日记即使内容相同也不猜测 ID 对应关系。"""
    if (len({str(item["id"]) for item in local}) != len(local)
            or len({str(item["id"]) for item in remote}) != len(remote)):
        raise ValueError("日记 ID 重复，无法安全建立映射")
    local_index = defaultdict(list)
    remote_index = defaultdict(list)
    for diary in local:
        local_index[_identity_key(diary)].append(diary)
    for diary in remote:
        expected = "sha256:" + hashlib.sha256(str(diary["content"]).encode("utf-8")).hexdigest()
        if diary.get("deleted_at") or diary.get("content_hash") != expected:
            raise ValueError("服务器日记内容哈希异常，停止建立映射")
        remote_index[_identity_key(diary)].append(diary)

    matches = {}
    local_only = []
    remote_only = []
    ambiguous = []
    for fingerprint in local_index.keys() | remote_index.keys():
        local_items = local_index[fingerprint]
        remote_items = remote_index[fingerprint]
        if len(local_items) == len(remote_items) == 1:
            local_item, remote_item = local_items[0], remote_items[0]
            matches[str(local_item["id"])] = {
                "remote_id": str(remote_item["id"]),
                "version": int(remote_item["version"]),
                "content_hash": remote_item["content_hash"],
                "date": canonical_payload(local_item)["date"],
                "payload_hash": payload_digest(local_item),
            }
        elif local_items and remote_items:
            ambiguous.extend(str(item["id"]) for item in local_items)
        else:
            local_only.extend(str(item["id"]) for item in local_items)
            remote_only.extend(str(item["id"]) for item in remote_items)
    return MappingPlan(matches, sorted(local_only), sorted(remote_only), sorted(ambiguous))
