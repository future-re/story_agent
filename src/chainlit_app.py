"""Chainlit web entrypoint for Story Agent."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import chainlit as cl

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from config import config
from generation import OutlineGenerator
from interactive import LANGGRAPH_AVAILABLE, StoryWriteWorkflow
from models import get_client
from skills_runtime import DEFAULT_CHAT_SYSTEM_PROMPT, SkillRegistry, WritingSkillRouter
from storage import StorageManager
from tools import StoryEditTools, StoryReadTools


def _parse_command(text: str) -> Tuple[str, str]:
    raw = text.strip()
    if not raw.startswith("/"):
        return "", ""
    parts = raw.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    return cmd, arg


def _session_storage() -> StorageManager:
    storage = cl.user_session.get("storage")
    if storage is None:
        storage = StorageManager(config.output_dir)
        cl.user_session.set("storage", storage)
    return storage


def _session_read_tools() -> StoryReadTools:
    tools = cl.user_session.get("read_tools")
    if tools is None:
        tools = StoryReadTools(_session_storage())
        cl.user_session.set("read_tools", tools)
    return tools


def _session_edit_tools() -> StoryEditTools:
    tools = cl.user_session.get("edit_tools")
    if tools is None:
        tools = StoryEditTools(_session_storage())
        cl.user_session.set("edit_tools", tools)
    return tools


def _session_skill_router() -> WritingSkillRouter:
    router = cl.user_session.get("skill_router")
    if router is None:
        router = WritingSkillRouter(
            registry=SkillRegistry(config.skills_dir),
            outline_skill_name=config.outline_skill_name,
            continuation_skill_name=config.continuation_skill_name,
            rewrite_skill_name=config.rewrite_skill_name,
            fallback_skill_name=config.writing_skill_name,
            enabled=config.enable_skill_writing,
        )
        cl.user_session.set("skill_router", router)
    return router


def _session_ai() -> Optional[Any]:
    return cl.user_session.get("ai")


def _require_project() -> Optional[str]:
    project_name = cl.user_session.get("project_name")
    return str(project_name).strip() if project_name else None


def _set_pending_write(workflow: StoryWriteWorkflow, preparation: Dict[str, Any]) -> None:
    cl.user_session.set("pending_write_workflow", workflow)
    cl.user_session.set("pending_write_preparation", preparation)


def _clear_pending_write() -> None:
    cl.user_session.set("pending_write_workflow", None)
    cl.user_session.set("pending_write_preparation", None)


async def _send_help() -> None:
    help_text = """可用命令：
/new <项目名>        创建或切换项目
/list                列出项目
/outline <点子>      生成大纲
/expand <要求>       扩展已保存大纲
/write               准备并生成章节（含规划确认）
/approve             确认当前写作规划并生成
/reject              放弃当前写作规划
/status              查看项目状态
/export              导出完整小说
/clear               清空对话历史
/help                查看帮助"""
    await cl.Message(content=help_text).send()


async def _run_outline(project_name: str, idea: str) -> None:
    ai = _session_ai()
    if ai is None:
        await cl.Message(content="❌ 未初始化模型客户端，请检查 API Key 配置。").send()
        return

    storage = _session_storage()
    gen = OutlineGenerator(ai_client=ai, storage=storage)
    outline = await asyncio.to_thread(gen.from_idea, idea, project_name)
    preview = outline[:1500] + ("..." if len(outline) > 1500 else "")
    await cl.Message(content=f"✅ 大纲已保存\n\n{preview}").send()


async def _run_expand(project_name: str, request: str) -> None:
    ai = _session_ai()
    if ai is None:
        await cl.Message(content="❌ 未初始化模型客户端，请检查 API Key 配置。").send()
        return

    storage = _session_storage()
    gen = OutlineGenerator(ai_client=ai, storage=storage)
    try:
        outline = await asyncio.to_thread(gen.load_and_expand, project_name, request)
    except FileNotFoundError:
        await cl.Message(content="❌ 没有找到已保存的大纲，请先执行 /outline。").send()
        return

    preview = outline[:1500] + ("..." if len(outline) > 1500 else "")
    await cl.Message(content=f"✅ 大纲已扩展\n\n{preview}").send()


async def _run_write_prepare(project_name: str) -> None:
    ai = _session_ai()
    if ai is None:
        await cl.Message(content="❌ 未初始化模型客户端，请检查 API Key 配置。").send()
        return

    storage = _session_storage()
    workflow = StoryWriteWorkflow(
        project_name=project_name,
        ai_client=ai,
        storage=storage,
    )
    state = await asyncio.to_thread(workflow.invoke, approved=False, preparation=None)

    if state.get("error"):
        await cl.Message(content=f"❌ {state['error']}").send()
        return

    logs = "".join(state.get("logs") or []).strip()
    if logs:
        logs_preview = logs[:1200] + ("..." if len(logs) > 1200 else "")
        await cl.Message(content=f"准备阶段日志：\n{logs_preview}").send()

    if state.get("awaiting_approval"):
        _set_pending_write(workflow, state.get("preparation", {}))
        plan_text = state.get("plan_text", "已生成规划，请确认是否继续。")
        plan_preview = plan_text[:3000] + ("..." if len(plan_text) > 3000 else "")
        await cl.Message(content=f"{plan_preview}\n\n输入 /approve 确认，或 /reject 放弃。").send()
        return

    await _send_write_result(state)


async def _run_write_approve() -> None:
    workflow = cl.user_session.get("pending_write_workflow")
    preparation = cl.user_session.get("pending_write_preparation")
    if workflow is None or preparation is None:
        await cl.Message(content="❌ 当前没有待确认的写作规划，请先执行 /write。").send()
        return

    state = await asyncio.to_thread(workflow.invoke, approved=True, preparation=preparation)
    _clear_pending_write()
    await _send_write_result(state)


async def _send_write_result(state: Dict[str, Any]) -> None:
    if state.get("error"):
        await cl.Message(content=f"❌ {state['error']}").send()
        return

    result = state.get("result") or {}
    generated = str(state.get("generated_text", "")).strip()
    preview = generated[:2000] + ("..." if len(generated) > 2000 else "")

    summary = (
        f"✅ 生成完成：第{result.get('chapter', '?')}章《{result.get('title', '未命名')}》\n"
        f"本次新增：{result.get('added_words', '?')} 字\n"
        f"保存路径：{state.get('saved_path', '未保存')}"
    )
    await cl.Message(content=f"{summary}\n\n{preview}").send()

    world_logs = "".join(state.get("world_update_logs") or []).strip()
    if world_logs:
        world_preview = world_logs[:1000] + ("..." if len(world_logs) > 1000 else "")
        await cl.Message(content=f"世界状态更新：\n{world_preview}").send()


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("history", [])
    cl.user_session.set("project_name", None)
    _clear_pending_write()
    _session_storage()
    _session_read_tools()
    _session_edit_tools()
    skill_router = _session_skill_router()

    try:
        ai = get_client(config.model_name)
    except Exception as exc:
        ai = None
        await cl.Message(content=f"⚠️ 模型初始化失败：{exc}").send()

    cl.user_session.set("ai", ai)

    langgraph_text = "可用" if LANGGRAPH_AVAILABLE else "未安装（将自动降级为线性流程）"
    active = skill_router.describe_active_skills()
    skill_lines = ", ".join([f"{name}:{'on' if enabled else 'off'}" for name, enabled in active.items()])
    await cl.Message(
        content=(
            "Story Agent Web 已启动。\n"
            f"LangGraph: {langgraph_text}\n"
            f"Skills: {skill_lines}\n"
            "先执行 `/new 项目名`，再用 `/outline 点子` 或 `/write`。输入 `/help` 查看命令。"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    text = message.content.strip()
    cmd, arg = _parse_command(text)

    if cmd:
        if cmd in {"/help", "/"}:
            await _send_help()
            return
        if cmd == "/new":
            if not arg:
                await cl.Message(content="❌ 用法：/new <项目名>").send()
                return
            cl.user_session.set("project_name", arg)
            await cl.Message(content=f"✅ 当前项目：{arg}").send()
            return
        if cmd == "/list":
            read_tools = _session_read_tools()
            projects = read_tools.list_projects()
            if not projects:
                await cl.Message(content="暂无项目").send()
                return
            lines = ["项目列表："]
            for name in sorted(projects):
                info = read_tools.get_project_info(name)
                lines.append(f"- {name} ({info['chapter_count']}章, {info['total_words']}字)")
            await cl.Message(content="\n".join(lines)).send()
            return
        if cmd == "/clear":
            cl.user_session.set("history", [])
            await cl.Message(content="✅ 对话历史已清空").send()
            return
        if cmd == "/reject":
            _clear_pending_write()
            await cl.Message(content="🗑️ 已放弃当前写作规划").send()
            return
        if cmd == "/approve":
            await _run_write_approve()
            return

        project_name = _require_project()
        if not project_name:
            await cl.Message(content="❌ 请先设置项目：/new <项目名>").send()
            return

        if cmd == "/outline":
            if not arg:
                await cl.Message(content="❌ 用法：/outline <创意点子>").send()
                return
            await _run_outline(project_name, arg)
            return
        if cmd == "/expand":
            if not arg:
                await cl.Message(content="❌ 用法：/expand <扩展要求>").send()
                return
            await _run_expand(project_name, arg)
            return
        if cmd == "/write":
            await _run_write_prepare(project_name)
            return
        if cmd == "/status":
            read_tools = _session_read_tools()
            info = read_tools.get_project_info(project_name)
            await cl.Message(
                content=(
                    f"📚 项目: {project_name}\n"
                    f"📖 章节数: {info['chapter_count']}\n"
                    f"📝 总字数: {info['total_words']}"
                )
            ).send()
            return
        if cmd == "/export":
            edit_tools = _session_edit_tools()
            try:
                path = edit_tools.export_full_novel(project_name)
            except FileNotFoundError:
                await cl.Message(content="❌ 没有章节可导出").send()
                return
            await cl.Message(content=f"✅ 已导出: {path}").send()
            return

        await cl.Message(content=f"❓ 未知命令: {cmd}，输入 /help 查看帮助。").send()
        return

    ai = _session_ai()
    if ai is None:
        await cl.Message(content="❌ 模型客户端不可用，请检查环境变量后重启。").send()
        return

    history: List[Dict[str, Any]] = cl.user_session.get("history") or []
    history.append({"role": "user", "content": text})
    skill_router = _session_skill_router()
    runtime = skill_router.route("chat-consult", user_text=text)
    system_prompt = runtime.build_system_prompt("编辑咨询", DEFAULT_CHAT_SYSTEM_PROMPT)

    reply = cl.Message(content="")
    await reply.send()
    response_text = ""
    for chunk in ai.stream_chat(text, history=history[:-1], system_prompt=system_prompt):
        response_text += str(chunk)
        await reply.stream_token(str(chunk))

    history.append({"role": "assistant", "content": response_text})
    cl.user_session.set("history", history)
