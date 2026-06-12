# Spark 向量接入 FAISS 说明

## 脚本路径

```text
scripts/build_faiss_from_spark_vectors.py
```

## 输入文件

```text
data/faiss/movie_vectors.npy
data/faiss/movie_ids.npy
```

## 输出文件

```text
models/faiss_hnsw_spark.index
models/faiss_hnsw_spark_ids.npy
```

## 为什么不要覆盖原 FAISS 索引

原系统已经使用：

```text
models/faiss_hnsw.index
```

作为在线推荐链路的召回索引。本阶段只是验证 Spark ALS 向量能否构建独立 FAISS 索引，所以输出到 `faiss_hnsw_spark.index`，避免破坏当前已跑通系统。

## FAISS 构建方式

脚本读取 Spark ALS 导出的 `float32` 归一化向量，使用：

```text
faiss.IndexHNSWFlat(dim, M=32, METRIC_INNER_PRODUCT)
```

构建 HNSW 索引。由于向量已 L2 归一化，inner product 可以作为 cosine similarity 使用。

## sample search 示例

当前样例查询使用第一条 movie vector，Top-10 结果示例：

```text
movieId=1 score=1.0
movieId=78499 score=0.9538
movieId=6377 score=0.9427
movieId=3114 score=0.9375
movieId=588 score=0.9288
```

## 后续如何接入在线 RecallService

后续可以新增可选配置：

```text
FAISS_INDEX_PATH=models/faiss_hnsw_spark.index
FAISS_ID_MAP_PATH=models/faiss_hnsw_spark_ids.npy
```

或新增独立 `SparkFaissRecallService`。在完成回归测试前，不建议直接替换原 `models/faiss_hnsw.index`。
