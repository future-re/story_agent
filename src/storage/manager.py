"""
存储管理器

负责将生成的小说内容持久化存储到本地文件。
"""
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any


class StorageManager:
    """存储管理器 - 管理小说内容的本地存储"""
    
    def __init__(self, base_dir: str = "./output"):
        """
        初始化存储管理器
        :param base_dir: 基础输出目录
        """
        self.base_dir = base_dir
        self._ensure_dir(base_dir)
    
    def _ensure_dir(self, path: str):
        """确保目录存在"""
        if not os.path.exists(path):
            os.makedirs(path)
    
    def get_project_dir(self, project_name: str) -> str:
        """获取项目目录。"""
        # 清理项目名称，移除非法字符
        safe_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_name = safe_name.replace(' ', '_') or "unnamed_project"
        project_dir = os.path.join(self.base_dir, safe_name)
        self._ensure_dir(project_dir)
        return project_dir

    def _get_project_dir(self, project_name: str) -> str:
        """兼容旧接口。"""
        return self.get_project_dir(project_name)
    
    def save_chapter(self, project_name: str, chapter_index: int, 
                     title: str, content: str) -> str:
        """
        保存章节内容为 txt 文件
        :param project_name: 项目/小说名称
        :param chapter_index: 章节序号
        :param title: 章节标题
        :param content: 章节正文
        :return: 保存的文件路径
        """
        project_dir = self.get_project_dir(project_name)
        chapters_dir = os.path.join(project_dir, "chapters")
        self._ensure_dir(chapters_dir)
        
        # 文件名格式：001_章节标题.txt
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-', '，', '。')).strip()
        filename = f"{chapter_index:03d}_{safe_title or '未命名'}.txt"
        filepath = os.path.join(chapters_dir, filename)
        
        # 写入内容
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"第{chapter_index}章 {title}\n")
            f.write("=" * 40 + "\n\n")
            f.write(content)
        
        return filepath
    
    def save_outline(self, project_name: str, outline_content: str) -> str:
        """
        保存大纲
        :param project_name: 项目名称
        :param outline_content: 大纲内容
        :return: 文件路径
        """
        project_dir = self.get_project_dir(project_name)
        filepath = os.path.join(project_dir, "大纲.txt")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"《{project_name}》大纲\n")
            f.write("=" * 40 + "\n\n")
            f.write(outline_content)
        
        return filepath
    
    def save_character_profile(self, project_name: str, character_name: str,
                               profile: Dict[str, Any]) -> str:
        """
        保存角色档案
        :param project_name: 项目名称
        :param character_name: 角色名称
        :param profile: 角色信息
        :return: 文件路径
        """
        project_dir = self.get_project_dir(project_name)
        chars_dir = os.path.join(project_dir, "characters")
        self._ensure_dir(chars_dir)
        
        filepath = os.path.join(chars_dir, f"{character_name}.txt")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"角色档案：{character_name}\n")
            f.write("=" * 40 + "\n\n")
            for key, value in profile.items():
                f.write(f"【{key}】\n{value}\n\n")
        
        return filepath
    
    def save_world_state(self, project_name: str, state_data: Dict[str, Any]) -> str:
        """
        保存世界状态（用于断点续写）
        :param project_name: 项目名称
        :param state_data: 状态数据
        :return: 文件路径
        """
        project_dir = self.get_project_dir(project_name)
        filepath = os.path.join(project_dir, "world_state.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2, default=str)
        
        return filepath
    
    def load_world_state(self, project_name: str) -> Optional[Dict[str, Any]]:
        """
        加载世界状态
        :param project_name: 项目名称
        :return: 状态数据，不存在则返回 None
        """
        project_dir = self.get_project_dir(project_name)
        filepath = os.path.join(project_dir, "world_state.json")
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def export_full_novel(self, project_name: str) -> str:
        """
        导出完整小说（合并所有章节）
        :param project_name: 项目名称
        :return: 导出文件路径
        """
        project_dir = self.get_project_dir(project_name)
        chapters_dir = os.path.join(project_dir, "chapters")
        
        if not os.path.exists(chapters_dir):
            raise FileNotFoundError(f"章节目录不存在: {chapters_dir}")
        
        # 获取所有章节文件并排序
        chapter_files = sorted([f for f in os.listdir(chapters_dir) if f.endswith('.txt')])
        
        # 合并内容
        full_content = f"《{project_name}》\n\n"
        full_content += "=" * 50 + "\n\n"
        
        for chapter_file in chapter_files:
            chapter_path = os.path.join(chapters_dir, chapter_file)
            with open(chapter_path, 'r', encoding='utf-8') as f:
                full_content += f.read()
                full_content += "\n\n" + "-" * 40 + "\n\n"
        
        # 保存完整小说
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = os.path.join(project_dir, f"{project_name}_完整版_{timestamp}.txt")
        
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write(full_content)
        
        return export_path
    
    def list_chapters(self, project_name: str) -> List[str]:
        """
        列出所有章节
        :param project_name: 项目名称
        :return: 章节文件名列表
        """
        project_dir = self.get_project_dir(project_name)
        chapters_dir = os.path.join(project_dir, "chapters")
        
        if not os.path.exists(chapters_dir):
            return []
        
        return sorted([f for f in os.listdir(chapters_dir) if f.endswith('.txt')])
    
    def get_project_info(self, project_name: str) -> Dict[str, Any]:
        """
        获取项目信息
        :param project_name: 项目名称
        :return: 项目信息
        """
        project_dir = self.get_project_dir(project_name)
        chapters = self.list_chapters(project_name)
        
        # 统计总字数
        total_words = 0
        for chapter_file in chapters:
            chapter_path = os.path.join(project_dir, "chapters", chapter_file)
            with open(chapter_path, 'r', encoding='utf-8') as f:
                total_words += len(f.read())
        
        return {
            "project_name": project_name,
            "project_dir": project_dir,
            "chapter_count": len(chapters),
            "total_words": total_words,
            "chapters": chapters
        }
