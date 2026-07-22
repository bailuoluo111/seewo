# Seewo MCP

本目录提供一个本地 `stdio` MCP 服务，统一暴露希沃课堂观察相关工具。

## 作用

- 把 7 个单维度取数工具和 1 个全量上下文工具收口到一个 MCP 服务
- 让 `agent.py` 不再直接依赖 `skills/*/scripts/*.py`
- 保留 `skills/*/SKILL.md` 作为分析指引来源

## 当前工具

- `analyze_student_interaction`
- `analyze_student_behavior`
- `analyze_solo_classification`
- `analyze_answer_time`
- `analyze_teacher_speech`
- `analyze_course_reengineering`
- `analyze_question_effectiveness`
- `get_all_classroom_context`

## 文件说明

- `tools.py`: 工具定义、统一取数逻辑、希沃数据客户端
- `server.py`: 本地 stdio MCP 服务
- `client.py`: Agent 侧的 MCP 桥接客户端

## 调用链

```text
agent.py
   ↓
SeewoMCPClient
   ↓
mcp/server.py
   ↓
mcp/tools.py
   ↓
希沃课堂观察原始接口
```

## 使用原则

- 默认优先使用单维度工具
- 只有在当前维度证据不足、需要交叉验证或补充解释时，再使用 `get_all_classroom_context`
- 即使使用全量工具，也应保持当前分析主题，不把所有维度逐个展开
