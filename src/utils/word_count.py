"""
工具函数集合
"""
import re


_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_EN_WORD_PATTERN = re.compile(r"[a-zA-Z]+")
_DIGIT_PATTERN = re.compile(r"[0-9０-９]")


def count_story_words(text: str) -> int:
    """
    统一字数统计（中文小说场景）
    规则：
    - 中文字符每个算1字
    - 英文单词每个算1字
    - 数字每个算1字
    - 标点符号不计入
    """
    chinese = len(_CJK_PATTERN.findall(text))
    english_words = len(_EN_WORD_PATTERN.findall(text))
    numbers = len(_DIGIT_PATTERN.findall(text))

    return chinese + english_words + numbers


def count_chinese_words(text: str) -> int:
    """兼容旧命名。"""
    return count_story_words(text)


def count_words_detail(text: str) -> dict:
    """
    详细字数统计
    """
    chinese = len(_CJK_PATTERN.findall(text))
    english_words = len(_EN_WORD_PATTERN.findall(text))
    numbers = len(_DIGIT_PATTERN.findall(text))

    return {
        'total': chinese + english_words + numbers,
        'chinese': chinese,
        'english_words': english_words,
        'numbers': numbers,
        'characters': len(text)  # 总字符数（含标点）
    }
