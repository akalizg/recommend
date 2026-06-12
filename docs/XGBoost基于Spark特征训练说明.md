# XGBoost 基于 Spark 特征训练说明

## 脚本路径

```text
rank/train_from_spark_features.py
```

该脚本读取 Spark 导出的排序训练特征，训练离线 XGBoost 二分类精排模型。当前阶段不接入线上推荐链路。

## 输入文件

```text
data/rank/rank_train.csv
data/rank/rank_feature_columns.json
```

`rank_feature_columns.json` 用于保证训练和预测阶段使用完全一致的特征列。

## 输出文件

```text
models/xgb_rank_model_spark.json
models/xgb_rank_feature_columns.json
data/rank/xgb_train_metrics.json
data/rank/xgb_feature_importance.csv
```

## 训练目标

当前阶段使用 `XGBClassifier` 做二分类：

```text
objective = binary:logistic
eval_metric = auc
```

标签含义：

```text
label = 1: 用户高评分或喜欢该电影
label = 0: 用户低评分或不喜欢该电影
```

后续可以扩展为 `rank:pairwise` 或 LambdaRank 类目标。

## 模型参数

本次正式运行使用参数：

```text
n_estimators = 200
max_depth = 5
learning_rate = 0.05
subsample = 0.8
colsample_bytree = 0.8
random_state = 42
tree_method = hist
```

测试脚本会使用较小的 `n_estimators=20` 和 `max_depth=3`，用于快速验证脚本可运行。

## 训练 / 验证划分

脚本在 `rank_train.csv` 内部再做一次 80/20 划分：

```text
train = 80%
valid = 20%
random_state = 42
```

当正负样本数量满足条件时使用 stratify，保持训练集和验证集类别比例稳定。

## 正负样本数量

本次运行统计：

```text
rank_train rows: 87134
positive samples: 48217
negative samples: 38917
train rows: 69707
valid rows: 17427
feature count: 31
```

## 训练指标

本次运行指标：

```text
train AUC: 0.881401
valid AUC: 0.873056
train accuracy: 0.795630
valid accuracy: 0.788948
train logloss: 0.423833
valid logloss: 0.437016
```

## 特征重要性 Top10

```text
movie_avg_rating        0.366810
user_avg_rating         0.181390
user_movie_score_gap    0.051032
movie_rating_std        0.045078
movie_popularity        0.044670
genre_match_score       0.041057
decade_match_score      0.034700
user_rating_std         0.033072
user_min_rating         0.029088
user_rating_count       0.027239
```

当前模型主要依赖电影平均评分、用户评分习惯、用户电影评分差、电影热度和类型匹配等特征，符合第一版精排模型的预期。

## 运行命令

```bash
python rank/train_from_spark_features.py
```

也可以显式指定路径：

```bash
python rank/train_from_spark_features.py \
  --train data/rank/rank_train.csv \
  --features data/rank/rank_feature_columns.json \
  --model-output models/xgb_rank_model_spark.json \
  --model-features-output models/xgb_rank_feature_columns.json \
  --metrics-output data/rank/xgb_train_metrics.json \
  --importance-output data/rank/xgb_feature_importance.csv
```

## 质量校验

脚本已校验：

```text
模型文件存在
模型特征列文件存在
训练样本数大于 0
正负样本都存在
预测概率位于 [0, 1]
训练指标文件存在
特征重要性文件存在且非空
```
