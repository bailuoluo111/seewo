# 🤖 简单Agent示例

两个简单的Agent示例，展示如何使用希沃数据提取器和Skill辅助函数。

---

## 📁 文件说明

### 1. `simple_agent.py` - 自动化测试Agent

包含完整的Agent类和3个测试用例。

**运行：**
```bash
python simple_agent.py
```

**功能：**
- 自动运行3个测试用例
- 展示完整的执行步骤（5步）
- 显示详细的分析结果

**核心流程：**
```
Step 1: 提取report_id
Step 2: 识别分析类型（Skill 1-7）
Step 3: 获取课堂数据
Step 4: 加载System Prompt
Step 5: 调用LLM分析（模拟）
```

---

### 2. `interactive_agent.py` - 交互式Agent

可以输入自然语言进行实时对话。

**运行：**
```bash
python interactive_agent.py
```

**使用：**
```
📝 请输入: 帮我分析一下报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况

[执行分析...]

📊 分析结果
从课堂互动数据来看，学生的平均抬头率表现良好...

📝 请输入: 
```

**退出：**
输入 `quit` 或 `exit` 或按 `Ctrl+C`

---

## 🎯 支持的分析类型

| 编号 | 分析类型 | 关键词 |
|------|----------|--------|
| 1 | 学生互动分析 | 互动、抬头率、举手率、参与 |
| 2 | 学习行为分析 | 学习行为、学习金字塔、知识留存 |
| 3 | SOLO分类分析 | SOLO、回答质量、建构 |
| 4 | 应答时间分析 | 应答时间、回答时长、思考 |
| 5 | 讲授分析 | 讲授、语速、讲话 |
| 6 | 课堂流程重构 | 课堂流程、课前、课后 |
| 7 | 提问有效性分析 | 提问、布鲁姆、理答、问题 |

---

## 📝 输入示例

```
✅ 帮我分析一下报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况
✅ 看看这个课 96f58e78b80c462cb1194fa2f6ef4e97 的提问质量怎么样
✅ 分析报告 96f58e78b80c462cb1194fa2f6ef4e97 的学习行为
✅ 96f58e78b80c462cb1194fa2f6ef4e97 这节课的应答时间怎么样
```

只需包含32位的report_id即可，其他都是自然语言。

---

## 🔧 核心代码

### Agent类
```python
from skill_helpers import get_skill_input

class SeewoAgent:
    def analyze(self, user_input: str):
        # 1. 提取report_id
        report_id = self.extract_report_id(user_input)
        
        # 2. 识别分析类型
        skill_number = self.identify_skill(user_input)
        
        # 3. 获取数据（自动从SEEWO_CONFIG.md读取Cookie）
        skill_data = get_skill_input(report_id, skill_number)
        
        # 4. 加载System Prompt
        system_prompt = self.load_system_prompt(skill_number)
        
        # 5. 调用LLM
        result = call_llm(system_prompt, skill_data['input_text'])
        
        return result
```

---

## 🚀 接入真实LLM

将 `simple_agent.py` 中的 `mock_llm_response()` 替换为真实的LLM调用：

### OpenAI示例
```python
def call_openai_llm(self, system_prompt: str, user_input: str) -> str:
    import openai
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        temperature=0.7,
        max_tokens=200
    )
    
    return response.choices[0].message.content
```

### Claude示例
```python
def call_claude_llm(self, system_prompt: str, user_input: str) -> str:
    import anthropic
    
    client = anthropic.Anthropic(api_key="your-api-key")
    
    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=200,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_input}
        ]
    )
    
    return response.content[0].text
```

---

## 📊 输出格式

返回字典包含：
```python
{
    "success": True,
    "report_id": "96f58e78b80c462cb1194fa2f6ef4e97",
    "skill_number": 1,
    "skill_name": "学生互动分析",
    "course_info": {
        "课程名称": "可能性的大小-新",
        "教师姓名": "徐老师",
        "学校名称": "上海市民办丽英小学",
        "学段": "小学"
    },
    "input_data": "平均抬头率72.6%...",
    "analysis": "从课堂互动数据来看..."
}
```

---

## ⚙️ 依赖

确保以下文件在同一目录：
- `SEEWO_CONFIG.md` - Cookie配置
- `seewo_http_data_extractor.py` - 数据提取器
- `skill_helpers.py` - Skill辅助函数
- `skills/` - Skill文档目录

---

## 🎯 特点

1. ✅ **自动配置** - 从SEEWO_CONFIG.md自动读取Cookie
2. ✅ **智能识别** - 根据关键词自动识别分析类型
3. ✅ **自然语言** - 支持各种自然语言输入
4. ✅ **完整流程** - 展示从输入到输出的每一步
5. ✅ **易于扩展** - 只需替换LLM调用函数即可接入真实API

---

## 📚 相关文档

- `agent_simulation.py` - 完整的Trace模拟（包含详细的工具调用记录）
- `AGENT_SIMULATION.md` - Trace模拟说明文档
