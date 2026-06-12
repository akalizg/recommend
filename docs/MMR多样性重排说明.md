# MMR 多样性重排说明

## 脚本路径

```text
rank/mmr_rerank.py
```

该脚本读取 XGBoost 精排后的 Top50 结果，基于电影类型相似度进行标准 MMR 多样性重排，输出每个用户 Top10。当前阶段只生成离线产物，不接入 FastAPI 或 Vue。

## 输入文件

```text
data/rank/ranked_top50.csv
data/features/movie_profile.csv
```

`ranked_top50.csv` 提供 XGBoost 的 `rank_score`；`movie_profile.csv` 提供电影 `genres` 和 `movie_rating_count`。

## 输出文件

```text
data/rank/ranked_top10_mmr.csv
```

输出字段：

```text
userId
movieId
rank_position
rank_score
mmr_score
label
als_score
itemcf_score
merged_recall_score
recall_source_count
genre_match_score
movie_avg_rating
movie_rating_count
movie_popularity
```

## MMR 原理

MMR 用于在相关性和多样性之间做折中。每次从剩余候选中选择一个电影，既考虑它自身的相关性，也惩罚它与已选电影的相似度。

## 标准 MMR 公式

```text
MMR(i) = lambda_rel * relevance(i)
       - (1 - lambda_rel) * max_similarity(i, selected)
```

本阶段：

```text
relevance(i) = XGBoost rank_score
lambda_rel = 0.7
```

`lambda_rel` 越大，越偏向相关性；越小，越偏向多样性。

## 相似度计算方法

电影之间的相似度使用类型 Jaccard：

```text
genre_jaccard_similarity = intersection(genres_i, genres_j) / union(genres_i, genres_j)
```

如果电影类型为空，相似度记为 0。

## 运行命令

```bash
python rank/mmr_rerank.py
```

也可以指定参数：

```bash
python rank/mmr_rerank.py \
  --ranked data/rank/ranked_top50.csv \
  --movie-profile data/features/movie_profile.csv \
  --output data/rank/ranked_top10_mmr.csv \
  --top-n 10 \
  --lambda-rel 0.7
```

## 运行结果统计

本次运行结果：

```text
ranked_top50 rows: 30500
user count: 610
movie count: 1967
topN: 10
lambda_rel: 0.7
output rows: 6100
average recommendations per user: 10.0000
average diversity score: 0.909618
```

## 质量校验结果

已校验：

```text
ranked_top10_mmr.csv 存在
每个用户推荐数量不超过 10
rank_position 从 1 开始
mmr_score 非空
输出字段完整
输出用户数量合理
```

## 长尾说明

本阶段没有加入长尾推荐、`long_tail_score`、`novelty_score`、`is_long_tail_movie` 或 LongTailRatio 指标。当前目标仍然是标准电影个性化推荐链路中的多样性重排。
