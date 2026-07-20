# Skill：应答时间分析

## 基本信息

| 字段 | 值 |
|------|-----|
| skill_id | response_time_analysis |
| version | 1.0.0 |
| dimension | 应答时间 |
| applicable_scenarios | 分析课堂中教师候答时间分布与学生应答时长分布，评估教师是否给予学生充分的思考空间；在发现候答时间分配与学生回答质量不匹配时，按需引用回答建构分类或学生互动数据进行交叉验证，形成有依据的课堂节奏与思考空间分析报告 |

**Description**

分析课堂应答时间数据，包括教师候答时间分布（3秒以内 / 3-5秒 / 5秒以上）和学生应答时长分布，评估教师候答行为是否与问题认知难度相匹配，是否为学生提供了充分的思考空间；在发现候答时间与问答效果存在明显落差时，按需引用回答建构分类数据或学生互动数据进行验证归因，形成多维度的课堂应答节奏分析报告。

---

## 分析目标

1. 评估候答时间的整体分布是否合理（短候答 / 适中候答 / 充分候答各占比）
2. 识别高频短候答时段及其对学生思考深度的潜在影响
3. 分析学生应答时长分布，判断学生回答的充分程度
4. 结合关联维度验证候答时间分配对回答质量和互动参与的实际影响
5. 提出调整候答时间策略的针对性建议

---

## 可调用数据工具

### 主数据（必须调用）

**get_response_time_data**
- 功能：获取当前课程的应答时间维度数据
- 输入：`course_id`
- 关键返回字段：
  - `wait_time_distribution`：候答时间分布（次数和占比）
    - `within_3s`：3秒以内次数/占比
    - `between_3_5s`：3-5秒次数/占比
    - `above_5s`：5秒以上次数/占比
  - `avg_wait_time`：平均候答时长（秒）
  - `student_response_duration_distribution`：学生应答时长分布
  - `avg_student_response_duration`：平均学生应答时长（秒）
  - `total_questions`：有效问答总次数
  - `short_wait_segments`：高频短候答时段列表（时间轴）

### 关联数据（按需调用）

**get_answer_construction_data**
- 触发条件：短候答（3秒以内）占比 > 40%，需验证短候答是否与低阶回答（单点结构主导）相关
- 关键字段：`solo_distribution`、`no_response_count`、`qa_mode_distribution`

**get_student_interaction_data**
- 触发条件：候答时间充足（5秒以上 > 50%）但学生举手率仍低（< 20%），需判断候答充足时参与度是否仍未提升，排除候答时间以外的制约因素
- 关键字段：`avg_hand_raise_rate`、`avg_participation_rate`、`interaction_student_count`

**get_student_learning_data**
- 触发条件：不同教学活动类型（讲解 vs 探究）中候答时间分配差异明显，需验证教学模式切换与候答行为变化的关联
- 关键字段：`activity_timeline`、`pta_distribution`

**get_all_dimension_data**
- 触发条件：多项指标异常且关联分析仍无法归因时调用
- 说明：高 Token 消耗，仅在必要时使用

---

## 关联维度使用策略

| 关联维度 | 使用标识 | 使用场景 |
|---------|---------|---------|
| 回答建构分类 | 验 | 短候答占比高时，验证是否对应低阶 SOLO 回答比例上升，形成因果链 |
| 学生互动数据 | 辅 | 候答充足但举手率低时，补充说明参与度低可能有其他成因 |
| 学生学习数据 | 辅 | 候答时间在不同活动类型中差异明显时，补充说明教学模式对候答节奏的影响 |

关联数据不得无条件全量加载，须先读取主数据，发现异常后再按上述触发条件调用。

---

## ReAct 执行步骤

1. **识别任务**：确认分析目标为应答时间维度
2. **调用主数据**：执行 `get_response_time_data(course_id)`
3. **数据完整性检查**：确认 `total_questions` > 0，检查 `wait_time_distribution` 各字段完整性
4. **提取关键事实**：
   - 计算短候答（≤3秒）、适中候答（3-5秒）、充分候答（>5秒）的各自占比
   - 计算平均候答时长，与教育研究建议值（3-5秒基础问题 / 5秒以上高阶问题）对比
   - 分析学生应答时长分布，识别极短应答（< 3秒）的占比
   - 定位高频短候答时段，与课堂活动时段对应
5. **判断是否需要关联数据**：
   - 若短候答占比 > 40% → 调用 `get_answer_construction_data`
   - 若候答充足（>5秒 > 50%）但举手率低 → 调用 `get_student_interaction_data`
   - 若候答分布在不同时段差异明显 → 调用 `get_student_learning_data`
6. **跨维度分析**：将关联数据与候答时间分布对照，补充验证或归因
7. **形成结论与建议**：针对候答时间分配给出可量化的改进目标（如：将高阶问题候答时间提升至5秒以上）
8. **按 JSON Schema 输出结果**

---

## Reflection 检查规则

输出前必须自检：

- [ ] 候答时间各区间占比之和是否接近 100%，数值是否与工具返回一致
- [ ] 是否将"短候答"直接等同于"教学质量差"（部分简单确认型问题短候答是合理的）
- [ ] 调用关联数据前是否满足触发条件，无冗余数据调用
- [ ] 是否区分了不同类型问题（事实性 vs 分析性）对候答时间合理范围的不同要求
- [ ] 若样本量（`total_questions`）较少（< 10），是否已说明数据局限性
- [ ] 学生应答时长极短时，是否考虑了"齐答"场景（多人同时简短回答）的可能性
- [ ] 建议中的目标候答时长是否有数据或研究依据支撑，避免主观判断
- [ ] 输出是否满足 JSON Schema

---

## 输出 JSON Schema

```json
{
  "course_id": "string",
  "skill_id": "response_time_analysis",
  "skill_version": "1.0.0",
  "dimension": "response_time",
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
  "wait_time_summary": {
    "avg_wait_time_seconds": "number",
    "short_wait_ratio": "number",
    "medium_wait_ratio": "number",
    "long_wait_ratio": "number",
    "high_frequency_short_wait_segments": ["string"]
  },
  "student_response_summary": {
    "avg_response_duration_seconds": "number",
    "very_short_response_ratio": "number"
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
