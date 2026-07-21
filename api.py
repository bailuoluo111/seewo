#!/usr/bin/env python3
"""
api.py — 把希沃课堂分析 Agent 封装成 HTTP API，供测评平台调用。

响应中同时返回：
  - answer      Agent 的自然语言输出
  - metrics     从 trace 提炼的关键指标（耗时/轮次/工具数/token）
  - trace       本次请求的完整调用链 span 列表（供深度评估）

复用 agent.py 的 SeewoAgent 和已配置好的 TracerProvider，不改动 agent.py。

启动:
    python api.py                      # 默认 0.0.0.0:8008
    uvicorn api:app --host 0.0.0.0 --port 8008

调用:
    curl -X POST http://localhost:8008/analyze \
         -H 'Content-Type: application/json' \
         -d '{"input": "分析 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动"}'
"""

import sys
sys.dont_write_bytecode = True  # 动态加载 skill 脚本时不生成 __pycache__

import threading
from datetime import datetime
from typing import Optional, Dict, List, Any

from fastapi import FastAPI
from pydantic import BaseModel

import agent as ag  # 复用 SeewoAgent + tracer

# ── 内存 Trace 收集器（按 trace_id 分组保存本次请求的 span）──────────────
class InMemoryTraceCollector:
    """
    实现 OTel SpanExporter 接口的最小收集器。
    挂到 agent 已有的 TracerProvider 上，按 trace_id 缓存 span，
    请求结束后按 trace_id 取出并清理，避免内存无限增长。
    """

    def __init__(self):
        self._store: Dict[int, List[dict]] = {}
        self._lock = threading.Lock()

    # OTel SpanExporter 接口：export / shutdown
    def export(self, spans):
        with self._lock:
            for s in spans:
                self._store.setdefault(s.context.trace_id, []).append(self._serialize(s))
        return None  # SpanExportResult.SUCCESS 的兼容返回

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000):
        return True

    @staticmethod
    def _serialize(span) -> dict:
        """把 ReadableSpan 转成可 JSON 序列化的 dict。"""
        ctx = span.context
        parent = span.parent
        return {
            "name": span.name,
            "span_id": f"0x{ctx.span_id:016x}",
            "trace_id": f"0x{ctx.trace_id:032x}",
            "parent_span_id": f"0x{parent.span_id:016x}" if parent else None,
            "start_time": datetime.fromtimestamp(span.start_time / 1e9).isoformat(),
            "end_time": datetime.fromtimestamp(span.end_time / 1e9).isoformat(),
            "duration_ms": round((span.end_time - span.start_time) / 1e6, 2),
            "status": span.status.status_code.name if span.status else "UNSET",
            "attributes": dict(span.attributes or {}),
        }

    def pop(self, trace_id: int) -> List[dict]:
        """取出并移除某个 trace 的所有 span，按开始时间排序。"""
        with self._lock:
            spans = self._store.pop(trace_id, [])
        return sorted(spans, key=lambda s: s["start_time"])


# ── 把收集器挂到 agent 的 TracerProvider ─────────────────────────────────
_collector = InMemoryTraceCollector()
from opentelemetry import trace as _otel
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
_provider = _otel.get_tracer_provider()
_provider.add_span_processor(SimpleSpanProcessor(_collector))
_api_tracer = _otel.get_tracer("seewo.api")


# ── 从 trace 提炼评估指标 ───────────────────────────────────────────────
def _extract_metrics(spans: List[dict]) -> Dict[str, Any]:
    """从 span 列表提炼平台评估常用的关键指标。"""
    # 总耗时取最外层 span（api.analyze），轮次取 agent.run span
    root = next((s for s in spans if s["parent_span_id"] is None), None)
    run_span = next((s for s in spans if s["name"] == "seewo.agent.run"), None)
    llm_spans  = [s for s in spans if s["name"] == "seewo.llm.call"]
    tool_spans = [s for s in spans if s["name"] == "seewo.tool.execute"]

    total_tokens = sum(s["attributes"].get("llm.tokens.total", 0) for s in llm_spans)
    prompt_tokens = sum(s["attributes"].get("llm.tokens.prompt", 0) for s in llm_spans)
    completion_tokens = sum(s["attributes"].get("llm.tokens.completion", 0) for s in llm_spans)
    tools_used = [s["attributes"].get("tool.name", "") for s in tool_spans]

    return {
        "total_duration_ms": root["duration_ms"] if root else None,
        "turns":             run_span["attributes"].get("loop.turns_total") if run_span else None,
        "tool_calls":        len(tool_spans),
        "llm_calls":         len(llm_spans),
        "tokens": {
            "prompt":     prompt_tokens,
            "completion": completion_tokens,
            "total":      total_tokens,
        },
        "tools_used":        tools_used,
        "span_count":        len(spans),
        "has_error":         any(s["status"] == "ERROR" for s in spans),
    }


# ── FastAPI 应用 ────────────────────────────────────────────────────────
app = FastAPI(title="Seewo Agent API", version="1.0")

_agent: Optional[ag.SeewoAgent] = None


def _get_agent() -> ag.SeewoAgent:
    global _agent
    if _agent is None:
        _agent = ag.SeewoAgent()
    return _agent


class AnalyzeRequest(BaseModel):
    input: str                          # 用户的自然语言输入
    include_trace: bool = True          # 是否在响应中返回完整 trace


class AnalyzeResponse(BaseModel):
    success: bool
    answer: Optional[str] = None
    error: Optional[str] = None
    course_info: Optional[dict] = None
    metrics: Optional[dict] = None
    trace: Optional[List[dict]] = None
    trace_id: Optional[str] = None


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """
    接收自然语言输入，运行 Agent，返回输出 + 指标 + 完整 trace。
    用一个 api.analyze 根 span 包住 agent.run()，
    这样本次请求所有 span 共享同一 trace_id，便于收集。
    """
    agent = _get_agent()

    with _api_tracer.start_as_current_span("seewo.api.analyze") as root:
        trace_id_int = root.get_span_context().trace_id
        root.set_attribute("api.input", req.input[:200])

        result = agent.run(req.input)

        root.set_attribute("api.success", result.get("success", False))

    # agent.run 及其子 span 已同步落到 collector，按 trace_id 取出
    spans = _collector.pop(trace_id_int)
    metrics = _extract_metrics(spans)

    return AnalyzeResponse(
        success     = result.get("success", False),
        answer      = result.get("answer"),
        error       = result.get("error"),
        course_info = result.get("course_info"),
        metrics     = metrics,
        trace       = spans if req.include_trace else None,
        trace_id    = f"0x{trace_id_int:032x}",
    )


@app.get("/")
def root():
    """API 说明。"""
    return {
        "service": "Seewo Agent API",
        "endpoints": {
            "POST /analyze": "运行 Agent，返回 answer + metrics + trace",
            "GET /health":   "健康检查",
            "GET /docs":     "交互式 API 文档（Swagger UI）",
        },
        "example": {
            "method": "POST",
            "url": "/analyze",
            "body": {"input": "分析 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动", "include_trace": True},
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
