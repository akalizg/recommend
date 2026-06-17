<template>
  <div class="mx-auto max-w-6xl space-y-6">
    <section class="rounded-2xl border border-slate-700 bg-slate-900 shadow-lg shadow-black/20">
      <div class="border-b border-slate-700 px-5 py-6 md:px-8">
        <p class="text-sm font-medium text-emerald-300">新用户引导</p>
        <h1 class="mt-1 text-3xl font-bold text-gray-100">先告诉我你的口味偏好</h1>
        <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
          我会根据你选择的菜系、忌口、目标和做饭时间，先给你一轮更贴近需求的冷启动推荐。
        </p>
      </div>

      <div class="p-5 md:p-8">
        <div class="grid gap-6 lg:grid-cols-2">
          <section class="rounded-2xl border border-slate-700 bg-slate-950/60 p-5">
            <h2 class="text-lg font-semibold text-gray-100">喜欢的菜系 / 标签</h2>
            <div class="mt-4 flex flex-wrap gap-2">
              <button v-for="option in cuisineOptions" :key="option.value" type="button" class="rounded-full border px-4 py-2 text-sm transition-colors" :class="selections.tags.includes(option.value) ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100' : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-emerald-400'" @click="toggleSelection('tags', option.value)">{{ option.label }}</button>
            </div>
          </section>

          <section class="rounded-2xl border border-slate-700 bg-slate-950/60 p-5">
            <h2 class="text-lg font-semibold text-gray-100">喜欢的食材</h2>
            <div class="mt-4 flex flex-wrap gap-2">
              <button v-for="option in preferredIngredientOptions" :key="option.value" type="button" class="rounded-full border px-4 py-2 text-sm transition-colors" :class="selections.preferred_ingredients.includes(option.value) ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100' : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-emerald-400'" @click="toggleSelection('preferred_ingredients', option.value)">{{ option.label }}</button>
            </div>
          </section>

          <section class="rounded-2xl border border-slate-700 bg-slate-950/60 p-5">
            <h2 class="text-lg font-semibold text-gray-100">忌口食材</h2>
            <div class="mt-4 flex flex-wrap gap-2">
              <button v-for="option in dislikedIngredientOptions" :key="option.value" type="button" class="rounded-full border px-4 py-2 text-sm transition-colors" :class="selections.disliked_ingredients.includes(option.value) ? 'border-rose-400 bg-rose-500/15 text-rose-100' : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-rose-400'" @click="toggleSelection('disliked_ingredients', option.value)">{{ option.label }}</button>
            </div>
          </section>

          <section class="rounded-2xl border border-slate-700 bg-slate-950/60 p-5">
            <h2 class="text-lg font-semibold text-gray-100">饮食目标</h2>
            <div class="mt-4 flex flex-wrap gap-2">
              <button v-for="option in goalOptions" :key="option.value" type="button" class="rounded-full border px-4 py-2 text-sm transition-colors" :class="selections.goals.includes(option.value) ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100' : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-emerald-400'" @click="toggleSelection('goals', option.value)">{{ option.label }}</button>
            </div>
          </section>

          <section class="rounded-2xl border border-slate-700 bg-slate-950/60 p-5 lg:col-span-2">
            <h2 class="text-lg font-semibold text-gray-100">烹饪时间</h2>
            <div class="mt-4 flex flex-wrap gap-2">
              <button v-for="option in timeOptions" :key="option.value" type="button" class="rounded-full border px-4 py-2 text-sm transition-colors" :class="selections.times.includes(option.value) ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100' : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-emerald-400'" @click="toggleSelection('times', option.value)">{{ option.label }}</button>
            </div>
          </section>
        </div>

        <div class="mt-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p class="text-sm text-slate-400">你可以多选，后面也可以继续根据反馈调整。</p>
          <div class="flex gap-3">
            <button class="rounded-xl border border-slate-700 px-5 py-3 text-sm text-slate-300" @click="resetAll">清空重选</button>
            <button class="rounded-xl bg-primary-600 px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-600" :disabled="loading" @click="submit">
              {{ loading ? '正在推荐...' : '开始推荐' }}
            </button>
          </div>
        </div>

        <div v-if="error" class="mt-4 rounded-xl border border-red-500/30 bg-red-950/30 px-4 py-3 text-sm text-red-200">{{ error }}</div>

        <div v-if="recommendations.length" class="mt-8 space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-xl font-semibold text-gray-100">为你准备的冷启动推荐</h2>
            <p class="text-sm text-slate-400">基于你刚刚选择的偏好</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <article v-for="item in recommendations" :key="item.movie_id || item.recipe_id" class="overflow-hidden rounded-2xl border border-slate-700 bg-slate-950/60 shadow-lg shadow-black/20">
              <div class="h-48 bg-slate-800">
                <img v-if="item.image_url" :src="item.image_url" :alt="item.title" class="h-full w-full object-cover" />
                <div v-else class="flex h-full w-full items-center justify-center text-sm text-slate-500">暂无图片</div>
              </div>
              <div class="p-4">
                <div class="flex items-start justify-between gap-3">
                  <h3 class="text-base font-semibold text-gray-100">{{ item.title }}</h3>
                  <span class="rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-200">{{ Number(item.score || 0).toFixed(4) }}</span>
                </div>
                <p class="mt-3 text-sm leading-6 text-slate-300">{{ item.reason || item.final_reason }}</p>
              </div>
            </article>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { getColdStartRecipes, getScenarioRecommendations } from "../api";
import { saveOnboardingPreferences } from "../api/onboarding";
import { getCurrentUser, setCurrentUser } from "../utils/session";

const router = useRouter();
const loading = ref(false);
const error = ref(null);
const recommendations = ref([]);

const cuisineOptions = ["川菜", "粤菜", "湘菜", "甜点", "快手菜", "家常菜", "清淡", "下饭菜"].map((label) => ({ label, value: label }));
const preferredIngredientOptions = ["鸡肉", "牛肉", "猪肉", "海鲜", "鸡蛋", "蔬菜", "豆制品", "低脂"].map((label) => ({ label, value: label }));
const dislikedIngredientOptions = ["鸡肉", "牛肉", "猪肉", "海鲜", "鸡蛋", "蔬菜", "豆制品", "低脂"].map((label) => ({ label, value: label }));
const goalOptions = ["健身增肌", "低脂减重", "高蛋白", "控糖", "健康饮食", "营养均衡"].map((label) => ({ label, value: label }));
const timeOptions = ["15分钟快手", "30分钟以内", "1小时内", "周末大餐"].map((label) => ({ label, value: label }));

const selections = reactive({ tags: [], preferred_ingredients: [], disliked_ingredients: [], goals: [], times: [] });

function toggleSelection(key, value) {
  const list = selections[key];
  const idx = list.indexOf(value);
  if (idx >= 0) list.splice(idx, 1);
  else list.push(value);
}

function resetAll() {
  selections.tags = [];
  selections.preferred_ingredients = [];
  selections.disliked_ingredients = [];
  selections.goals = [];
  selections.times = [];
  recommendations.value = [];
  error.value = null;
}

function buildPayload(userId) {
  const maxMinutes = selections.times.includes("15分钟快手") ? 15 : selections.times.includes("30分钟以内") ? 30 : selections.times.includes("1小时内") ? 60 : undefined;
  return {
    user_id: userId,
    preferred_tags: selections.tags,
    preferred_ingredients: selections.preferred_ingredients,
    disliked_ingredients: selections.disliked_ingredients,
    ingredients: selections.preferred_ingredients,
    dietary_goals: selections.goals,
    max_minutes: maxMinutes,
    min_rating: selections.goals.includes("低脂减重") || selections.goals.includes("健康饮食") ? 4 : undefined,
    scenario: "personalized",
    limit: 12,
  };
}

async function submit() {
  error.value = null;
  const user = getCurrentUser();
  const userId = Number(user?.user_id || user?.recipe_user_id || 1);
  loading.value = true;
  try {
    const payload = buildPayload(userId);
    let data;
    try {
      const res = await getColdStartRecipes(payload);
      data = res.data;
    } catch {
      const scenarioPayload = {
        ...payload,
        scenario: payload.max_minutes && payload.max_minutes <= 30 ? "quick" : payload.dietary_goals.some((g) => /低脂|健康|减重|控糖/.test(g)) ? "healthy" : payload.preferred_ingredients.length ? "ingredients" : "explore",
      };
      const res = await getScenarioRecommendations(scenarioPayload);
      data = res.data;
    }
    recommendations.value = (data.recommendations || data.items || []).map((item) => ({
      ...item,
      image_url: item.image_url || "",
      title: item.title || item.name || `Recipe ${item.movie_id || item.recipe_id}`,
    }));

    const current = getCurrentUser() || {};
    const onboarding_preferences = payload;
    setCurrentUser({
      ...current,
      onboarding_done: true,
      onboarding_preferences,
    });
    await saveOnboardingPreferences(userId, onboarding_preferences).catch(() => null);

    if (recommendations.value.length) {
      router.push({ path: "/", query: { onboarding: "1" } });
    }
  } catch (e) {
    error.value = e?.response?.data?.detail || "推荐失败，请稍后重试";
  } finally {
    loading.value = false;
  }
}
</script>
