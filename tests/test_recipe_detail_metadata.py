from __future__ import annotations

import json

import pandas as pd


def test_build_recipe_detail_metadata_outputs_json_fields(tmp_path):
    from scripts.build_recipe_detail_metadata import build_recipe_detail_metadata

    enhanced = pd.DataFrame(
        [
            {
                "id": 10,
                "name": "Test Recipe",
                "minutes": 25,
                "submitted": "2020-01-01",
                "tags": "['easy', 'dinner']",
                "nutrition": "[100, 1, 2, 3, 4, 5, 6]",
                "n_steps": 2,
                "steps": "['mix', 'serve']",
                "description": "A test recipe.",
                "ingredients": "['rice', 'salt']",
                "n_ingredients": 2,
                "quantities": "['1 cup', '1 tsp']",
                "serves": "2",
                "has_image": 1,
                "image_url": "https://example.com/recipe.jpg",
                "recipe_yield_raw": "2 serving(s)",
                "recipe_yield_min": 2,
                "recipe_yield_max": 2,
                "serves_best_guess": 2,
                "yield_unit_raw": "serving(s)",
                "yield_type": "servings",
                "ready_in_display": "25mins",
                "author_name": "chef",
                "photo_count": 1,
                "rating_value": 4.5,
                "review_count": 8,
            }
        ]
    )
    source = tmp_path / "enhanced.csv"
    output = tmp_path / "detail.csv"
    enhanced.to_csv(source, index=False)

    summary = build_recipe_detail_metadata(source, output)

    detail = pd.read_csv(output)
    assert summary["output_rows"] == 1
    assert json.loads(detail.loc[0, "ingredients_json"]) == ["rice", "salt"]
    assert json.loads(detail.loc[0, "steps_json"]) == ["mix", "serve"]
    assert json.loads(detail.loc[0, "nutrition_json"])["calories"] == 100
    assert detail.loc[0, "source_url"].endswith("test-recipe-10")
