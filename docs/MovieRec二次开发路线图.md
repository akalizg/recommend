# MovieRec 二次开发路线图

## 总体目标

在当前已经跑通的 MovieRec 系统基础上，逐步升级为：

```text
基于 Spark 离线计算、FAISS 向量召回、XGBoost 精排的电影多阶段推荐系统
```

开发原则：

1. 先离线，后在线。
2. 先旁路产物，后接入主链路。
3. 每一步都有可验证输出。
4. 保留当前可运行系统，避免一次性大改。

## 阶段路线

### 第一步：实现 `spark_preprocess.py`

目标：

- 使用 Spark DataFrame 读取 MovieLens 原始 CSV。
- 完成去重、缺失值处理、类型转换、评分归一化、genres 拆分、年份提取。

输出：

- `data/processed/ratings_clean.csv`
- `data/processed/movies_clean.csv`
- `data/processed/movie_tags.csv`

验证：

- 行数合理。
- `movieId`、`userId` 类型正确。
- 与当前 `FeaturePipeline` 清洗结果口径一致。

### 第二步：实现 `spark_train_test_split.py`

目标：

- 按用户时间线划分训练集和测试集。
- 每个用户最后一次评分进入测试集，其余评分进入训练集。

输出：

- `data/processed/train_ratings.csv`
- `data/processed/test_ratings.csv`

验证：

- 每个有效用户测试集最多一条记录。
- 训练集和测试集无重复评分记录。

### 第三步：实现 `spark_build_profile.py`

目标：

- 构建用户画像和电影画像。
- 为排序、解释、评估提供稳定离线特征。

输出：

- `data/features/user_profile.csv`
- `data/features/movie_profile.csv`

验证：

- 用户画像包含评分数量、均分、标准差、偏好类型、偏好年代、活跃度。
- 电影画像包含均分、评分数、热度、类型、年份、tag 文本。

### 第四步：实现 `spark_als_train.py`

目标：

- 使用 Spark MLlib ALS 训练协同过滤模型。
- 导出 user factors、movie factors 和 ALS 召回结果。

输出：

- `data/factors/user_factors.csv`
- `data/factors/movie_factors.csv`
- `data/recall/als_recall.csv`
- `models/spark_als/`

验证：

- factor 维度为 64。
- movie factors 能覆盖主要电影。
- ALS recall 每个用户有 TopN 候选。

### 第五步：实现 `spark_export_faiss_vectors.py`

目标：

- 将 Spark ALS 的 `movie_factors.csv` 转为 FAISS 可读取的 NumPy 文件。

输出：

- `data/faiss/movie_vectors.npy`
- `data/faiss/movie_ids.npy`

验证：

- `movie_vectors.shape[0] == movie_ids.shape[0]`。
- 向量维度与 FAISS 配置一致。
- 向量已归一化，适合当前 FAISS inner product 检索。

### 第六步：让原 FAISS 构建脚本读取 Spark ALS 输出

目标：

- 新增兼容构建入口或参数，允许 FAISS 使用 Spark ALS movie vectors。
- 保留当前 `EmbeddingService` 向量构建方式作为兜底。

可能改动：

- 新增 `scripts/build_faiss_from_spark_vectors.py`。
- 或扩展 `scripts/build_index.py` 增加可选参数。

验证：

- 能成功生成 `models/faiss_hnsw.index`。
- `/recommend/{user_id}` 仍可正常返回。

### 第七步：实现 `spark_itemcf_recall.py`

目标：

- 基于用户-电影共现行为计算 ItemCF 相似度。
- 生成 ItemCF 用户候选集。

输出：

- `data/recall/itemcf_recall.csv`

验证：

- 相似度公式正确。
- 每个用户候选去除了已看电影。
- 与 ALS/FAISS 召回形成互补。

### 第八步：实现 `spark_feature_export.py`

目标：

- 融合用户画像、电影画像、ALS 召回、ItemCF 召回、后续 FAISS 召回。
- 导出 XGBoost 训练和候选排序特征。

输出：

- `data/rank/rank_train.csv`
- `data/rank/rank_candidates.csv`

验证：

- 特征列齐全。
- label 口径明确。
- 缺失值有统一填充策略。

### 第九步：让 XGBoost 使用 Spark 导出的增强特征

目标：

- 从 `data/rank/rank_train.csv` 训练 XGBoost。
- 加入 ALS、ItemCF、FAISS 多路召回分数和召回来源数量。

可能改动：

- 新增 `rank/train_from_spark_features.py`。
- 或扩展 `rank/train.py` 支持 CSV 特征输入。

验证：

- 离线 RMSE/MAE 或排序指标可输出。
- 原推荐接口不回退。

### 第十步：新增 MMR 重排

目标：

- 在 XGBoost 精排后增加多样性重排。
- 降低结果中过度相似电影的比例。

验证：

- 推荐列表类型更丰富。
- 相关性损失可控。

### 第十一步：新增推荐效果评估指标

目标：

- 基于 `test_ratings.csv` 增加 Recall@K、Precision@K、NDCG@K、HitRate@K。

输出：

- `data/eval/*.csv`
- 或终端评估报告。

### 第十二步：新增推荐理由

目标：

- 根据类型匹配、相似电影、热门趋势、用户偏好生成推荐理由。

示例：

- 因为你喜欢 `Drama` 和 `Crime`。
- 与你高分评价的电影相似。
- 近期高评分热门电影。

### 第十三步：新增用户反馈闭环

目标：

- 支持喜欢、不喜欢、已看、不感兴趣等反馈。
- 将反馈写入离线数据源，供 Spark 后续批处理使用。

### 第十四步：新增 A/B 实验

目标：

- 支持不同召回/排序策略分桶。
- 记录曝光、点击、反馈指标。

### 第十五步：新增 Prometheus + Grafana 监控

目标：

- 监控接口耗时、推荐缓存命中率、召回候选数量、错误率。

### 第十六步：完善 Vue 页面

目标：

- 增加推荐理由、反馈按钮、筛选排序、实验展示、用户偏好解释。

## 当前阶段完成标准

第一阶段只要求：

1. 完成原项目推荐链路分析。
2. 完成 Spark 接入设计。
3. 新增 `spark_jobs/` 脚本骨架。
4. 新增本路线图。

第一阶段不要求：

1. 不训练 Spark ALS。
2. 不改 FastAPI 推荐接口。
3. 不改 Vue 前端。
4. 不重建 FAISS。
5. 不训练 XGBoost。
