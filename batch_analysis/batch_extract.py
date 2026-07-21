#!/usr/bin/env python3
"""
批量提取希沃课堂数据脚本（严格对齐前端展示字段）

从Excel读取课程链接 → 提取course_id → 调用API → 汇总成一个Excel，
每行一个课程。所有字段名和取值口径与前端报告页面保持一致。

字段来源（已用前端截图逐项校验）：
  学生互动数据   → studentStudyStatistic
  学习行为分布   → studentStudyBehavior（按时长占比，7类学习金字塔）
  回答建构分类   → solo（SOLO五级，占比排除无回答）
  应答时间       → studentAnswerClassification（回答时长分档）
  讲授分析       → speechData
  课堂流程重构   → courseProcessReengineering
  提问有效性     → bloom(提问总数) + teacherAppraisalClassification(评价次数) + questionScoreExplain(平均有效性)
  提问类型       → bloom（布鲁姆六级）
  候答时间       → questionAnswerExtraResult（近似：首个回答起始 - 提问结束）
  评价类型       → teacherAppraisalClassification

使用方法:
    cd /Users/zwj/Projects/seewo/batch_analysis
    python batch_extract.py
    python batch_extract.py --excel ../report.xlsx --output 结果.xlsx
"""

import sys
import re
import time
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path

# 导入同目录下的底层提取器（已移入本目录）
sys.path.insert(0, str(Path(__file__).parent))
from seewo_http_data_extractor import SeewoHttpDataExtractor


# ============================================================================
# 枚举映射（均已用真实数据校验）
# ============================================================================

# 学习行为分布：behaviorType 为学习金字塔层级顺序
BEHAVIOR_MAP = {
    '0': '听讲', '1': '阅读', '2': '视听', '3': '演示',
    '4': '讨论', '5': '实践', '6': '教给他人',
}
PASSIVE_TYPES = {'0', '1', '2', '3'}   # 被动学习
ACTIVE_TYPES = {'4', '5', '6'}         # 主动学习

# 回答建构分类（SOLO）
SOLO_MAP = {
    'FRONT_STRUCTURE': '前结构',
    'SINGLE_STRUCTURE': '单点结构',
    'MULTI_STRUCTURE': '多点结构',
    'ASSOCIATION_STRUCTURE': '关联结构',
    'ABSTRACT_EXTENDED_STRUCTURE': '抽象拓展结构',
}
SOLO_ORDER = ['前结构', '单点结构', '多点结构', '关联结构', '抽象拓展结构']

# 布鲁姆分类（提问类型）
BLOOM_MAP = {
    'REMEMBERING': '记忆', 'UNDERSTANDING': '理解', 'APPLYING': '应用',
    'ANALYZING': '分析', 'EVALUATING': '评价', 'CREATING': '创造',
}
BLOOM_ORDER = ['记忆', '理解', '应用', '分析', '评价', '创造']

# 评价类型（教师理答）
APPRAISAL_MAP = {
    'SIMPLE_POSITIVE': '简单肯定',
    'TARGETED_POSITIVE': '针对肯定',
    'INSPIRE_ENCOURAGE': '激励',
    'DIRECT_NEGATIVE': '否定',
    'REPEAT_QUESTION_OR_STUDENT_ANSWER': '重复',
}
APPRAISAL_ORDER = ['简单肯定', '针对肯定', '激励', '否定', '重复']

# 课堂流程重构等级
LEVEL_MAP = {
    'BEGINNER_LEVEL': '初阶',
    'PROGRESSIVE_LEVEL': '进阶',
    'INTERMEDIATE_LEVEL': '中阶',
    'ADVANCED_LEVEL': '高阶',
}

# 应答时间分档（秒）
ANSWER_TIME_ORDER = ['应答5秒以内', '应答5~15秒', '应答15秒以上']
# 候答时间分档（秒，近似）
WAIT_TIME_ORDER = ['等候3秒以内', '等候3~5秒', '等候5秒以上']

def _pct(counter: Dict[str, float], total: float) -> Dict[str, float]:
    """把计数字典转成占比(%)字典，保留1位小数。"""
    if not total:
        return {}
    return {k: round(v / total * 100, 1) for k, v in counter.items()}


class BatchDataExtractor:
    """批量课堂数据提取器：读取Excel → 提取course_id → 调用API → 汇总输出"""

    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.course_ids: List[str] = []
        self.results: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, str]] = []

    # ------------------------------------------------------------------
    # Step 1: 从Excel提取course_id
    # ------------------------------------------------------------------
    def extract_course_ids(self) -> List[str]:
        """解析Excel网页端链接列，提取detail后的32位course_id。"""
        print(f"→ 读取Excel: {self.excel_path}")
        df = pd.read_excel(self.excel_path, header=None)
        pat = re.compile(r'detail/(?:[^/]+/)?([0-9a-f]{32})', re.IGNORECASE)
        seen, ids = set(), []
        for _, row in df.iterrows():
            for cell in row:
                if isinstance(cell, str) and 'easiinsight.seewo.com' in cell:
                    m = pat.search(cell)
                    if m and m.group(1).lower() not in seen:
                        seen.add(m.group(1).lower())
                        ids.append(m.group(1).lower())
                    break
        self.course_ids = ids
        print(f"✓ 找到 {len(ids)} 个唯一课程ID")
        return ids

    # ------------------------------------------------------------------
    # Step 2: 提取单个课程 → 一行数据（字段名对齐前端）
    # ------------------------------------------------------------------
    def _extract_single_course(self, course_id: str) -> Dict[str, Any]:
        ext = SeewoHttpDataExtractor(course_id)
        info = ext.get_course_info()

        row: Dict[str, Any] = {
            'course_id':   course_id,
            '课程名称':     info.get('课程名称', ''),
            '教师姓名':     info.get('教师姓名', ''),
            '学校':        info.get('学校名称', ''),
            '学段':        info.get('学段', ''),
            '学科':        info.get('学科', ''),
        }

        row.update(self._student_interaction(ext))   # 学生互动数据
        row.update(self._study_behavior(ext))        # 学习行为分布
        row.update(self._solo(ext))                  # 回答建构分类
        row.update(self._answer_time(ext))           # 应答时间
        row.update(self._speech(ext))                # 讲授分析
        row.update(self._reengineering(ext))         # 课堂流程重构
        row.update(self._question_effectiveness(ext))  # 提问有效性+提问类型+评价类型
        row.update(self._wait_time(ext))             # 候答时间（近似）
        return row

    # ── 学生互动数据 ──────────────────────────────────────────────────
    def _student_interaction(self, ext) -> Dict[str, Any]:
        d = ext.fetch_api('studentStudyStatistic', silent=True) or {}
        det = d.get('reportDetail', {}) or {}
        return {
            '学生互动-平均抬头率(%)': round(det.get('raiseHeadRatio', 0) * 100, 1),
            '学生互动-平均举手率(%)': round(det.get('handUpRatio', 0) * 100, 1),
            '学生互动-平均参与度(%)': round(det.get('answerRatio', 0) * 100, 1),
        }

    # ── 学习行为分布（按时长占比，7类学习金字塔）────────────────────────
    def _study_behavior(self, ext) -> Dict[str, Any]:
        d = ext.fetch_api('studentStudyBehavior', silent=True) or {}
        det = d.get('reportDetail', []) or []
        dur: Dict[str, float] = {}
        for it in det:
            bt = str(it.get('behaviorType'))
            dur[bt] = dur.get(bt, 0) + it.get('durationTimeMills', 0)
        total = sum(dur.values())
        out = {
            '学习行为-被动学习(%)': round(sum(v for k, v in dur.items() if k in PASSIVE_TYPES) / total * 100, 1) if total else 0,
            '学习行为-主动学习(%)': round(sum(v for k, v in dur.items() if k in ACTIVE_TYPES) / total * 100, 1) if total else 0,
        }
        for code, name in BEHAVIOR_MAP.items():
            out[f'学习行为-{name}(%)'] = round(dur.get(code, 0) / total * 100, 1) if total else 0
        return out

    # ── 回答建构分类（SOLO五级，占比排除无回答）────────────────────────
    def _solo(self, ext) -> Dict[str, Any]:
        d = ext.fetch_api('solo', silent=True) or {}
        det = d.get('reportDetail', []) or []
        cnt: Dict[str, int] = {}
        for it in det:
            name = SOLO_MAP.get(it.get('soloAnswerType'))
            if name:  # 忽略 NO_ANSWER 等非五级项
                cnt[name] = cnt.get(name, 0) + 1
        total = sum(cnt.values())
        out = {'回答建构分类-总回答数': total}
        pct = _pct(cnt, total)
        for name in SOLO_ORDER:
            out[f'回答建构分类-{name}(%)'] = pct.get(name, 0)
        return out

    # ── 应答时间（回答时长分档 ≤5 / 5-15 / >15 秒）─────────────────────
    def _answer_time(self, ext) -> Dict[str, Any]:
        d = ext.fetch_api('studentAnswerClassification', silent=True) or {}
        det = d.get('reportDetail', []) or []
        b = {'应答5秒以内': 0, '应答5~15秒': 0, '应答15秒以上': 0}
        for it in det:
            s, e = it.get('startTime'), it.get('endTime')
            if s is None or e is None:
                continue
            g = (e - s) / 1000
            if g <= 5:
                b['应答5秒以内'] += 1
            elif g <= 15:
                b['应答5~15秒'] += 1
            else:
                b['应答15秒以上'] += 1
        total = sum(b.values())
        out = {'应答时间-总回答数': total}
        pct = _pct(b, total)
        for name in ANSWER_TIME_ORDER:
            out[f'应答时间-{name}(%)'] = pct.get(name, 0)
        return out

    # ── 讲授分析 ──────────────────────────────────────────────────────
    def _speech(self, ext) -> Dict[str, Any]:
        d = ext.fetch_api('speechData', silent=True) or {}
        det = d.get('reportDetail', {}) or {}
        wc = det.get('speechWordCount', 0)
        dur = det.get('speechDurationInSeconds', 0)
        return {
            '讲授分析-平均语速(字/秒)': round(wc / dur, 1) if dur else 0,
            '讲授分析-讲授字数(词)': wc,
        }

    # ── 课堂流程重构 ──────────────────────────────────────────────────
    def _reengineering(self, ext) -> Dict[str, Any]:
        d = ext.fetch_api('courseProcessReengineering', silent=True) or {}
        det = d.get('reportDetail', {}) or {}
        pre = det.get('preClassToInClassLink') or {}
        post = det.get('inClassToPostClassLink') or {}
        return {
            '课堂流程重构-课前与课中链接': LEVEL_MAP.get(pre.get('level'), pre.get('level', '')),
            '课堂流程重构-课中与课后链接': LEVEL_MAP.get(post.get('level'), post.get('level', '')),
        }

    # ── 提问有效性（三卡片）+ 提问类型（布鲁姆）+ 评价类型 ──────────────
    def _question_effectiveness(self, ext) -> Dict[str, Any]:
        out: Dict[str, Any] = {}

        # 布鲁姆分类 → 提问总数 + 提问类型占比
        bd = ext.fetch_api('bloom', silent=True) or {}
        det = bd.get('reportDetail')
        stats = det.get('statistics', []) if isinstance(det, dict) else (det or [])
        bloom_cnt: Dict[str, int] = {}
        for it in stats:
            name = BLOOM_MAP.get(it.get('problemType'))
            if name:
                bloom_cnt[name] = it.get('value', 0)
        total_q = sum(bloom_cnt.values())
        out['提问有效性-提问总数'] = total_q
        bpct = _pct(bloom_cnt, total_q)
        for name in BLOOM_ORDER:
            out[f'提问类型-{name}(%)'] = bpct.get(name, 0)

        # 教师理答 → 评价次数 + 评价类型占比
        ad = ext.fetch_api('teacherAppraisalClassification', silent=True) or {}
        appr = ad.get('reportDetail', []) or []
        appr_cnt: Dict[str, int] = {}
        for it in appr:
            name = APPRAISAL_MAP.get(it.get('teacherAppraisalType'))
            if name:
                appr_cnt[name] = appr_cnt.get(name, 0) + 1
        total_a = len(appr)
        out['提问有效性-评价次数'] = total_a
        apct = _pct(appr_cnt, sum(appr_cnt.values()))
        for name in APPRAISAL_ORDER:
            out[f'评价类型-{name}(%)'] = apct.get(name, 0)

        # 提问有效性得分
        sd = ext.fetch_api('questionScoreExplain', silent=True) or {}
        sdet = sd.get('reportDetail', {}) or {}
        out['提问有效性-平均有效性(分)'] = sdet.get('score', 0)
        return out

    # ── 候答时间（近似：首个回答起始 - 提问结束）────────────────────────
    def _wait_time(self, ext) -> Dict[str, Any]:
        d = ext.fetch_api('questionAnswerExtraResult', silent=True) or {}
        det = d.get('reportDetail', []) or []
        b = {'等候3秒以内': 0, '等候3~5秒': 0, '等候5秒以上': 0}
        for it in det:
            q = it.get('question')
            al = it.get('answerList') or []
            if not q or not al:
                continue
            gap = (al[0].get('startTime', 0) - q.get('endTime', 0)) / 1000
            if gap < 0:
                continue
            if gap <= 3:
                b['等候3秒以内'] += 1
            elif gap <= 5:
                b['等候3~5秒'] += 1
            else:
                b['等候5秒以上'] += 1
        total = sum(b.values())
        pct = _pct(b, total)
        # 列名加 (近似) 后缀，提示该口径为反推、非前端精确值
        return {f'候答时间-{name}(%)(近似)': pct.get(name, 0) for name in WAIT_TIME_ORDER}

    # ------------------------------------------------------------------
    # Step 3: 批量处理
    # ------------------------------------------------------------------
    def batch_extract(self, delay: float = 0.3) -> pd.DataFrame:
        total = len(self.course_ids)
        print(f"\n→ 开始批量提取（共 {total} 个课程）")
        print("=" * 80)
        for i, cid in enumerate(self.course_ids, 1):
            print(f"[{i:2d}/{total}] {cid}", end="  ", flush=True)
            try:
                row = self._extract_single_course(cid)
                self.results.append(row)
                print(f"✓  {row['课程名称']} / {row['教师姓名']}")
            except Exception as e:
                self.errors.append({'course_id': cid, 'error': str(e)})
                print(f"✗  {e}")
            if i < total:
                time.sleep(delay)
        print("=" * 80)
        print(f"完成：✓ {len(self.results)} 成功  ✗ {len(self.errors)} 失败")
        for err in self.errors:
            print(f"  • {err['course_id']}: {err['error']}")
        return pd.DataFrame(self.results) if self.results else pd.DataFrame()

    # ------------------------------------------------------------------
    # Step 4: 导出Excel
    # ------------------------------------------------------------------
    def export_to_excel(self, df: pd.DataFrame, output_path: str) -> None:
        if df.empty:
            print("⚠️  没有数据可导出")
            return
        print(f"\n→ 写入Excel: {output_path}")
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='课程数据汇总', index=False)
            if self.errors:
                pd.DataFrame(self.errors).to_excel(writer, sheet_name='提取失败', index=False)
        print(f"✓ 写入成功：{len(df)} 行 × {len(df.columns)} 列")


# ============================================================================
# 入口
# ============================================================================

def main():
    import argparse
    p = argparse.ArgumentParser(description='批量提取希沃课堂数据（对齐前端字段）')
    p.add_argument('--excel', default='report.xlsx', help='源Excel路径')
    p.add_argument('--output', default=None, help='输出xlsx路径')
    p.add_argument('--delay', type=float, default=0.3, help='课程间隔秒数')
    args = p.parse_args()

    print("\n" + "=" * 80)
    print("🤖  希沃课堂数据批量提取工具")
    print("=" * 80)

    excel = Path(args.excel)
    if not excel.is_absolute():
        excel = (Path(__file__).parent / excel).resolve()
    if not excel.exists():
        print(f"❌ 找不到Excel文件：{excel}")
        return

    if args.output:
        out = Path(args.output)
    else:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out = Path(__file__).parent / f"课程数据汇总_{ts}.xlsx"

    ext = BatchDataExtractor(str(excel))
    ext.extract_course_ids()
    if not ext.course_ids:
        print("❌ 未找到任何课程ID")
        return
    df = ext.batch_extract(delay=args.delay)
    if df.empty:
        print("\n❌ 没有成功提取任何数据")
        return
    ext.export_to_excel(df, str(out))
    print(f"\n✅ 完成！结果文件：{out}\n")


if __name__ == '__main__':
    main()
