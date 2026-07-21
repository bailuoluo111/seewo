#!/usr/bin/env python3
"""
extract_all.py — 一次性提取全部7个维度的课堂数据（自包含）

每个 Skill 优先使用自己维度的 extract.py，
但可选地调用本脚本获取所有维度数据（用于跨维度分析或参考）。

只依赖同目录的 seewo_client.py，无其他项目内部依赖。

返回结构（extract_all）：
{
    "course_info":           {...},   # 课程基本信息
    "student_interaction":   {...},   # 学生互动：抬头率/举手率/参与度
    "student_behavior":      {...},   # 学习行为：7类占比+知识留存率
    "solo_classification":   {...},   # 回答建构：SOLO五级占比
    "answer_time":           {...},   # 应答时间：三档分布
    "teacher_speech":        {...},   # 讲授分析：字数/时长/语速
    "course_reengineering":  {...},   # 课堂流程重构：链接等级
    "question_effectiveness":{...},   # 提问有效性：布鲁姆+理答+得分
}

用法：
    python extract_all.py <report_id>
"""

import sys
from typing import Dict, Any, Optional
from seewo_client import SeewoClient

# ── 枚举映射 ─────────────────────────────────────────────────────────

BEHAVIOR_MAP = {
    "0": "听讲", "1": "阅读", "2": "视听", "3": "演示",
    "4": "讨论", "5": "实践", "6": "教给他人",
}
PASSIVE = {"0", "1", "2", "3"}
ACTIVE  = {"4", "5", "6"}
RETENTION_RATE = {"听讲": 5, "阅读": 10, "视听": 20, "演示": 30,
                  "讨论": 50, "实践": 75, "教给他人": 90}

SOLO_MAP = {
    "FRONT_STRUCTURE": "前结构", "SINGLE_STRUCTURE": "单点结构",
    "MULTI_STRUCTURE": "多点结构", "ASSOCIATION_STRUCTURE": "关联结构",
    "ABSTRACT_EXTENDED_STRUCTURE": "抽象拓展",
}
SOLO_ORDER = ["前结构", "单点结构", "多点结构", "关联结构", "抽象拓展"]

BLOOM_MAP = {
    "REMEMBERING": "记忆", "UNDERSTANDING": "理解", "APPLYING": "应用",
    "ANALYZING": "分析", "EVALUATING": "评价", "CREATING": "创造",
}
BLOOM_ORDER = ["记忆", "理解", "应用", "分析", "评价", "创造"]
HIGH_ORDER  = {"分析", "评价", "创造"}

APPRAISAL_MAP = {
    "SIMPLE_POSITIVE": "简单肯定",
    "TARGETED_POSITIVE": "针对肯定",
    "INSPIRE_ENCOURAGE": "启发鼓励",
    "DIRECT_NEGATIVE": "否定",
    "REPEAT_QUESTION_OR_STUDENT_ANSWER": "重复",
}
HIGH_QUALITY = {"启发鼓励"}

LEVEL_MAP = {
    "BEGINNER_LEVEL": "初阶", "PROGRESSIVE_LEVEL": "进阶",
    "INTERMEDIATE_LEVEL": "中阶", "ADVANCED_LEVEL": "高阶",
}
SCORE_MAP = {
    "NO_REFACTOR": "无重构", "PRELIMINARY_REFACTOR": "初步重构",
    "GOOD_REFACTOR": "良好重构", "EXCELLENT_REFACTOR": "优秀重构",
}

# ── 各维度提取函数 ─────────────────────────────────────────────────────

def _student_interaction(client: SeewoClient) -> Dict[str, Any]:
    data = (client.fetch("studentStudyStatistic") or {}).get("reportDetail", {}) or {}
    return {
        "平均抬头率(%)": round(data.get("raiseHeadRatio", 0) * 100, 1),
        "平均举手率(%)": round(data.get("handUpRatio", 0) * 100, 1),
        "平均参与度(%)": round(data.get("answerRatio", 0) * 100, 1),
    }


def _student_behavior(client: SeewoClient) -> Dict[str, Any]:
    detail = (client.fetch("studentStudyBehavior") or {}).get("reportDetail", []) or []
    dur: Dict[str, float] = {}
    for it in detail:
        bt = str(it.get("behaviorType"))
        dur[bt] = dur.get(bt, 0) + it.get("durationTimeMills", 0)
    total = sum(dur.values())
    pct = {name: round(dur.get(code, 0) / total * 100, 1) if total else 0
           for code, name in BEHAVIOR_MAP.items()}
    passive = round(sum(v for k, v in dur.items() if k in PASSIVE) / total * 100, 1) if total else 0
    active  = round(sum(v for k, v in dur.items() if k in ACTIVE) / total * 100, 1) if total else 0
    retention = round(sum(pct[n] * r / 100 for n, r in RETENTION_RATE.items()), 1)
    return {"各行为占比(%)": pct, "被动学习占比(%)": passive, "主动学习占比(%)": active,
            "估算知识留存率(%)": retention}


def _solo_classification(client: SeewoClient) -> Dict[str, Any]:
    detail = (client.fetch("solo") or {}).get("reportDetail", []) or []
    cnt: Dict[str, int] = {}
    for it in detail:
        name = SOLO_MAP.get(it.get("soloAnswerType"))
        if name:
            cnt[name] = cnt.get(name, 0) + 1
    total = sum(cnt.values())
    pct = {n: round(cnt.get(n, 0) / total * 100, 1) if total else 0 for n in SOLO_ORDER}
    return {"总回答数": total,
            "各等级回答数": {n: cnt.get(n, 0) for n in SOLO_ORDER},
            "各等级占比(%)": pct}


def _answer_time(client: SeewoClient) -> Dict[str, Any]:
    detail = (client.fetch("studentAnswerClassification") or {}).get("reportDetail", []) or []
    cnt = {"≤5秒": 0, "5-15秒": 0, ">15秒": 0}
    for it in detail:
        s, e = it.get("startTime"), it.get("endTime")
        if s is None or e is None:
            continue
        g = (e - s) / 1000
        if g <= 5:   cnt["≤5秒"] += 1
        elif g <= 15: cnt["5-15秒"] += 1
        else:         cnt[">15秒"] += 1
    total = sum(cnt.values())
    pct = {k: round(cnt[k] / total * 100, 1) if total else 0 for k in cnt}
    return {"总回答数": total, "各时段回答数": cnt, "各时段占比(%)": pct}


def _teacher_speech(client: SeewoClient) -> Dict[str, Any]:
    detail = (client.fetch("speechData") or {}).get("reportDetail", {}) or {}
    wc  = detail.get("speechWordCount", 0)
    dur = detail.get("speechDurationInSeconds", 0)
    return {"讲授字数": wc, "讲授时长(秒)": dur,
            "平均语速(字/秒)": round(wc / dur, 1) if dur else 0}


def _link_detail(link_data: Optional[Dict]) -> Dict[str, Any]:
    if not link_data:
        return {"等级": "", "子任务": []}
    tasks = [{"名称": t.get("name"),
               "分数": SCORE_MAP.get(t.get("score"), t.get("score")),
               "原因": t.get("reason")}
             for t in link_data.get("subTasks", [])]
    return {"等级": LEVEL_MAP.get(link_data.get("level"), link_data.get("level", "")),
            "子任务": tasks}


def _course_reengineering(client: SeewoClient) -> Dict[str, Any]:
    detail = (client.fetch("courseProcessReengineering") or {}).get("reportDetail", {}) or {}
    return {"课前到课中链接": _link_detail(detail.get("preClassToInClassLink")),
            "课中到课后链接": _link_detail(detail.get("inClassToPostClassLink"))}


def _question_effectiveness(client: SeewoClient) -> Dict[str, Any]:
    # 布鲁姆
    det = (client.fetch("bloom") or {}).get("reportDetail")
    stats = det.get("statistics", []) if isinstance(det, dict) else (det or [])
    bloom_cnt = {}
    for it in stats:
        n = BLOOM_MAP.get(it.get("problemType"))
        if n:
            bloom_cnt[n] = it.get("value", 0)
    total_q = sum(bloom_cnt.values())
    bloom_pct = {n: round(bloom_cnt.get(n, 0) / total_q * 100, 1) if total_q else 0
                 for n in BLOOM_ORDER}
    high_order = round(sum(bloom_pct[n] for n in HIGH_ORDER), 1)

    # 理答
    appr = (client.fetch("teacherAppraisalClassification") or {}).get("reportDetail", []) or []
    appr_cnt: Dict[str, int] = {}
    for it in appr:
        n = APPRAISAL_MAP.get(it.get("teacherAppraisalType"))
        if n:
            appr_cnt[n] = appr_cnt.get(n, 0) + 1
    total_a = sum(appr_cnt.values())
    appr_pct = {n: round(c / total_a * 100, 1) for n, c in appr_cnt.items()} if total_a else {}
    high_q = round(sum(v for n, v in appr_pct.items() if n in HIGH_QUALITY), 1)

    # 得分
    score_det = (client.fetch("questionScoreExplain") or {}).get("reportDetail", {}) or {}

    return {
        "布鲁姆": {"总问题数": total_q, "各等级占比(%)": bloom_pct, "高阶思维占比(%)": high_order},
        "理答":   {"总理答次数": total_a, "各类型占比(%)": appr_pct, "高质量理答占比(%)": high_q},
        "提问有效性得分": score_det.get("score"),
    }


# ── 主入口 ───────────────────────────────────────────────────────────

def extract_all(report_id: str, token: str = None, username: str = None) -> Dict[str, Any]:
    """一次性提取全部7个维度的数据，返回按模块组织的字典。"""
    client = SeewoClient(report_id, token, username)
    return {
        "course_info":            client.get_course_info(),
        "student_interaction":    _student_interaction(client),
        "student_behavior":       _student_behavior(client),
        "solo_classification":    _solo_classification(client),
        "answer_time":            _answer_time(client),
        "teacher_speech":         _teacher_speech(client),
        "course_reengineering":   _course_reengineering(client),
        "question_effectiveness": _question_effectiveness(client),
    }


if __name__ == "__main__":
    import json
    if len(sys.argv) < 2:
        print("用法: python extract_all.py <report_id>")
        sys.exit(1)
    result = extract_all(sys.argv[1])
    # 打印时隐藏过长的子任务原因文本，避免刷屏
    def _trim(obj, max_len=80):
        if isinstance(obj, dict):
            return {k: _trim(v, max_len) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_trim(i, max_len) for i in obj]
        if isinstance(obj, str) and len(obj) > max_len:
            return obj[:max_len] + "…"
        return obj
    print(json.dumps(_trim(result), ensure_ascii=False, indent=2))
