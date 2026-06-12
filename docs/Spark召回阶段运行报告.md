# Spark 召回阶段运行报告

## 本阶段完成内容

1. 新增 Spark ALS 向量独立 FAISS 索引构建脚本。
2. 实现 Spark ItemCF 召回。
3. 实现 ALS + ItemCF 多路召回融合。
4. 新增统一运行脚本 `scripts/run_spark_recall_stage.py`。

本阶段没有修改 FastAPI、Vue、原 `models/faiss_hnsw.index` 或 XGBoost。

## FAISS Spark index 构建结果

输出：

```text
models/faiss_hnsw_spark.index
models/faiss_hnsw_spark_ids.npy
```

输入向量：

```text
data/faiss/movie_vectors.npy shape=(9701, 32)
data/faiss/movie_ids.npy shape=(9701,)
```

sample search 示例：

```text
movieId=1 score=1.0
movieId=78499 score=0.9538
movieId=6377 score=0.9427
movieId=3114 score=0.9375
movieId=588 score=0.9288
```

## ItemCF recall 行数

```text
data/recall/itemcf_recall.csv rows: 30450
```

## merged recall 行数

```text
data/recall/merged_recall_candidates.csv rows: 59014
```

## 平均每用户候选数量

```text
average candidates per user: 96.7443
```

## 示例召回结果前 10 行

```text
userId,movieId,als_score,itemcf_score,recall_source_count,merged_recall_score
1,318,5.205355,6.033068,2,1.130124
1,1193,5.007686,2.351710,2,0.899997
1,33649,5.296398,0.000000,1,0.700000
1,3347,5.266506,0.000000,1,0.696614
1,3925,5.266271,0.000000,1,0.696587
1,177593,5.235629,0.000000,1,0.693116
1,3379,5.208017,0.000000,1,0.689988
1,5915,5.204998,0.000000,1,0.689646
1,78836,5.202664,0.000000,1,0.689381
1,171495,5.189080,0.000000,1,0.687843
```

## 测试结果

本阶段新增测试：

```text
tests/test_build_faiss_from_spark_vectors.py
tests/test_spark_itemcf_recall.py
tests/test_spark_merge_recall.py
```

最终测试结果：

```text
tests/test_build_faiss_from_spark_vectors.py: 2 passed
tests/test_spark_itemcf_recall.py: 2 passed
tests/test_spark_merge_recall.py: 2 passed
```

## 本阶段没有改动原在线推荐链路

本阶段所有产物都是旁路离线结果：

```text
models/faiss_hnsw_spark.index
models/faiss_hnsw_spark_ids.npy
data/recall/itemcf_recall.csv
data/recall/merged_recall_candidates.csv
```

原在线链路仍然使用原有 FastAPI、Redis、FAISS、XGBoost 和 Vue 页面。

## 下一步如何导出 XGBoost 排序特征

下一步建议实现：

```text
spark_jobs/spark_feature_export.py
```

输入：

```text
data/features/user_profile.csv
data/features/movie_profile.csv
data/recall/merged_recall_candidates.csv
```

输出：

```text
data/rank/rank_train.csv
data/rank/rank_candidates.csv
```

把多路召回分数、画像特征、来源数量等统一导出给 XGBoost 精排。
