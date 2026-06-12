# Spark 预处理实现说明

## 脚本路径

```text
spark_jobs/spark_preprocess.py
```

该脚本是 Spark 离线处理层的第一步，只生成旁路离线产物，不修改当前 pandas 版 `FeaturePipeline`，不修改 FastAPI 接口，不修改 Vue 前端，也不会训练 ALS、FAISS 或 XGBoost。

## 输入文件

默认输入目录：

```text
data/ml-latest-small
```

需要包含：

```text
ratings.csv
movies.csv
tags.csv
links.csv
```

如果默认目录不存在，脚本会自动查找包含上述四个文件的目录，并在日志中输出实际使用的输入目录。

## 输出文件

默认输出目录：

```text
data/processed
```

输出三个单文件 CSV：

```text
data/processed/ratings_clean.csv
data/processed/movies_clean.csv
data/processed/movie_tags.csv
```

## 清洗规则

### ratings_clean.csv

处理规则：

1. 去除重复评分记录。
2. 删除 `userId`、`movieId`、`rating` 为空或类型转换失败的记录。
3. `userId` 转为 `int`。
4. `movieId` 转为 `int`。
5. `rating` 转为 `double`。
6. `timestamp` 转为 `long`。
7. 新增 `rating_norm = rating / 5.0`。

保留字段：

```text
userId
movieId
rating
rating_norm
timestamp
```

### movies_clean.csv

处理规则：

1. 去除重复电影记录。
2. 删除 `movieId` 或 `title` 为空的记录。
3. `movieId` 转为 `int`。
4. 从标题末尾的 `(YYYY)` 中提取 `year`。
5. 去掉标题末尾年份，生成 `clean_title`。
6. 将 `genres` 按 `|` 拆分；`(no genres listed)` 输出为空数组。
7. 计算 `genre_count`。

保留字段：

```text
movieId
title
clean_title
year
genres
genre_count
```

说明：Spark 内部按 `array<string>` 处理 `genres`；写入 CSV 时使用 `|` 拼接，例如 `Adventure|Comedy`。这样和 MovieLens 原始格式保持兼容，后续 Spark 脚本可继续用 `split('|')` 读回数组。

### movie_tags.csv

处理规则：

1. 从 `movies.csv` 的 genres 拆分出 `tag_type = genre` 的标签。
2. 从 `tags.csv` 的用户标签生成 `tag_type = user_tag` 的标签。
3. tag 统一转为小写。
4. 去除空 tag。
5. 按 `movieId`、`tag`、`tag_type` 去重。

保留字段：

```text
movieId
tag
tag_type
```

## 字段说明

| 文件 | 字段 | 说明 |
| --- | --- | --- |
| `ratings_clean.csv` | `userId` | MovieLens 用户 ID |
| `ratings_clean.csv` | `movieId` | MovieLens 电影 ID |
| `ratings_clean.csv` | `rating` | 原始评分 |
| `ratings_clean.csv` | `rating_norm` | 归一化评分，`rating / 5.0` |
| `ratings_clean.csv` | `timestamp` | 原始评分时间戳 |
| `movies_clean.csv` | `movieId` | MovieLens 电影 ID |
| `movies_clean.csv` | `title` | 原始电影标题 |
| `movies_clean.csv` | `clean_title` | 去掉年份后的电影标题 |
| `movies_clean.csv` | `year` | 从标题中提取的年份，无法提取时为空 |
| `movies_clean.csv` | `genres` | 使用 `|` 拼接的类型字符串，空类型输出为空字符串 |
| `movies_clean.csv` | `genre_count` | 类型数量 |
| `movie_tags.csv` | `movieId` | MovieLens 电影 ID |
| `movie_tags.csv` | `tag` | 小写标签文本 |
| `movie_tags.csv` | `tag_type` | `genre` 或 `user_tag` |

## 运行命令

默认运行：

```bash
python spark_jobs/spark_preprocess.py
```

指定输入输出目录：

```bash
python spark_jobs/spark_preprocess.py --input-dir data/ml-latest-small --output-dir data/processed
```

如果缺少 PySpark：

```bash
pip install -r requirements.txt
```

或单独安装：

```bash
pip install pyspark
```

Windows 下还需要确保 Java 可用：

```bash
java -version
```

如果 Java 或 `JAVA_HOME` 配置有问题，脚本会给出明确错误提示。

## 运行结果示例

日志会打印：

```text
Input directory: .../data/ml-latest-small
Output directory: .../data/processed
ratings raw rows: 100836
ratings clean rows: 100836
movies raw rows: 9742
movies clean rows: 9742
movie_tags rows: ...
rating range: 0.5 - 5.0
user count: 610
movie count: 9742
wrote ratings_clean.csv: True
wrote movies_clean.csv: True
wrote movie_tags.csv: True
all outputs written successfully: True
```

## 与原 FeaturePipeline 的关系

当前原项目仍然使用：

```text
feature/pipeline.py
```

读取和处理 MovieLens 数据。本脚本输出的 `data/processed/*.csv` 暂时只是 Spark 离线层产物，不会替换当前线上推荐链路。

后续可以在确认 Spark 输出稳定后，再让 `FeaturePipeline` 增加可选读取 processed 数据的能力。这个动作不属于本阶段。

## 下一步如何接 spark_train_test_split.py

下一阶段实现：

```text
spark_jobs/spark_train_test_split.py
```

它应该读取：

```text
data/processed/ratings_clean.csv
```

并输出：

```text
data/processed/train_ratings.csv
data/processed/test_ratings.csv
```

推荐切分策略：

1. 按 `userId` 分组。
2. 按 `timestamp` 倒序排序。
3. 每个用户最新一条评分进入测试集。
4. 其余评分进入训练集。
