from __future__ import annotations

import pandas as pd


def test_generate_reasons_use_llm_false(tmp_path):
    from reason.generate_reasons import generate_reasons
    from reason.llm_reason_generator import DEFAULT_LOCAL_LLM_PATH

    recs = pd.DataFrame(
        [
            {
                "userId": 1,
                "movieId": 10,
                "rank_position": 1,
                "rank_score": 0.9,
                "mmr_score": 0.8,
                "genre_match_score": 0.5,
                "movie_avg_rating": 4.0,
            }
        ]
    )
    movies = pd.DataFrame([{"movieId": 10, "title": "GoldenEye (1995)", "genres": "Action|Adventure", "movie_avg_rating": 4.0}])
    users = pd.DataFrame([{"userId": 1, "favorite_genres": "Action|Thriller"}])
    rec_path = tmp_path / "recs.csv"
    movie_path = tmp_path / "movies.csv"
    user_path = tmp_path / "users.csv"
    output_path = tmp_path / "out.csv"
    recs.to_csv(rec_path, index=False)
    movies.to_csv(movie_path, index=False)
    users.to_csv(user_path, index=False)

    summary = generate_reasons(
        input_path=rec_path,
        movie_profile_path=movie_path,
        user_profile_path=user_path,
        output_path=output_path,
        use_llm=False,
    )

    assert summary["output_rows"] == 1
    assert summary["model_path"] == DEFAULT_LOCAL_LLM_PATH
    assert summary["use_qwen"] is False
    df = pd.read_csv(output_path)
    expected = {
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
    }
    assert expected.issubset(df.columns)
    assert df.loc[0, "final_reason"]
    assert df.loc[0, "reason_source"] == "template"
    assert set(df["reason_source"]).issubset({"qwen", "template"})


def test_generate_reasons_missing_model_path_falls_back(tmp_path):
    from reason.generate_reasons import generate_reasons

    recs = pd.DataFrame(
        [
            {
                "userId": 1,
                "movieId": 10,
                "rank_position": 1,
                "rank_score": 0.9,
                "mmr_score": 0.8,
                "genre_match_score": 0.5,
                "movie_avg_rating": 4.0,
            }
        ]
    )
    movies = pd.DataFrame([{"movieId": 10, "title": "GoldenEye (1995)", "genres": "Action|Adventure", "movie_avg_rating": 4.0}])
    rec_path = tmp_path / "recs.csv"
    movie_path = tmp_path / "movies.csv"
    output_path = tmp_path / "out.csv"
    recs.to_csv(rec_path, index=False)
    movies.to_csv(movie_path, index=False)

    summary = generate_reasons(
        input_path=rec_path,
        movie_profile_path=movie_path,
        user_profile_path=tmp_path / "missing-users.csv",
        output_path=output_path,
        use_llm=True,
        model_path=tmp_path / "missing-qwen",
    )

    df = pd.read_csv(output_path)
    assert summary["model_path_exists"] is False
    assert summary["qwen_loaded"] is False
    assert summary["fallback_to_template"] is True
    assert df.loc[0, "final_reason"]
    assert df.loc[0, "reason_source"] == "template"
