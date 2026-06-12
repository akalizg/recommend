# MMR 参数调优说明

## 脚本路径

```text
evaluate/tune_mmr_lambda.py
```

## 输入文件

优先使用：

```text
data/rank/ranked_top50_ranker.csv
```

如果不存在，则回退到：

```text
data/rank/ranked_top50.csv
```

同时读取：

```text
data/features/movie_profile.csv
data/processed/test_ratings.csv
```

## 扫描参数

```text
lambda_rel = 0.5, 0.6, 0.7, 0.8, 0.9
```

每个 lambda 生成 Top10，并计算：

```text
Precision@10
Recall@10
NDCG@10
HitRate@10
Coverage@10
Diversity@10
```

## 输出文件

```text
data/eval/mmr_lambda_tuning.csv
data/eval/best_mmr_lambda.json
data/rank/ranked_top10_mmr_optimized.csv
```

## 本次扫描结果

```text
lambda  Precision@10  Recall@10  NDCG@10  Diversity@10
0.5     0.000826      0.008264   0.002970 0.919420
0.6     0.000275      0.002755   0.001377 0.904378
0.7     0.000275      0.002755   0.001377 0.882191
0.8     0.000275      0.002755   0.001186 0.863386
0.9     0.000275      0.002755   0.001066 0.848839
```

## 最佳 lambda

```text
lambda_rel = 0.5
```

选择原因：在本次扫描中，`0.5` 同时取得最高 NDCG@10 和最高 Diversity@10。

## 优化后 MMR 输出

```text
data/rank/ranked_top10_mmr_optimized.csv
```

每个用户最多 10 条推荐，不覆盖旧的：

```text
data/rank/ranked_top10_mmr.csv
```
