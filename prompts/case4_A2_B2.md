我的 Spark 作业出了问题，我觉得是内存不够，帮我看看。下面是相关材料。

【现象】
作业 ais_track_segments 本周明显变慢：以前约 20 min，本周约 58 min，偶尔有 executor 被 YARN 杀掉后重跑。
作业内容：按船舶 mmsi 分组，对每条船当天的轨迹点排序并切分航段。
集群：16 个 executor，每个 4 核。
最近改动（本周）：
- 运维为节省成本，把课题组默认模板里的 executor 内存从 16g 调到了 4g
- 作业改为读取新的分区目录（按天分区，目录结构变化，数据内容不变）
- 输入数据量比上周 +2%

【附 1】集群整体读数
- CPU 整体利用率：83%
- GC time 占 task 时间：19%（上周约 3%）
- 网络：正常

【附 2】Spark UI · Stage 2（排序与切分）· Summary Metrics（共 600 个 task）
| Metric | Min | 25th | Median | 75th | Max |
|---|---|---|---|---|---|
| Duration | 2.6 min | 3.1 min | 3.4 min | 3.7 min | 4.5 min |
| GC Time | 21 s | 33 s | 39 s | 44 s | 58 s |
| Shuffle Read Size | 168 MB | 176 MB | 181 MB | 186 MB | 197 MB |
| Shuffle Read Records | 190 万 | 198 万 | 203 万 | 208 万 | 221 万 |
| Spill (Memory) | 1.1 GB | 1.3 GB | 1.4 GB | 1.5 GB | 1.7 GB |
| Spill (Disk) | 0.4 GB | 0.5 GB | 0.55 GB | 0.6 GB | 0.7 GB |
（上周同一 Stage：Duration Median 1.1 min，Spill 全部为 0）

【附 3】Spark UI · Stage 2 · Aggregated Metrics by Executor（节选）
| Executor | Task Time | Spill (Memory) | Spill (Disk) | 备注 |
|---|---|---|---|---|
| 1 | 2.3 h | 52 GB | 20 GB | |
| 2 | 2.2 h | 51 GB | 20 GB | |
| 3 | 2.4 h | 54 GB | 21 GB | 本周被 YARN 杀掉 1 次 |
| … | … | … | … | 其余 13 个 executor 读数相近 |

【附 4】EXPLAIN FORMATTED（节选）
== Physical Plan ==
AdaptiveSparkPlan (6)
+- Window (5)
   +- Sort (4)
      +- Exchange (3)
         +- Filter (2)
            +- Scan parquet ais_points (1)

(3) Exchange
Arguments: hashpartitioning(mmsi#11L, 600), ENSURE_REQUIREMENTS

【附 5】executor 3 与 NodeManager 日志（节选，已脱敏）
INFO UnsafeExternalSorter: Thread 58 spilling sort data of 412.0 MB to disk (7 times so far)
WARN TaskMemoryManager: Failed to allocate a page (67108864 bytes), try again.
INFO UnsafeExternalSorter: Thread 61 spilling sort data of 398.0 MB to disk (9 times so far)
WARN YarnAllocator: Container killed by YARN for exceeding physical memory limits. 4.9 GB of 4.8 GB physical memory used.

【附 6】本次作业生效的配置
spark.executor.instances=16
spark.executor.cores=4
spark.executor.memory=4g
spark.executor.memoryOverhead=800m
spark.sql.shuffle.partitions=600
spark.sql.adaptive.enabled=true
spark.memory.fraction=0.6

【版本说明书】
Spark 版本：4.0.x
官方配置文档：https://spark.apache.org/docs/4.0.0/configuration.html
官方 SQL 性能调优文档：https://spark.apache.org/docs/4.0.0/sql-performance-tuning.html

与本作业相关的几项官方默认值（摘要）：
- spark.sql.adaptive.enabled：默认 true（AQE 自 Spark 3.2.0 起默认开启）
- spark.sql.adaptive.skewJoin.enabled：默认 true（AQE 开启时，自动拆分 sort-merge / shuffled hash join 中倾斜的分区）
- spark.sql.autoBroadcastJoinThreshold：默认 10MB（优化器估算小于该值的表会被广播；设为 -1 可禁用广播）
- spark.memory.fraction：默认 0.6（(堆内存 - 300MB) 中用于 execution + storage 的比例）
- spark.memory.storageFraction：默认 0.5（storage 中免于被驱逐的比例）

【要求】
① 先用人话复述现象和关键读数
② 列出不超过 3 个可能的原因假设，按可能性从高到低排序
③ 每个假设配 1 个可执行的验证动作（只用只读操作：看指标、看计划、看日志、小样本试跑）
④ 不要修改集群或配置，不要直接下结论
