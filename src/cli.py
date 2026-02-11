#!/usr/bin/env python3
"""
Story Agent CLI - 命令行交互入口
"""
import argparse
import sys
import os
import shutil
import subprocess

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 添加 src 到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import StoryAgent


def cmd_new(args):
    """创建新项目"""
    agent = StoryAgent(args.name, args.output)
    print(f"✨ 创建项目: {args.name}")
    
    if args.idea:
        if args.pipeline:
            print("🧱 执行五阶段初始化中（粗纲→细纲→世界→角色）...")
            result = agent.create_story_pipeline(args.idea, chapter_count=args.chapters)
            outline_preview = result.get("detailed_outline", {}).get("outline_markdown", "")
            print("\n" + outline_preview[:500] + "...\n")
            print(f"✅ 已生成并保存：")
            print(f"   - {args.output}/{args.name}/story_blueprint.json")
            print(f"   - {args.output}/{args.name}/detailed_outline.json")
            print(f"   - {args.output}/{args.name}/大纲.txt")
            print(f"   - {args.output}/{args.name}/world_state.json")
        else:
            print("📝 生成大纲中...")
            outline = agent.create_outline(args.idea)
            print("\n" + outline[:500] + "...\n")
            print(f"✅ 大纲已保存到 {args.output}/{args.name}/大纲.txt")


def cmd_outline(args):
    """大纲操作"""
    agent = StoryAgent(args.project, args.output)
    
    if args.action == "create":
        if not args.idea:
            print("❌ 请提供 --idea 参数")
            return
        outline = agent.create_outline(args.idea)
        print(outline)
    
    elif args.action == "expand":
        if not args.request:
            print("❌ 请提供 --request 参数")
            return
        outline = agent.expand_outline(args.request)
        print(outline)
    
    elif args.action == "continue":
        outline = agent.continue_outline(args.count)
        print(outline)
    
    elif args.action == "pipeline":
        if not args.idea:
            print("❌ 请提供 --idea 参数")
            return
        result = agent.create_story_pipeline(args.idea, chapter_count=args.count)
        outline_preview = result.get("detailed_outline", {}).get("outline_markdown", "")
        world_char_count = len(result.get("world_state", {}).get("characters", []))
        print("✅ 五阶段流程完成：")
        print(f"- 结构化粗纲: {args.output}/{args.project}/story_blueprint.json")
        print(f"- 结构化细纲: {args.output}/{args.project}/detailed_outline.json")
        print(f"- 文本大纲: {args.output}/{args.project}/大纲.txt")
        print(f"- 世界状态: {args.output}/{args.project}/world_state.json")
        print(f"- 角色数: {world_char_count}")
        if outline_preview:
            print("\n细纲预览：\n")
            print(outline_preview[:1200] + ("..." if len(outline_preview) > 1200 else ""))


def cmd_write(args):
    """写章节"""
    agent = StoryAgent(args.project, args.output)
    
    print(f"✍️ 正在生成第 {args.chapter} 章: {args.title}")
    content = agent.write_chapter(args.chapter, args.title, args.context, args.previous or "")
    
    print(f"\n{content[:300]}...")
    print(f"\n✅ 已保存")


def cmd_status(args):
    """查看项目状态"""
    agent = StoryAgent(args.project, args.output)
    info = agent.status()
    
    print(f"📚 项目: {info['project_name']}")
    print(f"📖 章节数: {info['chapter_count']}")
    print(f"📝 总字数: {info['total_words']}")
    
    if info.get('chapters'):
        print("\n已完成章节:")
        for ch in info['chapters']:
            print(f"  - {ch}")


def cmd_export(args):
    """导出完整小说"""
    agent = StoryAgent(args.project, args.output)
    path = agent.export()
    print(f"✅ 小说已导出: {path}")


def cmd_import(args):
    """导入已有章节"""
    from storage import StorageManager
    
    storage = StorageManager(args.output)
    
    if args.file:
        # 导入单个文件
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        path = storage.save_chapter(args.project, args.chapter, args.title or f"第{args.chapter}章", content)
        print(f"✅ 已导入: {path}")
    
    elif args.dir:
        # 批量导入目录下的所有 txt 文件
        import os
        files = sorted([f for f in os.listdir(args.dir) if f.endswith('.txt')])
        
        for i, filename in enumerate(files, 1):
            filepath = os.path.join(args.dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 从文件名提取标题
            title = os.path.splitext(filename)[0]
            path = storage.save_chapter(args.project, i, title, content)
            print(f"✅ [{i}] {filename} -> {path}")
        
        print(f"\n共导入 {len(files)} 章")
    
    # 提示用户可以生成后续大纲
    print(f"\n💡 现在可以运行: story-agent outline {args.project} continue")
    print(f"   来根据已有章节生成后续大纲")


def cmd_web(args):
    """启动 Chainlit Web 交互模式。"""
    chainlit_bin = shutil.which("chainlit")
    if chainlit_bin is None:
        print("❌ 未检测到 chainlit 命令。请先安装：pip install chainlit")
        return

    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chainlit_app.py")
    command = [chainlit_bin, "run", app_path]
    if args.watch:
        command.append("-w")
    if args.host:
        command.extend(["--host", args.host])
    if args.port:
        command.extend(["--port", str(args.port)])

    print("🌐 启动 Web 交互模式中...")
    print("   访问地址将由 Chainlit 输出。")
    subprocess.run(command, check=False)


def cmd_interactive(args):
    """交互模式 - 连续对话"""
    from prompt_toolkit import prompt
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.completion import Completer, Completion
    from models import get_client
    from storage import StorageManager
    from generation import OutlineGenerator, ChapterGenerator
    
    class StoryCompleter(Completer):
        """自定义补全器，支持命令描述和项目选择"""
        
        def __init__(self, storage: StorageManager):
            self.storage = storage
            self.commands = {
                '/new': '创建/切换项目',
                '/list': '列出所有项目',
                '/init': '从大纲初始化角色和世界',
                '/save': '保存AI回复为大纲',
                '/outline': '根据对话生成大纲',
                '/expand': '扩展当前大纲',
                '/chars': '查看角色列表',
                '/world': '查看世界状态',
                '/style': '管理风格参考（导入/查看）',
                '/write': '自动续写（<3k追加，>=3k新章）',
                '/status': '查看项目状态',
                '/export': '导出完整小说',
                '/clear': '清空对话历史',
                '/help': '显示帮助',
                '/quit': '退出程序',
            }
        
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            
            # 命令补全
            if text.startswith('/'):
                word = text.split()[0] if text else ''
                for cmd, desc in self.commands.items():
                    if cmd.startswith(word):
                        yield Completion(
                            cmd, 
                            start_position=-len(word),
                            display_meta=desc
                        )
            
            # /new 后补全项目名
            if text.startswith('/new ') or text.startswith('/list'):
                projects = self._get_projects()
                prefix = text.split()[-1] if len(text.split()) > 1 else ''
                for proj in projects:
                    if proj.startswith(prefix) or not prefix:
                        yield Completion(
                            proj,
                            start_position=-len(prefix),
                            display_meta='已有项目'
                        )
        
        def _get_projects(self):
            """获取所有项目"""
            import os
            if not os.path.exists(self.storage.base_dir):
                return []
            return [d for d in os.listdir(self.storage.base_dir) 
                    if os.path.isdir(os.path.join(self.storage.base_dir, d))]
    
    storage = StorageManager(args.output)
    completer = StoryCompleter(storage)
    
    print("=" * 50)
    print("    📚 Story Agent - 连续对话模式")
    print("=" * 50)
    print("\n输入 / 按 Tab 选择命令（带说明）")
    print("直接输入文字与 AI 对话")
    print("-" * 50)
    
    ai = get_client()
    project_name = None
    history = []
    input_history = InMemoryHistory()
    
    system_prompt = """你是一位资深网络小说编辑和创作顾问。你的任务是：
1. 帮助用户构思故事点子、人物设定、世界观
2. 讨论剧情走向、冲突设计、爽点安排
3. 提供专业的网文创作建议
请用简洁专业的语言回答。"""
    
    while True:
        try:
            prompt_text = f"\n[{project_name}] 你: " if project_name else "\n你: "
            user_input = prompt(prompt_text, history=input_history, completer=completer).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见!")
            break
        
        if not user_input:
            continue
        
        # 处理命令
        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=2)
            cmd = parts[0].lower()
            
            if cmd == "/quit" or cmd == "/exit":
                print("👋 再见!")
                break
            
            elif cmd == "/" or cmd == "/help":
                print("\n命令列表:")
                print("  /new <项目名>        创建或切换项目")
                print("  /outline             从对话生成大纲")
                print("  /expand <要求>       扩展已有大纲")
                print("  /write <章节号> <标题>  生成章节")
                print("  /status              查看项目状态")
                print("  /export              导出完整小说")
                print("  /clear               清空对话历史")
                print("  /quit                退出")
            
            elif cmd == "/new":
                if len(parts) > 1:
                    project_name = parts[1]
                    print(f"✨ 当前项目: {project_name}")
                else:
                    # 显示项目列表供选择
                    projects = completer._get_projects()
                    if projects:
                        print("\n📚 已有项目:")
                        for i, p in enumerate(projects, 1):
                            print(f"  {i}. {p}")
                        print("\n用法: /new 项目名")
                    else:
                        print("❌ 暂无项目，请指定新项目名: /new 项目名")
            
            elif cmd == "/list":
                projects = completer._get_projects()
                if projects:
                    print("\n📚 项目列表:")
                    for i, p in enumerate(projects, 1):
                        info = storage.get_project_info(p)
                        print(f"  {i}. {p}  ({info['chapter_count']}章, {info['total_words']}字)")
                else:
                    print("暂无项目")
            
            elif cmd == "/outline":
                if not project_name:
                    print("❌ 请先创建项目: /new 项目名")
                    continue
                
                # 从对话历史提取创意
                context = "\n".join([f"{m['role']}: {m['content']}" for m in history[-10:]])
                if not context:
                    print("❌ 请先和我聊聊你的创意点子")
                    continue
                
                print("\n📝 正在根据对话生成大纲...")
                gen = OutlineGenerator(ai, storage)
                prompt = f"根据以下对话内容，提取创意并生成完整小说大纲：\n\n{context}"
                outline = gen.from_idea(prompt, save_to=project_name)
                print(f"\n{outline}")
                print(f"\n✅ 大纲已保存")
            
            elif cmd == "/expand":
                if not project_name:
                    print("❌ 请先创建项目: /new 项目名")
                    continue
                request = parts[1] if len(parts) > 1 else "细化章节大纲"
                print(f"\n📝 扩展中...")
                gen = OutlineGenerator(ai, storage)
                try:
                    outline = gen.load_and_expand(project_name, request)
                    print(f"\n{outline}")
                except FileNotFoundError:
                    print("❌ 没有找到已保存的大纲，请先使用 /outline 生成")
            
            elif cmd == "/write":
                if not project_name:
                    print("❌ 请先创建项目: /new 项目名")
                    continue
                
                gen = ChapterGenerator(project_name, ai, storage)
                
                # 获取最新章节状态
                ch_num, ch_title, ch_content, ch_len = gen._get_latest_chapter()
                
                if ch_len < 3000 and ch_num > 0:
                    print(f"\n✍️ 续写第 {ch_num} 章《{ch_title}》(当前 {ch_len} 字)")
                else:
                    print(f"\n✍️ 开始新章节 第 {ch_num + 1} 章")
                print("=" * 50)
                
                # ===== 第一阶段：准备 + 思考 =====
                preparation = None
                try:
                    for output in gen.prepare_writing():
                        if isinstance(output, dict):
                            preparation = output
                        else:
                            print(output, end="", flush=True)
                except Exception as e:
                    print(f"\n❌ 思考阶段出错: {e}")
                    continue
                
                if not preparation:
                    print("⚠️ 准备失败")
                    continue
                
                thinking_plan = preparation.get("thinking_plan")
                
                # 调试：显示 thinking_plan 状态
                if thinking_plan:
                    print(f"\n[DEBUG] 思考规划已获取，包含字段: {list(thinking_plan.keys())}")
                else:
                    print(f"\n[DEBUG] thinking_plan 为空或 None")
                
                # ===== 第二阶段：展示规划并交互确认 =====
                if thinking_plan and gen.thinking_engine:
                    print("\n" + gen.thinking_engine.format_full_plan_display(thinking_plan))
                    
                    # 交互式确认循环
                    while True:
                        print("\n📋 规划确认：")
                        print("  [Y] 确认生成  [N] 放弃  [M] 修改规划")
                        choice = input("请选择: ").strip().lower()
                        
                        if choice == 'y':
                            # 确认，进入生成阶段
                            break
                        
                        elif choice == 'n':
                            print("🗑️ 已放弃")
                            thinking_plan = None  # 清空，跳过生成
                            break
                        
                        elif choice == 'm':
                            # 修改规划
                            print("\n请输入你的修改意见（直接描述想要的改动）：")
                            feedback = input("> ").strip()
                            
                            if feedback:
                                # 调用修改方法
                                new_plan = None
                                for output in gen.thinking_engine.refine_plan(thinking_plan, feedback):
                                    if isinstance(output, dict):
                                        new_plan = output
                                    else:
                                        print(output, end="", flush=True)
                                
                                if new_plan:
                                    thinking_plan = new_plan
                                    preparation["thinking_plan"] = new_plan
                                    # 重新显示修改后的规划
                                    print("\n" + gen.thinking_engine.format_full_plan_display(thinking_plan))
                else:
                    # 没有思考引擎或思考失败，直接确认
                    choice = input("\n⏩ 未启用剧情思考，直接生成？[Y/N]: ").strip().lower()
                    if choice != 'y':
                        print("🗑️ 已放弃")
                        continue
                
                # 用户放弃了
                if thinking_plan is None and gen.thinking_engine:
                    continue
                
                # ===== 第三阶段：生成内容 =====
                print("\n" + "=" * 50)
                print("✍️ 正在生成内容...")
                print("=" * 50 + "\n")
                
                while True:
                    full_content = ""
                    result = None
                    try:
                        for chunk in gen.generate_from_plan(preparation):
                            if isinstance(chunk, dict):
                                result = chunk
                            else:
                                print(chunk, end="", flush=True)
                                full_content += chunk
                    except Exception as e:
                        print(f"\n❌ 生成出错: {e}")
                        break
                    
                    print("\n" + "=" * 50)
                    
                    if not result:
                        print("⚠️ 未收到生成结果")
                        break

                    mode_text = "追加" if result['mode'] == 'append' else "新建"
                    print(f"✅ 生成完成 | 第{result['chapter']}章《{result['title']}》| 本次 +{result['added_words']} 字")
                    
                    # 确认提示
                    while True:
                        choice = input("\n💾 满意吗？[Y]保存 [N]放弃 [R]重试 [P]润色: ").strip().lower()
                        
                        if choice == 'y':
                            # 保存文件
                            storage.save_chapter(project_name, result['chapter'], result['title'], result['full_text'])
                            print(f"✅ 文件已保存 (总 {result['total_words']} 字)")
                            
                            # 更新世界状态
                            if result.get('new_content'):
                                for update_chunk in gen.update_world_state(result.get('new_content')):
                                    print(update_chunk, end="", flush=True)
                                print()
                            break
                        
                        elif choice == 'n':
                            print("🗑️ 已放弃本次生成")
                            break
                        
                        elif choice == 'p':
                            # 润色功能
                            if gen.thinking_engine:
                                print("\n" + "=" * 50)
                                refined_content = ""
                                try:
                                    for chunk in gen.thinking_engine.refine_chapter(
                                        chapter_content=result['full_text'],
                                        world_context=preparation.get('world_context', ''),
                                        style_ref=preparation.get('style_ref', ''),
                                        focus="风格优化和节奏调整"
                                    ):
                                        if chunk.startswith("✨"):
                                            print(chunk, end="", flush=True)
                                        elif len(chunk) > 100:  # 这是最终的完整润色内容
                                            refined_content = chunk
                                        else:
                                            print(chunk, end="", flush=True)
                                    
                                    if refined_content:
                                        result['full_text'] = refined_content
                                        result['new_content'] = refined_content
                                        from utils.word_count import count_chinese_words
                                        result['total_words'] = count_chinese_words(refined_content)
                                        print(f"\n✅ 润色完成 (共 {result['total_words']} 字)")
                                    else:
                                        print("\n⚠️ 润色结果为空")
                                except Exception as e:
                                    print(f"\n❌ 润色出错: {e}")
                            else:
                                print("⚠️ 未启用思考引擎，无法润色")
                            # 润色后继续询问
                            continue
                        
                        elif choice == 'r':
                            print("\n🔄 正在重试...\n")
                            break  # 跳出确认循环，外层循环继续重试
                        
                    if choice != 'r':
                        break  # 如果不是重试，则结束生成循环
            
            elif cmd == "/status":
                if not project_name:
                    print("❌ 请先创建项目: /new 项目名")
                    continue
                info = storage.get_project_info(project_name)
                print(f"\n📚 项目: {project_name}")
                print(f"📖 章节数: {info['chapter_count']}")
                print(f"📝 总字数: {info['total_words']}")
            
            elif cmd == "/export":
                if not project_name:
                    print("❌ 请先创建项目: /new 项目名")
                    continue
                try:
                    path = storage.export_full_novel(project_name)
                    print(f"\n✅ 已导出: {path}")
                except FileNotFoundError:
                    print("❌ 没有章节可导出")
            
            elif cmd == "/clear":
                history.clear()
                print("✅ 对话历史已清空")
            
            elif cmd == "/save":
                # 保存最后一条 AI 回复为大纲
                if not project_name:
                    print("❌ 请先创建项目: /new 项目名")
                    continue
                
                # 查找最后一条 assistant 消息
                last_ai_msg = None
                for msg in reversed(history):
                    if msg["role"] == "assistant":
                        last_ai_msg = msg["content"]
                        break
                
                if not last_ai_msg:
                    print("❌ 没有可保存的内容")
                    continue
                
                # 保存为大纲
                path = storage.save_outline(project_name, last_ai_msg)
                print(f"✅ 大纲已保存到: {path}")
            
            elif cmd == "/style":
                # 风格参考管理
                if len(parts) > 1:
                    # 导入参考文件
                    ref_source = parts[1]
                    try:
                        if os.path.exists(ref_source):
                            with open(ref_source, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            target_path = os.path.join(storage.base_dir, "reference.txt")
                            with open(target_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            print(f"✅ 已导入风格参考: {ref_source} ({len(content)}字)")
                            print("   接下来的章节生成将模仿该文本的风格和节奏。")
                        else:
                            print(f"❌ 文件不存在: {ref_source}")
                    except Exception as e:
                        print(f"❌ 导入失败: {e}")
                else:
                    # 查看当前参考
                    ref_path = os.path.join(storage.base_dir, "reference.txt")
                    if os.path.exists(ref_path):
                        with open(ref_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        print(f"\n📝 当前风格参考 ({len(content)}字):")
                        print("=" * 50)
                        print(content[:500] + "..." if len(content) > 500 else content)
                        print("=" * 50)
                    else:
                        print("❌ 当前没有设置风格参考。使用 /style <文件路径> 导入。")
            
            elif cmd == "/init":
                # 从结构化大纲初始化角色和世界状态
                if not project_name:
                    print("❌ 请先创建项目: /new 项目名")
                    continue

                gen = OutlineGenerator(ai, storage)
                print("\n📊 正在根据结构化大纲初始化世界模型...")
                try:
                    world_data = gen.initialize_world_from_saved(project_name, save=True)
                    char_count = len(world_data.get("characters", []))
                    print("\n✅ 世界模型已初始化并保存")
                    print(f"   创建/更新了 {char_count} 个角色档案")
                except FileNotFoundError as e:
                    print(f"❌ {e}")
                    print("💡 请先执行：/outline（并保存）后再用命令行 pipeline 初始化，或直接用 new --pipeline")
                except Exception as e:
                    print(f"⚠️ 初始化失败: {e}")
            
            elif cmd == "/chars":
                # 查看角色列表
                if not project_name:
                    print("❌ 请先创建项目: /new 项目名")
                    continue
                
                world_data = storage.load_world_state(project_name)
                if not world_data or 'characters' not in world_data:
                    print("❌ 请先初始化世界模型: /init")
                    continue
                
                print("\n🎭 角色列表:")
                for i, char in enumerate(world_data['characters'], 1):
                    role_icon = "⭐" if char.get('role') == '主角' else "💀" if char.get('role') == '反派' else "👤"
                    print(f"  {i}. {role_icon} {char.get('name', '?')} [{char.get('role', '?')}]")
                    if char.get('personality'):
                        print(f"      性格: {char.get('personality')[:30]}")
                    if char.get('level'):
                         print(f"      境界: {char.get('level')}")
                    if char.get('abilities'):
                         print(f"      功法: {', '.join(char.get('abilities', []))}")
                    if char.get('items'):
                         print(f"      法宝: {', '.join(char.get('items', []))}")
            
            elif cmd == "/world":
                # 查看世界状态
                if not project_name:
                    print("❌ 请先创建项目: /new 项目名")
                    continue
                
                world_data = storage.load_world_state(project_name)
                if not world_data:
                    print("❌ 请先初始化世界模型: /init")
                    continue
                
                print("\n🌍 世界设定:")
                if 'world' in world_data:
                    w = world_data['world']
                    if w.get('environment'):
                        print(f"  📍 环境: {w.get('environment')[:50]}...")
                    if w.get('power_system'):
                        ps = w.get('power_system')
                        if isinstance(ps, str):
                            print(f"  ⚡ 力量体系: {ps[:50]}...")
                        else:
                            print(f"  ⚡ 力量体系: {str(ps)[:50]}...")
                    if w.get('known_methods'):
                        print(f"  📜 知名功法: {', '.join(w.get('known_methods', []))}")
                    if w.get('known_artifacts'):
                        print(f"  💎 知名法宝: {', '.join(w.get('known_artifacts', []))}")
                    if w.get('factions'):
                        print(f"  🏰 势力: {', '.join(w.get('factions', [])[:5])}")
                    
                    if w.get('cultivation_systems'):
                        print("\n  📚 修炼体系详情:")
                        for sys in w.get('cultivation_systems', []):
                            print(f"    🔸 {sys.get('name')} ({sys.get('description', '')[:30]}...)")
                            for rank in sorted(sys.get('ranks', []), key=lambda x: x.get('level_index', 0)):
                                print(f"       [{rank.get('level_index')}] {rank.get('name')}: {rank.get('description', '')[:20]}")
                            if sys.get('methods'):
                                print(f"       功法: {', '.join(sys.get('methods', []))}")
                            print()
                
                if 'locations' in world_data:
                    print(f"\n📍 地点 ({len(world_data['locations'])}个):")
                    for loc in world_data['locations'][:5]:
                        print(f"  - {loc.get('name', '?')}")
            
            else:
                print(f"❓ 未知命令: {cmd}，输入 /help 查看帮助")
        
        else:
            # 普通对话 - 流式输出
            history.append({"role": "user", "content": user_input})
            
            print("\n🤖: ", end="", flush=True)
            response_text = ""
            for chunk in ai.stream_chat(user_input, history=history[:-1], system_prompt=system_prompt):
                print(chunk, end="", flush=True)
                response_text += chunk
            print()  # 换行
            
            history.append({"role": "assistant", "content": response_text})


def main():
    parser = argparse.ArgumentParser(
        description="Story Agent - AI 小说创作助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 交互模式
  python cli.py
  
  # 创建新项目并生成大纲
  python cli.py new "代码修仙" --idea "程序员穿越修仙界用代码画符"
  
  # 五阶段初始化（粗纲->细纲->世界->角色）
  python cli.py new "代码修仙" --idea "程序员穿越修仙界用代码画符" --pipeline --chapters 12
  
  # 写章节
  python cli.py write "代码修仙" 1 "初入青云" --context "主角穿越到青云宗"
  
  # 查看状态
  python cli.py status "代码修仙"
  
  # 导出小说
  python cli.py export "代码修仙"
"""
    )
    parser.add_argument("-o", "--output", default="./output", help="输出目录")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # new 命令
    p_new = subparsers.add_parser("new", help="创建新项目")
    p_new.add_argument("name", help="项目名称")
    p_new.add_argument("--idea", help="创意点子（可选，用于直接生成大纲）")
    p_new.add_argument("--pipeline", action="store_true", help="启用五阶段初始化流程")
    p_new.add_argument("--chapters", type=int, default=10, help="细纲目标章节数（配合 --pipeline）")
    p_new.set_defaults(func=cmd_new)
    
    # outline 命令
    p_outline = subparsers.add_parser("outline", help="大纲操作")
    p_outline.add_argument("project", help="项目名称")
    p_outline.add_argument("action", choices=["create", "expand", "continue", "pipeline"], help="操作类型")
    p_outline.add_argument("--idea", help="创意点子")
    p_outline.add_argument("--request", help="扩展要求")
    p_outline.add_argument("--count", type=int, default=10, help="续写章节数 / pipeline目标章节数")
    p_outline.set_defaults(func=cmd_outline)
    
    # write 命令
    p_write = subparsers.add_parser("write", help="写章节")
    p_write.add_argument("project", help="项目名称")
    p_write.add_argument("chapter", type=int, help="章节序号")
    p_write.add_argument("title", help="章节标题")
    p_write.add_argument("--context", default="", help="章节概要")
    p_write.add_argument("--previous", help="前文摘要")
    p_write.set_defaults(func=cmd_write)
    
    # status 命令
    p_status = subparsers.add_parser("status", help="查看项目状态")
    p_status.add_argument("project", help="项目名称")
    p_status.set_defaults(func=cmd_status)
    
    # export 命令
    p_export = subparsers.add_parser("export", help="导出完整小说")
    p_export.add_argument("project", help="项目名称")
    p_export.set_defaults(func=cmd_export)
    
    # import 命令
    p_import = subparsers.add_parser("import", help="导入已有章节")
    p_import.add_argument("project", help="项目名称")
    p_import.add_argument("--file", help="导入单个文件")
    p_import.add_argument("--dir", help="批量导入目录下的所有 txt")
    p_import.add_argument("--chapter", type=int, default=1, help="章节序号（单文件导入时）")
    p_import.add_argument("--title", help="章节标题（单文件导入时）")
    p_import.set_defaults(func=cmd_import)

    # web 命令
    p_web = subparsers.add_parser("web", help="启动 Chainlit Web 交互模式")
    p_web.add_argument("--host", default="0.0.0.0", help="监听地址")
    p_web.add_argument("--port", type=int, default=8000, help="监听端口")
    p_web.add_argument("-w", "--watch", action="store_true", help="源码变更自动重载")
    p_web.set_defaults(func=cmd_web)
    
    args = parser.parse_args()
    
    if args.command:
        args.func(args)
    else:
        # 无命令时进入交互模式
        cmd_interactive(args)


if __name__ == "__main__":
    main()
