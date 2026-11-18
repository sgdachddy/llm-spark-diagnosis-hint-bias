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
