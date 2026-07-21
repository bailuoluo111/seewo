#!/usr/bin/env python3
"""
课堂流程重构 - 数据提取工具（自包含）

提取维度：课前→课中链接等级、课中→课后链接等级（含各子任务明细）
数据来源：courseProcessReengineering 接口的 reportDetail

等级映射（已用真实数据校验）：
    BEGINNER_LEVEL=初阶 PROGRESSIVE_LEVEL=进阶 INTERMEDIATE_LEVEL=中阶 ADVANCED_LEVEL=高阶
子任务分数：
    NO_REFACTOR=无重构 PRELIMINARY_REFACTOR=初步重构 GOOD_REFACTOR=良好重构 EXCELLENT_REFACTOR=优秀重构

用法：
    python extract.py <report_id>
"""

import sys
from typing import Dict, Any
from seewo_client import SeewoClient

LEVEL_MAP = {
    "BEGINNER_LEVEL": "初阶",
    "PROGRESSIVE_LEVEL": "进阶",
    "INTERMEDIATE_LEVEL": "中阶",
    "ADVANCED_LEVEL": "高阶",
}
SCORE_MAP = {
    "NO_REFACTOR": "无重构",
    "PRELIMINARY_REFACTOR": "初步重构",
    "GOOD_REFACTOR": "良好重构",
    "EXCELLENT_REFACTOR": "优秀重构",
}


def _link(link_data) -> Dict[str, Any]:
    if not link_data:
        return {"等级": "", "子任务": []}
    tasks = [
        {
            "名称": t.get("name"),
            "分数": SCORE_MAP.get(t.get("score"), t.get("score")),
            "原因": t.get("reason"),
        }
        for t in link_data.get("subTasks", [])
    ]
    return {"等级": LEVEL_MAP.get(link_data.get("level"), link_data.get("level")), "子任务": tasks}


def extract(report_id: str, token: str = None, username: str = None) -> Dict[str, Any]:
    """提取课前→课中、课中→课后链接的等级与子任务。"""
    client = SeewoClient(report_id, token, username)
    detail = (client.fetch("courseProcessReengineering") or {}).get("reportDetail", {}) or {}
    return {
        "课前到课中链接": _link(detail.get("preClassToInClassLink")),
        "课中到课后链接": _link(detail.get("inClassToPostClassLink")),
    }


def build_input(report_id: str, token: str = None, username: str = None) -> str:
    """构造喂给 LLM 的输入文本。"""
    d = extract(report_id, token, username)
    return (
        f"课前到课中链接等级：{d['课前到课中链接']['等级']}，"
        f"课中到课后链接等级：{d['课中到课后链接']['等级']}"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract.py <report_id>")
        sys.exit(1)
    rid = sys.argv[1]
    print("原始数据:", extract(rid))
    print("LLM输入 :", build_input(rid))
