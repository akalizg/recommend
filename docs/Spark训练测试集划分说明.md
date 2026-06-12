# Spark 训练测试集划分说明

## 脚本路径

```text
spark_jobs/spark_train_test_split.py
```

该脚本是 Spark 离线处理层的第二步，只负责把 `ratings_clean.csv` 划分为训练集和测试集。它不会训练 ALS，不会接入 FAISS，不会训练 XGBoost，也不会修改 FastAPI 接口或 Vue 前端。

## 输入文件

默认输入：

```text
data/processed/ratings_clean.csv
```

要求字段：

```text
userId
movieId
rating
rating_norm
timestamp
```

字段会统一转换为：

```text
userId: int
movieId: int
rating: double
rating_norm: double
timestamp: long
```

## 输出文件

默认输出目录：

```text
data/processed
```

输出文件：

```text
data/processed/train_ratings.csv
data/processed/test_ratings.csv
```

两个文件都保留字段：

```text
userId
movieId
rating
rating_norm
timestamp
```

脚本会将 Spark 默认目录输出整理成单文件 CSV，便于后续 pandas、Spark 或普通命令行工具读取。

## 划分策略

使用留一法：

```text
partitionBy(userId)
orderBy(timestamp desc, movieId desc)
```

生成：

```text
rn = row_number()
```

规则：

```text
rn = 1  -> test_ratings.csv
rn > 1  -> train_ratings.csv
```

当同一用户存在相同 `timestamp` 时，使用 `movieId desc` 作为次级排序，保证结果稳定。

## 为什么使用每个用户最后一次评分作为测试集

推荐系统通常希望模拟“用用户过去行为预测未来行为”。按时间留出每个用户最新一条评分，可以比随机切分更贴近线上场景：

1. 训练集代表用户历史。
2. 测试集代表用户后续可能喜欢的电影。
3. 每个用户都有测试样本，方便计算 Recall@K、HitRate@K、NDCG@K 等指标。

## 为什么过滤评分数量小于 2 的用户

如果某个用户只有 1 条评分，按留一法划分后，这条评分只能进入测试集，训练集中没有该用户行为，后续 ALS、画像、召回和评估都无法稳定处理。

因此脚本只保留：

```text
user_rating_count >= 2
```

并在日志中输出：

```text
filtered low-activity users
valid users
```

## 字段说明

| 字段 | 说明 |
| --- | --- |
| `userId` | MovieLens 用户 ID |
| `movieId` | MovieLens 电影 ID |
| `rating` | 原始评分 |
| `rating_norm` | 归一化评分，来自 `rating / 5.0` |
| `timestamp` | 评分时间戳 |

## 运行命令

默认运行：

```bash
python spark_jobs/spark_train_test_split.py
```

指定输入和输出目录：

```bash
python spark_jobs/spark_train_test_split.py --input data/processed/ratings_clean.csv --output-dir data/processed
```

## 运行结果统计

脚本会打印：

```text
Input file: .../data/processed/ratings_clean.csv
Output directory: .../data/processed
raw rating rows: ...
valid users: ...
filtered low-activity users: ...
filtered rating rows: ...
train rows: ...
test rows: ...
train users: ...
test users: ...
train movies: ...
test movies: ...
train/test duplicate userId+movieId+timestamp exists: False
test has at most one rating per user: True
all test users exist in train: True
train rows + test rows = filtered rows: True
wrote train_ratings.csv: True
wrote test_ratings.csv: True
```

## 质量校验结果

脚本内置以下校验，失败会抛出清晰错误：

1. `train_ratings.csv` 存在。
2. `test_ratings.csv` 存在。
3. 训练集和测试集没有重复的 `userId + movieId + timestamp` 记录。
4. 测试集中每个用户最多只有一条评分。
5. 测试集中的用户必须在训练集中也存在。
6. 训练集和测试集字段完整。
7. 训练集行数 + 测试集行数 = 过滤后评分行数。

## 下一步如何接 spark_build_profile.py

下一阶段实现：

```text
spark_jobs/spark_build_profile.py
```

它应该读取：

```text
data/processed/train_ratings.csv
data/processed/movies_clean.csv
data/processed/movie_tags.csv
```

并输出：

```text
data/features/user_profile.csv
data/features/movie_profile.csv
```

其中：

1. 用户画像只基于训练集行为，避免测试集泄漏。
2. 电影画像可以融合训练集评分统计、电影基础信息和标签。
3. 后续 ALS、ItemCF、排序特征都应优先使用训练集与画像产物。
