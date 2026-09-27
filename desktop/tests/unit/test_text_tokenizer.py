"""
多语种分词器 / 脚本分类器 / FTS5 MATCH 构造的单测
"""
import pytest

from utils.text_tokenizer import (
    CJK_HAN,
    CJK_HIRAGANA,
    CJK_KATAKANA,
    HANGUL,
    LATIN,
    LOGOGRAPHIC_SCRIPTS,
    build_fts_match,
    classify_char,
    classify_script,
    is_logographic,
    like_or_pattern,
    split_into_segments,
    tokenize,
)


# ---------------------------------------------------------------------------
# classify_char / classify_script
# ---------------------------------------------------------------------------

class TestClassifyChar:
    @pytest.mark.parametrize("ch, expected", [
        ('A', LATIN),
        ('z', LATIN),
        ('é', LATIN),          # 拉丁扩展
        ('中', CJK_HAN),
        ('鿿', CJK_HAN),
        ('㐀', CJK_HAN),       # 扩展 A
        ('あ', CJK_HIRAGANA),
        ('ア', CJK_KATAKANA),
        ('ｱ', CJK_KATAKANA),  # 半角片假名
        ('한', HANGUL),        # 韩文音节
        ('ᄀ', HANGUL),        # 韩文 Jamo
    ])
    def test_basic_scripts(self, ch, expected):
        assert classify_char(ch) == expected

    def test_punctuation(self):
        assert classify_char(',') in ('punctuation', 'other')
        assert classify_char(' ') in ('punctuation', 'other')

    def test_digit(self):
        assert classify_char('5') == 'digit'
        assert classify_char('〇') in ('digit', 'other', 'punctuation')


class TestClassifyScript:
    def test_pure_latin(self):
        assert classify_script("hello world") == {LATIN}

    def test_pure_cjk(self):
        assert classify_script("今天天气") == {CJK_HAN}

    def test_pure_japanese(self):
        # 修 Bug：原本 has_chinese 会漏掉假名
        scripts = classify_script("ありがとう")
        assert CJK_HIRAGANA in scripts

    def test_pure_korean(self):
        # 修 Bug：原本 has_chinese 会漏掉 Hangul
        scripts = classify_script("안녕하세요")
        assert HANGUL in scripts

    def test_mixed(self):
        scripts = classify_script("今天 weather")
        assert CJK_HAN in scripts
        assert LATIN in scripts

    def test_punctuation_only(self):
        assert classify_script("!?, 。") == set()

    def test_empty(self):
        assert classify_script("") == set()


class TestIsLogographic:
    @pytest.mark.parametrize("text, expected", [
        ("hello", False),
        ("", False),
        ("123", False),
        ("今天", True),
        ("谢谢", True),
        ("ありがとう", True),   # 假名
        ("カタカナ", True),     # 片假名
        ("안녕", True),         # 韩文
        ("hello 今天", True),   # 混合
    ])
    def test_logographic_detection(self, text, expected):
        assert is_logographic(text) is expected


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_pure_latin(self):
        assert tokenize("hello world") == ["hello", "world"]

    def test_latin_lowercased(self):
        assert tokenize("Hello WORLD") == ["hello", "world"]

    def test_latin_with_punctuation(self):
        assert tokenize("hello, world!") == ["hello", "world"]

    def test_pure_cjk_unigram(self):
        # 修 Bug：原实现搜"今天天气"会因 FTS5 整字匹配搜不到；
        # 字符 unigram 后每个汉字是一个 token
        assert tokenize("今天天气") == ["今", "天", "天", "气"]

    def test_pure_japanese(self):
        # 修 Bug：原实现 has_chinese 范围漏掉假名
        result = tokenize("ありがとう")
        assert "あ" in result
        assert "り" in result
        assert len(result) == 5

    def test_pure_korean(self):
        # 修 Bug：原实现 has_chinese 范围漏掉 Hangul
        result = tokenize("안녕")
        assert "안" in result
        assert "녕" in result

    def test_mixed_latin_cjk(self):
        result = tokenize("今天 hello 天气")
        assert "今天" not in result  # unigram
        assert "今" in result
        assert "天" in result
        assert "hello" in result
        assert "天气" not in result

    def test_empty(self):
        assert tokenize("") == []
        assert tokenize(None) == []

    def test_punctuation_only(self):
        assert tokenize("!?, 。") == []


# ---------------------------------------------------------------------------
# split_into_segments
# ---------------------------------------------------------------------------

class TestSplitIntoSegments:
    def test_mixed(self):
        segs = split_into_segments("今天 hello 天气")
        # 至少应包含 "今天" 和 "天气" 两段
        joined = "".join(segs)
        assert "今天" in joined
        assert "hello" in joined
        assert "天气" in joined

    def test_pure_cjk(self):
        segs = split_into_segments("今天天气")
        assert "".join(segs) == "今天天气"

    def test_empty(self):
        assert split_into_segments("") == []


# ---------------------------------------------------------------------------
# build_fts_match
# ---------------------------------------------------------------------------

class TestBuildFtsMatch:
    def test_pure_latin_phrase(self):
        match, tokens = build_fts_match("hello world")
        assert match == '"hello world"'
        assert tokens == ["hello", "world"]

    def test_pure_cjk_unigram_and(self):
        match, tokens = build_fts_match("今天天气")
        # 4 个 unigram 以 AND 拼接
        assert " AND " in match
        for ch in "今天天气":
            assert '"{}"'.format(ch) in match
        assert tokens == ["今", "天", "天", "气"]

    def test_pure_japanese_unigram_and(self):
        # 修 Bug：原 has_chinese 漏假名
        match, tokens = build_fts_match("ありがとう")
        assert " AND " in match
        assert '"あ"' in match
        assert '"り"' in match
        assert tokens[0] == "あ"

    def test_pure_korean_unigram_and(self):
        match, tokens = build_fts_match("안녕")
        assert " AND " in match
        assert '"안"' in match
        assert tokens == ["안", "녕"]

    def test_mixed(self):
        match, tokens = build_fts_match("今天 weather")
        assert " AND " in match
        assert '"今"' in match
        assert '"天"' in match
        assert '"weather"' in match
        assert "hello" not in tokens

    def test_empty(self):
        match, tokens = build_fts_match("")
        assert match == ""
        assert tokens == []

    def test_whitespace_only(self):
        match, tokens = build_fts_match("   ")
        assert match == ""
        assert tokens == []


# ---------------------------------------------------------------------------
# like_or_pattern
# ---------------------------------------------------------------------------

class TestLikeOrPattern:
    def test_cjk_multi_token(self):
        patterns = like_or_pattern("今天 weather")
        assert patterns == ["%今%", "%天%", "%weather%"]

    def test_latin(self):
        patterns = like_or_pattern("hello world")
        assert patterns == ["%hello%", "%world%"]

    def test_empty(self):
        assert like_or_pattern("") == []
        assert like_or_pattern(None) == []

    def test_whitespace_only(self):
        # 没有 token 也没有 stripped 字符
        assert like_or_pattern("   ") == []
