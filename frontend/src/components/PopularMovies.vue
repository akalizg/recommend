<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-bold text-gray-100">热门菜谱</h2>
      <span v-if="tookMs" class="text-xs text-gray-500">{{ tookMs }}ms</span>
    </div>

    <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <div v-for="i in 10" :key="i" class="bg-gray-800 rounded-xl h-64 animate-pulse">
        <div class="h-40 bg-gray-700 rounded-t-xl"></div>
        <div class="p-3 space-y-2">
          <div class="h-4 bg-gray-700 rounded w-3/4"></div>
          <div class="h-3 bg-gray-700 rounded w-1/2"></div>
        </div>
      </div>
    </div>

    <div v-else-if="error" class="text-red-400 text-center py-8">{{ error }}</div>

    <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <MovieCard v-for="movie in movies" :key="movie.movie_id || movie.movieId" :movie="movie" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { getOfflinePopularRecipes } from "../api";
import MovieCard from "./MovieCard.vue";

const movies = ref([]);
const loading = ref(true);
const error = ref(null);
const tookMs = ref(null);

const props = defineProps({
  limit: { type: Number, default: 20 },
});

onMounted(async () => {
  try {
    const started = performance.now();
    const { data } = await getOfflinePopularRecipes(props.limit);
    movies.value = data.popular || [];
    tookMs.value = Math.round(performance.now() - started);
  } catch (e) {
    error.value = "热门菜谱加载失败";
  } finally {
    loading.value = false;
  }
});
</script>

