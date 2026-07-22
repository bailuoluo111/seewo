#!/usr/bin/env python3
"""
agent.py — 通用 MCP ReAct Agent

架构：ReAct (Reasoning + Acting)
  - 通过本地 MCP 服务发现并调用工具
  - Agent 不内置任何业务领域逻辑
  - Agent loop：持续调用 LLM → 执行工具 → 喂回结果，直到无工具调用退出
  - OpenTelemetry 全链路追踪

使用方法:
    python agent.py
"""

import re
import os
import sys
import json
from pathlib import Path

# 保持运行目录整洁，避免本地模块生成 __pycache__
sys.dont_write_bytecode = True

# ── OpenTelemetry（必需依赖）─────────────────────────────────────────────
from opentelemetry import trace as _otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace.status import Status, StatusCode

from mcp.client import SeewoMCPClient


# ── Agent 系统提示 ────────────────────────────────────────────────────────
AGENT_SYSTEM_PROMPT = """\
你是一个通用的 ReAct Agent，可以按需调用外部工具完成用户任务。

【工作原则】
1. 先理解用户目标，再根据工具描述决定是否调用工具
2. 工具所需参数应优先从用户输入和已有上下文中提取
3. 如果缺少必要参数且无法可靠推断，应先向用户提问，不要臆造
4. 可以多轮调用工具，但只调用与当前任务直接相关的工具
5. 最终回答必须基于已有上下文和工具结果，不得编造未观测到的信息
6. 回答语言默认跟随用户输入语言
"""


# ── 紧凑 Trace Exporter（每个 span 一行精简 JSON）──────────────────────────
class CompactSpanExporter:
    """
    只输出关键字段，一个 span 一行：
      {"t":"12:00:01","span":"seewo.llm.call","dur_ms":3601,"status":"OK",
       "attrs":{"llm.tokens.total":1402,...}}
    去掉 resource / trace_state / kind / events / links 等重复噪音。
    """
    def __init__(self, out):
        self._out = out

    def export(self, spans):
        import json as _json
        from datetime import datetime as _dt
        for s in spans:
            attrs = dict(s.attributes or {})
            line = {
                "t":      _dt.fromtimestamp(s.start_time / 1e9).strftime("%H:%M:%S"),
                "span":   s.name,
                "dur_ms": round((s.end_time - s.start_time) / 1e6, 1),
                "status": s.status.status_code.name if s.status else "UNSET",
                "trace":  f"{s.context.trace_id:032x}"[:8],  # 短 trace_id，方便分组
            }
            if attrs:
                line["attrs"] = attrs
            self._out.write(_json.dumps(line, ensure_ascii=False) + "\n")
        return None

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000):
        _ = timeout_millis
        return True


# ── Tracer 初始化 ─────────────────────────────────────────────────────────
def _setup_tracing():
    import sys as _sys
    resource = Resource.create({"service.name": "seewo-agent", "service.version": "2.0"})
    provider = TracerProvider(resource=resource)

    # Trace 默认写文件，保持交互终端干净（监控数据不该喷在 CLI 里）
    #   SEEWO_TRACE_FILE=<path>  自定义文件路径
    #   SEEWO_TRACE_CONSOLE=1    改为打印到 stderr（调试用）
    #   OTEL_EXPORTER_OTLP_ENDPOINT=<url>  发送到 OTLP 后端（Jaeger/Tempo 等）
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    if os.environ.get("SEEWO_TRACE_CONSOLE") == "1":
        provider.add_span_processor(SimpleSpanProcessor(CompactSpanExporter(out=_sys.stderr)))
    else:
        trace_file = os.environ.get("SEEWO_TRACE_FILE", str(Path(__file__).parent / "seewo_traces.jsonl"))
        f = open(trace_file, "a", encoding="utf-8", buffering=1)
        # SimpleSpanProcessor：span 结束即同步写入，避免异步 flush 时机问题
        provider.add_span_processor(SimpleSpanProcessor(CompactSpanExporter(out=f)))
        _setup_tracing.trace_file = trace_file  # 供 CLI 启动时提示

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
            print(f"[OTel] OTLP traces → {otlp_endpoint}", file=_sys.stderr)
        except ImportError:
            print("[OTel] OTLP exporter 未安装（pip install opentelemetry-exporter-otlp-proto-grpc）", file=_sys.stderr)
    _otel_trace.set_tracer_provider(provider)
    return _otel_trace.get_tracer("seewo.agent")


tracer = _setup_tracing()


# ── 配置读取 ──────────────────────────────────────────────────────────────
def _load_config() -> dict:
    cfg_path = Path(__file__).parent / "SEEWO_CONFIG.md"
    if not cfg_path.exists():
        return {}
    content = cfg_path.read_text(encoding="utf-8")
    result = {}
    for key, pattern in [
        ("api_key",  r"api_key:\s*([^\s`]+)"),
        ("api_base", r"api_base:\s*([^\s`]+)"),
        ("model",    r"model:\s*([^\s`]+)"),
    ]:
        m = re.search(pattern, content)
        if m:
            result[key] = m.group(1).strip()
    return result


# ── 核心 Agent ────────────────────────────────────────────────────────────
class SeewoAgent:

    MAX_TURNS = 10  # 防止无限循环的安全上限
    EMPTY_ANSWER_RETRY_LIMIT = 1  # 最终回答为空时，额外追问一次

    def __init__(self):
        cfg = _load_config()
        self.api_key  = cfg.get("api_key")
        if not self.api_key:
            raise ValueError("未找到 api_key，请在 SEEWO_CONFIG.md 中配置")
        self.api_base = cfg.get("api_base") or "https://token.cvte.com/v1"
        self.model    = cfg.get("model") or "deepseek-v4-pro"
        self.mcp_client = SeewoMCPClient(project_root=Path(__file__).parent)
        self.tool_registry = self._load_mcp_tools()
        self.tools = [meta["tool_spec"] for meta in self.tool_registry.values()]
        if not self.tools:
            raise ValueError("未发现可用 MCP 工具，请检查 mcp/server.py")

    def _load_mcp_tools(self) -> dict:
        """从本地 MCP 服务发现工具。"""
        tools = self.mcp_client.list_tools()
        registry = {}
        for tool in tools:
            tool_name = (tool.get("name") or "").strip()
            if not tool_name:
                continue
            registry[tool_name] = {
                "tool_name": tool_name,
                "tool_spec": {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool.get("description", ""),
                        "parameters": tool.get("inputSchema", {}),
                    },
                },
            }
        return registry

    def _extract_context_from_tool_result(self, tool_result: dict) -> dict:
        """从工具结果里提取可用于 CLI / API 展示的通用上下文。"""
        if not isinstance(tool_result, dict):
            return {}
        if isinstance(tool_result.get("course"), dict):
            return tool_result["course"]
        if isinstance(tool_result.get("context"), dict):
            return tool_result["context"]
        return {}

    def _format_context_summary(self, context: dict) -> str:
        """把通用上下文字典压缩成一行摘要，避免 CLI 写死领域字段。"""
        if not isinstance(context, dict) or not context:
            return ""
        parts = []
        for key, value in context.items():
            if value in (None, "", [], {}):
                continue
            parts.append(f"{key}: {value}")
            if len(parts) >= 3:
                break
        return "  ".join(parts)

    # ── 内部：执行工具调用 ────────────────────────────────────────────
    def _execute_tool(self, tool_name: str, args: dict) -> str:
        """执行工具，返回 JSON 字符串给 LLM。"""
        with tracer.start_as_current_span("seewo.tool.execute") as span:
            span.set_attribute("tool.name", tool_name)
            for key, value in args.items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"tool.arg.{key}", value)

            tool_meta = self.tool_registry.get(tool_name)
            if not tool_meta:
                return json.dumps({"error": f"未知工具：{tool_name}"}, ensure_ascii=False)

            try:
                result = self.mcp_client.call_tool(tool_name, args)
                span.set_attribute("tool.success", True)
                if isinstance(result, dict):
                    span.set_attribute("tool.result.length", len(json.dumps(result, ensure_ascii=False)))
                return json.dumps(result, ensure_ascii=False, indent=2)
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── 内部：单次 LLM 调用 ───────────────────────────────────────────
    def _call_llm(self, messages: list, use_tools: bool = True):
        """调用 LLM，返回 (message, metadata)。"""
        with tracer.start_as_current_span("seewo.llm.call") as span:
            span.set_attribute("llm.model",          self.model)
            span.set_attribute("llm.messages.count", len(messages))
            span.set_attribute("llm.tools_enabled",  use_tools)
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key, base_url=self.api_base)
                kwargs = dict(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=768 if not use_tools else 512,
                )
                if use_tools:
                    kwargs["tools"]       = self.tools
                    kwargs["tool_choice"] = "auto"

                resp = client.chat.completions.create(**kwargs)
                choice = resp.choices[0]
                msg = choice.message
                finish_reason = getattr(choice, "finish_reason", None) or ""
                content = (msg.content or "").strip()

                if getattr(resp, "usage", None):
                    span.set_attribute("llm.tokens.prompt",     resp.usage.prompt_tokens)
                    span.set_attribute("llm.tokens.completion",  resp.usage.completion_tokens)
                    span.set_attribute("llm.tokens.total",       resp.usage.total_tokens)

                tool_calls = getattr(msg, "tool_calls", None) or []
                span.set_attribute("llm.finish_reason", finish_reason or "unknown")
                span.set_attribute("llm.has_content", bool(content))
                span.set_attribute("llm.content.length", len(content))
                span.set_attribute("llm.tool_calls.count", len(tool_calls))
                span.set_status(Status(StatusCode.OK))
                return msg, {
                    "finish_reason": finish_reason,
                    "content": content,
                    "tool_calls_count": len(tool_calls),
                }
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    # ── 公开：ReAct agent loop ────────────────────────────────────────
    def run(self, user_input: str) -> dict:
        """
        ReAct 循环：
          1. 把用户输入交给 LLM
          2. LLM 返回工具调用 → 执行 → 把结果追加到 messages → 继续
          3. LLM 不再调用工具 → 返回最终回答，退出循环
        """
        with tracer.start_as_current_span("seewo.agent.run") as root:
            root.set_attribute("user_input.length", len(user_input))

            messages = [
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user",   "content": user_input},
            ]
            tool_calls_total = 0
            course_info      = {}
            empty_answer_retries = 0

            try:
                for turn in range(1, self.MAX_TURNS + 1):
                    with tracer.start_as_current_span("seewo.agent.loop.turn") as ts:
                        ts.set_attribute("loop.turn", turn)

                        msg, llm_meta = self._call_llm(messages, use_tools=True)
                        tool_calls = getattr(msg, "tool_calls", None) or []
                        ts.set_attribute("tool_calls.this_turn", len(tool_calls))
                        ts.set_attribute("llm.finish_reason", llm_meta.get("finish_reason", ""))

                        # ── 无工具调用 → 最终回答，退出循环 ──────────────
                        if not tool_calls:
                            answer = llm_meta.get("content", "")
                            ts.set_attribute("answer.length", len(answer))

                            if not answer and empty_answer_retries < self.EMPTY_ANSWER_RETRY_LIMIT:
                                empty_answer_retries += 1
                                ts.set_attribute("llm.empty_answer_retry", empty_answer_retries)
                                retry_messages = messages + [{
                                    "role": "user",
                                    "content": (
                                        "请直接基于现有上下文输出最终回答，不要调用任何工具。"
                                        "必须返回可直接展示给用户的最终文本；"
                                        "如果信息不足，请明确说明原因。"
                                    ),
                                }]
                                _, retry_meta = self._call_llm(retry_messages, use_tools=False)
                                retry_answer = retry_meta.get("content", "")
                                ts.set_attribute("retry.answer.length", len(retry_answer))
                                ts.set_attribute("retry.finish_reason", retry_meta.get("finish_reason", ""))
                                if retry_answer:
                                    answer = retry_answer
                                else:
                                    ts.set_status(Status(StatusCode.ERROR, "LLM 返回空内容"))
                                    root.set_attribute("loop.turns_total", turn)
                                    root.set_attribute("tool_calls.total", tool_calls_total)
                                    root.set_attribute("answer.length", 0)
                                    root.set_status(Status(StatusCode.ERROR, "LLM 返回空内容"))
                                    return {
                                        "success": False,
                                        "error": (
                                            "模型本轮未返回可展示内容。"
                                            f"finish_reason={llm_meta.get('finish_reason') or 'unknown'}，"
                                            f"retry_finish_reason={retry_meta.get('finish_reason') or 'unknown'}。"
                                            "请重试，或缩小分析范围后再问。"
                                        ),
                                        "course_info": course_info,
                                        "turns": turn,
                                        "tool_calls": tool_calls_total,
                                    }

                            ts.set_attribute("loop.exit", True)
                            ts.set_status(Status(StatusCode.OK))
                            root.set_attribute("loop.turns_total",   turn)
                            root.set_attribute("tool_calls.total",   tool_calls_total)
                            root.set_attribute("answer.length",      len(answer))
                            root.set_status(Status(StatusCode.OK))
                            return {
                                "success":     True,
                                "answer":      answer,
                                "course_info": course_info,
                                "turns":       turn,
                                "tool_calls":  tool_calls_total,
                            }

                        # ── 把 assistant 消息（含工具调用）追加到历史 ──────
                        messages.append({
                            "role":       "assistant",
                            "content":    msg.content,
                            "tool_calls": [
                                {
                                    "id":       tc.id,
                                    "type":     "function",
                                    "function": {
                                        "name":      tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in tool_calls
                            ],
                        })

                        # ── 逐个执行工具，结果追加到历史 ─────────────────
                        for tc in tool_calls:
                            tool_calls_total += 1
                            tool_name = tc.function.name
                            try:
                                tool_args = json.loads(tc.function.arguments)
                            except json.JSONDecodeError:
                                tool_args = {}

                            print(f"  🔧 [{turn}] {tool_name}  args={tool_args}")

                            result_str = self._execute_tool(tool_name, tool_args)

                            # 顺带抓一下通用上下文供 CLI / API 展示
                            if not course_info:
                                try:
                                    obj = json.loads(result_str)
                                    context = self._extract_context_from_tool_result(obj)
                                    if context:
                                        course_info = context
                                except Exception:
                                    pass

                            messages.append({
                                "role":         "tool",
                                "tool_call_id": tc.id,
                                "content":      result_str,
                            })

                # 超出最大轮次
                root.set_attribute("loop.max_turns_exceeded", True)
                root.set_status(Status(StatusCode.ERROR, "超出最大轮次"))
                return {"success": False, "error": f"超出最大轮次 ({self.MAX_TURNS})，请重新提问"}

            except Exception as e:
                root.record_exception(e)
                root.set_status(Status(StatusCode.ERROR, str(e)))
                return {"success": False, "error": str(e)}


def main():
    try:
        agent = SeewoAgent()
    except Exception as e:
        print(f"❌ 初始化失败：{e}")
        print("请确保 SEEWO_CONFIG.md 中已配置 api_key，且本地 MCP 服务可正常启动")
        return
    print("你好，我能为你做什么？")

    while True:
        try:
            user_input = input("📝 请输入：").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q", "退出"):
                print("\n👋 再见！\n")
                break

            print()
            result = agent.run(user_input)
            print()

            if result["success"]:
                info = result.get("course_info", {})
                if info:
                    summary = agent._format_context_summary(info)
                    if summary:
                        print(f"上下文：{summary}")
                print(f"（调用 {result['tool_calls']} 个工具，共 {result['turns']} 轮对话）")
                print("─" * 80)
                answer = (result.get("answer") or "").strip()
                if answer:
                    print(f"\n💬 {answer}\n")
                else:
                    print("\n⚠️ 本轮模型未返回可展示内容，请重试或缩小分析范围。\n")
            else:
                print(f"❌ {result['error']}\n")

        except KeyboardInterrupt:
            print("\n\n👋 再见！\n")
            break
        except Exception as e:
            print(f"\n❌ 发生错误：{e}\n")


if __name__ == "__main__":
    main()
