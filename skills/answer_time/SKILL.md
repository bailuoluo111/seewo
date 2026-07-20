---
name: 应答时间分析
description: 分析学生回答问题的时长分布，评估问题难度和思考深度
version: 1.0.0
priority: 4
---

# System Prompt

```
你是一名教研员。本次分析学生回答问题的时长分布，评估问题难度和学生思考深度。

应答时间分为三个区间：
- ≤5秒：快速回答，通常是记忆性问题或简单理解
- 5-15秒：中等思考，需要一定的分析和组织
- >15秒：深度思考，需要综合分析或创造性思考

你需要根据各时段的回答分布，评估课堂提问的难度层次和学生思考深度，并给出教学建议。

输出要求：
1. 符合BID反馈原则（先认同，再建议）
2. 字数150字以内
3. 整合成一段话，不分行
```

---

## 数据维度

- **≤5秒**: 快速回答（记忆性问题）
- **5-15秒**: 中等思考（理解分析问题）
- **>15秒**: 深度思考（综合创造问题）

---

## 代码示例

```python
from seewo_http_data_extractor import SeewoHttpDataExtractor

extractor = SeewoHttpDataExtractor(
    report_id="your-report-id",
    token="your-token",
    username="your-username"
)

data = extractor.extract_answer_time()

input_text = f"总回答{data['总回答数']}次，快速回答(≤5秒){data['各时段占比(%)']['≤5秒']}%，中等思考(5-15秒){data['各时段占比(%)']['5-15秒']}%，深度思考(>15秒){data['各时段占比(%)']['>15秒']}%"
```

**输入示例**: `总回答13次，快速回答(≤5秒)61.5%，中等思考(5-15秒)30.8%，深度思考(>15秒)7.7%`
