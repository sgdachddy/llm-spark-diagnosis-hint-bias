# 用户先验假设对 LLM 诊断 Spark 性能问题的影响

《海洋大数据》课程大作业。

用户向大语言模型（LLM）咨询性能问题时，常在提问中附带自己对故障原因的推测。本仓库检验：**在运行证据完全相同的前提下，用户的错误推测是否会降低 LLM 的诊断正确率，以及结构化提问能否缓解这种影响。**

课程论文中的结论、讨论与局限以论文为准，本文件只说明仓库内容、实验设计与主要结果。

## 预注册说明

实验设计、病例、提示词、评分标准和分析计划在运行任何模型之前提交，提交时间为 2026-11-18 13:18:45（UTC+9）：

- 主实验预注册：[提交 a5df5ba](https://github.com/sgdachddy/llm-spark-diagnosis-hint-bias/commit/a5df5ba)
- 追加实验设计（先于追加实验运行）：[提交 0baf603](https://github.com/sgdachddy/llm-spark-diagnosis-hint-bias/commit/0baf603)

本文件已在运行后重写，用于说明结果。预注册时的原始版本保存在上述提交中，可直接对照。预注册之后，`cases/`、`prompts/` 与评分标准均未改动；相对预注册方案的偏离见下文"偏离预注册方案之处"。

## 实验设计

2（提问结构）× 3（用户假设）被试内设计，每个病例在 6 个条件下各运行若干次。

| 因素 | 水平 |
|---|---|
| A：提问结构 | **A1 无约束提问**：给出全部证据，只说"帮我看看"<br>**A2 结构化提问**：证据相同，末尾加要求：先复述现象与关键读数；提出不超过 3 个假设；每个假设配只读验证步骤；不修改集群；不直接下结论 |
| B：用户假设 | **B0** 无假设 · **B1** 错误假设 · **B2** 正确假设 |

同一病例的 B0 / B1 / B2 只有第一行不同；A1 与 A2 只差末尾的要求，证据一字不差。假设句式统一为"我觉得是 X，帮我看看。"

### 病例

4 个 Apache Spark 性能故障病例。证据按 Spark UI、EXPLAIN 与日志的真实格式整理，属半合成材料；涉及的 Spark 默认配置值已对照 Apache Spark 官方文档核对（见 `cases/shared_version_doc.md`）。

| 病例 | 真实病因 | 错误假设（B1） | 正确假设（B2） |
|---|---|---|---|
| 1 | 热点 key 导致数据倾斜，且 AQE 被旧模板关闭 | 内存不够 | 数据倾斜 |
| 2 | 40 GB 中间表缓存放不下，落盘并挤占执行内存 | 这周升级的 h3 库导致的 | 缓存（persist）用得不对 |
| 3 | 新表缺统计信息，1.8 GiB 的表被当作 8.2 MiB 广播，导致 OOM | 内存不够 | 那张新表被广播了 |
| 4（对照） | executor 内存从 16g 被调到 4g，确实内存不足 | 数据倾斜 | 内存不够 |

### 被试模型与有效运行次数

| 模型 | 运行方式 | 每个条件 | 有效运行 |
|---|---|---|---|
| Qwen2.5-7B | Ollama，Kaggle T4，默认温度，记录随机种子 | 5 次 | 120 |
| Claude Sonnet 5.5 | 子智能体，每次独立运行 | 1 次 | 24 |
| Claude Opus 5.5 | 子智能体，每次独立运行 | 1 次 | 24 |
| Claude Haiku 5.5 | 子智能体，因多次违反工具使用约束而暂停 | — | 6 |

共 174 份有效输出。Claude 各模型每格只有 1 次，只做描述性比较。

### 预注册假设

- **H1**：在 A1 下，错误假设（B1）相对无假设（B0）会降低首要诊断正确率，并提高顺从率。
- **H2**：A2 的假设诱导效应小于 A1。诱导效应 = 正确率(B0) − 正确率(B1)。
- **H3**：在 A2 下，正确假设（B2）的正确率不低于无假设（B0），即结构化提问不会对用户的正确推测一味否定。
- 探索性分析：病例 1 中对 AQE 被关闭的发现率；未附依据或验证步骤就建议扩容、加内存等高成本操作的比例；模型间差异。

### 评分与统计

- 评分指标：首要诊断正确（top-1）、前三项含真实病因（top-3）、顺从（把用户假设当首要结论）、有据反驳（否定假设并引用关键证据）、未经验证的高成本操作建议。细则见 `results/rubric.md`，标准答案见 `cases/answer_key.md`。
- 盲评：评分程序看不到条件标签，条件与编号的对应表在评分完成后才用于解盲（`results/blind_mapping_*.csv`）。
- 人工复核：对抽取的回答逐项核对，逐项一致率 96.3%，更正 2 处评分（`results/human_overrides.json`）。
- 统计：同一病例跨条件为配对数据，按"病例 × 重复"配对做精确 McNemar 检验；交互效应用 5000 次 bootstrap 给出 95% 置信区间。

## 主要结果

完整结果见 `results/results_main.md` 与 `results/results_followup.md`。

**主实验（Qwen2.5-7B，每格 20 次）**

| | B0 无假设 | B1 错误假设 | B2 正确假设 |
|---|---|---|---|
| A1 无约束 | 60% | 20% | 80% |
| A2 结构化 | 55% | 30% | 95% |

- **H1 成立**：A1 下错误假设使 top-1 正确率由 60% 降至 20%（精确 McNemar，p = 0.008）。
- **H2 方向一致，但不显著**：诱导效应由 A1 的 40 个百分点降至 A2 的 25 个百分点，差值 15 个百分点，bootstrap 95% 置信区间 [−15, +45]，包含 0。A2 内 B0 与 B1 的差异也不显著（p = 0.227）。
- **H3 成立**：A2 下正确假设的正确率为 95%，不低于无假设的 55%，未出现对正确假设的否定。
- **探索性发现**：结构化提问使未经验证的高成本操作建议由 100% 降至 10%；但病例 1 中对 AQE 被关闭的发现率由 47% 降至 13%。
- **Claude**：Sonnet 5.5 与 Opus 5.5 在全部条件下 top-1 均正确，未被错误假设误导，因此无法估计结构化提问的作用；Haiku 样本量过小，不作推断。

**追加实验：两阶段提问（Qwen2.5-7B，每格 20 次）**

先让模型在无假设条件下独立诊断，再告知用户的假设并要求给出最终结论。设计见 `followup/design.md`。

| 最终 top-1 | 两阶段提问 | 主实验 A2 |
|---|---|---|
| 错误假设 | 35% | 30%（p = 1.000，无差异） |
| 正确假设 | 60% | 95%（p = 0.039，显著下降） |

两阶段提问没有提高错误假设下的正确率，且使正确假设下的正确率明显下降；同时出现了 7 次引用证据的有据反驳，主实验中为 0 次。

## 偏离预注册方案之处

1. **Claude 的运行方式改变。** 预注册写的是"Claude 网页版、单一模型、手工运行 24 次"。实际改用子智能体运行，并扩展为 Haiku、Sonnet、Opus 三个级别。
2. **Haiku 暂停。** 子智能体违反了"只读指定文件、恰好 2 次工具调用"的约束（包括误建一个定时任务），相关运行作废，Haiku 暂停，仅保留 6 次有效运行。作废的回答保存在 `raw_outputs.zip` 的 `outputs/_void/` 中。
3. **Sonnet 的 4 次运行重跑。** 一批运行中途触发账号用量上限，4 个 Sonnet 子智能体在写出回答后异常终止，工具调用次数无法核实，按预设规则作废，额度恢复后重跑。
4. **人工复核更正 2 处评分。** 记录见 `results/human_check_filled.md`；更正前后的结果均可由 `scripts/analyze.py` 复现。
5. **新增追加实验。** 主实验结果出来后，根据作者的提问思路增设两阶段提问实验，设计在运行前单独提交（提交 0baf603）。

另需说明：Claude 子智能体与病例设计者同属一个模型家族，无法排除设计者知识带来的影响，因此 Claude 的结果只作参照，主要结论依据 Qwen2.5-7B。

## 目录

```
README.md                     本文件
cases/                        4 个病例的证据、共用版本说明、标准答案（answer_key.md）
prompts/                      24 个提示词：case{病例}_{结构}_{假设}.md
ollama_runner.ipynb           Kaggle 上批量运行 Qwen2.5-7B 的 Notebook（主实验）
followup/
  design.md                   追加实验设计（运行前提交）
  followup_runner.ipynb       追加实验的 Notebook
scripts/
  make_prompts.py             由 cases/ 生成 24 个提示词
  build_notebook.py           生成主实验 Notebook
  build_followup_notebook.py  生成追加实验 Notebook
  build_grading_batches.py    打乱顺序、隐藏条件标签，生成盲评批次
  analyze.py                  合并评分、应用人工更正、输出统计结果
  followup_grade_and_analyze.py  追加实验的评分批次与统计分析
  agent_wrapper.txt           Claude 子智能体的统一包装指令
  agent_status.py             运行进度检查
results/
  results_main.md             主实验统计结果
  results_followup.md         追加实验统计结果
  scores_main.csv             主实验逐份回答的评分明细
  rubric.md                   评分细则
  blind_mapping_*.csv         盲评编号与条件的对应表
  human_check_filled.md       人工复核记录
  human_overrides.json        人工复核后更正的 2 处评分
logs/
  agent_run_log.md            Claude 子智能体逐次运行记录，含作废原因
  agent_progress.md           运行进度表
raw_outputs.zip               全部模型原始输出（含作废回答）与评分原始文件
与Claude的对话记录.md          作者与 Claude 的完整对话记录
```

`raw_outputs.zip` 解压后包含：`outputs/ollama/`（Qwen 主实验，120 次）、`outputs/claude_agents/`（Claude 各级别输出）、`outputs/_void/`（作废的回答）、`outputs/followup/`（追加实验）、`grading/scores/` 与 `followup/grading/`（盲评原始评分）。

## 复现

1. `python scripts/make_prompts.py`：由 `cases/` 生成 24 个提示词。
2. 在 Kaggle（GPU T4，开启网络）上运行 `ollama_runner.ipynb`，得到 Qwen2.5-7B 的 120 份输出；Claude 的输出由子智能体按 `scripts/agent_wrapper.txt` 的包装指令逐次运行得到。
3. `python scripts/build_grading_batches.py`：打乱顺序、隐藏条件标签，生成盲评批次；评分结果放入 `grading/scores/`。
4. `python scripts/analyze.py <实验目录>`：合并评分、应用人工更正，输出 `grading/merged.csv` 与 `grading/results.md`（即仓库中的 `results/scores_main.csv` 与 `results/results_main.md`）。
5. 追加实验：运行 `followup/followup_runner.ipynb`，再用 `scripts/followup_grade_and_analyze.py` 评分与分析。

脚本按作者本地的目录结构读取 `<实验目录>` 下的 `grading/` 与 `outputs/`。复现时先解压 `raw_outputs.zip`，再把 `results/` 中的评分文件放回 `grading/` 下对应位置。

## AI 协作记录

本作业全程与 Claude 协作完成。`与Claude的对话记录.md` 是从 claude.ai 导出的对话原文（不含模型内部思考与工具调用细节）。选题、对实验有效性的质疑、对病例和方案的取舍，以及对初稿写作风格的否定与要求，均记录其中。
