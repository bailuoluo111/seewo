#!/usr/bin/env python3
"""
agent.py — 希沃课堂分析 Agent（ReAct 工具调用循环，DeepSeek v4）

架构：ReAct (Reasoning + Acting)
  - 7 个 Skill 注册为 LLM 工具，Agent 自主决定调用哪个
  - report_id 由 LLM 从自然语言中提取，不限制输入格式
  - Agent loop：持续调用 LLM → 执行工具 → 喂回结果，直到无工具调用退出
  - OpenTelemetry 全链路追踪

使用方法:
    python agent.py

自然语言输入示例:
    帮我看看这节课的学生互动：https://easiinsight.seewo.com/report/detail/96f58e78b80c462cb1194fa2f6ef4e97/home
    96f58e78b80c462cb1194fa2f6ef4e97 的提问质量怎么样？
    全面分析一下这个报告 96f58e78b80c462cb1194fa2f6ef4e97
"""

import re
import os
import sys
import json
import importlib.util
from pathlib import Path

# 动态加载 skill 脚本时不生成 __pycache__（避免污染 skills 目录）
sys.dont_write_bytecode = True

# ── OpenTelemetry（必需依赖）─────────────────────────────────────────────
from opentelemetry import trace as _otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace.status import Status, StatusCode


# ── Skill 目录映射 ────────────────────────────────────────────────────────
SKILLS_DIR = Path(__file__).parent / "skills"

SKILL_DIRS = {
    1: "student_interaction",
    2: "student_behavior",
    3: "solo_classification",
    4: "answer_time",
    5: "teacher_speech",
    6: "course_reengineering",
    7: "question_effectiveness",
}
SKILL_NAMES = {
    1: "学生互动分析",
    2: "学习行为分析",
    3: "SOLO分类分析",
    4: "应答时间分析",
    5: "讲授分析",
    6: "课堂流程重构",
    7: "提问有效性分析",
}

# 工具名 → skill 编号
TOOL_SKILL_MAP = {
    "analyze_student_interaction":    1,
    "analyze_student_behavior":       2,
    "analyze_solo_classification":    3,
    "analyze_answer_time":            4,
    "analyze_teacher_speech":         5,
    "analyze_course_reengineering":   6,
    "analyze_question_effectiveness": 7,
}

# ── 工具定义（传给 LLM 的 JSON Schema）──────────────────────────────────
_REPORT_ID_PARAM = {
    "type": "object",
    "properties": {
        "report_id": {
            "type": "string",
            "description": (
                "课程报告的唯一ID（32位十六进制字符串）。"
                "可从用户输入的URL中提取：.../report/detail/<report_id>/home，"
                "或直接出现在文字中。"
            ),
        }
    },
    "required": ["report_id"],
}

TOOLS = [
    {"type": "function", "function": {
        "name": "analyze_student_interaction",
        "description": "分析学生互动数据：平均抬头率（专注度）、平均举手率（参与意愿）、平均参与度（实际回答比例）。结合学段给出差异化建议。",
        "parameters": _REPORT_ID_PARAM,
    }},
    {"type": "function", "function": {
        "name": "analyze_student_behavior",
        "description": "基于学习金字塔理论分析学习行为分布：7类行为（听讲/阅读/视听/演示/讨论/实践/教给他人）的时长占比，估算知识留存率。",
        "parameters": _REPORT_ID_PARAM,
    }},
    {"type": "function", "function": {
        "name": "analyze_solo_classification",
        "description": "基于SOLO分类法评估学生回答建构水平：前结构/单点结构/多点结构/关联结构/抽象拓展五级分布。",
        "parameters": _REPORT_ID_PARAM,
    }},
    {"type": "function", "function": {
        "name": "analyze_answer_time",
        "description": "分析学生应答时间分布：≤5秒/5-15秒/>15秒三档，评估问题难度层次和学生思考深度。",
        "parameters": _REPORT_ID_PARAM,
    }},
    {"type": "function", "function": {
        "name": "analyze_teacher_speech",
        "description": "分析教师讲授数据：讲授字数、时长、平均语速（字/秒）。参考最佳语速3-4字/秒。",
        "parameters": _REPORT_ID_PARAM,
    }},
    {"type": "function", "function": {
        "name": "analyze_course_reengineering",
        "description": "评估课堂流程重构度：课前→课中、课中→课后链接等级（初阶/进阶/中阶/高阶）。",
        "parameters": _REPORT_ID_PARAM,
    }},
    {"type": "function", "function": {
        "name": "analyze_question_effectiveness",
        "description": "综合分析提问有效性：布鲁姆六级提问分类（含高阶思维占比）、教师理答类型分布（简单肯定/针对肯定/启发鼓励等）、提问有效性综合得分。",
        "parameters": _REPORT_ID_PARAM,
    }},
]

# ── Agent 系统提示 ────────────────────────────────────────────────────────
AGENT_SYSTEM_PROMPT = """\
你是一名希沃课堂分析助手，拥有丰富的教研经验。

【工具使用规则】
1. report_id 是 32 位十六进制字符串，请从用户输入自行提取：
   - 直接出现在文字中：如 "96f58e78b80c462cb1194fa2f6ef4e97"
   - 出现在 URL 中：.../report/detail/<report_id>/home 或 .../detail/js2/<report_id>/home
2. 根据用户的分析需求选择合适工具；"综合分析"或"全面分析"时可按需调用多个工具
3. 若无法从用户输入中找到 report_id，礼貌询问

【分析输出要求】
- 基于工具返回的真实数据，不得臆造
- 符合 BID 反馈原则：先认同优点，再给出改进建议
- 每个维度分析 150 字以内，整合成一段话，不分行
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
        ("token",    r"x-token=([^;`\s]+)"),
        ("username", r"x-username=([^;`\s]+)"),
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
        self.token    = cfg.get("token")
        self.username = cfg.get("username")
        if not self.api_key:
            raise ValueError("未找到 api_key，请在 SEEWO_CONFIG.md 中配置")
        self.api_base = cfg.get("api_base") or "https://token.cvte.com/v1"
        self.model    = cfg.get("model") or "deepseek-v4-pro"

    # ── 内部：获取 Skill 数据 ─────────────────────────────────────────
    def _get_skill_data(self, report_id: str, skill_num: int) -> dict:
        """动态加载 skills/<skill>/scripts/extract.py，返回 input_text 和 course_info。"""
        with tracer.start_as_current_span("seewo.skill.fetch_data") as span:
            skill_dir = SKILL_DIRS[skill_num]
            span.set_attribute("skill.name",   SKILL_NAMES[skill_num])
            span.set_attribute("skill.number", skill_num)
            span.set_attribute("report.id",    report_id)

            scripts_dir = str(SKILLS_DIR / skill_dir / "scripts")
            # extract.py 内部有 from seewo_client import，需先把 scripts_dir 加入 sys.path
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)

            # 动态加载 extract.py
            spec = importlib.util.spec_from_file_location(
                f"extract_{skill_num}", os.path.join(scripts_dir, "extract.py")
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            input_text = mod.build_input(report_id, self.token, self.username)
            span.set_attribute("skill.input_text.length", len(input_text))

            # 动态加载 seewo_client.py 取课程信息
            cspec = importlib.util.spec_from_file_location(
                f"seewo_client_{skill_num}", os.path.join(scripts_dir, "seewo_client.py")
            )
            cmod = importlib.util.module_from_spec(cspec)
            cspec.loader.exec_module(cmod)
            course_info = cmod.SeewoClient(report_id, self.token, self.username).get_course_info()

            span.set_attribute("course.name",    course_info.get("课程名称", ""))
            span.set_attribute("course.teacher", course_info.get("教师姓名", ""))
            return {"input_text": input_text, "course_info": course_info}

    # ── 内部：加载 Skill 专属分析指引 ────────────────────────────────
    def _load_skill_guidelines(self, skill_num: int) -> str:
        with tracer.start_as_current_span("seewo.skill.load_prompt") as span:
            span.set_attribute("skill.name", SKILL_NAMES[skill_num])
            skill_md = SKILLS_DIR / SKILL_DIRS[skill_num] / "SKILL.md"
            try:
                content = skill_md.read_text(encoding="utf-8")
                m = re.search(r"```\n(.*?)\n```", content, re.DOTALL)
                prompt = m.group(1).strip() if m else ""
                span.set_attribute("prompt.length", len(prompt))
                return prompt
            except Exception as e:
                span.record_exception(e)
                return ""

    # ── 内部：执行工具调用 ────────────────────────────────────────────
    def _execute_tool(self, tool_name: str, args: dict) -> str:
        """执行工具，返回 JSON 字符串给 LLM。"""
        with tracer.start_as_current_span("seewo.tool.execute") as span:
            span.set_attribute("tool.name", tool_name)
            report_id = args.get("report_id", "").strip()
            span.set_attribute("report.id", report_id)

            skill_num = TOOL_SKILL_MAP.get(tool_name)
            if not skill_num:
                return json.dumps({"error": f"未知工具：{tool_name}"}, ensure_ascii=False)
            if not report_id:
                return json.dumps({"error": "缺少 report_id 参数"}, ensure_ascii=False)

            try:
                skill_data  = self._get_skill_data(report_id, skill_num)
                guidelines  = self._load_skill_guidelines(skill_num)
                result = {
                    "skill":               SKILL_NAMES[skill_num],
                    "course":              skill_data["course_info"],
                    "data":                skill_data["input_text"],
                    "analysis_guidelines": guidelines,
                }
                span.set_attribute("tool.success", True)
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
                    kwargs["tools"]       = TOOLS
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
                                        "必须返回可直接展示给用户的中文分析文本；"
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

                            print(f"  🔧 [{turn}] {tool_name}  report_id={tool_args.get('report_id', '?')}")

                            result_str = self._execute_tool(tool_name, tool_args)

                            # 顺带抓一下课程信息供 CLI 展示
                            if not course_info:
                                try:
                                    obj = json.loads(result_str)
                                    if "course" in obj:
                                        course_info = obj["course"]
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


# ── 交互式 CLI ────────────────────────────────────────────────────────────
def print_banner():
    print("\n" + "=" * 80)
    print("🤖 希沃课堂分析 Agent（ReAct · DeepSeek v4）")
    print("=" * 80)
    print("\n自然语言输入示例：")
    print("  帮我看看这节课的互动情况：https://easiinsight.seewo.com/report/detail/96f58e78.../home")
    print("  分析一下 96f58e78b80c462cb1194fa2f6ef4e97 的提问质量")
    print("  全面分析这个报告 96f58e78b80c462cb1194fa2f6ef4e97")
    print("\n输入 quit 退出")
    print("=" * 80 + "\n")


def main():
    try:
        agent = SeewoAgent()
        print("✓ Agent 初始化成功（ReAct 模式）")
        tf = getattr(_setup_tracing, "trace_file", None)
        if tf:
            print(f"📊 Trace → {tf}（tail -f 可实时查看；设 SEEWO_TRACE_CONSOLE=1 打印到终端）")
        print()
    except Exception as e:
        print(f"❌ 初始化失败：{e}")
        print("请确保 SEEWO_CONFIG.md 中已配置 api_key 和 cookie")
        return

    print_banner()

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
                    print(f"课程：{info.get('课程名称', '')}  "
                          f"教师：{info.get('教师姓名', '')}  "
                          f"学校：{info.get('学校名称', '')}")
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
