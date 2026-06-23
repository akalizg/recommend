<template>
  <section class="rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/20">
    <div class="flex items-center justify-between gap-4">
      <div>
        <p class="text-xs font-semibold uppercase tracking-[0.08em] text-emerald-300">基于你的喜欢</p>
        <h2 class="mt-1 text-2xl font-bold text-gray-100">专属菜谱推荐</h2>
        <p class="mt-2 text-sm text-slate-400">根据你刚完成的偏好引导，先给你一组更贴合口味的菜谱。</p>
      </div>
      <router-link to="/onboarding" class="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:border-emerald-400">重新选择偏好</router-link>
    </div>

    <div v-if="preferenceSummary" class="mt-4 rounded-2xl border border-slate-700 bg-slate-950/60 p-4 text-sm text-slate-300">
      <p class="font-medium text-emerald-300">你刚刚喜欢的偏好摘要</p>
      <p class="mt-2 leading-6">{{ preferenceSummary }}</p>
    </div>

    <div v-if="loading" class="mt-5 text-sm text-slate-400">正在加载你的专属推荐...</div>
    <div v-else-if="recommendations.length" class="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <router-link
        v-for="item in recommendations"
        :key="recipeId(item)"
        :to="recipeDetailPath(item)"
        class="group block overflow-hidden rounded-2xl border border-slate-700 bg-slate-950/60 transition duration-200 hover:-translate-y-0.5 hover:border-emerald-400/80 hover:shadow-lg hover:shadow-emerald-950/30 focus:outline-none focus:ring-2 focus:ring-emerald-400"
        :aria-label="`查看菜谱详情：${item.title}`"
      >
        <div class="h-44 bg-slate-800">
          <img v-if="item.image_url" :src="item.image_url" :alt="item.title" class="h-full w-full object-cover transition duration-300 group-hover:scale-105" />
          <div v-else class="flex h-full w-full items-center justify-center text-sm text-slate-500">暂无图片</div>
        </div>
        <div class="p-4">
          <div class="flex items-start justify-between gap-3">
            <h3 class="text-base font-semibold text-gray-100 transition-colors group-hover:text-emerald-300">{{ item.title }}</h3>
            <span class="rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-200">{{ Number(item.score || 0).toFixed(4) }}</span>
          </div>
          <p class="mt-3 text-sm leading-6 text-slate-300">{{ item.final_reason || item.reason }}</p>
        </div>
      </router-link>
    </div>
    <p v-else class="mt-5 text-sm text-slate-400">你完成偏好引导后，这里会展示专门根据你喜欢生成的菜谱。</p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { getColdStartRecipes, getScenarioRecommendations } from "../api";
import { getCurrentUser } from "../utils/session";

const loading = ref(false);
const recommendations = ref([]);
const preferenceSummary = computed(() => {
  const user = getCurrentUser();
  const prefs = user?.onboarding_preferences;
  if (!prefs) return "";
  const parts = [];
  if (prefs.preferred_tags?.length) parts.push(`偏好菜系/标签：${prefs.preferred_tags.join("、")}`);
  if (prefs.preferred_ingredients?.length) parts.push(`喜欢的食材：${prefs.preferred_ingredients.join("、")}`);
  if (prefs.disliked_ingredients?.length) parts.push(`忌口食材：${prefs.disliked_ingredients.join("、")}`);
  if (prefs.dietary_goals?.length) parts.push(`目标：${prefs.dietary_goals.join("、")}`);
  if (prefs.max_minutes) parts.push(`时间偏好：${prefs.max_minutes} 分钟内`);
  return parts.join("；");
});

function recipeId(item = {}) {
  return item.movie_id || item.movieId || item.recipe_id;
}

function recipeDetailPath(item = {}) {
  return `/recipe/${recipeId(item)}`;
}

async function load() {
  const user = getCurrentUser();
  const prefs = user?.onboarding_preferences;
  if (!prefs) return;
  loading.value = true;
  try {
    const payload = {
      user_id: user?.user_id || user?.recipe_user_id || 1,
      preferred_tags: prefs.tags || [],
      preferred_ingredients: prefs.preferred_ingredients || [],
      disliked_ingredients: prefs.disliked_ingredients || [],
      dietary_goals: prefs.goals || [],
      max_minutes: Number.parseInt((prefs.times?.[0] || "").match(/\d+/)?.[0] || "0", 10) || undefined,
      limit: 6,
    };
    let data;
    try {
      data = (await getColdStartRecipes(payload)).data;
    } catch {
      data = (await getScenarioRecommendations({ ...payload, scenario: "personalized" })).data;
    }
    recommendations.value = (data.recommendations || data.items || []).slice(0, 6).map((item) => ({
      ...item,
      movie_id: recipeId(item),
      recipe_id: recipeId(item),
      image_url: item.image_url || "",
      title: item.title || item.name || `Recipe ${item.movie_id || item.recipe_id}`,
    }));
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>
