<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-100">Personalized Recommendations</h1>

    <!-- User ID Input -->
    <div class="flex gap-3 items-end">
      <div>
        <label class="block text-sm text-gray-400 mb-1">User ID</label>
        <input
          v-model.number="userId"
          type="number"
          min="1"
          max="610"
          class="bg-gray-800 border border-gray-600 rounded-lg px-4 py-2 text-gray-100 w-32 focus:outline-none focus:ring-2 focus:ring-primary-500"
          @keyup.enter="fetchRecommendations"
        />
      </div>
      <button
        @click="fetchRecommendations"
        :disabled="loading"
        class="px-6 py-2 bg-primary-600 hover:bg-primary-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white font-medium transition-colors"
      >
        {{ loading ? "Loading..." : "Get Recommendations" }}
      </button>
      <div class="flex gap-2 ml-2">
        <button
          v-for="n in [10, 20, 50]"
          :key="n"
          @click="topK = n; fetchRecommendations()"
          class="px-3 py-2 text-xs rounded-lg transition-colors"
          :class="topK === n ? 'bg-primary-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'"
        >
          Top {{ n }}
        </button>
      </div>
    </div>

    <!-- Quick User Picker -->
    <div class="flex flex-wrap gap-2">
      <span class="text-xs text-gray-500 self-center mr-2">Quick pick:</span>
      <button
        v-for="uid in [1, 2, 3, 5, 10, 50, 100, 200, 300, 400, 500, 600]"
        :key="uid"
        @click="userId = uid; fetchRecommendations()"
        class="px-2.5 py-1 text-xs rounded-full transition-colors"
        :class="userId === uid ? 'bg-primary-600 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'"
      >
        User {{ uid }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <div v-for="i in 10" :key="i" class="bg-gray-800 rounded-xl h-64 animate-pulse"></div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-center py-12 text-red-400">
      <p class="text-lg">{{ error }}</p>
      <p class="text-sm text-gray-500 mt-2">Try a different User ID (1-610)</p>
    </div>

    <!-- Results -->
    <div v-else-if="recommendations.length">
      <div class="flex items-center gap-4 mb-4">
        <div class="text-sm text-gray-400">
          <span v-if="resultInfo.cached" class="text-emerald-400 font-semibold">Cached</span>
          <span v-else class="text-yellow-400 font-semibold">Live</span>
          <span class="ml-1">· {{ resultInfo.tookMs }}ms</span>
        </div>
      </div>

      <!-- User Profile (side by side on larger screens) -->
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div class="lg:col-span-1">
          <UserProfile v-if="userId" :userId="userId" :key="userId" />
        </div>
        <div class="lg:col-span-3">
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            <MovieCard v-for="(movie, idx) in recommendations" :key="movie.movie_id" :movie="movie">
              <template #default>
                <div class="absolute top-2 left-2 bg-primary-600 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">
                  {{ idx + 1 }}
                </div>
              </template>
            </MovieCard>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-16 text-gray-500">
      <div class="text-6xl mb-4">🎬</div>
      <p class="text-lg">Enter a User ID and click "Get Recommendations"</p>
      <p class="text-sm mt-1">Try User 1, 50, or 200 to get started</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { getRecommendations } from "../api";
import MovieCard from "../components/MovieCard.vue";
import UserProfile from "../components/UserProfile.vue";

const userId = ref(1);
const topK = ref(20);
const recommendations = ref([]);
const loading = ref(false);
const error = ref(null);
const resultInfo = ref({ cached: false, tookMs: 0 });

async function fetchRecommendations() {
  if (!userId.value || userId.value < 1) {
    error.value = "Please enter a valid User ID";
    return;
  }

  loading.value = true;
  error.value = null;
  recommendations.value = [];

  try {
    const { data } = await getRecommendations(userId.value, topK.value);
    recommendations.value = data.recommendations;
    resultInfo.value = { cached: data.cached, tookMs: data.took_ms };
  } catch (e) {
    error.value = e.response?.data?.detail || "Failed to get recommendations";
  } finally {
    loading.value = false;
  }
}
</script>
