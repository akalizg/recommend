# XGBoost 精排预测说明

## 脚本路径

```text
rank/predict_from_spark_features.py
```

该脚本读取 Spark 候选特征和离线 XGBoost 模型，对每个用户的召回候选电影重新打分，输出每用户 Top50。当前阶段只生成离线结果，不接入 FastAPI 或 Vue。

## 输入文件

```text
data/rank/rank_candidates.csv
models/xgb_rank_model_spark.json
models/xgb_rank_feature_columns.json
```

模型特征列文件用于确保预测阶段的列顺序和训练阶段一致。

## 输出文件

```text
data/rank/ranked_top50.csv
```

## 精排预测流程

```text
读取 rank_candidates.csv
读取 XGBoost 模型
读取模型特征列
按特征列构造矩阵
输出 predict_proba 的正类概率
按用户内 rank_score 倒序排序
rank_score 相同则按 merged_recall_score 倒序
每个用户保留 Top50
```

## rank_score 含义

`rank_score` 是 XGBoost 二分类模型输出的正类概率，表示模型认为用户会喜欢该候选电影的概率分数。它不是原始评分，也不是召回分数。

## Top50 生成方式

排序规则：

```text
userId 分组
rank_score desc
merged_recall_score desc
movieId asc
每个用户最多保留 50 条
```

`rank_position` 从 1 开始，表示该电影在该用户精排列表中的位置。

## 输出字段说明

`ranked_top50.csv` 至少包含：

```text
userId
movieId
rank_position
rank_score
label
als_score
itemcf_score
merged_recall_score
recall_source_count
genre_match_score
movie_avg_rating
movie_popularity
```

`label` 保留自候选集，用于后续离线评估。

## 本次运行结果

```text
candidate rows: 59014
user count: 610
movie count: 1967
feature count: 31
ranked rows: 30500
average topN per user: 50.0000
output path: data/rank/ranked_top50.csv
```

## 示例精排结果前 10 行

```text
userId movieId rank_position rank_score label merged_recall_score genre_match_score movie_avg_rating
1      7122    1             0.99890721 0     0.667298            0.666667          5.0
1      3379    2             0.99888629 0     0.689988            1.000000          4.5
1      26073   3             0.99884099 0     0.669136            0.500000          5.0
1      26928   4             0.99875212 0     0.669136            0.666667          5.0
1      5490    5             0.99871492 0     0.681224            1.000000          5.0
1      7071    6             0.99871266 0     0.669136            1.000000          5.0
1      74226   7             0.99869233 0     0.669136            0.500000          5.0
1      33649   8             0.99866688 0     0.700000            0.666667          5.0
1      27523   9             0.99854785 0     0.670693            0.500000          5.0
1      5328    10            0.99854785 0     0.664898            0.500000          5.0
```

## 运行命令

```bash
python rank/predict_from_spark_features.py
```

也可以显式指定路径：

```bash
python rank/predict_from_spark_features.py \
  --candidates data/rank/rank_candidates.csv \
  --model models/xgb_rank_model_spark.json \
  --features models/xgb_rank_feature_columns.json \
  --output data/rank/ranked_top50.csv \
  --top-n 50
```

## 质量校验结果

脚本已校验：

```text
ranked_top50.csv 存在
每个用户推荐数量不超过 50
rank_score 非空
rank_score 位于 [0, 1]
rank_position 从 1 开始
输出字段完整
用户数量为 610
```
