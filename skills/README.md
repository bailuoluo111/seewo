# 希沃课堂观察七维度 Skills 总览

本目录包含7个课堂观察分析skill，每个skill对应一个分析维度，独立提取和分析数据。

## 📁 Skills 结构

```
skills/
├── student_interaction/         # Skill 1: 学生互动分析
│   └── SKILL.md
├── student_behavior/            # Skill 2: 学习行为分析
│   └── SKILL.md
├── solo_classification/         # Skill 3: SOLO分类分析
│   └── SKILL.md
├── answer_time/                 # Skill 4: 应答时间分析
│   └── SKILL.md
├── teacher_speech/              # Skill 5: 讲授分析
│   └── SKILL.md
├── course_reengineering/        # Skill 6: 课堂流程重构分析
│   └── SKILL.md
└── question_effectiveness/      # Skill 7: 提问有效性分析
    └── SKILL.md
```

## 🎯 Skills 概览

| # | Skill名称 | Priority | 使用LLM | 数据源 | 说明 |
|---|----------|---------|---------|-------|------|
| 1 | 学生互动分析 | 1 | ✅ | `extract_student_interaction()` | 分析抬头率、举手率、参与度 |
| 2 | 学习行为分析 | 2 | ✅ | `extract_student_behavior()` | 基于学习金字塔计算知识留存率 |
| 3 | SOLO分类分析 | 3 | ✅ | `extract_solo_classification()` | 评估学生回答的建构水平 |
| 4 | 应答时间分析 | 4 | ✅ | `extract_answer_time()` | 分析学生回答时长分布 |
| 5 | 讲授分析 | 5 | ❌ | `extract_speech_data()` | 前端规则匹配语速区间 |
| 6 | 课堂流程重构 | 6 | ✅ | `extract_course_reengineering()` | 评估课堂流程重构度 |
| 7 | 提问有效性 | 7 | ✅ | 多个方法组合 | 综合评估提问质量 |

## 📊 各Skill详细信息

### Skill 1: 学生互动分析

**元数据**:
```yaml
name: 学生互动分析
description: 分析学生课堂互动数据，包括平均抬头率、平均举手率和平均参与度
version: 1.0.0
priority: 1
```

**数据需求**:
- 平均抬头率 (%)
- 平均举手率 (%)
- 平均参与度 (%)
- 学段信息

**调用方法**:
```python
extractor.get_course_info()           # 获取学段
extractor.extract_student_interaction() # 获取互动数据
```

**LLM参数**:
- Model: VOLC_DOUBAO_SEEK_1_6
- Max Tokens: 32000
- Output: 150字以内，BID反馈模式

---

### Skill 2: 学习行为分析

**元数据**:
```yaml
name: 学习行为分析
description: 基于学习金字塔理论计算知识留存率，评估主动学习和被动学习占比
version: 1.0.0
priority: 2
```

**数据需求**:
- 总时长(秒)
- 各行为类型时长(秒)
- 各行为类型占比(%)

**调用方法**:
```python
extractor.extract_student_behavior()
```

**LLM参数**:
- Model: VOLC_DOUBAO_SEEK_1_6
- Max Tokens: 32000
- Output: 150字以内，BID反馈模式

**注意事项**:
- 需要确认behaviorType编码映射关系
- 知识留存率根据学习金字塔理论计算

---

### Skill 3: SOLO分类分析

**元数据**:
```yaml
name: SOLO分类分析
description: 基于SOLO理论分析学生回答建构水平，评估学生思维深度
version: 1.0.0
priority: 3
```

**数据需求**:
- 总回答数
- 各等级回答数（前结构、单点、多点、关联、抽象拓展）
- 各等级占比(%)

**调用方法**:
```python
extractor.extract_solo_classification()
```

**LLM参数**:
- Model: VOLC_DOUBAO_SEEK_1_6 或 VOLC_DOUBAO_1_5_PRO_32K
- Max Tokens: 16000
- Temperature: 0.7
- Top P: 0.7
- Output: 150字以内

**特别要求**:
- 不使用专业术语（如"单点结构"），要转化为通俗表达
- 必须整合成一段话，不分行

---

### Skill 4: 应答时间分析

**元数据**:
```yaml
name: 应答时间分析
description: 分析学生回答问题的时长分布，评估问题难度与思考深度
version: 1.0.0
priority: 4
```

**数据需求**:
- 总回答数
- 各时段回答数（≤5秒、5-15秒、>15秒）
- 各时段占比(%)

**调用方法**:
```python
extractor.get_course_info()       # 获取学段
extractor.extract_answer_time()   # 获取时间数据
```

**LLM参数**:
- Model: VOLC_DOUBAO_1_5_PRO_32K
- Max Tokens: 16000
- Temperature: 0.7
- Top P: 0.7
- Output: 150字以内

**评价标准**:
根据学段不同，理想时间分布有所不同：
- 小学：≤5秒(40-50%)，5-15秒(40-50%)，>15秒(10-20%)
- 初中：≤5秒(30-40%)，5-15秒(40-50%)，>15秒(20-30%)
- 高中：≤5秒(20-30%)，5-15秒(40-50%)，>15秒(30-40%)

---

### Skill 5: 讲授分析

**元数据**:
```yaml
name: 讲授分析
description: 分析教师讲授情况，根据语速区间匹配生成评价（前端规则，不用LLM）
version: 1.0.0
priority: 5
```

**数据需求**:
- 讲授字数
- 平均语速(字/秒)
- 讲授时长(秒)

**调用方法**:
```python
extractor.extract_speech_data()
```

**实现方式**:
- **不调用LLM**
- 前端根据语速区间规则匹配评价文案
- 语速区间：<2.0, 2.0-2.5, 2.5-3.5, 3.5-4.5, >4.5

**语速评价**:
- < 2.0: 语速偏慢
- 2.0-2.5: 语速较慢
- 2.5-3.5: 语速适中 ⭐
- 3.5-4.5: 语速略快
- > 4.5: 语速偏快

---

### Skill 6: 课堂流程重构分析

**元数据**:
```yaml
name: 课堂流程重构分析
description: 评估课堂流程重构度，分析课前课中、课中课后链接
version: 1.0.0
priority: 6
```

**数据需求**:
- 课前到课中链接（等级 + 3个子任务）
- 课中到课后链接（等级 + 1个子任务）
- 每个子任务包含：名称、分数、原因

**调用方法**:
```python
extractor.extract_course_reengineering()
```

**LLM参数**:
- Model: VOLC_DOUBAO_SEED_1_8
- Max Tokens: 32000
- Output: 不超过200字

**特殊处理**:
- System Prompt包含10个占位符，需要从数据中提取并替换
- 输出格式：整体评价 + 具体例子 + 改进建议（换行）
- 不使用markdown格式

---

### Skill 7: 提问有效性分析

**元数据**:
```yaml
name: 提问有效性分析
description: 综合评估课堂提问有效性，基于布鲁姆、SOLO、理答分类计算得分
version: 1.0.0
priority: 7
```

**数据需求**:
- 布鲁姆分类数据（各等级问题数）
- 教师理答数据（各类型次数）
- SOLO分类数据（各等级回答数）
- 提问记录（展示用）
- 问答额外结果（展示用）

**调用方法**:
```python
bloom = extractor.extract_bloom_classification()
appraisal = extractor.extract_teacher_appraisal()
solo = extractor.extract_solo_classification()
question = extractor.extract_question_record()
extra = extractor.extract_question_answer_extra()
```

**得分计算**:
```
提问有效性得分 = (布鲁姆平均分 + 理答平均分 + SOLO平均分) / 3
```

**水平划分**:
- 60-77分: 初阶水平
- 78-94分: 进阶水平
- 95-100分: 高阶水平

**LLM参数**:
- Model: VOLC_DOUBAO_SEEK_1_6
- Max Tokens: 32000
- Output: 不超过200字，使用三明治表达法

---

## 🔧 快速开始

### 1. 导入提取器

```python
import sys
sys.path.append('/Users/zwj/Projects/seewo')

from seewo_data_extractor import SeewoDataExtractor
```

### 2. 创建提取器实例

```python
extractor = SeewoDataExtractor(report_id="你的报告ID")
```

### 3. 提取各Skill所需数据

```python
# Skill 1: 学生互动
course_info = extractor.get_course_info()
interaction = extractor.extract_student_interaction()

# Skill 2: 学习行为
behavior = extractor.extract_student_behavior()

# Skill 3: SOLO分类
solo = extractor.extract_solo_classification()

# Skill 4: 应答时间
answer_time = extractor.extract_answer_time()

# Skill 5: 讲授分析
speech = extractor.extract_speech_data()

# Skill 6: 课堂流程重构
reengineering = extractor.extract_course_reengineering()

# Skill 7: 提问有效性
bloom = extractor.extract_bloom_classification()
appraisal = extractor.extract_teacher_appraisal()
solo = extractor.extract_solo_classification()
question = extractor.extract_question_record()
extra = extractor.extract_question_answer_extra()
```

### 4. 关闭提取器

```python
extractor.close()
```

---

## 📝 文档说明

每个skill目录下的`README.md`包含：

1. **元数据** (frontmatter)
   - name: Skill名称
   - description: 功能描述
   - version: 版本号
   - priority: 优先级

2. **功能说明**
   - 理论基础
   - 分析维度
   - 评价标准

3. **数据来源**
   - 需要调用的提取方法
   - 数据字段说明

4. **使用方法**
   - 完整代码示例
   - 数据提取步骤

5. **System Prompt**
   - 完整的System Prompt
   - User Prompt示例

6. **输出示例**
   - 输入数据示例
   - 输出文案示例

7. **技术参数**
   - LLM模型
   - Token限制
   - 温度等参数

8. **注意事项**
   - 特殊要求
   - 常见问题

---

## 🚀 与数据提取器集成

所有skill都基于 `seewo_data_extractor.py` 提供的数据提取方法：

| 提取方法 | 返回数据 | 对应Skill |
|---------|---------|----------|
| `get_course_info()` | 课程基础信息 | 1, 4 |
| `extract_student_interaction()` | 学生互动数据 | 1 |
| `extract_student_behavior()` | 学习行为分布 | 2 |
| `extract_solo_classification()` | SOLO分类 | 3, 7 |
| `extract_answer_time()` | 应答时间 | 4 |
| `extract_speech_data()` | 讲授分析 | 5 |
| `extract_course_reengineering()` | 课堂流程重构 | 6 |
| `extract_bloom_classification()` | 布鲁姆分类 | 7 |
| `extract_teacher_appraisal()` | 教师理答 | 7 |
| `extract_question_record()` | 提问记录 | 7 |
| `extract_question_answer_extra()` | 问答统计 | 7 |

---

## 📊 Skills依赖关系

```
报告ID
  ↓
SeewoDataExtractor
  ├─→ Skill 1 (学生互动)
  ├─→ Skill 2 (学习行为)
  ├─→ Skill 3 (SOLO分类)
  ├─→ Skill 4 (应答时间)
  ├─→ Skill 5 (讲授分析) - 不用LLM
  ├─→ Skill 6 (课堂流程重构)
  └─→ Skill 7 (提问有效性) - 需要多个数据源
```

---

## 💡 使用建议

1. **独立使用**: 每个skill可以独立使用，只提取所需数据
2. **批量分析**: 可以一次性提取所有数据，然后分别调用各skill的LLM
3. **复用实例**: 同一个extractor实例可以调用多个提取方法
4. **异常处理**: 数据为空时，各提取方法会返回空字典 `{}`
5. **成本控制**: Skill 5不调用LLM，可以降低成本

---

## 🔍 调试和测试

```bash
# 测试所有数据提取方法
cd /Users/zwj/Projects/seewo
python test_all_modules.py

# 测试单个skill的数据提取
python -c "
from seewo_data_extractor import SeewoDataExtractor
e = SeewoDataExtractor('你的报告ID')
data = e.extract_student_interaction()
print(data)
e.close()
"
```

---

*最后更新：2026-07-20*
*版本：1.0.0*
