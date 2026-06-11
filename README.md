# 基于 Spark、FAISS、LightGCN 与在线反馈闭环的电影多阶段推荐系统技术方案

## 一、项目名称

本项目最终命名为：

**基于 Spark 离线计算、FAISS 向量召回与 XGBoost 精排的电影多阶段推荐系统**

也可以在答辩中使用更完整的名称：

**融合多路召回、图神经网络召回、实时反馈与在线实验的电影个性化推荐平台**

---

## 二、项目定位

本项目基于开源电影推荐系统 MovieRec 进行二次开发，目标不是简单实现一个电影推荐列表，而是构建一个完整的电影个性化推荐平台。

系统以 MovieLens 数据集为基础，结合 Spark 离线数据处理、ALS 协同过滤、FAISS 向量召回、ItemCF 相似电影召回、LightGCN 图召回、热门召回、XGBoost 精排、MMR 多样性重排、推荐理由生成、Redis 缓存、FastAPI 推荐接口、Vue 前端展示、用户反馈闭环、A/B 实验和 Prometheus + Grafana 监控，形成一个较完整的工业级推荐系统缩小版。

系统最终支持：

1. 用户个性化电影推荐。
2. 多路召回候选电影。
3. LightGCN 图召回增强高阶协同信号。
4. XGBoost 精排推荐结果。
5. MMR 多样性重排。
6. 推荐理由解释。
7. 用户点赞、点踩、不感兴趣反馈。
8. 离线推荐效果评估。
9. 消融实验验证各模块有效性。
10. A/B 实验对比不同推荐模型。
11. 推荐接口延迟、缓存命中率、点击率等指标监控。
12. 前端展示电影推荐、电影详情、用户画像、模型评估和实验结果。

---

## 三、系统总体架构

系统采用“离线训练 + 在线推荐 + 实时反馈 + 效果评估”的整体架构。

整体流程如下：

```text
MovieLens 数据集
ratings.csv / movies.csv / tags.csv / links.csv
        ↓
Spark 离线数据处理层
数据清洗、评分归一化、类型解析、训练测试集划分
        ↓
用户画像 / 电影画像构建
        ↓
多路召回层
Embedding 召回 + ALS 协同过滤召回 + ItemCF 召回
+ LightGCN 图召回 + 内容召回 + 热门召回
        ↓
候选集融合 Top-300
        ↓
XGBoost 精排 Top-50
        ↓
MMR 多样性重排 Top-10
        ↓
推荐理由生成
        ↓
Redis 推荐缓存
        ↓
FastAPI 推荐接口
        ↓
Vue 前端展示
        ↓
用户点击 / 点赞 / 踩 / 不感兴趣
        ↓
反馈日志写入
        ↓
Spark Streaming / Flink 更新实时用户画像
        ↓
下一轮推荐与离线训练
```

系统整体分为八层：

1. 数据层
   存储 MovieLens 原始数据、电影元数据、用户评分、用户反馈、推荐日志、模型指标和实验结果等。

2. Spark 离线处理层
   负责数据清洗、特征工程、用户画像、电影画像、训练测试集划分、ALS 训练、ItemCF 计算和排序特征导出。

3. 图召回与多路召回层
   负责从全量电影中快速召回候选电影，包括 Embedding 召回、ALS 协同过滤召回、ItemCF 召回、LightGCN 图召回、内容召回和热门召回。

4. 排序层
   使用 XGBoost 对召回候选集进行精排，后续可扩展 DeepFM / Wide&Deep 作为深度排序模型。

5. 重排层
   使用 MMR 控制推荐结果多样性，避免推荐列表过于单一。

6. 在线服务层
   使用 FastAPI 提供推荐接口、电影详情接口、用户反馈接口、评估指标接口和实验指标接口。

7. 缓存与存储层
   使用 Redis 缓存用户推荐结果和实时画像，使用 MySQL 或 SQLite 存储推荐日志、模型指标、实验结果和用户反馈。

8. 前端展示层
   使用 Vue 3 + Vite + TailwindCSS 实现电影推荐页面、用户画像页面、推荐评估页面、A/B 实验页面和系统监控页面。

---

## 四、系统使用技术与框架

### 4.1 后端服务技术

| 技术       | 用途               |
| -------- | ---------------- |
| Python   | 推荐系统核心开发语言       |
| FastAPI  | 提供推荐接口、反馈接口、评估接口 |
| Uvicorn  | FastAPI 服务运行容器   |
| Pydantic | 请求参数和响应数据校验      |
| Pytest   | 后端接口与推荐算法测试      |

---

### 4.2 前端技术

| 技术          | 用途               |
| ----------- | ---------------- |
| Vue 3       | 前端单页应用开发         |
| Vite        | 前端构建工具           |
| TailwindCSS | 页面样式与响应式布局       |
| ECharts     | 用户画像、模型指标、监控图表展示 |
| Axios       | 调用后端 API         |

---

### 4.3 推荐算法技术

| 技术                 | 用途                     |
| ------------------ | ---------------------- |
| Spark DataFrame    | 大规模数据清洗和特征处理           |
| Spark MLlib ALS    | 训练用户向量和电影向量            |
| ItemCF             | 基于用户共同行为计算相似电影         |
| FAISS HNSW         | 基于电影 Embedding 进行向量召回  |
| LightGCN           | 基于用户-电影-类型等图结构学习高阶协同信号 |
| XGBoost            | 对候选电影进行精排              |
| MMR                | 推荐结果多样性重排              |
| Popular 推荐         | 新用户和冷启动兜底              |
| Content-Based 推荐   | 基于电影类型、标签、文本内容推荐       |
| DeepFM / Wide&Deep | 后续可扩展的深度排序模型           |

---

### 4.4 实时反馈与在线学习技术

| 技术                      | 用途                                      |
| ----------------------- | --------------------------------------- |
| Redis                   | 存储实时用户画像、推荐缓存                           |
| Spark Streaming / Flink | 消费用户实时反馈，更新短期兴趣画像                       |
| Feedback Log            | 记录点击、点赞、点踩、不感兴趣等反馈                      |
| 定时离线任务                  | 周期性重训 ALS、LightGCN、XGBoost 和更新 FAISS 索引 |

说明：
系统不直接实时重训 ALS、LightGCN 或 XGBoost 主模型，而是采用“离线模型周期训练 + 在线反馈画像更新”的方式。用户实时行为先更新 Redis 中的短期兴趣画像，主模型通过每日或周期性离线任务更新。这样实现难度可控，也更符合课程项目落地要求。

---

### 4.5 存储与缓存技术

| 技术              | 用途                        |
| --------------- | ------------------------- |
| Redis           | 推荐结果缓存、实时用户画像、A/B 实验分组    |
| MySQL / SQLite  | 用户、电影、评分、推荐日志、模型指标、实验结果存储 |
| CSV / Parquet   | Spark 离线中间数据存储            |
| FAISS Index 文件  | 存储电影向量索引                  |
| Joblib / Pickle | 保存 XGBoost、特征处理器等模型文件     |

---

### 4.6 监控与部署技术

| 技术             | 用途                    |
| -------------- | --------------------- |
| Prometheus     | 采集推荐接口延迟、QPS、缓存命中率等指标 |
| Grafana        | 展示监控面板                |
| Docker         | 后端、前端、Redis、监控组件容器化   |
| Docker Compose | 一键启动系统服务              |
| FAISS GPU      | 作为大规模向量召回的后续扩展        |

---

## 五、数据处理与特征工程设计

### 5.1 使用数据

系统主要使用 MovieLens 数据集：

```text
ratings.csv：用户评分数据
movies.csv：电影基本信息
tags.csv：用户标签数据
links.csv：电影与外部平台 ID 映射
```

如果需要补充电影封面，可以通过 `links.csv` 中的 tmdbId 或 imdbId 关联 TMDB / IMDb 元数据，补充：

```text
poster_url
overview
release_date
vote_average
genres
director
actors
```

其中导演和演员信息可以用于 LightGCN 图召回中的多类型节点扩展。

---

### 5.2 Spark 数据处理任务

系统新增 `spark_jobs/` 目录：

```text
spark_jobs/
├── spark_preprocess.py
├── spark_train_test_split.py
├── spark_build_profile.py
├── spark_als_train.py
├── spark_itemcf_recall.py
├── spark_lightgcn_graph_export.py
├── spark_feature_export.py
└── spark_export_faiss_vectors.py
```

---

### 5.3 Spark 预处理内容

`spark_preprocess.py` 负责：

1. 读取 ratings、movies、tags、links。
2. 去除重复数据。
3. 处理缺失值。
4. 将 genres 拆分为多标签。
5. 从电影标题中提取年份。
6. 统计电影评分均值、评分次数和热度。
7. 统计用户评分数量、平均评分和活跃度。
8. 生成干净的中间数据。

输出：

```text
data/processed/ratings_clean.csv
data/processed/movies_clean.csv
data/processed/movie_tags.csv
```

---

### 5.4 训练测试集划分

`spark_train_test_split.py` 负责：

1. 按 userId 对评分时间排序。
2. 每个用户最后一次评分作为测试集。
3. 其他评分作为训练集。
4. 保证每个有效用户至少有训练行为。

输出：

```text
data/processed/train_ratings.csv
data/processed/test_ratings.csv
```

---

### 5.5 用户画像构建

`spark_build_profile.py` 生成用户画像：

```text
user_rating_count
user_avg_rating
user_rating_std
favorite_genres
favorite_decades
high_rating_movies
recent_rating_movies
active_level
```

示例：

```json
{
  "user_id": 1001,
  "favorite_genres": ["Sci-Fi", "Action", "Adventure"],
  "favorite_decades": ["1990s", "2000s"],
  "avg_rating": 4.2,
  "active_level": "high"
}
```

---

### 5.6 电影画像构建

电影画像包括：

```text
movie_avg_rating
movie_rating_count
movie_popularity
genres
year
tag_text
poster_url
overview
director
actors
```

电影画像主要用于：

1. 内容推荐。
2. XGBoost 排序特征。
3. 推荐理由生成。
4. 用户画像匹配。
5. LightGCN 图结构构建。
6. 前端电影详情展示。

---

## 六、推荐算法流程设计

系统采用完整的“召回 → 融合 → 排序 → 重排 → 解释 → 评估”流程。

---

## 6.1 多路召回层

召回层目标是从全量电影中快速筛选出 Top-300 候选电影。

### 6.1.1 Embedding 召回

基于 Spark ALS 生成的电影向量构建 FAISS HNSW 索引。

流程：

```text
Spark ALS 训练用户向量和电影向量
        ↓
导出 movie_factors.csv
        ↓
转换为 movie_vectors.npy
        ↓
FAISS 构建 HNSW 索引
        ↓
根据用户向量检索相似电影 Top-200
```

输出字段：

```text
user_id
movie_id
recall_type = embedding
recall_score
```

---

### 6.1.2 协同过滤召回

使用 Spark MLlib ALS 训练协同过滤模型。

输入：

```text
train_ratings.csv
```

输出：

```text
data/recall/als_recall.csv
```

推荐参数：

```text
rank = 64
maxIter = 15
regParam = 0.1
coldStartStrategy = drop
```

作用：

```text
根据用户历史评分，推荐相似用户喜欢的电影。
```

---

### 6.1.3 ItemCF 召回

基于用户共同评分行为计算电影之间的相似度。

公式：

```text
sim(i, j) = common_users(i, j) / sqrt(user_count(i) * user_count(j))
```

作用：

```text
喜欢这部电影的用户，还可能喜欢哪些电影。
```

输出：

```text
data/recall/itemcf_recall.csv
```

---

### 6.1.4 LightGCN 图召回

LightGCN 用于学习用户与电影之间更高阶的协同关系，弥补 ALS 主要建模一阶用户-物品交互的不足。

#### 图结构设计

系统构建异构推荐图，包含五类节点：

```text
用户节点 User
电影节点 Movie
导演节点 Director
演员节点 Actor
类型节点 Genre
```

图中的边包括：

```text
用户 - 电影：评分、点击、点赞、收藏等行为
电影 - 类型：电影所属类型
电影 - 导演：电影导演
电影 - 演员：电影主演
```

如果数据集中暂时缺少导演和演员信息，第一阶段可以先构建：

```text
用户 - 电影 - 类型
```

后续通过 TMDB / IMDb 元数据补充导演和演员节点。

#### LightGCN 输出

LightGCN 训练后输出：

```text
user_gcn_embedding
movie_gcn_embedding
```

召回方式：

```text
计算用户向量与电影向量相似度
召回 Top-100 图召回候选电影
```

输出字段：

```text
user_id
movie_id
recall_type = lightgcn
recall_score
```

#### 与 ALS / FAISS 的融合方式

LightGCN 结果可以通过两种方式接入多路召回：

1. 作为独立召回通道，输出 `lightgcn_recall.csv`。
2. 将 LightGCN 向量与 ALS 向量拼接或加权融合，再交给 FAISS 构建向量索引。

融合示例：

```text
final_embedding = 0.6 × als_embedding + 0.4 × lightgcn_embedding
```

或者：

```text
final_embedding = concat(als_embedding, lightgcn_embedding)
```

#### 技术亮点

LightGCN 可以学习用户-电影图中的高阶协同信号，例如“用户喜欢的电影所关联的类型、演员和导演，再影响其他相似电影的推荐”。在评分数据稀疏场景下，图召回可以增强召回覆盖能力，是系统的研究型技术亮点。

---

### 6.1.5 内容召回

基于电影类型、标签和标题文本进行相似推荐。

使用字段：

```text
title
genres
tags
year
overview
director
actors
```

方法：

```text
TF-IDF + cosine similarity
```

适用场景：

1. 新电影冷启动。
2. 用户喜欢某一类电影。
3. 根据电影详情页推荐相似电影。
4. 辅助推荐理由生成。

---

### 6.1.6 热门召回

用于新用户冷启动和召回兜底。

热门分数：

```text
hot_score = movie_avg_rating × log(movie_rating_count + 1)
```

适用场景：

1. 新用户没有评分记录。
2. 个性化召回结果不足。
3. Redis 或模型结果为空时兜底。

---

## 6.2 候选集融合

多路召回结果合并后，需要统一去重和特征补充。

融合后字段：

```text
user_id
movie_id
is_embedding_recall
is_als_recall
is_itemcf_recall
is_lightgcn_recall
is_content_recall
is_hot_recall
embedding_score
als_score
itemcf_score
lightgcn_score
content_score
hot_score
recall_source_count
```

每个用户最多保留 Top-300 候选。

候选融合策略：

```text
1. 合并各召回通道结果
2. 按 user_id + movie_id 去重
3. 保留每一路召回分数
4. 统计 recall_source_count
5. 过滤用户已评分或已明确不感兴趣电影
6. 输出 Top-300 候选集
```

---

## 6.3 XGBoost 精排

XGBoost 对候选电影进行精排，输出 Top-50。

### 排序特征

用户侧特征：

```text
user_avg_rating
user_rating_count
user_rating_std
favorite_genres
favorite_decades
active_level
```

电影侧特征：

```text
movie_avg_rating
movie_rating_count
movie_popularity
movie_year
genre_count
```

交叉特征：

```text
genre_match_score
embedding_similarity
year_preference_match
user_movie_score_gap
director_match_score
actor_match_score
```

召回特征：

```text
embedding_score
als_score
itemcf_score
lightgcn_score
content_score
hot_score
recall_source_count
```

输出：

```text
user_id
movie_id
rank_score
```

---

## 6.4 DeepFM / Wide&Deep 扩展

主线排序模型仍然使用 XGBoost，因为 XGBoost 训练速度快、可解释性强，适合课程项目落地。

同时系统预留 DeepFM / Wide&Deep 扩展接口。

DeepFM / Wide&Deep 可以使用：

```text
user_id embedding
movie_id embedding
genres multi-hot
als_score
faiss_score
lightgcn_score
movie_avg_rating
user_avg_rating
genre_match_score
```

用于预测用户点击、点赞或高评分概率。

扩展策略：

```text
当前版本：XGBoost 作为主排序模型
扩展版本：DeepFM / Wide&Deep 作为深度排序模型对比实验
```

---

## 6.5 MMR 多样性重排

XGBoost 排序后，如果直接返回 Top-10，可能出现推荐结果过于集中，比如全部是动作片或科幻片。

因此使用 MMR 进行重排。

公式：

```text
MMR(i) = λ × relevance(i) - (1 - λ) × max_similarity(i, selected)
```

参数：

```text
λ = 0.7
```

其中：

```text
relevance(i)：XGBoost 排序分数
similarity(i, selected)：候选电影与已选电影之间的相似度
```

相似度基于：

```text
genres + tags + embedding cosine similarity
```

作用：

1. 保证推荐结果相关性。
2. 提升推荐结果多样性。
3. 避免推荐列表类型过于单一。
4. 提升用户体验。

最终输出 Top-10 推荐电影。

---

## 七、推荐理由设计

系统为每部推荐电影生成推荐理由，提升可解释性和用户体验。

### 7.1 模板式推荐理由

第一阶段采用模板式规则生成推荐理由，稳定、可控、容易落地。

推荐理由规则：

| 来源          | 推荐理由                         |
| ----------- | ---------------------------- |
| 类型匹配        | 因为你经常喜欢 Action / Sci-Fi 类型电影 |
| ALS 召回      | 与你兴趣相似的用户也喜欢这部电影             |
| FAISS 召回    | 该电影与你喜欢的电影在向量空间中相似           |
| ItemCF 召回   | 喜欢你高分电影的用户也常看这部电影            |
| LightGCN 召回 | 该电影在用户-电影-类型图中与你的兴趣路径相近      |
| 内容召回        | 该电影与你喜欢的电影在类型、标签或剧情简介上相似     |
| 热门召回        | 该电影评分较高且观看人数较多               |
| MMR 重排      | 该电影可以丰富你的推荐列表，避免类型过于单一       |
| 实时反馈        | 根据你最近点赞的电影，系统提高了相关类型权重       |

示例：

```text
推荐理由：你最近高分评价了多部科幻和动作电影，该电影在类型和向量表示上与你的兴趣相似，并且在相似用户群体中评分较高。
```

另一个示例：

```text
推荐理由：因为你喜欢《Inception》这类科幻悬疑电影，系统推荐同样具有烧脑剧情和高评分表现的《Interstellar》。
```

---

### 7.2 基于电影关系的推荐理由

如果补充导演、演员和电影详情数据，可以生成更具体的理由：

```text
因为你喜欢诺兰导演的《Inception》，推荐同导演的《Interstellar》。
```

```text
因为你多次高分评价主演相同的动作电影，系统推荐这部同演员作品。
```

这种方式能提升推荐理由的可信度和可解释性。

---

### 7.3 LLM 推荐理由扩展

进阶版本可以接入本地小模型生成自然语言推荐理由。

输入信息包括：

```text
用户偏好类型
用户高分电影
候选电影类型
候选电影导演 / 演员
召回来源
排序特征
```

输出为自然语言解释。

示例输入：

```text
用户喜欢 Sci-Fi、Action；
用户高分电影包括 Inception、The Matrix；
候选电影为 Interstellar；
召回来源为 LightGCN + Content-Based；
候选电影类型为 Sci-Fi、Drama。
```

输出示例：

```text
你喜欢带有科幻设定和复杂剧情结构的电影，而《Interstellar》在题材、导演风格和叙事方式上都与你喜欢的电影相似，因此推荐给你。
```

说明：
LLM 生成推荐理由作为扩展功能，主线仍然采用模板式推荐理由，避免本地模型效果不稳定影响项目演示。

---

## 八、用户反馈闭环设计

系统支持用户对推荐结果进行反馈。

前端按钮包括：

```text
喜欢
不喜欢
不感兴趣
已看过
收藏
```

反馈接口：

```http
POST /api/feedback
```

请求示例：

```json
{
  "user_id": 1001,
  "movie_id": 260,
  "feedback_type": "like",
  "source": "recommendation",
  "rank_position": 3
}
```

反馈数据写入：

```text
feedback_logs
recommendation_logs
```

---

### 8.1 短期反馈

实时更新 Redis 中的用户短期画像：

```text
user:realtime_profile:{user_id}
```

示例：

```json
{
  "like_genres": {
    "Sci-Fi": 3,
    "Action": 2
  },
  "dislike_genres": {
    "Horror": 2
  },
  "recent_clicked_movies": [1, 50, 260]
}
```

推荐时，系统读取实时画像，对重排结果进行轻量调整。

---

### 8.2 长期反馈

离线训练时将反馈行为加入训练数据：

```text
like / favorite：强正样本
click / watched：弱正样本
dislike / not_interested：负样本
```

形成闭环：

```text
推荐曝光 → 用户反馈 → 日志记录 → 实时画像 → 离线训练 → 新推荐结果
```

---

## 九、在线学习设计

系统采用轻量在线学习策略。

不直接实时重训 ALS、LightGCN 或 XGBoost，而是采用：

```text
离线模型周期训练 + 实时反馈画像更新
```

流程：

```text
用户实时反馈
        ↓
写入 Kafka / 本地消息队列 / 日志表
        ↓
Flink 或 Spark Streaming 消费反馈
        ↓
更新 Redis 用户短期画像
        ↓
推荐重排阶段使用短期画像调整权重
```

这样实现了实时反馈，又避免实时重训模型带来的复杂性。

---

## 十、A/B 实验框架设计

系统支持简单 A/B 实验，用于对比不同推荐策略在线效果。

实验分组方式：

```text
user_id % 2 == 0 → A 组
user_id % 2 == 1 → B 组
```

实验示例：

```text
A 组：ALS + FAISS + XGBoost
B 组：ALS + FAISS + LightGCN + XGBoost + MMR
```

实验日志表：

```text
experiment_logs
```

字段：

```text
user_id
experiment_name
group_name
model_version
movie_id
rank_position
is_clicked
is_liked
is_disliked
created_at
```

评估指标：

```text
CTR
Like Rate
Dislike Rate
Average Recommendation Latency
Precision@10
Recall@10
NDCG@10
Diversity
```

前端提供 A/B 实验页面，展示不同实验组的效果对比。

---

## 十一、监控告警设计

系统接入 Prometheus + Grafana，对推荐服务进行监控。

监控指标包括：

```text
推荐接口 QPS
推荐接口平均延迟
P95 延迟
P99 延迟
Redis 缓存命中率
FAISS 召回耗时
XGBoost 排序耗时
MMR 重排耗时
推荐点击率
推荐点赞率
推荐点踩率
推荐为空次数
服务错误率
```

FastAPI 暴露监控接口：

```http
GET /metrics
```

Grafana 面板包括：

1. 推荐服务请求量。
2. 推荐接口平均耗时。
3. Redis 缓存命中率。
4. 召回 / 排序 / 重排耗时占比。
5. 推荐点击率趋势。
6. 推荐点赞率趋势。
7. 模型版本效果对比。

告警规则示例：

```text
推荐接口 P95 延迟 > 500ms
Redis 命中率 < 60%
推荐为空次数连续升高
接口错误率 > 5%
```

---

## 十二、推荐效果评估设计

推荐效果评估是系统证明算法有效性的核心模块。系统需要实现完整的离线评估 pipeline，并通过消融实验验证每一步改进是否有效。

---

### 12.1 数据切分策略

采用时间顺序切分，保证评估更接近真实推荐场景。

切分方式：

```text
按用户评分时间排序
前 80% 作为训练集
后 20% 作为测试集
```

或者在用户交互较少时采用留一法：

```text
每个用户最后一次评分作为测试集
其余评分作为训练集
```

测试集只用于最终评估，不参与模型训练。

---

### 12.2 核心评估指标

离线评估指标包括：

```text
Precision@K
Recall@K
NDCG@K
HitRate@K
Coverage
Diversity
Novelty
```

其中核心展示指标为：

```text
Precision@10
Recall@10
NDCG@10
HitRate@10
Coverage
Diversity
```

指标说明：

| 指标          | 说明                  |
| ----------- | ------------------- |
| Precision@K | 推荐列表中用户真正喜欢电影的比例    |
| Recall@K    | 用户喜欢电影中被推荐命中的比例     |
| NDCG@K      | 考虑排名位置的排序质量         |
| HitRate@K   | Top-K 中是否至少命中一个相关电影 |
| Coverage    | 推荐系统覆盖的电影比例         |
| Diversity   | 推荐列表内部多样性           |
| Novelty     | 推荐结果的新颖性，避免只推热门电影   |

---

### 12.3 模型对比实验

系统对比以下模型：

```text
Popular 热门推荐
Embedding 召回 + 简单排序
ALS 协同过滤
ItemCF 召回
LightGCN 图召回
多路召回融合
多路召回 + XGBoost 精排
多路召回 + XGBoost 精排 + MMR 重排
```

评估结果存入：

```text
model_metrics
```

前端评估页面展示：

| 模型                   | Precision@10 | Recall@10 | NDCG@10 | HitRate@10 | Coverage | Diversity |
| -------------------- | -----------: | --------: | ------: | ---------: | -------: | --------: |
| Popular              |         代码计算 |      代码计算 |    代码计算 |       代码计算 |     代码计算 |      代码计算 |
| Embedding + 简单排序     |         代码计算 |      代码计算 |    代码计算 |       代码计算 |     代码计算 |      代码计算 |
| ALS                  |         代码计算 |      代码计算 |    代码计算 |       代码计算 |     代码计算 |      代码计算 |
| ItemCF               |         代码计算 |      代码计算 |    代码计算 |       代码计算 |     代码计算 |      代码计算 |
| LightGCN             |         代码计算 |      代码计算 |    代码计算 |       代码计算 |     代码计算 |      代码计算 |
| 多路召回                 |         代码计算 |      代码计算 |    代码计算 |       代码计算 |     代码计算 |      代码计算 |
| 多路召回 + XGBoost       |         代码计算 |      代码计算 |    代码计算 |       代码计算 |     代码计算 |      代码计算 |
| 多路召回 + XGBoost + MMR |         代码计算 |      代码计算 |    代码计算 |       代码计算 |     代码计算 |      代码计算 |

---

### 12.4 消融实验设计

为了证明每一步改进都有效，系统设计消融实验。

消融实验包括：

```text
完整模型
去掉 LightGCN
去掉 ItemCF
去掉内容召回
去掉 XGBoost
去掉 MMR
只保留 Embedding 召回 + 简单排序
```

实验目的：

1. 验证多路召回是否提升 Recall@K。
2. 验证 XGBoost 是否提升 Precision@K 和 NDCG@K。
3. 验证 MMR 是否提升 Diversity。
4. 验证 LightGCN 是否在稀疏用户场景下提升召回能力。
5. 验证推荐系统每个模块对最终效果的贡献。

示例结论写法：

```text
实验结果表明，相比只使用 Embedding 召回的 baseline，多路召回提升了 Recall@10；
加入 XGBoost 后，Precision@10 和 NDCG@10 得到提升；
加入 MMR 后，推荐列表 Diversity 提升，说明重排策略能够缓解推荐结果同质化问题；
加入 LightGCN 后，稀疏用户上的 Recall@10 有提升，说明图召回能够补充高阶协同信号。
```

---

### 12.5 特征重要性分析

XGBoost 可以输出特征重要性，用于解释排序模型。

展示特征包括：

```text
als_score
embedding_score
itemcf_score
lightgcn_score
movie_avg_rating
movie_popularity
genre_match_score
recall_source_count
user_avg_rating
```

该模块用于说明：

```text
排序模型主要依赖哪些特征
哪些召回分数对结果影响最大
用户画像和电影画像是否有效
```

这是推荐系统最有力的技术证明之一。

---

## 十三、数据库设计

系统建议使用 MySQL 或 SQLite 进行业务数据和评估结果存储。

核心表包括：

### 13.1 users 用户表

```text
user_id
username
created_at
```

### 13.2 movies 电影表

```text
movie_id
title
genres
year
poster_url
overview
tmdb_id
imdb_id
director
actors
```

### 13.3 ratings 评分表

```text
user_id
movie_id
rating
timestamp
```

### 13.4 user_profiles 用户画像表

```text
user_id
favorite_genres
favorite_decades
avg_rating
rating_count
active_level
profile_json
updated_at
```

### 13.5 movie_profiles 电影画像表

```text
movie_id
avg_rating
rating_count
popularity
genres
tag_text
profile_json
updated_at
```

### 13.6 recommendations 推荐结果表

```text
id
user_id
movie_id
rank_position
recommend_score
recommend_type
reason
model_version
created_at
```

### 13.7 recommendation_logs 推荐日志表

```text
id
user_id
movie_id
rank_position
is_exposed
is_clicked
is_liked
is_disliked
is_not_interested
created_at
```

### 13.8 feedback_logs 用户反馈表

```text
id
user_id
movie_id
feedback_type
source
rank_position
created_at
```

### 13.9 model_metrics 模型指标表

```text
id
model_name
model_version
precision_at_10
recall_at_10
ndcg_at_10
hit_rate_at_10
coverage
diversity
novelty
evaluate_time
```

### 13.10 experiment_logs A/B 实验日志表

```text
id
experiment_name
group_name
user_id
movie_id
model_version
rank_position
is_clicked
is_liked
is_disliked
created_at
```

### 13.11 ablation_metrics 消融实验结果表

```text
id
experiment_name
model_variant
removed_module
precision_at_10
recall_at_10
ndcg_at_10
hit_rate_at_10
coverage
diversity
evaluate_time
```

---

## 十四、Redis 缓存设计

Redis 主要用于推荐缓存和实时画像。

### 14.1 推荐结果缓存

```text
recommend:{user_id}
```

缓存内容：

```json
[
  {
    "movie_id": 260,
    "title": "Star Wars",
    "score": 0.96,
    "reason": "因为你喜欢科幻和冒险类型电影"
  }
]
```

TTL：

```text
30 分钟
```

---

### 14.2 实时用户画像缓存

```text
user:realtime_profile:{user_id}
```

用于记录用户最近点击、点赞、点踩、不感兴趣等行为。

---

### 14.3 A/B 实验分组缓存

```text
ab_group:{user_id}
```

用于保持用户实验组稳定。

---

## 十五、后端 API 设计

系统后端使用 FastAPI。

核心接口如下：

| 接口                          | 方法   | 功能              |
| --------------------------- | ---- | --------------- |
| /api/recommend/{user_id}    | GET  | 获取用户个性化推荐       |
| /api/movies/{movie_id}      | GET  | 获取电影详情          |
| /api/search                 | GET  | 搜索电影            |
| /api/user/profile/{user_id} | GET  | 获取用户画像          |
| /api/feedback               | POST | 提交用户反馈          |
| /api/evaluate/metrics       | GET  | 获取模型评估指标        |
| /api/evaluate/ablation      | GET  | 获取消融实验结果        |
| /api/ab/metrics             | GET  | 获取 A/B 实验指标     |
| /api/monitor/summary        | GET  | 获取系统监控摘要        |
| /metrics                    | GET  | Prometheus 指标接口 |

推荐接口流程：

```text
请求 /api/recommend/{user_id}
        ↓
检查 Redis 缓存
        ↓
缓存命中：直接返回
        ↓
缓存未命中：执行召回、排序、重排
        ↓
生成推荐理由
        ↓
写入 Redis
        ↓
返回推荐结果
```

---

## 十六、前端功能页面设计

前端使用 Vue 3 开发，整体设计成电影推荐平台。

---

### 16.1 首页推荐页

功能：

1. 展示用户个性化推荐 Top-10。
2. 展示热门电影。
3. 展示推荐理由。
4. 支持点赞、点踩、不感兴趣、已看过。
5. 点击电影进入详情页。

卡片内容：

```text
电影封面
电影名称
年份
类型
推荐分数
推荐理由
反馈按钮
```

---

### 16.2 电影搜索页

功能：

1. 按电影名称搜索。
2. 按类型筛选。
3. 按年份筛选。
4. 展示搜索结果。
5. 支持进入电影详情页。

---

### 16.3 电影详情页

功能：

1. 展示电影基础信息。
2. 展示电影类型、年份、封面、简介。
3. 展示相似电影推荐。
4. 展示用户评分入口。
5. 展示推荐理由。
6. 支持收藏、点赞、点踩。

---

### 16.4 用户画像页

功能：

1. 展示用户偏好类型。
2. 展示用户评分分布。
3. 展示用户喜欢的电影年代。
4. 展示历史高分电影。
5. 展示实时兴趣变化。

可视化图表：

```text
类型偏好雷达图
评分分布柱状图
年代偏好折线图
近期兴趣标签云
```

---

### 16.5 推荐效果评估页

功能：

1. 展示不同模型 Precision@10。
2. 展示不同模型 Recall@10。
3. 展示不同模型 NDCG@10。
4. 展示 HitRate@10、Coverage、Diversity。
5. 展示 XGBoost 特征重要性。
6. 展示模型版本对比。

---

### 16.6 消融实验页面

功能：

1. 展示完整模型和各消融版本。
2. 展示去掉 LightGCN 后的指标变化。
3. 展示去掉 XGBoost 后的指标变化。
4. 展示去掉 MMR 后 Diversity 的变化。
5. 输出实验结论，证明各模块有效。

---

### 16.7 A/B 实验页面

功能：

1. 展示当前实验列表。
2. 展示 A 组和 B 组模型。
3. 展示点击率、点赞率、点踩率。
4. 展示 Precision@10、Diversity 对比。
5. 展示实验结论。

---

### 16.8 系统监控页面

功能：

1. 展示推荐接口 QPS。
2. 展示接口平均延迟。
3. 展示 Redis 命中率。
4. 展示 FAISS 召回耗时。
5. 展示 XGBoost 排序耗时。
6. 展示推荐点击率。
7. 展示异常告警状态。

---

### 16.9 后台管理页面

功能：

1. 电影数据管理。
2. 用户数据管理。
3. 推荐结果管理。
4. 用户反馈管理。
5. 模型指标管理。
6. 消融实验结果管理。
7. A/B 实验管理。
8. 监控指标查看。

---

## 十七、完整推荐请求流程

一次完整推荐请求流程如下：

```text
用户打开首页
        ↓
Vue 调用 /api/recommend/{user_id}
        ↓
FastAPI 接收请求
        ↓
查询 Redis：recommend:{user_id}
        ↓
如果命中，直接返回推荐列表
        ↓
如果未命中，读取用户画像和实时画像
        ↓
FAISS Embedding 召回 Top-200
        ↓
ALS / ItemCF / LightGCN / 内容 / 热门召回补充候选
        ↓
候选集去重与融合
        ↓
构建排序特征
        ↓
XGBoost 对候选电影打分
        ↓
取 Top-50
        ↓
MMR 多样性重排
        ↓
生成 Top-10
        ↓
生成推荐理由
        ↓
写入 Redis
        ↓
返回 Vue 前端
        ↓
用户点击 / 点赞 / 点踩 / 不感兴趣
        ↓
写入 feedback_logs 和 recommendation_logs
        ↓
更新 Redis 实时用户画像
        ↓
进入下一轮推荐闭环
```

---

## 十八、项目实现优先级

### 18.1 必须完成

```text
Spark 数据处理
Spark ALS
FAISS Embedding 召回
ItemCF 召回
热门召回
XGBoost 精排
MMR 重排
离线推荐效果评估
消融实验
推荐理由
用户反馈闭环
Vue 推荐页面
Vue 评估页面
Redis 推荐缓存
```

---

### 18.2 尽量完成

```text
LightGCN 图召回
A/B 实验框架
Prometheus + Grafana 监控
用户画像页面
电影封面补充
推荐日志管理
特征重要性展示
消融实验页面
```

---

### 18.3 扩展预留

```text
DeepFM / Wide&Deep
FAISS GPU
LLM 推荐理由生成
Flink 完整实时训练
模型版本自动切换
A/B 实验自动决策
```

---

## 十九、评分项对应关系

| 评分项      | 本系统对应实现                                                                          |
| -------- | -------------------------------------------------------------------------------- |
| 数据处理与预处理 | Spark 清洗 MovieLens 数据、评分归一化、类型解析、训练测试划分、画像构建                                     |
| 系统设计     | Spark 离线层 + 多路召回层 + LightGCN 图召回 + XGBoost 排序层 + MMR 重排层 + FastAPI + Redis + Vue |
| Web 开发   | 首页推荐、搜索页、详情页、用户画像页、推荐评估页、消融实验页、A/B 实验页、监控页                                       |
| 推荐算法实现   | ALS、FAISS、ItemCF、LightGCN、Content-Based、Popular、XGBoost、DeepFM 扩展                |
| 召回、排序、重排 | Embedding 召回 + 协同过滤召回 + LightGCN 图召回 + 热门召回 + XGBoost 精排 + MMR 重排                |
| 数据库存储    | MySQL / SQLite 存储用户、电影、评分、推荐结果、反馈日志、模型指标、消融实验结果，Redis 缓存推荐结果                     |

---

## 二十、系统创新点

1. 多阶段推荐链路完整
   系统实现召回、融合、排序、重排完整流程，而不是简单相似度推荐。

2. Spark 离线计算增强数据处理能力
   使用 Spark 完成大规模评分数据清洗、画像构建和 ALS 训练。

3. FAISS 向量召回提升候选集检索效率
   使用电影 Embedding 构建向量索引，实现快速近似最近邻召回。

4. LightGCN 图召回引入高阶协同信号
   通过用户-电影-类型-导演-演员图结构学习高阶关系，提升稀疏场景下的召回能力。

5. XGBoost 精排提升推荐准确性
   融合用户特征、电影特征、交叉特征和召回特征进行排序。

6. MMR 重排提升推荐多样性
   避免推荐结果同质化，提高用户体验。

7. 推荐理由提升系统可解释性
   每条推荐结果给出原因，例如“因为你喜欢某类电影”或“与高分电影相似”，增强用户信任。

8. 离线评估与消融实验提供技术证明
   通过 Precision@K、Recall@K、NDCG@K 等指标评估模型，并用消融实验验证每一步改进有效。

9. 用户反馈闭环增强系统自适应能力
   用户点赞、点踩、不感兴趣等行为可以实时影响短期兴趣画像。

10. A/B 实验支持多模型效果对比
    支持不同推荐模型在线对比，展示点击率、点赞率和推荐指标差异。

11. Prometheus + Grafana 监控增强工程完整性
    可以监控推荐延迟、缓存命中率、召回耗时、排序耗时和用户反馈指标。

---

## 二十一、最终总结

本系统基于开源 MovieRec 项目进行二次开发，围绕电影推荐业务构建了一个完整的多阶段推荐平台。系统使用 MovieLens 数据集作为基础数据源，通过 Spark 完成数据清洗、用户画像、电影画像、训练测试集划分和 ALS 训练；通过 FAISS 实现基于电影向量的 Embedding 召回；通过 ALS、ItemCF、LightGCN、内容召回和热门召回构建多路候选集；通过 XGBoost 对候选电影进行精排；最后使用 MMR 对 Top-N 推荐结果进行多样性重排。

在工程实现方面，系统使用 FastAPI 提供推荐服务，Redis 缓存推荐结果和实时用户画像，Vue 前端展示推荐结果、电影详情、用户画像、推荐评估、消融实验、A/B 实验和系统监控。系统支持用户点赞、点踩、不感兴趣等反馈行为，并通过 Spark Streaming 或 Flink 更新短期兴趣画像，形成推荐闭环。

在算法验证方面，系统构建完整的离线评估 pipeline，使用 Precision@10、Recall@10、NDCG@10、HitRate@10、Coverage、Diversity 等指标评估推荐效果，并通过消融实验对比“Embedding 召回 + 简单排序”“多路召回”“多路召回 + XGBoost”“多路召回 + XGBoost + MMR”“加入 LightGCN 图召回”等不同模型版本，从而证明各模块对推荐效果的提升作用。

该系统能够较好覆盖课程评分标准中的数据处理、系统设计、Web 开发、推荐算法实现、召回排序重排和数据库存储要求，具备较强的技术深度、系统完整性、可解释性和后续扩展能力。
