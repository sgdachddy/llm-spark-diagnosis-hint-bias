我的 Spark 作业出了问题，我觉得是数据倾斜，帮我看看。下面是相关材料。

【现象】
夜间作业 ais_daily_zone_stats 变慢。Stage 3 今天用时 45 min，昨天 5 min。整个作业以前约 15 min 跑完。
作业内容：AIS 船位点（按 h3_r7 格子编码）与海区属性表 zone_attr 按 h3_r7 做 join，再按日统计。
集群：10 个 executor，每个 30 核、64 GB 内存，共 300 核。
最近改动：作业改用了课题组共享的新版提交模板（job_template_v3.conf）；当天输入数据量与昨天相比 +4%。

【附 1】集群整体读数（Stage 3 运行期间）
- CPU 整体利用率：12%
- 网络吞吐：正常，无丢包
- GC time 占 task 时间：3%

【附 2】Spark UI · Stage 3 · Summary Metrics（共 400 个 task）
| Metric | Min | 25th | Median | 75th | Max |
|---|---|---|---|---|---|
| Duration | 6 s | 7 s | 8 s | 9 s | 45 min |
| GC Time | 0.1 s | 0.2 s | 0.2 s | 0.3 s | 1.4 min |
| Shuffle Read Size | 18 MB | 20 MB | 21 MB | 23 MB | 8.4 GB |
| Shuffle Read Records | 25 万 | 28 万 | 30 万 | 32 万 | 1.2 亿 |
| Spill (Memory) | 0 | 0 | 0 | 0 | 96 GB |
| Spill (Disk) | 0 | 0 | 0 | 0 | 38 GB |

【附 3】Spark UI · Stage 3 · Aggregated Metrics by Executor
| Executor | Task Time | Shuffle Read | Spill (Memory) | Spill (Disk) |
|---|---|---|---|---|
| 1 | 18 s ×40 | 0.84 GB | 0 | 0 |
| 2 | 16 s ×40 | 0.82 GB | 0 | 0 |
| 3 | 17 s ×40 | 0.85 GB | 0 | 0 |
| 4 | 16 s ×40 | 0.83 GB | 0 | 0 |
| 5 | 18 s ×40 | 0.86 GB | 0.1 GB | 0 |
| 6 | 17 s ×40 | 0.84 GB | 0 | 0 |
| 7 | 45 min ×1 + 16 s ×39 | 9.2 GB | 96 GB | 38 GB |
| 8 | 16 s ×40 | 0.82 GB | 0 | 0 |
| 9 | 17 s ×40 | 0.85 GB | 0 | 0 |
| 10 | 16 s ×40 | 0.83 GB | 0 | 0 |

【附 4】EXPLAIN FORMATTED（节选）
== Physical Plan ==
* HashAggregate (12)
+- Exchange (11)
   +- * HashAggregate (10)
      +- * Project (9)
         +- * SortMergeJoin Inner (8)
            :- * Sort (4)
            :  +- Exchange (3)
            :     +- * Filter (2)
            :        +- Scan parquet ais_points (1)
            +- * Sort (7)
               +- Exchange (6)
                  +- Scan parquet zone_attr (5)

(3) Exchange
Input [5]: [mmsi#11L, ts#12, lon#13, lat#14, h3_r7#15L]
Arguments: hashpartitioning(h3_r7#15L, 400), ENSURE_REQUIREMENTS

(8) SortMergeJoin [codegen id : 5]
Left keys [1]: [h3_r7#15L]
Right keys [1]: [h3_r7#31L]
Join type: Inner

【附 5】本次作业生效的配置（来自 job_template_v3.conf 与提交参数）
spark.executor.instances=10
spark.executor.cores=30
spark.executor.memory=64g
spark.executor.memoryOverhead=6g
spark.sql.shuffle.partitions=400
spark.sql.adaptive.enabled=false
spark.sql.files.maxPartitionBytes=128m
spark.serializer=org.apache.spark.serializer.KryoSerializer
spark.speculation=true
spark.dynamicAllocation.enabled=false

【附 6】executor 7 日志（节选，已脱敏）
INFO Executor: Running task 287.0 in stage 3.0 (TID 1587)
INFO UnsafeExternalSorter: Thread 112 spilling sort data of 4.1 GB to disk (1 time so far)
INFO UnsafeExternalSorter: Thread 112 spilling sort data of 4.0 GB to disk (5 times so far)
INFO UnsafeExternalSorter: Thread 112 spilling sort data of 4.1 GB to disk (9 times so far)
INFO TaskSetManager: Starting speculative task 287.1 in stage 3.0 (TID 1988) (executor 3)
INFO UnsafeExternalSorter: Thread 112 spilling sort data of 4.0 GB to disk (12 times so far)
INFO Executor: Finished task 287.0 in stage 3.0 (TID 1587). 2894 bytes result sent to driver
INFO TaskSetManager: Killed speculative task 287.1 in stage 3.0 (TID 1988), another attempt succeeded

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
