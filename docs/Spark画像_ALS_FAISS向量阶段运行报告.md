# Spark 画像 ALS FAISS 向量阶段运行报告

## 本阶段完成内容

本阶段一次性完成三个 Spark 离线旁路模块：

1. `spark_jobs/spark_build_profile.py`
2. `spark_jobs/spark_als_train.py`
3. `spark_jobs/spark_export_faiss_vectors.py`

并新增统一执行脚本：

```text
scripts/run_spark_profile_als.py
```

本阶段没有修改 FastAPI 推荐接口，没有修改 Vue 前端，没有替换原 FAISS 索引，没有训练 XGBoost。

## 三个脚本运行结果

### 1. Spark 画像构建

输出：

```text
data/features/user_profile.csv
data/features/movie_profile.csv
```

结果：

```text
train ratings rows: 100226
movies rows: 9742
tags rows: 25624
user profile rows: 610
movie profile rows: 9742
valid users: 610
valid movies: 9701
average user rating count: 164.3049
average movie rating count: 10.2880
```

### 2. Spark ALS 训练

统一运行脚本参数：

```text
rank = 32
maxIter = 8
regParam = 0.1
topN = 50
```

输出：

```text
data/factors/user_factors.csv
data/factors/movie_factors.csv
data/recall/als_recall.csv
models/spark_als/
```

统一运行脚本结果：

```text
train rows: 100226
user count: 610
movie count: 9701
user factors rows: 610
movie factors rows: 9701
als recall rows: 30373
average recall per user: 49.8736
```

`tests/test_spark_als_train.py` 使用临时目录运行轻量参数，不覆盖正式 `data/factors`、`data/recall`、`models/spark_als` 产物：

```text
rank = 16
maxIter = 3
regParam = 0.1
topN = 20
```

### 3. FAISS 向量导出

输出：

```text
data/faiss/movie_vectors.npy
data/faiss/movie_ids.npy
```

统一运行脚本结果：

```text
movie factors rows: 9701
factor dimension: 32
movie_vectors shape: (9701, 32)
movie_ids shape: (9701,)
normalize enabled: True
```

## 输出文件行数

| 文件 | 行数 |
| --- | ---: |
| `data/features/user_profile.csv` | 610 |
| `data/features/movie_profile.csv` | 9742 |
| `data/factors/user_factors.csv` | 610 |
| `data/factors/movie_factors.csv` | 9701 |
| `data/recall/als_recall.csv` | 30373 |

## ALS recall 示例

```text
userId,movieId,recall_type,recall_score
1,33649,als,5.296398
1,3347,als,5.266506
1,3925,als,5.266271
1,177593,als,5.235629
1,3379,als,5.208017
1,318,als,5.205355
1,5915,als,5.204998
1,78836,als,5.202664
1,171495,als,5.189080
1,720,als,5.177293
```

## FAISS vectors shape

```text
movie_vectors.npy: (9701, 32)
movie_ids.npy: (9701,)
```

## 测试结果

本阶段新增测试：

```text
tests/test_spark_build_profile.py
tests/test_spark_als_train.py
tests/test_spark_export_faiss_vectors.py
```

最终测试执行结果：

```text
tests/test_spark_build_profile.py: 2 passed
tests/test_spark_als_train.py: 2 passed
tests/test_spark_export_faiss_vectors.py: 2 passed
```

## 本阶段没有改动原在线推荐链路

本阶段所有输出都位于：

```text
data/features/
data/factors/
data/recall/
data/faiss/
models/spark_als/
```

这些都是旁路离线产物。当前 FastAPI、Vue、原 FAISS 索引、XGBoost 排序链路都未接入这些产物。

## 下一步建议

1. 新增原项目 FAISS 构建脚本的可选入口，读取 `data/faiss/movie_vectors.npy` 和 `data/faiss/movie_ids.npy`。
2. 实现 `spark_jobs/spark_itemcf_recall.py`，增加 ItemCF 召回通道。
3. 实现 `spark_jobs/spark_feature_export.py`，融合画像、ALS 召回、ItemCF 召回和后续 FAISS 召回分数，为 XGBoost 导出增强排序特征。
