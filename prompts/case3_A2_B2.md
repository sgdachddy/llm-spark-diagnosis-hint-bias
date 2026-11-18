我的 Spark 作业出了问题，我觉得是那张新表被广播了，帮我看看。下面是相关材料。

【现象】
作业 ais_port_events 今天失败，昨天正常（约 12 min）。失败发生在 join 阶段，多个 executor 先后退出，作业重试 4 次后终止。
作业内容：AIS 船位点与港区属性表 zone_attr_v2 按 zone_id 做 join，再统计进出港事件。
集群：12 个 executor，每个 8 核、16 GB 内存。
最近改动：zone_attr_v2 是上游脚本昨天新生成的表，替换了原来的 zone_attr；作业代码未改。

【附 1】报错栈（driver 端，节选，已脱敏）
org.apache.spark.SparkException: Job aborted due to stage failure: Task 37 in stage 4.0 failed 4 times,
most recent failure: Lost task 37.3 in stage 4.0 (TID 611) (executor 9):
ExecutorLostFailure (executor 9 exited caused by one of the running tasks)
Reason: Executor heartbeat timed out / java.lang.OutOfMemoryError: Java heap space
  at org.apache.spark.sql.execution.joins.UnsafeHashedRelation$.apply(HashedRelation.scala:...)
  at org.apache.spark.sql.execution.joins.HashedRelation$.apply(HashedRelation.scala:...)
  at org.apache.spark.sql.execution.joins.HashedRelationBroadcastMode.transform(HashedRelation.scala:...)
  at org.apache.spark.sql.execution.exchange.BroadcastExchangeExec...
  ...（以下约 280 行为重复的调用链与 Caused by，略）

【附 2】Spark UI · Stage 4 · Summary Metrics（失败前已完成的 61 个 task）
| Metric | Min | 25th | Median | 75th | Max |
|---|---|---|---|---|---|
| Duration | 41 s | 48 s | 52 s | 57 s | 1.2 min |
| GC Time | 9 s | 12 s | 14 s | 16 s | 22 s |
| Input Size | 118 MB | 124 MB | 126 MB | 129 MB | 131 MB |
| Spill (Disk) | 0 | 0 | 0 | 0 | 0 |

【附 3】EXPLAIN FORMATTED（节选）
== Physical Plan ==
AdaptiveSparkPlan (10)
+- HashAggregate (9)
   +- Exchange (8)
      +- HashAggregate (7)
         +- Project (6)
            +- BroadcastHashJoin Inner BuildRight (5)
               :- Filter (2)
               :  +- Scan parquet ais_points (1)
               +- BroadcastExchange (4)
                  +- Scan parquet zone_attr_v2 (3)

【附 4】EXPLAIN COST（节选）
+- Relation spark_catalog.ocean.zone_attr_v2[zone_id#40,geom_wkt#41,attrs#42,...] parquet, Statistics(sizeInBytes=8.2 MiB)

【附 5】DESCRIBE TABLE EXTENDED ocean.zone_attr_v2（节选）
Created Time   Tue Nov 17 23:41:07 JST 2026
Type           MANAGED
Provider       parquet
Location       s3://<bucket>/warehouse/ocean.db/zone_attr_v2
（输出中没有 Statistics 行）

【附 6】存储目录列表
$ aws s3 ls --summarize --recursive s3://<bucket>/warehouse/ocean.db/zone_attr_v2/
Total Objects: 6
Total Size: 1.8 GiB

【附 7】本次作业生效的配置
spark.executor.instances=12
spark.executor.cores=8
spark.executor.memory=16g
spark.sql.adaptive.enabled=true
spark.sql.autoBroadcastJoinThreshold=10MB
spark.sql.shuffle.partitions=200

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
