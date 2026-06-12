<template>
  <router-link
    :to="`/recipe/${movie.movie_id || movie.movieId}`"
    class="group block overflow-hidden rounded-lg border border-slate-700/70 bg-slate-900 shadow-lg shadow-black/20 transition duration-200 hover:-translate-y-1 hover:border-emerald-400/70 hover:shadow-emerald-950/40"
  >
    <div class="relative aspect-[4/5] overflow-hidden bg-slate-800">
      <img
        :src="coverImage"
        :alt="title"
        class="h-full w-full object-cover transition duration-300 group-hover:scale-105"
        loading="lazy"
      />
      <div class="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-slate-950/90 to-transparent"></div>

      <slot />

      <div class="absolute right-2 top-2 rounded-md bg-black/75 px-2 py-1 text-xs font-bold text-amber-200 backdrop-blur">
        {{ ratingBadge }}
      </div>
    </div>

    <div class="space-y-2 p-3">
      <h3 class="line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-slate-100 transition-colors group-hover:text-emerald-300">
        {{ title }}
      </h3>

      <div class="flex flex-wrap gap-1">
        <span
          v-for="tag in visibleTags"
          :key="tag"
          class="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] text-slate-300"
        >
          {{ tag }}
        </span>
      </div>

      <div class="flex items-center justify-between gap-2 text-xs text-slate-400">
        <span>{{ metaDisplay }}</span>
        <span class="font-medium text-amber-300">{{ reviewDisplay }}</span>
      </div>
    </div>
  </router-link>
</template>

<script setup>
import { computed } from "vue";
import { recipeImage, recipeTags, recipeTitle } from "../utils/recipeCover";

const props = defineProps({
  movie: { type: Object, required: true },
});

const title = computed(() => recipeTitle(props.movie));
const coverImage = computed(() => recipeImage(props.movie));

function numericValue(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "" && !Number.isNaN(Number(value))) {
      return Number(value);
    }
  }
  return null;
}

const ratingValue = computed(() =>
  numericValue(props.movie.rating_value, props.movie.avg_rating, props.movie.avgRating, props.movie.movie_avg_rating)
);

const reviewCount = computed(() =>
  numericValue(props.movie.review_count, props.movie.rating_count, props.movie.movie_rating_count)
);

const ratingBadge = computed(() => {
  if (ratingValue.value !== null && ratingValue.value > 0) return ratingValue.value.toFixed(1);
  return "Recipe";
});

const reviewDisplay = computed(() => {
  if (reviewCount.value !== null && reviewCount.value > 0) {
    const count = Math.trunc(reviewCount.value).toLocaleString();
    return `${count} ${reviewCount.value === 1 ? "review" : "reviews"}`;
  }
  if (ratingValue.value !== null && ratingValue.value > 0) return `${ratingValue.value.toFixed(1)} stars`;
  return "Food.com";
});

const metaDisplay = computed(() => {
  if (props.movie.ready_in_display) return props.movie.ready_in_display;
  if (props.movie.minutes) return `${props.movie.minutes} min`;
  if (props.movie.year) return String(Math.trunc(props.movie.year));
  return "Food.com";
});

const visibleTags = computed(() => recipeTags(props.movie).slice(0, 2));
</script>
