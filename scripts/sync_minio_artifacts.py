from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib3.exceptions import HTTPError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from storage.minio_artifacts import DEFAULT_ARTIFACT_PATHS, MinioArtifactStore


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Sync offline recommendation artifacts with MinIO.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upload = subparsers.add_parser("upload", help="Upload local offline artifacts to MinIO.")
    upload.add_argument("--prefix", default=settings.minio_artifact_prefix)
    upload.add_argument("--paths", nargs="*", default=DEFAULT_ARTIFACT_PATHS)

    download = subparsers.add_parser("download", help="Download offline artifacts from MinIO.")
    download.add_argument("--prefix", default=settings.minio_artifact_prefix)
    download.add_argument("--target-root", default=str(PROJECT_ROOT))
    download.add_argument("--no-overwrite", action="store_true")

    list_cmd = subparsers.add_parser("list", help="List artifacts under the MinIO prefix.")
    list_cmd.add_argument("--prefix", default=settings.minio_artifact_prefix)
    return parser.parse_args()


def main() -> None:
    settings = get_settings()
    if not settings.minio_enabled:
        raise RuntimeError("MINIO_ENABLED is false. Enable MinIO before syncing artifacts.")

    args = parse_args()
    try:
        store = MinioArtifactStore(settings)
        if args.command == "upload":
            result = store.upload_paths(paths=args.paths, prefix=args.prefix, root=PROJECT_ROOT)
        elif args.command == "download":
            result = store.download_prefix(
                prefix=args.prefix,
                target_root=Path(args.target_root),
                overwrite=not args.no_overwrite,
            )
        elif args.command == "list":
            result = {"bucket": settings.minio_bucket, "prefix": args.prefix, "objects": store.list_prefix(args.prefix)}
        else:  # pragma: no cover
            raise ValueError(args.command)
    except HTTPError as exc:
        endpoint = settings.minio_endpoint
        print(
            f"MinIO 连接失败：{endpoint}。请确认 MinIO 已启动、端口可访问，并且 .env 中的账号密码正确。\n"
            f"原始错误：{exc}",
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as exc:
        print(f"MinIO 同步失败：{exc}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
