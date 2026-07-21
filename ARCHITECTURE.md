
# 希沃课堂分析系统 — 技术架构文档

本文档记录 **Skill 设计**与 **Agent 设计**的详细技术路线。

---

## 0. 全局架构

```
┌─────────────────────────────────────────────────────────────┐
│  入口层                                                        │
│    agent.py (命令行 ReAct Agent)   api.py (HTTP API)          │
└───────────────┬─────────────────────────┬───────────────────┘
                │                         │
                ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Agent 层（ReAct 循环 + 工具调度 + OpenTelemetry 埋点）        │
│    SeewoAgent.run()  →  LLM 决策  →  工具执行  →  喂回结果      │
└───────────────┬─────────────────────────────────────────────┘
                │ 动态加载 importlib
                ▼
┌─────────────────────────────────────────────────────────────┐
│  Skill 层（7 个自包含维度，各自独立可装配）                     │
│    skills/<skill>/                                            │
│      ├── SKILL.md              # System Prompt + 分析指引       │
│      └── scripts/                                            │
│          ├── seewo_client.py   # 自包含 HTTP 客户端            │
│          ├── extract.py        # 本维度提取 + build_input      │
│          └── extract_all.py    # 一次性取全部维度（可选）       │
└───────────────┬─────────────────────────────────────────────┘
                │ HTTP
                ▼
        希沃 edulyse API（课堂观察原始数据）
```

设计目标：**Skill 高内聚、可独立装配；Agent 只做调度、不含业务逻辑；全链路可观测。**

---

## 1. Skill 设计

### 1.1 设计动机

早期所有维度的提取逻辑集中在一个巨型 `seewo_http_data_extractor.py` + `skill_helpers.py` 里，7 个 skill 全部 `from seewo_http_data_extractor import ...`，无法把单个 skill 装配到别的 Agent。

**解耦目标**：每个 skill 成为一个自包含目录，复制该目录即可在任意 Agent 中独立运行，不依赖项目里其他任何文件。

### 1.2 目录结构

```
skills/<skill_name>/
├── SKILL.md                 # 元信息 + System Prompt + 数据维度说明 + 代码示例
└── scripts/
    ├── seewo_client.py      # 最小 HTTP 客户端（每个 skill 一份相同副本）
    ├── extract.py           # 本维度专属提取逻辑
    └── extract_all.py       # 一次性提取全部 7 维度（跨维度分析用，可选）
```

**关键取舍**：`seewo_client.py` 在 7 个目录里各存一份完全相同的副本。这是为「单目录即可独立装配」付出的代价——牺牲少量重复，换取零跨目录依赖。

### 1.3 七个维度

| # | Skill 目录                 | 中文名         | 数据来源接口                                                              | 核心指标                           |
| - | -------------------------- | -------------- | ------------------------------------------------------------------------- | ---------------------------------- |
| 1 | `student_interaction`    | 学生互动分析   | `studentStudyStatistic`                                                 | 抬头率、举手率、参与度             |
| 2 | `student_behavior`       | 学习行为分析   | `studentStudyBehavior`                                                  | 学习金字塔7类行为占比、知识留存率  |
| 3 | `solo_classification`    | SOLO分类分析   | `solo`                                                                  | 前结构/单点/多点/关联/抽象拓展五级 |
| 4 | `answer_time`            | 应答时间分析   | `studentAnswerClassification`                                           | ≤5s/5-15s/>15s 时长分布           |
| 5 | `teacher_speech`         | 讲授分析       | `speechData`                                                            | 字数、时长、语速                   |
| 6 | `course_reengineering`   | 课堂流程重构   | `courseProcessReengineering`                                            | 课前→课中、课中→课后链接等级     |
| 7 | `question_effectiveness` | 提问有效性分析 | `bloom` + `teacherAppraisalClassification` + `questionScoreExplain` | 布鲁姆六级、理答类型、有效性得分   |

### 1.4 seewo_client.py — 自包含 HTTP 客户端

只提供三件事：加载凭证、发 API 请求、取课程信息。

**凭证解析优先级**（先到先得，保证在任何环境都能取到）：

1. 构造函数参数 `token` / `username`
2. 环境变量 `SEEWO_TOKEN` / `SEEWO_USERNAME`
3. `SEEWO_CONFIG.md`（在当前目录及各级父目录中向上查找）

这个设计让 skill 既能被主项目用（读 SEEWO_CONFIG.md），也能被别的 Agent 用（传参或环境变量），互不绑定。

### 1.5 extract.py — 维度提取契约

每个 skill 的 `extract.py` 对外暴露统一的两个函数：

```python
def extract(report_id, token=None, username=None) -> dict:
    """返回结构化的原始维度数据（各指标数值）"""

def build_input(report_id, token=None, username=None) -> str:
    """返回拼好的、可直接喂给 LLM 的中文输入文本"""
```

- `extract()` 给程序用（如批量导出、二次计算）
- `build_input()` 给 LLM 用（Agent 直接拿它作为工具返回的数据）

**枚举映射经过前端真实数据逐项校验**。例如学习行为的 `behaviorType`：`0听讲/1阅读/2视听/3演示/4讨论/5实践/6教给他人`（金字塔顺序），修正了早期"3=讨论/4=实践"的错误映射；SOLO、布鲁姆、理答类型的枚举同样与前端页面数字对齐。

### 1.6 extract_all.py — 跨维度提取

自包含脚本（只依赖同目录 `seewo_client.py`），一次性提取全部 7 维度，按模块组织返回：

```python
{
  "course_info": {...},
  "student_interaction": {...},
  "student_behavior": {...},
  ...
  "question_effectiveness": {...},
}
```

用途：某个 skill 分析时若需参考其他维度数据（如"综合各维度看整体"），可调此函数拿全量。每个 skill 目录都有一份相同副本，保持独立性。

---

## 2. Agent 设计

### 2.1 从线性流水线到 ReAct

|                | 旧版（线性流水线）       | 新版（ReAct Loop）                |
| -------------- | ------------------------ | --------------------------------- |
| report_id 获取 | 正则硬匹配，格式错就报错 | LLM 从自然语言/URL 自行提取       |
| skill 选择     | 关键词匹配，易误判       | LLM 按语义自主决定                |
| 多维度分析     | 不支持                   | 同一对话可调多个工具              |
| 控制流         | `analyze()` 单次调用   | `run()` 循环直到 LLM 停止调工具 |

### 2.2 ReAct 循环（`SeewoAgent.run()`）

```
用户自然语言输入
   ↓
┌──────────────────────────────────────────┐
│ LLM 决策（带工具定义）                       │
│   - 从输入提取 report_id                    │
│   - 判断该调哪个/哪些工具                     │
└──────────┬───────────────────────────────┘
           │ 有工具调用？
      ┌────┴────┐
     是         否
      │          └──→ 生成最终回答，退出循环 ✓
      ▼
   执行工具（抓希沃数据）→ 结果追加进 messages → 回到 LLM 决策
```

- 最多 `MAX_TURNS=10` 轮，防止无限循环
- 退出条件：LLM 本轮不再返回 `tool_calls`（即数据够了，直接作答）

### 2.3 Skill = Tool 的双视角

7 个 skill 一一对应 7 个 LLM 工具。三层结构：

1. **工具声明**（`TOOLS`，JSON Schema）：给 LLM 看的能力清单，每个工具的 `description` 让 LLM 判断何时调用，参数统一为 `report_id`
2. **工具名 → skill 映射**（`TOOL_SKILL_MAP`）：执行时据此定位 skill 目录
3. **工具执行**（`_execute_tool`）：动态加载 skill 脚本 → 抓数据 → 读 SKILL.md 指引 → 打包 JSON 返回

**工具本身不做分析**，只负责「抓数据 + 给分析指引」，真正生成分析文字的是主 LLM。这样多维度分析时 LLM 能把多份数据综合起来。

### 2.4 动态加载机制

Agent 本身**不含任何希沃 API 逻辑**。运行时用 `importlib.util.spec_from_file_location` 动态加载 `skills/<skill>/scripts/extract.py` 和 `seewo_client.py`：

```python
scripts_dir = SKILLS_DIR / skill_dir / "scripts"
sys.path.insert(0, scripts_dir)          # 让 extract.py 内部的 import seewo_client 生效
spec = importlib.util.spec_from_file_location(f"extract_{n}", ".../extract.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.build_input(report_id, token, username)
```

配合 `sys.dont_write_bytecode = True`，动态加载不会在 skill 目录生成 `__pycache__`。

### 2.5 LLM 配置

- 模型：`deepseek-v4-pro`（走 CVTE OpenAI 兼容接口 `https://token.cvte.com/v1`）
- `tool_choice="auto"`：由 LLM 自主决定是否调工具
- 系统提示（`AGENT_SYSTEM_PROMPT`）约定：report_id 提取规则、多工具调用策略、BID 反馈原则、150字以内

---

## 3. 可观测性（OpenTelemetry）

### 3.1 Span 层级

一次请求被拆成带层级的 span 树：

```
seewo.agent.run                    ← 整条链路（总耗时/轮次/工具数）
├── seewo.agent.loop.turn          ← ReAct 每一轮
│   ├── seewo.llm.call             ← 每次 LLM 调用（模型/token/工具数）
│   └── seewo.tool.execute         ← 每次工具执行（工具名/report_id）
│       ├── seewo.skill.fetch_data ← 抓希沃数据（skill/课程/教师）
│       └── seewo.skill.load_prompt← 读 SKILL.md（prompt 长度）
└── seewo.agent.loop.turn
    └── seewo.llm.call             ← 无工具调用 → 退出
```

每个 span 带 `attributes`（token 消耗、工具名、课程名等）和 `status`（OK/ERROR），能定位性能瓶颈、成本、失败点。

### 3.2 输出方式（环境变量控制）

| 方式           | 触发                                  | 用途                               |
| -------------- | ------------------------------------- | ---------------------------------- |
| 写文件（默认） | 无                                    | 写`seewo_traces.jsonl`，终端干净 |
| stderr         | `SEEWO_TRACE_CONSOLE=1`             | 本地调试                           |
| 自定义文件     | `SEEWO_TRACE_FILE=<path>`           | 指定路径                           |
| OTLP 后端      | `OTEL_EXPORTER_OTLP_ENDPOINT=<url>` | 发 Jaeger/Grafana Tempo            |

### 3.3 紧凑格式 + 查看器

- `CompactSpanExporter`：每个 span 压成**一行** JSON，去掉 `resource`/`kind`/`events` 等重复噪音（一次请求从 ~280 行降到 ~8 行）
- `view_traces.py`：独立命令行工具，把 `seewo_traces.jsonl` 渲染成带耗时条形图的调用树（`python view_traces.py [-n N | --all]`）

---

## 4. 文件职责与部署

### 4.1 文件清单

| 文件                | 职责                                               |
| ------------------- | -------------------------------------------------- |
| `agent.py`        | 核心 ReAct Agent + 命令行入口 + OTel 埋点          |
| `api.py`          | FastAPI 封装，供测评平台调用                       |
| `test_api.py`     | HTTP 调用测试脚本，格式化展示 answer/metrics/trace |
| `view_traces.py`  | trace 文件查看器（独立工具，无代码依赖）           |
| `SEEWO_CONFIG.md` | 凭证配置（token / api_key）                        |
| `skills/`         | 7 个自包含维度                                     |
| `batch_analysis/` | 批量提取工具（含旧版共享 extractor）               |

### 4.2 两种入口

**命令行（交互式）：**

```bash
python agent.py
```

**HTTP API（供测评平台）：**

```bash
python api.py          # 0.0.0.0:8008
```

### 4.3 API 设计（`/analyze`）

响应同时返回**输出**和**本次请求 trace**，供平台评估：

```json
{
  "success": true,
  "answer": "...",           // 自然语言输出
  "course_info": {...},      // 分析的哪节课
  "metrics": {               // 从 trace 提炼的指标
    "total_duration_ms", "turns", "tool_calls",
    "llm_calls", "tokens", "tools_used", "has_error"
  },
  "trace": [ {span}, ... ]   // 完整调用链
}
```

**trace 按请求隔离**：给 Agent 的 TracerProvider 挂一个 `InMemoryTraceCollector`，每个请求用 `api.analyze` 根 span 包住 `agent.run()`，请求结束后按 `trace_id` 精确取出该请求的 span 并清理内存——并发调用互不串扰。

### 4.4 依赖

```bash
pip install requests openai pandas openpyxl \
            opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc \
            fastapi "uvicorn[standard]"
```

| 依赖                                       | 用途                       |
| ------------------------------------------ | -------------------------- |
| `requests`                               | 调希沃 HTTP 接口           |
| `openai`                                 | 调 DeepSeek（OpenAI 兼容） |
| `pandas` + `openpyxl`                  | 批量导出读写 Excel         |
| `opentelemetry-sdk`                      | trace 埋点（硬依赖）       |
| `opentelemetry-exporter-otlp-proto-grpc` | 发 OTLP 后端（可选）       |
| `fastapi` + `uvicorn`                  | HTTP API 服务              |

---

## 5. 设计要点总结

1. **Skill 自包含**：每个 skill 目录独立可装配，零跨目录依赖（代价：`seewo_client.py` 多份副本）
2. **Agent 只调度**：不含业务逻辑，运行时动态加载 skill 脚本
3. **工具只取数、LLM 做分析**：工具返回「数据+指引」，主 LLM 综合生成分析
4. **ReAct 自主决策**：report_id 提取、skill 选择、多维度组合全由 LLM 判断
5. **全链路可观测**：OTel 埋点覆盖每一步，trace 可写文件/终端/OTLP，API 响应内联 trace 供评估
