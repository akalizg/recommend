const COVER_RULES = [
  { key: "breakfast", words: ["breakfast", "brunch", "morning", "oat", "pancake"] },
  { key: "dessert", words: ["dessert", "cake", "cookie", "sweet", "chocolate", "pie"] },
  { key: "vegetarian", words: ["vegetarian", "vegan", "vegetables", "healthy", "salad"] },
  { key: "quick", words: ["15-minutes", "30-minutes", "quick", "easy", "time-to-make"] },
  { key: "main-dish", words: ["main-dish", "dinner", "lunch", "meat", "pasta", "chicken"] },
  { key: "global", words: ["cuisine", "mexican", "italian", "asian", "indian", "thai"] },
];

export function recipeTitle(item = {}) {
  return item.title || item.movie_title || item.name || "Untitled recipe";
}

export function recipeTags(item = {}) {
  const raw = item.genres || item.movie_genres || item.tags || "";
  return String(raw)
    .split("|")
    .map((tag) => tag.trim())
    .filter((tag) => tag && tag !== "(no genres listed)")
    .slice(0, 4);
}

export function recipeImage(item = {}) {
  if (item.image_url) return item.image_url;
  if (item.poster_url) return item.poster_url;
  if (item.backdrop_url) return item.backdrop_url;

  const haystack = `${recipeTitle(item)} ${recipeTags(item).join(" ")}`.toLowerCase();
  const matched = COVER_RULES.find((rule) => rule.words.some((word) => haystack.includes(word)));
  return `/recipe-covers/${matched?.key || "default"}.png`;
}
