<template>
  <div>
    <div v-if="loading" class="mx-auto max-w-5xl animate-pulse">
      <div class="h-72 rounded-lg bg-slate-800"></div>
      <div class="mt-6 grid gap-6 md:grid-cols-[220px_1fr]">
        <div class="aspect-[2/3] rounded-lg bg-slate-800"></div>
        <div class="space-y-4">
          <div class="h-8 w-2/3 rounded bg-slate-800"></div>
          <div class="h-4 w-1/2 rounded bg-slate-800"></div>
          <div class="h-24 rounded bg-slate-800"></div>
        </div>
      </div>
    </div>

    <div v-else-if="error" class="mx-auto max-w-2xl py-16 text-center">
      <p class="text-lg text-red-400">{{ error }}</p>
      <router-link to="/" class="mt-4 inline-block text-cyan-300 hover:text-cyan-200">Back to Home</router-link>
    </div>

    <div v-else-if="movie" class="mx-auto max-w-5xl">
      <router-link to="/" class="mb-5 inline-block text-sm text-slate-400 transition-colors hover:text-white">
        Back
      </router-link>

      <section class="overflow-hidden rounded-lg border border-slate-700 bg-slate-900 shadow-xl shadow-black/20">
        <div class="relative min-h-72 bg-slate-800">
          <img
            v-if="movie.backdrop_url"
            :src="movie.backdrop_url"
            :alt="movie.title"
            class="absolute inset-0 h-full w-full object-cover"
          />
          <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/70 to-slate-950/20"></div>

          <div class="relative grid gap-6 p-5 sm:p-8 md:grid-cols-[220px_1fr] md:items-end">
            <div class="aspect-[2/3] overflow-hidden rounded-lg border border-slate-600 bg-slate-800 shadow-2xl">
              <img
                v-if="movie.poster_url"
                :src="movie.poster_url"
                :alt="movie.title"
                class="h-full w-full object-cover"
              />
              <div v-else class="flex h-full items-center justify-center px-5 text-center text-sm font-semibold text-slate-300">
                {{ movie.title }}
              </div>
            </div>

            <div>
              <h1 class="text-3xl font-bold text-white sm:text-4xl">{{ movie.title }}</h1>
              <div class="mt-3 flex flex-wrap gap-2">
                <span
                  v-for="genre in genres"
                  :key="genre"
                  class="rounded bg-cyan-400/12 px-3 py-1 text-xs font-medium text-cyan-100 ring-1 ring-cyan-300/20"
                >
                  {{ genre }}
                </span>
              </div>
              <p v-if="movie.overview" class="mt-5 max-w-3xl text-sm leading-6 text-slate-200">
                {{ movie.overview }}
              </p>
            </div>
          </div>
        </div>

        <div class="grid gap-3 border-t border-slate-800 p-5 sm:grid-cols-2 lg:grid-cols-4">
          <div class="rounded bg-slate-800/70 p-4">
            <div class="text-xl font-bold text-amber-300">{{ tmdbRating }}</div>
            <div class="mt-1 text-xs text-slate-400">TMDB Rating</div>
          </div>
          <div class="rounded bg-slate-800/70 p-4">
            <div class="text-xl font-bold text-cyan-300">{{ avgRating }}</div>
            <div class="mt-1 text-xs text-slate-400">MovieLens Rating</div>
          </div>
          <div class="rounded bg-slate-800/70 p-4">
            <div class="text-xl font-bold text-emerald-300">{{ movie.rating_count ?? "N/A" }}</div>
            <div class="mt-1 text-xs text-slate-400">Ratings</div>
          </div>
          <div class="rounded bg-slate-800/70 p-4">
            <div class="text-xl font-bold text-violet-300">{{ releaseAndRuntime }}</div>
            <div class="mt-1 text-xs text-slate-400">Release / Runtime</div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import { getMovieDetail } from "../api";

const route = useRoute();
const movie = ref(null);
const loading = ref(true);
const error = ref(null);

const genres = computed(() => {
  if (!movie.value?.genres) return [];
  return movie.value.genres.split("|").filter((genre) => genre && genre !== "(no genres listed)");
});

const tmdbRating = computed(() => {
  const rating = movie.value?.vote_average;
  return rating !== undefined && rating !== null ? Number(rating).toFixed(1) : "N/A";
});

const avgRating = computed(() => {
  const rating = movie.value?.avg_rating;
  return rating !== undefined && rating !== null ? Number(rating).toFixed(1) : "N/A";
});

const releaseAndRuntime = computed(() => {
  const release = movie.value?.release_date || movie.value?.year || "N/A";
  const runtime = movie.value?.runtime ? `${movie.value.runtime} min` : "";
  return runtime ? `${release} / ${runtime}` : release;
});

onMounted(async () => {
  try {
    const movieId = route.params.movieId;
    const { data } = await getMovieDetail(movieId);
    movie.value = data;
  } catch (e) {
    error.value = "Failed to load movie details";
  } finally {
    loading.value = false;
  }
});
</script>
