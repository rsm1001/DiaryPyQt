"""
多语种文本工具

- ``classify_script``  / ``is_logographic`` 识别字符所属 Unicode 脚本（修 Bug：
  原实现 ``'一' <= c <= '鿿'`` 仅覆盖 CJK 基本平面，遗漏日文假名 / 韩文 Hangul /
  CJK 扩展区 / 兼容汉字，导致日文 / 韩文查询走错分支）
- ``tokenize`` 按脚本分词；CJK / Kana / Hangul 默认字符 unigram
  （无外部分词器依赖；空格串直接喂给 FTS5）
- ``split_into_segments`` 按脚本连续段切分，用于构造"片段 = 完整短语"的 MATCH
- ``build_fts_match`` 把查询翻译成 FTS5 MATCH 表达式
- ``like_or_pattern`` 退化为多 token LIKE OR 模式

所有函数 100% 纯 Python 3.8 兼容，仅依赖标准库。
"""
import re
import unicodedata
from typing import Iterable, List, Set, Tuple


# ---------------------------------------------------------------------------
# 脚本分类
# ---------------------------------------------------------------------------

LATIN = 'latin'
CJK_HAN = 'cjk_han'                # 汉字
CJK_HIRAGANA = 'cjk_hiragana'      # 平假名
CJK_KATAKANA = 'cjk_katakana'      # 片假名
HANGUL = 'hangul'                  # 韩文（音节 + Jamo）
DIGIT = 'digit'
PUNCTUATION = 'punctuation'
OTHER = 'other'

LOGOGRAPHIC_SCRIPTS = {CJK_HAN, CJK_HIRAGANA, CJK_KATAKANA, HANGUL}


def classify_char(ch: str) -> str:
    """
    判定单个字符所属脚本。

    实现要点：直接按 Unicode 区间判定，不依赖 ``unicodedata`` 的 category；
    日文 / 韩文 / CJK 扩展区都覆盖。
    """
    cp = ord(ch)
    # 拉丁字母（含重音拉丁 / 拉丁扩展）
    if (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A) or (0x00C0 <= cp <= 0x024F):
        return LATIN
    # 平假名
    if 0x3040 <= cp <= 0x309F:
        return CJK_HIRAGANA
    # 片假名 + 半角片假名
    if (0x30A0 <= cp <= 0x30FF) or (0xFF65 <= cp <= 0xFF9F):
        return CJK_KATAKANA
    # 韩文音节
    if 0xAC00 <= cp <= 0xD7AF:
        return HANGUL
    # 韩文 Jamo（兼容 / 扩展 / 尾字母）
    if (0x1100 <= cp <= 0x11FF) or (0xA960 <= cp <= 0xA97F) or (0xD7B0 <= cp <= 0xD7FF):
        return HANGUL
    # CJK 统一汉字基本平面
    if 0x4E00 <= cp <= 0x9FFF:
        return CJK_HAN
    # CJK 扩展 A
    if 0x3400 <= cp <= 0x4DBF:
        return CJK_HAN
    # CJK 扩展 B–F
    if 0x20000 <= cp <= 0x2BFFF:
        return CJK_HAN
    # CJK 兼容汉字
    if 0xF900 <= cp <= 0xFAFF:
        return CJK_HAN
    # 数字
    if ch.isdigit():
        return DIGIT
    # 标点 / 空白
    if unicodedata.category(ch)[0] in ('P', 'Z', 'C', 'S'):
        return PUNCTUATION
    return OTHER


def classify_script(text: str) -> Set[str]:
    """返回文本中出现的脚本集合（按字符扫描，自动跳过标点/空白）"""
    scripts: Set[str] = set()
    for ch in text:
        s = classify_char(ch)
        if s in LOGOGRAPHIC_SCRIPTS or s == LATIN:
            scripts.add(s)
    return scripts


def is_logographic(text: str) -> bool:
    """文本中是否包含 CJK / 假名 / Hangul 任一表意 / 表音脚本"""
    for ch in text:
        if classify_char(ch) in LOGOGRAPHIC_SCRIPTS:
            return True
    return False


# ---------------------------------------------------------------------------
# 分词
# ---------------------------------------------------------------------------

# 拉丁词切分：非字母数字即分隔
_LATIN_SPLIT_RE = re.compile(r'[^0-9A-Za-zÀ-ɏ]+')


def _is_logographic_char(ch: str) -> bool:
    return classify_char(ch) in LOGOGRAPHIC_SCRIPTS


def tokenize(text: str) -> List[str]:
    """
    多语种分词（无外部依赖）。

    - 拉丁片段：按非字母数字切分 + ``lower()``，去空
    - CJK / 假名 / Hangul：每字符一个 token（unigram 方案）
    - 标点 / 空白：跳过

    返回 token 列表（可能含重复；FTS5 自身会去重 / 合并）。
    """
    if not text:
        return []
    tokens: List[str] = []
    buf: List[str] = []
    for ch in text:
        if _is_logographic_char(ch):
            # 冲掉拉丁缓冲
            if buf:
                word = ''.join(buf).lower()
                if word:
                    tokens.append(word)
                buf = []
            tokens.append(ch)
        elif ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                word = ''.join(buf).lower()
                if word:
                    tokens.append(word)
                buf = []
    if buf:
        word = ''.join(buf).lower()
        if word:
            tokens.append(word)
    return tokens


def split_into_segments(text: str) -> List[str]:
    """
    按脚本连续段切分。同一脚本连续字符归为一段。

    例：``"今天 hello 天气"`` -> ``["今天", " hello ", "天气"]``
    返回的段保留分隔符（空格），方便上层识别拉丁短语边界。
    """
    if not text:
        return []
    segments: List[str] = []
    current: List[str] = []
    current_script: str = ''

    for ch in text:
        s = classify_char(ch)
        if s in LOGOGRAPHIC_SCRIPTS or s == LATIN:
            if current_script and s != current_script:
                segments.append(''.join(current))
                current = [ch]
                current_script = s
            else:
                current.append(ch)
                current_script = s
        else:
            # 标点 / 空白：归入当前段（作为天然分隔），不切换 current_script
            current.append(ch)
    if current:
        segments.append(''.join(current))
    return segments


# ---------------------------------------------------------------------------
# FTS5 MATCH 表达式构造
# ---------------------------------------------------------------------------

def _quote(token: str) -> str:
    """FTS5 双引号短语包裹；引号转义为 ``""``"""
    return '"' + token.replace('"', '""') + '"'


def build_fts_match(keyword: str) -> Tuple[str, List[str]]:
    """
    把用户输入翻译成 FTS5 MATCH 表达式。

    返回 ``(match_expr, tokens)``：
    - ``match_expr`` 是可直接传给 ``MATCH ?`` 的字符串
    - ``tokens`` 是分词结果，供上层高亮 / 兜底 LIKE 使用

    策略：
    - 空关键词 -> ``""``（上层应单独处理"显示全部"逻辑）
    - 纯拉丁 -> 整段当短语
    - 含表意 / 表音脚本 -> 用 unigram 列表以 AND 拼接
    - 混合 -> 每个 segment 单独 AND，segment 内 CJK 用 AND、拉丁用短语
    """
    keyword = (keyword or '').strip()
    if not keyword:
        return '', []

    tokens = tokenize(keyword)
    if not tokens:
        return '', []

    scripts = classify_script(keyword)

    # 纯拉丁：当短语处理
    if not (scripts & LOGOGRAPHIC_SCRIPTS):
        return _quote(keyword), tokens

    # 纯 CJK/日韩：unigram AND
    if not (scripts & {LATIN}):
        return ' AND '.join(_quote(t) for t in tokens), tokens

    # 混合：按段切
    segments = split_into_segments(keyword)
    parts: List[str] = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        seg_scripts = classify_script(seg)
        seg_tokens = tokenize(seg)
        if not seg_tokens:
            continue
        if seg_scripts & LOGOGRAPHIC_SCRIPTS:
            # CJK 段：每个字符 AND
            parts.append(' AND '.join(_quote(t) for t in seg_tokens))
        else:
            # 拉丁段：整段当短语
            parts.append(_quote(seg))
    if not parts:
        return '', tokens
    return ' AND '.join(parts), tokens


def like_or_pattern(keyword: str) -> List[str]:
    """
    LIKE 兜底用：把关键词拆成多个子串，生成 ``%sub%`` 列表。

    例：``"今天 weather"`` -> ``["%今天%", "%weather%"]``
    """
    tokens = tokenize(keyword)
    if not tokens:
        stripped = (keyword or '').strip()
        return [f'%{stripped}%'] if stripped else []
    return [f'%{t}%' for t in tokens]
