#!/usr/bin/env python3
"""
交互式希沃课堂分析Agent

使用方法:
    python interactive_agent.py
"""

from simple_agent import SeewoAgent


def print_banner():
    """打印欢迎信息"""
    print("\n" + "=" * 80)
    print("🤖 希沃课堂分析Agent - 交互模式")
    print("=" * 80)
    print("\n支持的分析类型：")
    print("  1. 学生互动分析 - 关键词：互动、抬头率、举手率、参与")
    print("  2. 学习行为分析 - 关键词：学习行为、学习金字塔、知识留存")
    print("  3. SOLO分类分析 - 关键词：SOLO、回答质量、建构")
    print("  4. 应答时间分析 - 关键词：应答时间、回答时长、思考")
    print("  5. 讲授分析 - 关键词：讲授、语速、讲话")
    print("  6. 课堂流程重构 - 关键词：课堂流程、课前、课后")
    print("  7. 提问有效性分析 - 关键词：提问、布鲁姆、理答、问题")
    print("\n示例输入：")
    print("  • 帮我分析一下报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况")
    print("  • 看看这个课 96f58e78b80c462cb1194fa2f6ef4e97 的提问质量怎么样")
    print("  • 分析报告 96f58e78b80c462cb1194fa2f6ef4e97")
    print("\n输入 'quit' 或 'exit' 退出")
    print("=" * 80 + "\n")


def main():
    """主函数"""
    agent = SeewoAgent()
    print_banner()

    while True:
        try:
            # 获取用户输入
            user_input = input("📝 请输入: ").strip()

            # 检查退出命令
            if user_input.lower() in ['quit', 'exit', 'q', '退出']:
                print("\n👋 再见！\n")
                break

            # 空输入，跳过
            if not user_input:
                continue

            # 调用Agent分析
            result = agent.analyze(user_input)

            # 显示结果
            if result['success']:
                print("\n" + "─" * 80)
                print("📊 分析结果")
                print("─" * 80)
                print(f"\n💬 {result['analysis']}\n")
            else:
                print(f"\n❌ 错误: {result['error']}\n")

        except KeyboardInterrupt:
            print("\n\n👋 再见！\n")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {e}\n")


if __name__ == "__main__":
    main()
