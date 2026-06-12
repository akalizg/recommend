from __future__ import annotations

import pandas as pd


def test_foodcom_conversion_outputs_canonical_files(tmp_path):
    from scripts.convert_foodcom_to_movielens_schema import convert_foodcom

    source = tmp_path / "food-com"
    output = tmp_path / "recipe-canonical"
    source.mkdir()
    recipes = pd.DataFrame(
        [
            {
                "name": "quick bean bowl",
                "id": 101,
                "minutes": 20,
                "contributor_id": 1,
                "submitted": "2010-01-01",
                "tags": "['easy', 'healthy', 'dinner']",
                "nutrition": "[300.0, 10.0, 5.0, 20.0, 30.0, 5.0, 12.0]",
                "n_steps": 3,
                "steps": "['mix', 'heat', 'serve']",
                "description": "A quick protein bowl.",
                "ingredients": "['beans', 'rice', 'salsa']",
                "n_ingredients": 3,
            },
            {
                "name": "oat breakfast",
                "id": 102,
                "minutes": 10,
                "contributor_id": 2,
                "submitted": "2011-01-01",
                "tags": "['breakfast', 'easy']",
                "nutrition": "[210.0, 4.0, 12.0, 3.0, 10.0, 2.0, 20.0]",
                "n_steps": 2,
                "steps": "['cook', 'serve']",
                "description": "Warm oats.",
                "ingredients": "['oats', 'milk']",
                "n_ingredients": 2,
            },
        ]
    )
    interactions = pd.DataFrame(
        [
            {"user_id": 1, "recipe_id": 101, "date": "2020-01-01", "rating": 5, "review": "great"},
            {"user_id": 1, "recipe_id": 102, "date": "2020-01-02", "rating": 4, "review": "good"},
            {"user_id": 2, "recipe_id": 101, "date": "2020-01-03", "rating": 5, "review": "nice"},
            {"user_id": 2, "recipe_id": 102, "date": "2020-01-04", "rating": 3, "review": "ok"},
            {"user_id": 3, "recipe_id": 101, "date": "2020-01-05", "rating": 0, "review": "review only"},
        ]
    )
    recipes.to_csv(source / "RAW_recipes.csv", index=False)
    interactions.to_csv(source / "RAW_interactions.csv", index=False)

    summary = convert_foodcom(
        source,
        output,
        min_recipe_interactions=1,
        min_user_interactions=2,
        max_recipes=10,
        max_users=10,
        max_interactions=10,
    )

    assert summary["ratings_rows"] == 4
    assert summary["recipe_rows"] == 2
    assert (output / "ratings.csv").exists()
    assert (output / "movies.csv").exists()
    assert (output / "tags.csv").exists()
    assert (output / "links.csv").exists()
    assert (output / "recipe_metadata.csv").exists()

    ratings = pd.read_csv(output / "ratings.csv")
    movies = pd.read_csv(output / "movies.csv")
    metadata = pd.read_csv(output / "recipe_metadata.csv")
    assert {"userId", "movieId", "rating", "timestamp"}.issubset(ratings.columns)
    assert {"movieId", "title", "genres"}.issubset(movies.columns)
    assert "quick bean bowl" in movies["title"].iloc[0] or "quick bean bowl" in movies["title"].iloc[1]
    assert {"recipe_id", "minutes", "ingredients", "calories"}.issubset(metadata.columns)
