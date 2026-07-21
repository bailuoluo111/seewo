#!/usr/bin/env python3
"""
学习行为分析 - 数据提取工具（自包含）

提取维度：学习金字塔7类学习行为的时长占比 + 估算知识留存率
数据来源：studentStudyBehavior 接口的 reportDetail（每条含 behaviorType + durationTimeMills）

behaviorType 映射（按学习金字塔层级顺序，已用前端真实数据校验）：
    0=听讲 1=阅读 2=视听 3=演示 | 4=讨论 5=实践 6=教给他人
    前四类为被动学习，后三类为主动学习。

知识留存率（Edgar Dale 学习金字塔）：
    听讲5% 阅读10% 视听20% 演示30% 讨论50% 实践75% 教给他人90%

用法：
    python extract.py <report_id>
"""

import sys
from typing import Dict, Any
from seewo_client import SeewoClient

# 行为类型 → 名称
BEHAVIOR_MAP = {
    "0": "听讲", "1": "阅读", "2": "视听", "3": "演示",
    "4": "讨论", "5": "实践", "6": "教给他人",
}
PASSIVE = {"0", "1", "2", "3"}
ACTIVE = {"4", "5", "6"}
# 各行为的知识留存率(%)
RETENTION = {"听讲": 5, "阅读": 10, "视听": 20, "演示": 30, "讨论": 50, "实践": 75, "教给他人": 90}


def extract(report_id: str, token: str = None, username: str = None) -> Dict[str, Any]:
    """提取学习行为时长占比、被动/主动学习占比、估算知识留存率。"""
    client = SeewoClient(report_id, token, username)
    detail = (client.fetch("studentStudyBehavior") or {}).get("reportDetail", []) or []

    dur: Dict[str, float] = {}
    for it in detail:
        bt = str(it.get("behaviorType"))
        dur[bt] = dur.get(bt, 0) + it.get("durationTimeMills", 0)
    total = sum(dur.values())

    # 各行为占比（按名称）
    pct = {}
    for code, name in BEHAVIOR_MAP.items():
        pct[name] = round(dur.get(code, 0) / total * 100, 1) if total else 0

    passive = round(sum(v for k, v in dur.items() if k in PASSIVE) / total * 100, 1) if total else 0
    active = round(sum(v for k, v in dur.items() if k in ACTIVE) / total * 100, 1) if total else 0
    retention = round(sum(pct[name] * r / 100 for name, r in RETENTION.items()), 1)

    return {
        "各行为占比(%)": pct,
        "被动学习占比(%)": passive,
        "主动学习占比(%)": active,
        "估算知识留存率(%)": retention,
    }


def build_input(report_id: str, token: str = None, username: str = None) -> str:
    """构造喂给 LLM 的输入文本。"""
    d = extract(report_id, token, username)
    p = d["各行为占比(%)"]
    return (
        f"被动学习{d['被动学习占比(%)']}%（听讲{p['听讲']}%、阅读{p['阅读']}%、"
        f"视听{p['视听']}%、演示{p['演示']}%），"
        f"主动学习{d['主动学习占比(%)']}%（讨论{p['讨论']}%、实践{p['实践']}%、"
        f"教给他人{p['教给他人']}%），估算知识留存率{d['估算知识留存率(%)']}%"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract.py <report_id>")
        sys.exit(1)
    rid = sys.argv[1]
    print("原始数据:", extract(rid))
    print("LLM输入 :", build_input(rid))
