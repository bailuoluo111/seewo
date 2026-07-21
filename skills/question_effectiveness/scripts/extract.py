#!/usr/bin/env python3
"""
提问有效性分析 - 数据提取工具（自包含）

综合三个接口：
  bloom                          → 布鲁姆认知层次分布、高阶思维占比、提问总数
  teacherAppraisalClassification → 教师理答类型分布、高质量理答占比
  questionScoreExplain           → 提问有效性综合得分

布鲁姆映射：记忆/理解/应用/分析/评价/创造；高阶思维 = 分析+评价+创造
理答映射（已用真实数据校验）：
  SIMPLE_POSITIVE=简单肯定 TARGETED_POSITIVE=针对肯定 INSPIRE_ENCOURAGE=启发鼓励
  DIRECT_NEGATIVE=否定 REPEAT_QUESTION_OR_STUDENT_ANSWER=重复
  高质量理答 = 启发鼓励

用法：
    python extract.py <report_id>
"""

import sys
from typing import Dict, Any
from seewo_client import SeewoClient

BLOOM_MAP = {
    "REMEMBERING": "记忆", "UNDERSTANDING": "理解", "APPLYING": "应用",
    "ANALYZING": "分析", "EVALUATING": "评价", "CREATING": "创造",
}
BLOOM_ORDER = ["记忆", "理解", "应用", "分析", "评价", "创造"]
HIGH_ORDER = {"分析", "评价", "创造"}

APPRAISAL_MAP = {
    "SIMPLE_POSITIVE": "简单肯定",
    "TARGETED_POSITIVE": "针对肯定",
    "INSPIRE_ENCOURAGE": "启发鼓励",
    "DIRECT_NEGATIVE": "否定",
    "REPEAT_QUESTION_OR_STUDENT_ANSWER": "重复",
}
HIGH_QUALITY = {"启发鼓励"}


def _bloom(client) -> Dict[str, Any]:
    det = (client.fetch("bloom") or {}).get("reportDetail")
    stats = det.get("statistics", []) if isinstance(det, dict) else (det or [])
    cnt = {}
    for it in stats:
        name = BLOOM_MAP.get(it.get("problemType"))
        if name:
            cnt[name] = it.get("value", 0)
    total = sum(cnt.values())
    pct = {n: round(cnt.get(n, 0) / total * 100, 1) if total else 0 for n in BLOOM_ORDER}
    high = round(sum(pct[n] for n in HIGH_ORDER), 1)
    return {"总问题数": total, "各等级占比(%)": pct, "高阶思维占比(%)": high}


def _appraisal(client) -> Dict[str, Any]:
    detail = (client.fetch("teacherAppraisalClassification") or {}).get("reportDetail", []) or []
    cnt = {}
    for it in detail:
        name = APPRAISAL_MAP.get(it.get("teacherAppraisalType"))
        if name:
            cnt[name] = cnt.get(name, 0) + 1
    total = sum(cnt.values())
    pct = {n: round(c / total * 100, 1) for n, c in cnt.items()} if total else {}
    high = round(sum(v for n, v in pct.items() if n in HIGH_QUALITY), 1)
    return {"总理答次数": total, "各类型占比(%)": pct, "高质量理答占比(%)": high}


def extract(report_id: str, token: str = None, username: str = None) -> Dict[str, Any]:
    """提取布鲁姆分类、理答分类、提问有效性得分。"""
    client = SeewoClient(report_id, token, username)
    score = (client.fetch("questionScoreExplain") or {}).get("reportDetail", {}) or {}
    return {
        "bloom": _bloom(client),
        "appraisal": _appraisal(client),
        "提问有效性得分": score.get("score"),
    }


def build_input(report_id: str, token: str = None, username: str = None) -> str:
    """构造喂给 LLM 的输入文本。"""
    d = extract(report_id, token, username)
    return (
        f"总问题{d['bloom']['总问题数']}个，高阶思维占比{d['bloom']['高阶思维占比(%)']}%，"
        f"高质量理答占比{d['appraisal']['高质量理答占比(%)']}%，"
        f"提问有效性得分{d['提问有效性得分']}"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract.py <report_id>")
        sys.exit(1)
    rid = sys.argv[1]
    print("原始数据:", extract(rid))
    print("LLM输入 :", build_input(rid))
