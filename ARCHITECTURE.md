# 希沃课堂观察 Skill 与 Agent 技术路线

本文档只记录当前仓库**已经实现**的内容：`skills/`、`agent.py`、`api.py`、配置与 trace。

---

## 1. 总体结构

```text
agent.py / api.py
        ↓
SeewoAgent（ReAct 调度）
        ↓
7 个 Skill Tool
        ↓
skills/<skill>/scripts/*.py
        ↓
希沃课堂观察原始接口
```

当前实现目标：

- Skill 自包含，可独立装配
- Agent 负责路由、工具调用和结果整合
- API 返回结果、指标和 trace，便于外部平台调用

---

## 2. Skill 设计

### 2.1 已实现的 Skill

当前共实现 7 个 Skill：

| 目录 | 能力 |
| --- | --- |
| `student_interaction` | 学生互动分析 |
| `student_behavior` | 学习行为分析 |
| `solo_classification` | SOLO 分类分析 |
| `answer_time` | 应答时间分析 |
| `teacher_speech` | 讲授分析 |
| `course_reengineering` | 课堂流程重构 |
| `question_effectiveness` | 提问有效性分析 |

### 2.2 Skill 目录结构

```text
skills/<skill_name>/
├── SKILL.md
└── scripts/
    ├── seewo_client.py
    ├── extract.py
    └── extract_all.py
```

说明：

- `SKILL.md`：保存 Skill 元信息、分析指引和示例
- `seewo_client.py`：当前 Skill 自带的数据访问客户端
- `extract.py`：当前维度提取逻辑
- `extract_all.py`：跨维度全量提取

### 2.3 Skill 契约

每个 Skill 的 `extract.py` 对外暴露统一接口：

```python
def extract(report_id, token=None, username=None) -> dict:
    ...

def build_input(report_id, token=None, username=None) -> str:
    ...
```

当前实现中：

- `extract()` 返回结构化维度数据
- `build_input()` 返回可直接喂给 LLM 的中文输入
- Agent 主要使用 `build_input()`

### 2.4 当前实现特点

- 每个 Skill 目录自包含，复制目录即可迁移
- `seewo_client.py` 在各 Skill 中保留副本，避免跨目录依赖
- Skill 负责取数和维度分析指引，不直接负责最终整合输出

---

## 3. Agent 设计

### 3.1 当前实现职责

`SeewoAgent` 负责：

- 接收用户自然语言输入
- 从输入中提取 `report_id`
- 决定调用哪个或哪些 Skill
- 执行工具并回填结果
- 生成最终分析结果

### 3.2 ReAct 流程

```text
用户输入
  ↓
LLM 判断是否调用工具
  ↓
执行 Skill Tool
  ↓
工具结果回填 messages
  ↓
LLM 继续决策
  ↓
无工具调用时输出最终答案
```

### 3.3 Skill 注册方式

Agent 将 7 个 Skill 注册为 LLM Tools，核心包括：

- `TOOLS`：工具定义
- `TOOL_SKILL_MAP`：工具名到 Skill 的映射
- `_execute_tool()`：实际执行 Skill

### 3.4 动态加载

Agent 运行时通过 `importlib` 动态加载 Skill 脚本，不直接写死业务导入：

```python
scripts_dir = SKILLS_DIR / skill_dir / "scripts"
spec = importlib.util.spec_from_file_location(...)
```

这样 Agent 只负责调度，Skill 逻辑留在各自目录中。

### 3.5 当前鲁棒性处理

当前 `agent.py` 已实现：

- `MAX_TURNS` 防止死循环
- 空回答保护，避免模型无输出却被当成成功
- 最终总结阶段增加一次兜底重试
- 记录 `finish_reason`、内容长度等元数据

---

## 4. API 与可观测性

### 4.1 API

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

### 4.2 Trace

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

当前 trace 主要用于记录：

- 调用了哪些 Skill
- 每轮 LLM 调用和工具调用情况
- 耗时、Token 和错误状态

---

## 5. 配置与文件

### 5.1 配置

`SEEWO_CONFIG.md` 当前保存：

- 希沃接口凭证
- `api_key`
- `api_base`
- `model`

当前模型通过配置读取，已支持切换到阿里云百炼 OpenAI 兼容接口。

### 5.2 关键文件

| 文件 | 职责 |
| --- | --- |
| `agent.py` | ReAct Agent 主体 |
| `api.py` | HTTP API 封装 |
| `skills/` | 7 个 Skill 的实现 |
| `SEEWO_CONFIG.md` | 运行配置 |
| `view_traces.py` | trace 查看工具 |

---

## 6. 总结

当前已实现的核心能力只有三块：

1. **7 个自包含 Skill**
2. **一个基于 ReAct 的 Agent**
3. **一个可返回 trace 的 HTTP API**

整体上，Skill 负责取数和维度指引，Agent 负责路由和整合输出，API 负责对外提供统一调用入口。
