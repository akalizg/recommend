<template>
  <div>
    <div v-if="loading" class="mx-auto max-w-6xl animate-pulse">
      <div class="h-72 rounded-lg bg-slate-800"></div>
      <div class="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        <div class="space-y-4">
          <div class="h-8 w-2/3 rounded bg-slate-800"></div>
          <div class="h-32 rounded bg-slate-800"></div>
        </div>
        <div class="h-72 rounded bg-slate-800"></div>
      </div>
    </div>

    <div v-else-if="error" class="mx-auto max-w-2xl py-16 text-center">
      <p class="text-lg text-red-400">{{ error }}</p>
      <router-link to="/" class="mt-4 inline-block text-emerald-300 hover:text-emerald-200">Back to Home</router-link>
    </div>

    <div v-else-if="recipe" class="mx-auto max-w-6xl">
      <router-link to="/" class="mb-5 inline-block text-sm text-slate-400 transition-colors hover:text-white">
        Back
      </router-link>

      <section class="overflow-hidden rounded-lg border border-slate-700 bg-slate-900 shadow-xl shadow-black/20">
        <div class="relative min-h-[22rem] bg-slate-800">
          <img :src="coverImage" :alt="recipe.title" class="absolute inset-0 h-full w-full object-cover" />
          <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/75 to-slate-950/20"></div>

          <div class="relative grid gap-6 p-5 sm:p-8 lg:grid-cols-[1fr_320px] lg:items-end">
            <div>
              <h1 class="max-w-4xl text-3xl font-bold text-white sm:text-5xl">{{ recipe.title }}</h1>
              <p v-if="recipe.description" class="mt-5 max-w-3xl text-sm leading-6 text-slate-200">
                {{ recipe.description }}
              </p>
              <div class="mt-5 flex flex-wrap gap-2">
                <span
                  v-for="tag in visibleTags"
                  :key="tag"
                  class="rounded bg-emerald-400/12 px-3 py-1 text-xs font-medium text-emerald-100 ring-1 ring-emerald-300/20"
                >
                  {{ tag }}
                </span>
              </div>
            </div>

            <div class="overflow-hidden rounded-lg border border-slate-600 bg-slate-800 shadow-2xl">
              <img :src="coverImage" :alt="recipe.title" class="aspect-[4/3] w-full object-cover" />
            </div>
          </div>
        </div>

        <div class="grid gap-3 border-t border-slate-800 p-5 sm:grid-cols-2 lg:grid-cols-5">
          <InfoBox label="Ready In" :value="recipe.ready_in_display || minutesDisplay" />
          <InfoBox label="Yield" :value="recipe.recipe_yield_raw || recipe.serves || 'N/A'" />
          <InfoBox label="Author" :value="recipe.author_name || 'Food.com'" />
          <InfoBox label="Rating" :value="ratingDisplay" />
          <InfoBox label="Reviews" :value="reviewDisplay" />
        </div>
      </section>

      <div class="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        <section class="space-y-6">
          <div class="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <h2 class="text-xl font-bold text-slate-100">Ingredients</h2>
            <div class="mt-4 grid gap-3 sm:grid-cols-2">
              <div
                v-for="(ingredient, index) in ingredients"
                :key="`${ingredient}-${index}`"
                class="rounded bg-slate-800/70 p-3"
              >
                <div class="text-sm font-semibold text-slate-100">{{ ingredient }}</div>
                <div v-if="quantities[index]" class="mt-1 text-xs text-slate-400">{{ quantities[index] }}</div>
              </div>
            </div>
          </div>

          <div class="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <h2 class="text-xl font-bold text-slate-100">Steps</h2>
            <ol class="mt-4 space-y-3">
              <li v-for="(step, index) in steps" :key="`${index}-${step}`" class="flex gap-3 rounded bg-slate-800/70 p-3">
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-sm font-bold text-white">
                  {{ index + 1 }}
                </span>
                <span class="text-sm leading-6 text-slate-200">{{ step }}</span>
              </li>
            </ol>
          </div>

          <div v-if="similarRecipes.length" class="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <h2 class="text-xl font-bold text-slate-100">Similar Recipes</h2>
            <div class="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
              <MovieCard v-for="item in similarRecipes" :key="item.movie_id" :movie="item" />
            </div>
          </div>
        </section>

        <aside class="space-y-6">
          <div class="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <h2 class="text-xl font-bold text-slate-100">Nutrition</h2>
            <div class="mt-4 space-y-3">
              <div v-for="item in nutritionItems" :key="item.label" class="flex items-center justify-between border-b border-slate-800 pb-2 text-sm">
                <span class="text-slate-400">{{ item.label }}</span>
                <span class="font-semibold text-slate-100">{{ item.value }}</span>
              </div>
            </div>
          </div>

          <div class="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <h2 class="text-xl font-bold text-slate-100">Recipe Info</h2>
            <dl class="mt-4 space-y-3 text-sm">
              <div class="flex justify-between gap-3">
                <dt class="text-slate-400">Ingredients</dt>
                <dd class="text-slate-100">{{ recipe.n_ingredients ?? ingredients.length }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-slate-400">Steps</dt>
                <dd class="text-slate-100">{{ recipe.n_steps ?? steps.length }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-slate-400">Photos</dt>
                <dd class="text-slate-100">{{ numberOrNA(recipe.photo_count) }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-slate-400">Submitted</dt>
                <dd class="text-slate-100">{{ recipe.submitted || recipe.year || "N/A" }}</dd>
              </div>
            </dl>
            <a
              v-if="recipe.source_url"
              :href="recipe.source_url"
              target="_blank"
              rel="noopener noreferrer"
              class="mt-5 inline-flex w-full items-center justify-center rounded bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500"
            >
              Open on Food.com
            </a>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { getMovieDetail, getSimilarRecipes } from "../api";
import MovieCard from "../components/MovieCard.vue";
import { recipeImage, recipeTags } from "../utils/recipeCover";

const InfoBox = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: [String, Number], default: "N/A" },
  },
  setup(props) {
    return () =>
      h("div", { class: "rounded bg-slate-800/70 p-4" }, [
        h("div", { class: "text-xl font-bold text-emerald-300" }, String(props.value || "N/A")),
        h("div", { class: "mt-1 text-xs text-slate-400" }, props.label),
      ]);
  },
});

const route = useRoute();
const recipe = ref(null);
const similarRecipes = ref([]);
const loading = ref(true);
const error = ref(null);

function parseJsonList(value) {
  if (Array.isArray(value)) return value;
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function parseJsonObject(value) {
  if (value && typeof value === "object") return value;
  if (!value) return {};
  try {
    return JSON.parse(value) || {};
  } catch {
    return {};
  }
}

function numberOrNA(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "N/A";
  return Number(value).toLocaleString();
}

const visibleTags = computed(() => recipeTags(recipe.value || {}).slice(0, 16));
const coverImage = computed(() => recipeImage(recipe.value || {}));
const ingredients = computed(() => parseJsonList(recipe.value?.ingredients_json));
const quantities = computed(() => parseJsonList(recipe.value?.quantities_json));
const steps = computed(() => parseJsonList(recipe.value?.steps_json));

const minutesDisplay = computed(() => {
  const minutes = recipe.value?.minutes;
  return minutes ? `${Math.trunc(Number(minutes))} mins` : "N/A";
});

const ratingDisplay = computed(() => {
  const rating = recipe.value?.rating_value ?? recipe.value?.avg_rating;
  return rating !== undefined && rating !== null && !Number.isNaN(Number(rating)) ? Number(rating).toFixed(1) : "N/A";
});

const reviewDisplay = computed(() => numberOrNA(recipe.value?.review_count ?? recipe.value?.rating_count));

const nutritionItems = computed(() => {
  const nutrition = parseJsonObject(recipe.value?.nutrition_json);
  const pairs = [
    ["Calories", nutrition.calories],
    ["Total fat (%DV)", nutrition.total_fat_pct],
    ["Sugar (%DV)", nutrition.sugar_pct],
    ["Sodium (%DV)", nutrition.sodium_pct],
    ["Protein (%DV)", nutrition.protein_pct],
    ["Saturated fat (%DV)", nutrition.saturated_fat_pct],
    ["Carbohydrates (%DV)", nutrition.carbohydrates_pct],
  ];
  return pairs.map(([label, value]) => ({
    label,
    value: value === undefined || value === null || Number.isNaN(Number(value)) ? "N/A" : Number(value).toFixed(1),
  }));
});

onMounted(async () => {
  try {
    const movieId = route.params.movieId;
    const { data } = await getMovieDetail(movieId);
    recipe.value = data;
    try {
      const { data } = await getSimilarRecipes(movieId, 8);
      similarRecipes.value = data.similar || [];
    } catch {
      similarRecipes.value = [];
    }
  } catch (e) {
    error.value = "Failed to load recipe details";
  } finally {
    loading.value = false;
  }
});
</script>
