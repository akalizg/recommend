# Spark 接入说明

本项目的 Spark 作业已经支持两种运行方式：

1. 本机 local 模式：默认使用 `local[*]`，适合小规模调试。
2. Spark standalone 集群模式：设置 `SPARK_MASTER_URL=spark://虚拟机IP:7077` 后，现有 Spark 作业会连接到虚拟机 Spark 集群。

## 一、虚拟机启动 Spark

以下命令在虚拟机里执行，路径按你的 Spark 安装目录调整。

启动 master：

```bash
$SPARK_HOME/sbin/start-master.sh
```

启动 worker：

```bash
$SPARK_HOME/sbin/start-worker.sh spark://虚拟机IP:7077
```

查看 master 页面：

```text
http://虚拟机IP:8080
```

如果页面里能看到 alive worker，说明 Spark 集群已经启动。

## 二、项目推荐提交方式

当前虚拟机 Spark 版本为 3.1.2，而 Windows 项目环境中的 PySpark 版本为 3.5.3。为了避免跨版本提交导致应用注册失败，推荐采用以下方式：

> 将 Spark Driver 放到 node1 虚拟机上，通过虚拟机自带的 `spark-submit` 提交项目 Spark 任务。

也就是说，Windows 本机负责开发和打包，虚拟机 Spark 集群负责执行离线计算任务。

Windows 项目中的 `.env` 可以保留以下配置，用于记录集群地址和资源参数：

```env
SPARK_MASTER_URL=spark://node1:7077
SPARK_DRIVER_MEMORY=1g
SPARK_EXECUTOR_MEMORY=1g
SPARK_EXECUTOR_CORES=1
SPARK_EXECUTOR_INSTANCES=3
SPARK_SQL_SHUFFLE_PARTITIONS=12
SPARK_DEFAULT_PARALLELISM=12
SPARK_UI_SHOW_CONSOLE_PROGRESS=false
```

如果每台虚拟机只分配 4G 内存，建议先使用上面这组保守配置。三台 worker 合计提供约 3 个 executor，每个 executor 使用 1G 内存和 1 个 CPU 核心，稳定性优先。

## 三、部署项目 Spark 任务到虚拟机

Windows 本机先打包项目 Spark 任务和处理后数据，再在 node1 下载并分发到三台虚拟机。

node1 下载：

```bash
cd /root
wget -O movierec_spark_payload.tar.gz http://192.168.88.8:8765/movierec_spark_payload.tar.gz
```

分发到 node2、node3：

```bash
scp /root/movierec_spark_payload.tar.gz root@node2:/root/
scp /root/movierec_spark_payload.tar.gz root@node3:/root/
```

三台解压到相同路径：

```bash
for host in node1 node2 node3
do
  ssh root@$host "rm -rf /root/movierec && mkdir -p /root/movierec && tar -xzf /root/movierec_spark_payload.tar.gz -C /root/movierec && chmod +x /root/movierec/scripts/vm_run_*.sh"
done
```

## 四、集群任务验证

先提交一个轻量分布式计算任务，确认 Spark 集群可以接收应用：

```bash
cd /root/movierec
bash scripts/vm_run_smoke.sh
```

成功输出示例：

```text
Spark connection OK
spark_version=3.1.2
master=spark://node1:7077
app_id=app-20260612205528-0002
test_count=1000
```

## 五、运行项目离线画像构建任务

继续提交项目自身的 Spark 画像构建任务：

```bash
cd /root/movierec
bash scripts/vm_run_sample_profile.sh
```

已验证结果：

```text
train ratings rows: 20000
movies rows: 178265
tags rows: 200000
user profile rows: 260
movie profile rows: 178265
valid users: 260
valid movies: 16124
quality validation result: success
```

该结果说明项目 Spark 离线画像构建任务已经能够在三节点集群上运行。

## 六、注意事项

1. Windows 可以访问虚拟机 Spark master 的 `7077` 端口和 Web UI 的 `8080` 端口，但由于本机 PySpark 版本和虚拟机 Spark 版本不同，不建议直接从 Windows 提交 Spark 应用。
2. 本机浏览器访问 master 页面通常是 `http://虚拟机IP:8080`。
3. 如果虚拟机防火墙开启，需要放行 `7077`、`8080` 和 worker 相关端口。
4. 当前验证任务使用本地文件系统，并将项目数据同步到三台虚拟机相同路径 `/root/movierec`，保证 worker 可以读取输入文件。
5. 后续如果要长期运行全量任务，建议接入 HDFS 或共享存储，避免分布式写本地文件带来的路径不一致问题。
