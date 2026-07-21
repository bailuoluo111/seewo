#!/usr/bin/env python3
"""
view_traces.py — 把 seewo_traces.jsonl 渲染成人类可读的调用树。

用法：
    python view_traces.py                    # 显示最近一次请求
    python view_traces.py --all              # 显示所有请求
    python view_traces.py -n 3               # 显示最近 3 次请求
    python view_traces.py --file other.jsonl
"""

import json
import argparse
from pathlib import Path
from collections import OrderedDict

C_GREEN = "\033[92m"; C_RED = "\033[91m"; C_CYAN = "\033[96m"
C_GRAY = "\033[90m"; C_BOLD = "\033[1m"; C_YELLOW = "\033[93m"; C_END = "\033[0m"

# span 名 → 简短中文标签
LABELS = {
    "seewo.api.analyze":      "API请求",
    "seewo.agent.run":        "Agent总流程",
    "seewo.agent.loop.turn":  "ReAct轮次",
    "seewo.agent.parse_input": "解析输入",
    "seewo.llm.call":         "LLM调用",
    "seewo.tool.execute":     "工具执行",
    "seewo.skill.fetch_data": "抓取数据",
    "seewo.skill.load_prompt": "读取Prompt",
}

# 每个 span 重点展示的 attribute：(attr键, 显示名)
KEY_ATTRS = {
    "seewo.llm.call":         [("llm.tokens.total", "tokens"), ("llm.tool_calls.count", "工具数")],
    "seewo.tool.execute":     [("tool.name", "工具")],
    "seewo.skill.fetch_data": [("skill.name", "维度"), ("course.name", "课程")],
    "seewo.agent.run":        [("tool_calls.total", "总工具数"), ("loop.turns_total", "总轮次")],
}


def load_spans(path: Path):
    """读紧凑 JSONL，按出现顺序分组为若干请求（同 trace 短ID 连续出现）。"""
    if not path.exists():
        print(f"{C_RED}找不到文件：{path}{C_END}")
        return []
    groups = OrderedDict()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            s = json.loads(line)
        except json.JSONDecodeError:
            continue
        groups.setdefault(s.get("trace", "?"), []).append(s)
    return list(groups.values())


def render_group(spans, idx):
    # span 按开始时间排序；用缩进近似层级（compact 格式无 parent_id，按耗时嵌套推断不可靠，
    # 故按记录顺序平铺，用颜色和标签区分）
    dur_total = max((s["dur_ms"] for s in spans), default=0)
    t0 = spans[0]["t"] if spans else "?"
    print(f"{C_BOLD}{'─' * 70}{C_END}")
    print(f"{C_BOLD}请求 {idx}{C_END}  {C_GRAY}{t0}  trace={spans[0].get('trace','?')}  "
          f"共{len(spans)}个span  总耗时≈{dur_total:.0f}ms{C_END}")

    for s in spans:
        name = s["span"]
        label = LABELS.get(name, name)
        status = s.get("status", "UNSET")
        color = C_GREEN if status == "OK" else (C_RED if status == "ERROR" else C_GRAY)
        bar = _mini_bar(s["dur_ms"], dur_total)

        # 关键 attributes
        attrs = s.get("attrs", {})
        extras = []
        for k, disp in KEY_ATTRS.get(name, []):
            if k in attrs:
                extras.append(f"{disp}={attrs[k]}")
        extra_str = f"  {C_YELLOW}{' '.join(extras)}{C_END}" if extras else ""

        print(f"  {color}{label:<12}{C_END} {s['dur_ms']:>7.0f}ms {bar}{extra_str}")


def _mini_bar(dur, total, width=20):
    if not total:
        return ""
    n = int(dur / total * width)
    return C_CYAN + "█" * n + C_GRAY + "·" * (width - n) + C_END


def main():
    p = argparse.ArgumentParser(description="查看 Seewo trace")
    p.add_argument("--file", default=str(Path(__file__).parent / "seewo_traces.jsonl"))
    p.add_argument("--all", action="store_true", help="显示全部请求")
    p.add_argument("-n", type=int, default=1, help="显示最近 N 次请求（默认1）")
    args = p.parse_args()

    groups = load_spans(Path(args.file))
    if not groups:
        print("没有可显示的 trace")
        return

    show = groups if args.all else groups[-args.n:]
    print(f"\n{C_BOLD}🌳 Trace 查看器{C_END}  文件共 {len(groups)} 次请求，显示 {len(show)} 次\n")
    base = len(groups) - len(show) + 1
    for i, g in enumerate(show):
        render_group(g, base + i)
    print()


if __name__ == "__main__":
    main()
