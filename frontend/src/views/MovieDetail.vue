<template>
  <div>
    <!-- Loading -->
    <div v-if="loading" class="max-w-2xl mx-auto bg-gray-800 rounded-xl p-8 animate-pulse">
      <div class="h-8 bg-gray-700 rounded w-2/3 mb-4"></div>
      <div class="h-4 bg-gray-700 rounded w-1/3 mb-2"></div>
      <div class="h-4 bg-gray-700 rounded w-1/2 mb-6"></div>
      <div class="grid grid-cols-3 gap-4">
        <div class="h-20 bg-gray-700 rounded"></div>
        <div class="h-20 bg-gray-700 rounded"></div>
        <div class="h-20 bg-gray-700 rounded"></div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="max-w-2xl mx-auto text-center py-16">
      <div class="text-6xl mb-4">😕</div>
      <p class="text-lg text-red-400">{{ error }}</p>
      <router-link to="/" class="text-primary-400 hover:underline mt-4 inline-block">Back to Home</router-link>
    </div>

    <!-- Movie Detail -->
    <div v-else-if="movie" class="max-w-2xl mx-auto">
      <!-- Back -->
      <router-link to="/" class="text-sm text-gray-400 hover:text-white transition-colors mb-6 inline-block">
        ← Back
      </router-link>

      <div class="bg-gray-800 rounded-xl overflow-hidden">
        <!-- Header -->
        <div class="h-48 bg-gradient-to-br from-primary-700 to-purple-800 flex items-center justify-center">
          <span class="text-6xl">🎬</span>
        </div>

        <!-- Info -->
        <div class="p-6">
          <h1 class="text-2xl font-bold text-gray-100 mb-2">
            {{ movie.title }}
          </h1>

          <div class="flex flex-wrap gap-2 mb-4">
            <span
              v-for="genre in genres"
              :key="genre"
              class="px-3 py-1 bg-gray-700 rounded-full text-xs text-gray-300"
            >
              {{ genre }}
            </span>
          </div>

          <!-- Stats Grid -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <div class="bg-gray-700/50 rounded-lg p-3 text-center">
              <div class="text-xl font-bold text-yellow-400">
                {{ movie.avg_rating ? movie.avg_rating.toFixed(1) : "N/A" }}
              </div>
              <div class="text-xs text-gray-400 mt-0.5">Avg Rating</div>
            </div>
            <div class="bg-gray-700/50 rounded-lg p-3 text-center">
              <div class="text-xl font-bold text-primary-400">
                {{ movie.rating_count ?? "N/A" }}
              </div>
              <div class="text-xs text-gray-400 mt-0.5">Ratings</div>
            </div>
            <div class="bg-gray-700/50 rounded-lg p-3 text-center">
              <div class="text-xl font-bold text-emerald-400">
                {{ movie.popularity_score ? movie.popularity_score.toFixed(1) : "N/A" }}
              </div>
              <div class="text-xs text-gray-400 mt-0.5">Popularity</div>
            </div>
            <div class="bg-gray-700/50 rounded-lg p-3 text-center">
              <div class="text-xl font-bold text-purple-400">
                {{ movie.year || "N/A" }}
              </div>
              <div class="text-xs text-gray-400 mt-0.5">Year</div>
            </div>
          </div>

          <!-- Genres Breakdown -->
          <div>
            <h3 class="text-sm font-semibold text-gray-300 mb-2">Genre Tags</h3>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="genre in genres"
                :key="genre"
                class="px-3 py-1.5 bg-gray-700/50 border border-gray-600 rounded-lg text-sm text-gray-300"
              >
                {{ genre }}
              </span>
            </div>
          </div>
        </div>
      </div>
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
  return movie.value.genres.split("|").filter((g) => g !== "(no genres listed)");
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
