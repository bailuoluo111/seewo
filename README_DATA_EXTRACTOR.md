# 希沃课堂观察数据提取器

模块化的数据提取工具，支持按需提取7个课堂观察模块的数据。

## 文件说明

- `seewo_data_extractor.py` - 核心提取器类，包含所有模块的提取方法
- `example_usage.py` - 使用示例，演示如何在不同 skill 中调用
- `seewo_state.json` - 登录状态保存文件（自动生成）

## 快速开始

### 1. 首次使用 - 登录

```python
from seewo_data_extractor import SeewoDataExtractor

extractor = SeewoDataExtractor(report_id="你的报告ID")
extractor.login()  # 会打开浏览器，需要手动扫码登录
extractor.close()
```

登录成功后，会保存登录状态到 `seewo_state.json`，下次可以直接使用。

### 2. 提取单个模块数据

```python
from seewo_data_extractor import SeewoDataExtractor

# 创建提取器实例
extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

# 提取学生互动数据
data = extractor.extract_student_interaction()
print(data)

# 关闭浏览器
extractor.close()
```

### 3. 提取多个模块数据

```python
extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

# 提取多个模块
interaction = extractor.extract_student_interaction()
behavior = extractor.extract_student_behavior()
solo = extractor.extract_solo_classification()

extractor.close()
```

### 4. 一次性提取所有模块

```python
extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

all_data = extractor.extract_all_modules()

extractor.close()
```

## 7个模块方法说明

### 模块1: 学生互动数据

```python
data = extractor.extract_student_interaction()
```

**返回数据结构:**
```json
{
  "平均抬头率": 72.6,
  "平均举手率": 35.8,
  "平均参与度": 16.8
}
```

---

### 模块2: 学习行为分布

```python
data = extractor.extract_student_behavior()
```

**返回数据结构:**
```json
{
  "总时长(秒)": 4101.4,
  "各行为类型时长(秒)": {
    "3": 375.0,
    "4": 2517.0,
    "0": 1209.4
  },
  "各行为类型占比(%)": {
    "3": 9.1,
    "4": 61.4,
    "0": 29.5
  }
}
```

**注意:** `behaviorType` 是数字编码，需要向业务方确认映射关系。

---

### 模块3: 回答建构分类 (SOLO)

```python
data = extractor.extract_solo_classification()
```

**返回数据结构:**
```json
{
  "总回答数": 13,
  "各等级回答数": {
    "单点结构": 8,
    "前结构": 1,
    "多点结构": 3,
    "关联结构": 1
  },
  "各等级占比(%)": {
    "单点结构": 61.5,
    "前结构": 7.7,
    "多点结构": 23.1,
    "关联结构": 7.7
  }
}
```

**SOLO等级说明:**
- **前结构** - 躲避回答或重复问题
- **单点结构** - 只有一个思路，回答简短
- **多点结构** - 多个思路但无联系
- **关联结构** - 多个思路有机整合
- **抽象拓展** - 拓展至新领域

---

### 模块4: 应答时间

```python
data = extractor.extract_answer_time()
```

**返回数据结构:**
```json
{
  "总回答数": 13,
  "各时段回答数": {
    "≤5秒": 8,
    "5-15秒": 4,
    ">15秒": 1
  },
  "各时段占比(%)": {
    "≤5秒": 61.5,
    "5-15秒": 30.8,
    ">15秒": 7.7
  }
}
```

---

### 模块5: 讲授分析

```python
data = extractor.extract_speech_data()
```

**返回数据结构:**
```json
{
  "讲授字数": 6724,
  "平均语速(字/秒)": 3.9,
  "讲授时长(秒)": 1722
}
```

---

### 模块6: 课堂流程重构

```python
data = extractor.extract_course_reengineering()
```

**返回数据结构:**
```json
{
  "课前到课中链接": {
    "等级": "ADVANCED_LEVEL",
    "子任务": [
      {
        "名称": "offerStudyResource",
        "分数": "GOOD_REFACTOR",
        "原因": "..."
      }
    ]
  },
  "课中到课后链接": {
    "等级": "ADVANCED_LEVEL",
    "子任务": [...]
  }
}
```

**等级说明:**
- `INITIAL_LEVEL` - 初阶（无重构）
- `PRELIMINARY_LEVEL` - 进阶（初步重构）
- `INTERMEDIATE_LEVEL` - 中阶（良好重构）
- `ADVANCED_LEVEL` - 高阶（高水平重构）

---

### 模块7: 提问有效性（综合多个子模块）

#### 7.1 提问记录
```python
data = extractor.extract_question_record()
```

#### 7.2 布鲁姆提问分类
```python
data = extractor.extract_bloom_classification()
```

**返回数据结构:**
```json
{
  "总问题数": 37,
  "各等级问题数": {
    "记忆": 5,
    "理解": 14,
    "应用": 6,
    "分析": 7,
    "评价": 3,
    "创造": 2
  },
  "各等级占比(%)": {...},
  "高阶思维占比(%)": 32.4
}
```

#### 7.3 教师理答分类
```python
data = extractor.extract_teacher_appraisal()
```

**返回数据结构:**
```json
{
  "总理答次数": 5,
  "各类型次数": {
    "针对性肯定": 2,
    "简单肯定": 2,
    "启发鼓励": 1
  },
  "各类型占比(%)": {...},
  "高质量理答占比(%)": 20.0
}
```

#### 7.4 问答额外结果
```python
data = extractor.extract_question_answer_extra()
```

#### 7.5 提问有效性得分
```python
data = extractor.extract_question_score()
```

**返回数据结构:**
```json
{
  "提问有效性得分": 71.0
}
```

---

## 获取课程基础信息

```python
info = extractor.get_course_info()
```

**返回数据结构:**
```json
{
  "课程ID": "96f58e78...",
  "课程名称": "可能性的大小-新",
  "教师姓名": "徐老师",
  "学校名称": "上海市民办丽英小学",
  "学段": "小学",
  "学科": "数学",
  "教室": "音乐教室1",
  "上课时间": "2025-04-23 10:44:30",
  "下课时间": "2025-04-23 11:30:19"
}
```

---

## 在不同 Skill 中的使用场景

### Skill 1: 学生互动分析

```python
def analyze_student_interaction(report_id: str):
    """分析学生互动情况"""
    extractor = SeewoDataExtractor(report_id)
    
    # 获取课程信息和学生互动数据
    course_info = extractor.get_course_info()
    data = extractor.extract_student_interaction()
    
    extractor.close()
    
    # 进行分析...
    return {
        "course": course_info,
        "interaction": data,
        "analysis": "..."
    }
```

### Skill 2: 学习行为分析

```python
def analyze_student_behavior(report_id: str):
    """分析学生学习行为"""
    extractor = SeewoDataExtractor(report_id)
    
    data = extractor.extract_student_behavior()
    extractor.close()
    
    # 进行分析...
    return data
```

### Skill 7: 提问有效性综合分析

```python
def analyze_question_effectiveness(report_id: str):
    """综合分析提问有效性"""
    extractor = SeewoDataExtractor(report_id)
    
    # 提取多个相关模块
    question_record = extractor.extract_question_record()
    bloom = extractor.extract_bloom_classification()
    appraisal = extractor.extract_teacher_appraisal()
    score = extractor.extract_question_score()
    
    extractor.close()
    
    # 综合分析...
    return {
        "question_record": question_record,
        "bloom": bloom,
        "appraisal": appraisal,
        "score": score,
        "analysis": "..."
    }
```

---

## 注意事项

1. **首次使用需要登录** - 调用 `extractor.login()` 会打开浏览器，需要手动扫码登录
2. **登录状态会保存** - 登录成功后会保存到 `seewo_state.json`，下次直接使用
3. **记得关闭浏览器** - 使用完毕后调用 `extractor.close()` 释放资源
4. **可以复用 extractor 实例** - 同一个实例可以调用多个提取方法
5. **异常处理** - 接口调用失败会返回空字典 `{}`，建议做空值判断

---

## 依赖安装

```bash
pip install playwright
python -m playwright install chromium
```

---

## 完整示例

查看 `example_usage.py` 文件，里面包含了7个 skill 的完整使用示例。

运行示例：
```bash
python example_usage.py
```
