#!/usr/bin/env python3
"""
批量提取希沃课堂数据脚本

从Excel文件中读取课程链接，提取course_id，批量调用API获取所有技能数据，
汇总成一个Excel文件，每行一个课程。

使用方法:
    cd /Users/zwj/Projects/seewo/batch_analysis
    python batch_extract.py
    python batch_extract.py --output my_result.xlsx
"""

import sys
import re
import time
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# 添加父目录到路径以便导入父目录中的模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from skill_helpers import get_all_skills_input
from seewo_http_data_extractor import SeewoHttpDataExtractor


# ============================================================================
# 主提取器类
# ============================================================================

class BatchDataExtractor:
    """批量课堂数据提取器：读取Excel → 提取course_id → 调用API → 汇总输出"""

    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.course_ids: List[str] = []
        self.results: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, str]] = []

    # -------------------------------------------------------------------------
    # Step 1: 从Excel提取课程ID
    # -------------------------------------------------------------------------

    def extract_course_ids(self) -> List[str]:
        """
        解析Excel，提取所有网页端链接中的course_id。

        URL格式：
          https://easiinsight.seewo.com/report/detail/<id>/home
          https://easiinsight.seewo.com/report/detail/js2/<id>/home
          https://easiinsight.seewo.com/analysis/report/detail/<id>/home
        """
        print(f"→ 读取Excel: {self.excel_path}")
        df = pd.read_excel(self.excel_path, header=None)

        url_pattern = re.compile(r'detail/(?:[^/]+/)?([0-9a-f]{32})', re.IGNORECASE)
        seen = set()
        course_ids = []

        for _, row in df.iterrows():
            for cell in row:
                if not isinstance(cell, str):
                    continue
                if 'easiinsight.seewo.com' not in cell:
                    continue
                m = url_pattern.search(cell)
                if m:
                    cid = m.group(1).lower()
                    if cid not in seen:
                        seen.add(cid)
                        course_ids.append(cid)
                    break  # 每行最多取一个ID

        self.course_ids = course_ids
        print(f"✓ 找到 {len(course_ids)} 个唯一课程ID")
        return course_ids

    # -------------------------------------------------------------------------
    # Step 2: 提取单个课程的全部数据
    # -------------------------------------------------------------------------

    def _extract_single_course(self, course_id: str) -> Dict[str, Any]:
        """
        对一个course_id调用所有Skill并整理成一行数据。

        数据来源映射（字段名来自实际API响应，通过seewo_http_data_extractor提取）：
          Skill 1 → 学生互动: 平均抬头率 / 平均举手率 / 平均参与度
          Skill 2 → 学习行为: 各行为类型占比, 知识留存率（加权估算）
          Skill 3 → SOLO分类: 各等级回答数及占比
          Skill 4 → 应答时间: 各时段回答数及占比
          Skill 5 → 讲授分析: 讲授字数 / 时长 / 语速
          Skill 6 → 课堂流程重构: 课前↔课中 / 课中↔课后 等级
          Skill 7 → 提问有效性: 布鲁姆分类 / 理答类型 / 提问有效性得分
        """
        # 一次性获取全部7个Skill的数据（每个Skill内部会复用同一个extractor实例的缓存）
        all_skills = get_all_skills_input(course_id)

        # ── 课程基本信息 ──────────────────────────────────────────────────────
        course_info = all_skills[1]['course_info']
        row: Dict[str, Any] = {
            'course_id':    course_id,
            'course_name':  course_info.get('课程名称', ''),
            'teacher_name': course_info.get('教师姓名', ''),
            'school':       course_info.get('学校名称', ''),
            'stage':        course_info.get('学段', ''),
            'subject':      course_info.get('学科', ''),
            'classroom':    course_info.get('教室', ''),
            'class_start':  course_info.get('上课时间', ''),
            'class_end':    course_info.get('下课时间', ''),
        }

        # ── Skill 1: 学生互动 ─────────────────────────────────────────────────
        s1 = all_skills[1]['raw_data']
        row['平均抬头率(%)']  = s1.get('平均抬头率', 0)
        row['平均举手率(%)']  = s1.get('平均举手率', 0)
        row['平均参与度(%)']  = s1.get('平均参与度', 0)

        # ── Skill 2: 学习行为 ─────────────────────────────────────────────────
        s2 = all_skills[2]['raw_data']
        pct2 = s2.get('各行为类型占比(%)', {})
        row['学习行为_被动学习占比(%)'] = pct2.get('0', 0)
        row['学习行为_讨论占比(%)']    = pct2.get('3', 0)
        row['学习行为_实践占比(%)']    = pct2.get('4', 0)
        row['学习行为_总时长(秒)']     = s2.get('总时长(秒)', 0)
        # 知识留存率：加权估算（被动*20% + 讨论*50% + 实践*75%）
        row['估算知识留存率(%)']       = round(all_skills[2].get('retention_rate', 0), 1)

        # ── Skill 3: SOLO分类 ─────────────────────────────────────────────────
        s3 = all_skills[3]['raw_data']
        s3_cnt = s3.get('各等级回答数', {})
        s3_pct = s3.get('各等级占比(%)', {})
        row['SOLO_总回答数']        = s3.get('总回答数', 0)
        row['SOLO_前结构_数量']     = s3_cnt.get('前结构', 0)
        row['SOLO_单点结构_数量']   = s3_cnt.get('单点结构', 0)
        row['SOLO_多点结构_数量']   = s3_cnt.get('多点结构', 0)
        row['SOLO_关联结构_数量']   = s3_cnt.get('关联结构', 0)
        row['SOLO_抽象拓展_数量']   = s3_cnt.get('抽象拓展', 0)
        row['SOLO_前结构_占比(%)']  = s3_pct.get('前结构', 0)
        row['SOLO_单点结构_占比(%)'] = s3_pct.get('单点结构', 0)
        row['SOLO_多点结构_占比(%)'] = s3_pct.get('多点结构', 0)
        row['SOLO_关联结构_占比(%)'] = s3_pct.get('关联结构', 0)
        row['SOLO_抽象拓展_占比(%)'] = s3_pct.get('抽象拓展', 0)

        # ── Skill 4: 应答时间 ─────────────────────────────────────────────────
        s4 = all_skills[4]['raw_data']
        s4_cnt = s4.get('各时段回答数', {})
        s4_pct = s4.get('各时段占比(%)', {})
        row['应答_总回答数']           = s4.get('总回答数', 0)
        row['应答_≤5秒_数量']         = s4_cnt.get('≤5秒', 0)
        row['应答_5-15秒_数量']       = s4_cnt.get('5-15秒', 0)
        row['应答_>15秒_数量']        = s4_cnt.get('>15秒', 0)
        row['应答_≤5秒_占比(%)']      = s4_pct.get('≤5秒', 0)
        row['应答_5-15秒_占比(%)']    = s4_pct.get('5-15秒', 0)
        row['应答_>15秒_占比(%)']     = s4_pct.get('>15秒', 0)

        # ── Skill 5: 讲授分析 ─────────────────────────────────────────────────
        s5 = all_skills[5]['raw_data']
        row['讲授_字数']            = s5.get('讲授字数', 0)
        row['讲授_时长(秒)']        = s5.get('讲授时长(秒)', 0)
        row['讲授_平均语速(字/秒)'] = s5.get('平均语速(字/秒)', 0)

        # ── Skill 6: 课堂流程重构 ─────────────────────────────────────────────
        s6 = all_skills[6]['raw_data']
        row['课前→课中_链接等级'] = s6.get('课前到课中链接', {}).get('等级', '')
        row['课中→课后_链接等级'] = s6.get('课中到课后链接', {}).get('等级', '')

        # ── Skill 7: 提问有效性 ───────────────────────────────────────────────
        s7 = all_skills[7]['raw_data']
        bloom    = s7.get('bloom', {})
        appraise = s7.get('appraisal', {})
        score    = s7.get('score', {})

        bloom_cnt = bloom.get('各等级问题数', {})
        bloom_pct = bloom.get('各等级占比(%)', {})
        row['布鲁姆_总问题数']      = bloom.get('总问题数', 0)
        row['布鲁姆_记忆_数量']     = bloom_cnt.get('记忆', 0)
        row['布鲁姆_理解_数量']     = bloom_cnt.get('理解', 0)
        row['布鲁姆_应用_数量']     = bloom_cnt.get('应用', 0)
        row['布鲁姆_分析_数量']     = bloom_cnt.get('分析', 0)
        row['布鲁姆_评价_数量']     = bloom_cnt.get('评价', 0)
        row['布鲁姆_创造_数量']     = bloom_cnt.get('创造', 0)
        row['布鲁姆_记忆_占比(%)']  = bloom_pct.get('记忆', 0)
        row['布鲁姆_理解_占比(%)']  = bloom_pct.get('理解', 0)
        row['布鲁姆_应用_占比(%)']  = bloom_pct.get('应用', 0)
        row['布鲁姆_分析_占比(%)']  = bloom_pct.get('分析', 0)
        row['布鲁姆_评价_占比(%)']  = bloom_pct.get('评价', 0)
        row['布鲁姆_创造_占比(%)']  = bloom_pct.get('创造', 0)
        row['布鲁姆_高阶思维占比(%)'] = bloom.get('高阶思维占比(%)', 0)

        appr_cnt = appraise.get('各类型次数', {})
        appr_pct = appraise.get('各类型占比(%)', {})
        row['理答_总次数']            = appraise.get('总理答次数', 0)
        row['理答_针对性肯定_数量']   = appr_cnt.get('针对性肯定', 0)
        row['理答_简单肯定_数量']     = appr_cnt.get('简单肯定', 0)
        row['理答_启发鼓励_数量']     = appr_cnt.get('启发鼓励', 0)
        row['理答_追问_数量']         = appr_cnt.get('追问', 0)
        row['理答_引导_数量']         = appr_cnt.get('引导', 0)
        row['理答_针对性肯定_占比(%)'] = appr_pct.get('针对性肯定', 0)
        row['理答_简单肯定_占比(%)']   = appr_pct.get('简单肯定', 0)
        row['理答_启发鼓励_占比(%)']   = appr_pct.get('启发鼓励', 0)
        row['理答_追问_占比(%)']       = appr_pct.get('追问', 0)
        row['理答_引导_占比(%)']       = appr_pct.get('引导', 0)
        row['理答_高质量理答占比(%)']  = appraise.get('高质量理答占比(%)', 0)

        row['提问有效性得分'] = score.get('提问有效性得分', 0)

        return row

    # -------------------------------------------------------------------------
    # Step 3: 批量处理
    # -------------------------------------------------------------------------

    def batch_extract(self, delay_seconds: float = 0.5) -> pd.DataFrame:
        """
        遍历所有course_id，依次提取数据并汇总。

        Args:
            delay_seconds: 每个课程之间的等待时间（避免触发速率限制）
        """
        total = len(self.course_ids)
        print(f"\n→ 开始批量提取（共 {total} 个课程，预计 {total * delay_seconds:.0f}+ 秒）")
        print("=" * 80)

        for idx, course_id in enumerate(self.course_ids, 1):
            print(f"\n[{idx:2d}/{total}] {course_id}", end="  ", flush=True)

            try:
                row = self._extract_single_course(course_id)
                self.results.append(row)
                print(f"✓  {row['course_name']} / {row['teacher_name']}")
            except Exception as e:
                self.errors.append({'course_id': course_id, 'error': str(e)})
                print(f"✗  {e}")

            # 非最后一个课程时等待
            if idx < total:
                time.sleep(delay_seconds)

        print("\n" + "=" * 80)
        print(f"提取完成：✓ {len(self.results)} 成功  ✗ {len(self.errors)} 失败")

        if self.errors:
            print("\n失败列表：")
            for err in self.errors:
                print(f"  • {err['course_id']}: {err['error']}")

        return pd.DataFrame(self.results) if self.results else pd.DataFrame()

    # -------------------------------------------------------------------------
    # Step 4: 导出Excel
    # -------------------------------------------------------------------------

    def export_to_excel(self, df: pd.DataFrame, output_path: str) -> None:
        """
        将汇总数据写入Excel，成功数据和失败记录分两个sheet。
        """
        if df.empty:
            print("⚠️  没有数据可导出")
            return

        print(f"\n→ 写入Excel: {output_path}")

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='课程数据汇总', index=False)
            if self.errors:
                pd.DataFrame(self.errors).to_excel(writer, sheet_name='提取失败', index=False)

        print(f"✓ 写入成功：{len(df)} 行 × {len(df.columns)} 列")

        # 展示关键指标的均值
        numeric_cols = [
            '平均抬头率(%)', '平均举手率(%)', '平均参与度(%)',
            '估算知识留存率(%)', '布鲁姆_高阶思维占比(%)',
            '理答_高质量理答占比(%)', '提问有效性得分',
        ]
        print("\n📊 关键指标均值（所有成功课程）：")
        for col in numeric_cols:
            if col in df.columns:
                vals = pd.to_numeric(df[col], errors='coerce').dropna()
                if not vals.empty:
                    print(f"   {col}: {vals.mean():.1f}")


# ============================================================================
# 入口
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='批量提取希沃课堂数据')
    parser.add_argument(
        '--excel',
        default='../【企微登录使用】对外演示的课堂反馈报告.xlsx',
        help='源Excel文件路径（默认：父目录下的演示报告）',
    )
    parser.add_argument(
        '--output',
        default=None,
        help='输出文件路径（默认：当前目录下带时间戳的xlsx）',
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='每个课程之间的间隔秒数（默认：0.5）',
    )
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("🤖  希沃课堂数据批量提取工具")
    print("=" * 80)

    # 解析Excel路径
    excel_path = Path(args.excel)
    if not excel_path.is_absolute():
        excel_path = (Path(__file__).parent / excel_path).resolve()

    if not excel_path.exists():
        print(f"❌ 找不到Excel文件：{excel_path}")
        return

    # 解析输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = Path(__file__).parent / f"课程数据汇总_{ts}.xlsx"

    # 执行
    extractor = BatchDataExtractor(str(excel_path))

    extractor.extract_course_ids()
    if not extractor.course_ids:
        print("❌ 未找到任何课程ID，请检查Excel文件格式")
        return

    df = extractor.batch_extract(delay_seconds=args.delay)

    if df.empty:
        print("\n❌ 没有成功提取任何数据")
        return

    extractor.export_to_excel(df, str(output_path))

    print(f"\n✅ 完成！结果文件：{output_path}\n")


if __name__ == '__main__':
    main()
