# Story Agent 📚

AI 驱动的小说创作助手，帮助你从点子到完整小说。

## 功能特点

- 🎯 **大纲生成** - 从点子生成完整大纲，或从已有章节续写
- 🧱 **五阶段流程** - 粗纲(JSON) → 细纲(JSON+Markdown) → 世界状态 → 角色初始化
- 🎭 **角色系统** - 创建有记忆和人格的角色 Agent
- ✍️ **章节创作** - AI 辅助生成章节正文
- 🧠 **双速思考** - `auto/fast/deep` 思考模式，支持缓存复用
- 🧩 **工具+技能架构** - 核心仅保留 `read/edit` 工具，写作策略由 `skills/writing-skill` 驱动
- 🧭 **技能路由** - 自动在 `outline-skill / continuation-skill / rewrite-skill` 之间切换
- 📚 **语料学习** - 可分析 10-20 本小说前 100 章并回写 skill 技巧库
- 💾 **本地存储** - 自动保存为 txt 文件
- 🔄 **多模式支持** - 从零开始 / 从章节反推 / 从大纲扩展

## 快速开始

### 安装

```bash
# 克隆项目
git clone <repo_url>
cd story_agent

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 安装（开发模式）
pip install -e .

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 DEEPSEEK_API_KEY
```

### 使用方式

#### 交互模式（推荐新手）

```bash
story-agent
```

#### Web 交互模式（Chainlit + LangGraph）

```bash
# 安装交互增强依赖（如果尚未安装）
pip install ".[interactive]"

# 启动 Web 界面
story-agent web --host 0.0.0.0 --port 8000
```

Web 模式核心命令：

- `/new <项目名>`：创建/切换项目
- `/outline <创意点子>`：生成并保存大纲
- `/write`：执行写作准备（生成规划）
- `/approve`：确认当前规划并写入章节
- `/reject`：放弃当前规划
- `/status`、`/export`：查看状态和导出

#### 技能学习命令（从小说语料提炼技巧）

```bash
# 从小说语料目录学习（每本最多前100章）
story-agent skills mine \
  --source /path/to/novels \
  --novels 20 \
  --chapters 100
```

语料目录支持两种形式：
- 每本小说一个子目录，目录下按章节放 `txt/md` 文件
- 每本小说一个 `txt/md` 文件（按“第X章 / Chapter X”自动切章）

分析结果会写入：
- `skills/outline-skill/references/learned_techniques.md`
- `skills/continuation-skill/references/learned_techniques.md`
- `skills/rewrite-skill/references/learned_techniques.md`

#### 命令行模式

```bash
# 创建新项目并生成大纲
story-agent new "代码修仙" --idea "程序员穿越修仙界用代码画符"

# 创建新项目并执行五阶段初始化
story-agent new "代码修仙" --idea "程序员穿越修仙界用代码画符" --pipeline --chapters 12

# 查看项目状态
story-agent status "代码修仙"

# 写章节
story-agent write "代码修仙" 1 "初入青云" --context "主角穿越到青云宗"

# 导入已有章节
story-agent import "代码修仙" --dir /path/to/chapters/

# 从已有章节生成后续大纲
story-agent outline "代码修仙" continue --count 10

# 扩展大纲
story-agent outline "代码修仙" expand --request "细化第一卷"

# 对已有项目执行五阶段初始化
story-agent outline "代码修仙" pipeline --idea "程序员穿越修仙界用代码画符" --count 12

# 导出完整小说
story-agent export "代码修仙"
```

#### Python API

```python
from main import StoryAgent

agent = StoryAgent("我的小说")

# 生成大纲
agent.create_outline("你的创意点子")

# 添加角色
agent.add_character("林夜", role="protagonist", 
                    personality="沉稳理性", desire="寻找回家的路")

# 写章节
agent.write_chapter(1, "初入青云", "主角穿越到青云宗")

# 导出
agent.export()
```

## 项目结构

```
src/
├── agents/       # 智能体（角色、叙述者、规划器）
├── simulation/   # 仿真（世界状态、事件、记忆）
├── generation/   # 生成（大纲、章节、Prompt）
│   └── services/ # 生成流程服务层（pipeline/prepare/write/update）
├── tools/        # read/edit/thinking 工具层（核心能力）
├── skills_runtime/ # 技能运行时（路由、注入、语料学习）
├── models/       # AI 模型适配
├── storage/      # 本地存储
├── schema/       # 数据模型
├── main.py       # 统一入口
├── cli.py        # 命令行工具
└── config.py     # 配置
```

## 输出目录

生成的内容存储在 `output/` 目录：

```
output/
└── 项目名/
    ├── 大纲.txt
    ├── story_blueprint.json
    ├── detailed_outline.json
    ├── world_state.json
    ├── chapters/
    │   ├── 001_第一章标题.txt
    │   └── ...
    └── characters/
        └── 角色名.txt
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `python src/cli.py` | 交互模式 |
| `story-agent web` | Web 交互模式（Chainlit） |
| `new <名称> [--idea]` | 创建项目 |
| `outline <项目> create --idea` | 从点子生成大纲 |
| `outline <项目> continue` | 从章节续写大纲 |
| `outline <项目> expand --request` | 扩展大纲 |
| `outline <项目> pipeline --idea` | 执行五阶段初始化 |
| `write <项目> <章节号> <标题>` | 写章节 |
| `import <项目> --dir/--file` | 导入已有章节 |
| `skills mine --source <目录>` | 分析小说语料并生成技能技巧库 |
| `status <项目>` | 查看状态 |
| `export <项目>` | 导出小说 |

## Thinking 配置

可通过环境变量调优思考速度与质量平衡：

```bash
# 思考模型（示例：GLM）
STORY_THINKING_MODEL=glm-4-plus

# GLM 官方思考参数（建议先 disabled，避免长时间只思考不出正文）
GLM_THINKING_TYPE=disabled
GLM_MAX_TOKENS=8192

# 思考模式：auto / fast / deep
STORY_THINKING_MODE=auto

# ===== 技能驱动写作 =====
# 是否启用写作技能注入（建议开启）
STORY_ENABLE_SKILL_WRITING=true

# 技能目录（默认 ./skills）
STORY_SKILLS_DIR=./skills

# 通用回退技能名（默认 writing-skill）
STORY_WRITING_SKILL_NAME=writing-skill

# 三类专项技能名（默认如下）
STORY_OUTLINE_SKILL_NAME=outline-skill
STORY_CONTINUATION_SKILL_NAME=continuation-skill
STORY_REWRITE_SKILL_NAME=rewrite-skill

# 思考缓存大小（LRU）
STORY_THINKING_CACHE_SIZE=20

# 思考上下文截断长度
STORY_THINKING_PREVIOUS_CONTEXT_CHARS=3000
STORY_THINKING_WORLD_CONTEXT_CHARS=2500

# 低质量规划自动重试修复次数
STORY_THINKING_QUALITY_RETRY=1

# 分镜最少镜头数（质量闸门）
STORY_THINKING_DEEP_MIN_SHOTS=4
STORY_THINKING_FAST_MIN_SHOTS=3
```

## License

MIT
