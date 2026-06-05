<template>
  <div v-if="loading" class="bg-gray-800 rounded-xl p-6 animate-pulse">
    <div class="h-6 bg-gray-700 rounded w-1/3 mb-4"></div>
    <div class="space-y-2">
      <div class="h-4 bg-gray-700 rounded w-2/3"></div>
      <div class="h-4 bg-gray-700 rounded w-1/2"></div>
    </div>
  </div>

  <div v-else-if="error" class="bg-gray-800 rounded-xl p-6 text-red-400">
    {{ error }}
  </div>

  <div v-else-if="profile" class="bg-gray-800 rounded-xl p-6">
    <h2 class="text-lg font-bold text-gray-100 mb-4">
      User #{{ profile.user_id }}
    </h2>

    <!-- Stats -->
    <div class="grid grid-cols-2 gap-3 mb-4">
      <div class="bg-gray-700/50 rounded-lg p-3 text-center">
        <div class="text-2xl font-bold text-primary-400">{{ profile.avg_rating }}</div>
        <div class="text-xs text-gray-400 mt-0.5">Avg Rating</div>
      </div>
      <div class="bg-gray-700/50 rounded-lg p-3 text-center">
        <div class="text-2xl font-bold text-primary-400">{{ profile.rating_count }}</div>
        <div class="text-xs text-gray-400 mt-0.5">Ratings</div>
      </div>
      <div class="bg-gray-700/50 rounded-lg p-3 text-center">
        <div class="text-2xl font-bold text-primary-400">{{ profile.rating_std }}</div>
        <div class="text-xs text-gray-400 mt-0.5">Std Dev</div>
      </div>
      <div class="bg-gray-700/50 rounded-lg p-3 text-center">
        <div class="text-sm font-bold text-emerald-400 uppercase">{{ profile.activity_level }}</div>
        <div class="text-xs text-gray-400 mt-0.5">Activity</div>
      </div>
    </div>

    <!-- Top Genres -->
    <div v-if="profile.top_genres?.length" class="mb-4">
      <h3 class="text-sm font-semibold text-gray-300 mb-2">Favorite Genres</h3>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="g in profile.top_genres.slice(0, 8)"
          :key="g.genre"
          class="px-2.5 py-1 bg-gray-700 rounded-full text-xs text-gray-300"
        >
          {{ g.genre }}
          <span class="text-primary-400 ml-1">{{ (g.score * 100).toFixed(0) }}%</span>
        </span>
      </div>
    </div>

    <!-- Top Rated -->
    <div v-if="profile.top_rated_movies?.length">
      <h3 class="text-sm font-semibold text-gray-300 mb-2">Top Rated</h3>
      <div class="space-y-1">
        <div
          v-for="m in profile.top_rated_movies.slice(0, 5)"
          :key="m.movieId"
          class="flex justify-between text-xs text-gray-400"
        >
          <span class="truncate mr-2">{{ m.title }}</span>
          <span class="text-yellow-500">★ {{ m.rating }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { getUserProfile } from "../api";

const props = defineProps({
  userId: { type: Number, required: true },
});

const profile = ref(null);
const loading = ref(true);
const error = ref(null);

onMounted(async () => {
  try {
    const { data } = await getUserProfile(props.userId);
    profile.value = data;
  } catch (e) {
    error.value = "Failed to load user profile";
  } finally {
    loading.value = false;
  }
});
</script>
