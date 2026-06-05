"""
Matrix Factorization (ALS-style) for generating user and movie embeddings.

Implements Alternating Least Squares on the sparse rating matrix to learn
dense vector representations (embeddings) for users and items.

Math:
    R ≈ U @ V^T,  where R is rating matrix, U is user factors, V is item factors.
    minimize ‖R - U V^T‖² + λ(‖U‖² + ‖V‖²)
"""
import logging
import time
from typing import Tuple

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds

logger = logging.getLogger(__name__)


class MatrixFactorization:
    """
    Alternating Least Squares matrix factorization.

    Learns user_factors (num_users × dim) and item_factors (num_items × dim)
    by alternating between solving for U given fixed V, and V given fixed U.
    """

    def __init__(
        self,
        n_factors: int = 64,
        regularization: float = 0.1,
        iterations: int = 20,
        random_state: int = 42,
    ):
        self.n_factors = n_factors
        self.regularization = regularization
        self.iterations = iterations
        self.random_state = random_state

        self.user_factors: np.ndarray = None  # (n_users, n_factors)
        self.item_factors: np.ndarray = None  # (n_items, n_factors)
        self.global_bias: float = 0.0
        self.user_biases: np.ndarray = None
        self.item_biases: np.ndarray = None

    def fit(self, rating_matrix: csr_matrix) -> "MatrixFactorization":
        """
        Train the MF model on a sparse rating matrix.

        Args:
            rating_matrix: csr_matrix of shape (n_users, n_items) with ratings.
        """
        n_users, n_items = rating_matrix.shape
        rng = np.random.default_rng(self.random_state)

        logger.info(
            f"Training MF: {n_users} users × {n_items} items, "
            f"dim={self.n_factors}, λ={self.regularization}, "
            f"iterations={self.iterations}"
        )

        # Normalize ratings to [0, 1]
        R = rating_matrix.astype(np.float32).tocoo()
        ratings = R.data.copy()
        self.global_bias = float(np.mean(ratings))
        ratings_centered = ratings - self.global_bias

        # Initialize factors
        scale = 1.0 / np.sqrt(self.n_factors)
        self.user_factors = rng.normal(0, scale, (n_users, self.n_factors)).astype(np.float32)
        self.item_factors = rng.normal(0, scale, (n_items, self.n_factors)).astype(np.float32)
        self.user_biases = np.zeros(n_users, dtype=np.float32)
        self.item_biases = np.zeros(n_items, dtype=np.float32)

        # Build CSC for efficient column access during item-factor solve
        R_csc = R.tocsc()
        R_csr = R.tocsr()

        lam = self.regularization
        lam_eye = lam * np.eye(self.n_factors, dtype=np.float32)

        t0 = time.perf_counter()

        for iteration in range(self.iterations):
            # ----- Solve for user factors (fixed item factors) -----
            for u in range(n_users):
                item_indices = R_csr.indices[R_csr.indptr[u] : R_csr.indptr[u + 1]]
                if len(item_indices) == 0:
                    continue
                item_ratings = R_csr.data[R_csr.indptr[u] : R_csr.indptr[u + 1]]
                V_u = self.item_factors[item_indices]  # (n_rated, dim)
                bias_corrected = item_ratings - self.global_bias - self.item_biases[item_indices]
                # (V_u^T V_u + λI)^-1 V_u^T bias_corrected
                A = V_u.T @ V_u + lam_eye
                b = V_u.T @ bias_corrected
                try:
                    self.user_factors[u] = np.linalg.solve(A, b)
                except np.linalg.LinAlgError:
                    self.user_factors[u] = np.linalg.lstsq(A, b, rcond=None)[0]

            # Update user biases
            for u in range(n_users):
                item_indices = R_csr.indices[R_csr.indptr[u] : R_csr.indptr[u + 1]]
                if len(item_indices) == 0:
                    continue
                item_ratings = R_csr.data[R_csr.indptr[u] : R_csr.indptr[u + 1]]
                pred = (
                    self.global_bias
                    + self.user_factors[u] @ self.item_factors[item_indices].T
                    + self.item_biases[item_indices]
                )
                self.user_biases[u] = np.mean(item_ratings - pred + self.user_biases[u])

            # ----- Solve for item factors (fixed user factors) -----
            for i in range(n_items):
                user_indices = R_csc.indices[R_csc.indptr[i] : R_csc.indptr[i + 1]]
                if len(user_indices) == 0:
                    continue
                user_ratings = R_csc.data[R_csc.indptr[i] : R_csc.indptr[i + 1]]
                U_i = self.user_factors[user_indices]  # (n_rated, dim)
                bias_corrected = user_ratings - self.global_bias - self.user_biases[user_indices]
                A = U_i.T @ U_i + lam_eye
                b = U_i.T @ bias_corrected
                try:
                    self.item_factors[i] = np.linalg.solve(A, b)
                except np.linalg.LinAlgError:
                    self.item_factors[i] = np.linalg.lstsq(A, b, rcond=None)[0]

            # Update item biases
            for i in range(n_items):
                user_indices = R_csc.indices[R_csc.indptr[i] : R_csc.indptr[i + 1]]
                if len(user_indices) == 0:
                    continue
                user_ratings = R_csc.data[R_csc.indptr[i] : R_csc.indptr[i + 1]]
                pred = (
                    self.global_bias
                    + self.user_factors[user_indices] @ self.item_factors[i]
                    + self.user_biases[user_indices]
                )
                self.item_biases[i] = np.mean(user_ratings - pred + self.item_biases[i])

            # Compute loss for monitoring
            if (iteration + 1) % 5 == 0:
                loss = self._compute_loss(R_csr)
                elapsed = time.perf_counter() - t0
                logger.info(f"  Iter {iteration + 1}/{self.iterations}, loss={loss:.4f}, time={elapsed:.1f}s")

        elapsed = time.perf_counter() - t0
        logger.info(f"MF training complete in {elapsed:.1f}s")

        return self

    def _compute_loss(self, R: csr_matrix) -> float:
        pred = (
            self.global_bias
            + self.user_factors[R.nonzero()[0]] * self.item_factors[R.nonzero()[1]]
        ).sum(axis=1)
        pred += self.user_biases[R.nonzero()[0]] + self.item_biases[R.nonzero()[1]]
        mse = np.mean((R.data - pred) ** 2)
        reg = self.regularization * (
            np.sum(self.user_factors ** 2) + np.sum(self.item_factors ** 2)
        )
        return float(mse + reg)

    def get_user_embedding(self, user_idx: int) -> np.ndarray:
        """Get embedding vector for a user by internal index."""
        if self.user_factors is None:
            raise RuntimeError("Model not fitted yet.")
        return self.user_factors[user_idx].copy()

    def get_item_embedding(self, item_idx: int) -> np.ndarray:
        """Get embedding vector for an item by internal index."""
        if self.item_factors is None:
            raise RuntimeError("Model not fitted yet.")
        return self.item_factors[item_idx].copy()

    def get_all_user_embeddings(self) -> np.ndarray:
        return self.user_factors.copy()

    def get_all_item_embeddings(self) -> np.ndarray:
        return self.item_factors.copy()

    def predict(self, user_idx: int, item_idx: int) -> float:
        """Predict rating for a user-item pair."""
        pred = (
            self.global_bias
            + float(np.dot(self.user_factors[user_idx], self.item_factors[item_idx]))
            + float(self.user_biases[user_idx])
            + float(self.item_biases[item_idx])
        )
        return pred

    def save(self, path: str) -> None:
        np.savez_compressed(
            path,
            user_factors=self.user_factors,
            item_factors=self.item_factors,
            user_biases=self.user_biases,
            item_biases=self.item_biases,
            global_bias=np.array([self.global_bias]),
            n_factors=np.array([self.n_factors]),
        )
        logger.info(f"MF model saved to {path}")

    @classmethod
    def load(cls, path: str) -> "MatrixFactorization":
        data = np.load(path, allow_pickle=True)
        model = cls(n_factors=int(data["n_factors"][0]))
        model.user_factors = data["user_factors"]
        model.item_factors = data["item_factors"]
        model.user_biases = data["user_biases"]
        model.item_biases = data["item_biases"]
        model.global_bias = float(data["global_bias"][0])
        logger.info(f"MF model loaded from {path}")
        return model
