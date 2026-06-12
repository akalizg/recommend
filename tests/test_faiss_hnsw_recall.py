from __future__ import annotations

import numpy as np
import pandas as pd


def test_faiss_hnsw_recall_outputs(tmp_path):
    import faiss

    from spark_jobs.spark_faiss_hnsw_recall import build_faiss_hnsw_recall

    vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.95, 0.05, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.95, 0.05],
        ],
        dtype="float32",
    )
    ids = np.array([10, 11, 20, 21], dtype="int64")
    index = faiss.IndexHNSWFlat(3, 8, faiss.METRIC_INNER_PRODUCT)
    index.add(vectors)

    train = pd.DataFrame(
        [
            {"userId": 1, "movieId": 10, "rating": 5.0},
            {"userId": 2, "movieId": 20, "rating": 5.0},
        ]
    )
    train_path = tmp_path / "train.csv"
    index_path = tmp_path / "faiss.index"
    index_ids_path = tmp_path / "index_ids.npy"
    vectors_path = tmp_path / "vectors.npy"
    vector_ids_path = tmp_path / "vector_ids.npy"
    output_path = tmp_path / "faiss_recall.csv"

    train.to_csv(train_path, index=False)
    faiss.write_index(index, str(index_path))
    np.save(index_ids_path, ids)
    np.save(vectors_path, vectors)
    np.save(vector_ids_path, ids)

    summary = build_faiss_hnsw_recall(
        train_path,
        index_path,
        index_ids_path,
        vectors_path,
        vector_ids_path,
        output_path,
        top_n=1,
        search_k=4,
    )

    assert summary["output_rows"] == 2
    output = pd.read_csv(output_path)
    assert set(output["recall_type"]) == {"embedding"}
    assert dict(zip(output["userId"], output["movieId"])) == {1: 11, 2: 21}
