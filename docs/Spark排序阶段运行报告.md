# Spark 排序阶段运行报告

## 本阶段完成内容

本阶段完成了 Spark 离线召回之后的精排链路：

```text
Spark 用户画像 + 电影画像 + 多路召回候选
        ->
Spark 批量导出排序特征
        ->
XGBoost 二分类精排模型训练
        ->
候选集精排预测
        ->
每用户 Top50 离线结果
```

新增脚本：

```text
spark_jobs/spark_feature_export.py
rank/train_from_spark_features.py
rank/predict_from_spark_features.py
scripts/run_spark_rank_stage.py
```

新增测试：

```text
tests/test_spark_feature_export.py
tests/test_train_from_spark_features.py
tests/test_predict_from_spark_features.py
```

## 输出文件

```text
data/rank/rank_train.csv
data/rank/rank_candidates.csv
data/rank/rank_feature_columns.json
models/xgb_rank_model_spark.json
models/xgb_rank_feature_columns.json
data/rank/xgb_train_metrics.json
data/rank/xgb_feature_importance.csv
data/rank/ranked_top50.csv
```

## 运行命令

```bash
python scripts/run_spark_rank_stage.py
```

本次运行成功完成三个阶段：

```text
Export Spark rank features
Train XGBoost rank model
Predict XGBoost Top50 rankings
```

Windows 下 Spark 退出时出现过少量子进程清理提示，但脚本返回码为 0，三个阶段均完成并通过质量校验。

## rank_train.csv 行数

```text
rank_train.csv: 87134
positive samples: 48217
negative samples: 38917
```

训练标签规则：

```text
rating >= 4.0 -> label = 1
rating <= 3.0 -> label = 0
```

## rank_candidates.csv 行数

```text
rank_candidates.csv: 59014
candidate positive labels: 96
candidate negative labels: 58918
```

候选集来自：

```text
data/recall/merged_recall_candidates.csv
```

## 特征数量

```text
feature count: 31
```

特征包括用户侧、电影侧、交叉特征和召回特征，具体列记录在：

```text
data/rank/rank_feature_columns.json
models/xgb_rank_feature_columns.json
```

## XGBoost 训练指标

```text
train rows: 69707
valid rows: 17427
train AUC: 0.881401
valid AUC: 0.873056
train accuracy: 0.795630
valid accuracy: 0.788948
train logloss: 0.423833
valid logloss: 0.437016
```

模型路径：

```text
models/xgb_rank_model_spark.json
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

## ranked_top50.csv 行数

```text
ranked_top50.csv: 30500
user count: 610
movie count: 1967
average recommendations per user: 50.0000
max recommendations per user: 50
```

## 示例精排结果前 10 行

```text
userId movieId rank_position rank_score label als_score itemcf_score merged_recall_score genre_match_score movie_avg_rating
1      7122    1             0.99890721 0     5.007726  0.000000     0.667298            0.666667          5.0
1      3379    2             0.99888629 0     5.208017  0.000000     0.689988            1.000000          4.5
1      26073   3             0.99884099 0     5.023952  0.000000     0.669136            0.500000          5.0
1      26928   4             0.99875212 0     5.023952  0.000000     0.669136            0.666667          5.0
1      5490    5             0.99871492 0     5.130653  0.000000     0.681224            1.000000          5.0
1      7071    6             0.99871266 0     5.023952  0.000000     0.669136            1.000000          5.0
1      74226   7             0.99869233 0     5.023952  0.000000     0.669136            0.500000          5.0
1      33649   8             0.99866688 0     5.296398  0.000000     0.700000            0.666667          5.0
1      27523   9             0.99854785 0     5.037697  0.000000     0.670693            0.500000          5.0
1      5328    10            0.99854785 0     4.986543  0.000000     0.664898            0.500000          5.0
```

## 测试结果

已执行：

```bash
pytest tests/test_spark_feature_export.py
pytest tests/test_train_from_spark_features.py
pytest tests/test_predict_from_spark_features.py
```

结果：

```text
tests/test_spark_feature_export.py: 2 passed
tests/test_train_from_spark_features.py: 2 passed
tests/test_predict_from_spark_features.py: 2 passed
```

pytest 中有 `pytest_asyncio` 默认配置的弃用提醒，不影响本阶段测试结果。

## 在线链路说明

本阶段没有修改：

```text
FastAPI 推荐接口
Vue 前端
在线召回 / 排序服务
现有 FeaturePipeline
现有线上模型文件 xgb_rank_model.json
```

本阶段新增的 `xgb_rank_model_spark.json` 是 Spark 离线排序模型，当前只是旁路产物。

## 下一步建议

下一阶段可以优先接：

```text
1. spark_offline_eval.py：基于 test_ratings.csv 评估 Recall@K、Precision@K、NDCG@K。
2. spark_mmr_rerank.py：在 ranked_top50.csv 基础上做多样性重排。
3. online bridge 设计：评估是否将 Spark 精排模型接入现有 FastAPI，但先保持灰度开关。
```

建议先做离线评估，再决定是否接入在线链路，这样可以用指标确认新链路确实优于当前版本。
