"""
高亮器（build_snippet / highlight_text / count_hits）的单测
"""
import pytest

from utils.text_highlighter import build_snippet, count_hits, highlight_text


# ---------------------------------------------------------------------------
# highlight_text
# ---------------------------------------------------------------------------

class TestHighlightText:
    def test_no_tokens(self):
        assert highlight_text("hello world", []) == "hello world"

    def test_empty_content(self):
        assert highlight_text("", ["hello"]) == ""

    def test_latin_case_insensitive(self):
        out = highlight_text("Hello WORLD", ["hello"])
        assert "<span" in out
        assert "Hello" in out  # 原文大小写被保留
        # 但应该确实在 span 内
        assert "background-color:#FFEB3B" in out

    def test_cjk_hit(self):
        out = highlight_text("今天天气很好", ["今天"])
        assert "background-color:#FFEB3B" in out
        assert "今天" in out

    def test_html_escape(self):
        # XSS 防护：原文 <script> 应被转义
        out = highlight_text("<script>alert(1)</script>", ["alert"])
        assert "<script>" not in out
        assert "&lt;script&gt;" in out

    def test_multiple_hits(self):
        out = highlight_text("今天今天今天", ["今"])
        # 3 个 hit 都被标黄
        assert out.count("<span") == 3


# ---------------------------------------------------------------------------
# build_snippet
# ---------------------------------------------------------------------------

class TestBuildSnippet:
    def test_no_hit_returns_preview(self):
        out = build_snippet("hello world", ["xyz"], window=20, max_hits=3)
        assert "hello world" in out
        assert "<span" not in out

    def test_with_hit_contains_span(self):
        out = build_snippet("今天天气很好啊", ["今天"], window=30, max_hits=3)
        assert "<span" in out
        assert "今天" in out

    def test_truncation_with_ellipsis(self):
        content = "x" * 200 + "今天" + "y" * 200
        out = build_snippet(content, ["今天"], window=10, max_hits=1)
        # 含省略号
        assert "…" in out or "..." in out
        assert "今天" in out

    def test_html_escape(self):
        out = build_snippet("内容 <危险> 今天", ["今"], window=20)
        assert "<危险>" not in out
        assert "&lt;危险&gt;" in out


# ---------------------------------------------------------------------------
# count_hits
# ---------------------------------------------------------------------------

class TestCountHits:
    def test_basic(self):
        assert count_hits("今天今天", ["今"]) == 2

    def test_no_hit(self):
        assert count_hits("hello", ["今"]) == 0

    def test_multiple_tokens_or(self):
        # 计 hit 区间总数（不是按 token 去重）
        assert count_hits("今天 hello 天气", ["今", "hello"]) == 2

    def test_empty(self):
        assert count_hits("", ["x"]) == 0
        assert count_hits("hello", []) == 0
