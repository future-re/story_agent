"""LangGraph-driven interactive workflows for Story Agent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from generation import ChapterGenerator
from storage import StorageManager

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    END = "__end__"
    START = "__start__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


class WriteWorkflowState(TypedDict, total=False):
    """章节写作工作流状态。"""

    approved: bool
    logs: List[str]
    preparation: Dict[str, Any]
    plan_text: str
    requires_approval: bool
    awaiting_approval: bool
    generated_text: str
    result: Dict[str, Any]
    saved_path: str
    world_update_logs: List[str]
    world_update: Dict[str, Any]
    error: str


class StoryWriteWorkflow:
    """章节写作交互工作流（prepare -> review -> generate -> persist）。"""

    def __init__(
        self,
        project_name: str,
        *,
        ai_client: Any = None,
        storage: Optional[StorageManager] = None,
        chapter_generator: Optional[ChapterGenerator] = None,
        enable_langgraph: bool = True,
    ):
        self.project_name = project_name
        self.storage = storage or StorageManager()
        self.chapter_gen = chapter_generator or ChapterGenerator(
            project_name=project_name,
            ai_client=ai_client,
            storage=self.storage,
        )
        self._graph = None
        if enable_langgraph and LANGGRAPH_AVAILABLE:
            self._graph = self._build_graph()

    @property
    def using_langgraph(self) -> bool:
        return self._graph is not None

    def invoke(
        self,
        *,
        approved: bool = False,
        preparation: Optional[Dict[str, Any]] = None,
    ) -> WriteWorkflowState:
        """执行工作流；首次调用建议 approved=False，确认后传 approved=True。"""
        state: WriteWorkflowState = {"approved": approved}
        if preparation is not None:
            state["preparation"] = preparation
        if self._graph is not None:
            return self._graph.invoke(state)
        return self._invoke_fallback(state)

    def _build_graph(self):
        graph = StateGraph(WriteWorkflowState)
        graph.add_node("prepare", self._node_prepare)
        graph.add_node("review", self._node_review)
        graph.add_node("generate", self._node_generate)
        graph.add_node("persist", self._node_persist)
        graph.add_edge(START, "prepare")
        graph.add_edge("prepare", "review")
        graph.add_conditional_edges(
            "review",
            self._route_after_review,
            {
                "await": END,
                "generate": "generate",
            },
        )
        graph.add_edge("generate", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _route_after_review(self, state: WriteWorkflowState) -> str:
        if state.get("awaiting_approval"):
            return "await"
        return "generate"

    def _invoke_fallback(self, state: WriteWorkflowState) -> WriteWorkflowState:
        current = dict(state)
        current.update(self._node_prepare(current))
        current.update(self._node_review(current))
        if current.get("awaiting_approval"):
            return current
        current.update(self._node_generate(current))
        if current.get("error"):
            return current
        current.update(self._node_persist(current))
        return current

    def _node_prepare(self, state: WriteWorkflowState) -> WriteWorkflowState:
        if state.get("preparation"):
            preparation = state["preparation"]
            requires_approval = bool(
                preparation.get("thinking_plan") and self.chapter_gen.thinking_engine
            )
            return {
                "preparation": preparation,
                "requires_approval": requires_approval,
                "plan_text": self._format_plan_text(preparation),
            }

        logs: List[str] = []
        preparation: Optional[Dict[str, Any]] = None
        try:
            for output in self.chapter_gen.prepare_writing():
                if isinstance(output, dict):
                    preparation = output
                else:
                    logs.append(str(output))
        except Exception as exc:  # pragma: no cover - relies on runtime model behavior
            return {"logs": logs, "error": f"准备阶段失败: {exc}"}

        if not preparation:
            return {"logs": logs, "error": "准备阶段未返回有效结果"}

        requires_approval = bool(
            preparation.get("thinking_plan") and self.chapter_gen.thinking_engine
        )
        return {
            "logs": logs,
            "preparation": preparation,
            "plan_text": self._format_plan_text(preparation),
            "requires_approval": requires_approval,
        }

    def _node_review(self, state: WriteWorkflowState) -> WriteWorkflowState:
        requires_approval = bool(state.get("requires_approval"))
        approved = bool(state.get("approved"))
        if requires_approval and not approved:
            return {"awaiting_approval": True}
        return {"awaiting_approval": False}

    def _node_generate(self, state: WriteWorkflowState) -> WriteWorkflowState:
        preparation = state.get("preparation")
        if not preparation:
            return {"error": "缺少 preparation，无法生成章节"}

        chunks: List[str] = []
        result: Optional[Dict[str, Any]] = None
        try:
            for output in self.chapter_gen.generate_from_plan(preparation):
                if isinstance(output, dict):
                    result = output
                else:
                    chunks.append(str(output))
        except Exception as exc:  # pragma: no cover - relies on runtime model behavior
            return {"error": f"生成阶段失败: {exc}"}

        if not result:
            return {"generated_text": "".join(chunks), "error": "生成阶段未返回结果"}

        return {"generated_text": "".join(chunks), "result": result}

    def _node_persist(self, state: WriteWorkflowState) -> WriteWorkflowState:
        result = state.get("result")
        if not result:
            return {"error": "缺少生成结果，无法保存"}

        saved_path = self.storage.save_chapter(
            self.project_name,
            int(result["chapter"]),
            str(result["title"]),
            str(result["full_text"]),
        )

        world_update_logs: List[str] = []
        world_update: Dict[str, Any] = {}
        new_content = result.get("new_content")
        if new_content:
            try:
                for update_chunk in self.chapter_gen.update_world_state(str(new_content)):
                    if isinstance(update_chunk, dict):
                        world_update = update_chunk
                    else:
                        world_update_logs.append(str(update_chunk))
            except Exception as exc:  # pragma: no cover - relies on runtime model behavior
                world_update_logs.append(f"更新世界状态失败: {exc}")

        return {
            "saved_path": saved_path,
            "world_update_logs": world_update_logs,
            "world_update": world_update,
        }

    def _format_plan_text(self, preparation: Dict[str, Any]) -> str:
        thinking_plan = preparation.get("thinking_plan")
        if thinking_plan and self.chapter_gen.thinking_engine:
            try:
                return self.chapter_gen.thinking_engine.format_full_plan_display(thinking_plan)
            except Exception:
                return "已生成剧情规划（显示失败，可直接确认生成）。"
        return "未启用剧情思考规划，将直接生成章节。"
