# 🎬 MovieRec — 基于 FAISS + XGBoost 的工业级电影推荐系统

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.0-brightgreen.svg)](https://vuejs.org/)
[![FAISS](https://img.shields.io/badge/FAISS-1.9.0-red.svg)](https://github.com/facebookresearch/faiss)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.1.4-orange.svg)](https://xgboost.readthedocs.io/)
[![Redis](https://img.shields.io/badge/Redis-7.0-dc382d.svg)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ed.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**MovieRec** 是一个基于 MovieLens 数据集构建的工业级电影推荐系统，采用 **多阶段推荐架构**（召回 → 粗排 → 精排 → 重排），融合了 **协同过滤**、**向量检索** 和 **机器学习排序** 三大技术范式。

---

## 📋 目录

- [系统架构](#-系统架构)
- [推荐流程](#-推荐流程)
- [技术栈](#-技术栈)
- [核心算法详解](#-核心算法详解)
  - [1. 矩阵分解 (Matrix Factorization)](#1-矩阵分解-matrix-factorization)
  - [2. FAISS HNSW 近似最近邻检索](#2-faiss-hnsw-近似最近邻检索)
  - [3. XGBoost 排序模型](#3-xgboost-排序模型)
  - [4. Redis 缓存策略](#4-redis-缓存策略)
- [项目结构](#-项目结构)
- [快速开始](#-快速开始)
  - [本地开发环境](#本地开发环境)
  - [Docker 一键部署](#docker-一键部署)
- [API 文档](#-api-文档)
- [前端界面](#-前端界面)
- [性能优化](#-性能优化)
- [测试](#-测试)
- [数据集](#-数据集)
- [常见问题](#-常见问题)
- [后续规划](#-后续规划)
- [许可证](#-许可证)

---

## 🏗 系统架构

```
                               ┌──────────────────────────┐
                               │    MovieLens Dataset      │
                               │  ratings / movies / tags  │
                               └────────────┬─────────────┘
                                            │
                               ┌────────────▼─────────────┐
                               │    Feature Pipeline       │
                               │  • 数据清洗与校验         │
                               │  • 用户/电影特征工程      │
                               │  • 流派多热编码           │
                               │  • 评分矩阵构建           │
                               └────────────┬─────────────┘
                                            │
                               ┌────────────▼─────────────┐
                               │  Matrix Factorization     │
                               │  ALS 交替最小二乘法       │
                               │  用户向量 ←→ 物品向量    │
                               └────────────┬─────────────┘
                                            │
                               ┌────────────▼─────────────┐
                               │  FAISS IndexHNSWFlat      │
                               │  HNSW 图 + 精确距离计算   │
                               │  余弦相似度 (内积)        │
                               └────────────┬─────────────┘
                                            │
              ┌─────────────────┬───────────┼───────────┬─────────────────┐
              │                 │           │           │                 │
     ┌────────▼────────┐ ┌─────▼─────┐ ┌───▼────┐ ┌───▼──────┐ ┌───────▼──────┐
     │  Recall Layer   │ │   Redis   │ │  Rank  │ │  Cache   │ │  FastAPI     │
     │  FAISS HNSW     │ │  Cache    │ │ XGBoost│ │  Aside   │ │  REST API    │
     │  Top-K ANN      │ │  Store    │ │ Rerank │ │  Pattern │ │  Gateway     │
     └────────┬────────┘ └─────┬─────┘ └───┬────┘ └───┬──────┘ └───────┬──────┘
              │                 │           │           │                 │
              └─────────────────┴───────────┴───────────┴─────────────────┘
                                            │
                               ┌────────────▼─────────────┐
                               │    Vue 3 + TailwindCSS    │
                               │    Responsive SPA         │
                               └──────────────────────────┘
```

---

## 🔄 推荐流程

一个完整的推荐请求经过以下流水线：

```
用户请求 (user_id, top_k=20)
    │
    ▼
┌─────────────────┐
│  1. Cache Check  │  ← 命中则直接返回 (Redis, TTL=30min)
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│  2. Recall       │  ← FAISS HNSW 检索 Top-200 候选
│     ANN Search   │     冷启动用户回退到热门推荐
└────────┬────────┘
         │ 200 candidates
         ▼
┌─────────────────┐
│  3. Filter       │  ← 过滤已评分电影
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. Feature      │  ← 构建 9 维特征向量
│     Construction │     (用户特征 + 电影特征 + 交叉特征)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. Rank         │  ← XGBoost 模型打分
│     XGBoost      │
└────────┬────────┘
         │ Scored candidates
         ▼
┌─────────────────┐
│  6. Sort &       │  ← 按预测分降序 → 返回 Top-20
│     Return       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  7. Write Cache  │  ← 写入 Redis (TTL + 15% jitter)
└─────────────────┘
```

---

## 📚 技术栈

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **API 网关** | FastAPI + Uvicorn | 0.115 / 0.34 | 异步 RESTful API，自带 Swagger 文档 |
| **特征工程** | Pandas + NumPy + SciPy | 2.2 / 2.2 / 1.15 | 数据清洗、特征构建、稀疏矩阵运算 |
| **嵌入层** | ALS Matrix Factorization | — | 学习用户/物品的稠密向量表示 (64维) |
| **召回层** | FAISS IndexHNSWFlat | 1.9.0 | HNSW 图结构的近似最近邻检索 |
| **排序层** | XGBoost | 2.1.4 | 基于特征的 Learning-to-Rank 精排模型 |
| **缓存层** | Redis | 7.0+ | Cache-Aside 模式，防穿透/击穿/雪崩 |
| **前端** | Vue 3 + Vite + TailwindCSS | 3.x | 响应式单页应用 |
| **部署** | Docker + Docker Compose | — | 三容器编排 (API + Frontend + Redis) |
| **测试** | Pytest + httpx | 8.3 / 0.28 | 单元测试 + API 集成测试 |

---

## 🧠 核心算法详解

### 1. 矩阵分解 (Matrix Factorization)

#### 数学原理

采用 **ALS (Alternating Least Squares)** 算法，将稀疏的用户-物品评分矩阵 $R_{m \times n}$ 分解为两个低秩矩阵的乘积：

$$R \approx U \times V^T$$

其中 $U \in \mathbb{R}^{m \times k}$ 为用户隐向量矩阵，$V \in \mathbb{R}^{n \times k}$ 为物品隐向量矩阵，$k=64$ 为隐向量维度。

**目标函数** (带 L2 正则化):

$$\min_{U, V} \sum_{(i,j) \in \Omega} (R_{ij} - U_i V_j^T)^2 + \lambda(\|U\|^2 + \|V\|^2)$$

#### ALS 迭代过程

ALS 的核心思想是：固定一个矩阵，优化另一个矩阵，交替进行。每次迭代将非凸问题转化为凸优化问题：

1. **固定 $V$，求解 $U$**：对每个用户 $u$，求解线性方程组 $(V_u^T V_u + \lambda I) U_u = V_u^T R_u$
2. **固定 $U$，求解 $V$**：对每个物品 $i$，求解线性方程组 $(U_i^T U_i + \lambda I) V_i = U_i^T R_i$
3. **交替更新偏置项**：用户偏置 $b_u$ 和物品偏置 $b_i$

```python
# 超参数配置
n_factors = 64          # 隐向量维度
regularization = 0.1    # L2 正则化系数
iterations = 20         # ALS 迭代次数
```

#### 为什么选择 ALS？

- ✅ **可并行化**：每个用户/物品的更新相互独立
- ✅ **隐式反馈友好**：容易扩展到隐式反馈场景
- ✅ **收敛稳定**：每次迭代目标函数单调递减
- ✅ **冷启动处理**：新用户可用物品相似度退化


### 2. FAISS HNSW 近似最近邻检索

#### HNSW 图结构

**HNSW (Hierarchical Navigable Small World)** 是一种基于图的 ANN 算法，其核心是构建多层导航图：

```
Layer 2:   ● ─────────── ●          ← 稀疏"高速公路"层，长距离跳跃
           │              │
Layer 1:   ● ─── ● ─── ● ─── ●      ← 中等密度，加速粗定位
           │     │     │     │
Layer 0:   ●─●─●─●─●─●─●─●─●─●     ← 稠密局部连接，精确搜索
```

**层级分配**：每个节点以概率 $P = \frac{1}{M_L}$ 逐层向上提升（指数衰减），$M_L = \frac{1}{\log(M)}$。因此：
- 99% 的节点仅在 Layer 0
- 少数节点出现在高层形成"高速公路"

#### 搜索过程

1. 从顶层入口点开始
2. 在当前层贪婪搜索最近邻
3. 下降到下一层，以上一层找到的点为起点
4. 重复直到 Layer 0，执行精细搜索

**时间复杂度**：$O(\log N)$，相比暴力搜索的 $O(N)$ 有数量级提升。

#### 关键参数配置

| 参数 | 默认值 | 作用 | 调优建议 |
|------|--------|------|----------|
| **M** | 32 | 每节点双向链接数 | 内存充足可增至 48~64 提高召回率 |
| **efConstruction** | 200 | 构建阶段搜索宽度 | 越大索引质量越高，构建越慢 |
| **efSearch** | 64 | 查询阶段搜索宽度 | 可运行时动态调整，越大越准越慢 |

#### IndexHNSWFlat 的优势

- **HNSW 图**：对数级搜索复杂度
- **Flat 存储**：候选集精确距离计算，无压缩损失
- **内积度量**：配合 L2 归一化向量 = 余弦相似度
- **增量插入**：支持不重建索引添加新向量


### 3. XGBoost 排序模型

#### 特征设计

模型使用 **9 维特征向量** 对每个 (用户, 候选电影) 对进行打分：

| # | 特征名 | 类型 | 描述 |
|---|--------|------|------|
| 1 | `user_avg_rating` | 用户统计 | 用户历史评分的均值 |
| 2 | `user_rating_count` | 用户统计 | 用户评分的总次数 |
| 3 | `user_rating_std` | 用户统计 | 用户评分的标准差（偏好波动） |
| 4 | `movie_avg_rating` | 物品统计 | 电影的平均评分 |
| 5 | `movie_rating_count` | 物品统计 | 电影的总评价数（热度） |
| 6 | `movie_popularity` | 物品统计 | **贝叶斯加权**流行度得分 |
| 7 | `embedding_similarity` | 交叉特征 | 用户-电影向量余弦相似度 |
| 8 | `genre_match_score` | 交叉特征 | 用户流派偏好 × 电影流派向量 |
| 9 | `movie_year` | 物品属性 | 电影发行年份 |

#### 贝叶斯流行度得分

$$Popularity = \frac{v}{v + m} \cdot \bar{R} + \frac{m}{v + m} \cdot C$$

其中 $v$ 为电影评分数，$\bar{R}$ 为电影平均分，$m$ 为 90% 分位线评分数，$C$ 为全局平均分。

#### 模型配置

```python
XGBRegressor(
    n_estimators=200,       # 树的数量
    max_depth=6,            # 树的最大深度
    learning_rate=0.05,     # 学习率
    subsample=0.8,          # 样本采样率（防过拟合）
    colsample_bytree=0.8,   # 特征采样率
    reg_alpha=0.1,          # L1 正则化
    reg_lambda=1.0,         # L2 正则化
)
```


### 4. Redis 缓存策略

#### Cache-Aside 模式

```
Read:
  请求 → 查缓存 → Hit → 返回
                → Miss → 从源加载 → 写缓存 → 返回

Write:
  请求 → 写数据源 → 失效/更新缓存
```

#### 三大缓存问题的防护

| 问题 | 现象 | 解决方案 |
|------|------|----------|
| **缓存穿透** (Penetration) | 请求不存在的 key，每次都打到数据库 | 缓存空值标记 `__NULL__`，TTL=60s |
| **缓存击穿** (Breakdown) | 热点 key 过期瞬间大量并发请求 | 分布式互斥锁 (SETNX) 控制刷新 |
| **缓存雪崩** (Avalanche) | 大量 key 同时过期，服务压力骤增 | 所有 TTL 添加 ±15% 随机抖动 |

#### TTL 分层设计

| 数据类型 | 基础 TTL | 抖动范围 | 原因 |
|----------|----------|----------|------|
| 用户画像 | 3600s (1h) | 3060~4140s | 用户兴趣短期稳定 |
| 推荐结果 | 1800s (30min) | 1530~2070s | 推荐结果需要定期刷新 |
| 热门电影 | 600s (10min) | 510~690s | 热门榜变化较快 |
| Top-K 候选 | 300s (5min) | 255~345s | 候选集变化频率高 |
| 空值标记 | 60s | — | 防止穿透，短 TTL 减少误伤 |

---

## 📂 项目结构

```
recommend/
│
├── app/                            # 🎯 应用核心
│   ├── main.py                     # FastAPI 入口 + 生命周期管理
│   ├── config.py                   # 集中配置 (pydantic-settings)
│   └── logging_config.py           # 日志配置
│
├── api/                            # 🌐 API 层
│   ├── routes.py                   # 路由处理器 (7 个端点)
│   └── schemas.py                  # Pydantic 请求/响应模型
│
├── feature/                        # 🔧 特征工程
│   ├── pipeline.py                 # 完整 ETL 管线 (加载→清洗→特征)
│   └── user_profile.py             # 用户画像构建器
│
├── embedding/                      # 🧮 嵌入层
│   ├── matrix_factorization.py     # ALS 矩阵分解实现
│   └── embedding_service.py        # 嵌入训练 + 查询服务
│
├── recall/                         # 🔍 召回层
│   ├── faiss_index.py              # FAISS HNSW 索引封装
│   └── recall_service.py           # 召回编排 (嵌入 → ANN 搜索)
│
├── rank/                           # 📊 排序层
│   ├── train.py                    # XGBoost 训练 + 数据构建器
│   └── rank_model.py               # 排序服务 (特征构建 + 推理)
│
├── cache/                          # ⚡ 缓存层
│   └── redis_cache.py              # Redis 封装 (Cache-Aside + 三防)
│
├── frontend/                       # 🖥️ Vue 3 前端
│   ├── src/
│   │   ├── api/index.js            # Axios API 客户端
│   │   ├── components/             # NavBar / MovieCard /
│   │   │                           #   UserProfile / PopularMovies
│   │   ├── views/                  # Home / Recommend / Search /
│   │   │                           #   MovieDetail
│   │   └── router/index.js         # Vue Router 路由配置
│   ├── nginx.conf                  # Nginx 生产部署配置
│   ├── vite.config.js              # Vite 构建配置
│   └── tailwind.config.js          # TailwindCSS 配置
│
├── scripts/                        # 🛠️ 工具脚本
│   ├── download_data.py            # 下载 MovieLens 数据集
│   ├── build_index.py              # 完整构建管线
│   └── init_redis.py               # Redis 缓存预热
│
├── tests/                          # 🧪 测试
│   ├── test_api.py                 # API 集成测试
│   ├── test_recall.py              # FAISS 索引 + 嵌入测试
│   └── test_cache.py               # 缓存逻辑测试
│
├── docker-compose.yml              # 🐳 三服务编排
├── Dockerfile                      # 后端 API 镜像
├── Dockerfile.frontend             # 前端 Nginx 镜像
├── requirements.txt                # Python 依赖
├── .env.example                    # 环境变量模板
├── .gitignore                      # Git 忽略规则
├── start.bat                       # Windows 启动脚本
├── stop.bat                        # Windows 停止脚本
└── README.md                       # 📖 本文档
```

---

## 🚀 快速开始

### 本地开发环境

#### 前置要求

- **Python** 3.10+
- **Redis** 7.0+
- **Node.js** 18+ (前端开发)
- **Git**

#### 1. 克隆仓库并安装依赖

```bash
git clone <your-repo-url>
cd recommend

# 创建虚拟环境
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt
```

#### 2. 下载数据并训练模型

```bash
# 下载 MovieLens 数据集 (ml-latest-small)
python scripts/download_data.py

# 一键执行完整管线:
#   数据下载 → 特征工程 → MF 训练 → FAISS 索引构建 → XGBoost 训练
python scripts/build_index.py
```

`build_index.py` 自动完成以下步骤：

| 步骤 | 内容 | 预估耗时 |
|------|------|----------|
| Step 1 | 下载 MovieLens 数据集 | ~10s (网络) |
| Step 2 | 运行特征工程管线 | ~5s |
| Step 3 | 训练 ALS 矩阵分解 (64维, 20轮) | ~30s |
| Step 4 | 构建 FAISS HNSW 索引 | ~3s |
| Step 5 | 训练 XGBoost 排序模型 | ~60s |
| **总计** | | **约 2 分钟** |

#### 3. 启动 Redis

```bash
# 使用 Docker（推荐）
docker run -d -p 6379:6379 --name redis redis:7-alpine

# 或使用本地安装的 Redis
redis-server
```

#### 4. 启动后端 API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后可访问：
- 🌐 **Swagger 文档**: http://localhost:8000/docs
- 📖 **ReDoc 文档**: http://localhost:8000/redoc
- ❤️ **健康检查**: http://localhost:8000/health

#### 5. 启动前端 (开发模式)

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器：http://localhost:3000

---

### Docker 一键部署

```bash
# 克隆仓库
git clone <your-repo-url>
cd recommend

# 启动所有服务 (Redis + API + Frontend)
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api
```

**三个容器服务：**

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| Redis | `rec-redis` | 6379 | 缓存层，maxmemory=256MB, LRU 淘汰 |
| API | `rec-api` | 8000 | FastAPI 后端，首次启动自动训练模型 |
| Frontend | `rec-frontend` | 3000 | Vue 3 SPA，Nginx 静态服务 |

> ⚠️ **注意**：首次启动 `api` 容器会自动下载数据并训练模型，约需 2~3 分钟。通过 `docker-compose logs -f api` 查看进度。

---

## 📡 API 文档

### 接口总览

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/recommend/{user_id}` | 个性化推荐 |
| `GET` | `/popular` | 热门电影列表 |
| `GET` | `/movie/{movie_id}` | 电影详情 |
| `GET` | `/user/{user_id}/profile` | 用户画像 |
| `GET` | `/search` | 电影搜索 |
| `POST` | `/rebuild-index` | 重建索引 |

---

### GET /health

健康检查接口，返回各组件运行状态。

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "redis": true,
  "faiss_index_size": 9724
}
```

---

### GET /recommend/{user_id}

获取个性化电影推荐。

**Parameters:**
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `user_id` | path:int | 必填 | 用户 ID (1~610) |
| `top_k` | query:int | 20 | 推荐数量 (1~100) |
| `use_cache` | query:bool | true | 是否使用 Redis 缓存 |

**Example:**
```bash
curl "http://localhost:8000/recommend/1?top_k=10"
```

**Response:**
```json
{
  "user_id": 1,
  "recommendations": [
    {
      "movie_id": 318,
      "title": "Shawshank Redemption, The (1994)",
      "score": 0.9821
    },
    {
      "movie_id": 858,
      "title": "Godfather, The (1972)",
      "score": 0.9673
    }
  ],
  "cached": false,
  "took_ms": 12.5
}
```

---

### GET /popular

获取热门电影排行榜 (按贝叶斯流行度得分排序)。

```bash
curl "http://localhost:8000/popular?limit=20"
```

---

### GET /movie/{movie_id}

获取电影详细信息。

```bash
curl "http://localhost:8000/movie/1"
```

**Response:**
```json
{
  "movie_id": 1,
  "title": "Toy Story (1995)",
  "genres": "Adventure|Animation|Children|Comedy|Fantasy",
  "avg_rating": 3.92,
  "rating_count": 215,
  "popularity_score": 3.84,
  "year": 1995.0
}
```

---

### GET /user/{user_id}/profile

获取用户画像：评分统计、流派偏好、历史记录。

```bash
curl "http://localhost:8000/user/1/profile"
```

---

### GET /search

按标题搜索电影 (子串匹配)。

**Parameters:**
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `q` | query:string | 必填 | 搜索关键词 |
| `limit` | query:int | 20 | 返回数量上限 |

```bash
curl "http://localhost:8000/search?q=Toy+Story&limit=10"
```

---

### POST /rebuild-index

重建 FAISS 索引并重新训练嵌入模型。此操作会清除相关缓存。

```bash
curl -X POST "http://localhost:8000/rebuild-index"
```

---

## 🖥️ 前端界面

前端是基于 **Vue 3 Composition API** + **Vite** + **TailwindCSS** 构建的响应式单页应用。

### 页面路由

| 路由 | 组件 | 说明 |
|------|------|------|
| `/` | `Home.vue` | 首页：系统介绍 + 快捷入口 |
| `/recommend` | `Recommend.vue` | 个性化推荐：输入用户 ID 获取推荐 |
| `/search` | `Search.vue` | 电影搜索：关键词搜索 |
| `/movie/:id` | `MovieDetail.vue` | 电影详情页 |
| `/user/:id` | `UserProfile.vue` | 用户画像页 |

### 核心组件

| 组件 | 功能 |
|------|------|
| `NavBar.vue` | 顶部导航栏，路由切换 |
| `MovieCard.vue` | 电影卡片：海报占位图 + 评分 + 年份 |
| `PopularMovies.vue` | 热门电影横向滚动列表 |
| `UserProfile.vue` | 用户画像：活跃度 + 流派偏好雷达 |

### 构建与部署

```bash
cd frontend

# 开发模式
npm run dev

# 生产构建
npm run build

# 预览构建产物
npm run preview
```

生产环境下由 Nginx 提供静态文件服务（见 `Dockerfile.frontend` 和 `nginx.conf`）。

---

## ⚡ 性能优化

| # | 优化策略 | 技术细节 | 效果 |
|---|----------|----------|------|
| 1 | **ANN 检索** | FAISS HNSW 实现 O(log N) 搜索 | 比暴力搜索快 100~1000x |
| 2 | **向量归一化** | L2 归一化后内积 = 余弦相似度 | 无需额外计算余弦 |
| 3 | **批量召回** | `search_batch()` 一次调用处理多用户 | 吞吐量提升 5~10x |
| 4 | **Cache-Aside** | Redis 缓存热点推荐结果 | 命中时延迟 < 1ms |
| 5 | **异步框架** | FastAPI + Uvicorn async | 非阻塞处理并发请求 |
| 6 | **召回-排序解耦** | 召回 200 候选 + 排序 Top-20 | 平衡精度与延迟 |
| 7 | **稀疏矩阵运算** | CSR/CSC 格式 ALS 高效求解 | 内存占用降低 80% |
| 8 | **TTL 抖动** | Redis ±15% 随机过期时间 | 防止缓存雪崩 |
| 9 | **模型预加载** | 启动时加载所有模型到内存 | 避免首次请求冷启动 |
| 10 | **特征缓存** | FeaturePipeline 序列化到磁盘 | 跳过重复的特征工程 |

### 延迟基准 (单次推荐请求)

| 场景 | 典型延迟 | 说明 |
|------|----------|------|
| 🟢 缓存命中 | < 1ms | Redis 直接返回 |
| 🟡 缓存未命中 (正常) | 10~20ms | FAISS 召回 + XGBoost 排序 |
| 🔴 冷启动 (无嵌入) | 5~15ms | 回退到热门推荐 |
| 🔵 首次启动 | ~2min | 数据加载 + 模型训练 |

---

## 🧪 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_api.py -v
pytest tests/test_recall.py -v
pytest tests/test_cache.py -v

# 生成覆盖率报告
pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html
```

### 测试覆盖

| 测试文件 | 测试内容 |
|----------|----------|
| `test_api.py` | API 端点：health / recommend / popular / search / movie |
| `test_recall.py` | FAISS 索引构建、搜索准确性、嵌入质量 |
| `test_cache.py` | Redis get/set、TTL 抖动、空值标记、pattern 删除 |

---

## 📊 数据集

本项目使用 **MovieLens Latest Small** 数据集：

| 文件 | 记录数 | 字段 |
|------|--------|------|
| `ratings.csv` | 100,836 | userId, movieId, rating, timestamp |
| `movies.csv` | 9,724 | movieId, title, genres |
| `tags.csv` | 3,683 | userId, movieId, tag, timestamp |
| `links.csv` | 9,724 | movieId, imdbId, tmdbId |

- **用户数**: 610
- **电影数**: 9,724
- **评分范围**: 0.5 ~ 5.0 (步长 0.5)
- **稀疏度**: ~1.7% (100,836 / 610×9,724)

> 📥 数据集来源：[GroupLens Research](https://grouplens.org/datasets/movielens/)

---

## ❓ 常见问题

<details>
<summary><b>Q: 首次启动很慢怎么办？</b></summary>

首次启动需要下载数据集 (~1MB) 并训练模型 (~2分钟)。后续启动会加载缓存的模型文件，速度很快。如果不需要重新训练，确保 `models/` 目录下的文件未被删除。
</details>

<details>
<summary><b>Q: Redis 连接失败怎么办？</b></summary>

系统设计为 **Redis 可选**——如果 Redis 不可用，系统会自动降级为无缓存模式运行，不影响核心推荐功能。只需确保 Redis 服务已启动，或通过环境变量配置正确的连接地址。
</details>

<details>
<summary><b>Q: 如何添加新电影？</b></summary>

可以使用 `faiss_index.add()` 方法增量添加新的电影嵌入向量，无需完全重建索引。但建议周期性调用 `/rebuild-index` 接口进行全量重建以保证图质量。
</details>

<details>
<summary><b>Q: 如何切换到更大的 MovieLens 数据集？</b></summary>

修改 `.env` 中的 `MOVIELENS_URL` 为对应数据集的 URL（如 `ml-latest`），并调整 `MOVIELENS_DATA_DIR`。重新运行 `build_index.py` 即可。
</details>

<details>
<summary><b>Q: Docker Compose 启动后前端无法访问？</b></summary>

检查 `docker-compose ps` 确认三个容器都在运行。首次启动 `api` 需要训练模型，`frontend` 依赖 `api` 健康检查通过后才启动。查看日志：`docker-compose logs -f api`。
</details>

---

## 🔮 后续规划

- [ ] **多路召回融合**：Embedding 召回 + 协同过滤召回 + 热门召回
- [ ] **在线学习**：基于用户实时反馈更新模型 (Flink/Spark Streaming)
- [ ] **A/B 实验框架**：支持多模型在线效果对比
- [ ] **DeepFM/Wide&Deep**：引入深度排序模型作为 XGBoost 的替代
- [ ] **GPU 加速**：FAISS GPU 版本支持更大规模数据集
- [ ] **监控告警**：Prometheus + Grafana 监控推荐延迟与命中率
- [ ] **推荐理由**：输出可解释的推荐原因（"因为你喜欢 XX 类型"）
- [ ] **用户反馈闭环**：支持点赞/踩/不感兴趣等隐式反馈

---

## 📝 许可证

本项目采用 [MIT License](LICENSE) 开源。

MovieLens 数据集版权归 [GroupLens Research](https://grouplens.org/datasets/movielens/) 所有，使用需遵循其许可条款。

---

## 🙏 致谢

- [GroupLens Research](https://grouplens.org/) — MovieLens 数据集
- [Facebook Research](https://github.com/facebookresearch/faiss) — FAISS 向量检索引擎
- [XGBoost](https://xgboost.readthedocs.io/) — 梯度提升决策树框架
- [FastAPI](https://fastapi.tiangolo.com/) — 现代化的 Python Web 框架
- [Vue.js](https://vuejs.org/) — 渐进式 JavaScript 框架

---

<p align="center">
  <b>⭐ 如果这个项目对你有帮助，请给一个 Star！</b>
  <br>
  <sub>Made with ❤️ for the recommendation systems community</sub>
</p>
