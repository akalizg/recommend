# XGBoost 排序优化说明

## 脚本路径

```text
rank/train_xgboost_ranker.py
```

## 优化目标

原 XGBoost 使用二分类目标，离线评估中 Top10 表现弱于 ItemCF。本阶段新增排序优化版本，优先使用：

```text
XGBRanker
objective = rank:ndcg
eval_metric = ndcg@10
```

如果本地环境不支持 XGBRanker，脚本会降级为 XGBClassifier 并在指标文件中记录原因。

## 输入文件

```text
data/rank/rank_train.csv
data/rank/rank_candidates_optimized.csv
data/rank/rank_feature_columns.json
```

`rank_candidates_optimized.csv` 基于优化后的召回融合候选生成。

## 输出文件

```text
models/xgb_ranker_model_spark.json
models/xgb_ranker_feature_columns.json
data/rank/xgb_ranker_train_metrics.json
data/rank/xgb_ranker_feature_importance.csv
data/rank/ranked_top50_ranker.csv
```

## 训练方式

```text
按 userId 作为 query group
按用户划分训练 / 验证集
同一用户不会同时出现在训练集和验证集
```

## 本次训练结果

```text
model_type: ranker
fallback_reason: null
train rows: 63813
valid rows: 23321
train users: 488
valid users: 122
feature count: 31
valid Precision@10: 0.878512
valid Recall@10: 0.238401
valid NDCG@10: 0.901628
valid HitRate@10: 1.000000
ranked rows: 30500
```

验证集指标来自 `rank_train.csv` 内部用户切分，不等同于最终 `test_ratings.csv` 离线指标。

## 特征重要性 Top10

```text
movie_avg_rating       0.324364
movie_popularity       0.129874
movie_rating_std       0.105896
genre_match_score      0.082496
movie_rating_count     0.078172
decade_match_score     0.052986
active_level_code      0.036186
user_rating_count      0.034240
movie_year             0.025806
tag_count              0.024622
```

## 离线测试集表现

```text
XGBoost_Classifier_Top50 NDCG@10: 0.000918
XGBoost_Ranker_Top50     NDCG@10: 0.000918
```

XGBRanker 成功训练，但在当前 MovieLens small 留一测试集上没有解决 XGBoost 相关性指标弱于 ItemCF 的问题。可能原因包括测试集正样本太少、候选集中目标电影覆盖不足，以及训练标签仍来自历史评分而非真实 Top-K 点击反馈。
