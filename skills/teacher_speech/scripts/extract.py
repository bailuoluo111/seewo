#!/usr/bin/env python3
"""
讲授分析 - 数据提取工具（自包含）

提取维度：讲授字数、讲授时长、平均语速
数据来源：speechData 接口的 reportDetail
          平均语速 = speechWordCount / speechDurationInSeconds（字/秒）

用法：
    python extract.py <report_id>
"""

import sys
from typing import Dict, Any
from seewo_client import SeewoClient


def extract(report_id: str, token: str = None, username: str = None) -> Dict[str, Any]:
    """提取讲授字数、时长、语速。"""
    client = SeewoClient(report_id, token, username)
    detail = (client.fetch("speechData") or {}).get("reportDetail", {}) or {}
    wc = detail.get("speechWordCount", 0)
    dur = detail.get("speechDurationInSeconds", 0)
    return {
        "讲授字数": wc,
        "讲授时长(秒)": dur,
        "平均语速(字/秒)": round(wc / dur, 1) if dur else 0,
    }


def build_input(report_id: str, token: str = None, username: str = None) -> str:
    """构造喂给 LLM 的输入文本。"""
    d = extract(report_id, token, username)
    return (
        f"讲授字数{d['讲授字数']}字，讲授时长{d['讲授时长(秒)']}秒，"
        f"平均语速{d['平均语速(字/秒)']}字/秒"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract.py <report_id>")
        sys.exit(1)
    rid = sys.argv[1]
    print("原始数据:", extract(rid))
    print("LLM输入 :", build_input(rid))
