# 🤖 真实LLM Agent - 使用说明

Agent已成功接入CCH的DeepSeek v4模型！

---

## 📁 文件说明

### 1. `agent_with_llm.py` - 真实LLM版本（自动测试）

使用DeepSeek v4分析课堂数据，包含3个测试用例。

**运行：**
```bash
python agent_with_llm.py
```

**特点：**
- ✅ 真实LLM调用（DeepSeek v4）
- ✅ 自动运行3个测试用例
- ✅ 展示完整的5步执行流程
- ✅ 显示真实的AI分析结果

---

### 2. `interactive_agent_llm.py` - 交互式LLM Agent

可以输入自然语言，实时获取AI分析。

**运行：**
```bash
python interactive_agent_llm.py
```

**使用：**
```
📝 请输入: 帮我分析报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动

[调用DeepSeek v4分析...]

📊 分析结果
课程: 可能性的大小-新
教师: 徐老师

💬 在课堂中，学生的平均抬头率达到72.6%，说明您营造了较好的听讲氛围...
```

---

## ⚙️ 配置

### 1. 编辑 SEEWO_CONFIG.md

```markdown
# 希沃配置

```config
cookie: x-token=xxx; x-username=yyy
api_key: sk-02be8377ffe2b265e752c7532cc8366e
```
```

需要配置：
- `cookie` - 希沃平台Cookie（用于获取数据）
- `api_key` - CCH API Key（用于调用DeepSeek）

### 2. 安装依赖

```bash
pip install openai
```

---

## 🎯 API配置

- **Endpoint**: https://token.cvte.com/v1
- **Model**: deepseek-v4-pro
- **接口**: OpenAI兼容接口

---

## 📊 测试结果示例

### 测试用例1: 学生互动分析

**输入：**
```
帮我分析报告 96f58e78b80c462cb1194fa2f6ef4e97 的学生互动情况
```

**数据：**
```
平均抬头率72.6%，平均举手率35.8%，平均参与度16.8%，小学学段
```

**DeepSeek v4分析：**
```
在课堂中，学生的平均抬头率达到72.6%，说明您营造了较好的听讲氛围，值得肯定。
在小学阶段，学生的表达欲通常较强，目前举手率与参与度有提升空间。建议可尝试
设计更多趣味性、开放性的提问，或采用"开火车""小组接龙"等游戏化互动，让更
多孩子乐于举手、有机会参与，逐步激活整体活力。
```

✅ **符合BID反馈原则** - 先肯定，再建议
✅ **字数合适** - 150字以内
✅ **专业建议** - 针对小学学段特点

---

## 🔄 Agent执行流程

```
用户输入
  ↓
Step 1: 提取report_id
  ↓
Step 2: 识别分析类型（Skill 1-7）
  ↓
Step 3: 获取课堂数据（HTTP请求，自动读取Cookie）
  ↓
Step 4: 加载System Prompt（从skills/*/SKILL.md）
  ↓
Step 5: 调用DeepSeek v4（真实LLM）
  ├─ API: https://token.cvte.com/v1
  ├─ Model: deepseek-v4-pro
  └─ System Prompt + User Data
  ↓
返回AI分析结果
```

---

## 💡 核心代码

### 初始化Agent
```python
from agent_with_llm import SeewoAgentWithLLM

# 自动从SEEWO_CONFIG.md读取API Key
agent = SeewoAgentWithLLM()

# 或手动传入API Key
agent = SeewoAgentWithLLM(api_key="sk-xxx")
```

### 分析报告
```python
result = agent.analyze("帮我分析报告 96f58e78... 的学生互动")

if result['success']:
    print(result['analysis'])  # DeepSeek v4生成的分析
```

### LLM调用
```python
def call_llm(self, system_prompt: str, user_input: str) -> str:
    from openai import OpenAI
    
    client = OpenAI(
        api_key=self.api_key,
        base_url="https://token.cvte.com/v1"
    )
    
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        temperature=0.7,
        max_tokens=300
    )
    
    return response.choices[0].message.content
```

---

## 🎓 System Prompt示例

Agent会自动从 `skills/*/SKILL.md` 加载对应的System Prompt：

**Skill 1 - 学生互动分析：**
```
你是一名教研员，拥有丰富的评课经验，且你已经具备一切评课需要的知识，
我将给你一些关于学生维度的评课数据信息，请你依据这些信息，生成对老师
的授课建议。本次分析维度是学生平均抬头率、平均举手率、平均参与度。

你的评价建议不能臆造，需要符合BID反馈原则，需要先认同，再给建议的原则，
字数要求150字以内。

请你务必整合成一段话，不能分行。
```

---

## ✅ 验证成功

- ✅ API调用成功
- ✅ DeepSeek v4返回专业分析
- ✅ 符合BID反馈原则
- ✅ 字数控制在150字以内
- ✅ 给出具体可行的教学建议

---

## 📚 文件对比

| 文件 | LLM | 用途 |
|------|-----|------|
| `simple_agent.py` | ❌ 模拟 | 演示流程 |
| `agent_with_llm.py` | ✅ DeepSeek v4 | 真实分析（测试） |
| `interactive_agent.py` | ❌ 模拟 | 交互演示 |
| `interactive_agent_llm.py` | ✅ DeepSeek v4 | 真实交互 |

**推荐使用：**
- 开发调试：`simple_agent.py`
- 真实分析：`agent_with_llm.py`
- 生产环境：`interactive_agent_llm.py`

---

## 🚀 下一步

1. ✅ 已完成 - Agent接入真实LLM
2. ✅ 已完成 - 测试所有7个Skill
3. 可选 - 添加错误重试机制
4. 可选 - 添加LLM响应缓存
5. 可选 - 支持批量分析

---

*使用CCH的DeepSeek v4-pro模型，专业、快速、准确！*
