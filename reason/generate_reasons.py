from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reason.llm_reason_generator import DEFAULT_LOCAL_LLM_PATH, QwenReasonGenerator
from reason.template_reason_generator import build_template_reason


DEFAULT_INPUT = PROJECT_ROOT / "data" / "rank" / "ranked_top10_mmr.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_USER_PROFILE = PROJECT_ROOT / "data" / "features" / "user_profile.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "final" / "recommendations_with_reasons.csv"

OUTPUT_COLUMNS = [
    "userId",
    "movieId",
    "rank_position",
    "rank_score",
    "mmr_score",
    "movie_title",
    "movie_genres",
    "favorite_genres",
    "template_reason",
    "llm_reason",
    "final_reason",
    "reason_source",
    "reason_evidence",
    "image_url",
    "recipe_yield_raw",
    "serves_best_guess",
    "ready_in_display",
    "author_name",
    "photo_count",
    "rating_value",
    "review_count",
]

logger = logging.getLogger(__name__)


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def generate_reasons(
    input_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    user_profile_path: str | Path | None = None,
    output_path: str | Path | None = None,
    use_llm: bool = True,
    model_path: str | Path | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    input_file = Path(input_path).resolve() if input_path else DEFAULT_INPUT
    movie_profile_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    user_profile_file = Path(user_profile_path).resolve() if user_profile_path else DEFAULT_USER_PROFILE
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT
    qwen_path = str(model_path or DEFAULT_LOCAL_LLM_PATH)

    if not input_file.exists():
        raise FileNotFoundError(f"Recommendation input not found: {input_file}")
    if not movie_profile_file.exists():
        raise FileNotFoundError(f"Item profile not found: {movie_profile_file}")

    recs = pd.read_csv(input_file)
    if limit is not None and limit > 0:
        recs = recs.head(limit).copy()
    movie_profile = pd.read_csv(
        movie_profile_file,
        usecols=lambda col: col
        in {
            "movieId",
            "title",
            "genres",
            "movie_avg_rating",
            "image_url",
            "recipe_yield_raw",
            "serves_best_guess",
            "ready_in_display",
            "author_name",
            "photo_count",
            "rating_value",
            "review_count",
        },
    )
    recs = recs.merge(movie_profile, on="movieId", how="left", suffixes=("", "_profile"))

    if "movie_avg_rating_profile" in recs.columns:
        recs["movie_avg_rating"] = recs.get("movie_avg_rating").fillna(recs["movie_avg_rating_profile"])

    if user_profile_file.exists():
        user_profile = pd.read_csv(user_profile_file, usecols=lambda col: col in {"userId", "favorite_genres"})
        recs = recs.merge(user_profile, on="userId", how="left")
    else:
        recs["favorite_genres"] = ""

    recs["movie_title"] = recs.get("title", "").fillna("")
    recs["movie_genres"] = recs.get("genres", "").fillna("")
    recs["favorite_genres"] = recs.get("favorite_genres", "").fillna("")

    generator = QwenReasonGenerator(qwen_path)
    rows: list[dict[str, Any]] = []
    for _, row in recs.iterrows():
        item = row.to_dict()
        template_reason = build_template_reason(item)
        item["template_reason"] = template_reason
        result = generator.generate(item, use_llm=use_llm)
        evidence = {
            "item_avg_rating": item.get("movie_avg_rating"),
            "genre_match_score": item.get("genre_match_score"),
            "rank_position": item.get("rank_position"),
        }
        item.update(
            {
                "template_reason": template_reason,
                "llm_reason": result["llm_reason"],
                "final_reason": result["final_reason"],
                "reason_source": result["reason_source"],
                "reason_evidence": json.dumps(evidence, ensure_ascii=False),
            }
        )
        rows.append(item)

    output = pd.DataFrame(rows)
    for col in OUTPUT_COLUMNS:
        if col not in output.columns:
            output[col] = ""
    output = output[OUTPUT_COLUMNS].copy()
    output["final_reason"] = output["final_reason"].fillna(output["template_reason"]).astype(str)
    output["reason_source"] = output["reason_source"].where(output["reason_source"].isin(["qwen", "template"]), "template")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False, encoding="utf-8-sig")

    source_distribution = output["reason_source"].value_counts().to_dict()
    samples = output.head(10)[["userId", "movieId", "movie_title", "final_reason", "reason_source"]].to_dict(orient="records")
    qwen_status = generator.status()
    summary = {
        "use_llm": bool(use_llm),
        "use_qwen": bool(use_llm),
        "model_path": qwen_path,
        "model_path_exists": Path(qwen_path).exists(),
        "qwen_loaded": bool(qwen_status["model_loaded"]),
        "qwen_device": qwen_status["device"],
        "qwen_load_error": str(qwen_status["load_error"]),
        "fallback_to_template": source_distribution.get("template", 0) > 0,
        "qwen_status": qwen_status,
        "output_path": str(output_file),
        "output_rows": int(len(output)),
        "reason_source_distribution": {str(k): int(v) for k, v in source_distribution.items()},
        "samples": samples,
    }
    logger.info("Reason generation summary: %s", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate recommendation reasons for MMR Top10 results.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input ranked Top10 CSV.")
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE), help="Movie profile CSV.")
    parser.add_argument("--user-profile", default=str(DEFAULT_USER_PROFILE), help="User profile CSV.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output recommendations_with_reasons.csv.")
    parser.add_argument("--use-llm", default="true", choices=["true", "false"], help="Use local Qwen when true.")
    parser.add_argument("--model-path", default=DEFAULT_LOCAL_LLM_PATH, help="Local Qwen model directory.")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit for smoke runs.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args()
    summary = generate_reasons(
        input_path=args.input,
        movie_profile_path=args.movie_profile,
        user_profile_path=args.user_profile,
        output_path=args.output,
        use_llm=parse_bool(args.use_llm),
        model_path=args.model_path,
        limit=args.limit,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
