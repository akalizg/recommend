# Spark ALS 训练说明

## 脚本路径

```text
spark_jobs/spark_als_train.py
```

## 输入文件

```text
data/processed/train_ratings.csv
```

## 输出文件

```text
data/factors/user_factors.csv
data/factors/movie_factors.csv
data/recall/als_recall.csv
models/spark_als/
```

## ALS 参数

脚本默认参数：

```text
rank = 64
maxIter = 15
regParam = 0.1
coldStartStrategy = drop
nonnegative = false
implicitPrefs = false
topN = 100
```

统一运行脚本为了本地开发速度使用：

```text
rank = 32
maxIter = 8
topN = 50
```

测试脚本使用更轻参数：

```text
rank = 16
maxIter = 3
topN = 20
```

## user_factors 字段说明

```text
userId
features
```

`features` 是 `|` 分隔的浮点向量，维度等于 ALS rank。

## movie_factors 字段说明

```text
movieId
features
```

`features` 是 `|` 分隔的浮点向量，维度等于 ALS rank。

## als_recall 字段说明

```text
userId
movieId
recall_type
recall_score
```

其中：

```text
recall_type = als
recall_score = ALS prediction score
```

## 如何过滤已评分电影

脚本使用 `recommendForAllUsers(topN + 100)` 生成较宽候选，再与训练集 `(userId, movieId)` 做 `left_anti` join，去除训练集中已经评分的电影。过滤后按 `recall_score desc, movieId asc` 排序，每个用户保留 TopN。

## 运行命令

```bash
python spark_jobs/spark_als_train.py
```

指定参数：

```bash
python spark_jobs/spark_als_train.py --train data/processed/train_ratings.csv --factors-dir data/factors --recall-dir data/recall --model-dir models/spark_als --rank 32 --max-iter 8 --reg-param 0.1 --top-n 50
```

## 运行结果统计

当前统一运行脚本参数下：

```text
train rows: 100226
user count: 610
movie count: 9701
rank: 32
maxIter: 8
regParam: 0.1
topN: 50
user factors rows: 610
movie factors rows: 9701
als recall rows: 30369
average recall per user: 49.8670
```

## 质量校验结果

脚本会检查：

1. `user_factors.csv` 存在。
2. `movie_factors.csv` 存在。
3. `als_recall.csv` 存在。
4. `models/spark_als/` 存在。
5. factors 维度等于 rank。
6. `recall_type` 全部为 `als`。
7. 每个用户推荐数不超过 TopN。
8. `recall_score` 非空。
9. 推荐结果不包含用户训练集中已评分电影。

当前运行结果：通过。

## Python 3.13 兼容说明

PySpark 3.5 的 `pyspark.ml` 在 Python 3.13 下仍会导入 `distutils.version.LooseVersion`。脚本内置了一个最小兼容 shim，只在导入 PySpark MLlib 时生效，不修改系统环境。
