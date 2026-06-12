# Food.com 食谱主题迁移说明

当前工程已经从电影推荐主题迁移为食谱推荐主题。为了最大化复用原有 Spark、ALS、ItemCF、LightGCN、XGBoost、MMR 和理由生成流水线，内部仍使用一组兼容字段名：

| 兼容字段 | 食谱含义 |
| --- | --- |
| `movieId` | `recipe_id` |
| `title` / `movie_title` | 食谱名称 |
| `genres` / `movie_genres` | 食谱标签、菜系、场景、饮食属性 |
| `rating` | 用户对食谱的 1-5 分评价 |
| `tags.csv` | 食谱标签和配料 token |

## 数据位置

原始 Food.com 数据已放入：

```text
data/food-com/RAW_recipes.csv
data/food-com/RAW_interactions.csv
```

转换后的兼容输入输出到：

```text
data/recipe-canonical/ratings.csv
data/recipe-canonical/movies.csv
data/recipe-canonical/tags.csv
data/recipe-canonical/links.csv
data/recipe-canonical/recipe_metadata.csv
```

其中 `recipe_metadata.csv` 保留了分钟数、配料、营养、步骤数等食谱专属字段，后续可用于前端详情页、营养筛选和更强的推荐理由。

## 运行方式

只转换数据：

```bash
python scripts/convert_foodcom_to_movielens_schema.py
```

跑食谱主题完整离线链路：

```bash
python scripts/run_recipe_pipeline.py
```

如果只想先跑转换、预处理和切分，可跳过较慢阶段：

```bash
python scripts/run_recipe_pipeline.py --skip-profile-als --skip-recall --skip-rank --skip-mmr-eval --skip-reasons
```

默认会抽取一个本地可控规模的子集：最多 12000 个食谱、1500 个用户、120000 条交互。需要扩大规模时可调整：

```bash
python scripts/run_recipe_pipeline.py --max-recipes 30000 --max-users 5000 --max-interactions 300000
```
