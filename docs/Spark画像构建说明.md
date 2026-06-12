# Spark 画像构建说明

## 脚本路径

```text
spark_jobs/spark_build_profile.py
```

## 输入文件

```text
data/processed/train_ratings.csv
data/processed/movies_clean.csv
data/processed/movie_tags.csv
```

用户画像只读取 `train_ratings.csv`，不读取 `test_ratings.csv`。

## 输出文件

```text
data/features/user_profile.csv
data/features/movie_profile.csv
```

## 用户画像字段说明

| 字段 | 说明 |
| --- | --- |
| `userId` | 用户 ID |
| `user_rating_count` | 训练集中评分数量 |
| `user_avg_rating` | 平均评分 |
| `user_rating_std` | 评分标准差，缺失填 0 |
| `user_min_rating` | 最低评分 |
| `user_max_rating` | 最高评分 |
| `favorite_genres` | 高分电影中出现最多的 Top5 类型，`|` 拼接 |
| `favorite_decades` | 高分电影中出现最多的年代，`|` 拼接 |
| `active_level` | `low`、`medium`、`high` |
| `high_rating_movie_ids` | 评分 >= 4 的 TopN 电影 ID，`|` 拼接 |
| `recent_movie_ids` | 最近评分 TopN 电影 ID，`|` 拼接 |

## 电影画像字段说明

| 字段 | 说明 |
| --- | --- |
| `movieId` | 电影 ID |
| `title` | 原始标题 |
| `clean_title` | 去年份后的标题 |
| `year` | 上映年份 |
| `decade` | 年代，例如 `1990s` |
| `genres` | 类型字符串，`|` 拼接 |
| `genre_count` | 类型数量 |
| `movie_avg_rating` | 训练集平均评分 |
| `movie_rating_count` | 训练集评分次数 |
| `movie_rating_std` | 训练集评分标准差 |
| `movie_popularity` | `movie_avg_rating * log(movie_rating_count + 1)` |
| `tag_text` | 所有标签文本，`|` 拼接 |
| `tag_count` | 标签数量 |

未在训练集中出现评分的电影，评分统计字段填 0。

## 为什么只使用训练集构建用户画像

用户画像如果读取 `test_ratings.csv`，会把评估目标提前泄漏给训练和召回阶段。当前脚本只使用训练集行为，保证后续 ALS、ItemCF、排序评估都可以模拟“用历史预测未来”。

## 运行命令

```bash
python spark_jobs/spark_build_profile.py
```

指定路径：

```bash
python spark_jobs/spark_build_profile.py --train data/processed/train_ratings.csv --movies data/processed/movies_clean.csv --tags data/processed/movie_tags.csv --output-dir data/features
```

## 运行结果统计

当前 MovieLens small 产物统计：

```text
train ratings rows: 100226
movies rows: 9742
tags rows: 25624
user profile rows: 610
movie profile rows: 9742
valid users: 610
valid movies: 9701
average user rating count: 164.3049
average movie rating count: 10.2880
```

Top genres 示例：

```text
drama, comedy, thriller, action, romance
```

## 质量校验结果

脚本会检查：

1. `user_profile.csv` 存在。
2. `movie_profile.csv` 存在。
3. `userId` 不为空。
4. `movieId` 不为空。
5. user profile 行数等于训练集有效用户数。
6. movie profile 覆盖 `movies_clean.csv` 中的电影。
7. 不读取 `test_ratings.csv`。

当前运行结果：通过。
