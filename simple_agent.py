#!/usr/bin/env python3
"""
简单的希沃课堂分析Agent

使用方法:
    python simple_agent.py
"""

import re
from skill_helpers import get_skill_input


class SeewoAgent:
    """希沃课堂分析Agent"""

    def __init__(self):
        self.skill_names = {
            1: "学生互动分析",
            2: "学习行为分析",
            3: "SOLO分类分析",
            4: "应答时间分析",
            5: "讲授分析",
            6: "课堂流程重构",
            7: "提问有效性分析"
        }

    def extract_report_id(self, user_input: str) -> str:
        """从用户输入提取report_id"""
        # 匹配32位十六进制字符串
        pattern = r'[0-9a-f]{32}'
        match = re.search(pattern, user_input.lower())

        if match:
            return match.group(0)

        raise ValueError("未找到report_id，请在输入中包含报告ID")

    def identify_skill(self, user_input: str) -> int:
        """识别用户想要的分析类型"""
        keywords = {
            1: ["学生互动", "抬头", "举手", "参与"],
            2: ["学习行为", "学习金字塔", "知识留存"],
            3: ["solo", "回答质量", "建构"],
            4: ["应答时间", "回答时长", "思考"],
            5: ["讲授", "语速", "讲话"],
            6: ["课堂流程", "课前", "课后"],
            7: ["提问", "布鲁姆", "理答", "问题"],
        }

        user_lower = user_input.lower()

        for skill_num, words in keywords.items():
            if any(word in user_lower for word in words):
                return skill_num

        # 默认返回学生互动分析
        return 1

    def load_system_prompt(self, skill_number: int) -> str:
        """从Skill文档加载System Prompt"""
        skill_dirs = [
            "student_interaction", "student_behavior", "solo_classification",
            "answer_time", "teacher_speech", "course_reengineering",
            "question_effectiveness"
        ]

        skill_path = f"skills/{skill_dirs[skill_number - 1]}/SKILL.md"

        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取第一个```代码块中的内容
            import re
            match = re.search(r'```\n(.*?)\n```', content, re.DOTALL)
            if match:
                return match.group(1).strip()

            return ""
        except Exception as e:
            print(f"警告: 无法加载System Prompt: {e}")
            return ""

    def analyze(self, user_input: str) -> dict:
        """
        主函数：分析用户输入并返回结果

        Args:
            user_input: 用户的自然语言输入

        Returns:
            分析结果字典
        """
        print("=" * 80)
        print("🤖 希沃课堂分析Agent")
        print("=" * 80)
        print(f"\n📝 用户输入: {user_input}\n")

        try:
            # Step 1: 提取report_id
            print("Step 1: 提取report_id...")
            report_id = self.extract_report_id(user_input)
            print(f"  ✓ Report ID: {report_id}\n")

            # Step 2: 识别分析类型
            print("Step 2: 识别分析类型...")
            skill_number = self.identify_skill(user_input)
            skill_name = self.skill_names[skill_number]
            print(f"  ✓ 分析类型: Skill {skill_number} - {skill_name}\n")

            # Step 3: 获取数据
            print("Step 3: 获取课堂数据...")
            skill_data = get_skill_input(report_id, skill_number)
            print(f"  ✓ 课程: {skill_data['course_info']['课程名称']}")
            print(f"  ✓ 教师: {skill_data['course_info']['教师姓名']}")
            print(f"  ✓ 学校: {skill_data['course_info']['学校名称']}")
            print(f"  ✓ 数据: {skill_data['input_text']}\n")

            # Step 4: 加载System Prompt
            print("Step 4: 加载System Prompt...")
            system_prompt = self.load_system_prompt(skill_number)
            print(f"  ✓ System Prompt已加载 ({len(system_prompt)} 字符)\n")

            # Step 5: 调用LLM（这里模拟）
            print("Step 5: 调用LLM分析...")
            print("  ℹ️  实际使用时，这里应该调用真实的LLM API")
            print(f"  ℹ️  System Prompt: {system_prompt[:80]}...")
            print(f"  ℹ️  User Input: {skill_data['input_text']}\n")

            # 模拟LLM返回
            analysis_result = self.mock_llm_response(skill_number, skill_data['input_text'])
            print(f"  ✓ 分析完成\n")

            # 构造返回结果
            result = {
                "success": True,
                "report_id": report_id,
                "skill_number": skill_number,
                "skill_name": skill_name,
                "course_info": skill_data['course_info'],
                "input_data": skill_data['input_text'],
                "system_prompt": system_prompt[:100] + "...",
                "analysis": analysis_result
            }

            print("=" * 80)
            print("✅ 分析完成")
            print("=" * 80)

            return result

        except Exception as e:
            print(f"\n❌ 错误: {e}\n")
            return {
                "success": False,
                "error": str(e)
            }

    def mock_llm_response(self, skill_number: int, input_data: str) -> str:
        """模拟LLM响应（实际使用时替换为真实的LLM调用）"""
        responses = {
            1: "从课堂互动数据来看，学生的平均抬头率表现良好，说明大部分学生能够保持专注听课状态；平均举手率体现了积极的参与意愿。建议进一步提升平均参与度，可以通过增加小组讨论、同伴互助等方式，让更多学生有机会参与回答，从而提高整体的课堂参与广度。",
            2: "从学习行为分布来看，课堂中主动学习占比较高，这种以学生为中心的教学设计值得肯定。建议进一步提升讨论类活动的占比，可以通过增加小组讨论、思维碰撞等方式，进一步提高学生的深度参与和知识内化效果。",
            3: "从SOLO分类分布来看，学生回答主要集中在单点结构和多点结构层次，说明学生能够掌握基本知识点。建议通过追问、启发等方式，引导学生进行更深层次的思考，提升关联结构和抽象拓展层次的回答比例。",
            4: "从应答时间分布来看，快速回答占比较高，说明课堂提问以记忆性和理解性问题为主。建议适当增加需要深度思考的问题，给学生更多思考时间，培养学生的高阶思维能力。",
            5: "从讲授数据来看，教师语速适中，有利于学生理解和吸收知识。建议保持这种节奏，同时注意根据学生反馈灵活调整语速，确保所有学生都能跟上教学进度。",
            6: "从课堂流程重构来看，课前到课中、课中到课后的链接较好，体现了以学生为中心的教学设计理念。建议继续保持这种设计思路，让学习真正发生在课堂的每一个环节。",
            7: "从提问有效性来看，高阶思维问题占比合理，教师理答质量较好。建议进一步提升启发式理答的比例，通过追问、反问等方式，引导学生深入思考，提升课堂思维深度。"
        }

        return responses.get(skill_number, "分析结果...")


def main():
    """主函数"""
    agent = SeewoAgent()

    # 测试用例
    test_cases = [
        "帮我分析一下报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况",
        "看看这个课 96f58e78b80c462cb1194fa2f6ef4e97 的提问质量怎么样",
        "分析报告 96f58e78b80c462cb1194fa2f6ef4e97"
    ]

    for i, user_input in enumerate(test_cases, 1):
        print(f"\n\n{'=' * 80}")
        print(f"测试用例 {i}")
        print('=' * 80)

        result = agent.analyze(user_input)

        if result["success"]:
            print(f"\n📊 分析结果:")
            print(f"  课程: {result['course_info']['课程名称']}")
            print(f"  教师: {result['course_info']['教师姓名']}")
            print(f"  分析类型: {result['skill_name']}")
            print(f"  输入数据: {result['input_data']}")
            print(f"\n  💬 分析内容:")
            print(f"  {result['analysis']}")
        else:
            print(f"\n❌ 分析失败: {result['error']}")

        print("\n")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        希沃课堂分析Agent - 简单示例                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    main()

    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  使用说明:                                                                   ║
║                                                                              ║
║  1. 替换 mock_llm_response() 为真实的LLM调用                                ║
║  2. 支持的输入格式:                                                          ║
║     - "分析报告 {report_id} 的学生互动"                                     ║
║     - "看看课 {report_id} 的提问质量"                                       ║
║     - 任何包含32位report_id的自然语言                                       ║
║                                                                              ║
║  3. 自动识别7种分析类型（Skill 1-7）                                        ║
║  4. 自动从SEEWO_CONFIG.md读取Cookie                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
