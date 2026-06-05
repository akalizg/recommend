<template>
  <router-link
    :to="`/movie/${movie.movie_id || movie.movieId}`"
    class="block bg-gray-800 rounded-xl overflow-hidden shadow-lg hover:shadow-xl hover:ring-2 hover:ring-primary-500 transition-all duration-200 group"
  >
    <!-- Poster placeholder -->
    <div class="h-40 bg-gradient-to-br from-primary-700 to-purple-800 flex items-center justify-center relative">
      <span class="text-4xl">🎥</span>
      <div class="absolute top-2 right-2 bg-black/60 rounded-full px-2 py-0.5 text-xs font-bold text-yellow-400">
        {{ scoreDisplay }}
      </div>
    </div>

    <!-- Info -->
    <div class="p-3">
      <h3 class="font-semibold text-sm text-gray-100 truncate group-hover:text-primary-400 transition-colors">
        {{ movie.title || "Unknown Movie" }}
      </h3>
      <div class="flex items-center gap-2 mt-1 text-xs text-gray-400">
        <span v-if="movie.genres" class="truncate">{{ movie.genres.split("|")[0] }}</span>
        <span v-if="movie.year" class="text-gray-500">· {{ movie.year }}</span>
      </div>
      <div class="flex items-center gap-1 mt-1 text-xs text-gray-500">
        <span class="text-yellow-500">★</span>
        <span>{{ avgRating }}</span>
        <span class="text-gray-600">({{ ratingCount }})</span>
      </div>
    </div>
  </router-link>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  movie: { type: Object, required: true },
});

const scoreDisplay = computed(() => {
  const s = props.movie.score;
  if (s === undefined || s === null) return "N/A";
  if (s > 1) return s.toFixed(1);
  return (s * 10).toFixed(1);
});

const avgRating = computed(() => {
  const r = props.movie.avg_rating || props.movie.avgRating;
  return r ? Number(r).toFixed(1) : "N/A";
});

const ratingCount = computed(() => {
  const c = props.movie.rating_count || props.movie.ratingCount;
  return c ?? "N/A";
});
</script>
