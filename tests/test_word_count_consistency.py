import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from storage.manager import StorageManager
from utils.word_count import count_story_words, count_words_detail


def test_count_story_words_digits_are_per_char():
    text = "第12章 abc ９８7"
    detail = count_words_detail(text)

    # 中文: 第 章 => 2
    assert detail["chinese"] == 2
    # 英文单词: abc => 1
    assert detail["english_words"] == 1
    # 数字按字符: 1,2,９,８,7 => 5
    assert detail["numbers"] == 5
    assert detail["total"] == 8
    assert count_story_words(text) == 8


def test_project_info_uses_same_metric_as_generation():
    with tempfile.TemporaryDirectory() as tmp:
        storage = StorageManager(base_dir=tmp)
        project = "test_project"
        chapter_body = "他抬手一按，阴符亮起。第12次呼吸后，门开了。"
        storage.save_chapter(project, 1, "试章", chapter_body)

        info = storage.get_project_info(project)
        # total_words 应只统计正文，不受 save_chapter 自动标题影响
        assert info["total_words"] == count_story_words(chapter_body)
