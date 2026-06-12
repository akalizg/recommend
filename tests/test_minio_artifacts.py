from __future__ import annotations

from pathlib import Path

import pytest

from storage.minio_artifacts import (
    iter_artifact_files,
    make_object_name,
    normalize_minio_endpoint,
    safe_download_target,
)


def test_normalize_minio_endpoint_accepts_plain_and_url() -> None:
    assert normalize_minio_endpoint("localhost:9000", False) == ("localhost:9000", False)
    assert normalize_minio_endpoint("http://192.168.88.1:9000", True) == ("192.168.88.1:9000", False)
    assert normalize_minio_endpoint("https://minio.example.com", False) == ("minio.example.com", True)


def test_iter_artifact_files_keeps_project_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "data" / "features").mkdir(parents=True)
    (tmp_path / "data" / "features" / "user_profile.csv").write_text("u,v\n1,2\n", encoding="utf-8")
    (tmp_path / "missing").mkdir()

    files = iter_artifact_files(["data/features", "not-exist"], root=tmp_path)

    assert len(files) == 1
    assert files[0].relative_path == "data/features/user_profile.csv"
    assert files[0].size_bytes > 0


def test_object_name_uses_prefix() -> None:
    assert make_object_name("offline/latest/", "data\\final\\recommendations.csv") == (
        "offline/latest/data/final/recommendations.csv"
    )


def test_safe_download_target_rejects_path_traversal(tmp_path: Path) -> None:
    target = safe_download_target(tmp_path, "offline/latest/data/final/a.csv", "offline/latest")
    assert target == tmp_path / "data" / "final" / "a.csv"

    with pytest.raises(ValueError):
        safe_download_target(tmp_path, "offline/latest/../../bad.txt", "offline/latest")
