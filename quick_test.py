#!/usr/bin/env python3
"""
快速测试脚本 - 一次性展示所有方法的效果
"""

from seewo_http_data_extractor import SeewoHttpDataExtractor
import json

# ============================================================================
# 配置信息
# ============================================================================

REPORT_ID = "96f58e78b80c462cb1194fa2f6ef4e97"
TOKEN = "e953f17a521f49209c052796c055d4ea-0992"
USERNAME = "13429851339"

# ============================================================================
# 美化输出
# ============================================================================

def print_section(title):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"📊 {title}")
    print("=" * 70)

def print_data(data, indent=0):
    """递归美化输出数据"""
    prefix = "  " * indent

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{prefix}{key}:")
                print_data(value, indent + 1)
            else:
                print(f"{prefix}{key}: {value}")
    elif isinstance(data, list):
        for i, item in enumerate(data[:5]):  # 只显示前5项
            if isinstance(item, (dict, list)):
                print(f"{prefix}[{i}]:")
                print_data(item, indent + 1)
            else:
                print(f"{prefix}[{i}]: {item}")
        if len(data) > 5:
            print(f"{prefix}... (还有 {len(data) - 5} 项)")
    else:
        print(f"{prefix}{data}")

# ============================================================================
# 主函数
# ============================================================================

def main():
    print("=" * 70)
    print("希沃课堂观察数据提取器 - 快速测试")
    print("=" * 70)

    # 创建提取器
    extractor = SeewoHttpDataExtractor(
        report_id=REPORT_ID,
        token=TOKEN,
        username=USERNAME
    )

    # 测试连接
    print("\n→ 测试Token有效性...")
    if not extractor.test_connection():
        print("❌ Token无效或已过期")
        return

    print("✓ Token有效")

    # ========================================================================
    # 0. 课程信息
    # ========================================================================
    print_section("0. 课程信息")
    course_info = extractor.get_course_info()
    print_data(course_info)

    # ========================================================================
    # 1. 学生互动数据 (Skill 1)
    # ========================================================================
    print_section("1. 学生互动数据 (Skill 1)")
    interaction = extractor.extract_student_interaction()
    print_data(interaction)
    print(f"\n💡 用途: 分析抬头率、举手率、参与度，评估学生课堂参与情况")

    # ========================================================================
    # 2. 学习行为分布 (Skill 2)
    # ========================================================================
    print_section("2. 学习行为分布 (Skill 2)")
    behavior = extractor.extract_student_behavior()
    print_data(behavior)
    print(f"\n💡 用途: 基于学习金字塔理论，计算知识留存率")

    # ========================================================================
    # 3. SOLO分类 (Skill 3)
    # ========================================================================
    print_section("3. SOLO分类 (Skill 3)")
    solo = extractor.extract_solo_classification()
    print_data(solo)
    print(f"\n💡 用途: 评估学生回答的建构水平（前结构→单点→多点→关联→抽象拓展）")

    # ========================================================================
    # 4. 应答时间 (Skill 4)
    # ========================================================================
    print_section("4. 应答时间 (Skill 4)")
    answer_time = extractor.extract_answer_time()
    print_data(answer_time)
    print(f"\n💡 用途: 分析学生回答时长，评估问题难度和思考深度")

    # ========================================================================
    # 5. 讲授分析 (Skill 5)
    # ========================================================================
    print_section("5. 讲授分析 (Skill 5)")
    speech = extractor.extract_speech_data()
    print_data(speech)
    print(f"\n💡 用途: 评估教师讲授节奏（语速区间匹配，前端实现）")

    # ========================================================================
    # 6. 课堂流程重构 (Skill 6)
    # ========================================================================
    print_section("6. 课堂流程重构 (Skill 6)")
    reengineering = extractor.extract_course_reengineering()
    print("\n课前到课中链接:")
    if '课前到课中链接' in reengineering:
        link = reengineering['课前到课中链接']
        print(f"  等级: {link.get('等级')}")
        print(f"  子任务数: {len(link.get('子任务', []))}")
    print("\n课中到课后链接:")
    if '课中到课后链接' in reengineering:
        link = reengineering['课中到课后链接']
        print(f"  等级: {link.get('等级')}")
        print(f"  子任务数: {len(link.get('子任务', []))}")
    print(f"\n💡 用途: 评估课堂流程重构度，关注课前/课中/课后链接")

    # ========================================================================
    # 7. 提问记录 (Skill 7的一部分)
    # ========================================================================
    print_section("7. 提问记录 (Skill 7)")
    question_record = extractor.extract_question_record()
    print(f"提问总数: {question_record.get('提问总数')}")
    print(f"有效回答数: {question_record.get('有效回答数')}")
    print(f"提问列表: {len(question_record.get('提问列表', []))} 条")
    print(f"\n💡 用途: Skill 7的基础数据，记录所有提问和回答")

    # ========================================================================
    # 8. 布鲁姆分类 (Skill 7的一部分)
    # ========================================================================
    print_section("8. 布鲁姆分类 (Skill 7)")
    bloom = extractor.extract_bloom_classification()
    print_data(bloom)
    print(f"\n💡 用途: Skill 7的组成部分，评估提问层次（记忆→理解→应用→分析→评价→创造）")

    # ========================================================================
    # 9. 教师理答分类 (Skill 7的一部分)
    # ========================================================================
    print_section("9. 教师理答分类 (Skill 7)")
    appraisal = extractor.extract_teacher_appraisal()
    print_data(appraisal)
    print(f"\n💡 用途: Skill 7的组成部分，评估教师理答质量")

    # ========================================================================
    # 10. 问答额外结果 (Skill 7的一部分)
    # ========================================================================
    print_section("10. 问答额外结果 (Skill 7)")
    extra = extractor.extract_question_answer_extra()
    print_data(extra)
    print(f"\n💡 用途: Skill 7的辅助数据，统计问答情况")

    # ========================================================================
    # 11. 提问有效性得分 (Skill 7的核心)
    # ========================================================================
    print_section("11. 提问有效性得分 (Skill 7)")
    score = extractor.extract_question_score()
    print_data(score)
    print(f"\n💡 用途: Skill 7的最终输出，综合评估提问有效性")

    # ========================================================================
    # 总结
    # ========================================================================
    print("\n" + "=" * 70)
    print("🎉 测试完成！")
    print("=" * 70)
    print("\n📊 数据提取方法与7个Skill的对应关系：")
    print("\nSkill 1: 学生互动分析")
    print("  └─ extract_student_interaction()")
    print("\nSkill 2: 学习行为分析")
    print("  └─ extract_student_behavior()")
    print("\nSkill 3: SOLO分类分析")
    print("  └─ extract_solo_classification()")
    print("\nSkill 4: 应答时间分析")
    print("  └─ extract_answer_time()")
    print("\nSkill 5: 讲授分析")
    print("  └─ extract_speech_data()")
    print("\nSkill 6: 课堂流程重构")
    print("  └─ extract_course_reengineering()")
    print("\nSkill 7: 提问有效性分析")
    print("  ├─ extract_question_record()")
    print("  ├─ extract_bloom_classification()")
    print("  ├─ extract_teacher_appraisal()")
    print("  ├─ extract_question_answer_extra()")
    print("  └─ extract_question_score()")

    print("\n💡 提示:")
    print("  - 每个方法返回的数据可以直接用于对应的Skill")
    print("  - Skill 7需要组合多个方法的数据")
    print("  - 所有数据都是结构化的JSON格式")

if __name__ == "__main__":
    main()
