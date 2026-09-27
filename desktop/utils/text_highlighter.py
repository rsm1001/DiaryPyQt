"""
搜索结果关键词高亮器

- ``build_snippet``  截取关键词命中上下文窗口，生成行内富文本摘要
- ``highlight_text`` 全文高亮（用于预览面板 / 详情面板）

所有用户原文先 ``html.escape`` 转义，避免 XSS。

Python 3.8 兼容，仅依赖标准库。
"""
import html
import re
from typing import Iterable, List, Sequence, Tuple


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _is_logographic(ch: str) -> bool:
    """委托给 text_tokenizer 的脚本判定，避免循环 import 引发反向依赖"""
    from utils.text_tokenizer import classify_char, LOGOGRAPHIC_SCRIPTS
    return classify_char(ch) in LOGOGRAPHIC_SCRIPTS


def _is_caseless(ch: str) -> bool:
    """该字符是否不区分大小写（CJK / 假名 / Hangul 等无大小写）"""
    return _is_logographic(ch) or not ch.isalpha()


# ---------------------------------------------------------------------------
# 命中定位
# ---------------------------------------------------------------------------

def _find_hits(content: str, tokens: Sequence[str]) -> List[Tuple[int, int]]:
    """
    返回所有命中区间 ``[(start, end), ...]``，已排序且互不重叠。
    拉丁 token 用 ``re.escape`` + ``re.IGNORECASE``；CJK / 日 / 韩等用 ``str.find``
    （这些脚本无大小写概念）。
    """
    if not content or not tokens:
        return []
    hits: List[Tuple[int, int]] = []

    # 分离两种 token
    caseless_tokens: List[str] = []
    regex_tokens: List[str] = []
    for t in tokens:
        if not t:
            continue
        if all(_is_caseless(c) for c in t):
            caseless_tokens.append(t)
        else:
            regex_tokens.append(re.escape(t))

    # 表意 / 表音 token：直接子串扫描（去重避免重复报告）
    for t in sorted(set(caseless_tokens), key=len, reverse=True):
        start = 0
        while True:
            idx = content.find(t, start)
            if idx < 0:
                break
            hits.append((idx, idx + len(t)))
            start = idx + 1

    # 拉丁 token：合并为一个正则一次性扫描
    if regex_tokens:
        # 按 token 长度倒序，长 token 优先匹配
        pattern = '|'.join(sorted(regex_tokens, key=len, reverse=True))
        for m in re.finditer(pattern, content, flags=re.IGNORECASE):
            hits.append((m.start(), m.end()))

    # 排序 + 合并重叠
    hits.sort()
    merged: List[Tuple[int, int]] = []
    for start, end in hits:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _merge_windows(windows: List[Tuple[int, int]], window: int) -> List[Tuple[int, int]]:
    """
    把每个 hit 扩展为 ±``window`` 字符的窗口，相邻 / 重叠窗口合并。

    边界裁剪到 [0, len(content)] 由调用方处理。
    """
    if not windows:
        return []
    windows.sort()
    merged: List[Tuple[int, int]] = [(max(0, s - window), e + window) for s, e in windows]
    out: List[Tuple[int, int]] = [merged[0]]
    for s, e in merged[1:]:
        if s <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------

# 关键词高亮的内联样式（亮黄底 + 深字 + 加粗）
_HIGHLIGHT_STYLE = 'background-color:#FFEB3B;color:#222;font-weight:bold;border-radius:2px;padding:0 2px;'

# 默认外观参数
_DEFAULT_WINDOW = 60
_DEFAULT_MAX_HITS = 5


def _render_segment(
    text: str,
    rel_hits: List[Tuple[int, int]],
    total_hits: int,
) -> str:
    """渲染单个窗口片段为 HTML 片段（不含前后省略号）"""
    if not rel_hits:
        return html.escape(text)
    parts: List[str] = []
    cursor = 0
    for s, e in rel_hits:
        if s > cursor:
            parts.append(html.escape(text[cursor:s]))
        parts.append(
            '<span style="{}">{}</span>'.format(
                _HIGHLIGHT_STYLE,
                html.escape(text[s:e]),
            )
        )
        cursor = e
    if cursor < len(text):
        parts.append(html.escape(text[cursor:]))
    return ''.join(parts)


def build_snippet(
    content: str,
    tokens: Sequence[str],
    window: int = _DEFAULT_WINDOW,
    max_hits: int = _DEFAULT_MAX_HITS,
) -> str:
    """
    构造行内富文本摘要（用于搜索结果列表项）。

    - 取前 ``max_hits`` 个 hit 周围 ±``window`` 字符的窗口
    - 窗口之间用 ``…`` 连接
    - 命中位置以 ``<span style="...">...</span>`` 包裹

    返回完整 HTML 字符串（不含 ``<html>`` 头），可直接赋给
    ``QListWidgetItem.setData(DisplayRole, html)`` 或 ``QTextBrowser.setHtml()``。
    """
    if not content or not tokens:
        return html.escape(content) if content else ''

    hits = _find_hits(content, tokens)
    total_hits = len(hits)
    if total_hits == 0:
        return html.escape(content[: window * 2]) + (
            '…' if len(content) > window * 2 else ''
        )

    windows = _merge_windows([(s, e) for s, e in hits], window)[:max_hits]
    n = len(content)
    parts: List[str] = []
    for i, (s, e) in enumerate(windows):
        if i > 0 and s > 0:
            parts.append('<span style="color:#999;">…</span>')
        s_clip = max(0, s)
        e_clip = min(n, e)
        if s_clip > 0:
            parts.append('<span style="color:#999;">…</span>')
        seg = content[s_clip:e_clip]
        # 把 hits 映射到 seg 内相对坐标
        rel = [(max(0, hs - s_clip), min(len(seg), he - s_clip)) for hs, he in hits if hs < e_clip and he > s_clip]
        parts.append(_render_segment(seg, rel, total_hits))
        if e_clip < n:
            parts.append('<span style="color:#999;">…</span>')
    return ''.join(parts)


def highlight_text(
    content: str,
    tokens: Sequence[str],
) -> str:
    """
    全文高亮（用于预览面板 / 详情面板）。不做截断，把所有命中位置用
    ``<span>`` 标黄。
    """
    if not content:
        return ''
    if not tokens:
        return html.escape(content)
    hits = _find_hits(content, tokens)
    if not hits:
        return html.escape(content)
    parts: List[str] = []
    cursor = 0
    for s, e in hits:
        if s > cursor:
            parts.append(html.escape(content[cursor:s]))
        parts.append(
            '<span style="{}">{}</span>'.format(
                _HIGHLIGHT_STYLE,
                html.escape(content[s:e]),
            )
        )
        cursor = e
    if cursor < len(content):
        parts.append(html.escape(content[cursor:]))
    return ''.join(parts)


def count_hits(content: str, tokens: Sequence[str]) -> int:
    """统计命中次数（用于"命中 N 处"标签）"""
    if not content or not tokens:
        return 0
    return len(_find_hits(content, tokens))
