#!/usr/bin/env python3
"""
SOLO分类分析 - 数据提取工具（自包含）

提取维度：SOLO五级回答建构的数量与占比
数据来源：solo 接口的 reportDetail（每条含 soloAnswerType）

SOLO 层级：前结构 < 单点结构 < 多点结构 < 关联结构 < 抽象拓展结构
（NO_ANSWER 等非五级项不计入占比）

用法：
    python extract.py <report_id>
"""

import sys
from typing import Dict, Any
from seewo_client import SeewoClient

SOLO_MAP = {
    "FRONT_STRUCTURE": "前结构",
    "SINGLE_STRUCTURE": "单点结构",
    "MULTI_STRUCTURE": "多点结构",
    "ASSOCIATION_STRUCTURE": "关联结构",
    "ABSTRACT_EXTENDED_STRUCTURE": "抽象拓展",
}
SOLO_ORDER = ["前结构", "单点结构", "多点结构", "关联结构", "抽象拓展"]


def extract(report_id: str, token: str = None, username: str = None) -> Dict[str, Any]:
    """提取 SOLO 各等级回答数与占比。"""
    client = SeewoClient(report_id, token, username)
    detail = (client.fetch("solo") or {}).get("reportDetail", []) or []

    cnt: Dict[str, int] = {}
    for it in detail:
        name = SOLO_MAP.get(it.get("soloAnswerType"))
        if name:
            cnt[name] = cnt.get(name, 0) + 1
    total = sum(cnt.values())

    pct = {name: round(cnt.get(name, 0) / total * 100, 1) if total else 0 for name in SOLO_ORDER}
    return {
        "总回答数": total,
        "各等级回答数": {name: cnt.get(name, 0) for name in SOLO_ORDER},
        "各等级占比(%)": pct,
    }


def build_input(report_id: str, token: str = None, username: str = None) -> str:
    """构造喂给 LLM 的输入文本。"""
    d = extract(report_id, token, username)
    p = d["各等级占比(%)"]
    return (
        f"总回答{d['总回答数']}次，前结构{p['前结构']}%，单点{p['单点结构']}%，"
        f"多点{p['多点结构']}%，关联{p['关联结构']}%，抽象拓展{p['抽象拓展']}%"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract.py <report_id>")
        sys.exit(1)
    rid = sys.argv[1]
    print("原始数据:", extract(rid))
    print("LLM输入 :", build_input(rid))
