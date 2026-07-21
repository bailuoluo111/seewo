#!/usr/bin/env python3
"""
test_api.py — 调用正在运行的 Seewo Agent API，直观展示效果。

模拟测评平台的真实调用方式：通过 HTTP 请求 /analyze，
把返回的 answer / metrics / trace 调用树格式化打印。

前置：先启动服务
    python api.py

运行：
    python test_api.py
    python test_api.py --url http://localhost:8000
    python test_api.py --input "分析 96f58e78b80c462cb1194fa2f6ef4e97 的提问质量"
"""

import sys
import argparse
import requests

DEFAULT_URL = "http://localhost:8000"

# 默认演示的几个场景（覆盖不同能力）
DEMO_CASES = [
    "帮我看看这节课的学生互动：https://easiinsight.seewo.com/report/detail/96f58e78b80c462cb1194fa2f6ef4e97/home",
    "96f58e78b80c462cb1194fa2f6ef4e97 的提问质量怎么样",
    "全面分析一下报告 96f58e78b80c462cb1194fa2f6ef4e97",
    "你好，你能做什么？",
]

C_GREEN = "\033[92m"; C_RED = "\033[91m"; C_CYAN = "\033[96m"
C_GRAY = "\033[90m"; C_BOLD = "\033[1m"; C_END = "\033[0m"


def check_health(base_url: str) -> bool:
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        if r.status_code == 200:
            print(f"{C_GREEN}✓ 服务在线{C_END}  {r.json()}\n")
            return True
    except requests.exceptions.ConnectionError:
        pass
    print(f"{C_RED}✗ 连不上服务 {base_url}{C_END}")
    print("  请先启动： python api.py\n")
    return False


def render_trace_tree(spans: list):
    """把扁平 span 列表还原成缩进调用树。"""
    by_id = {s["span_id"]: s for s in spans}
    children = {}
    for s in spans:
        children.setdefault(s["parent_span_id"], []).append(s)

    def walk(span_id, depth):
        s = by_id.get(span_id)
        if not s:
            return
        status = s["status"]
        color = C_GREEN if status == "OK" else (C_RED if status == "ERROR" else C_GRAY)
        indent = "  " * depth
        print(f"    {indent}{color}├─ {s['name']:<26}{C_END} "
              f"{s['duration_ms']:>8.0f}ms  {color}{status}{C_END}")
        for c in sorted(children.get(span_id, []), key=lambda x: x["start_time"]):
            walk(c["span_id"], depth + 1)

    for root in children.get(None, []):
        walk(root["span_id"], 0)


def run_case(base_url: str, user_input: str, idx: int = None):
    title = f"用例 {idx}" if idx is not None else "请求"
    print(f"{C_BOLD}{'=' * 78}{C_END}")
    print(f"{C_BOLD}{title}{C_END}  📝 {user_input}")
    print(f"{C_BOLD}{'=' * 78}{C_END}")

    try:
        r = requests.post(f"{base_url}/analyze",
                          json={"input": user_input, "include_trace": True},
                          timeout=120)
    except requests.exceptions.RequestException as e:
        print(f"{C_RED}请求失败: {e}{C_END}\n")
        return

    if r.status_code != 200:
        print(f"{C_RED}HTTP {r.status_code}: {r.text[:200]}{C_END}\n")
        return

    d = r.json()

    # ── 输出 ──
    if d["success"]:
        info = d.get("course_info") or {}
        if info.get("课程名称"):
            print(f"\n{C_CYAN}课程{C_END}：{info.get('课程名称')} / {info.get('教师姓名')} / "
                  f"{info.get('学校名称')}（{info.get('学段')}{info.get('学科')}）")
        print(f"\n{C_CYAN}💬 回答{C_END}：\n{d['answer']}\n")
    else:
        print(f"\n{C_RED}❌ {d.get('error')}{C_END}\n")

    # ── 指标 ──
    m = d.get("metrics") or {}
    tok = m.get("tokens", {})
    print(f"{C_CYAN}📊 指标{C_END}：")
    print(f"    总耗时      {m.get('total_duration_ms')} ms")
    print(f"    ReAct 轮次  {m.get('turns')}")
    print(f"    工具调用    {m.get('tool_calls')} 次  {m.get('tools_used')}")
    print(f"    LLM 调用    {m.get('llm_calls')} 次")
    print(f"    Token       输入 {tok.get('prompt')} + 输出 {tok.get('completion')} = {tok.get('total')}")
    print(f"    是否报错    {m.get('has_error')}")

    # ── trace 调用树 ──
    trace = d.get("trace") or []
    if trace:
        print(f"\n{C_CYAN}🌳 Trace 调用树{C_END}（{len(trace)} 个 span，trace_id={d.get('trace_id', '')[:18]}…）：")
        render_trace_tree(trace)
    print()


def main():
    p = argparse.ArgumentParser(description="测试 Seewo Agent API")
    p.add_argument("--url", default=DEFAULT_URL, help="API 地址")
    p.add_argument("--input", help="只测这一条输入（不给则跑内置演示用例）")
    args = p.parse_args()

    print(f"\n{C_BOLD}🧪 Seewo Agent API 测试{C_END}  → {args.url}\n")
    if not check_health(args.url):
        sys.exit(1)

    if args.input:
        run_case(args.url, args.input)
    else:
        for i, case in enumerate(DEMO_CASES, 1):
            run_case(args.url, case, i)

    print(f"{C_GREEN}✓ 测试完成{C_END}\n")


if __name__ == "__main__":
    main()
