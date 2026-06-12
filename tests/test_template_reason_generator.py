from __future__ import annotations

import importlib


def test_template_reason_generator_importable():
    module = importlib.import_module("reason.template_reason_generator")
    assert hasattr(module, "build_template_reason")


def test_template_reason_is_non_empty():
    from reason.template_reason_generator import build_template_reason

    reason = build_template_reason(
        {
            "favorite_genres": "Action|Comedy",
            "movie_genres": "Action|Adventure",
            "movie_avg_rating": 4.2,
            "genre_match_score": 0.5,
        }
    )
    assert reason
    assert len(reason) <= 80
