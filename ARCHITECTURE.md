# 希沃课堂观察 Skill 与 Agent 技术路线

本文档只记录当前仓库**已实现**的 MCP 版本架构。

---

## 1. 总体结构

```text
agent.py / api.py
        ↓
SeewoAgent（ReAct 调度）
        ↓
SeewoMCPClient
        ↓
mcp/server.py
        ↓
mcp/tools.py
        ↓
希沃课堂观察原始接口
```

当前实现目标：

- Skill 只保留分析指引，不承载运行时取数入口
- 工具统一收口到本地 MCP 服务
- Agent 负责路由、工具调用和结果整合
- API 返回结果、指标和 trace，便于外部平台调用

---

## 2. Skill 设计

当前共保留 7 个 Skill：

| 目录 | 能力 |
| --- | --- |
| `student_interaction` | 学生互动分析 |
| `student_behavior` | 学习行为分析 |
| `solo_classification` | SOLO 分类分析 |
| `answer_time` | 应答时间分析 |
| `teacher_speech` | 讲授分析 |
| `course_reengineering` | 课堂流程重构 |
| `question_effectiveness` | 提问有效性分析 |

当前运行形态下，`skills/` 目录主要用于保存 `SKILL.md`：

- 保存 Skill 元信息
- 保存该维度的分析指引
- 作为 Agent 在工具结果返回后补充给模型的提示材料

---

## 3. MCP 工具层

本地 MCP 服务统一暴露 8 个工具：

- 7 个单维度工具：
  - `analyze_student_interaction`
  - `analyze_student_behavior`
  - `analyze_solo_classification`
  - `analyze_answer_time`
  - `analyze_teacher_speech`
  - `analyze_course_reengineering`
  - `analyze_question_effectiveness`
- 1 个全量工具：
  - `get_all_classroom_context`

实现位置：

- `mcp/tools.py`：工具定义、统一取数逻辑、希沃数据客户端
- `mcp/server.py`：本地 stdio MCP 服务
- `mcp/client.py`：Agent 侧 MCP 桥接客户端

设计原则：

- 默认优先使用当前维度工具
- 当前维度证据不足时，再使用全量工具补充上下文
- 即使使用全量工具，也保持当前问题主线，不把所有维度逐个展开

---

## 4. Agent 设计

`SeewoAgent` 负责：

- 接收用户自然语言输入
- 从输入中提取 `report_id`
- 从本地 MCP 服务发现工具
- 调用 MCP 工具并回填结果
- 读取 `SKILL.md` 分析指引
- 生成最终分析结果

ReAct 流程：

```text
用户输入
  ↓
LLM 判断是否调用工具
  ↓
Agent 转发到 MCP 服务
  ↓
MCP 返回结构化数据
  ↓
工具结果回填 messages
  ↓
LLM 继续决策
  ↓
无工具调用时输出最终答案
```

当前 `agent.py` 已实现：

- `MAX_TURNS` 防止死循环
- 空回答保护，避免模型无输出却被当成成功
- 最终总结阶段增加一次兜底重试
- 记录 `finish_reason`、内容长度等元数据

---

## 5. API 与可观测性

`api.py` 将 Agent 封装为 HTTP 服务，当前主要接口是：

- `POST /analyze`

响应返回：

```json
{
  "success": true,
  "answer": "...",
  "course_info": {},
  "metrics": {},
  "trace": [],
  "trace_id": "0x..."
}
```

当前使用 OpenTelemetry 记录执行链路，核心 span 包括：

```text
seewo.api.analyze
└── seewo.agent.run
    ├── seewo.agent.loop.turn
    │   ├── seewo.llm.call
    │   └── seewo.tool.execute
    │       ├── seewo.skill.fetch_data
    │       └── seewo.skill.load_prompt
```

---

## 6. 关键文件

| 文件 | 职责 |
| --- | --- |
| `agent.py` | ReAct Agent 主体，负责 MCP 工具桥接 |
| `api.py` | HTTP API 封装 |
| `mcp/tools.py` | 8 个课堂观察工具与统一取数逻辑 |
| `mcp/server.py` | 本地 stdio MCP 服务 |
| `mcp/client.py` | Agent 到 MCP 的桥接客户端 |
| `skills/` | 7 个 Skill 的分析指引 |
| `SEEWO_CONFIG.md` | 运行配置 |
| `view_traces.py` | trace 查看工具 |

---

## 7. 总结

当前实现可以概括为三层：

1. **Skill 负责分析指引**
2. **MCP 服务负责统一提供工具**
3. **Agent 负责路由、调用和整合输出**

这样工具能力从 Skill 脚本中抽离出来，统一收口到 MCP 服务，Agent 只保留调度职责。
