# Spark 向量导出 FAISS 说明

## 脚本路径

```text
spark_jobs/spark_export_faiss_vectors.py
```

## 输入文件

```text
data/factors/movie_factors.csv
```

字段：

```text
movieId
features
```

## 输出文件

```text
data/faiss/movie_vectors.npy
data/faiss/movie_ids.npy
```

## features 字段解析方式

`features` 使用 `|` 分隔，例如：

```text
0.123|-0.532|0.881
```

脚本会将它解析为 `float32` NumPy 数组。所有行的 factor 维度必须一致。

## 向量归一化方式

默认启用 L2 归一化：

```bash
--normalize true
```

归一化方式：

```text
vector = vector / ||vector||
```

零向量会保留为零向量，避免除零。

## movie_vectors.npy 与 movie_ids.npy 的关系

两个文件按相同顺序保存：

```text
movie_vectors[i] 对应 movie_ids[i]
```

脚本按 `movieId` 升序排序后保存，保证输出稳定。

## 后续如何接入原项目 FAISS 构建脚本

当前原项目 FAISS 构建入口仍然是：

```text
recall/faiss_index.py
```

后续可以新增一个脚本读取：

```python
movie_vectors = np.load("data/faiss/movie_vectors.npy")
movie_ids = np.load("data/faiss/movie_ids.npy")
faiss_index.build(movie_vectors, movie_ids)
```

本阶段只导出 NumPy 文件，不替换当前线上 FAISS 索引。

## 运行命令

```bash
python spark_jobs/spark_export_faiss_vectors.py
```

指定参数：

```bash
python spark_jobs/spark_export_faiss_vectors.py --movie-factors data/factors/movie_factors.csv --output-dir data/faiss --normalize true
```

## 质量校验结果

脚本会检查：

1. `movie_vectors.npy` 存在。
2. `movie_ids.npy` 存在。
3. `movie_vectors.shape[0] == movie_ids.shape[0]`。
4. `movie_vectors.shape[1] == factor_dim`。
5. `movie_vectors.dtype == float32`。
6. 不存在 NaN 或 Inf。
7. normalize=true 时，非零向量范数接近 1。

当前统一运行脚本参数下：

```text
movie factors rows: 9701
factor dimension: 32
movie_vectors shape: (9701, 32)
movie_ids shape: (9701,)
normalize enabled: True
```

当前运行结果：通过。
