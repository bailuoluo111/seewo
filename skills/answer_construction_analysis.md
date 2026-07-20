# Skill：回答建构分类分析

## 基本信息

| 字段 | 值 |
|------|-----|
| skill_id | answer_construction_analysis |
| version | 1.0.0 |
| dimension | 回答建构分类 |
| applicable_scenarios | 基于 SOLO 分类理论分析学生回答的认知建构层次分布，评估课堂问题设计的认知挑战水平；在发现高阶回答比例偏低或无响应比例偏高时，按需引用候答时间或互动数据进行交叉验证与归因，形成有依据的提问质量与学生思维深度分析报告 |

**Description**

分析学生回答建构分类数据（前结构 / 单点结构 / 多点结构 / 关联结构 / 抽象拓展结构），结合问答模式分布（常规问答 / 追问 / 思考再答 / 无响应）和教师理答类型（简单肯定 / 针对肯定 / 激励 / 否定），评估课堂提问对高阶思维的激发程度；在发现认知层次偏低或无响应异常时，按需引用候答时间数据或学生互动数据进行佐证归因，输出提问质量与思维深度的多维度分析报告。

---

## 分析目标

1. 评估学生回答的 SOLO 认知层次分布（低阶 vs 高阶比例）
2. 分析问答模式结构（追问比例、无响应比例、思考再答占比）
3. 评估教师理答方式的多样性与质量（是否有针对性反馈、激励追问）
4. 识别提问难度设置与学生认知能力之间的匹配度问题
5. 结合关联维度判断高阶思维激发不足的深层原因（候答时间不足 / 参与面过窄 / 问题设计单一）
6. 提出提升提问质量和理答水平的具体建议

---

## 可调用数据工具

### 主数据（必须调用）

**get_answer_construction_data**
- 功能：获取当前课程的回答建构分类及提问相关数据
- 输入：`course_id`
- 关键返回字段：
  - `solo_distribution`：SOLO 各层次次数和占比（前结构 / 单点结构 / 多点结构 / 关联结构 / 抽象拓展结构）
  - `qa_mode_distribution`：问答模式分布（常规问答 / 追问 / 思考再答 / 无响应）
  - `questioning_type_distribution`：提问类型分布（布鲁姆分类法：识记/理解/应用/分析/评价/创造）
  - `teacher_response_distribution`：教师理答类型分布（简单肯定/针对肯定/激励/否定）
  - `total_questions`：核心提问总次数
  - `effectiveness_score`：提问有效性综合评分及分项（问题认知水平/教师理答水平/学生回答水平）
  - `no_response_count`：无响应次数

### 关联数据（按需调用）

**get_response_time_data**
- 触发条件：无响应占比 > 25% 或单点结构占比 > 70%，需验证候答时间是否足够支持高阶思考
- 关键字段：`wait_time_distribution`（候答时间分布）、`short_wait_ratio`（3秒以内候答比例）

**get_student_interaction_data**
- 触发条件：无响应次数 > 3 或回答覆盖学生数量偏少，需验证参与面是否过窄（少数学生主导回答）
- 关键字段：`avg_participation_rate`、`interaction_student_count`、`total_student_count`

**get_student_learning_data**
- 触发条件：高阶提问（分析/评价/创造）占比 > 30% 但关联结构及以上回答占比 < 20%，需验证课堂是否为探究学习提供了足够的学习准备
- 关键字段：`pta_distribution`、`behavior_distribution`

**get_all_dimension_data**
- 触发条件：多项指标异常且关联分析仍无法归因时调用
- 说明：高 Token 消耗，仅在必要时使用

---

## 关联维度使用策略

| 关联维度 | 使用标识 | 使用场景 |
|---------|---------|---------|
| 应答时间数据 | 验 | 无响应比例高或高阶回答少时，验证候答时间是否是制约学生思考深度的原因 |
| 学生互动数据 | 辅 | 回答覆盖面窄时，补充说明互动参与的不均衡性 |
| 学生学习数据 | 辅 | 高阶提问多但高阶回答少时，补充说明课堂是否为深度思考提供了足够的活动支撑 |

关联数据不得无条件全量加载，须先读取主数据，发现异常后再按上述触发条件调用。

---

## ReAct 执行步骤

1. **识别任务**：确认分析目标为回答建构分类维度
2. **调用主数据**：执行 `get_answer_construction_data(course_id)`
3. **数据完整性检查**：确认 `total_questions` > 0，检查各分布字段是否完整
4. **提取关键事实**：
   - 计算高阶回答比例（关联结构 + 抽象拓展结构占比）
   - 计算低阶主导比例（前结构 + 单点结构占比）
   - 识别无响应占比
   - 识别教师理答中"针对肯定"和"激励"的合计占比
   - 对比提问类型（布鲁姆）与回答层次（SOLO）的匹配度
5. **判断是否需要关联数据**：
   - 若无响应 > 25% 或单点结构 > 70% → 调用 `get_response_time_data`
   - 若无响应次数 > 3 → 调用 `get_student_interaction_data`
   - 若高阶提问多但高阶回答少 → 调用 `get_student_learning_data`
6. **跨维度分析**：将关联数据与回答建构异常点对照，补充说明或归因
7. **形成结论与建议**：结合提问类型、理答方式、候答时间给出可操作建议
8. **按 JSON Schema 输出结果**

---

## Reflection 检查规则

输出前必须自检：

- [ ] SOLO 各层次占比之和是否接近 100%，数值是否与工具返回一致
- [ ] 是否将"单点结构占比高"直接归因为"问题太简单"（需结合提问类型和候答时间综合判断）
- [ ] 调用关联数据前是否满足触发条件，无冗余数据调用
- [ ] 是否区分了"无响应"（学生无法回答）与"无响应"（教师未点名等待）两种情况
- [ ] 教师理答类型为"否定"时，是否已说明其可能对学生参与意愿的影响
- [ ] 提问有效性综合评分的三个分项（问题认知水平/理答水平/学生回答水平）是否都已分析
- [ ] 若 `total_questions` 较少（< 10），是否已说明样本量对结论可信度的影响
- [ ] 输出是否满足 JSON Schema

---

## 输出 JSON Schema

```json
{
  "course_id": "string",
  "skill_id": "answer_construction_analysis",
  "skill_version": "1.0.0",
  "dimension": "answer_construction",
  "key_findings": [
    {
      "conclusion": "string",
      "evidence": [
        {
          "dimension": "string",
          "metric": "string",
          "value": "number | string"
        }
      ],
      "confidence": "number (0-1)"
    }
  ],
  "solo_summary": {
    "high_order_ratio": "number",
    "low_order_ratio": "number",
    "no_response_ratio": "number",
    "dominant_level": "string"
  },
  "questioning_quality": {
    "effectiveness_score": "number",
    "cognitive_level_score": "number",
    "teacher_response_score": "number",
    "student_answer_score": "number",
    "high_order_question_ratio": "number"
  },
  "cross_dimension_analysis": [
    {
      "referenced_dimension": "string",
      "purpose": "supplement | verify | attribution",
      "finding": "string"
    }
  ],
  "uncertainties": ["string"],
  "recommendations": [
    {
      "target": "string",
      "action": "string",
      "rationale": "string"
    }
  ],
  "data_sources": ["string"],
  "reflection_result": {
    "passed": "boolean",
    "issues": ["string"]
  }
}
```
