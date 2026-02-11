"""
Prompt 模板集合
"""

# ==================== 大纲生成 ====================

PROMPT_FROM_IDEA = """你是一位资深网络小说总编。请根据以下创意点子，生成一份完整的大纲（偏编辑视角，可读性优先）。

【创意点子】
{idea}

请按以下格式输出（必须包含全部模块）：

## 一、人物设定
- 姓名 / 性别 / 身份 / 年龄
- 外貌特征
- 性格与气质
- 角色渴望与短期目标

## 二、核心事件
- 主人公核心要做的事（发财/升官/复仇/争霸/恋爱/结婚等）
- 事件意义（为什么必须做）
- 主要困难（资源、敌人、规则、时限）

## 三、冲突与矛盾
- 冲突来源（人与人/人与组织/人与规则/人与自我）
- 阶段性结果（成功/失败/代价）
- 解决路径（如何化解或转移矛盾）

## 四、情节发展
- 起因
- 发展
- 转折
- 高潮
- 结局

## 五、场景公式（地点+人物+事件+结果）
- 场景1：
- 场景2：
- 场景3：
"""

PROMPT_FROM_CHAPTERS = """你是一位资深网络小说总编。以下是已写好的章节内容。
请分析故事走向，并生成后续章节大纲。

【已完成章节】
{chapters_content}

【当前进度】
已完成 {chapter_count} 章，约 {word_count} 字。

请输出：

## 一、已有内容分析
- 当前主线进度：
- 已埋伏笔：
- 人物关系现状：

## 二、后续章节大纲
（从第 {next_chapter} 章开始规划 {plan_count} 章）

### 第X章：章节标题
- 核心事件：
- 涉及人物：
- 爽点/钩子：

## 三、长线规划建议
"""

PROMPT_FROM_OUTLINE = """你是一位资深网络小说总编。请根据要求扩展大纲。

【现有大纲】
{existing_outline}

【扩展要求】
{expansion_request}

请输出扩展后的大纲：
"""

# ==================== 章节生成 ====================

PROMPT_CHAPTER_OUTLINE = """请针对本章节规划细纲：
- 角色渴望：主角想要什么
- 遇到障碍：遇到什么阻碍
- 核心冲突：谁与谁对碰
- 行动：暗中/明面动作
- 爽点：如何给读者正反馈

本章概况：{chapter_context}
"""

PROMPT_CHAPTER_CONTENT = """根据以下细纲撰写章节正文（约3000字）：

【章节标题】{title}
【细纲】
{outline}

【前情提要】
{previous_summary}

请开始创作：
"""

PROMPT_REFINE_VOLUME = """将分卷概述扩展为详细章节大纲。

【故事背景】{story_context}
【分卷】{volume_title}
【概述】{volume_summary}
【目标】约 {chapter_count} 章，{word_count} 字

请规划章节大纲：
"""


# ==================== 结构化五阶段管线 ====================

PROMPT_STRUCTURED_BLUEPRINT = """你是资深中文网文策划编辑。请基于创意点子，输出“结构化粗纲 JSON”。

【创意点子】
{idea}

输出要求：
1. 只输出 JSON，不要附加解释。
2. 字段必须完整；无法确定时给出合理默认值，不要留空字符串。
3. `scene_formula` 必须严格使用“地点+人物+事件+结果”。

JSON 结构：
{{
  "title_candidate": "书名候选",
  "genre": "题材",
  "target_audience": "目标读者",
  "character_setup": [
    {{
      "name": "角色名",
      "gender": "性别",
      "identity": "身份",
      "age": "年龄",
      "appearance": "外貌",
      "personality_temperament": "性格与气质",
      "desire": "核心欲望",
      "short_term_goal": "短期目标"
    }}
  ],
  "core_event": {{
    "event_goal": "主人公核心要做的事",
    "meaning": "事件意义",
    "difficulties": ["困难1", "困难2", "困难3"]
  }},
  "conflicts": [
    {{
      "conflict": "冲突内容",
      "phase_result": "阶段结果",
      "resolution_path": "解决路径"
    }}
  ],
  "plot_development": {{
    "cause": "起因",
    "development": "发展",
    "twist": "转折",
    "climax": "高潮",
    "ending": "结局"
  }},
  "scene_formula": [
    {{
      "location": "地点",
      "characters": ["人物A", "人物B"],
      "event": "事件",
      "result": "结果"
    }}
  ]
}}
"""

PROMPT_DETAILED_OUTLINE_FROM_BLUEPRINT = """你是小说拆解编辑。请把结构化粗纲拆成“可写作细纲 JSON”。

【结构化粗纲 JSON】
{blueprint_json}

【章节目标】
总章节数约 {chapter_count} 章。

输出要求：
1. 只输出 JSON，不要解释。
2. `outline_markdown` 必须为可读的 Markdown，并遵循如下模式：
   - 卷标题：`## 卷X：标题（第a-b章）`
   - 阶段标题：`### 阶段名（第a-b章）`
   - 章节条目：`- **第n章**: 章节目标`
3. 每章都给 `scene_formula`（地点+人物+事件+结果）。

JSON 结构：
{{
  "summary": "整体细纲摘要",
  "volumes": [
    {{
      "title": "卷标题",
      "start_chapter": 1,
      "end_chapter": 10,
      "phase": "阶段名称",
      "volume_goal": "本卷目标",
      "chapter_beats": [
        {{
          "chapter": 1,
          "title": "章节标题",
          "goal": "本章目标",
          "conflict": "本章冲突",
          "hook": "章末钩子",
          "scene_formula": [
            {{
              "location": "地点",
              "characters": ["人物A"],
              "event": "事件",
              "result": "结果"
            }}
          ]
        }}
      ]
    }}
  ],
  "outline_markdown": "完整 Markdown 大纲文本"
}}
"""

PROMPT_WORLD_STATE_FROM_OUTLINE = """你是长篇小说世界状态建模器。请根据结构化粗纲和细纲，初始化世界状态 JSON。

【结构化粗纲 JSON】
{blueprint_json}

【细纲 JSON】
{detailed_outline_json}

【可选章节样本】
{chapter_samples}

输出要求：
1. 只输出 JSON，不要解释。
2. 角色要区分 `appeared`（是否已出场）。
3. 角色必须包含：等级、技能、性格、物品、当前目标。
4. 主角必须包含可执行的“按性格行动”倾向（用于后续章节推演）。

JSON 结构：
{{
  "characters": [
    {{
      "name": "角色名",
      "role": "主角/反派/配角",
      "appeared": false,
      "personality": "性格",
      "level": "体系·大境界·小阶段",
      "abilities": ["技能1"],
      "items": ["物品1"],
      "current_goal": "当前目标",
      "action_tendency": "该角色会如何按性格行动",
      "relationships": [
        {{
          "target": "目标角色",
          "relation_type": "盟友/敌对/师徒/亲属/陌生",
          "description": "关系说明"
        }}
      ],
      "current_status": [],
      "action_history": [],
      "memory_short_term": [],
      "memory_long_term": []
    }}
  ],
  "world": {{
    "environment": "世界环境",
    "power_system": "力量体系简述",
    "factions": ["势力1"],
    "known_methods": ["功法1"],
    "known_artifacts": ["法宝1"],
    "scene_rules": ["场景运行规则1"]
  }},
  "locations": [
    {{
      "name": "地点",
      "description": "描述"
    }}
  ],
  "plot_history": [],
  "timeline": [],
  "faction_history": [],
  "world_state_notes": []
}}
"""
