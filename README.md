# 希沃课堂观察数据提取器

高性能HTTP数据提取器，用于提取希沃课堂观察系统的课堂分析数据。

## 📁 文件说明

```
.
├── README.md                                    # 本文档
├── seewo_http_data_extractor.py                # 数据提取器（核心）
├── quick_test.py                                # 快速测试脚本
├── 课堂观察七维度Prompt与Handler合并文档.md   # 业务文档
│
└── skills/                                      # 7个分析Skill
    ├── README.md                                # Skills总览
    ├── student_interaction/SKILL.md             # Skill 1: 学生互动
    ├── student_behavior/SKILL.md                # Skill 2: 学习行为
    ├── solo_classification/SKILL.md             # Skill 3: SOLO分类
    ├── answer_time/SKILL.md                     # Skill 4: 应答时间
    ├── teacher_speech/SKILL.md                  # Skill 5: 讲授分析
    ├── course_reengineering/SKILL.md            # Skill 6: 课堂流程重构
    └── question_effectiveness/SKILL.md          # Skill 7: 提问有效性
```

---

## 🚀 快速开始

### 1. 获取Token

从浏览器Cookie中获取：

1. 打开希沃课堂观察报告页面
2. 按 **F12** → **Network** 标签
3. 刷新页面，查看任意请求的 Cookie
4. 复制 `x-token` 和 `x-username` 的值

示例：
```
x-token=e953f17a521f49209c052796c055d4ea-0992
x-username=13429851339
```

### 2. 测试提取器

```bash
# 运行测试脚本，查看所有方法效果
python quick_test.py
```

### 3. 使用提取器

```python
from seewo_http_data_extractor import SeewoHttpDataExtractor

# 创建提取器
extractor = SeewoHttpDataExtractor(
    report_id="96f58e78b80c462cb1194fa2f6ef4e97",
    token="your-token",
    username="your-username"
)

# 测试连接
if extractor.test_connection():
    # Skill 1: 学生互动
    data = extractor.extract_student_interaction()
    print(data)
    # {'平均抬头率': 72.6, '平均举手率': 35.8, '平均参与度': 16.8}
```

---

## 📊 数据提取方法

### 基础方法
- `test_connection()` - 测试Token有效性
- `get_course_info()` - 获取课程信息

### 学生维度（Skill 1-4）
1. `extract_student_interaction()` - 学生互动（抬头率、举手率、参与度）
2. `extract_student_behavior()` - 学习行为（学习金字塔、知识留存率）
3. `extract_solo_classification()` - SOLO分类（回答建构水平）
4. `extract_answer_time()` - 应答时间（回答时长分布）

### 教师维度（Skill 5-6）
5. `extract_speech_data()` - 讲授分析（语速、字数、时长）
6. `extract_course_reengineering()` - 课堂流程重构

### 提问有效性（Skill 7）
7. `extract_question_record()` - 提问记录
8. `extract_bloom_classification()` - 布鲁姆分类
9. `extract_teacher_appraisal()` - 教师理答分类
10. `extract_question_answer_extra()` - 问答统计
11. `extract_question_score()` - 提问有效性得分

### 工具方法
- `extract_all_modules()` - 一次性提取所有模块

---

## 💡 使用示例

### 示例1: 提取单个模块

```python
extractor = SeewoHttpDataExtractor(...)

# Skill 1: 学生互动
interaction = extractor.extract_student_interaction()
print(f"平均抬头率: {interaction['平均抬头率']}%")
```

### 示例2: 提取所有模块

```python
# 一次性提取所有数据
all_data = extractor.extract_all_modules()

# 访问各模块
interaction = all_data['modules']['学生互动数据']
behavior = all_data['modules']['学习行为分布']
```

### 示例3: 批量处理

```python
report_ids = ["report1", "report2", "report3"]

for report_id in report_ids:
    extractor = SeewoHttpDataExtractor(
        report_id=report_id,
        token=token,
        username=username
    )
    if extractor.test_connection():
        data = extractor.extract_all_modules()
        # 处理数据...
```

---

## 📖 详细文档

- **`skills/README.md`** - 7个Skill的详细说明
- **`skills/*/SKILL.md`** - 每个Skill的完整文档
- **`课堂观察七维度Prompt与Handler合并文档.md`** - 业务需求文档

---

## ⚡ 性能

- **速度**: ~3秒提取所有11个模块
- **内存**: ~50MB
- **依赖**: 只需 `requests` 库

---

## 🎯 7个Skill与提取方法对应

| Skill | 提取方法 |
|-------|---------|
| 1. 学生互动 | `extract_student_interaction()` |
| 2. 学习行为 | `extract_student_behavior()` |
| 3. SOLO分类 | `extract_solo_classification()` |
| 4. 应答时间 | `extract_answer_time()` |
| 5. 讲授分析 | `extract_speech_data()` |
| 6. 课堂流程重构 | `extract_course_reengineering()` |
| 7. 提问有效性 | `extract_question_score()` + 其他4个方法 |

详见 `skills/` 目录中的文档。

---

*最后更新: 2026-07-20*
