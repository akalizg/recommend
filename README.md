# RecipeRec 食谱推荐系统（Food.com 个性化菜谱推荐平台）

RecipeRec 是一个基于 Food.com 数据集构建的个性化食谱推荐系统，面向“用户不知道做什么菜、想发现更符合口味和场景的食谱”这一典型需求，提供从离线训练、在线推荐、搜索详情、实时反馈到效果评估的完整推荐系统链路。

当前系统已经接入 Food.com 官方训练集、验证集和测试集划分，完成了离线推荐链路、增强排序模型对比、冷启动推荐、实时反馈闭环、前后端接口、Elasticsearch 搜索、推荐理由、图片增强、MinIO 产物同步、A/B 实验基础能力和监控指标基础能力。

## 目录

1. 项目背景
2. 项目意义
3. 数据集说明
4. 当前数据规模
5. 技术栈
6. 系统总体架构
7. 技术路线
8. 推荐流程
9. 前端页面
10. 后端接口
11. 官方测试集指标为 0 的解释
12. 全量测试效果
13. 当前已完成内容
14. 常用命令
15. 后续优化方向

## 一、项目背景

随着在线菜谱平台、健康饮食应用和生活服务平台的发展，用户面对的食谱数量越来越多。Food.com 这类平台包含大量菜谱、用户评分、评论、标签、配料、步骤、营养信息和图片链接。用户在选择食谱时通常会受到以下因素影响：

- 个人口味偏好，例如甜品、快手菜、早餐、低脂、高蛋白等。
- 做饭场景，例如工作日晚餐、聚会、健身餐、儿童餐等。
- 食材约束，例如家里已有食材、忌口、过敏、饮食习惯等。
- 时间成本，例如 15 分钟快手菜、慢炖、烘焙等。
- 营养目标，例如热量、蛋白质、糖分、钠含量等。

传统搜索只能根据关键词返回结果，例如搜索 `chicken` 或 `salad`，但它不能很好地理解用户长期偏好，也不能主动发现用户可能喜欢但没有搜索过的食谱。因此，构建一个个性化食谱推荐系统具有实际意义。

本项目的目标不是只做一个简单的“热门菜谱列表”，而是搭建一条较完整的推荐系统链路，包括：

- 离线数据处理。
- 用户画像和食谱画像。
- 多路召回。
- 向量检索。
- 图神经网络召回。
- 排序模型。
- 多样性重排。
- 推荐理由。
- 前端展示。
- 搜索服务。
- 用户反馈闭环。
- A/B 实验。
- 监控指标。

## 二、项目意义

本项目适合作为推荐系统课程设计、毕业设计或工程实践项目，主要意义包括：

1. 将推荐系统从单一算法扩展为完整工程链路。

   项目不是只训练一个 ALS 或 ItemCF 模型，而是覆盖“数据处理、召回、排序、重排、解释、服务、前端、反馈、监控”的完整流程。

2. 使用真实大规模 Food.com 数据。

   当前已经接入 Food.com 官方数据划分，训练交互接近 70 万条，食谱画像达到 17.8 万个，比小型示例数据集更接近真实推荐场景。

3. 推荐主题具有较强应用价值。

   食谱推荐可以延展到健康饮食、外卖推荐、食材搭配、健身餐推荐、营养分析、家庭菜谱助手等方向。

4. 支持多种推荐算法对比。

   当前系统包含 ALS 协同过滤、ItemCF 物品协同过滤、FAISS_HNSW 向量召回、LightGCN 图召回、内容召回、热门召回、XGBoost 排序基线、LightGBM 最优排序模型和 MMR 多样性重排，可以做消融实验和算法对比。

5. 具备继续扩展实时排序、GPU 训练和 LLM 推荐理由的空间。

   项目已经完成离线计算、在线服务、虚拟机 Spark 集群验证、Kafka 反馈事件链路、Redis 实时画像、FAISS 实时推荐缓存和 MinIO 产物同步，后续可以继续增强实时排序、GPU LightGCN、本地 Qwen 推荐理由生成等模块。

## 三、数据集说明

当前主要使用 Food.com 数据：

### 1. Food.com 原始数据

- `data/food-com/RAW_recipes.csv`
  - 231,637 条食谱。
  - 包含名称、分钟数、提交日期、标签、营养、步骤数、配料、配料数量等。

- `data/food-com/RAW_interactions.csv`
  - 1,132,367 条用户交互。
  - 包含用户、食谱、日期、评分、评论等。

### 2. Food.com 官方数据划分

项目已经接入官方划分：

- `data/interactions_train.csv`
- `data/interactions_validation.csv`
- `data/interactions_test.csv`

导入后生成：

- `data/processed/train_ratings.csv`：698,901 条训练交互。
- `data/processed/valid_ratings.csv`：7,023 条验证交互。
- `data/processed/test_ratings.csv`：12,455 条测试交互。
- `data/processed/ratings_clean.csv`：718,379 条总交互。

### 3. Food.com Enhanced V3

- `data/recipe_enhanced_v3.csv`
  - 231,637 条增强详情。
  - 补充图片链接、作者、人份、原链接、评分、评论数量等。

- `data/recipe-canonical/recipe_detail_metadata.csv`
  - 231,637 条详情页元数据。
  - 用于食谱详情页展示配料、步骤、营养、人份、作者和原链接等。

## 四、当前数据规模

官方数据划分已完成导入和全链路运行。

| 数据/产物 | 当前规模 |
| --- | ---: |
| 训练交互 `train_ratings.csv` | 698,901 |
| 验证交互 `valid_ratings.csv` | 7,023 |
| 测试交互 `test_ratings.csv` | 12,455 |
| 用户数 | 25,076 |
| 食谱画像数 | 178,265 |
| 标签/配料特征行 `movie_tags.csv` | 4,745,034 |
| ALS 召回 | 1,252,895 |
| ItemCF 召回 | 1,232,634 |
| FAISS_HNSW 召回 | 1,239,940 |
| LightGCN 召回 | 1,242,300 |
| Content 召回 | 1,242,300 |
| Hot 召回 | 1,253,800 |
| 合并召回候选 | 2,507,600 |
| LightGBM Top50 | 1,253,800 |
| MMR Top10 | 250,760 |
| 最终推荐 | 250,760 |
| ES 索引文档数 | 178,265 |

图片覆盖情况：

| 对象 | 有图数量 | 覆盖率 |
| --- | ---: | ---: |
| 食谱画像 | 41,162 / 178,265 | 约 23.09% |
| 最终推荐 | 54,283 / 250,760 | 约 21.65% |

## 五、技术栈

### 1. 后端与服务

| 技术 | 用途 |
| --- | --- |
| Python | 推荐系统核心开发语言 |
| FastAPI | 后端 API 服务 |
| Uvicorn | FastAPI 运行服务 |
| Pydantic | 请求和响应数据校验 |
| SQLite | 本地反馈、曝光、A/B 日志存储 |
| Redis | 实时用户画像和缓存基础能力 |
| Kafka | 用户反馈事件消息队列和实时闭环基础 |
| Elasticsearch | 食谱搜索和详情快速读取 |
| MinIO | 离线模型、画像、召回、排序和推荐结果产物同步 |
| Prometheus 指标格式 | 系统监控指标输出 |

### 2. 离线计算与算法

| 技术 | 用途 |
| --- | --- |
| PySpark | 数据处理、画像构建、ALS、ItemCF 等离线任务 |
| Spark MLlib ALS | 协同过滤召回和 item embedding |
| FAISS HNSW | 基于 ALS embedding 的向量近邻召回 |
| PyTorch | LightGCN 图召回训练 |
| LightGCN | 基于用户-食谱二部图的图神经网络召回 |
| scikit-learn | TF-IDF 内容召回、特征处理 |
| XGBoost | 排序基线模型 |
| LightGBM | 比较后选出的当前主排序模型 |
| Logistic Regression | 排序基线模型，用于和树模型对比 |
| pandas | 本地特征处理、召回合并、排序特征导出 |
| NumPy | 向量和矩阵处理 |

### 3. 前端

| 技术 | 用途 |
| --- | --- |
| Vue 3 | 前端单页应用 |
| Vite | 前端构建工具 |
| Axios | 请求后端 API |
| CSS / 组件化页面 | 首页、推荐页、搜索页、详情页展示 |

### 4. 工程与测试

| 技术 | 用途 |
| --- | --- |
| pytest | 单元测试和接口测试 |
| npm / Vite build | 前端构建验证 |
| PowerShell | Windows 本地运行脚本 |
| Git | 版本管理 |

## 六、系统总体架构

系统采用“离线训练 + MinIO 产物同步 + 在线推荐 + 搜索服务 + 用户反馈 + 监控评估”的整体架构。

```text
Food.com 原始数据 / 官方数据划分
        |
        v
数据转换与清洗
        |
        v
用户画像 / 食谱画像
        |
        v
多路召回
ALS / ItemCF / FAISS_HNSW / LightGCN / Content / Hot
        |
        v
召回融合 Top100
        |
        v
LightGBM 排序 Top50
        |
        v
MMR 多样性重排 Top10
        |
        v
推荐理由与图片增强
        |
        v
MinIO 离线产物同步
        |
        v
FastAPI 推荐接口
        |
        v
Vue 前端展示
        |
        v
点击 / 喜欢 / 不喜欢 / 评分 / 曝光
        |
        v
反馈日志 / A-B 实验 / 监控指标
        |
        v
Kafka 反馈事件 / Redis 实时画像 / FAISS 实时推荐缓存
```

从推荐系统工程角度看，系统可以进一步拆成以下分层架构：

```text
┌──────────────────────────────────────────────────────────────┐
│ 1. 数据层                                                     │
│ Food.com 原始食谱、官方 train/valid/test、Enhanced V3 图片详情 │
│ 用户评分、评论、反馈日志、曝光日志、A/B 实验日志              │
└──────────────────────────────────────────────────────────────┘
                              |
                              v
┌──────────────────────────────────────────────────────────────┐
│ 2. 离线特征与画像层                                           │
│ 数据清洗、ID 映射、用户画像、食谱画像、标签/配料特征、热度特征 │
│ Spark 集群任务 + pandas 本地执行实现                          │
└──────────────────────────────────────────────────────────────┘
                              |
                              v
┌──────────────────────────────────────────────────────────────┐
│ 3. 多路召回层                                                 │
│ ALS 协同过滤、ItemCF、FAISS_HNSW、LightGCN、Content、Hot       │
│ 目标：从 17.8 万食谱中快速筛出候选集                           │
└──────────────────────────────────────────────────────────────┘
                              |
                              v
┌──────────────────────────────────────────────────────────────┐
│ 4. 排序与重排层                                               │
│ 召回融合 Top100 -> LightGBM 精排 Top50 -> MMR 多样性重排 Top10 │
│ 目标：兼顾相关性、多样性、覆盖率和可解释性                     │
└──────────────────────────────────────────────────────────────┘
                              |
                              v
┌──────────────────────────────────────────────────────────────┐
│ 5. 解释与内容增强层                                           │
│ 推荐理由、图片链接、制作时间、人份、作者、原链接、营养和步骤   │
│ 目标：让推荐结果不只是 ID，而是可展示、可理解、可点击的食谱     │
└──────────────────────────────────────────────────────────────┘
                              |
                              v
┌──────────────────────────────────────────────────────────────┐
│ 5.5 离线产物同步层                                            │
│ Spark/本地离线任务输出 data 与 models 产物                     │
│ 通过 MinIO 统一上传、下载和版本化同步                          │
└──────────────────────────────────────────────────────────────┘
                              |
                              v
┌──────────────────────────────────────────────────────────────┐
│ 6. 在线服务层                                                 │
│ FastAPI 推荐、详情、搜索、相似食谱、反馈、曝光、A/B、metrics   │
│ Elasticsearch 提供搜索和详情快速读取，Redis 提供缓存           │
└──────────────────────────────────────────────────────────────┘
                              |
                              v
┌──────────────────────────────────────────────────────────────┐
│ 7. 实时反馈闭环层                                             │
│ 前端行为 -> /feedback -> Kafka -> Consumer -> Redis 实时画像   │
│ 基于 ALS embedding + FAISS 生成实时推荐缓存                    │
└──────────────────────────────────────────────────────────────┘
                              |
                              v
┌──────────────────────────────────────────────────────────────┐
│ 8. 评估与监控层                                               │
│ Precision/Recall/NDCG、Coverage、Diversity、AUC、Accuracy     │
│ 消融实验、推荐结果质量评估、Prometheus 指标、A/B 实验指标      │
└──────────────────────────────────────────────────────────────┘
```

与典型推荐系统相比，当前项目已经覆盖“数据处理、画像、召回、排序、重排、解释、在线服务、搜索、反馈、A/B、监控和评估”的主体链路。后续如果继续增强，重点不应再只是增加组件数量，而应围绕推荐系统效果和闭环能力补足以下方向：

| 能力方向 | 当前状态 | 后续可补充内容 |
| --- | --- | --- |
| 冷启动推荐 | 已支持显式偏好冷启动推荐 | 后续接入前端新用户引导页，继续补充过敏原、忌口、厨房设备等偏好 |
| 反馈回流训练 | 已记录反馈并写入 Kafka/Redis/SQLite | 将点击、喜欢、评分等反馈周期性合并进训练样本，参与下一轮离线训练 |
| 实时推荐排序 | 已实现 Kafka 消费 + FAISS 实时推荐缓存 | 在实时召回后增加轻量排序，例如时间衰减、反馈强度、食谱评分、图片可用性 |
| 离线任务调度 | 已有脚本化离线链路和 Spark 集群验证 | 增加 Airflow/Azkaban 调度，每天自动跑画像、召回、排序、评估和索引更新 |
| 分布式存储 | 已接入 MinIO 作为离线产物中心，支持 Spark 产物上传和本地后端下载 | 后续可继续接入 HDFS，让 Spark 多节点直接读取同一份全量输入数据 |
| 在线实验分析 | 已有 A/B 分组和基础指标 | 增加实验看板，展示不同模型组的曝光、点击、喜欢、转化和留存指标 |
| 推荐可解释性 | 已有模板推荐理由 | 后续可接入本地 Qwen，对推荐理由进行自然语言增强 |
| 监控可视化 | 已输出 Prometheus 格式指标 | 增加 Grafana 面板，展示接口延迟、QPS、缓存命中率、Kafka 消费量和反馈率 |

## 七、技术路线

### 1. 数据建模与预处理路线

项目围绕 Food.com 食谱推荐任务构建统一的数据处理链路，将原始食谱、用户交互、图片详情和官方数据划分整理成后续画像、召回、排序和在线服务可以直接使用的标准产物。

主要处理内容包括：

- 读取 Food.com 原始食谱、用户评分、评论和官方 train/valid/test 划分。
- 统一食谱 ID、用户 ID、评分、时间戳、标签、配料、步骤和营养字段。
- 生成训练、验证、测试交互文件，保证离线训练和评估使用同一套数据口径。
- 构建食谱画像、用户画像、标签/配料特征、详情页元数据和图片字段。
- 保留统一的 `data/processed`、`data/features`、`data/rank`、`data/final`、`models` 产物目录，方便本地服务、Spark 任务和 MinIO 同步脚本共同使用。

### 2. 离线训练路线

当前离线训练路线已经不是单一的“ALS + XGBoost”流程，而是包含数据导入、画像构建、多路召回、排序模型升级、重排、评估、搜索索引和 MinIO 产物同步的完整离线链路。

离线训练主要分为以下阶段：

1. 导入 Food.com 官方训练集、验证集和测试集。
2. 将 Food.com 食谱、评分、评论和图片详情转换为项目内部标准格式。
3. 构建 `ratings_clean.csv`、`train_ratings.csv`、`valid_ratings.csv`、`test_ratings.csv`。
4. 构建食谱基础画像 `movies_clean.csv`，保留标题、标签、制作时间、评分、评论数等字段。
5. 构建食谱详情元数据，补充配料、步骤、营养、人份、作者、Food.com 原链接和图片链接。
6. 构建标签、配料和文本特征 `movie_tags.csv`。
7. 基于训练集构建用户画像 `user_profile.csv` 和食谱画像 `movie_profile.csv`。
8. 训练 Spark MLlib ALS，导出用户向量和食谱 item embedding。
9. 基于 ALS item embedding 构建 FAISS HNSW 向量索引，用于向量召回和详情页相似食谱。
10. 分别生成 ALS、ItemCF、FAISS_HNSW、LightGCN、Content、Hot 多路召回结果。
11. 融合多路召回候选，形成排序前候选集。
12. 导出排序特征，包含召回分数、画像特征、用户-食谱交叉特征、热门度、评分、图片可用性、评论数、时间和营养等特征。
13. 训练基础 XGBoost 排序模型，作为排序基线。
14. 在已有 `data/rank/` 训练数据上训练增强排序模型，对比 XGBoost、LightGBM 和逻辑回归排序基线。
15. 根据验证集结果选择 LightGBM 作为当前主排序模型，验证集 AUC 达到 `0.980079`，LogLoss 为 `0.082833`。
16. 使用选出的 LightGBM 模型对全量 2,507,600 条候选打分，生成覆盖 25,076 个用户的 Top50 候选结果。
17. 使用 MMR 进行多样性重排，得到最终 Top10 推荐。
18. 生成模板推荐理由，让推荐结果具备可解释性。
19. 合并图片、配料、步骤、营养、人份、作者和原链接等详情字段。
20. 生成离线评估结果，包括推荐结果质量评估、官方测试集 TopK 指标、消融实验和排序模型指标。
21. 将食谱数据导入 Elasticsearch，支撑搜索、详情页快速读取和前端展示。
22. 将 `data/` 与 `models/` 中的离线产物上传到 MinIO，作为统一的模型与推荐结果产物仓库。

离线产物当前已经上传到 MinIO：

```text
Bucket: reciperec
Prefix: offline/latest
文件数: 115
总大小: 2577.2 MB
```

因此演示时不需要在虚拟机现场重新训练，可以直接从 MinIO 同步已经生成好的画像、召回、排序、推荐结果和模型文件。

### 3. 在线服务路线

在线服务主要由 FastAPI 提供：

- 个性化推荐接口读取离线生成的 `LightGBM + MMR` 推荐结果。
- 统一场景推荐接口 `/recipes/scenario-recommend` 支持个性化、食材、健康、快手菜和探索推荐。
- 详情接口优先读取 Elasticsearch。
- 搜索接口优先读取 Elasticsearch。
- 相似食谱接口使用 ALS embedding + FAISS HNSW 近邻。
- 反馈接口记录点击、喜欢、不喜欢、评分等行为。
- 曝光接口记录推荐展示日志。
- A/B 接口返回稳定实验分组。
- 监控接口输出 Prometheus 文本指标。

当前在线推荐已经不只是“输入用户 ID 返回一组推荐”，而是按不同使用场景拆分为多种推荐入口：

| 场景 | 接口参数 `scenario` | 推荐来源 | 说明 |
| --- | --- | --- | --- |
| 个性化推荐 | `personalized` | 离线 `LightGBM + MMR` 最终推荐 | 根据用户历史交互生成个性化 TopN。若用户请求 Top20/Top50，而最终 MMR Top10 不足，会从 LightGBM Top50 候选继续补齐。 |
| 食材推荐 / 冰箱推荐 | `ingredients` | 内容画像冷启动推荐 | 根据用户输入的食材，例如 `chicken, egg, potato`，匹配标题、标签、配料和热门质量信号。 |
| 健康目标推荐 | `healthy` | 内容画像 + 营养特征 | 根据低卡、高蛋白、低脂、低糖、低钠等饮食目标生成推荐。 |
| 快手菜推荐 | `quick` | 内容画像 + 制作时间特征 | 根据最大烹饪时间和餐别标签推荐 15/30/45/60 分钟内适合制作的食谱。 |
| 探索推荐 | `explore` | LightGBM Top50 二次重排 | 在个性化候选中加入新颖度、图片可用性、热门度、评分和多样性惩罚，让推荐结果不只重复用户历史偏好。 |

统一场景推荐接口的优势是：前端只需要调用一个入口，后端根据场景自动选择离线推荐、内容冷启动或探索重排链路，既保留推荐算法资产，也让系统表现更像真实食谱推荐产品。

### 4. 实时反馈与实时推荐路线

实时链路用于弥补离线推荐“周期性更新”的不足。当用户刚刚点击、喜欢、不喜欢或评分某个食谱时，系统不需要重新训练 ALS、LightGCN 或 XGBoost，而是使用轻量级实时更新方式快速调整推荐结果。

实时更新主要分为以下阶段：

1. 前端产生用户行为。
   用户在推荐页、搜索页或详情页中点击、喜欢、不喜欢、评分食谱，前端调用后端 `/feedback` 接口。

2. FastAPI 记录反馈事件。
   后端先把反馈写入本地 SQLite 反馈日志，同时更新 Redis 中的实时用户画像。

3. 反馈事件写入 Kafka。
   `FeedbackService` 会把同一条反馈封装为 JSON 事件，发送到 Kafka 的 `recipe_feedback` topic。事件中包含用户 ID、食谱 ID、反馈类型、反馈值、推荐位置、分数、推荐理由和时间戳。

4. Kafka Consumer 消费反馈事件。
   `scripts/kafka_feedback_consumer.py` 持续消费 `recipe_feedback`，把用户最近反馈写入 Redis：

   ```text
   user:recent_feedback:{user_id}
   user:realtime_profile:{user_id}
   ```

5. 基于 FAISS 生成实时推荐缓存。
   消费端读取用户最近正反馈食谱，使用这些食谱的 ALS embedding 到 FAISS HNSW 索引中查找相似食谱，并过滤用户已经反馈或明确不喜欢的食谱，生成实时推荐列表：

   ```text
   recipe:realtime_rec:user:{user_id}:k:{top_k}
   ```

6. 推荐接口优先返回实时推荐。
   `/recipes/recommend/{user_id}` 和兼容接口 `/recommend/{user_id}` 会先读取实时推荐缓存。如果存在实时结果，就直接返回；如果没有实时缓存，再回退到离线生成的推荐结果。

这条实时路线的特点是：不重训大模型、不重新跑全量数据，只基于“用户最近行为 + ALS item embedding + FAISS 近邻检索”快速生成短期兴趣推荐。它适合体现“用户反馈可以影响下一次推荐”的闭环能力。

当前实时链路已经完成：

- Kafka 反馈事件发送。
- Kafka 消费端脚本。
- Redis 实时用户画像。
- FAISS 实时相似食谱推荐缓存。
- 推荐接口优先读取实时缓存。

后续还可以继续增强：

- 把实时推荐结果也写入 `recipe_realtime_recommend` topic，供其他服务消费。
- 在实时召回后增加轻量排序规则，例如结合反馈类型、时间衰减、食谱评分和图片可用性。
- 加入滑动窗口统计，例如最近 10 分钟点击率、喜欢率和不喜欢率。
- 将实时反馈特征周期性回流到离线训练集，用于下一轮模型训练。

### 5. Spark 集群与本地执行路线

当前项目已经完成三节点 Spark standalone 集群接入，并通过项目离线画像构建任务验证。Spark 已经作为项目的大数据计算扩展能力接入。

当前 Spark 集群部署情况：

| 节点 | IP | 角色 |
| --- | --- | --- |
| node1 | 192.168.88.161 | Spark Master、Worker、ZooKeeper、Kafka |
| node2 | 192.168.88.162 | Spark Worker、ZooKeeper |
| node3 | 192.168.88.163 | Spark Worker、ZooKeeper |

集群验证结果：

```text
Spark Master: spark://node1:7077
Alive Workers: 3
Total Cores: 6
Total Memory: 6.0 GiB
```

项目已经在虚拟机 Spark 集群上完成离线画像构建验证：

```text
train ratings rows: 20000
movies rows: 178265
tags rows: 200000
user profile rows: 260
movie profile rows: 178265
quality validation result: success
```

因此当前计算路线分为两层：

1. Spark 集群路线。
   用于体现项目的大数据处理能力，适合运行离线画像构建、ALS 训练、ItemCF 计算、召回特征构建等任务。当前已验证三节点 Spark 可以运行项目任务。

2. 本地执行路线。
   Windows 本机保留 pandas 版本脚本，用于演示、调试和快速复现部分离线结果。

保留的本地执行脚本包括：

- `scripts/merge_recall_pandas.py`
  - 用于在本机内存有限或 Spark 不可用时合并召回。
  - 可处理百万级召回候选。

- `scripts/export_rank_features_pandas.py`
  - 用于在本机内存有限或 Spark 不可用时导出排序特征。
  - 支持分块处理大规模候选。

当前项目的定位是“本机负责开发、接口和快速离线执行，虚拟机 Spark 集群负责展示分布式离线计算能力”。Spark 或本地离线任务生成的 `data/`、`models/` 产物可以通过 MinIO 同步回本地服务，避免每次手动下载文件。后续如果继续升级，可以接入 HDFS 或共享存储，把全量画像构建、ALS、ItemCF、召回合并和排序特征导出固定为 Spark 集群任务稳定运行。

### 6. MinIO 离线产物同步路线

MinIO 用来解决“Spark 在虚拟机训练完，本地后端怎么拿到最新模型和推荐结果”的问题。它不是推荐算法本身，而是离线计算产物的统一中转站。

当前同步路线如下：

```text
虚拟机 Spark 离线任务
        |
        v
data/features、data/factors、data/recall、data/rank、data/final、models/*
        |
        v
上传到 MinIO bucket: reciperec / prefix: offline/latest
        |
        v
Windows 本地后端执行下载脚本
        |
        v
FastAPI、FAISS、排序模型、推荐结果读取最新本地产物
```

已实现的脚本：

| 脚本 | 作用 |
| --- | --- |
| `scripts/sync_minio_artifacts.py upload` | 上传离线产物到 MinIO |
| `scripts/sync_minio_artifacts.py download` | 从 MinIO 下载离线产物到本地项目目录 |
| `scripts/sync_minio_artifacts.py list` | 查看 MinIO 中当前已有的离线产物 |
| `scripts/upload_artifacts_to_minio.py` | 上传命令的简化入口 |
| `scripts/download_artifacts_from_minio.py` | 下载命令的简化入口 |

默认配置：

```text
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=reciperec
MINIO_ARTIFACT_PREFIX=offline/latest
```

如果脚本在虚拟机 node1 上运行，而 MinIO 在 Windows 本机上，需要把 `MINIO_ENDPOINT` 改成 Windows 主机在虚拟机网段可访问的地址，例如 `192.168.88.x:9000`。

## 八、推荐流程

### 1. ALS 召回

ALS 使用用户-食谱评分矩阵训练隐向量，得到用户向量和食谱向量。系统根据用户向量预测用户可能喜欢的食谱，并过滤训练集中已经交互过的食谱。

当前 ALS 配置：

- rank：24
- maxIter：6
- regParam：0.1
- topN：50

### 2. ItemCF 召回

ItemCF 基于用户共同喜欢的食谱计算食谱相似度。如果用户喜欢 A，而 A 和 B 经常被相同用户喜欢，则 B 会作为候选推荐给该用户。

ItemCF 适合捕捉“共同口味”和“相似用户行为”。

### 3. FAISS_HNSW 向量召回

FAISS_HNSW 使用 ALS item embedding 构建近邻索引。对每个用户：

1. 找到用户高评分食谱。
2. 取这些食谱的 ALS embedding 平均值作为用户查询向量。
3. 在 FAISS HNSW 索引中查找近邻食谱。
4. 过滤用户已经交互过的食谱。

这个召回通道也用于详情页的“相似食谱”：

> 用户点开一个菜谱后，用该菜谱的 ALS embedding 到 FAISS 里查近邻，展示口味和交互人群相近的食谱。

### 4. LightGCN 召回

LightGCN 使用用户-食谱二部图训练图神经网络 embedding。它通过图传播捕捉高阶协同信号，例如：

- 用户 A 和用户 B 喜欢相似食谱。
- 用户 A 喜欢的食谱与另一个食谱被相似用户共同喜欢。
- 多跳路径带来的潜在兴趣。

当前 LightGCN 已经是真正的 PyTorch 实现，不是占位逻辑。

### 5. 内容召回

Content 召回基于食谱标题、标签、配料、类别等文本特征，通过 TF-IDF 计算用户偏好和食谱内容的相似度。

在全量官方数据划分下，原始全库逐用户相似度计算过慢，因此当前采用候选池优化：

- 先选取热门/高评分候选食谱池。
- 再在候选池中做内容相似度召回。

### 6. Hot 召回

Hot 召回用于补充冷启动和兜底推荐。分数主要来自：

```text
hot_score = movie_avg_rating * log(movie_rating_count + 1)
```

即评分高且评分人数较多的食谱更容易进入热门候选。

### 7. 多路召回融合

当前融合权重：

| 召回通道 | 权重 |
| --- | ---: |
| ALS | 0.30 |
| ItemCF | 0.22 |
| FAISS_HNSW | 0.16 |
| LightGCN | 0.12 |
| Content | 0.12 |
| Hot | 0.08 |

同时加入来源数量奖励：

```text
merged_score += 0.1 * recall_source_count
```

如果一个食谱同时被多个通道召回，说明它在多个角度上都可能适合用户，因此会获得额外加分。

### 8. 排序模型选择与 LightGBM 精排

排序阶段先以 XGBoost 作为基础排序基线，再在同一批排序训练数据上加入增强特征，对比 XGBoost、LightGBM 和 Logistic Regression。当前系统根据验证集效果选择 LightGBM 作为主排序模型。

基础排序特征包括：

- 用户评分数量。
- 用户平均评分。
- 用户活跃等级。
- 食谱平均评分。
- 食谱评分数量。
- 食谱热度。
- 年份和年代特征。
- 标签数量。
- 用户偏好标签和食谱标签匹配分。
- ALS 分数。
- ItemCF 分数。
- FAISS_HNSW 分数。
- LightGCN 分数。
- Content 分数。
- Hot 分数。
- 多路召回来源数量。
- 融合召回分数。

基础 XGBoost 训练结果：

- 训练样本：698,901
- 正样本：645,970
- 负样本：52,931
- 特征数：31
- Train AUC：0.949110
- Validation AUC：0.947570

### 9. 增强排序模型对比与落地

项目新增增强排序模型选择脚本：

```text
rank/train_enhanced_ranker.py
```

该脚本不重新跑 Spark 和召回阶段，而是直接复用 `data/rank/` 下已经生成的排序训练集和全量候选集：

- `data/rank/rank_train.csv`
- `data/rank/rank_candidates.csv`
- `data/rank/rank_feature_columns.json`
- `data/features/user_profile.csv`
- `data/features/movie_profile.csv`
- `data/recipe-canonical/recipe_metadata.csv`

增强排序在原有 31 个排序特征基础上，增加了 29 个推荐系统特征，包括：

- 用户-食谱评分匹配特征。
- 用户最近行为命中特征。
- 用户高评分历史命中特征。
- 图片可用性、照片数量、评论数量。
- 食谱制作时间、步骤数、配料数。
- 热量、蛋白质、脂肪、糖、钠、碳水等营养特征。
- 食谱新鲜度和人份信息。

增强排序对比了以下模型：

```text
XGBoost
LightGBM
Logistic Regression
```

当前增强排序模型对比中，LightGBM 表现最好，并已作为主排序模型用于最终推荐生成：

| 指标 | 数值 |
| --- | ---: |
| 最佳模型 | LightGBM |
| 训练样本 | 554,972 |
| 验证样本 | 143,929 |
| 特征数 | 60 |
| 新增增强特征数 | 29 |
| Validation AUC | 0.980079 |
| Validation Accuracy | 0.966324 |
| Validation LogLoss | 0.082833 |
| 打分候选数 | 2,507,600 |
| 生成增强排序 Top50 | 1,253,800 |
| 覆盖用户数 | 25,076 |

增强排序产物保存在：

- `data/rank/enhanced/enhanced_model_comparison.csv`
- `data/rank/enhanced/enhanced_feature_importance.csv`
- `data/rank/enhanced/enhanced_ranker_metrics.json`
- `data/rank/enhanced/ranked_top50_enhanced.csv`
- `models/enhanced_ranker/best_enhanced_lightgbm.txt`

最终推荐链路已经切换为：

```text
多路召回 -> LightGBM Top50 -> MMR Top10 -> 推荐理由与详情增强
```

### 10. MMR 多样性重排

LightGBM 排序后得到 Top50，MMR 从中选出 Top10。MMR 会同时考虑：

- 相关性：LightGBM 排序分数高。
- 多样性：不要全是同一类食谱。

当前 MMR 的 `lambda_rel = 0.7`，即更偏向相关性，同时保留一定多样性。

### 11. 冷启动推荐

冷启动推荐用于解决新用户没有历史评分或历史行为不足的问题。项目新增了基于显式偏好的冷启动推荐能力：

```text
recommendation/cold_start.py
POST /recipes/cold-start
```

用户可以输入：

- 偏好标签，例如 `quick`、`dinner`、`dessert`。
- 已有或喜欢的食材，例如 `chicken`、`potato`、`cheese`。
- 饮食目标，例如 `high protein`、`low calorie`、`low fat`。
- 最大烹饪时间。
- 是否要求有图片。
- 最低评分。

冷启动推荐会综合：

- 内容匹配分。
- 食材匹配分。
- 饮食目标匹配分。
- 时间匹配分。
- 食谱评分和热度。
- 图片可用性。
- 多样性选择。

示例输入：

```json
{
  "preferred_tags": ["quick", "dinner"],
  "ingredients": ["chicken"],
  "dietary_goals": ["high protein"],
  "max_minutes": 45,
  "require_image": true,
  "limit": 3
}
```

实测会返回符合偏好的鸡肉快手菜，例如：

```text
quick and easy chicken liver pate
quick n easy vietnamese chicken salad
quick chicken soup with buttermilk dumplings
```

## 九、前端页面

当前前端围绕食谱推荐场景设计，主要页面包括：

### 1. 首页

首页展示系统入口、热门食谱、数据规模和主要技术栈，用于快速进入推荐控制台、搜索和详情浏览流程。当前首页已经更新为食谱推荐系统展示，不再使用电影推荐系统文案。首页展示的核心信息包括：

- 食谱规模：约 178K。
- 用户规模：约 25K。
- 最终 Top10 推荐规模：约 250K。
- 当前主排序模型 AUC：约 0.980。
- 技术栈：FastAPI、Spark、FAISS HNSW、LightGBM、Redis、Elasticsearch、Vue 3、Food.com。

### 2. 推荐页

推荐页已经改为多场景食谱推荐控制台，不再只是输入用户 ID 的单一推荐演示。当前推荐页支持以下模式：

| 前端模式 | 后端场景 | 页面输入 | 推荐逻辑 |
| --- | --- | --- | --- |
| Personalized | `personalized` | 登录账号绑定的 Food.com User ID、TopK | 读取 `LightGBM + MMR` 离线个性化推荐，不足 TopK 时用 LightGBM Top50 补齐。 |
| Pantry | `ingredients` | 食材文本、食材快捷按钮、TopK、是否优先有图 | 根据食材、标签、评分、热度、图片和多样性做内容冷启动推荐。 |
| Healthy | `healthy` | 健康目标按钮、TopK、是否优先有图 | 根据低卡、高蛋白、低脂、低糖、低钠等营养目标推荐。 |
| Quick meals | `quick` | 最大制作时间、餐别标签、TopK、是否优先有图 | 根据制作时间、快手标签和食谱质量信号推荐。 |
| Explore | `explore` | 登录账号绑定的 Food.com User ID、探索强度滑杆、TopK | 在用户 LightGBM Top50 候选中按探索强度做新颖度和多样性重排。 |

每个推荐卡片包含：

- 食谱标题。
- 图片。
- 推荐理由。
- 评分。
- 评论/评分数量。
- 标签或简要信息。

推荐页顶部会展示当前链路标签，例如 `LightGBM main ranker`、`MMR Top10`、`Content cold start`，用于说明当前推荐系统不是单一路径，而是由个性化排序、内容冷启动和探索重排共同组成。

### 3. 登录注册页

前端已新增简单登录注册页：

- 注册时填写用户名、密码、显示名。
- 注册时绑定一个 Food.com User ID，用于个性化推荐和反馈闭环。
- 密码由后端使用 PBKDF2 哈希后写入 SQLite，不明文保存。
- 登录后前端把账号信息保存到浏览器本地缓存。
- 导航栏会显示当前登录用户和绑定的 Food.com User ID。
- 推荐页、探索推荐和反馈按钮会自动使用当前登录账号绑定的 `user_id`。

该登录注册用于课程设计和演示场景，重点是解决“前端反馈不知道当前用户是谁”的问题。

### 4. 搜索页

搜索页通过 Elasticsearch 查询食谱，支持根据关键词搜索标题、标签、配料等内容。搜索接口优先读取 ES，速度比直接扫描 CSV 更快。

### 5. 食谱详情页

详情页已经扩展为真正的菜谱详情页，展示：

- 食谱图片。
- 标题。
- 描述。
- 配料。
- 制作步骤。
- 营养信息。
- 制作时间。
- 人份/产量。
- 作者。
- 评分。
- 评论数量。
- Food.com 原链接。
- 相似食谱。

相似食谱来自 ALS embedding + FAISS HNSW 近邻。

### 6. 热门食谱组件

热门食谱根据食谱评分和交互数量展示，用于首页或兜底推荐。

### 7. 反馈交互

推荐页已经接入前端反馈按钮。用户登录后，每张推荐卡片下方会展示：

- `Like`：写入 `feedback_type=like`。
- `Dislike`：写入 `feedback_type=dislike`。
- `1-5` 评分按钮：写入 `feedback_type=rating` 和 `feedback_value`。

这些操作会调用后端 `/feedback` 接口，记录用户 ID、食谱 ID、反馈类型、评分值、推荐位置、模型分数和推荐理由。后端会先写入 SQLite 反馈日志，并更新 Redis 实时画像；如果 Kafka 已启动，还会把反馈事件发送到 `recipe_feedback` topic。Kafka 消费端可继续更新 Redis 实时画像，并基于 FAISS 相似食谱生成实时推荐缓存。

如果没有启动 Kafka，接口仍然可用，只是返回中的 `kafka_sent=false`，表示该条反馈已完成本地日志和 Redis 更新，但没有进入 Kafka 消息队列。

## 十、后端接口

主要接口：

| 接口 | 用途 |
| --- | --- |
| `POST /auth/register` | 注册本地演示账号，并绑定 Food.com 推荐用户 ID |
| `POST /auth/login` | 登录本地演示账号，返回账号信息和绑定的推荐用户 ID |
| `GET /recipes/recommend/{user_id}` | 获取用户个性化食谱推荐 |
| `POST /recipes/scenario-recommend` | 统一多场景推荐接口，支持个性化、食材、健康、快手菜和探索推荐 |
| `GET /recipes/popular` | 获取热门食谱 |
| `POST /recipes/cold-start` | 根据新用户显式偏好生成冷启动推荐 |
| `GET /recipe/{id}` | 获取食谱详情 |
| `GET /recipe/{id}/similar` | 获取相似食谱 |
| `GET /recipes/search?q=...` | 搜索食谱 |
| `POST /feedback` | 写入点击、喜欢、不喜欢、评分反馈 |
| `POST /recommendation-exposure` | 写入推荐曝光 |
| `GET /ab/group/{user_id}` | 获取用户 A/B 分组 |
| `GET /ab/metrics` | 查看 A/B 指标 |
| `GET /metrics` | Prometheus 监控指标 |

统一场景推荐接口示例：

```http
POST /recipes/scenario-recommend
Content-Type: application/json
```

个性化推荐：

```json
{
  "scenario": "personalized",
  "user_id": 1535,
  "limit": 20
}
```

食材推荐：

```json
{
  "scenario": "ingredients",
  "ingredients": ["chicken", "egg"],
  "limit": 10,
  "require_image": true
}
```

健康推荐：

```json
{
  "scenario": "healthy",
  "dietary_goals": ["healthy", "high-protein", "low-fat"],
  "limit": 10,
  "require_image": true
}
```

快手菜推荐：

```json
{
  "scenario": "quick",
  "max_minutes": 30,
  "preferred_tags": ["dinner"],
  "limit": 10,
  "require_image": true
}
```

探索推荐：

```json
{
  "scenario": "explore",
  "user_id": 1535,
  "limit": 10,
  "exploration": 0.65
}
```

## 十一、关于官方测试集上 Precision/Recall/NDCG 为 0 的解释

当前官方测试集评估结果中：

- `Precision@10 = 0`
- `Recall@10 = 0`
- `NDCG@10 = 0`

这不代表系统没有生成推荐，也不代表推荐链路没有跑通。当前系统已经为 25,076 个用户生成了 250,760 条 Top10 推荐。

### 1. 这三个指标分别是什么意思

`Precision@10` 表示推荐给用户的前 10 个食谱里，有多少比例真的出现在该用户的测试集正样本中。例如推荐 10 个，命中 1 个，Precision@10 就是 0.1。

`Recall@10` 表示用户测试集里真正喜欢的食谱，有多少比例被前 10 个推荐结果找回。例如某用户测试集中有 2 个正样本，推荐命中 1 个，Recall@10 就是 0.5。

`NDCG@10` 不只看有没有命中，还看命中的位置。命中的食谱排得越靠前，NDCG 越高；如果命中项排在第 1 名，会比排在第 10 名得分更高。

本项目还输出了几个辅助指标：

- `HitRate@10`：只看用户是否至少命中 1 个测试正样本。
- `Coverage@10`：所有推荐结果覆盖了多少比例的食谱库，越高说明推荐结果不是只集中在少数热门食谱。
- `Diversity@10`：推荐列表内部的差异程度，越高说明同一个用户看到的食谱类型更丰富。

### 2. 为什么这次三个命中指标全是 0

它真正表示的是：

> 按照当前严格离线评估方式，推荐列表中的食谱没有命中官方测试集里用户评分大于等于 4 的食谱。

这次排序候选导出时，250 万候选里只包含 1 条官方测试集正样本。因此后面的 XGBoost、MMR 再怎么排序，也很难在 Precision/Recall/NDCG 上得到有效分数。

可能原因包括：

1. 官方数据划分里的测试食谱和训练兴趣之间较稀疏。
2. 当前召回主要过滤训练已交互项，但没有专门优化官方测试集命中。
3. Food.com 用户行为非常长尾，很多测试食谱不在当前候选覆盖范围内。
4. 当前内容召回为了本地可运行，使用了热门候选池，可能牺牲了部分长尾测试样本覆盖。
5. 当前评估是非常严格的“必须命中测试集中同一个 recipe_id”，没有考虑相似食谱、同类食谱或替代食谱的合理性。

因此，当前指标应该这样解读：

- Coverage 和 Diversity 可以说明推荐结果覆盖范围和多样性。
- XGBoost AUC 可以说明排序模型能区分训练样本中的高低评分。
- Precision/Recall/NDCG 暂时不能说明线上推荐效果，因为候选集没有覆盖到官方测试集正样本。

一句话总结：

> 现在的问题不是“系统没有推荐”，而是“当前召回候选没有覆盖官方测试集正样本，所以严格命中型离线指标无法体现推荐质量”。

后续优化方向：

1. 提高召回阶段的测试集正样本覆盖率。
2. 针对官方数据划分做召回参数调优。
3. 增加长尾召回或按用户历史食谱的近邻召回。
4. 使用验证集调权重，而不是直接固定融合权重。
5. 增加“相似食谱命中”或“标签相似命中”的辅助评估。
6. 对 Content 召回扩大候选池，或使用更大内存的 Spark/向量检索环境。

## 十二、全量测试效果

本节记录的是当前项目基于 Food.com 官方训练集、验证集和测试集跑出来的全量离线结果，不是小样本测试结果。

### 1. 全量数据运行范围

| 项目 | 数量 |
| --- | ---: |
| 训练交互 | 698,901 |
| 验证交互 | 7,023 |
| 测试交互 | 12,455 |
| 有效用户数 | 25,076 |
| 食谱画像数 | 178,265 |
| 标签/配料特征行 | 4,745,034 |

这说明当前不是只跑了少量示例数据，而是已经接入 Food.com 官方划分并跑过较大规模离线链路。

### 2. 多路召回与最终推荐产物规模

| 产物 | 数量 |
| --- | ---: |
| ALS 召回结果 | 1,252,895 |
| ItemCF 召回结果 | 1,232,634 |
| FAISS_HNSW 召回结果 | 1,239,940 |
| LightGCN 召回结果 | 1,242,300 |
| 内容召回结果 | 1,242,300 |
| 热门召回结果 | 1,253,800 |
| 多路融合召回候选 | 2,507,600 |
| LightGBM Top50 排序结果 | 1,253,800 |
| MMR Top10 重排结果 | 250,760 |
| 最终推荐结果 | 250,760 |

从产物规模看，ALS、ItemCF、FAISS_HNSW、LightGCN、内容召回、热门召回、多路融合、LightGBM 排序、MMR 重排都已经在全量官方数据上生成了结果。

### 3. XGBoost 排序模型测试效果

XGBoost 使用 31 个排序特征训练，训练集和验证集效果如下：

| 指标 | 数值 |
| --- | ---: |
| 排序训练样本数 | 698,901 |
| 特征数量 | 31 |
| 正样本数量 | 645,970 |
| 负样本数量 | 52,931 |
| 训练集 AUC | 0.949110 |
| 验证集 AUC | 0.947570 |
| 训练集 Accuracy | 0.947990 |
| 验证集 Accuracy | 0.946946 |
| 训练集 LogLoss | 0.131235 |
| 验证集 LogLoss | 0.133105 |

从 AUC 和 Accuracy 看，排序模型在当前训练/验证划分下具备较强的高低评分区分能力。需要注意的是，AUC 衡量的是排序模型区分正负样本的能力，和 TopK 是否精确命中官方测试集正样本不是同一个问题。

### 4. 排序模型选择与增强排序测试效果

为了让排序阶段更像完整推荐系统，项目新增了增强排序模型选择流程。该流程直接复用 `data/rank/` 下已有排序训练集和全量候选集，不重新跑召回或 Spark 任务。

增强排序新增了用户-食谱交叉特征、最近行为特征、图片/评论特征、制作时间特征和营养特征，并对比了 XGBoost、LightGBM 和 Logistic Regression。

模型对比结果如下。由于当前验证候选集上多个模型的 Top10 命中集合高度一致，Precision@10、Recall@10 和 NDCG@10 难以区分模型，因此模型选择表只保留 AUC、Accuracy 和 LogLoss。当前按验证集 AUC 和 LogLoss 选择 LightGBM 作为主排序模型：

| 模型 | AUC | Accuracy | LogLoss |
| --- | ---: | ---: | ---: |
| LightGBM | 0.980079 | 0.966324 | 0.082833 |
| XGBoost depth5 lr0.08 | 0.978999 | 0.965629 | 0.085127 |
| XGBoost depth5 lr0.05 | 0.977997 | 0.964684 | 0.087882 |
| XGBoost depth4 lr0.05 | 0.976363 | 0.963211 | 0.091333 |
| Logistic Regression | 0.964588 | 0.889967 | 0.258185 |

本次增强排序最佳模型为 LightGBM，已经对全量 2,507,600 条候选完成打分，并输出覆盖 25,076 个用户的 Top50。输出产物包括：

- `data/rank/enhanced/enhanced_model_comparison.csv`
- `data/rank/enhanced/enhanced_feature_importance.csv`
- `data/rank/enhanced/enhanced_ranker_metrics.json`
- `data/rank/enhanced/ranked_top50_enhanced.csv`
- `models/enhanced_ranker/best_enhanced_lightgbm.txt`

基于 LightGBM Top50 继续执行 MMR 后，当前最终推荐结果为：

| 产物 | 数量 |
| --- | ---: |
| LightGBM Top50 | 1,253,800 |
| LightGBM + MMR Top10 | 250,760 |
| 覆盖用户数 | 25,076 |
| MMR 平均多样性 | 0.831713 |

特征重要性前几位包括：`movie_avg_rating`、`user_rating_std`、`movie_rating_std`、`user_rating_count`、`user_avg_rating`、`movie_popularity`、`external_rating_gap`、`log_review_count`、`popularity_adjusted_genre_match` 和 `rating_alignment_score`。这些特征可以解释为什么某个食谱会被排到前面。

### 5. 官方测试集 TopK 评估结果

当前使用官方测试集做严格命中评估，`rating >= 4` 作为正样本。K=10 时主要结果如下：

| 模型/阶段 | Precision@10 | Recall@10 | NDCG@10 | HitRate@10 | Coverage@10 | Diversity@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ALS | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.041040 | 0.781751 |
| ItemCF | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.167907 | 0.763579 |
| FAISS_HNSW | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.171974 | 0.772389 |
| 多路融合召回 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.080195 | 0.779145 |
| XGBoost Top50 基线 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.132348 | 0.773650 |
| LightGBM Top50 主排序 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.106521 | 0.780480 |
| LightGBM + MMR Top10 最终推荐 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.145334 | 0.831981 |

这组结果说明：

1. 严格命中指标 Precision、Recall、NDCG 当前为 0，原因是召回候选几乎没有覆盖官方测试集正样本。
2. FAISS_HNSW 在 Coverage@10 上高于 ALS，说明向量召回覆盖的食谱范围更广。
3. LightGBM + MMR 的 Diversity@10 最高，达到 0.831981，说明 MMR 重排明显提升了推荐列表多样性。
4. 当前 TopK 评估更适合暴露“召回覆盖不足”问题，不能简单理解为系统没有推荐能力。

### 6. 消融实验结论

消融实验对比了 ALS、ItemCF、FAISS_HNSW、多路融合召回、XGBoost 排序基线、LightGBM 主排序模型和 MMR 重排。当前结论如下：

- 多路融合召回没有提升官方测试集 Recall@10，主要受限于测试正样本覆盖不足。
- XGBoost 和 LightGBM 排序没有提升官方测试集 Precision@10 和 NDCG@10，因为候选集中可命中的测试正样本太少。
- LightGBM 是验证集排序效果最好的模型，因此被选为当前主排序模型。
- MMR 相比 LightGBM Top50 将 Diversity@10 从 0.780480 提升到 0.831981，提升约 0.051501。
- 因此当前最明确的实验收益来自 MMR 多样性重排；下一步最应该优化的是召回覆盖率，而不是继续堆排序模型。

### 7. 搜索与图片数据测试结果

| 项目 | 结果 |
| --- | ---: |
| Elasticsearch 索引 | `recipes` |
| ES 食谱文档数 | 178,265 |
| ES 索引状态 | green |
| ES 索引大小 | 约 335.5 MB |
| 食谱画像有图数量 | 41,162 / 178,265 |
| 食谱画像图片覆盖率 | 约 23.09% |
| 最终推荐有图数量 | 54,283 / 250,760 |
| 最终推荐图片覆盖率 | 约 21.65% |

这说明搜索服务已经完成大规模食谱导入，前端推荐卡片和详情页也可以使用增强数据中的图片链接展示真实菜谱图片。不过 Food.com Enhanced V3 本身并不是每条菜谱都有图片，所以图片覆盖率不是 100%。

### 8. 冷启动推荐测试结果

冷启动推荐接口已经使用真实数据测试通过。测试请求：

```json
{
  "preferred_tags": ["quick", "dinner"],
  "ingredients": ["chicken"],
  "dietary_goals": ["high protein"],
  "max_minutes": 45,
  "require_image": true,
  "limit": 3
}
```

接口返回：

```text
status = 200
total = 3
```

返回结果为符合偏好的鸡肉快手菜，说明冷启动推荐可以根据新用户显式偏好生成初始推荐。

### 9. 工程测试结果

已经跑通的轻量测试：

```text
tests/test_foodcom_official_splits.py
tests/test_content_hot_recall.py
tests/test_foodcom_conversion.py

结果：5 passed
```

这些测试覆盖了官方数据划分导入、Food.com 到项目内部结构的转换、内容召回和热门召回等关键逻辑。

另外，完整离线评估结果已经落盘到：

- `data/eval/offline_metrics.csv`
- `data/eval/eval_summary.json`
- `data/eval/ablation_metrics.csv`
- `data/eval/ablation_summary.md`
- `data/rank/xgb_train_metrics.json`

## 十三、当前已完成内容

### 数据层

- 已复制并整理 Food.com 数据。
- 已导入官方训练集、验证集和测试集。
- 已构建 canonical 数据结构。
- 已构建食谱详情元数据。
- 已合并 Enhanced V3 图片和详情字段。

### 算法层

- 已完成 ALS 召回。
- 已完成 ItemCF 召回。
- 已完成 FAISS HNSW 向量召回。
- 已完成真正 PyTorch LightGCN 召回。
- 已完成内容召回。
- 已完成 Hot 召回。
- 已完成多路召回融合。
- 已完成 XGBoost 排序基线。
- 已完成增强排序模型选择，新增 29 个排序特征，并对比 XGBoost、LightGBM 和 Logistic Regression。
- 已选择 LightGBM 作为当前主排序模型，并已对全量候选生成 Top50，产物保存在 `data/rank/enhanced/` 和 `models/enhanced_ranker/`。
- 已完成 MMR 多样性重排。
- 已完成冷启动推荐，支持根据新用户偏好标签、食材、饮食目标、烹饪时间和图片要求生成初始推荐。
- 已完成多场景推荐封装，将个性化推荐、食材推荐、健康推荐、快手菜推荐和探索推荐统一到同一个推荐接口。
- 已完成探索推荐重排，在 LightGBM Top50 候选上结合用户偏好差异、新颖度、图片可用性、热门度、评分和多样性惩罚生成探索型结果。
- 已完成个性化 TopK 补齐逻辑，当最终 MMR Top10 不足以满足 Top20/Top50 请求时，自动从 LightGBM Top50 候选补齐。
- 已完成离线指标评估。
- 已完成消融实验报告。

### 服务层

- 已完成简单登录注册接口 `POST /auth/register` 和 `POST /auth/login`。
- 已使用 SQLite 保存本地演示账号，并使用 PBKDF2 哈希保存密码。
- 已支持账号绑定 Food.com User ID，使个性化推荐和反馈闭环有明确用户身份。
- 已完成 FastAPI 推荐接口。
- 已完成冷启动推荐接口 `POST /recipes/cold-start`。
- 已完成统一场景推荐接口 `POST /recipes/scenario-recommend`。
- 已完成食谱详情接口。
- 已完成搜索接口。
- 已完成相似食谱接口。
- 已完成反馈接口。
- 已完成曝光接口。
- 已完成反馈事件发送 Kafka，支持将点击、喜欢、不喜欢、评分等行为写入 `recipe_feedback` topic。
- 已新增 Kafka 消费端脚本，可消费反馈事件并更新 Redis 实时用户画像。
- 已新增基于 ALS embedding + FAISS 的实时推荐缓存，用户反馈后可生成 `recipe:realtime_rec:user:{user_id}:k:{top_k}`。
- 推荐接口已支持优先读取实时推荐缓存，未命中时回退到离线推荐结果。
- 已完成 A/B 分组和指标接口。
- 已完成 Prometheus 指标接口。

### 搜索层

- 已接入 Elasticsearch 9.1.3。
- 已创建 `recipes` 索引。
- 已导入 178,265 个食谱文档。
- 详情和搜索接口优先读取 ES。

### 前端层

- 首页已完成食谱主题展示。
- 首页已更新当前系统规模、主排序模型和技术栈展示。
- 已新增登录注册页，支持创建本地演示账号并绑定 Food.com User ID。
- 导航栏已显示当前登录用户和绑定的推荐用户 ID，并支持退出登录。
- 推荐页已从单一用户 ID 推荐页升级为多场景推荐控制台。
- 推荐页已支持 `Personalized` 个性化推荐、`Pantry` 食材推荐、`Healthy` 健康推荐、`Quick meals` 快手菜推荐和 `Explore` 探索推荐。
- 推荐页已支持食材快捷按钮、健康目标按钮、制作时间选择、探索强度滑杆、TopK 切换和是否优先有图。
- 推荐页已接入前端反馈按钮，支持登录用户对推荐结果进行 `Like`、`Dislike` 和 1-5 分评分，并写入后端 `/feedback` 接口。
- 搜索页已接入食谱搜索。
- 详情页已展示配料、步骤、营养、人份、作者、原链接和相似食谱。
- 卡片评分已改为真实评分字段，不再展示内部模型分数。

### 工程层

- 已新增官方数据划分导入脚本。
- 已新增 pandas 版召回合并实现。
- 已新增 pandas 版排序特征导出实现。
- 已完成三节点 Spark standalone 集群接入。
- 已使用项目 Spark 画像构建任务验证集群运行能力，处理 20,000 条训练交互、178,265 条食谱数据和 200,000 条标签/配料样本，并成功生成用户画像和食谱画像。
- 已接入 MinIO 作为离线产物仓库，已上传本地完整 `data/` 和 `models/` 关键产物，方便演示时直接同步而不重新训练。
- 已更新 README。
- 已补充相关测试。
- 已跑通关键编译检查和轻量测试。
- 已完成本地联调验证：FastAPI 后端运行在 `http://localhost:8000`，Vue 前端运行在 `http://localhost:3000`，前端 `/api` 可正常代理到后端。
- 已通过真实数据 smoke 测试：`ingredients`、`personalized`、`explore` 三类场景推荐接口均可返回结果。
- 已通过前端代理反馈 smoke 测试：`POST http://localhost:3000/api/feedback` 可正常写入评分反馈并返回实时画像状态。
- 已通过真实 HTTP 登录注册 smoke 测试：注册账号、登录账号、读取绑定用户 ID 并请求个性化推荐均可正常返回。

## 十四、常用命令

### 1. 导入官方训练集、验证集和测试集

```powershell
.\.venv\Scripts\python.exe scripts\import_foodcom_official_splits.py --split-dir data --recipe-file data\food-com\RAW_recipes.csv --canonical-dir data\recipe-canonical --processed-dir data\processed
```

### 2. 构建画像

```powershell
.\.venv\Scripts\python.exe spark_jobs\spark_build_profile.py --train data\processed\train_ratings.csv --movies data\processed\movies_clean.csv --tags data\processed\movie_tags.csv --output-dir data\features --max-tags-per-movie 50
```

### 3. 训练 ALS

```powershell
.\.venv\Scripts\python.exe spark_jobs\spark_als_train.py --train data\processed\train_ratings.csv --factors-dir data\factors --recall-dir data\recall --model-dir models\spark_als --rank 24 --max-iter 6 --reg-param 0.1 --top-n 50
```

### 4. 导出 FAISS 向量

```powershell
.\.venv\Scripts\python.exe spark_jobs\spark_export_faiss_vectors.py --movie-factors data\factors\movie_factors.csv --output-dir data\faiss --normalize true
```

### 5. 合并召回

```powershell
.\.venv\Scripts\python.exe scripts\merge_recall_pandas.py --als data\recall\als_recall.csv --itemcf data\recall\itemcf_recall.csv --embedding data\recall\faiss_hnsw_recall.csv --lightgcn data\recall\lightgcn_recall.csv --content data\recall\content_recall.csv --hot data\recall\hot_recall.csv --output data\recall\merged_recall_candidates.csv --top-n 100
```

### 6. 导出排序特征

```powershell
.\.venv\Scripts\python.exe scripts\export_rank_features_pandas.py --user-profile data\features\user_profile.csv --movie-profile data\features\movie_profile.csv --merged-recall data\recall\merged_recall_candidates.csv --train-ratings data\processed\train_ratings.csv --test-ratings data\processed\test_ratings.csv --output-dir data\rank --candidate-chunk-size 300000
```

### 7. 训练 XGBoost

```powershell
.\.venv\Scripts\python.exe rank\train_from_spark_features.py --train data\rank\rank_train.csv --features data\rank\rank_feature_columns.json --model-output models\xgb_rank_model_spark.json --model-features-output models\xgb_rank_feature_columns.json --metrics-output data\rank\xgb_train_metrics.json --importance-output data\rank\xgb_feature_importance.csv --n-estimators 120 --max-depth 5 --learning-rate 0.05
```

### 8. 训练增强排序模型

```powershell
.\.venv\Scripts\python.exe rank\train_enhanced_ranker.py
```

该脚本直接复用 `data/rank/` 下已有训练集和候选集，不重新跑 Spark 和召回阶段。输出目录：

```text
data/rank/enhanced/
models/enhanced_ranker/
```

### 9. 预测 XGBoost 基线 Top50

```powershell
.\.venv\Scripts\python.exe rank\predict_from_spark_features.py --candidates data\rank\rank_candidates.csv --model models\xgb_rank_model_spark.json --features models\xgb_rank_feature_columns.json --output data\rank\ranked_top50.csv --top-n 50
```

### 10. 使用 LightGBM Top50 做 MMR 重排

```powershell
.\.venv\Scripts\python.exe rank\mmr_rerank.py --ranked data\rank\enhanced\ranked_top50_enhanced.csv --movie-profile data\features\movie_profile.csv --output data\rank\ranked_top10_mmr.csv --top-n 10 --lambda-rel 0.7
```

### 11. 评估和消融

```powershell
.\.venv\Scripts\python.exe evaluate\offline_metrics.py --test data\processed\test_ratings.csv --movie-profile data\features\movie_profile.csv --output-dir data\eval --ks 10
.\.venv\Scripts\python.exe evaluate\ablation_eval.py --metrics data\eval\offline_metrics.csv --output-dir data\eval --k 10
```

### 12. 推荐理由和图片增强

```powershell
.\.venv\Scripts\python.exe scripts\run_reason_generation.py --use-llm false
.\.venv\Scripts\python.exe scripts\enrich_recipe_images.py --enhanced data\recipe_enhanced_v3.csv --profile data\features\movie_profile.csv --recommendations data\final\recommendations_with_reasons.csv --metadata-output data\recipe-canonical\recipe_enhanced_metadata.csv
```

### 13. 重建 ES

```powershell
.\.venv\Scripts\python.exe scripts\index_recipes_to_es.py --es-url http://localhost:9200 --index recipes --recreate --batch-size 1000
```

检查 ES：

```powershell
curl.exe http://localhost:9200/_cat/indices/recipes?v
```

### 14. MinIO 产物同步

查看 MinIO 中已有离线产物：

```powershell
.\.venv\Scripts\python.exe scripts\sync_minio_artifacts.py list
```

上传本地离线产物：

```powershell
.\.venv\Scripts\python.exe scripts\sync_minio_artifacts.py upload
```

从 MinIO 下载产物到当前项目：

```powershell
.\.venv\Scripts\python.exe scripts\sync_minio_artifacts.py download
```

### 15. Kafka 实时反馈消费

```powershell
.\.venv\Scripts\python.exe scripts\kafka_feedback_consumer.py
```

只验证少量事件：

```powershell
.\.venv\Scripts\python.exe scripts\kafka_feedback_consumer.py --max-events 10
```

### 16. 运行后端

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 17. 运行前端

```powershell
cd frontend
npm run dev
```

前端默认运行在：

```text
http://localhost:3000
```

后端默认运行在：

```text
http://localhost:8000
```

Vite 已配置 `/api` 代理到 `http://localhost:8000`，因此前端页面可以直接调用后端接口。

### 18. 场景推荐接口测试

健康检查：

```powershell
Invoke-RestMethod -Uri http://localhost:8000/health | ConvertTo-Json -Depth 4
```

注册并登录演示账号：

```powershell
$username = "demo_$(Get-Date -Format 'HHmmss')"
$register = @{ username=$username; password='secret123'; display_name='Demo User'; recipe_user_id=1535 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/auth/register -Body $register -ContentType 'application/json'

$login = @{ username=$username; password='secret123' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/auth/login -Body $login -ContentType 'application/json'
```

食材推荐：

```powershell
$body = @{ scenario='ingredients'; ingredients=@('chicken','egg'); limit=3; require_image=$true } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/recipes/scenario-recommend -Body $body -ContentType 'application/json'
```

探索推荐：

```powershell
$body = @{ scenario='explore'; user_id=1535; limit=3; exploration=0.65 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/recipes/scenario-recommend -Body $body -ContentType 'application/json'
```

通过前端代理测试后端：

```powershell
$body = @{ scenario='explore'; user_id=1535; limit=3; exploration=0.65 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:3000/api/recipes/scenario-recommend -Body $body -ContentType 'application/json'
```

反馈接口测试：

```powershell
$body = @{ user_id=1535; movie_id=101; feedback_type='rating'; feedback_value=5; rank_position=2; score=0.8; reason='frontend feedback smoke' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:3000/api/feedback -Body $body -ContentType 'application/json'
```

### 19. 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_foodcom_official_splits.py tests\test_content_hot_recall.py tests\test_foodcom_conversion.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_faiss_hnsw_recall.py tests\test_offline_metrics.py tests\test_ablation_eval.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_api.py tests\test_ab_monitor_lightgcn.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_minio_artifacts.py tests\test_kafka_feedback.py tests\test_cold_start.py -q
cd frontend
npm run build
```

## 十五、后续优化方向

1. 优化官方数据划分的召回命中率。

   当前最重要的问题是官方测试集正样本没有被召回候选覆盖。应优先提升召回覆盖，再讨论排序效果。

2. 使用验证集自动调融合权重。

   当前融合权重是人工设定。后续可以用验证集调 ALS、ItemCF、FAISS、LightGCN、内容召回、热门召回的权重。

3. 增强长尾召回。

   Food.com 食谱长尾明显，需要针对低频食谱加入长尾召回、标签召回或相似配料召回。

4. 深化 Spark 集群全量离线链路。

   当前已经完成三节点 Spark standalone 集群接入，并通过项目离线画像构建任务验证。后续如果接入 HDFS、共享目录或其他分布式存储，可以进一步把全量画像构建、ALS、ItemCF、召回合并和排序特征导出固定为 Spark 集群任务，形成更完整的分布式离线计算链路。

5. 增强 Kafka 实时推荐闭环。

   当前反馈事件已经可以写入 Kafka，并由消费端更新 Redis 实时画像、触发 FAISS 相似食谱召回、写入实时推荐缓存，推荐接口会优先读取实时缓存。后续可以进一步加入实时排序、实时推荐 Topic 下游消费、滑动窗口统计和在线特征更新。

6. 升级冷启动推荐体验。

   当前后端已经支持根据口味、食材、烹饪时间、饮食目标和图片要求生成冷启动推荐，前端推荐控制台也已经接入食材、健康和快手菜场景。后续可以继续增加新用户引导页，并补充更多偏好维度，例如过敏原、忌口、厨房设备、预算和家庭人数。

7. 建立反馈回流训练机制。

   当前用户反馈已经能进入 Kafka、Redis 和 SQLite。后续可以将高价值反馈周期性转换为训练样本，合并进下一轮离线训练，使推荐模型真正吸收用户新行为。

8. 增加离线任务调度。

   当前离线链路主要通过脚本执行。后续可以接入 Airflow 或 Azkaban，定时运行数据处理、画像构建、召回、排序、评估、推荐结果导出和 ES 索引更新。

9. 使用 GPU 训练 LightGCN。

   当前 LightGCN 可以使用 PyTorch，后续 CUDA 环境稳定后可以切到 GPU。

10. 升级推荐理由。

   当前最终推荐理由使用模板生成。本地 Qwen 可作为后续增强，用于生成更自然的个性化解释。

11. 前端美化。

   当前前端已经完成食谱主题、多场景推荐控制台、搜索页和详情页。后续可以继续统一视觉模板、增加更精细的筛选控件、反馈按钮、推荐解释面板和指标展示面板。
