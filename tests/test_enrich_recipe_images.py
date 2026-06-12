from __future__ import annotations

import pandas as pd


def test_enrich_recipe_images_adds_image_columns(tmp_path):
    from scripts.enrich_recipe_images import enrich_recipe_images

    enhanced = pd.DataFrame(
        [
            {
                "id": 10,
                "has_image": 1,
                "image_url": "https://example.com/recipe.jpg",
                "recipe_yield_raw": "4 serving(s)",
                "recipe_yield_min": 4,
                "recipe_yield_max": 4,
                "serves_best_guess": 4,
                "yield_unit_raw": "serving(s)",
                "yield_type": "servings",
                "ready_in_display": "25mins",
                "author_name": "chef",
                "photo_count": 2,
                "rating_value": 4.5,
                "review_count": 12,
            }
        ]
    )
    profile = pd.DataFrame([{"movieId": 10, "title": "test recipe", "genres": "easy"}])
    recs = pd.DataFrame([{"userId": 1, "movieId": 10, "movie_title": "test recipe"}])
    enhanced_path = tmp_path / "enhanced.csv"
    profile_path = tmp_path / "profile.csv"
    recs_path = tmp_path / "recs.csv"
    metadata_path = tmp_path / "metadata.csv"
    enhanced.to_csv(enhanced_path, index=False)
    profile.to_csv(profile_path, index=False)
    recs.to_csv(recs_path, index=False)

    summary = enrich_recipe_images(enhanced_path, profile_path, recs_path, metadata_path)

    out_profile = pd.read_csv(profile_path)
    out_recs = pd.read_csv(recs_path)
    assert summary["profile_rows_with_image"] == 1
    assert summary["recommendation_rows_with_image"] == 1
    assert out_profile.loc[0, "image_url"] == "https://example.com/recipe.jpg"
    assert out_recs.loc[0, "image_url"] == "https://example.com/recipe.jpg"
    assert out_recs.loc[0, "ready_in_display"] == "25mins"
