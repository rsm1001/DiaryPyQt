"""
i18n 核心模块 - gettext 封装
"""
import gettext
import locale
import os
import sys
from pathlib import Path

# 翻译对象，初始为 None
_translator = None
_current_lang = 'zh_CN'

# 获取项目根目录
def _get_project_root():
    """获取项目根目录"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的路径
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


def init_i18n(lang=None):
    """
    初始化翻译系统

    Args:
        lang: 指定语言，如 'zh_CN', 'en_US'。如果为 None，则自动检测系统语言。
    """
    global _translator, _current_lang

    # 语言映射
    lang_map = {
        'zh': 'zh_CN',
        'zh_CN': 'zh_CN',
        'en': 'en_US',
        'en_US': 'en_US',
    }

    # 如果未指定语言，自动检测
    if lang is None:
        # 尝试从环境变量获取
        lang = os.environ.get('LANGUAGE') or os.environ.get('LANG') or ''

        # 提取语言代码
        if lang:
            lang_code = lang.split('.')[0].lower()
            lang = lang_map.get(lang_code, 'zh_CN')
        else:
            # 尝试系统 locale
            try:
                system_lang = locale.getdefaultlocale()[0]
                if system_lang:
                    lang = lang_map.get(system_lang.lower(), 'zh_CN')
                else:
                    lang = 'zh_CN'
            except:
                lang = 'zh_CN'

    _current_lang = lang

    # 设置 locale 路径
    locale_dir = _get_project_root() / 'i18n' / 'locale'

    try:
        _translator = gettext.translation(
            'messages',
            localedir=str(locale_dir),
            languages=[lang],
            fallback=True  # 找不到时回退到 msgid (英文原文)
        )
    except Exception as e:
        print(f"Warning: Failed to load translation for {lang}: {e}")
        _translator = gettext.NullTranslations()

    # 安装 _ 函数到内置命名空间
    _translator.install()

    return lang


def _(s):
    """
    翻译函数

    Args:
        s: 要翻译的字符串

    Returns:
        翻译后的字符串
    """
    global _translator
    if _translator is None:
        init_i18n()
    return _translator.gettext(s)


def set_language(lang):
    """
    动态切换语言

    Args:
        lang: 语言代码，如 'zh_CN', 'en_US'
    """
    init_i18n(lang)


def get_current_language():
    """获取当前语言"""
    return _current_lang


def get_available_languages():
    """获取可用的语言列表"""
    return ['zh_CN', 'en_US']


def get_language_name(lang_code):
    """获取语言代码对应的显示名称"""
    names = {
        'zh_CN': '简体中文',
        'en_US': 'English',
    }
    return names.get(lang_code, lang_code)
