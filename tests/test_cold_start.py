from __future__ import annotations

from recommendation.cold_start import cold_start_recommend


def test_cold_start_prefers_matching_recipe(tmp_path):
    profile = tmp_path / "movie_profile.csv"
    profile.write_text(
        "movieId,title,clean_title,genres,tag_text,movie_avg_rating,movie_rating_count,"
        "movie_popularity,has_image,image_url,ready_in_display,recipe_yield_raw,author_name,"
        "review_count,rating_value\n"
        "1,Quick Chicken Dinner,Quick Chicken Dinner,quick|dinner|chicken,"
        "ingredient:chicken|quick|dinner,4.8,100,30,1,https://example.com/1.jpg,30mins,4 servings,A,80,4.9\n"
        "2,Slow Apple Dessert,Slow Apple Dessert,dessert|apple,"
        "ingredient:apple|dessert,4.9,120,35,1,https://example.com/2.jpg,120mins,8 servings,B,90,4.9\n",
        encoding="utf-8",
    )
    metadata = tmp_path / "recipe_metadata.csv"
    metadata.write_text(
        "recipe_id,minutes,n_steps,n_ingredients,calories,total_fat_pct,sugar_pct,sodium_pct,"
        "protein_pct,saturated_fat_pct,carbohydrates_pct\n"
        "1,30,5,6,350,10,5,20,70,5,10\n"
        "2,120,8,5,700,20,80,30,5,15,70\n",
        encoding="utf-8",
    )

    result = cold_start_recommend(
        preferred_tags=["quick", "dinner"],
        ingredients=["chicken"],
        dietary_goals=["high protein"],
        max_minutes=45,
        require_image=True,
        limit=2,
        profile_path=profile,
        metadata_path=metadata,
    )

    assert result["total"] == 2
    assert result["recommendations"][0]["movie_id"] == 1
    assert result["preference_profile"]["ingredients"] == ["chicken"]
