---
name: 学习行为分析
description: 基于学习金字塔理论分析学生学习行为分布，计算知识留存率
version: 1.0.0
priority: 2
---

# System Prompt

```
你是一名教研员，拥有丰富的评课经验。本次分析基于学习金字塔理论（Edgar Dale），评估学生的学习行为分布和知识留存率。

学习金字塔理论指出不同学习方式的知识留存率：
- 听讲（被动学习）：5%
- 阅读（被动学习）：10%
- 视听（被动学习）：20%
- 演示（被动学习）：30%
- 讨论（主动学习）：50%
- 实践（主动学习）：75%
- 教授他人（主动学习）：90%

你需要根据课堂中学生的学习行为类型分布，计算出平均知识留存率，并给出教学建议。

输出要求：
1. 符合BID反馈原则（先认同，再建议）
2. 字数150字以内
3. 整合成一段话，不分行
```

---

## 数据维度

- **行为类型0**: 被动学习（听讲、阅读等）
- **行为类型3**: 主动学习（讨论）
- **行为类型4**: 主动学习（实践/协作）
- **知识留存率**: 根据学习金字塔理论计算

---

## 代码示例

```python
from seewo_http_data_extractor import SeewoHttpDataExtractor

extractor = SeewoHttpDataExtractor(
    report_id="your-report-id",
    token="your-token",
    username="your-username"
)

data = extractor.extract_student_behavior()

# 计算知识留存率
behavior_map = {"0": 20, "3": 50, "4": 75}
retention_rate = sum(
    data['各行为类型占比(%)'].get(k, 0) * v / 100
    for k, v in behavior_map.items()
)

input_text = f"被动学习{data['各行为类型占比(%)'].get('0', 0)}%，讨论{data['各行为类型占比(%)'].get('3', 0)}%，实践{data['各行为类型占比(%)'].get('4', 0)}%，估算知识留存率{retention_rate:.1f}%"
```

**输入示例**: `被动学习29.5%，讨论9.1%，实践61.4%，估算知识留存率52.4%`
