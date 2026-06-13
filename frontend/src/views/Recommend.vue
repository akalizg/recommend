<template>
  <div class="space-y-6">
    <section class="rounded-lg border border-slate-700 bg-slate-900 p-5 shadow-lg shadow-black/20">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p class="text-sm font-medium text-emerald-300">智能食谱助手</p>
          <h1 class="mt-1 text-3xl font-bold text-gray-100">今天想怎么吃？</h1>
          <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            选择一个用餐场景，系统会结合离线推荐、内容匹配、排序模型和多样性重排生成当前这一批菜谱。
          </p>
        </div>

        <div class="flex flex-wrap gap-2">
          <button
            @click="refreshBatch"
            :disabled="loading || !recommendations.length"
            class="h-10 rounded-lg border border-slate-600 px-4 text-sm font-medium text-slate-200 transition-colors hover:border-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            换一批
          </button>
          <button
            @click="fetchRecommendations"
            :disabled="loading"
            class="h-10 rounded-lg bg-primary-600 px-5 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:bg-gray-600"
          >
            {{ loading ? "推荐中..." : "手动刷新" }}
          </button>
        </div>
      </div>

      <div class="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <button
          v-for="item in modes"
          :key="item.id"
          @click="selectMode(item.id)"
          class="min-h-28 rounded-lg border p-4 text-left transition"
          :class="mode === item.id
            ? 'border-emerald-400 bg-emerald-500/15 shadow-lg shadow-emerald-950/30'
            : 'border-slate-700 bg-slate-800/70 hover:border-slate-500'"
        >
          <span class="text-xs font-semibold text-slate-400">{{ item.kicker }}</span>
          <span class="mt-1 block text-base font-bold text-slate-100">{{ item.label }}</span>
          <span class="mt-2 block text-xs leading-5 text-slate-400">{{ item.description }}</span>
        </button>
      </div>
    </section>

    <div
      v-if="currentUser"
      class="rounded-lg border border-emerald-500/30 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-100"
    >
      当前账号：
      <span class="font-semibold">{{ currentUser.display_name || currentUser.username }}</span>
      <span class="ml-2 text-emerald-300">Food.com 用户 {{ currentUser.user_id }}</span>
    </div>

    <div
      v-else
      class="flex flex-col gap-3 rounded-lg border border-amber-500/30 bg-amber-950/20 px-4 py-3 text-sm text-amber-100 md:flex-row md:items-center md:justify-between"
    >
      <span>个性化推荐、探索发现和反馈闭环需要先登录；冷启动场景可直接体验。</span>
      <router-link
        to="/login"
        class="inline-flex h-9 items-center justify-center rounded-lg bg-primary-600 px-4 font-medium text-white transition-colors hover:bg-primary-500"
      >
        登录 / 注册
      </router-link>
    </div>

    <section class="rounded-lg border border-slate-700 bg-slate-900/80 p-4">
      <div class="grid gap-4 lg:grid-cols-[1fr_auto]">
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <div v-if="needsUser" class="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2">
            <span class="block text-sm text-gray-400">推荐身份</span>
            <span class="mt-1 block text-sm font-semibold text-gray-100">
              {{ currentUser ? `Food.com 用户 ${currentUser.user_id}` : "需要登录" }}
            </span>
          </div>

          <label v-if="mode === 'ingredients'" class="block md:col-span-2">
            <span class="mb-1 block text-sm text-gray-400">已有食材</span>
            <input
              v-model="ingredientText"
              type="text"
              placeholder="输入已有食材，例如 鸡肉、鸡蛋、土豆"
              class="h-10 w-full rounded-lg border border-gray-600 bg-gray-800 px-3 text-gray-100 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              @keyup.enter="fetchRecommendations"
            />
          </label>

          <div v-if="mode === 'healthy'" class="md:col-span-2 xl:col-span-3">
            <span class="mb-2 block text-sm text-gray-400">饮食目标</span>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="goal in dietaryGoals"
                :key="goal.value"
                @click="toggleGoal(goal.value)"
                class="rounded-lg border px-3 py-2 text-sm transition-colors"
                :class="selectedGoals.includes(goal.value)
                  ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
                  : 'border-slate-700 bg-slate-800 text-slate-300 hover:border-slate-500'"
              >
                {{ goal.label }}
              </button>
            </div>
          </div>

          <div v-if="mode === 'quick'" class="md:col-span-2">
            <span class="mb-2 block text-sm text-gray-400">最长烹饪时间</span>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="minutes in [15, 30, 45, 60]"
                :key="minutes"
                @click="setMaxMinutes(minutes)"
                class="rounded-lg border px-3 py-2 text-sm transition-colors"
                :class="maxMinutes === minutes
                  ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
                  : 'border-slate-700 bg-slate-800 text-slate-300 hover:border-slate-500'"
              >
                {{ minutes }} 分钟
              </button>
            </div>
          </div>

          <div v-if="mode === 'explore'" class="md:col-span-2">
            <div class="mb-1 flex items-center justify-between text-sm">
              <span class="text-gray-400">探索强度</span>
              <span class="font-semibold text-emerald-300">{{ Math.round(exploration * 100) }}%</span>
            </div>
            <input
              v-model.number="exploration"
              type="range"
              min="0"
              max="1"
              step="0.05"
              class="w-full accent-emerald-500"
            />
          </div>

          <div v-if="mode === 'ingredients'" class="md:col-span-2 xl:col-span-3">
            <span class="mb-2 block text-sm text-gray-400">常用食材</span>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="item in ingredientPresets"
                :key="item.value"
                @click="addIngredient(item.value)"
                class="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300 transition-colors hover:border-slate-500"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <div v-if="mode === 'quick'" class="md:col-span-2 xl:col-span-3">
            <span class="mb-2 block text-sm text-gray-400">用餐场景</span>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="tag in quickTags"
                :key="tag.value"
                @click="toggleTag(tag.value)"
                class="rounded-lg border px-3 py-2 text-sm transition-colors"
                :class="selectedTags.includes(tag.value)
                  ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
                  : 'border-slate-700 bg-slate-800 text-slate-300 hover:border-slate-500'"
              >
                {{ tag.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="flex flex-col gap-3 rounded-lg border border-slate-700 bg-slate-950/50 p-3">
          <div>
            <span class="mb-2 block text-sm text-gray-400">结果数量</span>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="n in [10, 20, 50]"
                :key="n"
                @click="setTopK(n)"
                class="h-9 rounded-lg border text-sm transition-colors"
                :class="topK === n
                  ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
                  : 'border-slate-700 bg-slate-800 text-slate-300 hover:border-slate-500'"
              >
                {{ n }}
              </button>
            </div>
          </div>

          <label v-if="usesColdStart" class="flex items-center gap-2 text-sm text-slate-300">
            <input v-model="requireImage" type="checkbox" class="h-4 w-4 rounded border-slate-600 accent-emerald-500" />
            优先显示有图片的菜谱
          </label>
        </div>
      </div>
    </section>

    <div v-if="feedbackNotice" class="rounded-lg border border-sky-500/30 bg-sky-950/30 px-4 py-3 text-sm text-sky-100">
      {{ feedbackNotice }}
    </div>

    <div v-if="loading" class="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      <div v-for="i in 10" :key="i" class="h-64 animate-pulse rounded-lg bg-gray-800"></div>
    </div>

    <div v-else-if="error" class="rounded-lg border border-red-500/30 bg-red-950/30 px-4 py-5 text-red-200">
      {{ error }}
    </div>

    <div v-else-if="displayedRecommendations.length" class="space-y-6">
      <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div class="text-sm text-gray-400">
          <span class="font-semibold text-emerald-300">{{ activeMode.label }}</span>
          <span class="ml-2">当前展示 {{ displayedRecommendations.length }} 道菜谱</span>
          <span class="ml-2">请求耗时 {{ resultInfo.tookMs }}ms</span>
        </div>
        <div class="max-w-full truncate text-xs text-gray-500">数据来源：{{ resultInfo.source }}</div>
      </div>

      <div class="grid grid-cols-1 gap-6" :class="showProfile ? 'lg:grid-cols-[280px_1fr]' : ''">
        <UserProfile v-if="showProfile" :userId="userId" :key="userId" />

        <div class="space-y-6">
          <section v-if="heroItems.length" class="rounded-lg border border-emerald-500/25 bg-emerald-950/10 p-4">
            <div class="mb-4 flex items-center justify-between">
              <div>
                <h2 class="text-lg font-bold text-slate-100">今日主推</h2>
                <p class="mt-1 text-xs text-slate-400">综合当前场景、排序分和可解释证据选出的优先结果</p>
              </div>
              <button
                @click="refreshBatch"
                class="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition-colors hover:border-emerald-400"
              >
                换一批
              </button>
            </div>
            <div class="grid gap-4 lg:grid-cols-3">
              <RecommendationCard
                v-for="(item, index) in heroItems"
                :key="`hero-${item.movie_id}`"
                :item="item"
                :rank="index + 1"
                :can-feedback="canSendFeedback"
                :feedback-status="feedbackStatus[item.movie_id]"
                :feedback-loading="isFeedbackLoading(item.movie_id)"
                @feedback="sendFeedback(item, index, $event.type, $event.value)"
              />
            </div>
          </section>

          <section v-for="section in resultSections" :key="section.id" class="space-y-3">
            <div>
              <h2 class="text-lg font-bold text-slate-100">{{ section.title }}</h2>
              <p class="mt-1 text-xs text-slate-400">{{ section.description }}</p>
            </div>
            <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <RecommendationCard
                v-for="(item, index) in section.items"
                :key="`${section.id}-${item.movie_id}`"
                :item="item"
                :rank="index + 1"
                :can-feedback="canSendFeedback"
                :feedback-status="feedbackStatus[item.movie_id]"
                :feedback-loading="isFeedbackLoading(item.movie_id)"
                @feedback="sendFeedback(item, index, $event.type, $event.value)"
              />
            </div>
          </section>
        </div>
      </div>
    </div>

    <div v-else class="rounded-lg border border-slate-800 bg-slate-900/60 py-12 text-center text-gray-500">
      暂无推荐结果
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { getScenarioRecommendations, submitFeedback } from "../api";
import UserProfile from "../components/UserProfile.vue";
import { getCurrentUser } from "../utils/session";
import { recipeImage, recipeTags, recipeTitle } from "../utils/recipeCover";

const RecommendationCard = defineComponent({
  props: {
    item: { type: Object, required: true },
    rank: { type: Number, required: true },
    canFeedback: { type: Boolean, default: false },
    feedbackStatus: { type: Object, default: null },
    feedbackLoading: { type: Boolean, default: false },
  },
  emits: ["feedback"],
  setup(props, { emit }) {
    return () => {
      const item = props.item;
      const title = recipeTitle(item);
      const cover = recipeImage(item);
      const rating = numberValue(item.rating_value, item.avg_rating, item.movie_avg_rating);
      const reviews = numberValue(item.review_count, item.rating_count, item.movie_rating_count);
      return h("article", { class: "overflow-hidden rounded-lg border border-slate-800 bg-slate-950/70 shadow-lg shadow-black/20" }, [
        h(RouterLink, { to: `/recipe/${item.movie_id || item.movieId}`, class: "group block" }, {
          default: () => [
            h("div", { class: "relative aspect-[4/3] overflow-hidden bg-slate-800" }, [
              h("img", { src: cover, alt: title, class: "h-full w-full object-cover transition duration-300 group-hover:scale-105", loading: "lazy" }),
              h("div", { class: "absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-slate-950/90 to-transparent" }),
              h("div", { class: "absolute left-2 top-2 rounded bg-primary-600 px-2 py-1 text-xs font-bold text-white" }, `#${props.rank}`),
              h("div", { class: "absolute right-2 top-2 rounded bg-black/75 px-2 py-1 text-xs font-bold text-amber-200" }, rating ? rating.toFixed(1) : "菜谱"),
            ]),
            h("div", { class: "space-y-3 p-3" }, [
              h("h3", { class: "line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-slate-100 group-hover:text-emerald-300" }, title),
              h("div", { class: "flex flex-wrap gap-1" }, item.evidenceTags.slice(0, 4).map((tag) =>
                h("span", { key: tag, class: "rounded bg-emerald-500/12 px-2 py-1 text-[11px] font-medium text-emerald-200" }, tag)
              )),
              h("p", { class: "line-clamp-3 text-xs leading-5 text-slate-400" }, item.templateReason),
              h("div", { class: "flex items-center justify-between gap-2 text-xs text-slate-500" }, [
                h("span", item.ready_in_display || (item.runtime ? `${item.runtime} 分钟` : "Food.com")),
                h("span", { class: "text-amber-300" }, reviews ? `${Math.trunc(reviews).toLocaleString()} 条评价` : "可查看详情"),
              ]),
            ]),
          ],
        }),
        props.canFeedback
          ? h("div", { class: "space-y-2 border-t border-slate-800 p-2" }, [
              h("div", { class: "grid grid-cols-3 gap-2" }, [
                feedbackButton("喜欢", "like", "emerald", props, emit),
                feedbackButton("不喜欢", "dislike", "red", props, emit),
                feedbackButton("减少类似", "less_similar", "sky", props, emit),
              ]),
              h("div", { class: "grid grid-cols-5 gap-1" }, [1, 2, 3, 4, 5].map((ratingValue) =>
                h("button", {
                  key: ratingValue,
                  disabled: props.feedbackLoading,
                  onClick: () => emit("feedback", { type: "rating", value: ratingValue }),
                  class: [
                    "h-7 rounded border text-[11px] transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                    props.feedbackStatus?.type === "rating" && props.feedbackStatus?.value === ratingValue
                      ? "border-amber-300 bg-amber-500/15 text-amber-200"
                      : "border-slate-700 bg-slate-900 text-slate-400 hover:border-amber-400",
                  ],
                }, String(ratingValue))
              )),
              h("div", { class: ["min-h-4 text-center text-[11px]", props.feedbackStatus?.ok ? "text-emerald-300" : "text-red-300"] }, props.feedbackStatus?.message || ""),
            ])
          : null,
      ]);
    };
  },
});

function feedbackButton(label, type, color, props, emit) {
  const active = props.feedbackStatus?.type === type;
  const activeClass = {
    emerald: "border-emerald-400 bg-emerald-500/15 text-emerald-200",
    red: "border-red-400 bg-red-500/15 text-red-200",
    sky: "border-sky-400 bg-sky-500/15 text-sky-200",
  }[color];
  const hoverClass = {
    emerald: "hover:border-emerald-500",
    red: "hover:border-red-500",
    sky: "hover:border-sky-500",
  }[color];
  return h("button", {
    disabled: props.feedbackLoading,
    onClick: () => emit("feedback", { type }),
    class: [
      "h-8 rounded border text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
      active ? activeClass : `border-slate-700 bg-slate-900 text-slate-300 ${hoverClass}`,
    ],
  }, label);
}

const modes = [
  { id: "personalized", label: "不知道吃什么", kicker: "个性化", pipeline: "LightGBM + MMR", description: "结合历史偏好和多样性重排，给出最稳妥的一批。" },
  { id: "ingredients", label: "用冰箱现有食材", kicker: "食材驱动", pipeline: "食材内容匹配", description: "输入家里已有食材，优先找能直接做的菜谱。" },
  { id: "healthy", label: "健康一点", kicker: "营养目标", pipeline: "营养特征筛选", description: "按低热量、高蛋白、低脂等目标筛选推荐。" },
  { id: "quick", label: "30 分钟快手饭", kicker: "时间约束", pipeline: "时间感知推荐", description: "适合工作日、赶时间或不想复杂备菜的场景。" },
  { id: "explore", label: "换个新口味", kicker: "探索发现", pipeline: "新颖性重排", description: "在不完全偏离口味的前提下，增加新鲜感。" },
];

const dietaryGoals = [
  { value: "healthy", label: "健康" },
  { value: "low-calorie", label: "低热量" },
  { value: "high-protein", label: "高蛋白" },
  { value: "low-fat", label: "低脂" },
  { value: "low-sugar", label: "低糖" },
  { value: "low-sodium", label: "低钠" },
];

const quickTags = [
  { value: "dinner", label: "晚餐" },
  { value: "breakfast", label: "早餐" },
  { value: "lunch", label: "午餐" },
  { value: "snacks", label: "小吃" },
];

const ingredientPresets = [
  { value: "鸡肉", label: "鸡肉" },
  { value: "鸡蛋", label: "鸡蛋" },
  { value: "土豆", label: "土豆" },
  { value: "米饭", label: "米饭" },
  { value: "番茄", label: "番茄" },
  { value: "奶酪", label: "奶酪" },
  { value: "牛肉", label: "牛肉" },
  { value: "苹果", label: "苹果" },
];

const ingredientTermMap = {
  鸡肉: "chicken",
  鸡胸肉: "chicken breast",
  鸡蛋: "egg",
  蛋: "egg",
  土豆: "potato",
  马铃薯: "potato",
  米饭: "rice",
  大米: "rice",
  番茄: "tomato",
  西红柿: "tomato",
  奶酪: "cheese",
  芝士: "cheese",
  牛肉: "beef",
  猪肉: "pork",
  鱼: "fish",
  虾: "shrimp",
  苹果: "apple",
  香蕉: "banana",
  洋葱: "onion",
  大蒜: "garlic",
  胡萝卜: "carrot",
  蘑菇: "mushroom",
  面包: "bread",
  面粉: "flour",
  牛奶: "milk",
  黄油: "butter",
  豆腐: "tofu",
  生菜: "lettuce",
  菠菜: "spinach",
};

const currentUser = ref(getCurrentUser());
const mode = ref("personalized");
const topK = ref(20);
const ingredientText = ref("鸡肉、鸡蛋");
const selectedGoals = ref(["healthy", "high-protein"]);
const selectedTags = ref(["dinner"]);
const maxMinutes = ref(30);
const exploration = ref(0.55);
const requireImage = ref(true);
const recommendations = ref([]);
const loading = ref(false);
const error = ref(null);
const resultInfo = ref({ tookMs: 0, source: "" });
const feedbackStatus = ref({});
const feedbackLoading = ref({});
const feedbackNotice = ref("");
const dismissedIds = ref(new Set());
const likedIds = ref(new Set());
const batchPage = ref(0);
const autoFetchReady = ref(false);
let autoFetchTimer = null;
let noticeTimer = null;
let requestVersion = 0;

const activeMode = computed(() => modes.find((item) => item.id === mode.value) || modes[0]);
const needsUser = computed(() => ["personalized", "explore"].includes(mode.value));
const usesColdStart = computed(() => ["ingredients", "healthy", "quick"].includes(mode.value));
const userId = computed(() => currentUser.value?.user_id || null);
const showProfile = computed(() => needsUser.value && Boolean(userId.value));
const canSendFeedback = computed(() => Boolean(userId.value));

const enrichedRecommendations = computed(() =>
  recommendations.value.map((item, index) => enrichRecommendation(item, index))
);

const filteredRecommendations = computed(() => {
  const liked = likedIds.value;
  const dismissed = dismissedIds.value;
  return enrichedRecommendations.value
    .filter((item) => !dismissed.has(Number(item.movie_id)))
    .sort((a, b) => {
      const aLiked = liked.has(Number(a.movie_id)) ? 1 : 0;
      const bLiked = liked.has(Number(b.movie_id)) ? 1 : 0;
      if (aLiked !== bLiked) return bLiked - aLiked;
      return (a._originalIndex || 0) - (b._originalIndex || 0);
    });
});

const displayedRecommendations = computed(() => {
  const items = filteredRecommendations.value;
  if (items.length <= 12) return items;
  const start = (batchPage.value * 9) % items.length;
  return [...items.slice(start), ...items.slice(0, start)].slice(0, 12);
});

const heroItems = computed(() => displayedRecommendations.value.slice(0, 3));

const resultSections = computed(() => {
  const rest = displayedRecommendations.value.slice(3);
  const primary = rest.slice(0, 6);
  const secondary = rest.slice(6, 12);
  const sections = [];
  if (primary.length) {
    sections.push({
      id: "scenario",
      title: activeMode.value.label,
      description: sectionDescription(mode.value),
      items: primary,
    });
  }
  if (secondary.length) {
    sections.push({
      id: "more",
      title: "补充发现",
      description: "用于增加选择空间，避免推荐结果只停留在一种口味里。",
      items: secondary,
    });
  }
  return sections;
});

function splitTerms(value) {
  return String(value || "")
    .split(/[;,，、|]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toIngredientQueryTerms(value) {
  return splitTerms(value).map((item) => ingredientTermMap[item] || item.toLowerCase());
}

function addIngredient(value) {
  const current = splitTerms(ingredientText.value);
  if (!current.includes(value)) current.push(value);
  ingredientText.value = current.join("、");
  scheduleFetch(0);
}

function toggleGoal(value) {
  if (selectedGoals.value.includes(value)) {
    selectedGoals.value = selectedGoals.value.filter((item) => item !== value);
  } else {
    selectedGoals.value = [...selectedGoals.value, value];
  }
  scheduleFetch(0);
}

function toggleTag(value) {
  if (selectedTags.value.includes(value)) {
    selectedTags.value = selectedTags.value.filter((item) => item !== value);
  } else {
    selectedTags.value = [...selectedTags.value, value];
  }
  scheduleFetch(0);
}

function selectMode(value) {
  if (mode.value === value) {
    scheduleFetch(0);
    return;
  }
  mode.value = value;
  scheduleFetch(0);
}

function setMaxMinutes(value) {
  if (maxMinutes.value === value) {
    scheduleFetch(0);
    return;
  }
  maxMinutes.value = value;
  scheduleFetch(0);
}

function setTopK(value) {
  if (topK.value === value) {
    scheduleFetch(0);
    return;
  }
  topK.value = value;
  scheduleFetch(0);
}

function refreshBatch() {
  batchPage.value += 1;
  showNotice("已切换到下一批候选菜谱。");
}

function scheduleFetch(delay = 300) {
  if (!autoFetchReady.value) return;
  if (autoFetchTimer) clearTimeout(autoFetchTimer);
  autoFetchTimer = window.setTimeout(() => {
    autoFetchTimer = null;
    fetchRecommendations();
  }, delay);
}

function buildPayload() {
  const payload = {
    scenario: mode.value,
    limit: topK.value,
    require_image: requireImage.value,
  };

  if (needsUser.value) {
    payload.user_id = Number(userId.value);
  }
  if (mode.value === "ingredients") {
    payload.ingredients = toIngredientQueryTerms(ingredientText.value);
  }
  if (mode.value === "healthy") {
    payload.dietary_goals = selectedGoals.value;
  }
  if (mode.value === "quick") {
    payload.max_minutes = maxMinutes.value;
    payload.preferred_tags = selectedTags.value;
  }
  if (mode.value === "explore") {
    payload.exploration = exploration.value;
  }

  return payload;
}

async function fetchRecommendations() {
  if (autoFetchTimer) {
    clearTimeout(autoFetchTimer);
    autoFetchTimer = null;
  }

  if (needsUser.value && (!userId.value || userId.value < 1)) {
    error.value = "请先登录后再使用个性化推荐";
    return;
  }

  const currentRequest = ++requestVersion;
  loading.value = true;
  error.value = null;
  recommendations.value = [];
  dismissedIds.value = new Set();
  likedIds.value = new Set();
  batchPage.value = 0;

  try {
    const started = performance.now();
    const { data } = await getScenarioRecommendations(buildPayload());
    if (currentRequest !== requestVersion) return;
    recommendations.value = data.recommendations || [];
    feedbackStatus.value = {};
    feedbackLoading.value = {};
    resultInfo.value = {
      tookMs: Math.round(performance.now() - started),
      source: data.source || "",
    };
  } catch (e) {
    if (currentRequest !== requestVersion) return;
    error.value = e.response?.data?.detail || "获取菜谱推荐失败";
  } finally {
    if (currentRequest === requestVersion) {
      loading.value = false;
    }
  }
}

function isFeedbackLoading(movieId) {
  return Boolean(feedbackLoading.value[movieId]);
}

async function sendFeedback(movie, index, type, value = null) {
  if (!canSendFeedback.value) return;
  const movieId = Number(movie.movie_id || movie.movieId);
  if (!movieId) return;

  applyImmediateFeedback(movieId, type, value);
  feedbackLoading.value = { ...feedbackLoading.value, [movieId]: true };
  try {
    await submitFeedback({
      user_id: Number(userId.value),
      movie_id: movieId,
      feedback_type: type,
      feedback_value: value,
      run_id: activeMode.value.id,
      experiment_name: "recipe_recall_rank_v1",
      group_name: mode.value,
      rank_position: index + 1,
      score: Number(movie.score || 0),
      reason: movie.templateReason || movie.final_reason || "",
    });
    feedbackStatus.value = {
      ...feedbackStatus.value,
      [movieId]: {
        ok: true,
        type,
        value,
        message: feedbackMessage(type, value),
      },
    };
  } catch (e) {
    feedbackStatus.value = {
      ...feedbackStatus.value,
      [movieId]: {
        ok: false,
        type,
        value,
        message: e.response?.data?.detail || "提交失败",
      },
    };
  } finally {
    feedbackLoading.value = { ...feedbackLoading.value, [movieId]: false };
  }
}

function applyImmediateFeedback(movieId, type, value) {
  if (type === "like" || (type === "rating" && Number(value) >= 4)) {
    likedIds.value = new Set([...likedIds.value, movieId]);
    showNotice("已收到正向反馈，当前列表会优先保留相似口味。");
  }
  if (type === "dislike" || type === "less_similar" || (type === "rating" && Number(value) <= 2)) {
    dismissedIds.value = new Set([...dismissedIds.value, movieId]);
    showNotice(type === "less_similar" ? "已减少类似菜谱，并从候选池补位。" : "已移除这道菜，并从候选池补位。");
  }
}

function feedbackMessage(type, value) {
  if (type === "rating") return `已评分 ${value}/5`;
  if (type === "like") return "已标记喜欢";
  if (type === "dislike") return "已减少推荐";
  if (type === "less_similar") return "已减少类似";
  return "反馈已保存";
}

function showNotice(message) {
  feedbackNotice.value = message;
  if (noticeTimer) clearTimeout(noticeTimer);
  noticeTimer = window.setTimeout(() => {
    feedbackNotice.value = "";
    noticeTimer = null;
  }, 2600);
}

function enrichRecommendation(item, index) {
  const tags = recipeTags(item);
  const evidenceTags = buildEvidenceTags(item, tags);
  return {
    ...item,
    _originalIndex: index,
    evidenceTags,
    templateReason: buildTemplateReason(item, evidenceTags, tags),
  };
}

function buildEvidenceTags(item, tags) {
  const evidence = [];
  const text = `${tags.join(" ")} ${item.ready_in_display || ""} ${item.title || ""}`.toLowerCase();
  const rating = numberValue(item.rating_value, item.avg_rating, item.movie_avg_rating);
  const reviews = numberValue(item.review_count, item.rating_count, item.movie_rating_count);
  const minutes = numberValue(item.runtime, item.minutes);

  if (mode.value === "personalized") evidence.push("口味匹配");
  if (mode.value === "ingredients") evidence.push("食材匹配");
  if (mode.value === "healthy") evidence.push(...selectedGoalLabels().slice(0, 2));
  if (mode.value === "quick") evidence.push(`${maxMinutes.value} 分钟内优先`);
  if (mode.value === "explore") evidence.push("新口味探索");
  if (rating && rating >= 4.5) evidence.push("高评分");
  if (reviews && reviews >= 50) evidence.push("评价稳定");
  if (minutes && minutes <= maxMinutes.value) evidence.push("省时");
  if (text.includes("easy") || text.includes("quick") || text.includes("30-minutes")) evidence.push("易上手");
  if (item.image_url) evidence.push("有图片");
  return [...new Set(evidence)].slice(0, 5);
}

function buildTemplateReason(item, evidenceTags, tags) {
  const titleTags = tags.slice(0, 3).join("、") || "当前菜谱标签";
  const rating = numberValue(item.rating_value, item.avg_rating, item.movie_avg_rating);
  const ratingText = rating ? `评分约 ${rating.toFixed(1)}，` : "";

  if (mode.value === "ingredients") {
    const terms = splitTerms(ingredientText.value).slice(0, 4).join("、");
    return `你输入了 ${terms || "现有食材"}，系统会把中文食材转换成 Food.com 可检索特征；这道菜与 ${titleTags} 等内容信号匹配，${ratingText}适合从现有食材出发快速筛选。`;
  }
  if (mode.value === "healthy") {
    return `当前目标是 ${selectedGoalLabels().join("、")}。系统会综合营养信号、评分和图片可用性筛选，这道菜在 ${evidenceTags.join("、")} 上更符合本轮健康推荐。`;
  }
  if (mode.value === "quick") {
    return `你选择了 ${maxMinutes.value} 分钟内的快手场景。系统优先考虑耗时、步骤复杂度和 ${titleTags} 标签，这道菜更适合时间有限时制作。`;
  }
  if (mode.value === "explore") {
    return `这道菜用于探索新口味：它不会完全偏离你的历史偏好，同时通过新颖性和多样性重排避免结果过于重复。`;
  }
  return `根据你的历史高分菜谱和相似用户行为，系统用多路召回生成候选，再由排序模型和 MMR 选择这道菜；它的 ${titleTags} 特征与当前偏好更接近。`;
}

function selectedGoalLabels() {
  const labels = new Map(dietaryGoals.map((goal) => [goal.value, goal.label]));
  return selectedGoals.value.map((goal) => labels.get(goal) || goal);
}

function sectionDescription(value) {
  if (value === "ingredients") return "围绕你输入的食材组织结果，让推荐看起来更像做饭助手。";
  if (value === "healthy") return "用营养目标解释排序结果，而不是只给出一串菜谱。";
  if (value === "quick") return "优先展示适合快速决策和快速制作的菜谱。";
  if (value === "explore") return "刻意加入新颖性和多样性，避免一直推荐同一类菜。";
  return "把个性化排序结果转成用户能理解的推荐证据。";
}

function numberValue(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "" && !Number.isNaN(Number(value))) {
      return Number(value);
    }
  }
  return null;
}

watch(mode, () => {
  error.value = null;
  feedbackStatus.value = {};
  feedbackLoading.value = {};
});

watch([exploration, requireImage, userId], () => {
  error.value = null;
  feedbackStatus.value = {};
  feedbackLoading.value = {};
  scheduleFetch(300);
});

function syncCurrentUser() {
  currentUser.value = getCurrentUser();
}

onMounted(() => {
  window.addEventListener("storage", syncCurrentUser);
  window.addEventListener("reciperec:user-changed", syncCurrentUser);
  autoFetchReady.value = true;
  fetchRecommendations();
});

onUnmounted(() => {
  if (autoFetchTimer) clearTimeout(autoFetchTimer);
  if (noticeTimer) clearTimeout(noticeTimer);
  window.removeEventListener("storage", syncCurrentUser);
  window.removeEventListener("reciperec:user-changed", syncCurrentUser);
});
</script>
