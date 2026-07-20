#!/usr/bin/env python3
"""
希沃课堂分析Agent - 真实LLM版本

使用CCH的DeepSeek模型进行分析

使用方法:
    python agent_with_llm.py
"""

import re
import os
from skill_helpers import get_skill_input


class SeewoAgentWithLLM:
    """希沃课堂分析Agent（使用真实LLM）"""

    def __init__(self, api_key: str = None):
        """
        初始化Agent

        Args:
            api_key: CCH API Key，如果不提供则从SEEWO_CONFIG.md读取
        """
        self.skill_names = {
            1: "学生互动分析",
            2: "学习行为分析",
            3: "SOLO分类分析",
            4: "应答时间分析",
            5: "讲授分析",
            6: "课堂流程重构",
            7: "提问有效性分析"
        }

        # API配置
        self.api_base = "https://token.cvte.com/v1"
        self.model = "deepseek-v4-pro"

        # 获取API Key
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = self._load_api_key_from_config()

        if not self.api_key:
            raise ValueError("未提供API Key，请在SEEWO_CONFIG.md中添加或通过参数传入")

    def _load_api_key_from_config(self) -> str:
        """从SEEWO_CONFIG.md读取API Key"""
        try:
            with open("SEEWO_CONFIG.md", 'r', encoding='utf-8') as f:
                content = f.read()

            # 匹配 api_key: xxx
            match = re.search(r'^api_key:\s*(.+)$', content, re.MULTILINE)
            if match:
                return match.group(1).strip()

            return ""
        except Exception as e:
            print(f"警告: 无法从配置文件读取API Key: {e}")
            return ""

    def extract_report_id(self, user_input: str) -> str:
        """从用户输入提取report_id"""
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
            match = re.search(r'```\n(.*?)\n```', content, re.DOTALL)
            if match:
                return match.group(1).strip()

            return ""
        except Exception as e:
            print(f"警告: 无法加载System Prompt: {e}")
            return ""

    def call_llm(self, system_prompt: str, user_input: str) -> str:
        """
        调用CCH的DeepSeek模型

        Args:
            system_prompt: System Prompt
            user_input: 用户输入（数据）

        Returns:
            LLM生成的分析结果
        """
        try:
            # 使用OpenAI兼容接口
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.7,
                max_tokens=300
            )

            return response.choices[0].message.content.strip()

        except ImportError:
            raise ImportError("请安装openai库: pip install openai")
        except Exception as e:
            raise Exception(f"LLM调用失败: {e}")

    def analyze(self, user_input: str, verbose: bool = True) -> dict:
        """
        主函数：分析用户输入并返回结果

        Args:
            user_input: 用户的自然语言输入
            verbose: 是否打印详细过程

        Returns:
            分析结果字典
        """
        if verbose:
            print("=" * 80)
            print("🤖 希沃课堂分析Agent（DeepSeek v4）")
            print("=" * 80)
            print(f"\n📝 用户输入: {user_input}\n")

        try:
            # Step 1: 提取report_id
            if verbose:
                print("Step 1: 提取report_id...")
            report_id = self.extract_report_id(user_input)
            if verbose:
                print(f"  ✓ Report ID: {report_id}\n")

            # Step 2: 识别分析类型
            if verbose:
                print("Step 2: 识别分析类型...")
            skill_number = self.identify_skill(user_input)
            skill_name = self.skill_names[skill_number]
            if verbose:
                print(f"  ✓ 分析类型: Skill {skill_number} - {skill_name}\n")

            # Step 3: 获取数据
            if verbose:
                print("Step 3: 获取课堂数据...")
            skill_data = get_skill_input(report_id, skill_number)
            if verbose:
                print(f"  ✓ 课程: {skill_data['course_info']['课程名称']}")
                print(f"  ✓ 教师: {skill_data['course_info']['教师姓名']}")
                print(f"  ✓ 学校: {skill_data['course_info']['学校名称']}")
                print(f"  ✓ 数据: {skill_data['input_text']}\n")

            # Step 4: 加载System Prompt
            if verbose:
                print("Step 4: 加载System Prompt...")
            system_prompt = self.load_system_prompt(skill_number)
            if verbose:
                print(f"  ✓ System Prompt已加载 ({len(system_prompt)} 字符)\n")

            # Step 5: 调用LLM
            if verbose:
                print("Step 5: 调用DeepSeek v4分析...")
                print(f"  → API: {self.api_base}")
                print(f"  → Model: {self.model}")
                print(f"  → 正在生成分析...\n")

            analysis_result = self.call_llm(system_prompt, skill_data['input_text'])

            if verbose:
                print(f"  ✓ 分析完成\n")

            # 构造返回结果
            result = {
                "success": True,
                "report_id": report_id,
                "skill_number": skill_number,
                "skill_name": skill_name,
                "course_info": skill_data['course_info'],
                "input_data": skill_data['input_text'],
                "analysis": analysis_result,
                "model": self.model
            }

            if verbose:
                print("=" * 80)
                print("✅ 分析完成")
                print("=" * 80)

            return result

        except Exception as e:
            if verbose:
                print(f"\n❌ 错误: {e}\n")
            return {
                "success": False,
                "error": str(e)
            }


def main():
    """主函数"""
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "希沃课堂分析Agent - DeepSeek v4" + " " * 25 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    # 创建Agent
    try:
        agent = SeewoAgentWithLLM()
        print("✓ Agent初始化成功")
        print(f"✓ API: {agent.api_base}")
        print(f"✓ Model: {agent.model}\n")
    except Exception as e:
        print(f"❌ Agent初始化失败: {e}")
        print("\n请在 SEEWO_CONFIG.md 中添加 API Key:")
        print("```")
        print("api_key: sk-your-api-key-here")
        print("```")
        return

    # 测试用例
    test_cases = [
        "帮我分析一下报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况",
        # "看看这个课 96f58e78b80c462cb1194fa2f6ef4e97 的提问质量怎么样",
    ]

    for i, user_input in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"测试用例 {i}")
        print('=' * 80)

        result = agent.analyze(user_input)

        if result["success"]:
            print(f"\n📊 分析结果:")
            print(f"  课程: {result['course_info']['课程名称']}")
            print(f"  教师: {result['course_info']['教师姓名']}")
            print(f"  分析类型: {result['skill_name']}")
            print(f"  模型: {result['model']}")
            print(f"  输入数据: {result['input_data']}")
            print(f"\n  💬 分析内容:")
            print(f"  {result['analysis']}")
        else:
            print(f"  ❌ 分析失败: {result.get('error')}")

    print("\n" + "╔" + "═" * 78 + "╗")
    print("║  接入真实LLM成功！                                                          ║")
    print("║  替换 simple_agent.py 即可在交互模式中使用                                 ║")
    print("╚" + "═" + "═" * 77 + "╝\n")


if __name__ == "__main__":
    main()
