# Skill：学生学习分析

## 基本信息

| 字段 | 值 |
|------|-----|
| skill_id | student_learning_analysis |
| version | 1.0.0 |
| dimension | 学生学习 |
| applicable_scenarios | 分析课堂学习行为时长分布与 PTA 教学模式分布，评估教学活动结构的合理性与学生深度学习的发生情况；在发现结构失衡时，按需引用互动数据或回答建构数据进行交叉验证，形成有依据的课堂活动结构分析报告 |

**Description**

分析课堂学生学习行为分布（教师讲授/师生问答/学生讨论/学生练习等）和 PTA 教学模式分布（交互教学/探究学习/讲解教学/巩固检测等），评估课堂活动结构是否支撑深度学习；在活动结构异常时，按需引用学生互动数据或回答建构分类数据进行佐证与归因，形成多维度的学习行为结构分析报告。

---

## 分析目标

1. 评估课堂各学习行为的时长分布是否均衡（教师主导 vs 学生主导）
2. 评估 PTA 模式分布是否支撑目标教学意图（讲解型 / 探究型 / 混合型）
3. 识别高认知负荷时段（长时间讲解教学）与低参与时段的相关性
4. 结合关联维度判断活动结构问题对学生参与和思维深度的实际影响
5. 提出针对课堂活动结构的优化建议

---

## 可调用数据工具

### 主数据（必须调用）

**get_student_learning_data**
- 功能：获取当前课程的学生学习行为与 PTA 模式数据
- 输入：`course_id`
- 关键返回字段：
  - `behavior_distribution`：各课堂行为时长（教师讲授 / 师生问答 / 学生练习 / 学生讨论 / 学生展示 / 学生实验 / 自主学习等）
  - `teacher_student_ratio`：教师行为时长占比 vs 学生行为时长占比
  - `pta_distribution`：PTA 模型各类型时长（交互教学 / 探究学习 / 讲解教学 / 知识总结 / 巩固检测 / 识记学习等）
  - `dominant_mode`：课堂主导教学模式
  - `activity_timeline`：活动类型时间轴

### 关联数据（按需调用）

**get_student_interaction_data**
- 触发条件：教师行为占比 > 60%，需验证高讲授比例是否导致学生参与度下降
- 关键字段：`avg_head_up_rate`、`avg_participation_rate`、`low_engagement_segments`

**get_answer_construction_data**
- 触发条件：探究学习或讨论时长占比 > 30%，需验证学生在深度学习时段的思维质量
- 关键字段：`solo_distribution`（SOLO层次分布）、`high_order_ratio`

**get_response_time_data**
- 触发条件：师生问答时长占比 > 25%，需判断问答环节中候答时间分配是否支持有效思考
- 关键字段：`wait_time_distribution`、`avg_wait_time`

**get_all_dimension_data**
- 触发条件：多项行为指标失衡且关联分析仍无法归因时调用
- 说明：高 Token 消耗，仅在必要时使用

---

## 关联维度使用策略

| 关联维度 | 使用标识 | 使用场景 |
|---------|---------|---------|
| 学生互动数据 | 辅 | 教师行为占比偏高时，补充说明学生参与度和专注度的实际表现 |
| 回答建构分类 | 验 | 探究学习占比高时，验证学生思维深度是否达到关联结构及以上水平 |
| 应答时间数据 | 辅 | 问答时长占比高时，补充说明候答时间分配是否与活动结构匹配 |

关联数据不得无条件全量加载，须先读取主数据，发现异常后再按上述触发条件调用。

---

## ReAct 执行步骤

1. **识别任务**：确认分析目标为学生学习行为维度
2. **调用主数据**：执行 `get_student_learning_data(course_id)`
3. **数据完整性检查**：确认 `behavior_distribution` 各字段不全为空，检查 `data_quality_flags`
4. **提取关键事实**：
   - 计算教师行为 vs 学生行为的时长占比
   - 识别 PTA 主导模式（占比最高的1-2种）
   - 标记时长为 0 的行为类型（如学生实验、自主学习）
   - 定位讲解教学连续超过 10 分钟的时段
5. **判断是否需要关联数据**：
   - 若教师行为占比 > 60% → 调用 `get_student_interaction_data`
   - 若探究学习/讨论时长 > 30% → 调用 `get_answer_construction_data`
   - 若师生问答时长 > 25% → 调用 `get_response_time_data`
6. **跨维度分析**：将关联数据与活动结构异常点对照，补充说明或归因
7. **形成结论与建议**：评估活动结构合理性，给出具体优化方向（非泛化建议）
8. **按 JSON Schema 输出结果**

---

## Reflection 检查规则

输出前必须自检：

- [ ] 所有时长数值和占比是否与工具返回数据一致，无凭空捏造
- [ ] 是否把"讲解教学时长长"与"学生理解效果差"直接等同（相关性 ≠ 因果）
- [ ] 调用关联数据前是否满足触发条件，无冗余数据调用
- [ ] 对于时长为 0 的行为类型，是否已说明其缺席对课堂结构的影响而非直接判定为"不好"
- [ ] 若 `data_quality_flags` 有标记，结论中是否已注明数据局限性
- [ ] 课堂类型（理科 / 文科 / 实践课）是否已在建议中被考虑
- [ ] 输出是否满足 JSON Schema

---

## 输出 JSON Schema

```json
{
  "course_id": "string",
  "skill_id": "student_learning_analysis",
  "skill_version": "1.0.0",
  "dimension": "student_learning",
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
  "activity_structure": {
    "teacher_ratio": "number",
    "student_ratio": "number",
    "dominant_pta_modes": ["string"],
    "zero_activity_types": ["string"]
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
