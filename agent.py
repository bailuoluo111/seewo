#!/usr/bin/env python3
"""
agent.py — 希沃课堂分析 Agent（交互式，DeepSeek v4）

数据提取直接调用各 Skill 的 scripts/extract.py，无共享模块依赖。
System Prompt 从对应 SKILL.md 自动加载。

使用方法:
    python agent.py

示例输入:
    帮我分析一下报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况
    看看这个课 96f58e78b80c462cb1194fa2f6ef4e97 的提问质量怎么样
"""

import re
import os
import sys
import importlib.util
from pathlib import Path
from typing import Optional

# ── Skill 目录映射 ────────────────────────────────────────────────────
SKILLS_DIR = Path(__file__).parent / "skills"

SKILL_DIRS = {
    1: "student_interaction",
    2: "student_behavior",
    3: "solo_classification",
    4: "answer_time",
    5: "teacher_speech",
    6: "course_reengineering",
    7: "question_effectiveness",
}
SKILL_NAMES = {
    1: "学生互动分析",
    2: "学习行为分析",
    3: "SOLO分类分析",
    4: "应答时间分析",
    5: "讲授分析",
    6: "课堂流程重构",
    7: "提问有效性分析",
}
SKILL_KEYWORDS = {
    1: ["学生互动", "抬头", "举手", "参与"],
    2: ["学习行为", "学习金字塔", "知识留存", "被动", "主动"],
    3: ["solo", "回答质量", "建构"],
    4: ["应答时间", "回答时长", "思考"],
    5: ["讲授", "语速", "讲话"],
    6: ["课堂流程", "课前", "课后", "重构"],
    7: ["提问", "布鲁姆", "理答", "问题"],
}


# ── API 配置（从 SEEWO_CONFIG.md 读取）────────────────────────────────
def _load_config() -> dict:
    cfg_path = Path(__file__).parent / "SEEWO_CONFIG.md"
    if not cfg_path.exists():
        return {}
    content = cfg_path.read_text(encoding="utf-8")
    result = {}
    m = re.search(r"x-token=([^;`\s]+)", content)
    if m:
        result["token"] = m.group(1).strip()
    m = re.search(r"x-username=([^;`\s]+)", content)
    if m:
        result["username"] = m.group(1).strip()
    m = re.search(r"api_key:\s*([^\s`]+)", content)
    if m:
        result["api_key"] = m.group(1).strip()
    return result


# ── 核心 Agent ────────────────────────────────────────────────────────
class SeewoAgent:

    def __init__(self):
        cfg = _load_config()
        self.api_key = cfg.get("api_key")
        self.token = cfg.get("token")
        self.username = cfg.get("username")
        if not self.api_key:
            raise ValueError("未找到 api_key，请在 SEEWO_CONFIG.md 中配置")
        self.api_base = "https://token.cvte.com/v1"
        self.model = "deepseek-v4-pro"

    # ── 解析用户输入 ───────────────────────────────────────────────────
    def extract_report_id(self, text: str) -> str:
        m = re.search(r"[0-9a-f]{32}", text.lower())
        if m:
            return m.group(0)
        raise ValueError("未找到 report_id（32位十六进制串），请在输入中包含课程 ID")

    def identify_skill(self, text: str) -> int:
        lower = text.lower()
        for num, keywords in SKILL_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return num
        return 1  # 默认学生互动分析

    # ── 获取数据（调用 Skill 自带脚本）───────────────────────────────
    def get_skill_data(self, report_id: str, skill_num: int) -> dict:
        """动态加载对应 Skill 的 extract.py，获取 input_text 和 course_info。"""
        scripts_dir = str(SKILLS_DIR / SKILL_DIRS[skill_num] / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        # 模块名固定为 extract，但不同 skill 的模块不同——强制重新加载
        import importlib
        spec = importlib.util.spec_from_file_location(
            f"extract_{skill_num}",
            os.path.join(scripts_dir, "extract.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        input_text = mod.build_input(report_id, self.token, self.username)

        # 取课程基础信息（通过 seewo_client）
        client_spec = importlib.util.spec_from_file_location(
            f"seewo_client_{skill_num}",
            os.path.join(scripts_dir, "seewo_client.py"),
        )
        client_mod = importlib.util.module_from_spec(client_spec)
        client_spec.loader.exec_module(client_mod)
        course_info = client_mod.SeewoClient(report_id, self.token, self.username).get_course_info()

        return {"input_text": input_text, "course_info": course_info}

    # ── 加载 System Prompt ────────────────────────────────────────────
    def load_system_prompt(self, skill_num: int) -> str:
        skill_md = SKILLS_DIR / SKILL_DIRS[skill_num] / "SKILL.md"
        try:
            content = skill_md.read_text(encoding="utf-8")
            # 取第一个 ``` 代码块（即 System Prompt 块）
            m = re.search(r"```\n(.*?)\n```", content, re.DOTALL)
            return m.group(1).strip() if m else ""
        except Exception as e:
            print(f"  ⚠ 无法加载 System Prompt：{e}")
            return ""

    # ── 调用 LLM ──────────────────────────────────────────────────────
    def call_llm(self, system_prompt: str, user_input: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.api_base)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_input},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        return resp.choices[0].message.content.strip()

    # ── 主分析流程 ────────────────────────────────────────────────────
    def analyze(self, user_input: str) -> dict:
        try:
            report_id  = self.extract_report_id(user_input)
            skill_num  = self.identify_skill(user_input)
            skill_name = SKILL_NAMES[skill_num]

            print(f"  → Report ID : {report_id}")
            print(f"  → 分析类型  : {skill_name}")

            skill_data    = self.get_skill_data(report_id, skill_num)
            system_prompt = self.load_system_prompt(skill_num)
            analysis      = self.call_llm(system_prompt, skill_data["input_text"])

            return {
                "success":     True,
                "report_id":   report_id,
                "skill_name":  skill_name,
                "course_info": skill_data["course_info"],
                "input_data":  skill_data["input_text"],
                "analysis":    analysis,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── 交互式 CLI ────────────────────────────────────────────────────────
def print_banner():
    print("\n" + "=" * 80)
    print("🤖 希沃课堂分析 Agent（DeepSeek v4）")
    print("=" * 80)
    print("\n支持的分析类型：")
    for num, name in SKILL_NAMES.items():
        kws = " / ".join(SKILL_KEYWORDS[num][:3])
        print(f"  Skill {num}  {name:<12}  关键词：{kws}…")
    print("\n示例：帮我分析报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况")
    print("输入 quit 退出")
    print("=" * 80 + "\n")


def main():
    try:
        agent = SeewoAgent()
        print("✓ Agent 初始化成功\n")
    except Exception as e:
        print(f"❌ 初始化失败：{e}")
        print("请确保 SEEWO_CONFIG.md 中已配置 api_key 和 cookie")
        return

    print_banner()

    while True:
        try:
            user_input = input("📝 请输入：").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q", "退出"):
                print("\n👋 再见！\n")
                break

            print()
            result = agent.analyze(user_input)
            print()

            if result["success"]:
                info = result["course_info"]
                print("─" * 80)
                print(f"课程：{info.get('课程名称')}　教师：{info.get('教师姓名')}　"
                      f"学校：{info.get('学校名称')}")
                print(f"分析类型：{result['skill_name']}")
                print(f"\n💬 {result['analysis']}\n")
            else:
                print(f"❌ {result['error']}\n")

        except KeyboardInterrupt:
            print("\n\n👋 再见！\n")
            break
        except Exception as e:
            print(f"\n❌ 发生错误：{e}\n")


if __name__ == "__main__":
    main()
