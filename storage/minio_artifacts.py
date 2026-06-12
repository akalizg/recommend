from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from app.config import PROJECT_ROOT, Settings, get_settings


DEFAULT_ARTIFACT_PATHS = [
    "data/features",
    "data/factors",
    "data/faiss",
    "data/recall",
    "data/rank",
    "data/final",
    "data/eval",
    "data/processed",
    "data/recipe-canonical",
    "data/recommendations.db",
    "models/faiss_hnsw.index",
    "models/faiss_hnsw_spark.index",
    "models/faiss_hnsw_spark_ids.npy",
    "models/xgb_rank_model.json",
    "models/enhanced_ranker",
]


@dataclass(frozen=True)
class ArtifactFile:
    source_path: Path
    relative_path: str
    size_bytes: int


def normalize_prefix(prefix: str) -> str:
    return prefix.strip().strip("/")


def normalize_minio_endpoint(endpoint: str, secure: bool) -> tuple[str, bool]:
    value = endpoint.strip()
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        host = parsed.netloc or parsed.path
        return host.rstrip("/"), parsed.scheme == "https"
    return value.rstrip("/"), secure


def make_object_name(prefix: str, relative_path: str) -> str:
    clean_prefix = normalize_prefix(prefix)
    clean_relative = relative_path.replace("\\", "/").lstrip("/")
    return f"{clean_prefix}/{clean_relative}" if clean_prefix else clean_relative


def iter_artifact_files(paths: Iterable[str | Path], root: Path = PROJECT_ROOT) -> list[ArtifactFile]:
    root = root.resolve()
    files: list[ArtifactFile] = []
    for raw_path in paths:
        path = Path(raw_path)
        source = path if path.is_absolute() else root / path
        if not source.exists():
            continue
        candidates = sorted(source.rglob("*")) if source.is_dir() else [source]
        for candidate in candidates:
            if not candidate.is_file():
                continue
            resolved = candidate.resolve()
            relative = resolved.relative_to(root).as_posix()
            files.append(ArtifactFile(resolved, relative, resolved.stat().st_size))
    return files


def safe_download_target(root: Path, object_name: str, prefix: str) -> Path:
    root = root.resolve()
    clean_prefix = normalize_prefix(prefix)
    normalized_object = object_name.replace("\\", "/").lstrip("/")
    if clean_prefix:
        expected = f"{clean_prefix}/"
        if not normalized_object.startswith(expected):
            raise ValueError(f"Object {object_name!r} is outside prefix {prefix!r}")
        normalized_object = normalized_object[len(expected) :]
    target = (root / normalized_object).resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"Unsafe MinIO object path: {object_name!r}")
    return target


class MinioArtifactStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        endpoint, secure = normalize_minio_endpoint(self.settings.minio_endpoint, self.settings.minio_secure)
        self.endpoint = endpoint
        self.secure = secure
        try:
            from minio import Minio
        except Exception as exc:  # pragma: no cover - exercised only when dependency is missing.
            raise RuntimeError("MinIO client is not installed. Run: pip install -r requirements.txt") from exc
        from urllib3 import PoolManager, Timeout

        self.client = Minio(
            endpoint,
            access_key=self.settings.minio_access_key,
            secret_key=self.settings.minio_secret_key,
            secure=secure,
            http_client=PoolManager(
                timeout=Timeout(
                    connect=self.settings.minio_connect_timeout_seconds,
                    read=self.settings.minio_read_timeout_seconds,
                ),
                retries=False,
            ),
        )

    @property
    def bucket(self) -> str:
        return self.settings.minio_bucket

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_paths(
        self,
        paths: Iterable[str | Path] = DEFAULT_ARTIFACT_PATHS,
        prefix: str | None = None,
        root: Path = PROJECT_ROOT,
    ) -> dict:
        artifact_prefix = normalize_prefix(prefix or self.settings.minio_artifact_prefix)
        files = iter_artifact_files(paths, root=root)
        self.ensure_bucket()

        uploaded: list[dict] = []
        for item in files:
            object_name = make_object_name(artifact_prefix, item.relative_path)
            self.client.fput_object(self.bucket, object_name, str(item.source_path))
            uploaded.append(
                {
                    "object_name": object_name,
                    "relative_path": item.relative_path,
                    "size_bytes": item.size_bytes,
                }
            )

        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "bucket": self.bucket,
            "prefix": artifact_prefix,
            "root": str(root.resolve()),
            "file_count": len(uploaded),
            "total_size_bytes": sum(item["size_bytes"] for item in uploaded),
            "files": uploaded,
        }
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        self.client.put_object(
            self.bucket,
            make_object_name(artifact_prefix, "_manifest.json"),
            BytesIO(manifest_bytes),
            length=len(manifest_bytes),
            content_type="application/json",
        )
        return manifest

    def download_prefix(
        self,
        prefix: str | None = None,
        target_root: Path = PROJECT_ROOT,
        overwrite: bool = True,
    ) -> dict:
        artifact_prefix = normalize_prefix(prefix or self.settings.minio_artifact_prefix)
        target_root = target_root.resolve()
        objects = list(self.client.list_objects(self.bucket, prefix=artifact_prefix, recursive=True))
        downloaded: list[dict] = []
        skipped: list[str] = []

        for obj in objects:
            target = safe_download_target(target_root, obj.object_name, artifact_prefix)
            if target.exists() and not overwrite:
                skipped.append(obj.object_name)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            self.client.fget_object(self.bucket, obj.object_name, str(target))
            downloaded.append(
                {
                    "object_name": obj.object_name,
                    "relative_path": target.relative_to(target_root).as_posix(),
                    "size_bytes": getattr(obj, "size", None),
                }
            )

        return {
            "bucket": self.bucket,
            "prefix": artifact_prefix,
            "target_root": str(target_root),
            "downloaded_count": len(downloaded),
            "skipped_count": len(skipped),
            "downloaded": downloaded,
            "skipped": skipped,
        }

    def list_prefix(self, prefix: str | None = None) -> list[dict]:
        self.ensure_bucket()
        artifact_prefix = normalize_prefix(prefix or self.settings.minio_artifact_prefix)
        return [
            {
                "object_name": obj.object_name,
                "size_bytes": getattr(obj, "size", None),
                "last_modified": str(getattr(obj, "last_modified", "")),
            }
            for obj in self.client.list_objects(self.bucket, prefix=artifact_prefix, recursive=True)
        ]
