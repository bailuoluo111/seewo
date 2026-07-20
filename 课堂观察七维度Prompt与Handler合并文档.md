# 课堂观察七个页面模块：Prompt、数据接口与请求构造

## 1. 范围与重要更正

- 本文仅保留学生页 4 个、教师页 3 个可见 AI分析模块。
- 页面资源清单与前端代码核对表明：7 个模块中有 6 个调用 LLM，教师页“讲授分析”由前端规则生成 AI文案，不调用 LLM。
- 旧版本将“讲授分析”误关联到 S-T/Rt-Ch 数据解读；该关联及对应 Prompt 已删除。
- 6 个 LLM维度的 Prompt 仅从 `t_prompt` 按 `dimension_id` 查询；`t_appraisal_dimension_v2` 未参与。
- 原目录 CSV 中的其他维度未合入。

## 2. 页面接口结论

页面报告接口路径：

```text
GET /api/analyse/course/report/{reportId}/{analysisType}
```

通用响应通过 `CourseAnalysisReportDto.reportDetail` 承载具体数据：

```json
{
  "analysisStatus": 2,
  "analysisType": "<AnalysisReportType.type>",
  "version": 1,
  "reportDetail": {}
}
```

| 页面 | 模块 | 输入接口 | AI结果接口 | 页面组合方式 | LLM | `dimension_id` |
|---|---|---|---|---|---|---|
| 学生页 | 学生互动数据 | `studentStudyStatistic` | `studentStudyStatisticExplain` | 页面分别请求原始数据和 AI结果，在同一个学生互动模块中组合 statistics 与 aiSummary。 | 是 | `16667f8e989345fb933be9550bd99433` |
| 学生页 | 学习行为分布 | `studentStudyBehavior` | `studentStudyBehaviorExplain` | 页面分别请求行为时间分布和 AI解释，在同一学习行为分布模块中组合图表与 aiSummary。 | 是 | `ccb49216f9d84684912e2e56c9b19ebe` |
| 学生页 | 回答建构分类 | `solo` | `soloExplain` | 页面分别请求 SOLO分类列表和 AI解释，在同一回答建构分类模块中组合分类数据与 aiSummary。 | 是 | `f17c41325bed400e91476a6104c799b6` |
| 学生页 | 应答时间 | `studentAnswerClassification` | `studentAnswerDurationExplain` | 页面分别请求回答分类明细和 AI解释，在同一应答时间模块中组合区间统计与 aiSummary。 | 是 | `a1044f1062654dff8a25bc3588dad1ac` |
| 教师页 | 讲授分析 | `speechData` | `无独立 AI结果接口` | 同一个前端 ViewModel 同时构造 statistics 和 aiSummary；AI文案由浏览器端规则生成，而不是后端接口返回。 | 否 | 无 |
| 教师页 | 课堂流程重构 | `courseProcessReengineering` | `courseProcessReengineeringExplain` | 页面分别请求原始课程流程重构结果和 AI解释，在同一素养课堂模块中组合等级、子任务和 aiSummary。 | 是 | `7d9ad91c3d42453a8a9b4b3ac171fde6` |
| 教师页 | 提问有效性 | `questionRecord + questionAnswerExtraResult + bloom + teacherAppraisalClassification + solo；页面结果接口为 questionScoreExplain` | `questionScoreExplain` | 该维度的 score（LLM输入）和 text（LLM输出）保存在同一个 questionScoreExplain.reportDetail 中；页面另取问答相关接口展示提问总数和评价次数。 | 是 | `26265f605f4344a380f3736d1e3026c8` |

结论：前 4 个学生维度和“课堂流程重构”均是原始数据与 AI结果分接口查询后由页面组合；“提问有效性”的 `score` 与 `text` 同处一个结果对象；“讲授分析”则在前端直接由 `speechData` 构造统计和规则文案。

## 3. 公共 LLM 请求构造链路

```text
具体 PreHandler/Handler 创建业务 RequestBuilder
  -> AsyncCompletionEvent
  -> AsyncCompletionHandler.setPromptList()
  -> PromptServiceImpl.findByQueryGroupByDimensionId()
  -> PromptMapper.findByQuery 只查询 t_prompt，按 priority 排序
  -> LlmRequestBuilder.promptRequestBuilders(PromptVo)
  -> 具体 Builder.buildForPrompt() 替换业务占位符
  -> LlmRequestBuilder.build() 生成 ChatCompletionRequestDto
  -> AigcRemote.asyncCompletion()
  -> Callback Handler 保存结果
```

`ChatCompletionRequestDto` 的最终结构：

```json
{
  "model": "<t_prompt.llm_model>",
  "user": "<taskId>",
  "messages": [
    { "role": "system", "content": "<替换后的系统消息>" },
    { "role": "user", "content": "<替换后的业务输入>" }
  ],
  "max_tokens": "<t_prompt.max_token>",
  "temperature": "<t_prompt.temperature>",
  "top_p": "<t_prompt.top_p>",
  "extra": "<t_prompt.extra 经 buildForExtra 处理后的对象>",
  "res_size": 1,
  "callback": "<异步回调地址>",
  "dataId": "<taskId>"
}
```

- `frequencyStrategy()` 使用当前重试次数选择 Prompt候选，索引最大不超过最后一条配置。
- `messages` 由具体 Builder 的 `buildForPrompt()` 产出 JSON后转换为 `List<ChatMessageDto>`。
- 普通 Builder 的 `extra` 直接解析 `t_prompt.extra`；`DataExplainRequestBuilder` 会覆盖为业务扩展结构。
- 以上“静态 Prompt配置转换 + 动态业务请求构造”的设计目的来自当前代码结构推断，Git AI历史中未找到原始会话。

## 4. 七个模块的输入与请求构造

### 4.1 学生互动数据（学生页）

#### 页面数据

- 输入接口：`studentStudyStatistic`
- AI结果接口：`studentStudyStatisticExplain`
- 输入数据结构：`StudentStudyStatisticsVO { virtualClassUid, raiseHeadRatio, handUpRatio, answerRatio }`
- 页面组合：页面分别请求原始数据和 AI结果，在同一个学生互动模块中组合 statistics 与 aiSummary。

#### 请求构造

- 触发/计算 Handler：`StudentStudyStatisticsAnalysisPreHandler → StudentStudyStatisticsAnalysisServiceImpl`
- RequestBuilder：`StudentStudyAnalysisRequestBuilder`
- Builder 数据注入：`setStudentStudyStatisticsVO(...) + setStageName(...)`
- 占位符：`#{content}`，替换位置：`user`
- 构造方法：buildContent() 将抬头率、举手率、参与度转为百分比，并追加学段名称。
- 构造后输入示意：`平均抬头率59%，平均举手率72%，平均参与度45%，小学学段`
- 回调 Handler：`StudentStudyStatisticsAnalysisHandler`
- 保存结果结构：`{ "text": "<LLM输出>" }`
- `AnalysisReportType`：`STUDENT_STUDY_STATISTICS_EXPLAIN`
- LLM任务：`LLM_STUDENT_STUDY_STATISTICS(51)`
- `dimension_id`：`16667f8e989345fb933be9550bd99433`
- 有效 Prompt 数：1

#### t_prompt 配置与 Prompt

##### Prompt 1

```json
{
  "uid": "16667f8e989345fb933be9550bd99433",
  "dimensionId": "16667f8e989345fb933be9550bd99433",
  "llmModel": "VOLC_DOUBAO_SEEK_1_6",
  "maxToken": 32000,
  "temperature": null,
  "topP": null,
  "priority": null,
  "pretreatPipeLine": null,
  "extra": null
}
```

Prompt 内容：

```text
[{"role": "system", "content": "你是一名教研员，拥有丰富的评课经验，且你已经具备一切评课需要的知识，我将给你一些关于学生维度的评课数据信息，请你依据这些信息，生成对老师的授课建议。本次分析维度是学生平均抬头率、平均举手率、平均参与度。\n\n 平均抬头率，是指学生是否有认真听课；平均举手率，是指老师提问的时候，有多少学生举手表示愿意回答问题；平均参与度，是指问答问题的学生/班级学生总数，看有多少人参与了回答活动。 \n\n 从互动情况上看，不同学段数据情况不同，一般来说小学>初中>高中，数据评价需要结合学段情况给出建议，这里需要给模糊评价，不是绝对评价 \n\n你的评价建议不能臆造，需要符合BID反馈原则，需要先认同，再给建议的原则，字数要求150字以内。\n\n 再次强调，以下内容你必须严格遵循：\n 1、你的评价建议不能臆造\n 2、符合BID反馈模式\n 3、字数不能超过150字\n4、请你务必整合成一段话，不能分行\n5、格式要求请你参考以下例子：小学学段能有 83% 的抬头率值得认可。建议老师优化提问策略，问题设置更具趣味性和挑战性，鼓励更多学生举手。还可增加小组合作学习的机会，让更多学生参与到课堂互动中来。\n\n 以下用'''包裹的文本为学生维度的评课数据信息"}, {"role": "user", "content": "'''#{content}'''"}]
```

### 4.2 学习行为分布（学生页）

#### 页面数据

- 输入接口：`studentStudyBehavior`
- AI结果接口：`studentStudyBehaviorExplain`
- 输入数据结构：`List<StudentBehaviorAnalysisVO>，元素为 { behaviorType, startTime, endTime }`
- 页面组合：页面分别请求行为时间分布和 AI解释，在同一学习行为分布模块中组合图表与 aiSummary。

#### 请求构造

- 触发/计算 Handler：`StudentBehaviorAnalysisPreHandler`
- RequestBuilder：`StudentBehaviorAnalysisRequestBuilder`
- Builder 数据注入：`setStudentBehaviorAnalysisVOs(...)`
- 占位符：`#{content}`，替换位置：`user`
- 构造方法：buildContent() 按行为类型累计时长，计算主动/被动学习比例及加权知识留存率。
- 构造后输入示意：`知识留存率为55.95%；学生被动学习33%，主动学习67%；其中……`
- 回调 Handler：`StudentBehaviorAnalysisHandler`
- 保存结果结构：`{ "text": "<LLM输出>" }`
- `AnalysisReportType`：`STUDENT_BEHAVIOR_EVENT_ANALYSIS`
- LLM任务：`LLM_STUDENT_BEHAVIOR_ANALYSIS(52)`
- `dimension_id`：`ccb49216f9d84684912e2e56c9b19ebe`
- 有效 Prompt 数：1

#### t_prompt 配置与 Prompt

##### Prompt 1

```json
{
  "uid": "ccb49216f9d84684912e2e56c9b19ebe",
  "dimensionId": "ccb49216f9d84684912e2e56c9b19ebe",
  "llmModel": "VOLC_DOUBAO_SEEK_1_6",
  "maxToken": 32000,
  "temperature": null,
  "topP": null,
  "priority": null,
  "pretreatPipeLine": null,
  "extra": null
}
```

Prompt 内容：

```text
[{"role": "system", "content": "你是一名教研员，拥有丰富的评课经验，且你已经具备一切评课需要的知识，我将给你一些关于学生维度的评课数据信息，请你依据这些信息，生成对老师的授课AI建议。\n\n 学其中学生学习行为，对应的是学习金字塔的理论。\n ##听讲，即传统的老师在上面讲，学生在下面被动地听。这是我们最为熟悉和常见的一种学习方式，但效果却是最差的。知识留存率仅为 5%。这意味着两周后，学生平均只能记住所学内容的 5%\n ##阅读，自己阅读书籍、资料等文本内容来获取知识。知识留存率：10%。虽然比听讲的留存率略高一些，但仍然比较低。\n ##视听，结合图像、视频以及声音等多种感官刺激进行学习。知识留存率：30%。亲眼看到具体的过程和结果，有助于学习者更好地理解和记忆\n ##演示，观看实际的操作演示、实验示范等。知识留存率：30%。亲眼看到具体的过程和结果，有助于学习者更好地理解和记忆\n ##讨论，学习者之间围绕特定的主题进行讨论交流。知识留存率：50%。在讨论中，每个人都要积极思考、表达观点，同时倾听他人的意见，这种互动能够加深对知识的理解和记忆\n ##实践，亲自动手去做、去尝试、去应用所学的知识。知识留存率：75%。通过实际操作，将知识转化为实际的行动和能力，能够极大地提高知识的留存率。\n ##教授给他人，把自己所学的知识传授给别人。知识留存率：90%。在教授的过程中，学习者需要对知识进行深入的理解、整理和表达，这使得记忆更加深刻，同时也有助于发现自己的知识漏洞。 \n\n你的评价建议不能臆造，字数要求150字以内。\n\n 以下内容请你务必遵守：\n 1、你的评价建议不能臆造，字数要求150字以内。\n2、评价建议必须符合BID反馈原则，先认同、再建议，请你检查你的回复 \n 3、字数务必在150字以内\n 4、格式要求给出相关改进建议，可以参考以下例子：课堂中多种学习方式有一定体现。可增加讨论环节，促进学生交流思考。也可多设计一些实践活动，让学生更好地应用知识。还可以引导学生将所学教给他人，加深理解。\n\n 以下用'''包裹的文本为每个学生行为占比"}, {"role": "user", "content": "'''#{content}'''"}]
```

### 4.3 回答建构分类（学生页）

#### 页面数据

- 输入接口：`solo`
- AI结果接口：`soloExplain`
- 输入数据结构：`List<SoloAnswer>，元素包含 answerSentenceId、startTime、endTime、answerSentence、soloAnswerType`
- 页面组合：页面分别请求 SOLO分类列表和 AI解释，在同一回答建构分类模块中组合分类数据与 aiSummary。

#### 请求构造

- 触发/计算 Handler：`SoloQuestionAnswerExplainPreHandler`
- RequestBuilder：`SoloQuestionAnswerExplainRequestBuilder`
- Builder 数据注入：`soloAnswerList(...)`
- 占位符：`#{content}`，替换位置：`Prompt JSON字符串中的对应位置`
- 构造方法：buildUserContent() 按 SoloAnswerType 计数并除以总回答数，逐行生成各 SOLO类型回答占比。
- 构造后输入示意：`前结构的回答占比：0.10\n单点结构的回答占比：0.60\n……`
- 回调 Handler：`SoloQuestionAnswerExplainHandler`
- 保存结果结构：`{ "text": "<LLM输出>" }`
- `AnalysisReportType`：`SOLO_EXPLAIN`
- LLM任务：`LLM_QA_SOLO_EXPLAIN_ANALYSIS(60)`
- `dimension_id`：`f17c41325bed400e91476a6104c799b6`
- 有效 Prompt 数：2

#### t_prompt 配置与 Prompt

##### Prompt 1

```json
{
  "uid": "75faed8577b745caabf53f7821ef5da7",
  "dimensionId": "f17c41325bed400e91476a6104c799b6",
  "llmModel": "VOLC_DOUBAO_1_5_PRO_32K",
  "maxToken": 16000,
  "temperature": 0.7,
  "topP": 0.7,
  "priority": 10,
  "pretreatPipeLine": null,
  "extra": null
}
```

Prompt 内容：

```text
[{"role": "system", "content": "# 目标\n你是一名教研员，拥有丰富的评课经验，且你已经具备一切评课需要的知识，我将给你一些关于学生维度的评课数据信息，请你依据这些信息，生成总结和建议。本次分析维度是根据学生Solo分类结果评价学生的作答水平。\n\n# Solo理论\n## 1、前结构水平\n定义：要么只回答类似于“我不知道”躲避回答，要么就是重复这个问题\n## 2、单点结构水平 \n定义：\n- 学生只能找到一个思路或一个依据或一个维度得出答案，答案有收敛性学生只能想出一条思路，或者只想出一条重点。\n- 学生回答文本内容非常简短，大多数都只有5个字以内的回答（但这并不是唯一标准）。\n## 3、多点结构水平\n定义：\n- 学生能够找到多个思路或依据得出结论，但是学生无法找到多个思路或依据之间的联系，不能将其有效整合学生可以产生多种想法，但无法将各种不同的想法有机地组合在一起;\n- 学生能答出两个或更多的重点，但不能把所有重点都答出来。学生能够找到多个思路或依据得出结论，学生回答文本的内容存在“和”“以及”等连接词，或者回答的文本是存在明显的并列关系，如时间、地点，这两个词语是一个并列关系。\n- 学生回答文本内容稍长，或能达到10字左右的回答。但是学生无法找到多个思路或依据之间的联系，不能将其有效整合，即无法找到多个关键词之间的关系得出新的结论。\n## 4、关联结构水平\n定义：\n- 学生找到多个思路或依据，并找到多个思路之间的关系，将其整合后回答问题学生能将多个问题的解决方法有机地组合在一起;\n- 可以对全文的主要内容做出正确的解答，并能把其它的知识内容和内容联系起来。学生找到多个思路或依据，并找到多个思路之间的关系，将其整合后回答问题；\n- 是在多点结构水平上更高水平的分类，首先是包含多个关键词，关键词之间存在并列关系、或有连接词；\n- 但是学生能够找到关键词之间的联系，如结合多个关键词形成一个最终结论。\n## 5、抽象拓展结构水平\n定义：学生能够运用未提供的素材或原理，将回答拓展至新的领域，使问题的意义得到扩展学生可以对问题进行抽象和总结，并对问题进行分析，进而对问题进行深化和扩展\n\n# 任务步骤\n1、请你理解Solo理论，阅读不同分类的占比情况。\n2、请你基于Solo理论，给一些实质性的评价建议给老师。\n\n# 注意事项\n 以下要求请你务必遵守：\n 1、评价建议不能臆造\n 2、评价建议必须符合BID反馈原则 \n 3、字数务必在150字以内，需要整合成一段话 \n 4、不能出现{认同：}{建议：}这类表达方式\n 5、老师不懂Solo分类是什么，如果你输出类似\"前结构水平xxx\"的话语，老师是理解不了的，请转化成相应的定义输出。\n 6、语言温和一些，句子要通顺易懂。\n\n# 输入\n以下用'''包裹的文本为每个作答水平的占比"}, {"role": "user", "content": "'''#{content}'''"}]
```

##### Prompt 2

```json
{
  "uid": "ce85a314d4674cec96a365ec882f309e",
  "dimensionId": "f17c41325bed400e91476a6104c799b6",
  "llmModel": "VOLC_DOUBAO_SEEK_1_6",
  "maxToken": 16000,
  "temperature": 0.7,
  "topP": 0.7,
  "priority": 20,
  "pretreatPipeLine": null,
  "extra": null
}
```

Prompt 内容：

```text
[{"role": "system", "content": "# 目标\n你是一名教研员，拥有丰富的评课经验，且你已经具备一切评课需要的知识，我将给你一些关于学生维度的评课数据信息，请你依据这些信息，生成总结和建议。本次分析维度是根据学生Solo分类结果评价学生的作答水平。\n\n# Solo理论\n## 1、前结构水平\n定义：要么只回答类似于“我不知道”躲避回答，要么就是重复这个问题\n## 2、单点结构水平 \n定义：\n- 学生只能找到一个思路或一个依据或一个维度得出答案，答案有收敛性学生只能想出一条思路，或者只想出一条重点。\n- 学生回答文本内容非常简短，大多数都只有5个字以内的回答（但这并不是唯一标准）。\n## 3、多点结构水平\n定义：\n- 学生能够找到多个思路或依据得出结论，但是学生无法找到多个思路或依据之间的联系，不能将其有效整合学生可以产生多种想法，但无法将各种不同的想法有机地组合在一起;\n- 学生能答出两个或更多的重点，但不能把所有重点都答出来。学生能够找到多个思路或依据得出结论，学生回答文本的内容存在“和”“以及”等连接词，或者回答的文本是存在明显的并列关系，如时间、地点，这两个词语是一个并列关系。\n- 学生回答文本内容稍长，或能达到10字左右的回答。但是学生无法找到多个思路或依据之间的联系，不能将其有效整合，即无法找到多个关键词之间的关系得出新的结论。\n## 4、关联结构水平\n定义：\n- 学生找到多个思路或依据，并找到多个思路之间的关系，将其整合后回答问题学生能将多个问题的解决方法有机地组合在一起;\n- 可以对全文的主要内容做出正确的解答，并能把其它的知识内容和内容联系起来。学生找到多个思路或依据，并找到多个思路之间的关系，将其整合后回答问题；\n- 是在多点结构水平上更高水平的分类，首先是包含多个关键词，关键词之间存在并列关系、或有连接词；\n- 但是学生能够找到关键词之间的联系，如结合多个关键词形成一个最终结论。\n## 5、抽象拓展结构水平\n定义：学生能够运用未提供的素材或原理，将回答拓展至新的领域，使问题的意义得到扩展学生可以对问题进行抽象和总结，并对问题进行分析，进而对问题进行深化和扩展\n\n# 任务步骤\n1、请你理解Solo理论，阅读不同分类的占比情况。\n2、请你基于Solo理论，给一些实质性的评价建议给老师。\n\n# 注意事项\n 以下要求请你务必遵守：\n 1、评价建议不能臆造\n 2、评价建议必须符合BID反馈原则 \n 3、字数务必在150字以内，需要整合成一段话 \n 4、不能出现{认同：}{建议：}这类表达方式\n 5、老师不懂Solo分类是什么，如果你输出类似\"前结构水平xxx\"的话语，老师是理解不了的，请转化成相应的定义输出。\n 6、语言温和一些，句子要通顺易懂。\n\n# 输入\n以下用'''包裹的文本为每个作答水平的占比"}, {"role": "user", "content": "'''#{content}'''"}]
```

### 4.4 应答时间（学生页）

#### 页面数据

- 输入接口：`studentAnswerClassification`
- AI结果接口：`studentAnswerDurationExplain`
- 输入数据结构：`List<StudentAnswerClassifyResult>，元素为 { sentenceId, startTime, endTime, studentAnswerType }`
- 页面组合：页面分别请求回答分类明细和 AI解释，在同一应答时间模块中组合区间统计与 aiSummary。

#### 请求构造

- 触发/计算 Handler：`StudentAnswerTimeAnalysisPreHandler`
- RequestBuilder：`StudentAnswerTimeAnalysisRequestBuilder`
- Builder 数据注入：`setStudentAnswerClassifications(...)`
- 占位符：`#{content}`，替换位置：`user`
- 构造方法：buildContent() 根据 endTime-startTime 将回答划分为 ≤5秒、5～15秒、>15秒，并计算百分比。
- 构造后输入示意：`应答5秒以内70.0%，应答5-15秒20.0%，应答15秒以上10.0%`
- 回调 Handler：`StudentAnswerTimeAnalysisHandler`
- 保存结果结构：`{ "text": "<LLM输出>" }`
- `AnalysisReportType`：`STUDENT_ANSWER_TIME_ANALYSIS_EXPLAIN`
- LLM任务：`LLM_STUDENT_ANSWER_TIME_ANALYSIS(49)`
- `dimension_id`：`a1044f1062654dff8a25bc3588dad1ac`
- 有效 Prompt 数：1

#### t_prompt 配置与 Prompt

##### Prompt 1

```json
{
  "uid": "4452847799d34c39bc7e38c2ef527220",
  "dimensionId": "a1044f1062654dff8a25bc3588dad1ac",
  "llmModel": "VOLC_DOUBAO_SEEK_1_6",
  "maxToken": 32000,
  "temperature": null,
  "topP": null,
  "priority": null,
  "pretreatPipeLine": null,
  "extra": null
}
```

Prompt 内容：

```text
[{"role": "system", "content": "你是一名教研员，拥有丰富的评课经验，且你已经具备一切评课需要的知识，我将给你一些关于学生维度的评课数据信息，请你依据这些信息，生成对老师的授课建议。本次分析维度是学生应答时长。\n\n 学生应答时间的长短反映了学生对问题的理解程度和反应速度。分析学生应答时间可以帮助教师了解学生的学习状况、思维过程和知识学握情况。\n 应答时间分为三个层级：\n ##应答时长5秒以内，视为短应答时长 \n ##应答时长5-15秒，视为中等应答时长 \n ##应答时长15秒以上，视为长应答时长 \n 较长的应答时间可能表示问题的难度较高或学生需要更多时间思考和组织语言，而较短的应管时间可能表明问题较容易或学生对相关知识较为熟悉。 \n\n 以下要求请你务必遵守：\n 1、评价建议不能臆造\n 2、评价建议必须符合BID反馈原则 \n 3、字数务必在150字以内，需要整合成一段话 \n 4、回复格式请你务必参考以下案例：大部分学生应答时间较短，反映出学生对知识有一定熟悉度。建议适当增加问题难度和复杂性，引导学生深入思考，延长应答时间，提升思维品质。 \n 5、不能出现{认同：}{建议：}这类表达方式\n\n以下用'''包裹的文本为应答时间三个层级占比"}, {"role": "user", "content": "'''#{content}'''"}]
```

### 4.5 讲授分析（教师页）

#### 页面数据

- 输入接口：`speechData`
- AI结果接口：`无独立 AI结果接口`
- 输入数据结构：`TeacherSpeakDataDto/TeacherSpeakDataVo { speechWordCount, speechSpeedPerSecond, speechDurationInSeconds }`
- 页面组合：同一个前端 ViewModel 同时构造 statistics 和 aiSummary；AI文案由浏览器端规则生成，而不是后端接口返回。

#### 请求构造

- 触发/计算 Handler：`SpeechWordCountHandler`
- RequestBuilder：`无 LLM RequestBuilder`
- Builder 数据注入：`无`
- 占位符：`无`，替换位置：`无`
- 构造方法：前端 hook 从 speechData.reportDetail 读取 speechSpeedPerSecond 和 speechWordCount；按学科选择 normal/english 配置，再遍历 ranges，以 speed > min && speed <= max 匹配本地化文案作为 aiSummary。
- 构造后输入示意：`statistics = 平均语速 + 讲授字数；aiSummary = ranges 命中的固定文案`
- 回调 Handler：`无 LLM回调 Handler`
- 保存结果结构：`后端仅保存 speechData 指标；AI文案不作为 LLM结果保存。`
- `AnalysisReportType`：`SPEECH_DATA`
- LLM任务：无。
- `dimension_id`：无。
- `t_prompt`：不查询。

前端构造伪代码：

```javascript
const data = speechData.reportDetail;
const speed = data?.speechSpeedPerSecond || 0;
const config = isEnglish ? speechConfig.english : speechConfig.normal;
const matched = config.ranges.find(({ range }) =>
  speed > range[0] && speed <= range[1]
);
const statistics = [speed, data?.speechWordCount || 0];
const aiSummary = matched ? i18n(matched.text) : i18n("common.no_data");
```

### 4.6 课堂流程重构（教师页）

#### 页面数据

- 输入接口：`courseProcessReengineering`
- AI结果接口：`courseProcessReengineeringExplain`
- 输入数据结构：`CourseProcessReengineeringResultVo { preClassToInClassLink, inClassToPostClassLink }；每个 Detail 包含 level 和 subTasks[{name,score,reason}]`
- 页面组合：页面分别请求原始课程流程重构结果和 AI解释，在同一素养课堂模块中组合等级、子任务和 aiSummary。

#### 请求构造

- 触发/计算 Handler：`CourseProcessReengineeringExplainPreHandler`
- RequestBuilder：`CourseProcessReengineeringExplainRequestBuilder`
- Builder 数据注入：`setCourseProcessReengineeringData(...)`
- 占位符：`10 个课程流程占位符`，替换位置：`system`
- 构造方法：buildForPrompt() 将课前到课中、课中到课后的等级，以及自主学习、资源提供、学情分析、课后任务的等级和原因替换进 system消息。
- 构造后输入示意：`#{preClassToInClassLinkLevel}、#{studentSelfStudyLevel}、#{studentSelfStudyReason}、#{offerStudyResourceLevel}、#{offerStudyResourceReason}、#{analysisStudentStudyLevel}、#{analysisStudentStudyReason}、#{inClassToPostClassLinkLevel}、#{assignPostClassTaskLevel}、#{assignPostClassTaskReason}`
- 回调 Handler：`CourseProcessReengineeringExplainHandler`
- 保存结果结构：`{ "text": "<LLM输出>" }`
- `AnalysisReportType`：`COURSE_PROCESS_REENGINEERING_EXPLAIN`
- LLM任务：`LLM_COURSE_PROCESS_REENGINEERING_EXPLAIN(59)`
- `dimension_id`：`7d9ad91c3d42453a8a9b4b3ac171fde6`
- 有效 Prompt 数：1

#### t_prompt 配置与 Prompt

##### Prompt 1

```json
{
  "uid": "7d9ad91c3d42453a8a9b4b3ac171fde6",
  "dimensionId": "7d9ad91c3d42453a8a9b4b3ac171fde6",
  "llmModel": "VOLC_DOUBAO_SEED_1_8",
  "maxToken": 32000,
  "temperature": null,
  "topP": null,
  "priority": null,
  "pretreatPipeLine": null,
  "extra": null
}
```

Prompt 内容：

```text
[{"role": "system", "content": "你的任务是生成一段不多于200字的文案，用于对教师教学的课堂流程重构度进行点评，该文案将呈现在一个课堂反馈系统软件的网页上。\n\n背景信息\n课堂流程重构度指课堂不再以教师讲授为主的传统模式进行，教师能根据课堂学习目标、教学需要、学生情况及课堂活动设计等对课堂流程进行重新设计和优化，关注课前与课中链接、课中重构和课中与课后链接，从而促进学生自主学习和深度学习更有效的发生、落实学生核心素养发展及推动课堂高阶化发展。\n流程重构度分为两个大维度四个等级，每个大维度由一个或多个子维度组成，每个子维度会提供分析原因。\n两个维度：课前与课中链接、课中与课后链接\n课前与课中链接的子维度：\n1. 学生完成自主学习\n2. 教师课前提供学习资源\n3. 教师分析学生学习数据\n课中与课后链接：\n1. 布置课后学习任务\n\n每个大维度都分为 4个等级：初阶、进阶、中阶、高阶（逐步提升）\n\n接下来，你将得到6个变量：\n1. <课前与课中链接等级：#{preClassToInClassLinkLevel}>\n2. <学生完成自主学习 子维度等级：#{studentSelfStudyLevel} 原因：#{studentSelfStudyReason}>\n3. <教师课前提供学习资源 子维度等级：#{offerStudyResourceLevel} 原因：#{offerStudyResourceReason}>\n4. <教师分析学生学习数据 子维度等级：#{analysisStudentStudyLevel} 原因：#{analysisStudentStudyReason}>\n5. <课中与课后链接等级：#{inClassToPostClassLinkLevel}>\n6. <布置课后学习任务 子维度等级：#{assignPostClassTaskLevel} 原因：#{assignPostClassTaskReason}>\n\n[提示]在撰写文案时，请首先参考上述提供的原因，可参考下方的思路：\n1. 整体逻辑部分：\n1.1 如果课前与课中链接等级为高阶，表述可以为“教师本节课根据课堂学习内容及学生学情对课堂流程进行了高水平的重构，学生学习贯穿课前、课中和课后，充分利用智能技术赋能教学，课堂上真实发生了以学生为中心、建构性、探究式的学习，助力学生核心素养发展，推动课堂高阶化发展。”\n1.2 如果课前与课中链接等级为中阶，表述可以为“教师本节课根据课堂学习内容及学生学情对课堂流程进行了良好重构，课堂中以学生为中心，有较好地应用智能技术赋能教学的意识，关注（课前与课中的链接）、（课中与课后的链接）【此处根据课堂实际情况进行选择，处于2/初步重构水平及以上的写，处于1/无重构的不写】，促进了学生自主学习，有助于培养和发展学生的核心素养。”\n1.3 如果课前与课中链接等级为进阶（初步重构），表述可以为“教师本节课有根据课堂学习内容及学生学情对课堂流程重新设计和优化的意识，关注（课前与课中的链接）、（课中与课后的链接）【此处根据课堂实际情况进行选择，如果你获得的两个变量其中有处于2/初步重构水平及以上的写，处于1/无重构的不写】，教师在课堂中注重引导、组织、促进学生学习本堂课的知识。”\n1.4 如果课前与课中链接等级为初阶（无重构），并且课中与课后链接等级也为初阶（无重构），表述可以为“教师本节课基本按照传统模式进行教学，希望教师能够根据课堂学习目标、教学需要、学生情况及课堂活动设计等对课堂流程进行重新设计和优化，以促进学生自主学习和深度学习，落实学生核心素养发展并推动课堂高阶化发展。”\n1.5 如果课前与课中链接等级为初阶（无重构），但课中与课后链接等级为进阶（初步重构）或更高等级，表述可以为“教师本节课基本按照传统模式进行课前与课中的教学，但在课中与课后链接方面有根据课堂学习内容、学习内容及学生学情对课堂流程重新设计和优化的意识，关注（课中与课后的链接），教师在课堂中注重引导、组织、促进学生学习本堂课的知识。”\n\n2. 具体例子展示部分（这部分请你从上述你获得的原因中分析）：\n2.1 从所评价的这节具体的课堂中的AI抓取的评价要点整理逻辑与语序后构成，主语应为教师，例如“教师在课前给学生布置了一定的预习作业，引导学生课前自主学习。”“教师课前提供了导学案或助学单等丰富的学习资源给学生，并布置了难度适中的课前学习任务。”等（可根据实际情况选择合适的例子）。\n\n3. 改进建议部分：\n3.1 换行展示\n3.2 根据该节课做得不好的地方，视情况放入1 - 2条，例如若课前准备不足，可以考虑“（课前提供学习资源）课前给学生准备微课视频、导学案或助学单等丰富的学习资源，为课堂上能更深入讨论和解决问题奠定基础。\n或在课前利用智能技术给学生提供差异化的学习资源，不同层次的学生根据自身情况合理获取相对应的学习资源，满足学生的个性化需求。”等（可根据实际情况选择合适的建议）。\n\n4. 输出格式限制：\n4.1 不要以markdown格式输出\n\n请按照上述要求生成文案。"}]
```

### 4.7 提问有效性（教师页）

#### 页面数据

- 输入接口：`questionRecord + questionAnswerExtraResult + bloom + teacherAppraisalClassification + solo；页面结果接口为 questionScoreExplain`
- AI结果接口：`questionScoreExplain`
- 输入数据结构：`QuestionScoreExplainPreHandler 汇总 BloomProblem、TeacherAppraisalClassifyResult、SoloAnswer、QuestionAnswerExtraResultVo，计算 Double questionScore`
- 页面组合：该维度的 score（LLM输入）和 text（LLM输出）保存在同一个 questionScoreExplain.reportDetail 中；页面另取问答相关接口展示提问总数和评价次数。

#### 请求构造

- 触发/计算 Handler：`QuestionScoreExplainPreHandler`
- RequestBuilder：`QuestionScoreExplainRequestBuilder`
- Builder 数据注入：`setQuestionScore(...)`
- 占位符：`#{questionScore}`，替换位置：`user`
- 构造方法：countQuestionScore() 计算 Bloom得分 + 教师评价得分 + SOLO得分的单题得分，再求平均并保留一位小数；buildForPrompt() 将分数写入 user消息。
- 构造后输入示意：`questionScore = 71.6`
- 回调 Handler：`QuestionScoreExplainHandler`
- 保存结果结构：`{ "score": 71.6, "text": "<LLM输出>" }`
- `AnalysisReportType`：`QUESTION_SCORE_EXPLAIN`
- LLM任务：`LLM_QUESTION_SCORE_EXPLAIN(61)`
- `dimension_id`：`26265f605f4344a380f3736d1e3026c8`
- 有效 Prompt 数：1

#### t_prompt 配置与 Prompt

##### Prompt 1

```json
{
  "uid": "26265f605f4344a380f3736d1e3026c8",
  "dimensionId": "26265f605f4344a380f3736d1e3026c8",
  "llmModel": "VOLC_DOUBAO_SEEK_1_6",
  "maxToken": 32000,
  "temperature": null,
  "topP": null,
  "priority": null,
  "pretreatPipeLine": null,
  "extra": null
}
```

Prompt 内容：

```text
[{"role": "system", "content": "你的任务是为教师教学的提问有效性生成一段不超过200字的点评文案，该文案将呈现在课堂反馈系统软件的网页上。\n\n你将得到本节课提问有效性的评价分数，分数范围是60-100分。\n\n下面是提问有效性的定义：\n课堂提问有效性是教学有效性的具体体现，该指标将从课堂言语入手，以教师提问、学生回答、教师理答三部分文本为主要分析内容，同时也详细记录教师提问方式、候答时间等教师行为信息，关注教师课堂提问是否连贯深入、是否能够引发学生深入思考，从而促进学生深度学习的有效发生，提高学生的学科核心素养。\n\n以下是各个分类标准及各水平的样例解释：\n\n1. 初阶水平——分数60-77分\n特点：纯讲授、问题提问均处于初阶水平，并没有通过学生回答生成新问题启发思考。\n解释参考：\n老师在课堂上展现出了良好的教学热情与责任心,问题设计具有连贯性，从单元主题到具体知识点逐步深入，确保学生对知识的逐步理解与掌握。注重引导学生思考，帮助学生构建基础的知识框架。对学生的回答给予了及时的反馈和引导。建议老师进一步丰富课堂高阶问题的提问，从学生回答出发，生成新问题，帮助学生培养高阶思维。同时教师对学生的回答仍是聚焦答案正确性和简单的复述，建议教师丰富对学生回答的评价方式，增加更多层次的肯定和指导，以更好地激发学生的学习积极性。\n\n2. 进阶水平——分数78-94分\n特点：问题初步具有问题链的特点，能够提出高阶问题，但仍然以初阶的重复方式进行理答。\n解释参考：\n老师在课堂上展现出了良好的教学能力，问题设计不仅具有系统性，还初步形成了问题链，能够引导学生从简单到复杂、从表面到深入地思考问题。然而，在理答方面，老师仍然较多地采用了初阶的重复方式，如简单确认学生的答案或对学生回答进行简单重述，未能充分利用学生的回答生成新的问题或进行更深层次的探讨。建议老师进一步提升理答的生成性，通过追问、反问等方式，引导学生深入思考，形成更加活跃和高效的课堂互动。\n\n3. 高阶水平——分数95-100分\n特点：高阶问题占比大，能够总结出课堂提问的鲜明问题链，理答方式具有生成性。\n解释参考：\n老师在课堂上展现出了卓越的教学智慧和教学机智，问题设计系统深入，而且形成了鲜明的问题链。\n-------\n下面是分数的计算标准，供你参考学习：\n有效性的分数是等于提问+理答+学生回答总和，再求其平均值\n‘’‘\n| 提问等级  | 分数 | 理答等级       | 分数 | 学生回答等级   | 分数 |\n|-----|----|----------|----|------|----|\n| 记忆型 | 25 | 无应答      | 15 | 无答   | 20 |\n| 理解型 | 31 | 简单的肯定/否定 | 21 | 前结构  | 21 |\n| 应用型 | 35 | 重述       | 25 | 单点结构 | 25 |\n| 分析型 | 38 | 单点建构     | 28 | 多点结构 | 28 |\n| 评价型 | 39 | 追问       | 29 | 关联结构 | 29 |\n| 创造型 | 40 | 多点建构     | 30 | 抽象拓展 | 30 |\n‘’‘\n------\n\n根据你得到的平均分数，判断其所属水平，然后参考对应水平的样例解释来生成点评文案。要确保文案简洁明了且不超过200字，使用三明治表达法。"}, {"role": "user", "content": "平均分数：#{questionScore}分"}]
```

## 5. 占位符替换与 LLM 请求构造完整实现

本章展示实际参与请求构造的完整方法。代码来自当前项目；为便于阅读，仅省略 import、构造器、Getter/Setter 等不参与构造的内容，不省略占位符替换、输入统计或请求装配逻辑。

### 5.1 从 t_prompt 查询并注入 Prompt

`AsyncCompletionHandler#setPromptList()` 收集 Builder 的 `dimensionId`，通过 `PromptService` 查询 `t_prompt`，再把查询结果转成 `LlmPromptRequestBuilder`：

```java
private void setPromptList(List<LlmRequestBuilder> requestBuilders) {
    Set<String> dimensionIds = requestBuilders.stream()
            .map(LlmRequestBuilder::getDimensionId)
            .collect(Collectors.toSet());
    PromptQuery promptQuery = new PromptQuery(new ArrayList<>(dimensionIds));
    Map<String, List<PromptVo>> dimensionIdMap =
            promptService.findByQueryGroupByDimensionId(promptQuery);
    requestBuilders.forEach(it -> {
        List<PromptVo> prompts = dimensionIdMap.get(it.getDimensionId());
        if (CollectionUtils.isEmpty(prompts)) {
            log.error("检测到维度缺失相关Prompt，维度ID：{}", it.getDimensionId());
        } else {
            it.setPromptRequestBuilders(it.promptRequestBuilders(prompts));
        }
    });
}
```

`PromptMapper.findByQuery` 的实际 SQL：

```xml
<select id="findByQuery" resultMap="ResultMap">
    SELECT
        uid, dimension_id, llm_model, prompt_text, max_token,
        temperature, top_p, priority, pretreat_pipeLine, extra
    FROM t_prompt
    WHERE dimension_id IN
        <foreach collection="query.dimensionIds"
                 item="dimensionId" open="(" separator="," close=")">
            #{dimensionId}
        </foreach>
      AND is_deleted = 0
    ORDER BY priority
</select>
```

`LlmRequestBuilder#promptRequestBuilders()` 完整保留每条 Prompt 的模型和采样配置：

```java
public List<LlmPromptRequestBuilder> promptRequestBuilders(List<PromptVo> promptVos) {
    return promptVos.stream()
            .map(it -> new LlmPromptRequestBuilder(
                    it.getUid(),
                    it.getLlmModel(),
                    it.getPromptText(),
                    it.getMaxToken(),
                    it.getTemperature(),
                    it.getTopP(),
                    it.getPretreatPipeLine(),
                    it.getExtra()))
            .collect(Collectors.toList());
}
```

### 5.2 最终 ChatCompletionRequestDto 装配

`LlmRequestBuilder#build()` 先通过 `frequencyStrategy()` 选择本次使用的 Prompt，再调用具体 Builder 的 `buildForPrompt()`：

```java
@SneakyThrows
public ChatCompletionRequestDto build() {
    LlmPromptRequestBuilder promptRequestBuilder = frequencyStrategy();
    ModelType modelType = promptRequestBuilder.getModelType(
            promptRequestBuilder.llmModel);
    return new ChatCompletionRequestDto()
            .setModel(modelType.name())
            .setUser(taskId)
            .setMessages(promptRequestBuilder.build(this))
            .setMax_tokens(promptRequestBuilder.getMaxToken())
            .setTemperature(promptRequestBuilder.getTemperature())
            .setTop_p(promptRequestBuilder.getTopP())
            .setExtra(promptRequestBuilder.extraOf(this))
            .setRes_size(1)
            .setTemperature(promptRequestBuilder.getTemperature())
            .setCallback(callBackUrl)
            .setDataId(taskId);
}

public LlmPromptRequestBuilder frequencyStrategy() {
    int index = Math.min((promptRequestBuilders.size() - 1), frequency);
    return promptRequestBuilders.get(index);
}

public boolean hasRetry() {
    frequency++;
    return frequency < MAX_FREQUENCY;
}
```

`LlmPromptRequestBuilder` 将替换后的 Prompt JSON 转成最终 `messages`，同时处理 `extra`：

```java
public List<ChatMessageDto> build(LlmRequestBuilder requestBuilder) {
    return com.alibaba.fastjson2.JSON.parseArray(
            requestBuilder.buildForPrompt(promptText),
            ChatMessageDto.class);
}

public Map<String, Object> extraOf(LlmRequestBuilder requestBuilder) {
    return Optional.ofNullable(extra)
            .map(it -> JSON.parseObject(
                    requestBuilder.buildForExtra(it),
                    new TypeReference<Map<String, Object>>() {}))
            .orElse(null);
}
```

最终提交发生在 `AsyncCompletionHandler#submitOpenAI()`：

```java
private void submitOpenAI(
        List<LlmRequestBuilder> requestBuilders,
        String virtualClassId,
        AbstractObservationChannel channel) {
    List<ChatCompletionRequestDto> chatCompletionRequests = requestBuilders
            .stream()
            .map(LlmRequestBuilder::build)
            .collect(Collectors.toList());
    ListUtils.partition(chatCompletionRequests, CHUNK_SIZE).forEach(list -> {
        try {
            aigcRemote.asyncCompletion(list, virtualClassId);
            return;
        } catch (Exception exception) {
            List<String> taskIds = requestBuilders.stream()
                    .map(LlmRequestBuilder::getTaskId)
                    .collect(Collectors.toList());
            log.error(
                    "提交OpenAI任务失败, 课程ID: " + virtualClassId
                            + "任务ID: [" + String.join(",", taskIds) + "]",
                    exception);
        }
        channel.fireUserEventTriggered(new AsyncCompletionRetryEvent(
                requestBuilders,
                AsyncCompletionRetryEvent.AsyncCompletionRetryType.DELAY_RETRY));
    });
}
```

### 5.3 学生互动数据：StudentStudyAnalysisRequestBuilder

数据注入：

```java
public StudentStudyAnalysisRequestBuilder setStudentStudyStatisticsVO(
        StudentStudyStatisticsVO studentStudyStatisticsVO) {
    this.studentStudyStatisticsVO = studentStudyStatisticsVO;
    return this;
}

public StudentStudyAnalysisRequestBuilder setStageName(String stageName) {
    this.stageName = stageName;
    return this;
}
```

完整占位符替换：仅遍历 `role=user` 的消息，将 `#{content}` 替换为 `buildContent()` 的结果。

```java
@Override
String buildForPrompt(String prompt) {
    JSONArray promptArray = JSON.parseArray(prompt);
    for (int i = 0; i < promptArray.size(); i++) {
        JSONObject promptJson = promptArray.getJSONObject(i);
        if ("user".equals(promptJson.get("role"))) {
            String newContent = promptJson.getString("content")
                    .replaceAll("#\\{content}", this.buildContent());
            promptJson.put("content", newContent);
        }
    }
    return promptArray.toJSONString();
}

private static final String TEMPLATE =
        "平均抬头率{0}%，平均举手率{1}%，平均参与度{2}%，{3}学段";

private String buildContent() {
    return MessageFormat.format(
            TEMPLATE,
            String.valueOf((int) (studentStudyStatisticsVO.getRaiseHeadRatio() * 100)),
            String.valueOf((int) (studentStudyStatisticsVO.getHandUpRatio() * 100)),
            String.valueOf((int) (studentStudyStatisticsVO.getAnswerRatio() * 100)),
            stageName);
}
```

字段映射：

| 占位符内容 | 来源 |
|---|---|
| 平均抬头率 | `raiseHeadRatio * 100` 后转 `int` |
| 平均举手率 | `handUpRatio * 100` 后转 `int` |
| 平均参与度 | `answerRatio * 100` 后转 `int` |
| 学段 | `StageSubjectHolder` 根据 `stageCode` 获取的 `stageName` |

### 5.4 学习行为分布：StudentBehaviorAnalysisRequestBuilder

数据注入：

```java
public StudentBehaviorAnalysisRequestBuilder setStudentBehaviorAnalysisVOs(
        List<StudentBehaviorAnalysisVO> studentBehaviorAnalysisVOs) {
    this.studentBehaviorAnalysisVOs = studentBehaviorAnalysisVOs;
    return this;
}
```

完整占位符替换和输入统计：

```java
@Override
String buildForPrompt(String prompt) {
    JSONArray promptArray = JSON.parseArray(prompt);
    for (int i = 0; i < promptArray.size(); i++) {
        JSONObject promptJson = promptArray.getJSONObject(i);
        if ("user".equals(promptJson.get("role"))) {
            String newContent = promptJson.getString("content")
                    .replaceAll("#\\{content}", this.buildContent());
            promptJson.put("content", newContent);
        }
    }
    return promptArray.toJSONString();
}

private static final String TEMPLATE =
        "知识留存率为{0}%；学生被动学习{1}%，主动学习{2}%；"
        + "其中被动学习中，听讲{3}%，阅读{4}%，视听{5}%，演示{6}%；"
        + "主动学习中讨论{7}%，实践{8}%，教给他人{9}%";

private String buildContent() {
    Map<StudentBehaviorType, AtomicLong> valueMap = new HashMap<>();
    for (StudentBehaviorAnalysisVO studentBehaviorAnalysisVO
            : studentBehaviorAnalysisVOs) {
        StudentBehaviorType type = StudentBehaviorType.codeOf(
                studentBehaviorAnalysisVO.getBehaviorType());
        valueMap.computeIfAbsent(type, key -> new AtomicLong(0L))
                .addAndGet(studentBehaviorAnalysisVO.getDurationTimeMills());
    }

    AtomicLong listenDuration = valueMap.getOrDefault(
            StudentBehaviorType.LISTEN, new AtomicLong(0));
    AtomicLong readDuration = valueMap.getOrDefault(
            StudentBehaviorType.READ, new AtomicLong(0));
    AtomicLong visualDuration = valueMap.getOrDefault(
            StudentBehaviorType.VISUAL, new AtomicLong(0));
    AtomicLong demonstrationDuration = valueMap.getOrDefault(
            StudentBehaviorType.DEMONSTRATION, new AtomicLong(0));
    AtomicLong discussDuration = valueMap.getOrDefault(
            StudentBehaviorType.DISCUSS, new AtomicLong(0));
    AtomicLong practiceDuration = valueMap.getOrDefault(
            StudentBehaviorType.PRACTICE, new AtomicLong(0));
    AtomicLong teachOtherDuration = valueMap.getOrDefault(
            StudentBehaviorType.TEACH_OTHER, new AtomicLong(0));

    long passive = listenDuration.get()
            + readDuration.get()
            + visualDuration.get()
            + demonstrationDuration.get();
    long active = discussDuration.get()
            + practiceDuration.get()
            + teachOtherDuration.get();
    long total = active + passive;

    double listen = getCount(listenDuration, total);
    double read = getCount(readDuration, total);
    double visual = getCount(visualDuration, total);
    double demonstration = getCount(demonstrationDuration, total);
    double discuss = getCount(discussDuration, total);
    double practice = getCount(practiceDuration, total);
    double teachOther = getCount(teachOtherDuration, total);

    avgKnowledgeRetentionRate = listen * 0.05
            + read * 0.1
            + visual * 0.2
            + demonstration * 0.3
            + discuss * 0.5
            + practice * 0.75
            + teachOther * 0.9;

    return MessageFormat.format(
            TEMPLATE,
            avgKnowledgeRetentionRate,
            getCount(passive, total),
            getCount(active, total),
            listen,
            read,
            visual,
            demonstration,
            discuss,
            practice,
            teachOther);
}

private double getCount(long value, long total) {
    if (total == 0) {
        return 0;
    }
    return BigDecimal.valueOf(value)
            .divide(BigDecimal.valueOf(total), 2, RoundingMode.HALF_UP)
            .multiply(new BigDecimal("100"))
            .doubleValue();
}

private double getCount(AtomicLong value, long total) {
    if (total == 0) {
        return 0;
    }
    return BigDecimal.valueOf(value.get())
            .divide(BigDecimal.valueOf(total), 2, RoundingMode.HALF_UP)
            .multiply(new BigDecimal("100"))
            .doubleValue();
}
```

行为归类：

| 聚合项 | 行为类型 |
|---|---|
| 被动学习 | `LISTEN + READ + VISUAL + DEMONSTRATION` |
| 主动学习 | `DISCUSS + PRACTICE + TEACH_OTHER` |
| 知识留存率 | 听讲×5% + 阅读×10% + 视听×20% + 演示×30% + 讨论×50% + 实践×75% + 教给他人×90% |

### 5.5 回答建构分类：SoloQuestionAnswerExplainRequestBuilder

完整数据注入、计数和替换：

```java
public SoloQuestionAnswerExplainRequestBuilder soloAnswerList(
        List<SoloAnswer> soloAnswerList) {
    this.soloAnswerList = soloAnswerList;
    return this;
}

private static final String CONTENT_FORMAT = "%s 的回答占比：%s";

@Override
String buildForPrompt(String prompt) {
    return prompt.replace("#{content}", buildUserContent());
}

private String buildUserContent() {
    Map<SoloAnswerType, Integer> typeCountMap =
            new EnumMap<>(SoloAnswerType.class);
    if (CollectionUtils.isNotEmpty(soloAnswerList)) {
        for (SoloAnswer soloAnswer : soloAnswerList) {
            int count = typeCountMap.getOrDefault(
                    soloAnswer.getSoloAnswerType(), 0) + 1;
            typeCountMap.put(soloAnswer.getSoloAnswerType(), count);
        }
    }

    int total = CollectionUtils.isEmpty(soloAnswerList)
            ? 0 : soloAnswerList.size();

    StringBuilder builder = new StringBuilder();
    for (SoloAnswerType soloAnswerType : SoloAnswerType.values()) {
        int count = typeCountMap.getOrDefault(soloAnswerType, 0);
        float rate = total == 0 ? 0 : count * 1.0f / total;
        builder.append(String.format(
                        CONTENT_FORMAT,
                        soloAnswerType.getDesc(),
                        String.format("%.2f", rate)))
                .append("\n");
    }
    return builder.toString();
}
```

这里不是只修改 `role=user`：它直接对完整 Prompt JSON字符串执行一次 `replace("#{content}", ...)`。每种 `SoloAnswerType` 即使计数为 0，也会输出一行，占比保留两位小数且范围为 0～1。

### 5.6 应答时间：StudentAnswerTimeAnalysisRequestBuilder

完整数据注入、分桶和替换：

```java
public StudentAnswerTimeAnalysisRequestBuilder setStudentAnswerClassifications(
        List<StudentAnswerClassifyResult> studentAnswerClassifications) {
    this.studentAnswerClassifications = studentAnswerClassifications;
    return this;
}

@Override
String buildForPrompt(String prompt) {
    JSONArray promptArray = JSON.parseArray(prompt);
    for (int i = 0; i < promptArray.size(); i++) {
        JSONObject promptJson = promptArray.getJSONObject(i);
        if ("user".equals(promptJson.get("role"))) {
            String newContent = promptJson.getString("content")
                    .replaceAll("#\\{content}", this.buildContent());
            promptJson.put("content", newContent);
        }
    }
    return promptArray.toJSONString();
}

private static final String TEMPLATE =
        "应答5秒以内{0}%，应答5-15秒{1}%，应答15秒以上{2}%";

private String buildContent() {
    int in5second = 0;
    int between5to115second = 0;
    int betterThan15second = 0;
    for (StudentAnswerClassifyResult result : studentAnswerClassifications) {
        long time = (result.getEndTime() - result.getStartTime()) / 1000;
        if (time <= 5) {
            in5second++;
        } else if (time <= 15) {
            between5to115second++;
        } else {
            betterThan15second++;
        }
    }
    int studentAnswerTotalNum = in5second
            + between5to115second
            + betterThan15second;
    double in5secondProportion =
            in5second * 100.0 / studentAnswerTotalNum;
    double between5to115secondProportion =
            between5to115second * 100.0 / studentAnswerTotalNum;
    double betterThan15secondProportion =
            betterThan15second * 100.0 / studentAnswerTotalNum;
    return TEMPLATE
            .replace("{0}", String.valueOf(in5secondProportion))
            .replace("{1}", String.valueOf(between5to115secondProportion))
            .replace("{2}", String.valueOf(betterThan15secondProportion));
}
```

边界规则完整如下：`time <= 5`、`5 < time <= 15`、`time > 15`。`time` 由毫秒差除以 1000 得到整数秒。

### 5.7 课堂流程重构：CourseProcessReengineeringExplainRequestBuilder

数据注入：

```java
public CourseProcessReengineeringExplainRequestBuilder
        setCourseProcessReengineeringData(
                CourseProcessReengineeringResultVo result) {
    this.courseProcessReengineeringResult = result;
    return this;
}
```

完整占位符替换：只修改 `role=system` 的消息，共替换 10 个占位符。

```java
@Override
String buildForPrompt(String prompt) {
    JSONArray promptArray = JSON.parseArray(prompt);
    for (int i = 0; i < promptArray.size(); i++) {
        JSONObject promptJson = promptArray.getJSONObject(i);
        if ("system".equals(promptJson.get("role"))) {
            Map<String, Pair<String, String>> subTaskMap = getSubTaskMap();
            String newContent = promptJson.getString("content")
                    .replace(
                            "#{preClassToInClassLinkLevel}",
                            CourseProcessReengineeringEvaluationLevelEnum
                                    .getEnumByName(courseProcessReengineeringResult
                                            .getPreClassToInClassLink().getLevel())
                                    .getDesc())
                    .replace(
                            "#{studentSelfStudyLevel}",
                            subTaskMap.get(CourseProcessReengineeringEnum
                                    .STUDENT_SELF_STUDY.getName()).getKey())
                    .replace(
                            "#{studentSelfStudyReason}",
                            subTaskMap.get(CourseProcessReengineeringEnum
                                    .STUDENT_SELF_STUDY.getName()).getValue())
                    .replace(
                            "#{offerStudyResourceLevel}",
                            subTaskMap.get(CourseProcessReengineeringEnum
                                    .OFFER_STUDY_RESOURCE.getName()).getKey())
                    .replace(
                            "#{offerStudyResourceReason}",
                            subTaskMap.get(CourseProcessReengineeringEnum
                                    .OFFER_STUDY_RESOURCE.getName()).getValue())
                    .replace(
                            "#{analysisStudentStudyLevel}",
                            subTaskMap.get(CourseProcessReengineeringEnum
                                    .ANALYSIS_STUDENT_STUDY.getName()).getKey())
                    .replace(
                            "#{analysisStudentStudyReason}",
                            subTaskMap.get(CourseProcessReengineeringEnum
                                    .ANALYSIS_STUDENT_STUDY.getName()).getValue())
                    .replace(
                            "#{inClassToPostClassLinkLevel}",
                            CourseProcessReengineeringEvaluationLevelEnum
                                    .getEnumByName(courseProcessReengineeringResult
                                            .getInClassToPostClassLink().getLevel())
                                    .getDesc())
                    .replace(
                            "#{assignPostClassTaskLevel}",
                            subTaskMap.get(CourseProcessReengineeringEnum
                                    .ASSIGN_POST_CLASS_TASK.getName()).getKey())
                    .replace(
                            "#{assignPostClassTaskReason}",
                            subTaskMap.get(CourseProcessReengineeringEnum
                                    .ASSIGN_POST_CLASS_TASK.getName()).getValue());
            promptJson.put("content", newContent);
        }
        log.info(
                "[COURSE PROCESS REENGINEERING] "
                        + "课程流程重构解释请求参数替换, "
                        + "taskId: {}, virtualClassId: {}, prompt: {}",
                taskId,
                virtualClassId,
                promptJson.toJSONString());
    }
    return promptArray.toJSONString();
}

private Map<String, Pair<String, String>> getSubTaskMap() {
    Map<String, Pair<String, String>> result = new HashMap<>();
    populateSubTaskMap(
            result,
            courseProcessReengineeringResult.getPreClassToInClassLink());
    populateSubTaskMap(
            result,
            courseProcessReengineeringResult.getInClassToPostClassLink());
    return result;
}

private void populateSubTaskMap(
        Map<String, Pair<String, String>> result,
        CourseProcessReengineeringDetailVo detail) {
    for (CourseProcessReengineeringSubTaskVo subTask : detail.getSubTasks()) {
        CourseProcessReengineeringEnum type =
                CourseProcessReengineeringEnum.getEnumByName(subTask.getName());
        if (Objects.nonNull(type)) {
            result.put(
                    type.getName(),
                    new Pair<>(
                            CourseProcessReengineeringScoreEnum
                                    .getEnumByName(subTask.getScore()).getDesc(),
                            subTask.getReason()));
        } else {
            log.error(
                    "[COURSE PROCESS REENGINEERING] "
                            + "课程流程重构子任务名称不匹配, "
                            + "name: {}, taskId: {}, virtualClassId: {}",
                    subTask.getName(),
                    taskId,
                    virtualClassId);
        }
    }
}
```

10 个占位符的来源：

| 占位符 | 来源 |
|---|---|
| `#{preClassToInClassLinkLevel}` | `preClassToInClassLink.level` 转评价等级描述 |
| `#{studentSelfStudyLevel}` | “学生自主学习”子任务 `score` 转描述 |
| `#{studentSelfStudyReason}` | “学生自主学习”子任务 `reason` |
| `#{offerStudyResourceLevel}` | “提供学习资源”子任务 `score` 转描述 |
| `#{offerStudyResourceReason}` | “提供学习资源”子任务 `reason` |
| `#{analysisStudentStudyLevel}` | “分析学生学情”子任务 `score` 转描述 |
| `#{analysisStudentStudyReason}` | “分析学生学情”子任务 `reason` |
| `#{inClassToPostClassLinkLevel}` | `inClassToPostClassLink.level` 转评价等级描述 |
| `#{assignPostClassTaskLevel}` | “布置课后任务”子任务 `score` 转描述 |
| `#{assignPostClassTaskReason}` | “布置课后任务”子任务 `reason` |

### 5.8 提问有效性：QuestionScoreExplainRequestBuilder

占位符值不是页面传入，而是 `QuestionScoreExplainPreHandler` 先计算得到。完整聚合方法：

```java
public Double countQuestionScore(String virtualClassUid) {
    List<BloomProblem> bloomProblemList = analysisResultService
            .getAnalysisResults(
                    virtualClassUid,
                    AnalysisReportType.BLOOM,
                    BloomProblem.class);
    List<TeacherAppraisalClassifyResult> appraisalList = analysisResultService
            .getAnalysisResults(
                    virtualClassUid,
                    AnalysisReportType.TEACHER_APPRAISAL_CLASSIFY,
                    TeacherAppraisalClassifyResult.class);
    List<SoloAnswer> soloAnswerList = analysisResultService
            .getAnalysisResults(
                    virtualClassUid,
                    AnalysisReportType.SOLO,
                    SoloAnswer.class);
    List<QuestionAnswerExtraResultVo> extraResultList = analysisResultService
            .getAnalysisResults(
                    virtualClassUid,
                    AnalysisReportType.QUESTION_ANSWER_EXTRA_RESULT,
                    QuestionAnswerExtraResultVo.class);

    Map<String, TeacherAppraisalType> sentenceIdToAppraisalTypeMap =
            new HashMap<>();
    appraisalList.forEach(result -> sentenceIdToAppraisalTypeMap.put(
            result.getSentenceId(), result.getTeacherAppraisalType()));

    Map<String, SoloAnswerType> sentenceIdToSoloTypeMap = new HashMap<>();
    soloAnswerList.forEach(answer -> sentenceIdToSoloTypeMap.put(
            answer.getAnswerSentenceId(), answer.getSoloAnswerType()));

    Map<String, QuestionRecordItemVo> questionRecordItemMap = new HashMap<>();
    extraResultList.forEach(extra -> extra.getQuestionRecordItemVoList()
            .forEach(item -> questionRecordItemMap.put(
                    item.getQuestionSentence().getSentenceId(), item)));

    double totalScore = bloomProblemList.stream()
            .mapToDouble(problem -> countSingleQuestionScoreByList(
                    problem,
                    questionRecordItemMap,
                    sentenceIdToAppraisalTypeMap,
                    sentenceIdToSoloTypeMap))
            .sum();

    int size = bloomProblemList.size();
    double result = 0;
    if (size != 0) {
        BigDecimal roundedValue = BigDecimal.valueOf(totalScore / size)
                .setScale(1, RoundingMode.HALF_UP);
        result = roundedValue.doubleValue();
        log.info(
                "[COUNT QUESTION SCORE] virtualClassUid: {}, "
                        + "question score is : {}",
                virtualClassUid,
                result);
    }
    return result;
}

private double countSingleQuestionScoreByList(
        BloomProblem bloomProblem,
        Map<String, QuestionRecordItemVo> questionRecordItemMap,
        Map<String, TeacherAppraisalType> appraisalTypeMap,
        Map<String, SoloAnswerType> soloTypeMap) {
    double bloomScore = QuestionsValidity.getBloomScore(
            bloomProblem.getProblemType());
    double appraisalScore = 15;
    QuestionRecordItemVo questionRecordItemVo =
            questionRecordItemMap.get(bloomProblem.getProblemId());
    if (questionRecordItemVo != null
            && !questionRecordItemVo.getAppraisalSentences().isEmpty()) {
        appraisalScore = questionRecordItemVo.getAppraisalSentences().stream()
                .mapToDouble(appraisal -> QuestionsValidity.getAppraisalScore(
                        appraisalTypeMap.get(appraisal.getSentenceId())))
                .sum()
                / questionRecordItemVo.getAppraisalSentences().size();
    }

    double soloScore = 20;
    long soloSize = questionRecordItemVo.getAnswerSentences().stream()
            .filter(Objects::nonNull)
            .count();
    if (questionRecordItemVo != null
            && !questionRecordItemVo.getAnswerSentences().isEmpty()
            && soloSize > 0) {
        soloScore = questionRecordItemVo.getAnswerSentences().stream()
                .filter(Objects::nonNull)
                .mapToDouble(answer -> QuestionsValidity.getSoloScore(
                        soloTypeMap.get(answer.getSentenceId())))
                .sum()
                / soloSize;
    }
    return bloomScore + appraisalScore + soloScore;
}
```

计算完成后注入 Builder，并完整替换 `role=user` 消息中的 `#{questionScore}`：

```java
public QuestionScoreExplainRequestBuilder setQuestionScore(
        Double questionScore) {
    this.questionScore = questionScore;
    return this;
}

@Override
String buildForPrompt(String prompt) {
    JSONArray promptArray = JSON.parseArray(prompt);
    for (int i = 0; i < promptArray.size(); i++) {
        JSONObject promptJson = promptArray.getJSONObject(i);
        if ("user".equals(promptJson.get("role"))) {
            String newContent = promptJson.getString("content")
                    .replace(
                            "#{questionScore}",
                            this.questionScore.toString());
            promptJson.put("content", newContent);
        }
    }
    return promptArray.toJSONString();
}
```

完整公式为：

```text
单题得分 = Bloom 得分 + 教师评价平均得分 + SOLO 回答平均得分
课堂提问有效性 = 所有 Bloom 问题单题得分之和 / Bloom 问题数
最终结果 = HALF_UP 保留 1 位小数
```

默认值：没有教师评价时 `appraisalScore=15`；没有有效 SOLO回答时 `soloScore=20`；没有 Bloom问题时课堂得分为 `0`。

### 5.9 讲授分析：非 LLM 前端规则完整等价实现

该模块没有 Prompt、占位符或 `RequestBuilder`。后端 `SpeechWordCountHandler` 只保存主讲人的讲话字数和讲话时长：

```java
protected void userEventTriggered0(
        ChannelHandlerContext ctx,
        AbstractObservationChannel channel,
        Object event) throws Exception {
    CourseTaskEvent taskEvent = (CourseTaskEvent) event;
    AudioAnalysisResultDto audioResult =
            (AudioAnalysisResultDto) taskEvent.getTaskResult();

    long wordCountTotal = 0L;
    long speakTotalTimeSec = 0L;
    for (Map.Entry<String, SpeakerInfoDto> entry
            : audioResult.getSpeakers().entrySet()) {
        SpeakerInfoDto speaker = entry.getValue();
        if (speaker.getRole().equals(SpeakerRoleType.MAJOR.getRole())) {
            wordCountTotal += speaker.getTextLength();
            speakTotalTimeSec += speaker.getDuration();
        }
    }

    TeacherSpeakDataVo data = new TeacherSpeakDataVo();
    data.setSpeechWordCount(wordCountTotal);
    data.setSpeechDurationInSeconds(speakTotalTimeSec);
    analysisResultService.saveOrUpdateAnalysisResult(
            channel.courseInfoVo().getVirtualClassUid(),
            data,
            AnalysisReportType.SPEECH_DATA);
}
```

前端从 `speechData.reportDetail` 计算展示数据和 `aiSummary`。下面是对当前压缩前端实现的完整可读等价展开：

```javascript
function buildLectureAnalysis({
  speechWordCount,
  speechSpeedPerSecond,
  isEnglish,
  translate,
  localLang,
}) {
  const displaySpeed = isEnglish
    ? speechSpeedPerSecond * 60
    : speechSpeedPerSecond;
  const config = isEnglish ? speechConfig.english : speechConfig.normal;
  const speedValue = formatNumber(displaySpeed, {
    localLang,
    maximumFractionDigits: 2,
  });
  const wordCountValue = formatNumber(speechWordCount, {
    localLang,
    maximumFractionDigits: 2,
  });
  const empty = !displaySpeed && !speechWordCount;

  const statistics = [
    {
      count: speedValue.num,
      unit: speedValue.unit + translate(config.fullUnit),
      desc: translate("teacher.average_speaking_rate"),
      empty,
    },
    {
      count: wordCountValue.num,
      unit: wordCountValue.unit + translate(config.unit),
      desc: translate("teacher.lecture_word_count"),
      empty,
    },
  ];

  let content = translate("common.no_data");
  const summaryEmpty = !displaySpeed;
  if (!summaryEmpty) {
    for (const { range, text } of config.ranges) {
      if (displaySpeed > range[0] && displaySpeed <= range[1]) {
        content = translate(text);
        break;
      }
    }
  }

  return {
    statistics,
    aiSummary: {
      content,
      empty: summaryEmpty,
    },
  };
}
```

关键边界条件是左开右闭：`displaySpeed > range[0] && displaySpeed <= range[1]`。英语学科先把每秒语速乘以 60，再使用英语配置区间；其他学科直接使用每秒语速和普通配置区间。

## 6. 结果数据结构

6 个 LLM维度的解释结果查询最终使用 `DataExplainDto`：

```java
class DataExplainDto {
    BigDecimal score;
    String text;
}
```

- 学生互动、学习行为、回答建构、应答时间、课堂流程重构：实际保存 `{ "text": "..." }`，`score` 为空。
- 提问有效性：在调用 LLM前先保存 `{ "score": <计算值>, "text": "" }`，回调后只更新 `text`，所以输入分数和 LLM输出同处一个 `reportDetail`。
- 讲授分析：`speechData.reportDetail` 只保存字数、语速、时长；AI文案在前端计算，不写回分析结果。

## 7. 完整性结论

- 页面模块数：7。
- 实际 LLM维度数：6。
- 从 `t_prompt` 查询并保留的有效 Prompt 数：7。
- S-T/Rt-Ch 数据解读不是当前 7 个可见模块之一，已从本文移除。
- 课堂流程重构内部计算子维度未纳入。
- 文档未查询或使用 `t_appraisal_dimension_v2`。
