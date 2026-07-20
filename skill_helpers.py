#!/usr/bin/env python3
"""
Skill辅助函数 - 为Agent提供简化的数据获取接口

每个函数返回：
{
    "input_text": "格式化的LLM输入文本",
    "raw_data": {...原始数据...},
    "course_info": {...课程信息...}
}
"""

from seewo_http_data_extractor import SeewoHttpDataExtractor
from typing import Dict, Any


def get_skill1_input(report_id: str) -> Dict[str, Any]:
    """
    Skill 1: 学生互动分析

    Args:
        report_id: 报告ID

    Returns:
        包含 input_text, raw_data, course_info 的字典
    """
    extractor = SeewoHttpDataExtractor(report_id)
    course_info = extractor.get_course_info()
    data = extractor.extract_student_interaction()

    input_text = (
        f"平均抬头率{data['平均抬头率']}%，"
        f"平均举手率{data['平均举手率']}%，"
        f"平均参与度{data['平均参与度']}%，"
        f"{course_info['学段']}学段"
    )

    return {
        "input_text": input_text,
        "raw_data": data,
        "course_info": course_info
    }


def get_skill2_input(report_id: str) -> Dict[str, Any]:
    """
    Skill 2: 学习行为分析

    Args:
        report_id: 报告ID

    Returns:
        包含 input_text, raw_data, course_info 的字典
    """
    extractor = SeewoHttpDataExtractor(report_id)
    course_info = extractor.get_course_info()
    data = extractor.extract_student_behavior()

    # 计算知识留存率
    behavior_map = {"0": 20, "3": 50, "4": 75}
    retention_rate = sum(
        data['各行为类型占比(%)'].get(k, 0) * v / 100
        for k, v in behavior_map.items()
    )

    input_text = (
        f"被动学习占比{data['各行为类型占比(%)'].get('0', 0)}%，"
        f"讨论占比{data['各行为类型占比(%)'].get('3', 0)}%，"
        f"实践占比{data['各行为类型占比(%)'].get('4', 0)}%，"
        f"估算知识留存率{retention_rate:.1f}%"
    )

    return {
        "input_text": input_text,
        "raw_data": data,
        "course_info": course_info,
        "retention_rate": retention_rate
    }


def get_skill3_input(report_id: str) -> Dict[str, Any]:
    """
    Skill 3: SOLO分类分析

    Args:
        report_id: 报告ID

    Returns:
        包含 input_text, raw_data, course_info 的字典
    """
    extractor = SeewoHttpDataExtractor(report_id)
    course_info = extractor.get_course_info()
    data = extractor.extract_solo_classification()

    input_text = (
        f"总回答{data['总回答数']}次，"
        f"前结构{data['各等级占比(%)'].get('前结构', 0)}%，"
        f"单点{data['各等级占比(%)'].get('单点结构', 0)}%，"
        f"多点{data['各等级占比(%)'].get('多点结构', 0)}%，"
        f"关联{data['各等级占比(%)'].get('关联结构', 0)}%，"
        f"抽象拓展{data['各等级占比(%)'].get('抽象拓展', 0)}%"
    )

    return {
        "input_text": input_text,
        "raw_data": data,
        "course_info": course_info
    }


def get_skill4_input(report_id: str) -> Dict[str, Any]:
    """
    Skill 4: 应答时间分析

    Args:
        report_id: 报告ID

    Returns:
        包含 input_text, raw_data, course_info 的字典
    """
    extractor = SeewoHttpDataExtractor(report_id)
    course_info = extractor.get_course_info()
    data = extractor.extract_answer_time()

    input_text = (
        f"总回答{data['总回答数']}次，"
        f"快速回答(≤5秒){data['各时段占比(%)']['≤5秒']}%，"
        f"中等思考(5-15秒){data['各时段占比(%)']['5-15秒']}%，"
        f"深度思考(>15秒){data['各时段占比(%)']['>15秒']}%"
    )

    return {
        "input_text": input_text,
        "raw_data": data,
        "course_info": course_info
    }


def get_skill5_input(report_id: str) -> Dict[str, Any]:
    """
    Skill 5: 讲授分析

    Args:
        report_id: 报告ID

    Returns:
        包含 input_text, raw_data, course_info 的字典
    """
    extractor = SeewoHttpDataExtractor(report_id)
    course_info = extractor.get_course_info()
    data = extractor.extract_speech_data()

    input_text = (
        f"讲授字数{data['讲授字数']}字，"
        f"讲授时长{data['讲授时长(秒)']}秒，"
        f"平均语速{data['平均语速(字/秒)']}字/秒"
    )

    return {
        "input_text": input_text,
        "raw_data": data,
        "course_info": course_info
    }


def get_skill6_input(report_id: str) -> Dict[str, Any]:
    """
    Skill 6: 课堂流程重构

    Args:
        report_id: 报告ID

    Returns:
        包含 input_text, raw_data, course_info 的字典
    """
    extractor = SeewoHttpDataExtractor(report_id)
    course_info = extractor.get_course_info()
    data = extractor.extract_course_reengineering()

    input_text = (
        f"课前到课中链接等级：{data['课前到课中链接']['等级']}，"
        f"课中到课后链接等级：{data['课中到课后链接']['等级']}"
    )

    return {
        "input_text": input_text,
        "raw_data": data,
        "course_info": course_info
    }


def get_skill7_input(report_id: str) -> Dict[str, Any]:
    """
    Skill 7: 提问有效性分析

    Args:
        report_id: 报告ID

    Returns:
        包含 input_text, raw_data, course_info 的字典
    """
    extractor = SeewoHttpDataExtractor(report_id)
    course_info = extractor.get_course_info()

    # 提问有效性需要组合多个数据源
    bloom = extractor.extract_bloom_classification()
    appraisal = extractor.extract_teacher_appraisal()
    score = extractor.extract_question_score()

    input_text = (
        f"总问题{bloom['总问题数']}个，"
        f"高阶思维占比{bloom['高阶思维占比(%)']}%，"
        f"高质量理答占比{appraisal['高质量理答占比(%)']}%，"
        f"提问有效性得分{score['提问有效性得分']}"
    )

    return {
        "input_text": input_text,
        "raw_data": {
            "bloom": bloom,
            "appraisal": appraisal,
            "score": score
        },
        "course_info": course_info
    }


# ============================================================================
# Agent集成函数
# ============================================================================

def get_skill_input(report_id: str, skill_number: int) -> Dict[str, Any]:
    """
    统一的Skill数据获取接口

    Args:
        report_id: 报告ID
        skill_number: Skill编号 (1-7)

    Returns:
        Skill数据字典

    Raises:
        ValueError: 如果skill_number不在1-7范围内
    """
    skill_map = {
        1: get_skill1_input,
        2: get_skill2_input,
        3: get_skill3_input,
        4: get_skill4_input,
        5: get_skill5_input,
        6: get_skill6_input,
        7: get_skill7_input,
    }

    if skill_number not in skill_map:
        raise ValueError(f"无效的Skill编号: {skill_number}，必须在1-7之间")

    return skill_map[skill_number](report_id)


def get_all_skills_input(report_id: str) -> Dict[int, Dict[str, Any]]:
    """
    获取所有7个Skill的数据

    Args:
        report_id: 报告ID

    Returns:
        字典，key为skill编号，value为skill数据
    """
    return {
        skill_num: get_skill_input(report_id, skill_num)
        for skill_num in range(1, 8)
    }


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    # 示例：获取Skill 1的数据
    report_id = "96f58e78b80c462cb1194fa2f6ef4e97"

    print("=" * 70)
    print("测试 Skill 辅助函数")
    print("=" * 70)

    # 方式1: 获取单个Skill
    print("\n→ 获取 Skill 1 (学生互动) 数据:")
    skill1_data = get_skill1_input(report_id)
    print(f"输入文本: {skill1_data['input_text']}")
    print(f"课程: {skill1_data['course_info']['课程名称']}")

    # 方式2: 通过编号获取
    print("\n→ 通过编号获取 Skill 2 (学习行为) 数据:")
    skill2_data = get_skill_input(report_id, 2)
    print(f"输入文本: {skill2_data['input_text']}")
    print(f"知识留存率: {skill2_data['retention_rate']:.1f}%")

    # 方式3: 获取所有Skill
    print("\n→ 获取所有7个Skill的数据:")
    all_data = get_all_skills_input(report_id)
    for skill_num, data in all_data.items():
        print(f"  Skill {skill_num}: {data['input_text'][:50]}...")

    print("\n✓ 测试完成")
