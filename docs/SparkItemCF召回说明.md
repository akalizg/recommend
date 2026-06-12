# Spark ItemCF 召回说明

## 脚本路径

```text
spark_jobs/spark_itemcf_recall.py
```

## 输入文件

```text
data/processed/train_ratings.csv
```

## 输出文件

```text
data/recall/itemcf_recall.csv
```

## 高分电影定义

```text
rating >= 4.0
```

## 共现计算方法

脚本只使用训练集，先构建：

```text
userId -> liked movieIds
```

然后按用户内喜欢电影两两配对，统计电影共现次数。

## 相似度公式

```text
sim(i, j) = common_users(i, j) / sqrt(user_count(i) * user_count(j))
```

其中：

```text
common_users(i, j): 同时喜欢 i 和 j 的用户数
user_count(i): 喜欢 i 的用户数
user_count(j): 喜欢 j 的用户数
```

## 用户候选生成方式

对每个用户：

1. 取训练集高分电影。
2. 查找这些电影的 Top 相似电影。
3. 按候选电影聚合相似度分数。
4. 过滤训练集中已评分电影。
5. 每个用户保留 TopN。

## 如何过滤已评分电影

脚本将候选 `(userId, movieId)` 与训练集已评分 `(userId, movieId)` 做 `left_anti` join，确保输出尽量不包含训练集中已评分电影。

## 性能控制

默认参数：

```text
top_sim = 50
top_n = 50
min_rating = 4.0
max_liked_per_user = 100
```

`max_liked_per_user` 用于限制超活跃用户参与共现的高分电影数量，避免本地 Spark 堆内存被共现对撑爆。

## 运行结果统计

当前运行结果：

```text
train rows: 100226
valid users: 610
liked interactions: 30521
movie count: 4575
co-occurrence pair count: 1328530
item similarity rows: 221786
itemcf recall rows: 30450
average recall per user: 50.0000
```

## 质量校验结果

当前校验通过：

1. `itemcf_recall.csv` 已生成。
2. 字段包含 `userId,movieId,recall_type,recall_score`。
3. `recall_type` 全部为 `itemcf`。
4. 每个用户推荐数不超过 TopN。
5. `recall_score` 非空。
6. 训练集中已评分电影已过滤。
