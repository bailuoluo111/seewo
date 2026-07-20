#!/usr/bin/env python3
"""
示例：如何在不同的 skill 中使用 SeewoDataExtractor

每个 skill 可以只调用自己需要的模块数据
"""

from seewo_data_extractor import SeewoDataExtractor
import json


def skill_student_interaction():
    """
    Skill 1: 学生互动分析
    只需要学生互动数据
    """
    print("=" * 60)
    print("Skill 1: 学生互动分析")
    print("=" * 60)

    extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

    # 获取课程基础信息
    course_info = extractor.get_course_info()
    print(f"\n课程: {course_info.get('课程名称')}")
    print(f"教师: {course_info.get('教师姓名')}")

    # 提取学生互动数据
    data = extractor.extract_student_interaction()
    print(f"\n学生互动数据:")
    print(f"  平均抬头率: {data.get('平均抬头率')}%")
    print(f"  平均举手率: {data.get('平均举手率')}%")
    print(f"  平均参与度: {data.get('平均参与度')}%")

    extractor.close()
    return data


def skill_student_behavior():
    """
    Skill 2: 学习行为分析
    只需要学习行为分布数据
    """
    print("\n" + "=" * 60)
    print("Skill 2: 学习行为分析")
    print("=" * 60)

    extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

    data = extractor.extract_student_behavior()
    print(f"\n学习行为分布:")
    print(f"  总时长: {data.get('总时长(秒)')}秒")
    print(f"  各行为类型占比: {data.get('各行为类型占比(%)')}")

    extractor.close()
    return data


def skill_solo_classification():
    """
    Skill 3: SOLO分类分析
    只需要回答建构分类数据
    """
    print("\n" + "=" * 60)
    print("Skill 3: SOLO分类分析")
    print("=" * 60)

    extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

    data = extractor.extract_solo_classification()
    print(f"\nSOLO分类:")
    print(f"  总回答数: {data.get('总回答数')}")
    print(f"  各等级回答数: {data.get('各等级回答数')}")
    print(f"  各等级占比: {data.get('各等级占比(%)')}")

    extractor.close()
    return data


def skill_answer_time():
    """
    Skill 4: 应答时间分析
    只需要应答时间数据
    """
    print("\n" + "=" * 60)
    print("Skill 4: 应答时间分析")
    print("=" * 60)

    extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

    data = extractor.extract_answer_time()
    print(f"\n应答时间分布:")
    print(f"  总回答数: {data.get('总回答数')}")
    print(f"  各时段占比: {data.get('各时段占比(%)')}")

    extractor.close()
    return data


def skill_teacher_speech():
    """
    Skill 5: 教师讲授分析
    只需要讲授分析数据
    """
    print("\n" + "=" * 60)
    print("Skill 5: 教师讲授分析")
    print("=" * 60)

    extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

    data = extractor.extract_speech_data()
    print(f"\n讲授分析:")
    print(f"  讲授字数: {data.get('讲授字数')}")
    print(f"  平均语速: {data.get('平均语速(字/秒)')}字/秒")
    print(f"  讲授时长: {data.get('讲授时长(秒)')}秒")

    extractor.close()
    return data


def skill_course_reengineering():
    """
    Skill 6: 课堂流程重构分析
    只需要课堂流程重构数据
    """
    print("\n" + "=" * 60)
    print("Skill 6: 课堂流程重构分析")
    print("=" * 60)

    extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

    data = extractor.extract_course_reengineering()
    print(f"\n课堂流程重构:")
    print(f"  课前到课中链接等级: {data.get('课前到课中链接', {}).get('等级')}")
    print(f"  课中到课后链接等级: {data.get('课中到课后链接', {}).get('等级')}")

    extractor.close()
    return data


def skill_question_effectiveness():
    """
    Skill 7: 提问有效性分析
    需要提问记录、布鲁姆分类、教师理答、问答额外结果、提问有效性得分
    """
    print("\n" + "=" * 60)
    print("Skill 7: 提问有效性分析")
    print("=" * 60)

    extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

    # 提取多个相关模块的数据
    question_record = extractor.extract_question_record()
    bloom = extractor.extract_bloom_classification()
    appraisal = extractor.extract_teacher_appraisal()
    extra = extractor.extract_question_answer_extra()
    score = extractor.extract_question_score()

    print(f"\n提问记录:")
    print(f"  提问总数: {question_record.get('提问总数')}")

    print(f"\n布鲁姆分类:")
    print(f"  总问题数: {bloom.get('总问题数')}")
    print(f"  高阶思维占比: {bloom.get('高阶思维占比(%)')}%")

    print(f"\n教师理答:")
    print(f"  总理答次数: {appraisal.get('总理答次数')}")
    print(f"  高质量理答占比: {appraisal.get('高质量理答占比(%)')}%")

    print(f"\n提问有效性得分: {score.get('提问有效性得分')}")

    extractor.close()

    return {
        "提问记录": question_record,
        "布鲁姆分类": bloom,
        "教师理答": appraisal,
        "问答额外结果": extra,
        "提问有效性得分": score,
    }


def extract_all_modules():
    """
    一次性提取所有模块（如果需要）
    """
    print("\n" + "=" * 60)
    print("提取所有模块数据")
    print("=" * 60)

    extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

    all_data = extractor.extract_all_modules()

    # 保存到文件
    with open("all_modules_data.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print("\n✓ 所有模块数据已保存到 all_modules_data.json")

    extractor.close()
    return all_data


if __name__ == "__main__":
    # 运行示例
    # 注意：首次运行需要登录
    # extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")
    # extractor.login()  # 首次运行需要登录
    # extractor.close()

    # 模拟不同的 skill 调用不同的模块
    skill_student_interaction()
    skill_student_behavior()
    skill_solo_classification()
    skill_answer_time()
    skill_teacher_speech()
    skill_course_reengineering()
    skill_question_effectiveness()

    # 或者一次性提取所有模块
    # extract_all_modules()
