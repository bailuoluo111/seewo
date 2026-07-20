#!/usr/bin/env python3
"""
Agent模拟 - 展示完整的输入、输出、Trace和工具调用流程
"""

import re
import json
from datetime import datetime
from skill_helpers import get_skill_input


# ============================================================================
# 模拟的工具函数
# ============================================================================

def extract_report_id(user_input: str) -> str:
    """工具1: 从用户输入提取report_id"""
    print("\n[Tool Call] extract_report_id")
    print(f"  Input: {user_input[:80]}...")

    # 匹配32位十六进制
    pattern = r'[0-9a-f]{32}'
    match = re.search(pattern, user_input.lower())

    if match:
        report_id = match.group(0)
        print(f"  Output: {report_id}")
        return report_id

    raise ValueError("未找到report_id")


def identify_skill_type(user_input: str) -> int:
    """工具2: 识别用户想要的分析类型"""
    print("\n[Tool Call] identify_skill_type")
    print(f"  Input: {user_input[:80]}...")

    keywords_map = {
        1: ["学生互动", "抬头率", "举手率", "参与度", "互动"],
        2: ["学习行为", "学习金字塔", "知识留存", "行为"],
        3: ["solo", "回答质量", "建构水平", "思维层次"],
        4: ["应答时间", "回答时长", "思考时间"],
        5: ["讲授", "语速", "教师讲话", "讲课"],
        6: ["课堂流程", "课前课中", "课中课后", "流程"],
        7: ["提问", "布鲁姆", "理答", "提问有效性", "问题"],
    }

    user_lower = user_input.lower()

    for skill_num, keywords in keywords_map.items():
        if any(keyword in user_lower for keyword in keywords):
            skill_name = [
                "学生互动分析", "学习行为分析", "SOLO分类分析", "应答时间分析",
                "讲授分析", "课堂流程重构", "提问有效性分析"
            ][skill_num - 1]
            print(f"  Output: Skill {skill_num} - {skill_name}")
            return skill_num

    print("  Output: 未识别到特定类型，默认 Skill 1")
    return 1


def load_system_prompt(skill_number: int) -> str:
    """工具3: 从Skill文档加载System Prompt"""
    print(f"\n[Tool Call] load_system_prompt")
    print(f"  Input: skill_number={skill_number}")

    skill_dirs = [
        "student_interaction", "student_behavior", "solo_classification",
        "answer_time", "teacher_speech", "course_reengineering", "question_effectiveness"
    ]

    skill_path = f"skills/{skill_dirs[skill_number - 1]}/SKILL.md"

    try:
        with open(skill_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取System Prompt（在```之间）
        import re
        match = re.search(r'```\n(.*?)\n```', content, re.DOTALL)
        if match:
            system_prompt = match.group(1).strip()
            print(f"  Output: System Prompt加载成功 ({len(system_prompt)} 字符)")
            return system_prompt
        else:
            print("  Output: 未找到System Prompt")
            return ""
    except Exception as e:
        print(f"  Error: {e}")
        return ""


def call_llm(system_prompt: str, user_input: str) -> str:
    """工具4: 调用LLM（模拟）"""
    print(f"\n[Tool Call] call_llm")
    print(f"  System Prompt: {system_prompt[:100]}...")
    print(f"  User Input: {user_input}")

    # 模拟LLM响应
    response = (
        "从课堂互动数据来看，学生的平均抬头率达到72.6%，说明大部分学生能够保持专注听课状态；"
        "平均举手率为35.8%，体现了较为积极的参与意愿。建议进一步提升平均参与度（目前为16.8%），"
        "可以通过增加小组讨论、同伴互助等方式，让更多学生有机会参与回答，从而提高整体的课堂参与广度。"
    )

    print(f"  Output: {response[:80]}...")
    return response


# ============================================================================
# Agent主流程
# ============================================================================

def agent_process(user_input: str) -> dict:
    """
    Agent主流程：处理用户输入，返回分析结果

    包含完整的Trace和工具调用记录
    """
    print("=" * 100)
    print("🤖 AGENT START")
    print("=" * 100)
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📝 User Input: {user_input}")
    print("=" * 100)

    trace = {
        "timestamp": datetime.now().isoformat(),
        "user_input": user_input,
        "steps": [],
        "tool_calls": [],
        "result": None,
        "error": None
    }

    try:
        # ====================================================================
        # Step 1: 提取 report_id
        # ====================================================================
        print("\n" + "─" * 100)
        print("📍 STEP 1: 提取 report_id")
        print("─" * 100)

        report_id = extract_report_id(user_input)

        trace["steps"].append({
            "step": 1,
            "action": "extract_report_id",
            "output": report_id
        })
        trace["tool_calls"].append({
            "tool": "extract_report_id",
            "input": user_input,
            "output": report_id
        })

        # ====================================================================
        # Step 2: 识别分析类型
        # ====================================================================
        print("\n" + "─" * 100)
        print("📍 STEP 2: 识别分析类型")
        print("─" * 100)

        skill_number = identify_skill_type(user_input)

        trace["steps"].append({
            "step": 2,
            "action": "identify_skill_type",
            "output": skill_number
        })
        trace["tool_calls"].append({
            "tool": "identify_skill_type",
            "input": user_input,
            "output": skill_number
        })

        # ====================================================================
        # Step 3: 获取Skill数据
        # ====================================================================
        print("\n" + "─" * 100)
        print("📍 STEP 3: 获取Skill数据")
        print("─" * 100)
        print(f"\n[Tool Call] get_skill_input")
        print(f"  Input: report_id={report_id}, skill_number={skill_number}")

        skill_data = get_skill_input(report_id, skill_number)

        print(f"  Output:")
        print(f"    - course_info: {skill_data['course_info']['课程名称']}")
        print(f"    - input_text: {skill_data['input_text']}")

        trace["steps"].append({
            "step": 3,
            "action": "get_skill_input",
            "output": {
                "course_name": skill_data['course_info']['课程名称'],
                "teacher_name": skill_data['course_info']['教师姓名'],
                "input_text": skill_data['input_text']
            }
        })
        trace["tool_calls"].append({
            "tool": "get_skill_input",
            "input": {"report_id": report_id, "skill_number": skill_number},
            "output": skill_data['input_text']
        })

        # ====================================================================
        # Step 4: 加载System Prompt
        # ====================================================================
        print("\n" + "─" * 100)
        print("📍 STEP 4: 加载System Prompt")
        print("─" * 100)

        system_prompt = load_system_prompt(skill_number)

        trace["steps"].append({
            "step": 4,
            "action": "load_system_prompt",
            "output": f"{len(system_prompt)} characters"
        })
        trace["tool_calls"].append({
            "tool": "load_system_prompt",
            "input": skill_number,
            "output": system_prompt[:100] + "..."
        })

        # ====================================================================
        # Step 5: 调用LLM
        # ====================================================================
        print("\n" + "─" * 100)
        print("📍 STEP 5: 调用LLM生成分析")
        print("─" * 100)

        analysis_result = call_llm(system_prompt, skill_data['input_text'])

        trace["steps"].append({
            "step": 5,
            "action": "call_llm",
            "output": analysis_result
        })
        trace["tool_calls"].append({
            "tool": "call_llm",
            "input": {
                "system_prompt": system_prompt[:100] + "...",
                "user_input": skill_data['input_text']
            },
            "output": analysis_result
        })

        # ====================================================================
        # Step 6: 构造返回结果
        # ====================================================================
        print("\n" + "─" * 100)
        print("📍 STEP 6: 构造返回结果")
        print("─" * 100)

        result = {
            "report_id": report_id,
            "skill_number": skill_number,
            "skill_name": [
                "学生互动分析", "学习行为分析", "SOLO分类分析", "应答时间分析",
                "讲授分析", "课堂流程重构", "提问有效性分析"
            ][skill_number - 1],
            "course_info": skill_data['course_info'],
            "input_data": skill_data['input_text'],
            "analysis": analysis_result
        }

        trace["result"] = result

        print(f"\n✅ Result构造完成")
        print(f"  - Skill: {result['skill_name']}")
        print(f"  - Course: {result['course_info']['课程名称']}")
        print(f"  - Analysis: {result['analysis'][:80]}...")

        return result

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        trace["error"] = str(e)
        raise

    finally:
        # ====================================================================
        # 打印完整Trace
        # ====================================================================
        print("\n" + "=" * 100)
        print("📊 TRACE SUMMARY")
        print("=" * 100)
        print(f"\n总步骤数: {len(trace['steps'])}")
        print(f"工具调用次数: {len(trace['tool_calls'])}")

        print(f"\n执行流程:")
        for step in trace["steps"]:
            print(f"  Step {step['step']}: {step['action']}")

        print(f"\n工具调用:")
        for i, tool_call in enumerate(trace["tool_calls"], 1):
            print(f"  {i}. {tool_call['tool']}")

        if trace.get("error"):
            print(f"\n❌ Error: {trace['error']}")
        else:
            print(f"\n✅ Success")

        print("\n" + "=" * 100)
        print("🤖 AGENT END")
        print("=" * 100)


# ============================================================================
# 测试用例
# ============================================================================

if __name__ == "__main__":
    print("\n\n")
    print("🎯 " * 40)
    print("Agent模拟测试 - 完整的Trace流程")
    print("🎯 " * 40)

    # 测试用例1: 学生互动分析
    print("\n\n")
    print("=" * 100)
    print("测试用例 1: 学生互动分析")
    print("=" * 100)

    user_input_1 = "帮我分析一下报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况"

    result_1 = agent_process(user_input_1)

    print("\n\n📤 FINAL OUTPUT:")
    print("=" * 100)
    print(json.dumps(result_1, ensure_ascii=False, indent=2))

    # 测试用例2: 提问有效性分析
    print("\n\n\n")
    print("=" * 100)
    print("测试用例 2: 提问有效性分析")
    print("=" * 100)

    user_input_2 = "分析 96f58e78b80c462cb1194fa2f6ef4e97 这个课的教师提问质量"

    result_2 = agent_process(user_input_2)

    print("\n\n📤 FINAL OUTPUT:")
    print("=" * 100)
    print(json.dumps(result_2, ensure_ascii=False, indent=2))
