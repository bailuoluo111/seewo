# Agent模拟示例

`agent_simulation.py` - 展示完整的Agent工作流程，包括输入、输出、Trace和工具调用

## 运行

```bash
python agent_simulation.py
```

## 输出内容

### 1. 用户输入
```
📝 User Input: 帮我分析一下报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况
```

### 2. 执行步骤（Trace）

每个步骤都会显示：
- Step编号和名称
- 工具调用（Tool Call）
- 输入参数
- 输出结果

```
📍 STEP 1: 提取 report_id
[Tool Call] extract_report_id
  Input: 帮我分析一下报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况
  Output: 96f58e78b80c462cb1194fa2f6ef4e97

📍 STEP 2: 识别分析类型
[Tool Call] identify_skill_type
  Output: Skill 1 - 学生互动分析

📍 STEP 3: 获取Skill数据
[Tool Call] get_skill_input
  Output:
    - course_info: 可能性的大小-新
    - input_text: 平均抬头率72.6%，平均举手率35.8%，平均参与度16.8%，小学学段

📍 STEP 4: 加载System Prompt
[Tool Call] load_system_prompt
  Output: System Prompt加载成功 (381 字符)

📍 STEP 5: 调用LLM生成分析
[Tool Call] call_llm
  System Prompt: 你是一名教研员...
  User Input: 平均抬头率72.6%...
  Output: 从课堂互动数据来看...
```

### 3. Trace摘要

```
📊 TRACE SUMMARY

总步骤数: 5
工具调用次数: 5

执行流程:
  Step 1: extract_report_id
  Step 2: identify_skill_type
  Step 3: get_skill_input
  Step 4: load_system_prompt
  Step 5: call_llm
```

### 4. 最终输出（JSON）

```json
{
  "report_id": "96f58e78b80c462cb1194fa2f6ef4e97",
  "skill_number": 1,
  "skill_name": "学生互动分析",
  "course_info": {
    "课程名称": "可能性的大小-新",
    "教师姓名": "徐老师",
    "学段": "小学"
  },
  "input_data": "平均抬头率72.6%，平均举手率35.8%，平均参与度16.8%，小学学段",
  "analysis": "从课堂互动数据来看，学生的平均抬头率达到72.6%..."
}
```

## 测试用例

脚本包含3个测试用例：

1. **学生互动分析** - 识别关键词"学生互动"
2. **提问有效性分析** - 识别关键词"提问质量"
3. **综合分析** - 未指定类型，使用默认Skill

## 工具调用

Agent使用的5个工具：

1. `extract_report_id()` - 从输入提取report_id
2. `identify_skill_type()` - 识别分析类型
3. `get_skill_input()` - 获取Skill数据（调用skill_helpers.py）
4. `load_system_prompt()` - 从SKILL.md加载提示词
5. `call_llm()` - 调用LLM生成分析（模拟）

## 核心流程

```
用户输入
  ↓
[Tool 1] 提取report_id
  ↓
[Tool 2] 识别分析类型（Skill 1-7）
  ↓
[Tool 3] 获取Skill数据（input_text + raw_data）
  ↓
[Tool 4] 加载System Prompt
  ↓
[Tool 5] 调用LLM
  ↓
返回结果（JSON）
```

## Trace数据结构

完整的trace包含：
- timestamp: 时间戳
- user_input: 用户输入
- steps: 执行步骤列表
- tool_calls: 工具调用列表
- result: 最终结果
- error: 错误信息（如果有）

可用于：
- 调试
- 监控
- 日志记录
- 性能分析
