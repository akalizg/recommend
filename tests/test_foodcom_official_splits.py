from __future__ import annotations

import pandas as pd


def test_import_foodcom_official_splits_outputs_canonical_and_processed_files(tmp_path):
    from scripts.import_foodcom_official_splits import import_official_splits

    split_dir = tmp_path / "splits"
    split_dir.mkdir()
    recipe_file = tmp_path / "RAW_recipes.csv"
    canonical_dir = tmp_path / "recipe-canonical"
    processed_dir = tmp_path / "processed"

    recipes = pd.DataFrame(
        [
            {
                "name": "bean bowl",
                "id": 101,
                "minutes": 20,
                "submitted": "2010-01-01",
                "tags": "['easy', 'dinner']",
                "nutrition": "[300.0, 10.0, 5.0, 20.0, 30.0, 5.0, 12.0]",
                "n_steps": 3,
                "description": "A bean bowl.",
                "ingredients": "['beans', 'rice']",
                "n_ingredients": 2,
            },
            {
                "name": "oat cup",
                "id": 102,
                "minutes": 10,
                "submitted": "2011-01-01",
                "tags": "['breakfast']",
                "nutrition": "[210.0, 4.0, 12.0, 3.0, 10.0, 2.0, 20.0]",
                "n_steps": 2,
                "description": "Oats.",
                "ingredients": "['oats', 'milk']",
                "n_ingredients": 2,
            },
            {
                "name": "unused recipe",
                "id": 999,
                "minutes": 5,
                "submitted": "2012-01-01",
                "tags": "['unused']",
                "nutrition": "[1, 1, 1, 1, 1, 1, 1]",
                "n_steps": 1,
                "description": "",
                "ingredients": "['water']",
                "n_ingredients": 1,
            },
        ]
    )
    recipes.to_csv(recipe_file, index=False)

    train = pd.DataFrame(
        [
            {"user_id": 1, "recipe_id": 101, "date": "2020-01-01", "rating": 5.0, "u": 0, "i": 0},
            {"user_id": 1, "recipe_id": 102, "date": "2020-01-02", "rating": 3.0, "u": 0, "i": 1},
        ]
    )
    valid = pd.DataFrame(
        [{"user_id": 1, "recipe_id": 101, "date": "2020-01-03", "rating": 4.0, "u": 0, "i": 0}]
    )
    test = pd.DataFrame(
        [{"user_id": 2, "recipe_id": 102, "date": "2020-01-04", "rating": 5.0, "u": 1, "i": 1}]
    )
    train.to_csv(split_dir / "interactions_train.csv", index=False)
    valid.to_csv(split_dir / "interactions_validation.csv", index=False)
    test.to_csv(split_dir / "interactions_test.csv", index=False)

    summary = import_official_splits(split_dir, recipe_file, canonical_dir, processed_dir)

    assert summary["train_rows"] == 2
    assert summary["valid_rows"] == 1
    assert summary["test_rows"] == 1
    assert summary["recipe_count"] == 2

    expected_processed = [
        "ratings_clean.csv",
        "train_ratings.csv",
        "valid_ratings.csv",
        "test_ratings.csv",
        "movies_clean.csv",
        "movie_tags.csv",
    ]
    expected_canonical = ["ratings.csv", "movies.csv", "tags.csv", "links.csv", "recipe_metadata.csv"]
    for file_name in expected_processed:
        assert (processed_dir / file_name).exists()
    for file_name in expected_canonical:
        assert (canonical_dir / file_name).exists()

    train_out = pd.read_csv(processed_dir / "train_ratings.csv")
    valid_out = pd.read_csv(processed_dir / "valid_ratings.csv")
    test_out = pd.read_csv(processed_dir / "test_ratings.csv")
    assert {"userId", "movieId", "rating", "rating_norm", "timestamp"}.issubset(train_out.columns)
    assert len(train_out) == 2
    assert len(valid_out) == 1
    assert len(test_out) == 1
    assert set(valid_out["movieId"]) == {101}
    assert set(test_out["movieId"]) == {102}
