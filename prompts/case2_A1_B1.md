我的 Spark 作业出了问题，我觉得是这周升级的 h3 库导致的，帮我看看。下面是相关材料。

【现象】
作业 ais_vessel_features 本周变慢：以前约 18 min，本周约 31 min。没有报错。
作业内容：读取 AIS 船位点，过滤后得到中间表 feat，再基于 feat 计算三组特征（航速分布、停泊时长、航线密度），分别写出。
集群：10 个 executor，每个 8 核、24 GB 内存，共 80 核。
最近改动（本周）：
- 代码中给中间表 feat 加了 persist(StorageLevel.MEMORY_AND_DISK)
- 升级了 h3 Python 库的小版本
- 输入数据量比上周 +3%

【附 1】集群整体读数
- CPU 整体利用率：34%
- 磁盘 IO wait：28%（上周约 5%）
- GC time 占 task 时间：6%

【附 2】Spark UI · Storage 页
| RDD Name | Storage Level | Cached Partitions | Fraction Cached | Size in Memory | Size on Disk |
|---|---|---|---|---|---|
| feat（*(1) Filter … Scan parquet ais_points） | Disk Memory Deserialized 1x Replicated | 320 | 100% | 10.2 GB | 29.8 GB |

【附 3】Spark UI · Jobs 概览
| Job | 内容 | 用时（本周） | 用时（上周） |
|---|---|---|---|
| 0 | feat.count()（物化缓存） | 9.5 min | — |
| 1 | 航速分布 | 7.1 min | 6.2 min |
| 2 | 停泊时长 | 7.6 min | 5.8 min |
| 3 | 航线密度 | 6.8 min | 5.9 min |

【附 4】Spark UI · Job 2 中聚合 Stage 的 Summary Metrics（共 320 个 task）
| Metric | Min | 25th | Median | 75th | Max |
|---|---|---|---|---|---|
| Duration | 58 s | 1.1 min | 1.2 min | 1.3 min | 1.9 min |
| Shuffle Read Size | 92 MB | 101 MB | 104 MB | 108 MB | 121 MB |
| Spill (Memory) | 0.6 GB | 0.9 GB | 1.0 GB | 1.1 GB | 1.4 GB |
| Spill (Disk) | 0.2 GB | 0.3 GB | 0.35 GB | 0.4 GB | 0.5 GB |
（上周同一 Stage：Spill 全部为 0）

【附 5】EXPLAIN FORMATTED（Job 2，节选）
== Physical Plan ==
* HashAggregate (6)
+- Exchange (5)
   +- * HashAggregate (4)
      +- * Project (3)
         +- InMemoryTableScan (2)
               +- InMemoryRelation (1)
                     +- * Filter
                        +- * ColumnarToRow
                           +- Scan parquet ais_points
                              PushedFilters: [IsNotNull(sog), GreaterThan(sog,0.5)]
                              ReadSchema: struct<mmsi:bigint,ts:timestamp,lon:double,lat:double,sog:double,cog:double,h3_r7:bigint,nav_status:int>

【附 6】代码片段
# h3_r7 列由上游预先计算并写入 parquet
feat = (spark.read.parquet("s3://<bucket>/ais_points/2026-11/")
        .filter("sog IS NOT NULL AND sog > 0.5"))
feat.persist(StorageLevel.MEMORY_AND_DISK)
feat.count()
speed_dist(feat).write.parquet(out1)
berth_time(feat).write.parquet(out2)
lane_density(feat).write.parquet(out3)

【附 7】本次作业生效的配置
spark.executor.instances=10
spark.executor.cores=8
spark.executor.memory=24g
spark.sql.shuffle.partitions=320
spark.sql.adaptive.enabled=true
spark.memory.fraction=0.6
spark.memory.storageFraction=0.5

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
