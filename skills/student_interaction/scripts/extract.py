#!/usr/bin/env python3
"""
学生互动分析 - 数据提取工具（自包含）

提取维度：平均抬头率、平均举手率、平均参与度
数据来源：studentStudyStatistic 接口的 reportDetail

用法：
    from extract import extract, build_input
    data = extract(report_id)                 # 取原始维度
    text = build_input(report_id)             # 直接得到可喂给 LLM 的输入串

    # 或命令行：
    python extract.py <report_id>
"""

import sys
from typing import Dict, Any
from seewo_client import SeewoClient


def extract(report_id: str, token: str = None, username: str = None) -> Dict[str, Any]:
    """提取学生互动数据。"""
    client = SeewoClient(report_id, token, username)
    data = client.fetch("studentStudyStatistic") or {}
    detail = data.get("reportDetail", {}) or {}
    return {
        "平均抬头率": round(detail.get("raiseHeadRatio", 0) * 100, 1),
        "平均举手率": round(detail.get("handUpRatio", 0) * 100, 1),
        "平均参与度": round(detail.get("answerRatio", 0) * 100, 1),
    }


def build_input(report_id: str, token: str = None, username: str = None) -> str:
    """构造喂给 LLM 的输入文本（含学段，便于分学段模糊评价）。"""
    client = SeewoClient(report_id, token, username)
    info = client.get_course_info()
    d = extract(report_id, token, username)
    return (
        f"平均抬头率{d['平均抬头率']}%，平均举手率{d['平均举手率']}%，"
        f"平均参与度{d['平均参与度']}%，{info.get('学段', '')}学段"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract.py <report_id>")
        sys.exit(1)
    rid = sys.argv[1]
    print("原始数据:", extract(rid))
    print("LLM输入 :", build_input(rid))
