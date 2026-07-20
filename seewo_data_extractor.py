#!/usr/bin/env python3
"""
seewo_data_extractor.py — 模块化的课堂观察数据提取器

每个模块都有独立的提取方法，可以单独调用。
适用于不同的 skill 调用不同模块的数据。

用法：
  from seewo_data_extractor import SeewoDataExtractor

  extractor = SeewoDataExtractor(report_id="...")
  extractor.login()  # 首次使用需要登录

  # 提取单个模块
  student_interaction = extractor.extract_student_interaction()

  # 或提取所有模块
  all_data = extractor.extract_all_modules()
"""

import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
from typing import Dict, List, Optional, Any


class SeewoDataExtractor:
    """希沃课堂观察数据提取器"""

    def __init__(self, report_id: str, state_file: str = "seewo_state.json"):
        """
        初始化提取器

        Args:
            report_id: 报告ID
            state_file: 登录状态保存文件
        """
        self.report_id = report_id
        self.state_file = state_file
        self.base_url = "https://easiinsight.seewo.com"
        self.api_host = "https://edulyse.seewo.com"
        self.report_url = f"{self.base_url}/report/detail/{report_id}/home"
        self.api_template = f"{self.api_host}/api/analyse/course/report/{report_id}/{{atype}}"

        self.context = None
        self.browser = None
        self.playwright = None
        self._course_info_cache = None

    def _has_cookies(self) -> bool:
        """检查是否有有效的登录态"""
        if not os.path.exists(self.state_file):
            return False
        try:
            with open(self.state_file, encoding="utf-8") as f:
                state = json.load(f)
            return len(state.get("cookies", [])) > 0
        except Exception:
            return False

    def _looks_logged_in(self, page) -> bool:
        """检查页面是否已登录"""
        try:
            content = page.content()
            return "/report/detail/" in page.url and "扫码" not in content[:8000]
        except Exception:
            return False

    def login(self, headless: bool = False) -> bool:
        """
        登录希沃平台（如果需要）

        Args:
            headless: 是否无头模式

        Returns:
            是否登录成功
        """
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)

        ctx_kwargs = dict(locale="zh-CN")
        if self._has_cookies():
            ctx_kwargs["storage_state"] = self.state_file
            print(f"→ 复用登录态 {self.state_file}")
        else:
            print("→ 无有效登录态，需手动登录")

        self.context = self.browser.new_context(**ctx_kwargs)
        page = self.context.new_page()

        print("→ 打开报告页...")
        page.goto(self.report_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        if not self._looks_logged_in(page):
            print("\n请在浏览器中手动登录（扫码或账号密码）。")
            print("务必确认已看到报告内容后，再回终端按回车。")
            input("登录完成后按【回车】继续... ")
            page.goto(self.report_url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)

        # 保存登录态
        self.context.storage_state(path=self.state_file)
        page.close()

        if not self._has_cookies():
            print("\n❌ 登录失败")
            return False

        print("✓ 登录成功")
        return True

    def _ensure_context(self):
        """确保浏览器上下文已创建"""
        if self.context is None:
            if not self._has_cookies():
                raise RuntimeError("未登录，请先调用 login() 方法")

            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.context = self.browser.new_context(
                locale="zh-CN",
                storage_state=self.state_file
            )

    def _fetch_api(self, analysis_type: str) -> Optional[Dict]:
        """
        调用接口获取数据

        Args:
            analysis_type: 分析类型

        Returns:
            接口返回的数据，失败返回 None
        """
        self._ensure_context()

        url = self.api_template.format(atype=analysis_type)
        try:
            resp = self.context.request.get(url, timeout=20000)
            if resp.status != 200:
                print(f"  ✗ 接口返回 {resp.status}: {analysis_type}")
                return None

            data = resp.json()
            inner_data = data.get("data", {})
            return inner_data
        except Exception as e:
            print(f"  ✗ 接口调用失败: {analysis_type} - {e}")
            return None

    def close(self):
        """关闭浏览器"""
        if self.context:
            self.context.close()
            self.context = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None

    # ========================================================================
    # 课程基础信息
    # ========================================================================

    def get_course_info(self) -> Dict[str, Any]:
        """
        获取课程基础信息

        Returns:
            包含课程ID、课程名称、教师、学校、学段、学科等信息的字典
        """
        if self._course_info_cache:
            return self._course_info_cache

        # 从任意接口获取课程信息
        data = self._fetch_api("studentStudyStatistic")
        if not data:
            return {}

        def format_timestamp(ts):
            if ts:
                return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
            return None

        info = {
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

        self._course_info_cache = info
        return info

    # ========================================================================
    # 模块1: 学生互动数据
    # ========================================================================

    def extract_student_interaction(self) -> Dict[str, Any]:
        """
        提取学生互动数据

        Returns:
            {
                "平均抬头率": 72.6,
                "平均举手率": 35.8,
                "平均参与度": 16.8
            }
        """
        data = self._fetch_api("studentStudyStatistic")
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

        def to_percent(val):
            return round(val * 100, 1) if isinstance(val, (int, float)) else None

        return {
            "平均抬头率": to_percent(detail.get("raiseHeadRatio")),
            "平均举手率": to_percent(detail.get("handUpRatio")),
            "平均参与度": to_percent(detail.get("answerRatio")),
        }

    # ========================================================================
    # 模块2: 学习行为分布
    # ========================================================================

    def extract_student_behavior(self) -> Dict[str, Any]:
        """
        提取学习行为分布

        Returns:
            {
                "总时长(秒)": 4101.4,
                "各行为类型时长(秒)": {"3": 375.0, "4": 2517.0, "0": 1209.4},
                "各行为类型占比(%)": {"3": 9.1, "4": 61.4, "0": 29.5}
            }
        """
        data = self._fetch_api("studentStudyBehavior")
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail or not isinstance(detail, list):
            return {}

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

    # ========================================================================
    # 模块3: 回答建构分类 (SOLO)
    # ========================================================================

    def extract_solo_classification(self) -> Dict[str, Any]:
        """
        提取SOLO分类

        Returns:
            {
                "总回答数": 13,
                "各等级回答数": {"单点结构": 8, "前结构": 1, ...},
                "各等级占比(%)": {"单点结构": 61.5, "前结构": 7.7, ...}
            }
        """
        data = self._fetch_api("solo")
        if not data:
            return {}

        detail = data.get("reportDetail")
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

    # ========================================================================
    # 模块4: 应答时间
    # ========================================================================

    def extract_answer_time(self) -> Dict[str, Any]:
        """
        提取应答时间分布

        Returns:
            {
                "总回答数": 13,
                "各时段回答数": {"≤5秒": 8, "5-15秒": 4, ">15秒": 1},
                "各时段占比(%)": {"≤5秒": 61.5, "5-15秒": 30.8, ">15秒": 7.7}
            }
        """
        data = self._fetch_api("studentAnswerClassification")
        if not data:
            return {}

        detail = data.get("reportDetail")
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
            for time_range, count in time_ranges.items():
                occupancy[time_range] = round(count / total_count * 100, 1)
            result["各时段占比(%)"] = occupancy

        return result

    # ========================================================================
    # 模块5: 讲授分析
    # ========================================================================

    def extract_speech_data(self) -> Dict[str, Any]:
        """
        提取讲授分析数据

        Returns:
            {
                "讲授字数": 6724,
                "平均语速(字/秒)": 3.9,
                "讲授时长(秒)": 1722
            }
        """
        data = self._fetch_api("speechData")
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

        return {
            "讲授字数": detail.get("speechWordCount"),
            "平均语速(字/秒)": detail.get("speechSpeedPerSecond"),
            "讲授时长(秒)": detail.get("speechDurationInSeconds"),
        }

    # ========================================================================
    # 模块6: 课堂流程重构
    # ========================================================================

    def extract_course_reengineering(self) -> Dict[str, Any]:
        """
        提取课堂流程重构数据

        Returns:
            {
                "课前到课中链接": {
                    "等级": "ADVANCED_LEVEL",
                    "子任务": [{"名称": "...", "分数": "...", "原因": "..."}, ...]
                },
                "课中到课后链接": {
                    "等级": "ADVANCED_LEVEL",
                    "子任务": [...]
                }
            }
        """
        data = self._fetch_api("courseProcessReengineering")
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

        def extract_link_data(link_data):
            if not link_data:
                return {}

            sub_tasks = link_data.get("subTasks", [])

            return {
                "等级": link_data.get("level"),
                "子任务": [
                    {
                        "名称": task.get("name"),
                        "分数": task.get("score"),
                        "原因": task.get("reason"),
                    }
                    for task in sub_tasks
                ] if sub_tasks else []
            }

        return {
            "课前到课中链接": extract_link_data(detail.get("preClassToInClassLink")),
            "课中到课后链接": extract_link_data(detail.get("inClassToPostClassLink")),
        }

    # ========================================================================
    # 模块7: 提问有效性（综合模块）
    # ========================================================================

    def extract_question_effectiveness(self) -> Dict[str, Any]:
        """
        提取提问有效性相关的所有数据

        Returns:
            {
                "提问有效性得分": 71.0,
                "提问记录": {...},
                "布鲁姆分类": {...},
                "教师理答分类": {...},
                "问答统计": {...}
            }
        """
        return {
            "提问有效性得分": self._extract_question_score(),
            "提问记录": self._extract_question_record(),
            "布鲁姆分类": self._extract_bloom_classification(),
            "教师理答分类": self._extract_teacher_appraisal(),
            "问答统计": self._extract_question_answer_extra(),
        }

    def _extract_question_score(self) -> Dict[str, Any]:
        """提取提问有效性得分"""
        data = self._fetch_api("questionScoreExplain")
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

        return {
            "得分": detail.get("score"),
        }

    def _extract_question_record(self) -> Dict[str, Any]:
        """提取提问记录"""
        data = self._fetch_api("questionRecord")
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

        # 兼容list和dict两种结构
        if isinstance(detail, list):
            return {
                "提问总数": len(detail),
                "问题列表": detail
            }

        if isinstance(detail, dict):
            question_list = detail.get("questionList", [])
            return {
                "提问总数": detail.get("questionCount", len(question_list)),
                "问题列表": question_list
            }

        return {}

    def _extract_bloom_classification(self) -> Dict[str, Any]:
        """提取布鲁姆提问分类"""
        data = self._fetch_api("bloom")
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

        # 处理两种可能的结构
        if isinstance(detail, dict):
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

            # 计算高阶思维占比
            high_order = sum(
                count for level, count in bloom_stats.items()
                if level in ["分析", "评价", "创造"]
            )
            result["高阶思维占比(%)"] = round(high_order / total_count * 100, 1)

        return result

    def _extract_teacher_appraisal(self) -> Dict[str, Any]:
        """提取教师理答分类"""
        data = self._fetch_api("teacherAppraisalClassification")
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail or not isinstance(detail, list):
            return {}

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

        appraisal_stats = {}
        total_count = len(detail)

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

            # 计算高质量理答占比
            high_quality = sum(
                count for appraisal_type, count in appraisal_stats.items()
                if appraisal_type in ["追问", "引导", "启发鼓励"]
            )
            result["高质量理答占比(%)"] = round(high_quality / total_count * 100, 1)

        return result

    def _extract_question_answer_extra(self) -> Dict[str, Any]:
        """提取问答额外结果"""
        data = self._fetch_api("questionAnswerExtraResult")
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

        # 兼容list和dict两种结构
        if isinstance(detail, list):
            if len(detail) > 0 and isinstance(detail[0], dict):
                detail = detail[0]
            else:
                return {}

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

    # ========================================================================
    # 批量提取
    # ========================================================================

    def extract_all_modules(self) -> Dict[str, Any]:
        """
        提取所有模块的数据

        Returns:
            包含所有模块数据的字典
        """
        print("→ 开始提取所有模块数据...")

        result = {
            "report_id": self.report_id,
            "course_info": self.get_course_info(),
            "modules": {}
        }

        modules = [
            ("学生互动数据", self.extract_student_interaction),
            ("学习行为分布", self.extract_student_behavior),
            ("回答建构分类", self.extract_solo_classification),
            ("应答时间", self.extract_answer_time),
            ("讲授分析", self.extract_speech_data),
            ("课堂流程重构", self.extract_course_reengineering),
            ("提问有效性", self.extract_question_effectiveness),
        ]

        for name, func in modules:
            try:
                result["modules"][name] = func()
                print(f"  ✓ {name}")
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                result["modules"][name] = {}

        print("✓ 所有模块提取完成")
        return result


# ============================================================================
# 命令行使用示例
# ============================================================================

def main():
    """命令行入口"""
    import sys

    # 默认报告ID
    report_id = "96f58e78b80c462cb1194fa2f6ef4e97"

    if len(sys.argv) > 1:
        report_id = sys.argv[1]

    extractor = SeewoDataExtractor(report_id)

    # 登录（如果需要）
    if not extractor._has_cookies():
        print("首次使用，需要登录...")
        if not extractor.login():
            print("登录失败，退出")
            return

    # 提取所有数据
    all_data = extractor.extract_all_modules()

    # 保存到文件
    output_file = "seewo_all_modules.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n→ 数据已保存到 {output_file}")

    # 关闭浏览器
    extractor.close()

    # 打印课程信息
    print("\n课程信息：")
    for k, v in all_data["course_info"].items():
        if v:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
