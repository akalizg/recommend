<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-100">搜索菜谱</h1>

    <div class="flex gap-3">
      <input
        v-model="query"
        type="text"
        placeholder="按菜谱名称、食材或标签搜索，例如 pasta、chicken、cookies"
        class="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-4 py-2.5 text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
        @keyup.enter="doSearch"
      />
      <button
        @click="doSearch"
        :disabled="loading || !query.trim()"
        class="px-6 py-2.5 bg-primary-600 hover:bg-primary-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white font-medium transition-colors"
      >
        {{ loading ? "搜索中..." : "搜索" }}
      </button>
    </div>

    <div v-if="loading" class="text-center py-8 text-gray-400">正在搜索...</div>

    <div v-else-if="results.length">
      <p class="text-sm text-gray-400 mb-4">找到 {{ total }} 条与 “{{ searchedQuery }}” 相关的结果</p>
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <MovieCard v-for="movie in results" :key="movie.movie_id" :movie="movie" />
      </div>
    </div>

    <div v-else-if="searchedQuery" class="text-center py-16 text-gray-500">
      <div class="text-6xl mb-4">🔍</div>
      <p>没有找到与 “{{ searchedQuery }}” 相关的菜谱</p>
    </div>

    <div v-else class="text-center py-16 text-gray-500">
      <div class="text-6xl mb-4">🔍</div>
      <p class="text-lg">搜索你想看的菜谱</p>
      <p class="text-sm mt-1">可以试试 “pasta”、“chicken” 或 “cookies”</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { searchMovies } from "../api";
import MovieCard from "../components/MovieCard.vue";

const query = ref("");
const searchedQuery = ref("");
const results = ref([]);
const total = ref(0);
const loading = ref(false);

async function doSearch() {
  if (!query.value.trim()) return;

  loading.value = true;
  results.value = [];
  searchedQuery.value = query.value.trim();

  try {
    const { data } = await searchMovies(query.value.trim());
    results.value = data.results;
    total.value = data.total;
  } catch (e) {
    results.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}
</script>

