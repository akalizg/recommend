<template>
  <div class="space-y-6">
    <section class="rounded-lg border border-slate-700 bg-slate-900 shadow-lg shadow-black/20">
      <div class="flex flex-col gap-4 border-b border-slate-700 px-5 py-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p class="text-sm font-medium text-emerald-300">Taste Twin</p>
          <h1 class="mt-1 text-3xl font-bold text-gray-100">寻找饭搭子</h1>
          <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            开启社区发现后，系统会根据你的实时反馈和口味向量，在公开吃货中寻找相似的人。
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <router-link to="/taste-twin/records" class="rounded-full border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:border-emerald-400">
            我的记录
          </router-link>
          <button
            class="rounded-full bg-primary-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:bg-gray-600"
            :disabled="loading || !settings?.is_discoverable"
            @click="rotateMatches"
          >
            重新寻找
          </button>
        </div>
      </div>

      <div class="space-y-5 p-5">
        <div v-if="!currentUser" class="rounded-lg border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-100">
          请先登录并绑定 Food.com 用户 ID 后使用饭搭子。
          <router-link to="/login" class="font-medium text-white underline underline-offset-4">去登录</router-link>
        </div>

        <section v-else class="rounded-lg border border-slate-700 bg-slate-800/70 p-4">
          <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <div class="flex items-center gap-3">
                <h2 class="text-base font-semibold text-gray-100">社区发现</h2>
                <span class="rounded-full px-2.5 py-1 text-xs font-medium" :class="settings?.is_discoverable ? 'bg-emerald-500/15 text-emerald-200' : 'bg-slate-900 text-slate-400'">
                  {{ settings?.is_discoverable ? "已开启" : "已关闭" }}
                </span>
              </div>
              <p class="mt-1 text-sm text-slate-400">关闭后你不会被别人发现，也不能继续寻找饭搭子。</p>
            </div>
            <button
              class="rounded-full px-5 py-2 text-sm font-medium transition-colors"
              :class="settings?.is_discoverable ? 'border border-slate-600 text-slate-200 hover:border-red-400 hover:text-red-200' : 'bg-emerald-600 text-white hover:bg-emerald-500'"
              :disabled="savingSettings"
              @click="toggleDiscovery"
            >
              {{ settings?.is_discoverable ? "关闭社区" : "开启社区" }}
            </button>
          </div>

          <div class="mt-4 grid gap-3 lg:grid-cols-[1fr_1.2fr_220px_120px]">
            <input
              v-model.trim="alias"
              maxlength="48"
              class="h-11 rounded-lg border border-gray-600 bg-gray-800 px-3 text-sm text-gray-100 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="吃货代号，可留空自动生成"
            />
            <input
              v-model.trim="tagInput"
              class="h-11 rounded-lg border border-gray-600 bg-gray-800 px-3 text-sm text-gray-100 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="手动输入偏好标签，用逗号分隔"
            />
            <div class="relative">
              <button
                type="button"
                class="flex h-11 w-full items-center justify-between rounded-lg border border-gray-600 bg-gray-800 px-3 text-left text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
                @click="showTagMenu = !showTagMenu"
              >
                <span>下拉选择标签</span>
                <span class="text-slate-400">⌄</span>
              </button>
              <div
                v-if="showTagMenu"
                class="absolute left-0 right-0 top-full z-30 mt-2 max-h-64 overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 p-2 shadow-xl shadow-black/30"
              >
                <button
                  v-for="tag in tagOptions"
                  :key="tag"
                  type="button"
                  class="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:text-slate-500"
                  :disabled="parsedTags.includes(tag)"
                  @click="addSelectedTag(tag)"
                >
                  <span class="truncate">{{ tag }}</span>
                  <span v-if="parsedTags.includes(tag)" class="ml-2 shrink-0 text-xs text-emerald-300">已选</span>
                </button>
              </div>
            </div>
            <button
              class="h-11 rounded-lg bg-primary-600 px-4 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:bg-gray-600"
              :disabled="savingSettings"
              @click="saveCurrentSettings"
            >
              {{ savingSettings ? "保存中" : "确认" }}
            </button>
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            <button
              v-for="tag in parsedTags"
              :key="tag"
              class="rounded-full bg-slate-900 px-3 py-1 text-xs text-slate-300 hover:text-red-200"
              @click="removeTag(tag)"
            >
              {{ tag }} x
            </button>
          </div>
        </section>

        <div v-if="loading" class="grid min-h-[360px] place-items-center rounded-lg border border-dashed border-slate-700 bg-slate-950/40">
          <div class="text-center">
            <div class="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-slate-700 border-t-emerald-400"></div>
            <p class="mt-4 text-sm font-medium text-slate-300">正在高维空间中寻找你的口味伴侣...</p>
          </div>
        </div>

        <div v-else-if="error" class="rounded-lg border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-100">
          {{ error }}
        </div>

        <div v-else-if="settings?.is_discoverable && matches.length === 0" class="rounded-lg border border-dashed border-slate-700 bg-slate-950/40 p-8 text-center">
          <h2 class="text-lg font-semibold text-gray-100">还没有找到可公开的饭搭子</h2>
          <p class="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            当前本地库里可能还没有其他公开用户。按隐私规则，未开启社区发现的用户不会进入匹配池。
          </p>
          <div class="mt-5 flex flex-wrap justify-center gap-3">
            <button class="rounded-full border border-slate-600 px-5 py-2 text-sm text-slate-200 hover:border-emerald-400" @click="loadMatches(true)">
              再找一次
            </button>
          </div>
        </div>

        <div v-else-if="settings?.is_discoverable" class="space-y-4">
          <div class="flex items-center justify-between gap-3">
            <p class="text-sm text-slate-400">已找到 {{ matches.length }} 个候选，每次展示 5 个。</p>
            <span class="text-sm text-slate-500">第 {{ matchPage + 1 }} 组</span>
          </div>

          <article v-for="match in visibleMatches" :key="match.user_id" class="rounded-lg border border-slate-700 bg-slate-800/70 p-4">
            <div class="flex items-start justify-between gap-4">
              <div>
                <h2 class="text-lg font-semibold text-gray-100">{{ match.community_alias }}</h2>
                <p class="mt-1 text-sm text-slate-400">口味契合度 {{ match.match_score }}%</p>
              </div>
              <div class="rounded-full bg-emerald-500/15 px-3 py-1 text-sm font-semibold text-emerald-200">{{ match.match_score }}%</div>
            </div>

            <div class="mt-3 flex flex-wrap gap-2">
              <span v-for="tag in displayTags(match)" :key="tag" class="rounded-full bg-slate-900 px-2.5 py-1 text-xs text-slate-300">
                {{ tag }}
              </span>
            </div>

            <div class="mt-4 grid gap-4 lg:grid-cols-2">
              <RecipeStrip title="本命菜谱" :recipes="match.high_rated_recipes" />
              <RecipeStrip title="避雷菜谱" :recipes="match.low_rated_recipes" />
            </div>

            <div class="mt-4 flex flex-wrap gap-2">
              <button class="rounded-full border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:border-emerald-400" @click="openProfile(match.user_id)">
                查看主页
              </button>
              <button class="rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500" @click="openJointMenu(match.user_id)">
                生成双人菜单
              </button>
            </div>

            <section v-if="jointMenu && activeTwinId === match.user_id" class="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-4">
              <div class="flex items-center justify-between gap-3">
                <h3 class="text-base font-semibold text-emerald-100">今日双人菜单</h3>
                <button class="rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500" @click="shuffleJointMenu">
                  换一换
                </button>
              </div>
              <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                <MovieCard v-for="recipe in jointMenu.recipes" :key="recipe.movie_id" :movie="recipe" />
              </div>
            </section>
          </article>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import MovieCard from "../components/MovieCard.vue";
import {
  getTasteTwinSettings,
  getTasteTwinMatches,
  getTasteTwinJointMenu,
  updateTasteTwinSettings,
} from "../api";
import { getCurrentUser } from "../utils/session";

const tagOptions = [
  "time-to-make",
  "course",
  "main-ingredient",
  "preparation",
  "dietary",
  "quick-and-easy",
  "easy",
  "30-minutes-or-less",
  "15-minutes-or-less",
  "60-minutes-or-less",
  "beginner-cook",
  "healthy",
  "low-fat",
  "low-calorie",
  "low-carb",
  "low-sodium",
  "low-cholesterol",
  "low-saturated-fat",
  "high-protein",
  "high-fiber",
  "vegetarian",
  "vegan",
  "gluten-free",
  "desserts",
  "main-dish",
  "side-dishes",
  "breakfast",
  "lunch",
  "dinner-party",
  "snacks",
  "appetizers",
  "beverages",
  "soups-stews",
  "salads",
  "breads",
  "chicken",
  "beef",
  "pork",
  "seafood",
  "fish",
  "eggs-dairy",
  "vegetables",
  "fruit",
  "pasta-rice-and-grains",
  "potatoes",
  "beans",
  "cheese",
  "chocolate",
  "american",
  "asian",
  "chinese",
  "japanese",
  "thai",
  "indian",
  "mexican",
  "italian",
  "french",
  "mediterranean",
  "middle-eastern",
  "southern-united-states",
  "spicy",
  "sweet",
  "savory",
  "comfort-food",
  "kid-friendly",
  "holiday-event",
  "summer",
  "winter",
  "oven",
  "stove-top",
  "grilling",
  "crock-pot-slow-cooker",
];

const router = useRouter();
const currentUser = ref(getCurrentUser());
const settings = ref(null);
const matches = ref([]);
const matchPage = ref(0);
const jointMenu = ref(null);
const activeTwinId = ref(null);
const jointOffset = ref(0);
const alias = ref("");
const tagInput = ref("");
const showTagMenu = ref(false);
const loading = ref(false);
const savingSettings = ref(false);
const error = ref("");

const userId = computed(() => currentUser.value?.user_id || null);
const parsedTags = computed(() => tagInput.value.split(",").map((tag) => tag.trim()).filter(Boolean).slice(0, 12));
const visibleMatches = computed(() => matches.value.slice(matchPage.value * 5, matchPage.value * 5 + 5));

function displayTags(match) {
  return match.shared_tags?.length ? match.shared_tags : match.top_preference_tags;
}

function addSelectedTag(tag) {
  if (!tag) return;
  const tags = new Set(parsedTags.value);
  tags.add(tag);
  tagInput.value = Array.from(tags).join(", ");
  showTagMenu.value = false;
}

function removeTag(tag) {
  tagInput.value = parsedTags.value.filter((item) => item !== tag).join(", ");
}

async function loadSettings() {
  if (!userId.value) return;
  const { data } = await getTasteTwinSettings(userId.value);
  settings.value = data;
  alias.value = data.community_alias || "";
  tagInput.value = (data.preference_tags || []).join(", ");
}

async function persistSettings(isDiscoverable) {
  if (!userId.value) return null;
  const { data } = await updateTasteTwinSettings(userId.value, {
    is_discoverable: isDiscoverable,
    community_alias: alias.value || null,
    preference_tags: parsedTags.value,
  });
  settings.value = data;
  alias.value = data.community_alias || "";
  tagInput.value = (data.preference_tags || []).join(", ");
  return data;
}

async function saveCurrentSettings() {
  if (!settings.value || savingSettings.value) return;
  savingSettings.value = true;
  error.value = "";
  try {
    await persistSettings(Boolean(settings.value.is_discoverable));
    if (settings.value.is_discoverable) await loadMatches(true);
  } catch (err) {
    error.value = err?.response?.data?.detail || "保存社区设置失败";
  } finally {
    savingSettings.value = false;
  }
}

async function saveDiscovery(isDiscoverable) {
  if (!userId.value) return;
  savingSettings.value = true;
  error.value = "";
  try {
    const data = await persistSettings(isDiscoverable);
    jointMenu.value = null;
    matches.value = [];
    matchPage.value = 0;
    if (data?.is_discoverable) await loadMatches(true);
  } catch (err) {
    error.value = err?.response?.data?.detail || "保存社区设置失败";
  } finally {
    savingSettings.value = false;
  }
}

function toggleDiscovery() {
  saveDiscovery(!settings.value?.is_discoverable);
}

async function loadMatches(resetPage = false) {
  if (!userId.value || !settings.value?.is_discoverable) return;
  loading.value = true;
  error.value = "";
  try {
    const { data } = await getTasteTwinMatches(userId.value, 10);
    matches.value = data || [];
    if (resetPage || matchPage.value * 5 >= matches.value.length) matchPage.value = 0;
  } catch (err) {
    error.value = err?.response?.data?.detail || "寻找饭搭子失败";
  } finally {
    loading.value = false;
  }
}

async function rotateMatches() {
  if (!matches.value.length) {
    await loadMatches(true);
    return;
  }
  const groupCount = Math.max(1, Math.ceil(matches.value.length / 5));
  matchPage.value = (matchPage.value + 1) % groupCount;
  await loadMatches(false);
}

function openProfile(twinUserId) {
  router.push(`/taste-twin/${twinUserId}`);
}

async function openJointMenu(twinUserId) {
  activeTwinId.value = twinUserId;
  jointOffset.value = 0;
  const { data } = await getTasteTwinJointMenu(userId.value, twinUserId, jointOffset.value);
  jointMenu.value = data;
  jointOffset.value = data.next_offset || 0;
}

async function shuffleJointMenu() {
  if (!activeTwinId.value) return;
  const { data } = await getTasteTwinJointMenu(userId.value, activeTwinId.value, jointOffset.value);
  jointMenu.value = data;
  jointOffset.value = data.next_offset || 0;
}

const RecipeStrip = defineComponent({
  props: {
    title: { type: String, required: true },
    recipes: { type: Array, default: () => [] },
  },
  setup(props) {
    return () => h("section", {
      class: "min-w-0 rounded-lg border border-slate-700 bg-slate-900/70 p-3",
    }, [
      h("h3", { class: "text-sm font-semibold text-slate-200" }, props.title),
      props.recipes?.length
        ? h("div", { class: "mt-3 grid grid-cols-3 gap-3 overflow-hidden" }, props.recipes.slice(0, 3).map((recipe) =>
            h("div", { key: recipe.movie_id, class: "min-w-0" }, [
              h(MovieCard, { movie: recipe }),
            ])
          ))
        : h("div", { class: "mt-3 grid h-56 place-items-center rounded-lg border border-dashed border-slate-700 p-3 text-center text-sm text-slate-500" }, "暂时没有公开菜谱"),
    ]);
  },
});

onMounted(async () => {
  try {
    await loadSettings();
    if (settings.value?.is_discoverable) await loadMatches(true);
  } catch (err) {
    error.value = err?.response?.data?.detail || "加载饭搭子失败";
  }
});
</script>
