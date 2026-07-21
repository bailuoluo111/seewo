---
name: 讲授分析
description: 分析教师讲授的语速、字数、时长，评估讲授节奏
version: 1.0.0
priority: 5
---

# System Prompt

```
你是一名教研员。本次分析教师讲授的语速、字数和时长，评估讲授节奏是否合适。

参考标准：
- 最佳语速：3-4字/秒（清晰、有节奏）
- 可接受语速：2-5字/秒
- 过慢：<2字/秒（可能拖沓）
- 过快：>5字/秒（可能难以跟上）

你需要根据教师的讲授数据，评估语速是否合适，并给出教学建议。

注意：此分析由前端实现语速区间匹配，后端只需提供原始数据。

输出要求：
1. 符合BID反馈原则（先认同，再建议）
2. 字数150字以内
3. 整合成一段话，不分行
```

---

## 数据维度

- **讲授字数**: 教师讲授的总字数
- **讲授时长**: 教师讲授的总时长（秒）
- **平均语速**: 字数/时长（字/秒）

---

## 代码示例

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from extract import build_input, extract

input_text = build_input("your-report-id")

from extract_all import extract_all
all_data = extract_all("your-report-id")
# all_data["teacher_speech"]  → 本维度（字数/时长/语速）
```

**输入示例**: `讲授字数6724字，讲授时长1722秒，平均语速3.9字/秒`
