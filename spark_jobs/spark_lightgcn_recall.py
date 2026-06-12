"""
Train a real LightGCN recall channel with PyTorch.

The surrounding project still uses legacy column names such as movieId, but in
the recipe migration those ids represent Food.com recipe ids.
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAIN = PROJECT_ROOT / "data" / "processed" / "train_ratings.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "recall" / "lightgcn_recall.csv"
DEFAULT_EMBED_DIR = PROJECT_ROOT / "data" / "lightgcn"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


class LightGCN(nn.Module):
    def __init__(self, n_users: int, n_items: int, embedding_dim: int, n_layers: int) -> None:
        super().__init__()
        self.n_users = n_users
        self.n_items = n_items
        self.n_layers = n_layers
        self.user_embedding = nn.Embedding(n_users, embedding_dim)
        self.item_embedding = nn.Embedding(n_items, embedding_dim)
        nn.init.normal_(self.user_embedding.weight, std=0.1)
        nn.init.normal_(self.item_embedding.weight, std=0.1)

    def propagate(self, norm_adj: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        all_emb = torch.cat([self.user_embedding.weight, self.item_embedding.weight], dim=0)
        outputs = [all_emb]
        emb = all_emb
        for _ in range(self.n_layers):
            emb = torch.sparse.mm(norm_adj, emb)
            outputs.append(emb)
        final = torch.stack(outputs, dim=0).mean(dim=0)
        return final[: self.n_users], final[self.n_users :]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train PyTorch LightGCN and emit recall candidates.")
    parser.add_argument("--train", default=str(DEFAULT_TRAIN))
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--embedding-dir", default=str(DEFAULT_EMBED_DIR))
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--min-rating", type=float, default=4.0)
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--layers", type=int, default=2)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--reg", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    return parser.parse_args()


def _device(name: str) -> torch.device:
    if name == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false.")
        return torch.device("cuda")
    if name == "auto" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _build_norm_adj(n_users: int, n_items: int, user_idx: np.ndarray, item_idx: np.ndarray, device: torch.device) -> torch.Tensor:
    rows = np.concatenate([user_idx, item_idx + n_users])
    cols = np.concatenate([item_idx + n_users, user_idx])
    deg = np.bincount(rows, minlength=n_users + n_items).astype(np.float32)
    deg[deg == 0] = 1.0
    values = 1.0 / np.sqrt(deg[rows] * deg[cols])
    indices = torch.tensor(np.vstack([rows, cols]), dtype=torch.long, device=device)
    vals = torch.tensor(values, dtype=torch.float32, device=device)
    return torch.sparse_coo_tensor(indices, vals, (n_users + n_items, n_users + n_items), device=device).coalesce()


def _sample_batch(
    positives: list[tuple[int, int]],
    user_positive_items: dict[int, set[int]],
    n_items: int,
    batch_size: int,
    rng: random.Random,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    batch = [positives[rng.randrange(len(positives))] for _ in range(batch_size)]
    users = []
    pos_items = []
    neg_items = []
    for user, pos_item in batch:
        seen = user_positive_items[user]
        neg = rng.randrange(n_items)
        while neg in seen:
            neg = rng.randrange(n_items)
        users.append(user)
        pos_items.append(pos_item)
        neg_items.append(neg)
    return (
        torch.tensor(users, dtype=torch.long, device=device),
        torch.tensor(pos_items, dtype=torch.long, device=device),
        torch.tensor(neg_items, dtype=torch.long, device=device),
    )


def _bpr_loss(
    user_emb: torch.Tensor,
    item_emb: torch.Tensor,
    users: torch.Tensor,
    pos_items: torch.Tensor,
    neg_items: torch.Tensor,
    reg: float,
    model: LightGCN,
) -> torch.Tensor:
    u = user_emb[users]
    pos = item_emb[pos_items]
    neg = item_emb[neg_items]
    pos_scores = (u * pos).sum(dim=1)
    neg_scores = (u * neg).sum(dim=1)
    loss = -torch.nn.functional.logsigmoid(pos_scores - neg_scores).mean()
    reg_loss = (
        model.user_embedding(users).pow(2).sum()
        + model.item_embedding(pos_items).pow(2).sum()
        + model.item_embedding(neg_items).pow(2).sum()
    ) / max(len(users), 1)
    return loss + reg * reg_loss


def build_lightgcn_recall(
    user_profile_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    train_path: str | Path | None = None,
    output_path: str | Path | None = None,
    top_n: int = 50,
    min_rating: float = 4.0,
    embedding_dim: int = 32,
    layers: int = 2,
    epochs: int = 5,
    batch_size: int = 4096,
    lr: float = 0.01,
    reg: float = 1e-4,
    seed: int = 2026,
    device_name: str = "auto",
    embedding_dir: str | Path | None = None,
) -> dict:
    del user_profile_path
    train_file = Path(train_path).resolve() if train_path else DEFAULT_TRAIN
    movie_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT
    embed_dir = Path(embedding_dir).resolve() if embedding_dir else DEFAULT_EMBED_DIR
    device = _device(device_name)

    torch.manual_seed(seed)
    np.random.seed(seed)
    rng = random.Random(seed)

    ratings = pd.read_csv(train_file, usecols=["userId", "movieId", "rating"])
    ratings["rating"] = pd.to_numeric(ratings["rating"], errors="coerce")
    ratings = ratings[ratings["rating"] >= min_rating].dropna(subset=["userId", "movieId"]).copy()
    if ratings.empty:
        raise ValueError("No positive interactions available for LightGCN training.")
    ratings["userId"] = ratings["userId"].astype(int)
    ratings["movieId"] = ratings["movieId"].astype(int)
    ratings = ratings.drop_duplicates(["userId", "movieId"])

    movies = pd.read_csv(movie_file, usecols=["movieId"])
    movie_ids = sorted(set(movies["movieId"].dropna().astype(int)) | set(ratings["movieId"]))
    user_ids = sorted(ratings["userId"].unique())
    user_to_idx = {user_id: idx for idx, user_id in enumerate(user_ids)}
    item_to_idx = {movie_id: idx for idx, movie_id in enumerate(movie_ids)}
    idx_to_user = np.array(user_ids, dtype=np.int64)
    idx_to_item = np.array(movie_ids, dtype=np.int64)

    user_idx = ratings["userId"].map(user_to_idx).to_numpy(dtype=np.int64)
    item_idx = ratings["movieId"].map(item_to_idx).to_numpy(dtype=np.int64)
    positives = list(zip(user_idx.tolist(), item_idx.tolist()))
    user_positive_items: dict[int, set[int]] = {}
    for user, item in positives:
        user_positive_items.setdefault(user, set()).add(item)

    norm_adj = _build_norm_adj(len(user_ids), len(movie_ids), user_idx, item_idx, device)
    model = LightGCN(len(user_ids), len(movie_ids), embedding_dim, layers).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    steps_per_epoch = max(1, int(np.ceil(len(positives) / batch_size)))
    logger.info(
        "Training LightGCN users=%s recipes=%s positives=%s dim=%s layers=%s epochs=%s device=%s",
        len(user_ids),
        len(movie_ids),
        len(positives),
        embedding_dim,
        layers,
        epochs,
        device,
    )

    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for _ in range(steps_per_epoch):
            users, pos_items, neg_items = _sample_batch(
                positives, user_positive_items, len(movie_ids), batch_size, rng, device
            )
            user_emb, item_emb = model.propagate(norm_adj)
            loss = _bpr_loss(user_emb, item_emb, users, pos_items, neg_items, reg, model)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        logger.info("LightGCN epoch %s/%s loss=%.5f", epoch, epochs, float(np.mean(losses)))

    model.eval()
    with torch.no_grad():
        user_emb, item_emb = model.propagate(norm_adj)
        user_emb = torch.nn.functional.normalize(user_emb, dim=1)
        item_emb = torch.nn.functional.normalize(item_emb, dim=1)
        scores = user_emb @ item_emb.T
        rows = []
        for user_index, user_id in enumerate(idx_to_user):
            seen = user_positive_items.get(user_index, set())
            if seen:
                scores[user_index, torch.tensor(list(seen), dtype=torch.long, device=device)] = -torch.inf
            k = min(top_n, len(movie_ids))
            values, indices = torch.topk(scores[user_index], k=k)
            rows.extend(
                {
                    "userId": int(user_id),
                    "movieId": int(idx_to_item[int(item_index)]),
                    "recall_type": "lightgcn",
                    "recall_score": float(score),
                }
                for score, item_index in zip(values.detach().cpu().tolist(), indices.detach().cpu().tolist())
                if np.isfinite(score)
            )

    output = pd.DataFrame(rows, columns=["userId", "movieId", "recall_type", "recall_score"])
    if output.empty:
        raise ValueError("LightGCN recall output is empty.")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)

    embed_dir.mkdir(parents=True, exist_ok=True)
    np.save(embed_dir / "lightgcn_user_ids.npy", idx_to_user)
    np.save(embed_dir / "lightgcn_recipe_ids.npy", idx_to_item)
    np.save(embed_dir / "lightgcn_user_embeddings.npy", user_emb.detach().cpu().numpy())
    np.save(embed_dir / "lightgcn_recipe_embeddings.npy", item_emb.detach().cpu().numpy())
    torch.save(
        {
            "state_dict": model.state_dict(),
            "n_users": len(user_ids),
            "n_items": len(movie_ids),
            "embedding_dim": embedding_dim,
            "layers": layers,
        },
        embed_dir / "lightgcn_model.pt",
    )

    summary = {
        "user_count": int(len(user_ids)),
        "recipe_count": int(len(movie_ids)),
        "positive_edges": int(len(positives)),
        "output_rows": int(len(output)),
        "top_n": int(top_n),
        "device": str(device),
        "output_path": str(output_file),
    }
    logger.info("LightGCN recall summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    try:
        build_lightgcn_recall(
            movie_profile_path=args.movie_profile,
            train_path=args.train,
            output_path=args.output,
            top_n=args.top_n,
            min_rating=args.min_rating,
            embedding_dim=args.embedding_dim,
            layers=args.layers,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            reg=args.reg,
            seed=args.seed,
            device_name=args.device,
            embedding_dir=args.embedding_dir,
        )
    except Exception as exc:
        logger.error("%s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
