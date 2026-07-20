# Skill：学生互动分析

## 基本信息

| 字段 | 值 |
|------|-----|
| skill_id | student_interaction_analysis |
| version | 1.0.0 |
| dimension | 学生互动 |
| applicable_scenarios | 分析课堂中学生的参与度、专注度和互动活跃程度，识别互动覆盖不均、参与度低等问题，结合关联维度提供有依据的教学改进建议 |

**Description**

分析课堂学生互动数据，包括抬头率、举手率、参与度和互动人次，评估课堂学生整体参与状态；在发现参与度异常时，按需引用学生学习行为分布、应答时间或回答建构数据进行交叉验证与归因，形成有数据支撑的多维度互动分析报告。

---

## 分析目标

1. 评估学生专注度水平（抬头率趋势与分布）
2. 评估课堂互动覆盖广度（举手率、参与度、互动人次分布）
3. 识别互动低谷时段及可能原因
4. 结合关联维度判断互动问题来源（教学活动类型 / 候答时间不足 / 问题认知难度偏高）
5. 提出针对性的互动优化建议

---

## 可调用数据工具

### 主数据（必须调用）

**get_student_interaction_data**
- 功能：获取当前课程的学生互动维度数据
- 输入：`course_id`
- 关键返回字段：
  - `avg_head_up_rate`：全程平均抬头率
  - `head_up_rate_timeline`：抬头率时间轴分布
  - `avg_hand_raise_rate`：平均举手率
  - `avg_participation_rate`：平均参与度（回答人数/总人数）
  - `interaction_student_count`：AI识别互动人次
  - `total_student_count`：班级总人数
  - `low_engagement_segments`：低参与时段列表

### 关联数据（按需调用）

**get_student_learning_data**
- 触发条件：抬头率 < 50% 或低参与时段 > 3个，需验证是否与课堂活动类型相关
- 关键字段：`behavior_distribution`（课堂行为时长分布）、`pta_distribution`（PTA模型分布）

**get_response_time_data**
- 触发条件：举手率 < 20%，需判断是否因候答时间不足导致学生缺乏响应机会
- 关键字段：`wait_time_distribution`（候答时间分布）、`avg_student_response_duration`

**get_answer_construction_data**
- 触发条件：参与度 < 20%，需判断参与学生的回答质量是否反映问题难度设置不合理
- 关键字段：`solo_distribution`（SOLO层次分布）、`no_response_count`（无响应次数）

**get_all_dimension_data**
- 触发条件：多项指标异常且关联分析仍无法归因时调用
- 说明：高 Token 消耗，仅在必要时使用

---

## 关联维度使用策略

| 关联维度 | 使用标识 | 使用场景 |
|---------|---------|---------|
| 学生学习数据 | 辅/验 | 验证低抬头率是否与讲解教学时段重合；补充说明探究学习时段的参与差异 |
| 应答时间数据 | 辅 | 举手率偏低时，验证候答时间是否充足 |
| 回答建构分类 | 辅 | 参与度偏低时，补充说明已参与学生的回答深度，判断问题设计是否存在难度断层 |

关联数据不得无条件全量加载，须先读取主数据，发现异常后再按上述触发条件调用。

---

## ReAct 执行步骤

1. **识别任务**：确认分析目标为学生互动维度
2. **调用主数据**：执行 `get_student_interaction_data(course_id)`
3. **数据完整性检查**：确认 `total_student_count` > 0，检查 `missing_fields` 和 `data_quality_flags`
4. **提取关键事实**：
   - 计算互动覆盖率（互动人次 / 总人数）
   - 定位抬头率低谷时段
   - 对比举手率与参与度的差值（差值大说明举手后未被点名）
5. **判断是否需要关联数据**：
   - 若抬头率 < 50% 或低参与时段 ≥ 3个 → 调用 `get_student_learning_data`
   - 若举手率 < 20% → 调用 `get_response_time_data`
   - 若参与度 < 20% → 调用 `get_answer_construction_data`
6. **跨维度分析**：将关联数据与互动异常点进行对照，补充验证或归因
7. **形成结论与建议**：给出数据支撑的结论、不确定性说明、可执行的教学建议
8. **按 JSON Schema 输出结果**

---

## Reflection 检查规则

输出前必须自检：

- [ ] 所有引用数值是否与工具返回数据一致，无凭空捏造
- [ ] 是否把相关性（如抬头率低与讲解时段重合）误表述为因果关系
- [ ] 调用的关联数据是否满足触发条件，有无无关数据被引用
- [ ] 若数据存在 `missing_fields` 或 `data_quality_flags`，结论中是否已注明不确定性
- [ ] 互动覆盖率与参与度的区别是否表述清晰
- [ ] 教学建议是否与识别的具体问题对应，避免泛化建议
- [ ] 输出是否满足 JSON Schema

---

## 输出 JSON Schema

```json
{
  "course_id": "string",
  "skill_id": "student_interaction_analysis",
  "skill_version": "1.0.0",
  "dimension": "student_interaction",
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
  "cross_dimension_analysis": [
    {
      "referenced_dimension": "string",
      "purpose": "supplement | verify | attribution",
      "finding": "string"
    }
  ],
  "low_engagement_segments": [
    {
      "time_range": "string",
      "head_up_rate": "number",
      "possible_cause": "string"
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
