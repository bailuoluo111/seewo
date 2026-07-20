#!/usr/bin/env python3
"""
seewo_http_data_extractor.py - 使用HTTP请求+Token获取希沃课堂观察数据（完整版）

优点：
1. 不需要Playwright，无需浏览器
2. 速度更快，资源占用更少
3. 部署更简单，只需requests库
4. Token可以长期使用（需定期更新）
"""

import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime


class SeewoHttpDataExtractor:
    """希沃课堂观察数据提取器（HTTP版本）"""

    def __init__(self, report_id: str, token: str, username: str):
        """
        初始化提取器

        Args:
            report_id: 报告ID
            token: x-token值（从浏览器Cookie中获取）
            username: x-username值（从浏览器Cookie中获取）
        """
        self.report_id = report_id
        self.token = token
        self.username = username
        self.api_host = "https://edulyse.seewo.com"
        self.api_template = f"{self.api_host}/api/analyse/course/report/{report_id}/{{atype}}"

        # 设置请求头
        self.headers = {
            "Cookie": f"x-token={token}; x-samesite-none-token={token}; x-username={username}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": f"https://easiinsight.seewo.com/report/detail/{report_id}/home",
        }

        self._course_info_cache = None

    def fetch_api(self, analysis_type: str, silent: bool = False) -> Optional[Dict]:
        """
        调用接口获取数据

        Args:
            analysis_type: 分析类型
            silent: 是否静默模式（不打印日志）

        Returns:
            接口返回的数据，失败返回 None
        """
        url = self.api_template.format(atype=analysis_type)

        try:
            response = requests.get(url, headers=self.headers, timeout=20)

            if not silent:
                print(f"  [{response.status_code}] {analysis_type}")

            if response.status_code != 200:
                if not silent:
                    print(f"    ✗ 请求失败: {response.status_code}")
                return None

            data = response.json()

            # 检查业务状态码
            if "code" in data and data["code"] != 0:
                if not silent:
                    print(f"    ✗ 业务错误: code={data.get('code')}, msg={data.get('msg')}")
                return None

            return data.get("data", {})

        except Exception as e:
            if not silent:
                print(f"    ✗ 错误: {e}")
            return None

    def test_connection(self) -> bool:
        """测试Token是否有效"""
        data = self.fetch_api("studentStudyStatistic", silent=True)
        return data is not None

    # ========================================================================
    # 课程基础信息
    # ========================================================================

    def get_course_info(self) -> Dict[str, Any]:
        """获取课程基础信息"""
        if self._course_info_cache:
            return self._course_info_cache

        data = self.fetch_api("studentStudyStatistic", silent=True)
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
        """提取学生互动数据"""
        data = self.fetch_api("studentStudyStatistic", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail", {})
        return {
            "平均抬头率": round(detail.get("raiseHeadRatio", 0) * 100, 1),
            "平均举手率": round(detail.get("handUpRatio", 0) * 100, 1),
            "平均参与度": round(detail.get("answerRatio", 0) * 100, 1),
        }

    # ========================================================================
    # 模块2: 学习行为分布
    # ========================================================================

    def extract_student_behavior(self) -> Dict[str, Any]:
        """提取学习行为数据"""
        data = self.fetch_api("studentStudyBehavior", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail", [])
        if not isinstance(detail, list):
            return {}

        behavior_durations = {}
        total_duration = 0

        for item in detail:
            start = item.get("startTime")
            end = item.get("endTime")
            behavior_type = item.get("behaviorType")

            if start is not None and end is not None:
                duration = (end - start) / 1000
                total_duration += duration

                if behavior_type is not None:
                    key = str(behavior_type)
                    behavior_durations[key] = behavior_durations.get(key, 0) + duration

        result = {
            "总时长(秒)": round(total_duration, 1),
            "各行为类型时长(秒)": {k: round(v, 1) for k, v in behavior_durations.items()},
        }

        if total_duration > 0:
            occupancy = {}
            for behavior_type, duration in behavior_durations.items():
                occupancy[behavior_type] = round(duration / total_duration * 100, 1)
            result["各行为类型占比(%)"] = occupancy

        return result

    # ========================================================================
    # 模块3: SOLO分类
    # ========================================================================

    def extract_solo_classification(self) -> Dict[str, Any]:
        """提取SOLO分类数据"""
        data = self.fetch_api("solo", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail", [])
        if not isinstance(detail, list):
            return {}

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
        """提取应答时间数据"""
        data = self.fetch_api("studentAnswerClassification", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail", [])
        if not isinstance(detail, list):
            return {}

        time_stats = {"≤5秒": 0, "5-15秒": 0, ">15秒": 0}

        for item in detail:
            start = item.get("startTime")
            end = item.get("endTime")

            if start is not None and end is not None:
                duration = (end - start) / 1000

                if duration <= 5:
                    time_stats["≤5秒"] += 1
                elif duration <= 15:
                    time_stats["5-15秒"] += 1
                else:
                    time_stats[">15秒"] += 1

        total_count = sum(time_stats.values())

        result = {
            "总回答数": total_count,
            "各时段回答数": time_stats,
        }

        if total_count > 0:
            occupancy = {}
            for time_range, count in time_stats.items():
                occupancy[time_range] = round(count / total_count * 100, 1)
            result["各时段占比(%)"] = occupancy

        return result

    # ========================================================================
    # 模块5: 讲授分析
    # ========================================================================

    def extract_speech_data(self) -> Dict[str, Any]:
        """提取讲授分析数据"""
        data = self.fetch_api("speechData", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail", {})

        word_count = detail.get("speechWordCount", 0)
        duration = detail.get("speechDurationInSeconds", 0)

        result = {
            "讲授字数": word_count,
            "讲授时长(秒)": duration,
        }

        if duration > 0:
            result["平均语速(字/秒)"] = round(word_count / duration, 1)

        return result

    # ========================================================================
    # 模块6: 课堂流程重构
    # ========================================================================

    def extract_course_reengineering(self) -> Dict[str, Any]:
        """提取课堂流程重构数据"""
        data = self.fetch_api("courseProcessReengineering", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail", {})

        def extract_link_data(link_data):
            if not link_data:
                return {}

            LEVEL_MAP = {
                "INITIAL_LEVEL": "初阶",
                "PRELIMINARY_LEVEL": "进阶",
                "INTERMEDIATE_LEVEL": "中阶",
                "ADVANCED_LEVEL": "高阶",
            }

            SCORE_MAP = {
                "NO_REFACTOR": "无重构",
                "PRELIMINARY_REFACTOR": "初步重构",
                "GOOD_REFACTOR": "良好重构",
                "EXCELLENT_REFACTOR": "优秀重构",
            }

            tasks = []
            for task in link_data.get("subTasks", []):
                tasks.append({
                    "名称": task.get("name"),
                    "分数": SCORE_MAP.get(task.get("score"), task.get("score")),
                    "原因": task.get("reason"),
                })

            return {
                "等级": LEVEL_MAP.get(link_data.get("level"), link_data.get("level")),
                "子任务": tasks,
            }

        return {
            "课前到课中链接": extract_link_data(detail.get("preClassToInClassLink")),
            "课中到课后链接": extract_link_data(detail.get("inClassToPostClassLink")),
        }

    # ========================================================================
    # 模块7: 提问有效性（多个子模块）
    # ========================================================================

    def extract_question_record(self) -> Dict[str, Any]:
        """提取提问记录"""
        data = self.fetch_api("questionRecord", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

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

    def extract_bloom_classification(self) -> Dict[str, Any]:
        """提取布鲁姆分类"""
        data = self.fetch_api("bloom", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

        if isinstance(detail, dict):
            statistics = detail.get("statistics", [])
        elif isinstance(detail, list):
            statistics = detail
        else:
            return {}

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

        if total_count > 0:
            occupancy = {}
            for level_name, count in bloom_stats.items():
                occupancy[level_name] = round(count / total_count * 100, 1)
            result["各等级占比(%)"] = occupancy

            high_order = sum(
                count for level, count in bloom_stats.items()
                if level in ["分析", "评价", "创造"]
            )
            result["高阶思维占比(%)"] = round(high_order / total_count * 100, 1)

        return result

    def extract_teacher_appraisal(self) -> Dict[str, Any]:
        """提取教师理答分类"""
        data = self.fetch_api("teacherAppraisalClassification", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail", [])
        if not isinstance(detail, list):
            return {}

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

        if total_count > 0:
            occupancy = {}
            for appraisal_type, count in appraisal_stats.items():
                occupancy[appraisal_type] = round(count / total_count * 100, 1)
            result["各类型占比(%)"] = occupancy

            high_quality = sum(
                count for appraisal_type, count in appraisal_stats.items()
                if appraisal_type in ["追问", "引导", "启发鼓励"]
            )
            result["高质量理答占比(%)"] = round(high_quality / total_count * 100, 1)

        return result

    def extract_question_answer_extra(self) -> Dict[str, Any]:
        """提取问答额外结果"""
        data = self.fetch_api("questionAnswerExtraResult", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

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

    def extract_question_score(self) -> Dict[str, Any]:
        """提取提问有效性得分"""
        data = self.fetch_api("questionScoreExplain", silent=True)
        if not data:
            return {}

        detail = data.get("reportDetail")
        if not detail:
            return {}

        return {
            "提问有效性得分": detail.get("score"),
        }

    # ========================================================================
    # 提取所有模块
    # ========================================================================

    def extract_all_modules(self) -> Dict[str, Any]:
        """提取所有模块的数据"""
        print("\n→ 开始提取所有模块数据...")

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
            ("提问记录", self.extract_question_record),
            ("布鲁姆分类", self.extract_bloom_classification),
            ("教师理答分类", self.extract_teacher_appraisal),
            ("问答额外结果", self.extract_question_answer_extra),
            ("提问有效性得分", self.extract_question_score),
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
# 命令行使用
# ============================================================================

def main():
    """命令行入口"""
    import sys

    # 配置信息
    REPORT_ID = "96f58e78b80c462cb1194fa2f6ef4e97"
    TOKEN = "e953f17a521f49209c052796c055d4ea-0992"
    USERNAME = "13429851339"

    print("=" * 60)
    print("希沃课堂观察数据提取器（HTTP版本）")
    print("=" * 60)

    # 创建提取器
    extractor = SeewoHttpDataExtractor(
        report_id=REPORT_ID,
        token=TOKEN,
        username=USERNAME,
    )

    # 测试连接
    print("\n→ 测试Token有效性...")
    if not extractor.test_connection():
        print("❌ Token验证失败")
        print("\n请检查:")
        print("  1. Token是否正确")
        print("  2. Token是否过期")
        print("  3. 网络连接是否正常")
        return

    print("✓ Token有效")

    # 提取所有数据
    all_data = extractor.extract_all_modules()

    # 保存到文件
    output_file = "seewo_http_extracted_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n→ 数据已保存到 {output_file}")

    # 打印课程信息
    print("\n课程信息：")
    for k, v in all_data["course_info"].items():
        if v:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
