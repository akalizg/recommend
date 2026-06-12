# Spark 集群接入验证

本文档记录本项目接入三节点 Spark standalone 集群后的实际验证结果。验证重点不是简单连接测试，而是确认项目中的离线推荐计算任务可以提交到 Spark 集群并成功执行。

## 一、集群环境

| 节点 | IP | 角色 | 状态 |
| --- | --- | --- | --- |
| node1 | 192.168.88.161 | Spark Master、Worker、ZooKeeper | ALIVE |
| node2 | 192.168.88.162 | Spark Worker、ZooKeeper | ALIVE |
| node3 | 192.168.88.163 | Spark Worker、ZooKeeper | ALIVE |

Spark Master 页面显示：

| 项目 | 结果 |
| --- | ---: |
| Master URL | `spark://node1:7077` |
| Alive Workers | 3 |
| Total Cores | 6 |
| Total Memory | 6.0 GiB |
| Cluster Status | ALIVE |

说明三台虚拟机的 Spark Worker 已经成功注册到 Master，集群处于可用状态。

## 二、项目文件部署方式

本项目在 Windows 本机打包 Spark 离线任务和处理后数据，再部署到虚拟机：

```text
/root/movierec
├── spark_jobs
├── scripts
├── data/processed
└── requirements.txt
```

由于当前虚拟机 Spark 版本为 3.1.2，而 Windows 本机 PySpark 为 3.5.3，为避免版本不一致，采用更稳定的方式：

> Spark Driver 运行在 node1 虚拟机上，通过虚拟机自带的 `spark-submit` 提交任务到 Spark 集群。

这样 Driver、Master、Worker 使用同一套 Spark 3.1.2 环境，避免跨版本提交导致的应用注册失败。

## 三、Spark 任务提交参数

三台虚拟机每台分配 4G 内存，因此 Spark 任务使用保守配置：

```bash
--master spark://node1:7077
--driver-memory 1g
--executor-memory 1g
--executor-cores 1
--num-executors 3
--conf spark.eventLog.enabled=false
--conf spark.hadoop.fs.defaultFS=file:///
```

其中：

- `spark.eventLog.enabled=false`：避免当前未启动 HDFS 时写入 `node1.itcast.cn:8020` 失败。
- `spark.hadoop.fs.defaultFS=file:///`：强制当前验证任务使用本地文件系统读取项目 CSV 数据。
- `--num-executors 3`：对应三台 worker。

## 四、集群计算预检结果

先提交一个轻量分布式计算任务，确认 Spark 集群可以接收并执行应用：

```bash
cd /root/movierec
bash scripts/vm_run_smoke.sh
```

输出结果：

```text
Spark connection OK
spark_version=3.1.2
master=spark://node1:7077
app_id=app-20260612205528-0002
default_parallelism=4
test_count=1000
```

该步骤说明 Spark 应用可以正常提交到三节点集群并完成计算。

## 五、项目离线画像构建任务验证

在完成集群计算预检后，继续提交项目自身的 Spark 离线画像构建任务：

```bash
cd /root/movierec
bash scripts/vm_run_sample_profile.sh
```

该任务调用项目中的：

```text
spark_jobs/spark_build_profile.py
```

处理数据：

| 数据 | 数量 |
| --- | ---: |
| 训练交互样本 | 20,000 |
| 食谱基础数据 | 178,265 |
| 标签/配料样本 | 200,000 |

执行结果：

```text
train ratings rows: 20000
movies rows: 178265
tags rows: 200000
user profile rows: 260
movie profile rows: 178265
valid users: 260
valid movies: 16124
average user rating count: 76.9231
average movie rating count: 0.1122
output paths: /root/movierec/data/features_sample/user_profile.csv, /root/movierec/data/features_sample/movie_profile.csv
quality validation result: success
```

该结果说明项目 Spark 离线画像构建逻辑已经可以在三节点 Spark 集群上成功运行，能够读取 Food.com 处理后数据，生成用户画像和食谱画像，并通过脚本内置质量校验。

## 六、验证结论

本项目已经完成 Spark standalone 三节点集群接入，并通过项目离线画像构建任务验证。当前集群包含 3 个 Worker、6 个 CPU Core 和 6.0 GiB 可用 Spark 内存。项目 Spark 作业能够通过 `spark-submit` 提交到集群执行，并成功处理 Food.com 食谱数据，生成用户画像与食谱画像。

因此，项目已经具备将离线数据处理、画像构建、ALS 训练、ItemCF 召回和排序特征导出等任务迁移到 Spark 集群执行的能力。当前全量推荐结果已经在本地离线链路中生成，后续如果接入 HDFS 或共享存储，可进一步将全量离线链路稳定迁移到三节点 Spark 集群。

