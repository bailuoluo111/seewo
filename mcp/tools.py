#!/usr/bin/env python3
"""统一封装希沃课堂观察相关 MCP 工具。"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests

REPORT_ID_SCHEMA = {
    "type": "object",
    "properties": {
        "report_id": {
            "type": "string",
            "description": "课程报告的唯一ID（32位十六进制字符串），可从URL或用户文本中提取。",
        }
    },
    "required": ["report_id"],
}

SKILL_TOOL_SPECS = [
    {
        "name": "analyze_student_interaction",
        "description": (
            "分析学生互动数据：平均抬头率（专注度）、平均举手率（参与意愿）、平均参与度（实际回答比例）。"
            "默认优先使用当前维度数据。"
        ),
        "skill_name": "学生互动分析",
        "skill_dir": "student_interaction",
    },
    {
        "name": "analyze_student_behavior",
        "description": (
            "基于学习金字塔理论分析学习行为分布：7类行为时长占比，估算知识留存率。"
            "默认优先使用当前维度数据。"
        ),
        "skill_name": "学习行为分析",
        "skill_dir": "student_behavior",
    },
    {
        "name": "analyze_solo_classification",
        "description": (
            "基于SOLO分类法评估学生回答建构水平：前结构/单点结构/多点结构/关联结构/抽象拓展五级分布。"
            "默认优先使用当前维度数据。"
        ),
        "skill_name": "SOLO分类分析",
        "skill_dir": "solo_classification",
    },
    {
        "name": "analyze_answer_time",
        "description": (
            "分析学生应答时间分布：≤5秒/5-15秒/>15秒三档，评估问题难度层次和学生思考深度。"
            "默认优先使用当前维度数据。"
        ),
        "skill_name": "应答时间分析",
        "skill_dir": "answer_time",
    },
    {
        "name": "analyze_teacher_speech",
        "description": (
            "分析教师讲授数据：讲授字数、时长、平均语速（字/秒）。参考最佳语速3-4字/秒。"
            "默认优先使用当前维度数据。"
        ),
        "skill_name": "讲授分析",
        "skill_dir": "teacher_speech",
    },
    {
        "name": "analyze_course_reengineering",
        "description": (
            "评估课堂流程重构度：课前→课中、课中→课后链接等级（初阶/进阶/中阶/高阶）。"
            "默认优先使用当前维度数据。"
        ),
        "skill_name": "课堂流程重构",
        "skill_dir": "course_reengineering",
    },
    {
        "name": "analyze_question_effectiveness",
        "description": (
            "综合分析提问有效性：布鲁姆六级提问分类、高阶思维占比、教师理答类型分布、提问有效性得分。"
            "默认优先使用当前维度数据。"
        ),
        "skill_name": "提问有效性分析",
        "skill_dir": "question_effectiveness",
    },
]

ALL_CONTEXT_TOOL = {
    "name": "get_all_classroom_context",
    "description": (
        "获取课堂观察全部7个维度的数据。仅当当前维度数据不足以支撑完整判断，"
        "或需要做跨维度交叉验证、解释差异、补充证据时再使用。"
    ),
    "skill_name": "全量课堂上下文",
    "skill_dir": None,
}

TOOL_SPECS = SKILL_TOOL_SPECS + [ALL_CONTEXT_TOOL]

TOOL_REGISTRY = {
    item["name"]: {
        "tool_name": item["name"],
        "skill_name": item["skill_name"],
        "skill_dir": item["skill_dir"],
        "tool_spec": {
            "name": item["name"],
            "description": item["description"],
            "inputSchema": REPORT_ID_SCHEMA,
        },
    }
    for item in TOOL_SPECS
}

BEHAVIOR_MAP = {
    "0": "听讲", "1": "阅读", "2": "视听", "3": "演示",
    "4": "讨论", "5": "实践", "6": "教给他人",
}
PASSIVE = {"0", "1", "2", "3"}
ACTIVE = {"4", "5", "6"}
RETENTION_RATE = {
    "听讲": 5, "阅读": 10, "视听": 20, "演示": 30,
    "讨论": 50, "实践": 75, "教给他人": 90,
}

SOLO_MAP = {
    "FRONT_STRUCTURE": "前结构",
    "SINGLE_STRUCTURE": "单点结构",
    "MULTI_STRUCTURE": "多点结构",
    "ASSOCIATION_STRUCTURE": "关联结构",
    "ABSTRACT_EXTENDED_STRUCTURE": "抽象拓展",
}
SOLO_ORDER = ["前结构", "单点结构", "多点结构", "关联结构", "抽象拓展"]

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


class SeewoClient:
    """希沃数据 API 的最小客户端。"""

    API_HOST = "https://edulyse.seewo.com"

    def __init__(self, report_id: str, token: str = None, username: str = None):
        self.report_id = report_id
        if not token or not username:
            cfg = self._load_config()
            token = token or os.environ.get("SEEWO_TOKEN") or cfg.get("token")
            username = username or os.environ.get("SEEWO_USERNAME") or cfg.get("username")
        if not token or not username:
            raise ValueError(
                "缺少 token/username：请通过构造参数、环境变量 SEEWO_TOKEN/SEEWO_USERNAME，"
                "或 SEEWO_CONFIG.md 提供"
            )
        self.token = token
        self.username = username
        self.api_template = f"{self.API_HOST}/api/analyse/course/report/{report_id}/{{atype}}"
        self.headers = {
            "Cookie": f"x-token={token}; x-samesite-none-token={token}; x-username={username}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": f"https://easiinsight.seewo.com/report/detail/{report_id}/home",
        }
        self._course_info_cache: Optional[Dict[str, Any]] = None

    @staticmethod
    def _load_config() -> Dict[str, str]:
        candidates = [Path.cwd(), *Path.cwd().parents, Path(__file__).resolve().parent, *Path(__file__).resolve().parents]
        for base in candidates:
            cfg = base / "SEEWO_CONFIG.md"
            if not cfg.exists():
                continue
            try:
                content = cfg.read_text(encoding="utf-8")
                match = re.search(r"^cookie:\s*(.+)$", content, re.MULTILINE)
                if not match:
                    continue
                cookie_str = match.group(1)
                token_match = re.search(r"x-token=([^;]+)", cookie_str)
                username_match = re.search(r"x-username=([^;]+)", cookie_str)
                return {
                    "token": token_match.group(1).strip() if token_match else None,
                    "username": username_match.group(1).strip() if username_match else None,
                }
            except Exception:
                continue
        return {}

    def fetch(self, analysis_type: str) -> Optional[Dict[str, Any]]:
        url = self.api_template.format(atype=analysis_type)
        try:
            resp = requests.get(url, headers=self.headers, timeout=20)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if "code" in data and data["code"] != 0:
                return None
            return data.get("data", {})
        except Exception:
            return None

    def get_course_info(self) -> Dict[str, Any]:
        if self._course_info_cache:
            return self._course_info_cache
        data = self.fetch("studentStudyStatistic")
        if not data:
            return {}

        def ts(v):
            return datetime.fromtimestamp(v / 1000).strftime("%Y-%m-%d %H:%M:%S") if v else None

        self._course_info_cache = {
            "课程ID": data.get("virtualClassUid"),
            "课程名称": data.get("courseName"),
            "教师姓名": data.get("teacherName"),
            "学校名称": data.get("schoolName"),
            "学段": data.get("stageName"),
            "学科": data.get("subjectName"),
            "教室": data.get("roomName"),
            "上课时间": ts(data.get("classStartTime")),
            "下课时间": ts(data.get("classFinishTime")),
        }
        return self._course_info_cache


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
    for item in detail:
        behavior_type = str(item.get("behaviorType"))
        dur[behavior_type] = dur.get(behavior_type, 0) + item.get("durationTimeMills", 0)
    total = sum(dur.values())
    pct = {
        name: round(dur.get(code, 0) / total * 100, 1) if total else 0
        for code, name in BEHAVIOR_MAP.items()
    }
    passive = round(sum(v for k, v in dur.items() if k in PASSIVE) / total * 100, 1) if total else 0
    active = round(sum(v for k, v in dur.items() if k in ACTIVE) / total * 100, 1) if total else 0
    retention = round(sum(pct[name] * rate / 100 for name, rate in RETENTION_RATE.items()), 1)
    return {
        "各行为占比(%)": pct,
        "被动学习占比(%)": passive,
        "主动学习占比(%)": active,
        "估算知识留存率(%)": retention,
    }


def _solo_classification(client: SeewoClient) -> Dict[str, Any]:
    detail = (client.fetch("solo") or {}).get("reportDetail", []) or []
    counts: Dict[str, int] = {}
    for item in detail:
        name = SOLO_MAP.get(item.get("soloAnswerType"))
        if name:
            counts[name] = counts.get(name, 0) + 1
    total = sum(counts.values())
    pct = {name: round(counts.get(name, 0) / total * 100, 1) if total else 0 for name in SOLO_ORDER}
    return {
        "总回答数": total,
        "各等级回答数": {name: counts.get(name, 0) for name in SOLO_ORDER},
        "各等级占比(%)": pct,
    }


def _answer_time(client: SeewoClient) -> Dict[str, Any]:
    detail = (client.fetch("studentAnswerClassification") or {}).get("reportDetail", []) or []
    counts = {"≤5秒": 0, "5-15秒": 0, ">15秒": 0}
    for item in detail:
        start_time, end_time = item.get("startTime"), item.get("endTime")
        if start_time is None or end_time is None:
            continue
        gap = (end_time - start_time) / 1000
        if gap <= 5:
            counts["≤5秒"] += 1
        elif gap <= 15:
            counts["5-15秒"] += 1
        else:
            counts[">15秒"] += 1
    total = sum(counts.values())
    pct = {key: round(counts[key] / total * 100, 1) if total else 0 for key in counts}
    return {"总回答数": total, "各时段回答数": counts, "各时段占比(%)": pct}


def _teacher_speech(client: SeewoClient) -> Dict[str, Any]:
    detail = (client.fetch("speechData") or {}).get("reportDetail", {}) or {}
    word_count = detail.get("speechWordCount", 0)
    duration = detail.get("speechDurationInSeconds", 0)
    return {
        "讲授字数": word_count,
        "讲授时长(秒)": duration,
        "平均语速(字/秒)": round(word_count / duration, 1) if duration else 0,
    }


def _link_detail(link_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not link_data:
        return {"等级": "", "子任务": []}
    tasks = [
        {
            "名称": task.get("name"),
            "分数": SCORE_MAP.get(task.get("score"), task.get("score")),
            "原因": task.get("reason"),
        }
        for task in link_data.get("subTasks", [])
    ]
    return {
        "等级": LEVEL_MAP.get(link_data.get("level"), link_data.get("level", "")),
        "子任务": tasks,
    }


def _course_reengineering(client: SeewoClient) -> Dict[str, Any]:
    detail = (client.fetch("courseProcessReengineering") or {}).get("reportDetail", {}) or {}
    return {
        "课前到课中链接": _link_detail(detail.get("preClassToInClassLink")),
        "课中到课后链接": _link_detail(detail.get("inClassToPostClassLink")),
    }


def _question_effectiveness(client: SeewoClient) -> Dict[str, Any]:
    bloom_detail = (client.fetch("bloom") or {}).get("reportDetail")
    statistics = bloom_detail.get("statistics", []) if isinstance(bloom_detail, dict) else (bloom_detail or [])
    bloom_counts: Dict[str, int] = {}
    for item in statistics:
        name = BLOOM_MAP.get(item.get("problemType"))
        if name:
            bloom_counts[name] = item.get("value", 0)
    total_questions = sum(bloom_counts.values())
    bloom_pct = {
        name: round(bloom_counts.get(name, 0) / total_questions * 100, 1) if total_questions else 0
        for name in BLOOM_ORDER
    }
    high_order = round(sum(bloom_pct[name] for name in HIGH_ORDER), 1)

    appraisals = (client.fetch("teacherAppraisalClassification") or {}).get("reportDetail", []) or []
    appraisal_counts: Dict[str, int] = {}
    for item in appraisals:
        name = APPRAISAL_MAP.get(item.get("teacherAppraisalType"))
        if name:
            appraisal_counts[name] = appraisal_counts.get(name, 0) + 1
    total_appraisals = sum(appraisal_counts.values())
    appraisal_pct = {
        name: round(count / total_appraisals * 100, 1)
        for name, count in appraisal_counts.items()
    } if total_appraisals else {}
    high_quality = round(sum(v for n, v in appraisal_pct.items() if n in HIGH_QUALITY), 1)

    score_detail = (client.fetch("questionScoreExplain") or {}).get("reportDetail", {}) or {}
    return {
        "布鲁姆": {
            "总问题数": total_questions,
            "各等级占比(%)": bloom_pct,
            "高阶思维占比(%)": high_order,
        },
        "理答": {
            "总理答次数": total_appraisals,
            "各类型占比(%)": appraisal_pct,
            "高质量理答占比(%)": high_quality,
        },
        "提问有效性得分": score_detail.get("score"),
    }


def _extract_all(client: SeewoClient) -> Dict[str, Any]:
    return {
        "course_info": client.get_course_info(),
        "student_interaction": _student_interaction(client),
        "student_behavior": _student_behavior(client),
        "solo_classification": _solo_classification(client),
        "answer_time": _answer_time(client),
        "teacher_speech": _teacher_speech(client),
        "course_reengineering": _course_reengineering(client),
        "question_effectiveness": _question_effectiveness(client),
    }


def _tool_payload(tool_name: str, skill_name: str, client: SeewoClient, data: Dict[str, Any], scope: str) -> Dict[str, Any]:
    return {
        "tool": tool_name,
        "skill": skill_name,
        "scope": scope,
        "course": client.get_course_info(),
        "data": data,
    }


def _build_single_dimension_payload(tool_name: str, report_id: str, token: str = None, username: str = None) -> Dict[str, Any]:
    client = SeewoClient(report_id, token, username)
    registry = {
        "analyze_student_interaction": _student_interaction,
        "analyze_student_behavior": _student_behavior,
        "analyze_solo_classification": _solo_classification,
        "analyze_answer_time": _answer_time,
        "analyze_teacher_speech": _teacher_speech,
        "analyze_course_reengineering": _course_reengineering,
        "analyze_question_effectiveness": _question_effectiveness,
    }
    extractor = registry[tool_name]
    meta = TOOL_REGISTRY[tool_name]
    return _tool_payload(tool_name, meta["skill_name"], client, extractor(client), "current_dimension")


def _build_all_context_payload(report_id: str, token: str = None, username: str = None) -> Dict[str, Any]:
    client = SeewoClient(report_id, token, username)
    data = _extract_all(client)
    return {
        "tool": ALL_CONTEXT_TOOL["name"],
        "skill": ALL_CONTEXT_TOOL["skill_name"],
        "scope": "all_dimensions",
        "course": data.get("course_info", {}),
        "data": data,
        "usage_hint": "此工具返回全量课堂数据，应优先提取与当前结论直接相关的少量辅助证据。",
    }


def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    report_id = (arguments.get("report_id") or "").strip()
    if not report_id:
        raise ValueError("缺少 report_id 参数")
    if name == ALL_CONTEXT_TOOL["name"]:
        return _build_all_context_payload(report_id)
    if name not in TOOL_REGISTRY:
        raise ValueError(f"未知工具：{name}")
    return _build_single_dimension_payload(name, report_id)
