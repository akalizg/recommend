<template>
  <router-link
    :to="`/movie/${movie.movie_id || movie.movieId}`"
    class="group block overflow-hidden rounded-lg border border-slate-700/70 bg-slate-900 shadow-lg shadow-black/20 transition duration-200 hover:-translate-y-1 hover:border-cyan-400/70 hover:shadow-cyan-950/40"
  >
    <div class="relative aspect-[2/3] overflow-hidden bg-slate-800">
      <img
        v-if="hasPoster"
        :src="movie.poster_url"
        :alt="movie.title || 'Movie poster'"
        class="h-full w-full object-cover transition duration-300 group-hover:scale-105"
        loading="lazy"
      />
      <div v-else class="flex h-full w-full flex-col items-center justify-center bg-[radial-gradient(circle_at_30%_20%,rgba(34,211,238,0.22),transparent_28%),linear-gradient(145deg,#0f172a,#1f2937_55%,#111827)] px-4 text-center">
        <div class="mb-3 h-14 w-10 rounded border-2 border-slate-500/70 shadow-inner"></div>
        <p class="line-clamp-3 text-sm font-semibold text-slate-200">{{ movie.title || "Unknown Movie" }}</p>
      </div>

      <slot />

      <div class="absolute right-2 top-2 rounded-md bg-black/75 px-2 py-1 text-xs font-bold text-amber-300 backdrop-blur">
        {{ scoreDisplay }}
      </div>

      <div
        v-if="movie.overview"
        class="absolute inset-x-0 bottom-0 max-h-full translate-y-full bg-slate-950/92 p-3 text-xs leading-relaxed text-slate-200 backdrop-blur-sm transition duration-300 group-hover:translate-y-0"
      >
        <p class="line-clamp-6">{{ movie.overview }}</p>
      </div>
    </div>

    <div class="space-y-2 p-3">
      <h3 class="line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-slate-100 transition-colors group-hover:text-cyan-300">
        {{ movie.title || "Unknown Movie" }}
      </h3>

      <div class="flex flex-wrap gap-1">
        <span
          v-for="genre in visibleGenres"
          :key="genre"
          class="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] text-slate-300"
        >
          {{ genre }}
        </span>
      </div>

      <div class="flex items-center justify-between gap-2 text-xs text-slate-400">
        <span>{{ releaseDate }}</span>
        <span class="font-medium text-amber-300">{{ ratingDisplay }}</span>
      </div>
    </div>
  </router-link>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  movie: { type: Object, required: true },
});

const hasPoster = computed(() => Boolean(props.movie.poster_url));

const scoreDisplay = computed(() => {
  const s = props.movie.score;
  if (s !== undefined && s !== null) {
    if (s > 1) return Number(s).toFixed(1);
    return (Number(s) * 10).toFixed(1);
  }

  const tmdb = props.movie.vote_average;
  if (tmdb !== undefined && tmdb !== null) return Number(tmdb).toFixed(1);

  const rating = props.movie.avg_rating ?? props.movie.avgRating;
  if (rating !== undefined && rating !== null) return Number(rating).toFixed(1);

  return "N/A";
});

const ratingDisplay = computed(() => {
  const tmdb = props.movie.vote_average;
  if (tmdb !== undefined && tmdb !== null) return `TMDB ${Number(tmdb).toFixed(1)}`;

  const rating = props.movie.avg_rating ?? props.movie.avgRating;
  if (rating !== undefined && rating !== null) return `Rating ${Number(rating).toFixed(1)}`;

  return "No rating";
});

const releaseDate = computed(() => {
  if (props.movie.release_date) return props.movie.release_date;
  if (props.movie.year) return String(Math.trunc(props.movie.year));
  return "Unknown date";
});

const visibleGenres = computed(() => {
  const raw = props.movie.genres || "";
  return raw
    .split("|")
    .filter((genre) => genre && genre !== "(no genres listed)")
    .slice(0, 2);
});
</script>
