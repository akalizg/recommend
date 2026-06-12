# Spark 排序特征导出说明

## 脚本路径

```text
spark_jobs/spark_feature_export.py
```

该脚本是离线旁路任务，只生成 XGBoost 精排可用的训练集和候选集特征，不修改 FastAPI 接口、Vue 前端或当前在线推荐链路。

## 输入文件

```text
data/features/user_profile.csv
data/features/movie_profile.csv
data/recall/merged_recall_candidates.csv
data/processed/train_ratings.csv
data/processed/test_ratings.csv
```

`user_profile.csv` 和 `movie_profile.csv` 由 Spark 画像阶段生成。用户画像只基于训练集构建，避免测试集泄漏；`test_ratings.csv` 仅用于给候选集打离线评估标签。

## 输出文件

```text
data/rank/rank_train.csv
data/rank/rank_candidates.csv
data/rank/rank_feature_columns.json
```

`rank_train.csv` 用于训练 XGBoost；`rank_candidates.csv` 用于对召回候选集做精排预测；`rank_feature_columns.json` 记录实际进入模型的数值特征列。

## 特征来源

排序特征由四类信息融合而来：

```text
用户画像
电影画像
用户-电影交叉特征
多路召回分数和命中标记
```

## 用户侧特征

```text
user_rating_count
user_avg_rating
user_rating_std
user_min_rating
user_max_rating
active_level_code
```

`active_level_code` 编码规则：

```text
low = 0
medium = 1
high = 2
unknown = -1
```

## 电影侧特征

```text
movie_avg_rating
movie_rating_count
movie_rating_std
movie_popularity
movie_year
movie_decade_code
genre_count
tag_count
```

`movie_decade_code` 从 `decade` 或 `year` 转换，例如 `1990s -> 1990`，未知值为 `-1`。

## 交叉特征

```text
genre_match_score
decade_match_score
user_movie_score_gap
```

`genre_match_score` 计算用户偏好类型与电影类型的交集占比：

```text
intersection(favorite_genres, movie_genres) / movie genre_count
```

`decade_match_score` 表示电影年代是否出现在用户偏好年代中。`user_movie_score_gap` 表示用户平均评分和电影平均评分的绝对差。

## 召回特征

```text
als_score
itemcf_score
embedding_score
lightgcn_score
content_score
hot_score
is_als_recall
is_itemcf_recall
is_embedding_recall
is_lightgcn_recall
is_content_recall
is_hot_recall
recall_source_count
merged_recall_score
```

当前已接入 ALS 和 ItemCF，其余通道字段保留为后续扩展位，缺失值统一填充为 0。

## Label 构造方式

`rank_train.csv` 基于 `train_ratings.csv` 构造：

```text
rating >= 4.0 -> label = 1
rating <= 3.0 -> label = 0
```

负样本最多控制为正样本的 3 倍。本次数据中负样本少于上限，因此保留全部负样本。

`rank_candidates.csv` 基于 `merged_recall_candidates.csv` 构造：

```text
若 userId + movieId 出现在 test_ratings.csv 且 rating >= 4.0 -> label = 1
否则 label = 0
```

候选集标签只用于后续离线评估，不代表线上真实反馈。

## 缺失值处理

所有数值特征、召回分数、召回标记和 label 缺失值统一填充为 0。字符串字段如 `genres`、`favorite_genres`、`tag_text` 不进入模型特征列。

## 运行命令

```bash
python spark_jobs/spark_feature_export.py
```

也可以显式指定路径：

```bash
python spark_jobs/spark_feature_export.py \
  --user-profile data/features/user_profile.csv \
  --movie-profile data/features/movie_profile.csv \
  --merged-recall data/recall/merged_recall_candidates.csv \
  --train-ratings data/processed/train_ratings.csv \
  --test-ratings data/processed/test_ratings.csv \
  --output-dir data/rank
```

## 质量校验结果

本次运行结果：

```text
user_profile rows: 610
movie_profile rows: 9742
merged recall rows: 59014
train rating rows: 100226
test rating rows: 610
rank_train rows: 87134
rank_candidates rows: 59014
positive train samples: 48217
negative train samples: 38917
candidate positive labels: 96
candidate negative labels: 58918
feature columns: 31
```

已校验：

```text
rank_train.csv 存在
rank_candidates.csv 存在
rank_feature_columns.json 存在
label 只包含 0 和 1
训练集正样本数量大于 0
特征列全部为数值列
候选集行数与 merged_recall_candidates.csv 一致
```
