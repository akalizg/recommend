<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-100">Personalized Recipe Recommendations</h1>

    <div class="flex items-end gap-3">
      <div>
        <label class="mb-1 block text-sm text-gray-400">Food.com User ID</label>
        <input
          v-model.number="userId"
          type="number"
          min="1"
          class="w-36 rounded-lg border border-gray-600 bg-gray-800 px-4 py-2 text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
          @keyup.enter="fetchRecommendations"
        />
      </div>
      <button
        @click="fetchRecommendations"
        :disabled="loading"
        class="rounded-lg bg-primary-600 px-6 py-2 font-medium text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:bg-gray-600"
      >
        {{ loading ? "Loading..." : "Get Recipes" }}
      </button>
      <div class="ml-2 flex gap-2">
        <button
          v-for="n in [10, 20, 50]"
          :key="n"
          @click="topK = n; fetchRecommendations()"
          class="rounded-lg px-3 py-2 text-xs transition-colors"
          :class="topK === n ? 'bg-primary-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'"
        >
          Top {{ n }}
        </button>
      </div>
    </div>

    <div class="flex flex-wrap gap-2">
      <span class="mr-2 self-center text-xs text-gray-500">Quick pick:</span>
      <button
        v-for="uid in quickUsers"
        :key="uid"
        @click="userId = uid; fetchRecommendations()"
        class="rounded-full px-2.5 py-1 text-xs transition-colors"
        :class="userId === uid ? 'bg-primary-600 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'"
      >
        User {{ uid }}
      </button>
    </div>

    <div v-if="loading" class="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      <div v-for="i in 10" :key="i" class="h-64 animate-pulse rounded-xl bg-gray-800"></div>
    </div>

    <div v-else-if="error" class="py-12 text-center text-red-400">
      <p class="text-lg">{{ error }}</p>
      <p class="mt-2 text-sm text-gray-500">Try one of the quick-pick Food.com users</p>
    </div>

    <div v-else-if="recommendations.length">
      <div class="mb-4 flex items-center gap-4">
        <div class="text-sm text-gray-400">
          <span class="font-semibold text-emerald-400">Offline recipe results</span>
          <span class="ml-1">{{ resultInfo.tookMs }}ms</span>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-6 lg:grid-cols-4">
        <div class="lg:col-span-1">
          <UserProfile v-if="userId" :userId="userId" :key="userId" />
        </div>
        <div class="lg:col-span-3">
          <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4">
            <MovieCard v-for="(movie, idx) in recommendations" :key="movie.movie_id" :movie="movie">
              <template #default>
                <div class="absolute left-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-primary-600 text-xs font-bold">
                  {{ idx + 1 }}
                </div>
                <div
                  v-if="movie.final_reason"
                  class="absolute inset-x-0 bottom-0 translate-y-full bg-slate-950/92 p-3 text-xs leading-relaxed text-slate-200 backdrop-blur-sm transition duration-300 group-hover:translate-y-0"
                >
                  <p class="line-clamp-5">{{ movie.final_reason }}</p>
                </div>
              </template>
            </MovieCard>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="py-16 text-center text-gray-500">
      <p class="text-lg">Enter a Food.com User ID and click "Get Recipes"</p>
      <p class="mt-1 text-sm">Try one of the quick-pick users above</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { getOfflineRecommendations } from "../api";
import MovieCard from "../components/MovieCard.vue";
import UserProfile from "../components/UserProfile.vue";

const quickUsers = [1535, 2310, 2312, 3288, 4291, 4439, 4470, 5060, 6258, 6357, 6546, 8688];
const userId = ref(quickUsers[0]);
const topK = ref(20);
const recommendations = ref([]);
const loading = ref(false);
const error = ref(null);
const resultInfo = ref({ tookMs: 0 });

async function fetchRecommendations() {
  if (!userId.value || userId.value < 1) {
    error.value = "Please enter a valid Food.com User ID";
    return;
  }

  loading.value = true;
  error.value = null;
  recommendations.value = [];

  try {
    const started = performance.now();
    const { data } = await getOfflineRecommendations(userId.value, topK.value);
    recommendations.value = data.recommendations.map((item) => ({
      ...item,
      movie_id: item.movie_id,
      title: item.movie_title,
      genres: item.movie_genres,
      score: item.rank_score,
      image_url: item.image_url,
      ready_in_display: item.ready_in_display,
      recipe_yield_raw: item.recipe_yield_raw,
      author_name: item.author_name,
      avg_rating: item.rating_value,
    }));
    resultInfo.value = { tookMs: Math.round(performance.now() - started) };
  } catch (e) {
    error.value = e.response?.data?.detail || "Failed to get recipe recommendations";
  } finally {
    loading.value = false;
  }
}

onMounted(fetchRecommendations);
</script>
