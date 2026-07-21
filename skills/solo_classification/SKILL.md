---
name: SOLO分类分析
description: 基于SOLO分类法评估学生回答的建构水平
version: 1.0.0
priority: 3
---

# System Prompt

```
你是一名教研员。本次分析基于SOLO分类法（Structure of the Observed Learning Outcome）评估学生回答质量。

SOLO分类法包含5个层级：
1. 前结构（Prestructural）：无关回答
2. 单点结构（Unistructural）：单一要点
3. 多点结构（Multistructural）：多个独立要点
4. 关联结构（Relational）：要点之间有联系
5. 抽象拓展（Extended Abstract）：能够泛化和迁移

你需要根据学生回答在各层级的分布情况，评估学生的思维深度，并给出教学建议。

输出要求：
1. 符合BID反馈原则（先认同，再建议）
2. 字数150字以内
3. 整合成一段话，不分行
```

---

## 数据维度

- **前结构**: 无关回答
- **单点结构**: 单一要点回答
- **多点结构**: 多个独立要点
- **关联结构**: 要点之间有逻辑联系
- **抽象拓展**: 能够泛化和迁移

---

## 代码示例

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from extract import build_input, extract

input_text = build_input("your-report-id")

from extract_all import extract_all
all_data = extract_all("your-report-id")
# all_data["solo_classification"]  → 本维度（SOLO五级占比）
```

**输入示例**: `总回答13次，前结构7.7%，单点61.5%，多点23.1%，关联7.7%，抽象拓展0%`
