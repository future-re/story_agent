"""
工具函数集合
"""
import re


def count_chinese_words(text: str) -> int:
    """
    统计中文字数
    规则：
    - 中文字符每个算1字
    - 英文单词每个算1字
    - 数字每个算1字
    - 标点符号不计入
    """
    # 中文字符
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    
    # 英文单词
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    
    # 数字
    numbers = len(re.findall(r'\d+', text))
    
    return chinese + english_words + numbers


def count_words_detail(text: str) -> dict:
    """
    详细字数统计
    """
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    numbers = len(re.findall(r'\d+', text))
    
    return {
        'total': chinese + english_words + numbers,
        'chinese': chinese,
        'english_words': english_words,
        'numbers': numbers,
        'characters': len(text)  # 总字符数（含标点）
    }
