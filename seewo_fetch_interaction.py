#!/usr/bin/env python3
"""
seewo_fetch_interaction.py — 抓取课堂观察 7 个模块的数据并提取关键指标

基于开发者接口文档，页面报告接口统一为：
  GET /api/analyse/course/report/{reportId}/{analysisType}
响应结构：{ analysisStatus, analysisType, version, reportDetail: {...} }

抓取策略：
  1. 复用/建立登录态，校验 cookie 非空
  2. 打开报告页拿到有效会话
  3. 用浏览器上下文 request API 直接遍历所有 analysisType 接口（自动带 cookie）
  4. 解析并计算关键指标
  5. 保存到 seewo_extracted_data.json

用法：
  python seewo_fetch_interaction.py
"""

import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

REPORT_ID = "96f58e78b80c462cb1194fa2f6ef4e97"
BASE_URL = "https://easiinsight.seewo.com"        # 报告页面域名
API_HOST = "https://edulyse.seewo.com"            # 后端 API 域名（与页面不同源）
REPORT_URL = f"{BASE_URL}/report/detail/{REPORT_ID}/home"
API_TMPL = f"{API_HOST}/api/analyse/course/report/{REPORT_ID}/{{atype}}"
STATE_FILE = "seewo_state.json"
OUTPUT_FILE = "seewo_extracted_data.json"

# 需要抓取的模块（仅输入数据接口）
MODULES = [
    # 学生页
    {"type": "studentStudyStatistic", "name": "学生互动数据", "page": "学生页"},
    {"type": "studentStudyBehavior", "name": "学习行为分布", "page": "学生页"},
    {"type": "solo", "name": "回答建构分类", "page": "学生页"},
    {"type": "studentAnswerClassification", "name": "应答时间", "page": "学生页"},
    # 教师页
    {"type": "speechData", "name": "讲授分析", "page": "教师页"},
    {"type": "courseProcessReengineering", "name": "课堂流程重构", "page": "教师页"},
    {"type": "questionRecord", "name": "提问记录", "page": "教师页"},
    {"type": "questionAnswerExtraResult", "name": "问答额外结果", "page": "教师页"},
    {"type": "bloom", "name": "布鲁姆提问分类", "page": "教师页"},
    {"type": "teacherAppraisalClassification", "name": "教师理答分类", "page": "教师页"},
    {"type": "questionScoreExplain", "name": "提问有效性得分", "page": "教师页"},
]


def state_has_cookies(path: str) -> bool:
    """校验登录态里是否真的存了 cookie"""
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        return len(state.get("cookies", [])) > 0
    except Exception:
        return False


def looks_logged_in(page) -> bool:
    try:
        content = page.content()
        return "/report/detail/" in page.url and "扫码" not in content[:8000]
    except Exception:
        return False


# ────────────────────────────────────────────────────────────
# 数据提取和计算函数
# ────────────────────────────────────────────────────────────

def extract_course_info(data: dict) -> dict:
    """提取课程基础信息"""
    if not data:
        return {}

    def format_timestamp(ts):
        if ts:
            return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
        return None

    return {
        "课程ID": data.get("virtualClassUid"),
        "课程名称": data.get("courseName"),
        "教师姓名": data.get("teacherName"),
        "学校名称": data.get("schoolName"),
        "学段": data.get("stageName"),
        "学科": data.get("subjectName"),
        "教室": data.get("roomName"),
        "上课时间": format_timestamp(data.get("classStartTime")),
        "下课时间": format_timestamp(data.get("classFinishTime")),
    }


def extract_student_interaction(detail: dict) -> dict:
    """提取学生互动数据"""
    if not detail:
        return {}

    def to_percent(val):
        return round(val * 100, 1) if isinstance(val, (int, float)) else None

    return {
        "平均抬头率": to_percent(detail.get("raiseHeadRatio")),
        "平均举手率": to_percent(detail.get("handUpRatio")),
        "平均参与度": to_percent(detail.get("answerRatio")),
    }


def extract_student_behavior(detail: list) -> dict:
    """提取学习行为分布并计算指标"""
    if not detail or not isinstance(detail, list):
        return {}

    # behaviorType 映射（根据实际数据，3可能代表某种行为类型）
    # 需要根据实际业务确定映射关系
    # 暂时统计时长即可
    total_duration = 0
    behavior_types = {}

    for item in detail:
        start = item.get("startTime")
        end = item.get("endTime")
        behavior_type = item.get("behaviorType")

        if start and end:
            duration = (end - start) / 1000  # 转换为秒
            total_duration += duration

            if behavior_type is not None:
                behavior_types[behavior_type] = behavior_types.get(behavior_type, 0) + duration

    result = {
        "总时长(秒)": round(total_duration, 1),
        "各行为类型时长(秒)": {str(k): round(v, 1) for k, v in behavior_types.items()},
    }

    # 计算占比
    if total_duration > 0:
        occupancy = {}
        for behavior_type, duration in behavior_types.items():
            occupancy[str(behavior_type)] = round(duration / total_duration * 100, 1)
        result["各行为类型占比(%)"] = occupancy

    return result


def extract_solo_classification(detail: list) -> dict:
    """提取SOLO分类并计算占比"""
    if not detail or not isinstance(detail, list):
        return {}

    # SOLO类型映射
    SOLO_TYPE_MAP = {
        "FRONT_STRUCTURE": "前结构",
        "SINGLE_STRUCTURE": "单点结构",
        "MULTI_STRUCTURE": "多点结构",
        "ASSOCIATION_STRUCTURE": "关联结构",
        "ABSTRACT_EXTENDED_STRUCTURE": "抽象拓展",
    }

    solo_stats = {}
    total_count = len(detail)

    for item in detail:
        solo_type = item.get("soloAnswerType")
        if solo_type:
            level_name = SOLO_TYPE_MAP.get(solo_type, solo_type)
            solo_stats[level_name] = solo_stats.get(level_name, 0) + 1

    result = {
        "总回答数": total_count,
        "各等级回答数": solo_stats,
    }

    # 计算占比
    if total_count > 0:
        occupancy = {}
        for level_name, count in solo_stats.items():
            occupancy[level_name] = round(count / total_count * 100, 1)
        result["各等级占比(%)"] = occupancy

    return result


def extract_answer_time(detail: list) -> dict:
    """提取应答时间并计算时段分布"""
    if not detail or not isinstance(detail, list):
        return {}

    # 时段统计
    time_ranges = {
        "≤5秒": 0,
        "5-15秒": 0,
        ">15秒": 0,
    }

    total_count = 0

    for item in detail:
        start = item.get("startTime")
        end = item.get("endTime")

        if start and end:
            duration = (end - start) / 1000  # 转换为秒
            total_count += 1

            if duration <= 5:
                time_ranges["≤5秒"] += 1
            elif duration <= 15:
                time_ranges["5-15秒"] += 1
            else:
                time_ranges[">15秒"] += 1

    result = {
        "总回答数": total_count,
        "各时段回答数": time_ranges,
    }

    # 计算占比
    if total_count > 0:
        occupancy = {}
        for range_name, count in time_ranges.items():
            occupancy[range_name] = round(count / total_count * 100, 1)
        result["各时段占比(%)"] = occupancy

    return result


def extract_speech_data(detail: dict) -> dict:
    """提取讲授分析数据"""
    if not detail:
        return {}

    return {
        "讲授字数": detail.get("speechWordCount"),
        "平均语速(字/秒)": detail.get("speechSpeedPerSecond"),
        "讲授时长(秒)": detail.get("speechDurationInSeconds"),
    }


def extract_course_reengineering(detail: dict) -> dict:
    """提取课堂流程重构数据"""
    if not detail:
        return {}

    def extract_link_data(link_data):
        if not link_data:
            return {}

        result = {
            "等级": link_data.get("level"),
            "子任务": []
        }

        sub_tasks = link_data.get("subTasks", [])
        for task in sub_tasks:
            result["子任务"].append({
                "名称": task.get("name"),
                "分数": task.get("score"),
                "原因": task.get("reason"),
            })

        return result

    return {
        "课前到课中链接": extract_link_data(detail.get("preClassToInClassLink")),
        "课中到课后链接": extract_link_data(detail.get("inClassToPostClassLink")),
    }


def extract_question_record(detail) -> dict:
    """提取提问记录"""
    if not detail:
        return {}

    # 如果是列表，直接使用
    if isinstance(detail, list):
        return {
            "提问总数": len(detail),
            "问题列表": [
                {
                    "问题ID": q.get("questionId"),
                    "问题文本": q.get("questionText") if isinstance(q, dict) else str(q),
                    "提问时间": q.get("questionTime") if isinstance(q, dict) else None,
                }
                for q in detail
            ]
        }

    # 如果是字典，从中提取 questionList
    if isinstance(detail, dict):
        question_list = detail.get("questionList", [])
        return {
            "提问总数": detail.get("questionCount", len(question_list)),
            "问题列表": [
                {
                    "问题ID": q.get("questionId"),
                    "问题文本": q.get("questionText"),
                    "提问时间": q.get("questionTime"),
                }
                for q in question_list
            ] if question_list else []
        }

    return {}


def extract_bloom_classification(detail) -> dict:
    """提取布鲁姆分类并计算占比"""
    if not detail:
        return {}

    # 处理两种可能的结构
    if isinstance(detail, dict):
        # 结构: {statistics: [...], problems: [...]}
        statistics = detail.get("statistics", [])
    elif isinstance(detail, list):
        statistics = detail
    else:
        return {}

    # 布鲁姆类型映射
    BLOOM_TYPE_MAP = {
        "REMEMBERING": "记忆",
        "UNDERSTANDING": "理解",
        "APPLYING": "应用",
        "ANALYZING": "分析",
        "EVALUATING": "评价",
        "CREATING": "创造",
    }

    bloom_stats = {}
    total_count = 0

    for item in statistics:
        problem_type = item.get("problemType")
        count = item.get("value", 0)

        if problem_type:
            level_name = BLOOM_TYPE_MAP.get(problem_type, problem_type)
            bloom_stats[level_name] = count
            total_count += count

    result = {
        "总问题数": total_count,
        "各等级问题数": bloom_stats,
    }

    # 计算占比
    if total_count > 0:
        occupancy = {}
        for level_name, count in bloom_stats.items():
            occupancy[level_name] = round(count / total_count * 100, 1)
        result["各等级占比(%)"] = occupancy

        # 计算高阶思维占比（分析、评价、创造）
        high_order = sum(
            count for level, count in bloom_stats.items()
            if level in ["分析", "评价", "创造"]
        )
        result["高阶思维占比(%)"] = round(high_order / total_count * 100, 1)

    return result


def extract_teacher_appraisal(detail: list) -> dict:
    """提取教师理答分类并计算占比"""
    if not detail or not isinstance(detail, list):
        return {}

    appraisal_stats = {}
    total_count = len(detail)

    # 教师理答类型映射
    APPRAISAL_TYPE_MAP = {
        "SIMPLE_POSITIVE": "简单肯定",
        "TARGETED_POSITIVE": "针对性肯定",
        "INSPIRE_ENCOURAGE": "启发鼓励",
        "SIMPLE_REPEAT": "简单重复",
        "FOLLOW_UP": "追问",
        "EVALUATION": "评价",
        "GUIDANCE": "引导",
    }

    for item in detail:
        appraisal_type = item.get("teacherAppraisalType")
        if appraisal_type:
            type_name = APPRAISAL_TYPE_MAP.get(appraisal_type, appraisal_type)
            appraisal_stats[type_name] = appraisal_stats.get(type_name, 0) + 1

    result = {
        "总理答次数": total_count,
        "各类型次数": appraisal_stats,
    }

    # 计算占比
    if total_count > 0:
        occupancy = {}
        for appraisal_type, count in appraisal_stats.items():
            occupancy[appraisal_type] = round(count / total_count * 100, 1)
        result["各类型占比(%)"] = occupancy

        # 计算高质量理答占比（追问、引导、启发鼓励）
        high_quality = sum(
            count for type_name, count in appraisal_stats.items()
            if type_name in ["追问", "引导", "启发鼓励"]
        )
        result["高质量理答占比(%)"] = round(high_quality / total_count * 100, 1)

    return result


def extract_question_answer_extra(detail) -> dict:
    """提取问答额外结果"""
    if not detail:
        return {}

    # 如果是列表，尝试从第一个元素获取数据
    if isinstance(detail, list):
        if len(detail) > 0 and isinstance(detail[0], dict):
            detail = detail[0]
        else:
            return {}

    # 如果是字典，提取字段
    if isinstance(detail, dict):
        total = detail.get("totalAnswerCount", 0)
        effective = detail.get("effectiveAnswerCount", 0)

        result = {
            "总回答次数": total,
            "有效回答次数": effective,
        }

        if total > 0:
            result["有效回答率(%)"] = round(effective / total * 100, 1)

        return result

    return {}



def extract_question_score(detail: dict) -> dict:
    """提取提问有效性得分"""
    if not detail:
        return {}

    return {
        "提问有效性得分": detail.get("score"),
    }


# 数据提取路由
EXTRACTORS = {
    "studentStudyStatistic": extract_student_interaction,
    "studentStudyBehavior": extract_student_behavior,
    "solo": extract_solo_classification,
    "studentAnswerClassification": extract_answer_time,
    "speechData": extract_speech_data,
    "courseProcessReengineering": extract_course_reengineering,
    "questionRecord": extract_question_record,
    "bloom": extract_bloom_classification,
    "teacherAppraisalClassification": extract_teacher_appraisal,
    "questionAnswerExtraResult": extract_question_answer_extra,
    "questionScoreExplain": extract_question_score,
}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx_kwargs = dict(locale="zh-CN")
        if state_has_cookies(STATE_FILE):
            ctx_kwargs["storage_state"] = STATE_FILE
            print(f"→ 复用登录态 {STATE_FILE}")
        else:
            print("→ 无有效登录态，需手动登录一次")

        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()

        print("→ 打开报告页...")
        page.goto(REPORT_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        if not looks_logged_in(page):
            print("\n请在浏览器中手动登录（扫码或账号密码）。")
            print("务必确认已看到报告内容后，再回终端按回车。")
            input("登录完成后按【回车】继续... ")
            page.goto(REPORT_URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)

        # 保存登录态并校验
        context.storage_state(path=STATE_FILE)
        if not state_has_cookies(STATE_FILE):
            print("\n❌ 登录态仍为空（无 cookie），登录未成功。请重试并确认登录后再按回车。")
            browser.close()
            return
        print("→ 登录态有效，开始遍历接口...\n")

        # 用浏览器上下文的 request API 直接调接口（自动带 cookie）
        raw_results = {}
        course_info = None

        for m in MODULES:
            atype = m["type"]
            url = API_TMPL.format(atype=atype)
            try:
                resp = context.request.get(url, timeout=20000)
                status = resp.status
                if status != 200:
                    print(f"  [{status}] {m['name']} ({atype})")
                    raw_results[atype] = {"module": m, "status": status, "error": True}
                    continue

                data = resp.json()
                inner_data = data.get("data", {})
                detail = inner_data.get("reportDetail")

                # 提取课程信息（只需提取一次）
                if not course_info:
                    course_info = extract_course_info(inner_data)

                raw_results[atype] = {
                    "module": m,
                    "status": status,
                    "reportDetail": detail,
                }

                print(f"  [200] {m['name']} ({atype})")

            except Exception as e:
                print(f"  [ERR] {m['name']} ({atype}): {e}")
                raw_results[atype] = {"module": m, "error": str(e)}

        context.storage_state(path=STATE_FILE)
        browser.close()

    # 保存原始数据用于调试
    with open("seewo_raw_data.json", "w", encoding="utf-8") as f:
        json.dump({
            "report_id": REPORT_ID,
            "raw_results": raw_results,
        }, f, ensure_ascii=False, indent=2)
    print("\n→ 原始数据已保存到 seewo_raw_data.json（用于调试）")

    # 提取和计算关键指标
    print("→ 开始提取和计算关键指标...")

    extracted_data = {
        "report_id": REPORT_ID,
        "course_info": course_info,
        "modules": {}
    }

    for atype, raw in raw_results.items():
        if raw.get("status") == 200:
            detail = raw.get("reportDetail")
            extractor = EXTRACTORS.get(atype)
            module_name = raw["module"]["name"]

            if extractor:
                if detail is None:
                    print(f"  ⚠ {module_name}: reportDetail 为 null")
                    extracted_data["modules"][module_name] = {}
                elif isinstance(detail, list) and len(detail) == 0:
                    print(f"  ⚠ {module_name}: reportDetail 为空列表")
                    extracted_data["modules"][module_name] = {}
                elif isinstance(detail, dict) and len(detail) == 0:
                    print(f"  ⚠ {module_name}: reportDetail 为空字典")
                    extracted_data["modules"][module_name] = {}
                else:
                    try:
                        extracted = extractor(detail)
                        extracted_data["modules"][module_name] = extracted
                        print(f"  ✓ 已提取: {module_name}")
                    except Exception as e:
                        print(f"  ✗ 提取失败: {module_name} - {e}")
                        import traceback
                        traceback.print_exc()

    # 保存提取结果
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=2)

    ok = sum(1 for v in raw_results.values() if v.get("status") == 200)
    print("\n" + "=" * 50)
    print(f"✅ 完成：{ok}/{len(MODULES)} 个接口返回 200")
    print(f"→ 提取的数据已保存到 {OUTPUT_FILE}")

    # 打印课程信息
    if course_info:
        print("\n课程信息：")
        for k, v in course_info.items():
            if v:
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
