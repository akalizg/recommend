# Spark 接入 MovieRec 设计说明

## 1. 当前 MovieRec 项目结构分析

当前项目已经形成一条可运行的 MovieLens 推荐链路，主要模块如下：

| 目录 | 当前职责 | 关键文件 |
| --- | --- | --- |
| `scripts/` | 数据下载、索引构建、元数据补全等离线脚本 | `scripts/build_index.py`, `scripts/download_data.py`, `scripts/enrich_movie_metadata.py` |
| `feature/` | 读取 MovieLens CSV、清洗数据、构建用户/电影特征 | `feature/pipeline.py`, `feature/user_profile.py` |
| `embedding/` | 矩阵分解训练与向量服务 | `embedding/matrix_factorization.py`, `embedding/embedding_service.py` |
| `recall/` | FAISS HNSW 向量召回 | `recall/faiss_index.py`, `recall/recall_service.py` |
| `rank/` | XGBoost 排序特征构建、模型训练、在线排序 | `rank/train.py`, `rank/rank_model.py` |
| `api/` | FastAPI 推荐、热门、详情、搜索等接口 | `api/routes.py`, `api/schemas.py` |
| `cache/` | Redis 缓存封装 | `cache/redis_cache.py` |
| `frontend/` | Vue 前端页面 | `frontend/src/views/Recommend.vue`, `frontend/src/components/MovieCard.vue` |
| `data/` | MovieLens 原始数据和后续派生数据 | `data/ml-latest-small/*.csv` |
| `models/` | 特征缓存、向量、FAISS 索引、XGBoost 模型 | `models/features.pkl`, `models/embeddings.npz`, `models/faiss_hnsw.index`, `models/xgb_rank_model.json` |
| `tests/` | API、缓存、召回相关测试 | `tests/test_api.py`, `tests/test_cache.py`, `tests/test_recall.py` |

## 2. 原项目推荐链路说明

当前完整构建链路位于 `scripts/build_index.py`：

1. `scripts/download_data.py` 下载或准备 MovieLens 数据。
2. `feature.pipeline.FeaturePipeline.run()` 读取 `ratings.csv`、`movies.csv`、`tags.csv`、`links.csv`，完成清洗、评分矩阵、电影特征、用户特征构建，并保存到 `models/features.pkl`。
3. `embedding.embedding_service.EmbeddingService.train()` 调用 `embedding.matrix_factorization.MatrixFactorization` 训练用户向量和电影向量，保存到 `models/embeddings.npz`。
4. `recall.faiss_index.FaissHNSWIndex.build()` 使用电影向量构建 FAISS HNSW 索引，保存到 `models/faiss_hnsw.index` 和 ID map。
5. `rank.train.train_rank_model()` 使用用户特征、电影特征、向量相似度、类型匹配等特征训练 XGBoost 模型，保存到 `models/xgb_rank_model.json`。

当前在线推荐链路位于 `api/routes.py` 的 `/recommend/{user_id}`：

1. 先读取 Redis 缓存。
2. `recall.recall_service.RecallService.recall()` 根据用户向量搜索 FAISS，得到候选电影。
3. `rank.rank_model.RankingService.rank()` 为候选电影构建排序特征并调用 XGBoost 打分。
4. `feature.pipeline.FeaturePipeline.get_movie_info()` 补充标题、类型、评分、海报等展示字段。
5. 结果写入 Redis 并返回给 Vue 前端。

## 3. 原项目已有模块保留判断

本阶段必须保留以下模块，不做破坏性改动：

| 模块 | 保留原因 |
| --- | --- |
| FAISS 向量召回 | 当前在线召回核心能力，毫秒级响应，后续 Spark ALS movie factors 可以接入它 |
| XGBoost 排序 | 当前精排模型已经可用，后续只增强特征输入 |
| Redis 推荐缓存 | 保证在线接口稳定和响应速度 |
| FastAPI 推荐接口 | 前端和测试已经依赖现有接口格式 |
| Vue 前端页面 | 当前系统已跑通，本阶段不改 UI |
| Docker / docker-compose | 保留当前部署方式 |
| MovieLens 数据读取逻辑 | 本地小数据模式仍然有价值，可作为 Spark 输出的兼容兜底 |
| 现有测试脚本 | 后续每次接入 Spark 输出时用于回归验证 |

## 4. 为什么要接入 Spark

当前项目使用 pandas 和本地 Python 训练链路，适合 `ml-latest-small` 规模，但当数据扩大到更多用户、电影、评分、行为日志后，会遇到这些限制：

1. pandas 单机内存压力变大。
2. 用户画像、电影画像、ItemCF 共现计算会变慢。
3. ALS 协同过滤更适合使用 Spark MLlib 这类分布式训练工具。
4. 排序训练特征需要融合多路召回、画像、统计指标，离线批处理更清晰。
5. 后续评估、A/B 实验、监控指标需要稳定的离线数据产物。

因此 Spark 的定位不是替代当前在线系统，而是作为“离线处理层”增强数据、召回和特征。

## 5. Spark 在系统中的位置

推荐系统分层如下：

```text
MovieLens CSV / 后续行为日志
        |
        v
Spark 离线处理层
  - 清洗
  - 切分训练/测试集
  - 用户画像 / 电影画像
  - ALS 向量和 ALS 召回
  - ItemCF 召回
  - XGBoost 排序特征导出
  - FAISS 可读向量导出
        |
        v
现有 Python 在线链路
  - FeaturePipeline 读取兼容数据或缓存
  - FAISS 构建/加载索引
  - XGBoost 训练/加载排序模型
  - FastAPI 提供推荐接口
  - Redis 缓存结果
  - Vue 展示结果
```

## 6. Spark 负责的任务

| 任务 | 原项目现在怎么做 | Spark 版本准备怎么做 | Spark 输出如何接回原项目 |
| --- | --- | --- | --- |
| 数据清洗 | `FeaturePipeline.load_data()` 和 `clean_data()` 用 pandas 处理 | `spark_preprocess.py` 读原始 CSV，去重、补缺失、类型转换、类型拆分、年份提取 | 输出 `data/processed/*.csv`，后续可让 `FeaturePipeline` 读取处理后数据 |
| 训练/测试集划分 | `rank/train.py` 内部用 sklearn 随机切分排序样本 | `spark_train_test_split.py` 按用户最后一次评分做测试集 | 输出 `train_ratings.csv`、`test_ratings.csv`，用于 ALS、评估、排序训练 |
| 用户画像 | `FeaturePipeline.build_user_features()` 本地聚合 | `spark_build_profile.py` 分布式聚合评分、类型、年代偏好、活跃度 | 输出 `data/features/user_profile.csv`，后续替换/增强 `user_features` |
| 电影画像 | `FeaturePipeline.build_movie_features()` 本地统计评分、热度、类型向量 | `spark_build_profile.py` 聚合评分、热度、tag_text、类型、年份 | 输出 `data/features/movie_profile.csv`，后续替换/增强 `movie_features` |
| ALS 协同过滤 | 当前是自定义矩阵分解 | `spark_als_train.py` 使用 Spark MLlib ALS 训练 user/movie factors | movie factors 通过 `spark_export_faiss_vectors.py` 输出为 `.npy` 后接入 FAISS |
| ItemCF 召回 | 当前没有独立 ItemCF 通道 | `spark_itemcf_recall.py` 基于共现计算 item similarity 和用户候选 | 输出 `data/recall/itemcf_recall.csv`，后续与 FAISS/ALS 多路召回融合 |
| 排序特征导出 | `RankingDataBuilder` 在线/训练时逐条构造特征 | `spark_feature_export.py` 批量融合画像和召回分数 | 输出 `data/rank/rank_train.csv` 和 `rank_candidates.csv`，后续供 XGBoost 训练/服务使用 |
| 评估数据生成 | 当前主要依赖测试脚本，推荐指标未系统化 | 基于 `test_ratings.csv` 和召回/排序结果计算 Recall@K、NDCG@K 等 | 后续新增 `data/eval/*.csv` 或评估脚本，不在本阶段实现 |

## 7. Spark 脚本输入和输出

| 脚本 | 作用 | 输入 | 输出 |
| --- | --- | --- | --- |
| `spark_jobs/spark_preprocess.py` | 读取原始 MovieLens 数据，生成清洗后的基础表 | `ratings.csv`, `movies.csv`, `tags.csv`, `links.csv` | `data/processed/ratings_clean.csv`, `data/processed/movies_clean.csv`, `data/processed/movie_tags.csv` |
| `spark_jobs/spark_train_test_split.py` | 按用户时间线切分训练/测试集 | `data/processed/ratings_clean.csv` | `data/processed/train_ratings.csv`, `data/processed/test_ratings.csv` |
| `spark_jobs/spark_build_profile.py` | 构建用户画像和电影画像 | `train_ratings.csv`, `movies_clean.csv`, `movie_tags.csv` | `data/features/user_profile.csv`, `data/features/movie_profile.csv` |
| `spark_jobs/spark_als_train.py` | 训练 Spark MLlib ALS 并导出 ALS 召回 | `data/processed/train_ratings.csv` | `data/factors/user_factors.csv`, `data/factors/movie_factors.csv`, `data/recall/als_recall.csv`, `models/spark_als/` |
| `spark_jobs/spark_itemcf_recall.py` | 计算 ItemCF 相似度和候选召回 | `data/processed/train_ratings.csv` | `data/recall/itemcf_recall.csv` |
| `spark_jobs/spark_feature_export.py` | 融合画像和召回结果，导出排序特征 | `user_profile.csv`, `movie_profile.csv`, `als_recall.csv`, `itemcf_recall.csv`, 后续 FAISS 召回结果 | `data/rank/rank_train.csv`, `data/rank/rank_candidates.csv` |
| `spark_jobs/spark_export_faiss_vectors.py` | 将 Spark ALS movie factors 转为 FAISS 可读向量 | `data/factors/movie_factors.csv` | `data/faiss/movie_vectors.npy`, `data/faiss/movie_ids.npy` |

## 8. Spark ALS 的 movie_factors 如何接入 FAISS

当前 FAISS 构建入口是 `recall/faiss_index.py` 的 `FaissHNSWIndex.build(embeddings, movie_ids)`，现有向量来自 `EmbeddingService.item_embeddings`。

后续 Spark 接入建议：

1. `spark_als_train.py` 输出 `data/factors/movie_factors.csv`，字段至少包含 `movieId` 和 `features`。
2. `spark_export_faiss_vectors.py` 将 `features` 转为 `float32` NumPy 矩阵，并做 L2 归一化。
3. 输出：
   - `data/faiss/movie_vectors.npy`
   - `data/faiss/movie_ids.npy`
4. 后续新增或改造一个 FAISS 构建脚本，让它读取这两个 `.npy` 文件并调用：

```python
faiss_index.build(movie_vectors, movie_ids)
```

本阶段不修改现有 FAISS 构建逻辑，只先定义输出契约。

## 9. Spark 导出的排序特征如何接入 XGBoost

当前 XGBoost 训练入口是 `rank/train.py`，其中 `RankingDataBuilder.build_training_data()` 逐条构建特征。

后续 Spark 接入建议：

1. `spark_feature_export.py` 直接输出 `data/rank/rank_train.csv`。
2. CSV 中包含 XGBoost 可直接读取的特征列和标签列，例如：
   - `user_avg_rating`
   - `user_rating_count`
   - `movie_avg_rating`
   - `movie_rating_count`
   - `movie_popularity`
   - `genre_match_score`
   - `als_score`
   - `itemcf_score`
   - `faiss_score`
   - `recall_source_count`
   - `label`
3. 后续新增 `rank/train_from_spark_features.py` 或扩展 `rank/train.py`，从 CSV 读取特征训练 XGBoost。
4. 在线 `RankingService` 仍可先保留现有实时构造方式，等候选和特征稳定后再改为读取离线候选/特征。

本阶段不训练 XGBoost，不改排序接口。

## 10. Spark ItemCF 如何作为新增召回通道

当前召回只有 FAISS 向量召回，代码位于 `recall/recall_service.py`。

ItemCF 后续接入方式：

1. `spark_itemcf_recall.py` 生成 `data/recall/itemcf_recall.csv`。
2. 推荐字段建议：
   - `userId`
   - `movieId`
   - `itemcf_score`
   - `source=itemcf`
3. 后续新增多路召回融合模块，例如 `recall/multi_recall_service.py`：
   - 读取 FAISS 在线召回结果
   - 读取 ALS 离线召回结果
   - 读取 ItemCF 离线召回结果
   - 合并去重
   - 记录 `recall_source_count`
   - 传给 XGBoost 排序

本阶段只建立 ItemCF 离线脚本骨架，不改现有 `RecallService`。

## 11. 后续开发顺序

建议按以下顺序推进：

1. 实现 `spark_preprocess.py`，先产出稳定清洗数据。
2. 实现 `spark_train_test_split.py`，建立可复现训练/测试划分。
3. 实现 `spark_build_profile.py`，把用户画像和电影画像落表。
4. 实现 `spark_als_train.py`，产出 Spark ALS factors 和 ALS 召回。
5. 实现 `spark_export_faiss_vectors.py`，把 ALS movie factors 接成 FAISS 可读 `.npy`。
6. 新增兼容脚本，让原 FAISS 构建链路可选择读取 Spark 向量。
7. 实现 `spark_itemcf_recall.py`，新增 ItemCF 召回通道。
8. 实现 `spark_feature_export.py`，导出 XGBoost 排序训练特征。
9. 让 XGBoost 使用 Spark 导出的增强特征。
10. 增加 MMR 重排、评估、推荐理由、反馈闭环、A/B 实验、监控和前端增强。

## 12. 本次不修改原系统运行逻辑的说明

本阶段只新增：

1. `spark_jobs/` 脚本骨架。
2. Spark 接入设计文档。
3. 二次开发路线图。

本阶段不做：

1. 不修改 FastAPI 推荐接口。
2. 不修改 Vue 前端页面。
3. 不训练 Spark ALS。
4. 不重建 FAISS 索引。
5. 不训练 XGBoost。
6. 不新增 MMR、A/B 实验或监控。
7. 不删除原有代码。

因此当前已经跑通的 MovieRec 系统不会被 Spark 接入设计影响。Spark 层先作为旁路离线层存在，等数据产物稳定后，再逐步接回现有 FAISS、XGBoost 和推荐服务。
