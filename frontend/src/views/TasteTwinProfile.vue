<template>
  <div class="space-y-6">
    <button class="text-sm font-medium text-slate-400 hover:text-white" @click="router.back()">返回</button>

    <section v-if="loading" class="grid min-h-[320px] place-items-center rounded-lg border border-dashed border-slate-700 bg-slate-900">
      <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-700 border-t-emerald-400"></div>
    </section>

    <section v-else-if="error" class="rounded-lg border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-100">
      {{ error }}
    </section>

    <template v-else-if="profile">
      <section class="rounded-lg border border-slate-700 bg-slate-900 p-5 shadow-lg shadow-black/20">
        <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p class="text-sm font-medium text-emerald-300">吃货公开主页</p>
            <h1 class="mt-1 text-3xl font-bold text-gray-100">{{ profile.community_alias }}</h1>
            <p class="mt-2 text-sm text-slate-400">
              <span v-if="profile.match_score">与你的口味契合度 {{ profile.match_score }}%。</span>
              这里仅展示公开口味信息。
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <span v-for="tag in profile.top_preference_tags" :key="tag" class="rounded-full bg-slate-800 px-2.5 py-1 text-xs text-slate-300">
              {{ tag }}
            </span>
          </div>
        </div>
      </section>

      <section class="rounded-lg border border-slate-700 bg-slate-900 p-5">
        <h2 class="text-lg font-semibold text-gray-100">Ta 觉得绝顶好吃，而你还没看过</h2>
        <div v-if="profile.recommended_recipes.length" class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <RecipeActionCard v-for="recipe in profile.recommended_recipes" :key="recipe.movie_id" :recipe="recipe" @toggle="toggleFavorite" />
        </div>
        <p v-else class="mt-4 rounded-lg border border-slate-700 p-4 text-sm text-slate-400">暂时没有新的可抄菜谱。</p>
      </section>

      <PagedRecipeSection
        title="高分评价列表"
        empty-text="Ta 暂时没有公开的高分评价。"
        :recipes="profile.high_rated_recipes"
        :page="profile.high_page"
        :total="profile.high_total"
        :has-more="profile.high_has_more"
        :loading="loadingHigh"
        @prev="changeHighPage(profile.high_page - 1)"
        @next="changeHighPage(profile.high_page + 1)"
        @toggle="toggleFavorite"
      />

      <PagedRecipeSection
        title="避雷列表"
        empty-text="Ta 暂时没有公开的避雷评价。"
        :recipes="profile.low_rated_recipes"
        :page="profile.low_page"
        :total="profile.low_total"
        :has-more="profile.low_has_more"
        :loading="loadingLow"
        @prev="changeLowPage(profile.low_page - 1)"
        @next="changeLowPage(profile.low_page + 1)"
        @toggle="toggleFavorite"
      />

      <div v-if="copyMessage" class="rounded-lg border border-emerald-500/30 bg-emerald-950/30 p-3 text-sm text-emerald-100">
        {{ copyMessage }}
      </div>
    </template>
  </div>
</template>

<script setup>
import { defineComponent, h, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import MovieCard from "../components/MovieCard.vue";
import { copyTasteTwinRecipe, getTasteTwinProfile } from "../api";
import { getCurrentUser } from "../utils/session";

const route = useRoute();
const router = useRouter();
const currentUser = ref(getCurrentUser());
const userId = currentUser.value?.user_id || null;
const twinUserId = Number(route.params.userId);
const profile = ref(null);
const loading = ref(false);
const loadingHigh = ref(false);
const loadingLow = ref(false);
const error = ref("");
const copyMessage = ref("");

async function loadProfile(highPage = 1, lowPage = 1) {
  if (!userId) throw new Error("请先登录后查看饭搭子主页");
  const { data } = await getTasteTwinProfile(userId, twinUserId, highPage, lowPage, 12);
  profile.value = data;
}

function updateCollectionState(movieId, isCollected) {
  if (!profile.value) return;
  const groups = [profile.value.recommended_recipes, profile.value.high_rated_recipes, profile.value.low_rated_recipes];
  groups.forEach((recipes) => {
    recipes.forEach((recipe) => {
      if (Number(recipe.movie_id) === Number(movieId)) recipe.is_collected = isCollected;
    });
  });
}

async function changeHighPage(page) {
  if (!profile.value || page < 1) return;
  loadingHigh.value = true;
  try {
    await loadProfile(page, profile.value.low_page);
  } finally {
    loadingHigh.value = false;
  }
}

async function changeLowPage(page) {
  if (!profile.value || page < 1) return;
  loadingLow.value = true;
  try {
    await loadProfile(profile.value.high_page, page);
  } finally {
    loadingLow.value = false;
  }
}

async function toggleFavorite(recipe) {
  if (!userId) return;
  const { data } = await copyTasteTwinRecipe(userId, recipe.movie_id);
  updateCollectionState(recipe.movie_id, Boolean(data.copied));
  copyMessage.value = data.message || (data.copied ? "已收藏" : "已取消收藏");
  window.setTimeout(() => {
    copyMessage.value = "";
  }, 1800);
}

const RecipeActionCard = defineComponent({
  props: { recipe: { type: Object, required: true } },
  emits: ["toggle"],
  setup(props, { emit }) {
    return () => h("div", { class: "space-y-2" }, [
      h(MovieCard, { movie: props.recipe }),
      h("button", {
        class: props.recipe.is_collected
          ? "w-full rounded-full border border-emerald-400 bg-emerald-500/15 px-3 py-2 text-sm font-medium text-emerald-100 hover:border-red-400 hover:text-red-100"
          : "w-full rounded-full bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-500",
        onClick: () => emit("toggle", props.recipe),
      }, props.recipe.is_collected ? "已收藏" : "一键收藏"),
    ]);
  },
});

const PagedRecipeSection = defineComponent({
  props: {
    title: String,
    emptyText: String,
    recipes: Array,
    page: Number,
    total: Number,
    hasMore: Boolean,
    loading: Boolean,
  },
  emits: ["prev", "next", "toggle"],
  setup(props, { emit }) {
    return () => h("section", { class: "rounded-lg border border-slate-700 bg-slate-900 p-5" }, [
      h("div", { class: "flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" }, [
        h("div", [
          h("h2", { class: "text-lg font-semibold text-gray-100" }, props.title),
          h("p", { class: "mt-1 text-xs text-slate-500" }, `共 ${props.total || 0} 条，每页最多 12 个`),
        ]),
        h("div", { class: "flex items-center gap-2" }, [
          h("button", {
            class: "rounded-full border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:cursor-not-allowed disabled:text-slate-500",
            disabled: props.loading || Number(props.page) <= 1,
            onClick: () => emit("prev"),
          }, "上一页"),
          h("span", { class: "text-sm text-slate-400" }, `第 ${props.page || 1} 页`),
          h("button", {
            class: "rounded-full border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:cursor-not-allowed disabled:text-slate-500",
            disabled: props.loading || !props.hasMore,
            onClick: () => emit("next"),
          }, "下一页"),
        ]),
      ]),
      props.recipes?.length
        ? h("div", { class: "mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4" }, props.recipes.map((recipe) =>
            h(RecipeActionCard, { key: recipe.movie_id, recipe, onToggle: (item) => emit("toggle", item) })
          ))
        : h("p", { class: "mt-4 rounded-lg border border-slate-700 p-4 text-sm text-slate-400" }, props.emptyText),
    ]);
  },
});

onMounted(async () => {
  loading.value = true;
  try {
    await loadProfile();
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || "加载主页失败";
  } finally {
    loading.value = false;
  }
});
</script>
