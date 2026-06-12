# Spark 多路召回融合说明

## 脚本路径

```text
spark_jobs/spark_merge_recall.py
```

## 输入文件

```text
data/recall/als_recall.csv
data/recall/itemcf_recall.csv
```

## 输出文件

```text
data/recall/merged_recall_candidates.csv
```

## 当前融合的召回通道

当前合并：

```text
ALS
ItemCF
```

后续可扩展：

```text
FAISS / LightGCN / Content / Hot
```

## 字段说明

输出字段：

```text
userId
movieId
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

当前尚未接入的通道分数填 0，对应命中标记填 0。

## 分数归一化方式

ALS 和 ItemCF 分数按每个用户内部做 min-max 归一化：

```text
normalized_score = (score - user_min_score) / (user_max_score - user_min_score)
```

如果某用户某通道分数全相同，则归一化为 1。

## merged_recall_score 公式

当前阶段：

```text
merged_recall_score = 0.6 * normalized_als_score
                    + 0.4 * normalized_itemcf_score
                    + 0.1 * recall_source_count
```

每个用户最多保留 Top100。

## 后续如何加入更多召回

新增召回只需要：

1. 输出统一 `(userId, movieId, recall_type, recall_score)`。
2. 在 merge 脚本中新增对应 score 和 is_xxx 字段。
3. 调整 `merged_recall_score` 权重。
4. 保持 `recall_source_count` 累加即可。
