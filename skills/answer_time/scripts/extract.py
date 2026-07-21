#!/usr/bin/env python3
"""
应答时间分析 - 数据提取工具（自包含）

提取维度：学生回答时长在 ≤5秒 / 5-15秒 / >15秒 三档的分布
数据来源：studentAnswerClassification 接口的 reportDetail（每条含 startTime/endTime）
          回答时长 = (endTime - startTime) / 1000 秒

用法：
    python extract.py <report_id>
"""

import sys
from typing import Dict, Any
from seewo_client import SeewoClient

ORDER = ["≤5秒", "5-15秒", ">15秒"]


def extract(report_id: str, token: str = None, username: str = None) -> Dict[str, Any]:
    """提取应答时间各档回答数与占比。"""
    client = SeewoClient(report_id, token, username)
    detail = (client.fetch("studentAnswerClassification") or {}).get("reportDetail", []) or []

    cnt = {"≤5秒": 0, "5-15秒": 0, ">15秒": 0}
    for it in detail:
        s, e = it.get("startTime"), it.get("endTime")
        if s is None or e is None:
            continue
        g = (e - s) / 1000
        if g <= 5:
            cnt["≤5秒"] += 1
        elif g <= 15:
            cnt["5-15秒"] += 1
        else:
            cnt[">15秒"] += 1
    total = sum(cnt.values())

    pct = {k: round(cnt[k] / total * 100, 1) if total else 0 for k in ORDER}
    return {"总回答数": total, "各时段回答数": cnt, "各时段占比(%)": pct}


def build_input(report_id: str, token: str = None, username: str = None) -> str:
    """构造喂给 LLM 的输入文本。"""
    d = extract(report_id, token, username)
    p = d["各时段占比(%)"]
    return (
        f"总回答{d['总回答数']}次，快速回答(≤5秒){p['≤5秒']}%，"
        f"中等思考(5-15秒){p['5-15秒']}%，深度思考(>15秒){p['>15秒']}%"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract.py <report_id>")
        sys.exit(1)
    rid = sys.argv[1]
    print("原始数据:", extract(rid))
    print("LLM输入 :", build_input(rid))
