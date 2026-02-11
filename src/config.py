"""
配置管理
"""
import os
from dataclasses import dataclass
from typing import Optional


def _env_bool(name: str, default: bool) -> bool:
    """读取布尔环境变量，非法值回退默认值。"""
    value = os.getenv(name)
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


def _env_int(name: str, default: int) -> int:
    """读取整数环境变量，非法值回退默认值。"""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


@dataclass
class Config:
    """全局配置"""
    
    # AI 模型
    model_name: str = "deepseek"
    api_key: Optional[str] = None
    
    # Kimi API (Moonshot)
    moonshot_api_key: Optional[str] = None
    
    # 思考模型 (用于剧情分析)
    thinking_model: str = "glm-4-plus"
    enable_plot_thinking: bool = True
    thinking_mode: str = "auto"  # auto/fast/deep
    thinking_cache_size: int = 20
    thinking_previous_context_chars: int = 3000
    thinking_world_context_chars: int = 2500
    thinking_quality_retry: int = 1
    thinking_deep_min_storyboard_shots: int = 4
    thinking_fast_min_storyboard_shots: int = 3
    
    # 存储
    output_dir: str = "./output"
    
    # 生成参数
    default_chapter_words: int = 3000
    default_outline_chapters: int = 10
    
    @classmethod
    def from_env(cls) -> 'Config':
        """从环境变量加载配置"""
        return cls(
            model_name=os.getenv("STORY_MODEL", cls.model_name),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            moonshot_api_key=os.getenv("MOONSHOT_API_KEY"),
            thinking_model=os.getenv("STORY_THINKING_MODEL", cls.thinking_model),
            enable_plot_thinking=_env_bool("STORY_ENABLE_PLOT_THINKING", cls.enable_plot_thinking),
            thinking_mode=os.getenv("STORY_THINKING_MODE", cls.thinking_mode),
            thinking_cache_size=_env_int("STORY_THINKING_CACHE_SIZE", cls.thinking_cache_size),
            thinking_previous_context_chars=_env_int(
                "STORY_THINKING_PREVIOUS_CONTEXT_CHARS",
                cls.thinking_previous_context_chars,
            ),
            thinking_world_context_chars=_env_int(
                "STORY_THINKING_WORLD_CONTEXT_CHARS",
                cls.thinking_world_context_chars,
            ),
            thinking_quality_retry=_env_int(
                "STORY_THINKING_QUALITY_RETRY",
                cls.thinking_quality_retry,
            ),
            thinking_deep_min_storyboard_shots=_env_int(
                "STORY_THINKING_DEEP_MIN_SHOTS",
                cls.thinking_deep_min_storyboard_shots,
            ),
            thinking_fast_min_storyboard_shots=_env_int(
                "STORY_THINKING_FAST_MIN_SHOTS",
                cls.thinking_fast_min_storyboard_shots,
            ),
            output_dir=os.getenv("STORY_OUTPUT_DIR", cls.output_dir),
            default_chapter_words=_env_int("STORY_DEFAULT_CHAPTER_WORDS", cls.default_chapter_words),
            default_outline_chapters=_env_int("STORY_DEFAULT_OUTLINE_CHAPTERS", cls.default_outline_chapters),
        )



# 全局配置实例
config = Config.from_env()
