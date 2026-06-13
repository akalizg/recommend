<template>
  <div class="space-y-6">
    <section class="rounded-lg border border-slate-700 bg-slate-900 shadow-lg shadow-black/20">
      <div class="flex flex-col gap-4 border-b border-slate-700 px-5 py-5 md:flex-row md:items-center md:justify-between">
        <div class="max-w-3xl">
          <p class="text-sm font-medium text-emerald-300">智能食谱助手</p>
          <h1 class="mt-1 text-3xl font-bold text-gray-100">今天想怎么吃？</h1>
          <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            直接输入你的要求，助手会理解食材、时间、口味和健康目标，并在对话里给出推荐结果。
          </p>
        </div>
        <div class="relative hidden h-32 w-[420px] shrink-0 md:block" aria-hidden="true">
          <img
            src="/hero-food/chicken-pizza.jpg"
            alt=""
            class="absolute right-0 top-2 h-28 w-44 rounded-lg border border-slate-700 object-cover shadow-lg"
          />
          <img
            src="/hero-food/yakisoba.jpg"
            alt=""
            class="absolute right-36 top-0 h-24 w-36 rounded-lg border border-slate-700 object-cover shadow-lg"
          />
          <img
            src="/hero-food/cheesecake.jpg"
            alt=""
            class="absolute right-24 bottom-0 h-20 w-32 rounded-lg border border-slate-700 object-cover shadow-lg"
          />
        </div>
      </div>

      <div class="bg-slate-800/50 px-4 py-5 md:px-6">
        <div class="flex min-h-[620px] flex-col gap-5 rounded-lg border border-slate-700 bg-slate-900/70 p-4 md:p-5">
        <div class="order-last mt-auto w-full">
          <div class="w-full space-y-3">
          <div class="flex flex-nowrap gap-2 overflow-x-auto pb-1">
            <button
              v-for="item in modes"
              :key="item.id"
              @click="selectMode(item.id)"
              class="h-8 shrink-0 rounded-full border border-slate-700 bg-slate-800 px-3 text-xs text-slate-300 transition hover:border-emerald-400"
              :title="item.description"
            >
              {{ item.label }}
            </button>
            <button
              @click="askSuggestion('为什么推荐这些菜？')"
              class="h-8 shrink-0 rounded-full border border-slate-700 bg-slate-800 px-3 text-left text-xs text-slate-300 transition-colors hover:border-emerald-400"
            >
              为什么推荐这些菜？
            </button>
          </div>

          <form class="flex flex-col gap-3 md:flex-row" @submit.prevent="sendChat">
            <input
              v-model.trim="chatInput"
              type="text"
              placeholder="例如：我有鸡肉和土豆，想吃 30 分钟内的高蛋白晚餐"
              class="h-12 flex-1 rounded-lg border border-gray-600 bg-gray-800 px-4 text-base text-gray-100 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <button
              type="submit"
              :disabled="!chatInput"
              class="h-12 rounded-lg bg-primary-600 px-6 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:bg-gray-600"
            >
              发送
            </button>
          </form>
          </div>
        </div>

          <div v-if="!currentUser" class="order-2 flex justify-center">
            <div class="flex max-w-3xl flex-col gap-3 rounded-full border border-amber-500/30 bg-amber-950/20 px-4 py-2 text-xs text-amber-100 md:flex-row md:items-center">
              <span>登录后可以使用个性化推荐、喜欢/不喜欢反馈和实时闭环。</span>
              <router-link to="/login" class="font-medium text-gray-100 underline underline-offset-4">登录 / 注册</router-link>
            </div>
          </div>

          <div v-for="message in chatMessages" :key="message.id" class="order-1 flex gap-3" :class="message.role === 'user' ? 'justify-end' : 'justify-start'">
            <div v-if="message.role !== 'user'" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-600 text-xs font-semibold text-white">
              AI
            </div>
            <div
              v-if="!message.type || message.type === 'text'"
              class="max-w-[92%] rounded-2xl border px-4 py-3 text-sm leading-6 shadow-sm md:max-w-[86%] xl:max-w-[90%]"
              :class="message.role === 'user'
                ? 'border-slate-700 bg-primary-600 text-white'
                : 'border-slate-700 bg-slate-800 text-slate-300'"
            >
              {{ message.content }}
            </div>
            <div v-else-if="message.type === 'guide'" class="min-w-0 flex-1 rounded-2xl border border-slate-700 bg-slate-800 p-4 shadow-sm">
              <p class="text-sm font-semibold text-gray-100">{{ message.title }}</p>
              <p class="mt-2 text-sm leading-6 text-slate-400">{{ message.content }}</p>

              <div v-if="isActiveGuide(message) && mode === 'ingredients'" class="mt-4 space-y-3">
                <div class="relative">
                  <input
                    v-model="ingredientText"
                    type="text"
                    placeholder="例如：鸡肉、鸡蛋、土豆"
                    class="h-11 w-full rounded-lg border border-gray-600 bg-gray-800 px-4 text-sm text-gray-100 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    @focus="showIngredientSuggestions = true"
                    @keyup.enter="startScenarioRecommendation"
                  />
                  <div
                    v-if="showIngredientSuggestions && ingredientSuggestions.length"
                    class="absolute left-0 right-0 top-full z-20 mt-2 max-h-64 overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 p-2 shadow-xl shadow-black/30"
                  >
                    <button
                      v-for="item in ingredientSuggestions"
                      :key="item.name"
                      type="button"
                      @mousedown.prevent="addIngredientDraft(item.label)"
                      class="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm text-slate-200 hover:bg-slate-800"
                    >
                      <span class="truncate">{{ item.label }}</span>
                      <span class="ml-3 shrink-0 text-xs text-slate-500">{{ item.count.toLocaleString() }} 道</span>
                    </button>
                  </div>
                </div>
                <p v-if="ingredientLookupError" class="text-xs text-amber-200">{{ ingredientLookupError }}</p>
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="item in ingredientPresets"
                    :key="item.value"
                    @click="addIngredientDraft(item.value)"
                    class="rounded-full border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-emerald-400"
                  >
                    {{ item.label }}
                  </button>
                </div>
                <button
                  @click="startScenarioRecommendation"
                  :disabled="!splitTerms(ingredientText).length"
                  class="rounded-full bg-primary-600 px-5 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-gray-600"
                >
                  按这些食材推荐
                </button>
              </div>

              <div v-else-if="isActiveGuide(message) && mode === 'healthy'" class="mt-4 flex flex-wrap gap-2">
                <button
                  v-for="goal in dietaryGoals"
                  :key="goal.value"
                  @click="chooseGoalAndRecommend(goal.value)"
                  class="rounded-full border px-4 py-2 text-sm transition-colors"
                  :class="selectedGoals.includes(goal.value)
                    ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
                    : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-emerald-400'"
                >
                  {{ goal.label }}
                </button>
              </div>

              <div v-else-if="isActiveGuide(message) && mode === 'quick'" class="mt-4 space-y-3">
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="minutes in [15, 30, 45, 60]"
                    :key="minutes"
                    @click="chooseMinutesAndRecommend(minutes)"
                    class="rounded-full border px-4 py-2 text-sm transition-colors"
                    :class="maxMinutes === minutes
                      ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
                      : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-emerald-400'"
                  >
                    {{ minutes }} 分钟内
                  </button>
                </div>
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="tag in quickTags"
                    :key="tag.value"
                    @click="chooseTagAndRecommend(tag.value)"
                    class="rounded-full border px-3 py-1.5 text-xs transition-colors"
                    :class="selectedTags.includes(tag.value)
                      ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
                      : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-emerald-400'"
                  >
                    {{ tag.label }}
                  </button>
                </div>
              </div>

              <div v-else-if="isActiveGuide(message) && mode === 'explore'" class="mt-4 space-y-3">
                <div class="flex items-center gap-3">
                  <span class="text-sm text-gray-400">稳一点</span>
                  <input
                    v-model.number="exploration"
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    class="flex-1 accent-emerald-500"
                  />
                  <span class="text-sm text-gray-400">新奇一点</span>
                  <span class="w-12 text-right text-sm font-semibold text-emerald-300">{{ Math.round(exploration * 100) }}%</span>
                </div>
                <button @click="startScenarioRecommendation" class="rounded-full bg-primary-600 px-5 py-2 text-sm font-medium text-white">
                  开始探索
                </button>
              </div>
            </div>
            <div v-else-if="message.type === 'recommendations'" class="min-w-0 flex-1 rounded-2xl border border-slate-700 bg-slate-800 p-4 shadow-sm">
              <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <p class="text-base font-semibold text-gray-100">按「{{ message.modeLabel }}」给你整理了这些菜谱</p>
                  <p class="mt-1 text-xs leading-5 text-slate-400">
                    当前展示 {{ message.items.length }} 道，耗时 {{ message.tookMs }}ms。你可以继续追问“为什么推荐”或直接说“换一批”。
                  </p>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <span
                      v-for="item in message.understoodItems"
                      :key="`${item.label}-${item.value}`"
                      class="rounded-full bg-slate-900 px-3 py-1 text-xs text-slate-300"
                    >
                      {{ item.label }}：{{ item.value }}
                    </span>
                  </div>
                </div>
                <button
                  v-if="message.id === latestRecommendationMessageId"
                  @click="refreshBatch"
                  class="h-9 rounded-full border border-slate-700 px-4 text-xs text-slate-300 transition-colors hover:border-emerald-400"
                >
                  换一批
                </button>
              </div>

              <div v-if="message.items.length" class="mt-4 grid gap-4 lg:grid-cols-3">
                <RecommendationCard
                  v-for="(item, index) in message.items.slice(0, 3)"
                  :key="`${message.id}-hero-${item.movie_id}`"
                  :item="item"
                  :rank="index + 1"
                  :can-feedback="canSendFeedback"
                  :feedback-status="feedbackStatus[item.movie_id]"
                  :feedback-loading="isFeedbackLoading(item.movie_id)"
                  @feedback="sendFeedback(item, index, $event.type, $event.value)"
                />
              </div>

              <div v-if="message.items.length > 3" class="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <RecommendationCard
                  v-for="(item, index) in message.items.slice(3, 12)"
                  :key="`${message.id}-more-${item.movie_id}`"
                  :item="item"
                  :rank="index + 4"
                  :can-feedback="canSendFeedback"
                  :feedback-status="feedbackStatus[item.movie_id]"
                  :feedback-loading="isFeedbackLoading(item.movie_id)"
                  @feedback="sendFeedback(item, index + 3, $event.type, $event.value)"
                />
              </div>
              <p v-if="!message.items.length" class="mt-4 text-sm leading-6 text-slate-400">
                暂时没有推荐结果。你可以继续补充食材、时间或饮食目标，我会在同一段对话里重新整理。
              </p>
            </div>
          </div>

          <div v-if="feedbackNotice" class="order-2 flex justify-center">
            <div class="rounded-full border border-sky-500/30 bg-sky-950/30 px-4 py-2 text-xs text-sky-100">
              {{ feedbackNotice }}
            </div>
          </div>

          <div v-if="loading" class="order-2 flex justify-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-600 text-xs font-semibold text-white">
              AI
            </div>
            <div class="min-w-0 flex-1 rounded-2xl border border-slate-700 bg-slate-800 p-4">
              <div class="mb-3 h-4 w-48 animate-pulse rounded bg-gray-800"></div>
              <div class="grid gap-4 md:grid-cols-3">
                <div v-for="i in 3" :key="i" class="h-64 animate-pulse rounded-lg bg-gray-800"></div>
              </div>
            </div>
          </div>

          <div v-else-if="error" class="order-2 flex justify-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-600 text-xs font-semibold text-white">
              AI
            </div>
            <div class="max-w-[92%] rounded-2xl border border-red-500/30 bg-red-950/30 px-4 py-3 text-sm text-red-200 md:max-w-[86%] xl:max-w-[90%]">
              {{ error }}
            </div>
          </div>
        </div>

      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { getRecipeIngredients, getScenarioRecommendations, submitFeedback } from "../api";
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
              h("img", {
                src: cover,
                alt: title,
                class: "h-full w-full object-cover transition duration-300 group-hover:scale-105",
                loading: "lazy",
                onError: useFallbackImage,
              }),
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
const mode = ref(currentUser.value ? "personalized" : "quick");
const topK = ref(20);
const ingredientText = ref("");
const ingredientSuggestions = ref([]);
const ingredientLookupError = ref("");
const showIngredientSuggestions = ref(false);
const selectedGoals = ref([]);
const selectedTags = ref([]);
const maxMinutes = ref(30);
const hasTimeConstraint = ref(false);
const exploration = ref(0.55);
const requireImage = ref(true);
const recommendations = ref([]);
const loading = ref(false);
const error = ref(null);
const resultInfo = ref({ tookMs: 0, source: "" });
const feedbackStatus = ref({});
const feedbackLoading = ref({});
const feedbackNotice = ref("");
const hasStartedChat = ref(false);
const hasRequestedRecommendations = ref(false);
const chatInput = ref("");
const chatMessages = ref([
  {
    id: 1,
    role: "assistant",
    type: "text",
    content: "今天想吃什么？可以直接告诉我食材、时间或饮食目标。",
  },
]);
const activeGuideMessageId = ref(null);
const latestRecommendationMessageId = ref(null);
const dismissedIds = ref(new Set());
const likedIds = ref(new Set());
const batchPage = ref(0);
const autoFetchReady = ref(false);
let autoFetchTimer = null;
let noticeTimer = null;
let ingredientLookupTimer = null;
let ingredientLookupVersion = 0;
let requestVersion = 0;
let chatMessageId = 2;

const activeMode = computed(() => modes.find((item) => item.id === mode.value) || modes[0]);
const needsUser = computed(() => ["personalized", "explore"].includes(mode.value));
const userId = computed(() => currentUser.value?.user_id || null);
const canSendFeedback = computed(() => Boolean(userId.value));
const understoodItems = computed(() => {
  const items = [{ label: "场景", value: activeMode.value.label }];
  const ingredients = splitTerms(ingredientText.value).slice(0, 4).join("、");

  if (ingredients) items.push({ label: "食材", value: ingredients });
  if ((mode.value === "quick" || hasTimeConstraint.value) && maxMinutes.value) items.push({ label: "时间", value: `${maxMinutes.value} 分钟内` });
  if (selectedGoals.value.length) items.push({ label: "目标", value: selectedGoalLabels().join("、") });
  if (selectedTags.value.length) items.push({ label: "用餐", value: mealLabels(selectedTags.value).join("、") });
  if (mode.value === "explore") items.push({ label: "探索", value: `${Math.round(exploration.value * 100)}%` });
  if (requireImage.value && mode.value !== "personalized") items.push({ label: "图片", value: "优先有图" });

  return items;
});

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
const additionalItems = computed(() => displayedRecommendations.value.slice(3, 12));

function splitTerms(value) {
  return String(value || "")
    .split(/[;,，、|]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function lastIngredientDraft(value) {
  const parts = String(value || "").split(/[;,，、|]/);
  return (parts[parts.length - 1] || "").trim();
}

function toIngredientQueryTerms(value) {
  return splitTerms(value);
}

function addIngredient(value) {
  const current = splitTerms(ingredientText.value);
  if (!current.includes(value)) current.push(value);
  ingredientText.value = current.join("、");
  scheduleFetch(0);
}

function addIngredientDraft(value) {
  const current = splitTerms(ingredientText.value);
  if (!current.includes(value)) current.push(value);
  ingredientText.value = current.join("、");
  showIngredientSuggestions.value = true;
}

function scheduleIngredientLookup(delay = 180) {
  if (ingredientLookupTimer) clearTimeout(ingredientLookupTimer);
  ingredientLookupTimer = setTimeout(() => {
    ingredientLookupTimer = null;
    fetchIngredientSuggestions();
  }, delay);
}

async function fetchIngredientSuggestions() {
  const currentRequest = ++ingredientLookupVersion;
  const query = lastIngredientDraft(ingredientText.value);
  ingredientLookupError.value = "";
  try {
    const { data } = await getRecipeIngredients({ q: query, limit: 12 });
    if (currentRequest !== ingredientLookupVersion) return;
    ingredientSuggestions.value = data.ingredients || [];
  } catch (e) {
    if (currentRequest !== ingredientLookupVersion) return;
    ingredientLookupError.value = "食材联想暂时不可用，但仍可手动输入食材。";
    ingredientSuggestions.value = [];
  }
}

function toggleGoal(value) {
  if (selectedGoals.value.includes(value)) {
    selectedGoals.value = selectedGoals.value.filter((item) => item !== value);
  } else {
    selectedGoals.value = [...selectedGoals.value, value];
  }
  scheduleFetch(0);
}

function chooseGoalAndRecommend(value) {
  toggleGoal(value);
  appendChat("user", `我更关注「${goalLabels([value])[0]}」`);
  if (selectedGoals.value.length) fetchRecommendations();
}

function toggleTag(value) {
  if (selectedTags.value.includes(value)) {
    selectedTags.value = selectedTags.value.filter((item) => item !== value);
  } else {
    selectedTags.value = [...selectedTags.value, value];
  }
  scheduleFetch(0);
}

function chooseTagAndRecommend(value) {
  toggleTag(value);
  appendChat("user", `这餐按「${mealLabels([value])[0]}」来`);
  fetchRecommendations();
}

function selectMode(value) {
  const selected = modes.find((item) => item.id === value);
  const nextMode = value === "personalized" && !currentUser.value ? "quick" : value;
  hasStartedChat.value = true;
  mode.value = nextMode;
  clearRecommendationState();
  appendChat("user", `我想试试「${selected?.label || value}」`);
  if (value === "personalized") {
    fetchRecommendations();
  } else {
    appendGuideMessage(nextMode);
  }
}

function setMaxMinutes(value) {
  if (maxMinutes.value === value) {
    if (hasStartedChat.value) scheduleFetch(0);
    return;
  }
  maxMinutes.value = value;
  if (hasStartedChat.value) scheduleFetch(0);
}

function chooseMinutesAndRecommend(value) {
  hasTimeConstraint.value = true;
  setMaxMinutes(value);
  appendChat("user", `我想要 ${value} 分钟内做好`);
  fetchRecommendations();
}

function setTopK(value) {
  if (topK.value === value) {
    if (hasStartedChat.value) scheduleFetch(0);
    return;
  }
  topK.value = value;
  if (hasStartedChat.value) scheduleFetch(0);
}

function refreshBatch(appendUserMessage = true) {
  if (!recommendations.value.length) {
    fetchRecommendations();
    return;
  }
  if (appendUserMessage) appendChat("user", "换一批");
  batchPage.value += 1;
  appendRecommendationMessage(resultInfo.value.tookMs, resultInfo.value.source);
  showNotice("已切换到下一批候选菜谱。");
}

function startScenarioRecommendation() {
  if (mode.value === "ingredients") {
    const terms = splitTerms(ingredientText.value).join("、");
    if (terms) appendChat("user", `我有${terms}`);
  }
  fetchRecommendations();
}

function clearRecommendationState() {
  recommendations.value = [];
  error.value = null;
  hasRequestedRecommendations.value = false;
  feedbackStatus.value = {};
  feedbackLoading.value = {};
  dismissedIds.value = new Set();
  likedIds.value = new Set();
  batchPage.value = 0;
  resultInfo.value = { tookMs: 0, source: "" };
}

function askSuggestion(text) {
  chatInput.value = text;
  sendChat();
}

function sendChat() {
  const text = chatInput.value.trim();
  if (!text) return;
  hasStartedChat.value = true;
  appendChat("user", text);
  chatInput.value = "";

  const intent = parseChatIntent(text);
  if (intent.action === "explain") {
    appendChat("assistant", explainCurrentRecommendations());
    return;
  }
  if (intent.action === "refresh") {
    refreshBatch(false);
    appendChat("assistant", "已为你换一批候选菜谱。如果还想继续缩小范围，可以告诉我食材、时间或营养目标。");
    return;
  }

  applyChatIntent(intent);
  appendChat("assistant", buildChatReply(intent));
  scheduleFetch(0);
}

function appendChat(role, content, extra = {}) {
  const id = chatMessageId++;
  chatMessages.value = [
    ...chatMessages.value,
    {
      id,
      role,
      type: "text",
      content,
      ...extra,
    },
  ];
  return id;
}

function appendGuideMessage(value) {
  const id = appendChat("assistant", guideText(value), {
    type: "guide",
    mode: value,
    title: guideTitle(value),
  });
  activeGuideMessageId.value = id;
}

function appendRecommendationMessage(tookMs = 0, source = "") {
  const items = displayedRecommendations.value.map((item) => ({
    ...item,
    evidenceTags: [...(item.evidenceTags || [])],
    templateReason: item.templateReason || "",
  }));
  const id = appendChat("assistant", "", {
    type: "recommendations",
    mode: mode.value,
    modeLabel: activeMode.value.label,
    items,
    understoodItems: understoodItems.value.map((item) => ({ ...item })),
    tookMs,
    source,
  });
  latestRecommendationMessageId.value = id;
  activeGuideMessageId.value = null;
}

function isActiveGuide(message) {
  return message.id === activeGuideMessageId.value && message.mode === mode.value;
}

function guideTitle(value) {
  if (value === "ingredients") return "请告诉我冰箱里有什么食材";
  if (value === "healthy") return "你这餐更关注哪个饮食目标？";
  if (value === "quick") return "你希望多快做好？";
  if (value === "explore") return "想探索到什么程度？";
  return "我可以直接帮你选一批";
}

function guideText(value) {
  if (value === "ingredients") return "输入已有食材，或直接点下面的常用食材。我会优先找能围绕这些食材制作的菜谱。";
  if (value === "healthy") return "选择一个或多个目标后，我会按营养特征、评分和图片可用性重新推荐。";
  if (value === "quick") return "选择时间限制或用餐场景后，我会优先推荐制作步骤更短、耗时更可控的菜谱。";
  if (value === "explore") return "探索强度越高，系统越会加入与你历史口味不完全相同但仍可能喜欢的新菜谱。";
  return "如果你还不知道吃什么，我会结合历史偏好、多样性和评分稳定性给出一批候选。";
}

function parseChatIntent(text) {
  const normalized = text.toLowerCase();
  if (/(为什么|原因|解释|怎么推荐|推荐逻辑)/.test(text)) {
    return { action: "explain" };
  }
  if (/(换一批|换一些|重新来|刷新|不喜欢这批)/.test(text)) {
    return { action: "refresh" };
  }

  const ingredients = extractIngredients(text);
  const goals = extractDietaryGoals(text);
  const minutes = extractMinutes(text);
  const mealTags = extractMealTags(text);
  let scenario = "personalized";

  if (/(新口味|探索|不普通|不一样|惊喜|换个口味|没吃过)/.test(text)) scenario = "explore";
  if (minutes || /(快手|快速|简单|省事|赶时间|马上|半小时)/.test(text)) scenario = "quick";
  if (goals.length) scenario = "healthy";
  if (ingredients.length) scenario = "ingredients";
  if (/(随便|不知道|帮我选|推荐一下|吃什么)/.test(text) && !ingredients.length && !goals.length && !minutes) {
    scenario = "personalized";
  }
  const requestedScenario = scenario;
  if ((scenario === "personalized" || scenario === "explore") && !currentUser.value) {
    scenario = ingredients.length ? "ingredients" : goals.length ? "healthy" : "quick";
  }

  return {
    action: "recommend",
    scenario,
    ingredients,
    goals,
    minutes,
    mealTags,
    exploration: /(大胆|更不一样|新奇|惊喜)/.test(text) ? 0.75 : null,
    fallbackAuth: requestedScenario !== scenario,
    raw: normalized,
  };
}

function applyChatIntent(intent) {
  mode.value = intent.scenario;
  if (intent.ingredients.length) {
    ingredientText.value = intent.ingredients.join("、");
  }
  if (intent.goals.length) {
    selectedGoals.value = intent.goals;
  }
  if (intent.minutes) {
    maxMinutes.value = intent.minutes;
    hasTimeConstraint.value = true;
  }
  if (intent.mealTags.length) {
    selectedTags.value = intent.mealTags;
  }
  if (intent.exploration !== null) {
    exploration.value = intent.exploration;
  }
}

function buildChatReply(intent) {
  const parts = [];
  parts.push(`我已切换到「${scenarioLabel(intent.scenario)}」场景。`);
  if (intent.ingredients.length) parts.push(`会优先匹配食材：${intent.ingredients.join("、")}。`);
  if (intent.goals.length) parts.push(`营养目标：${goalLabels(intent.goals).join("、")}。`);
  if (intent.minutes) parts.push(`时间限制：${intent.minutes} 分钟内优先。`);
  if (intent.mealTags.length) parts.push(`用餐场景：${mealLabels(intent.mealTags).join("、")}。`);
  if (intent.fallbackAuth) {
    parts.push("你还没登录，我先用不依赖用户 ID 的冷启动场景帮你推荐。");
  }
  parts.push("我会按这个理解继续给你整理一批菜谱。");
  return parts.join("");
}

function explainCurrentRecommendations() {
  const latest = [...chatMessages.value].reverse().find((message) => message.type === "recommendations" && message.items?.length);
  const first = latest?.items?.[0];
  if (!first) {
    return "当前还没有可解释的推荐结果。你可以先告诉我想吃什么，或者选择一个场景。";
  }
  return `最近一轮推荐来自「${latest.modeLabel}」场景。系统先根据这轮对话生成候选，再结合评分、图片、时间、标签和多样性进行排序。比如「${recipeTitle(first)}」被放在前面，是因为它具备 ${(first.evidenceTags || []).join("、")} 等证据：${first.templateReason}`;
}

function extractIngredients(text) {
  const terms = [];
  for (const key of Object.keys(ingredientTermMap)) {
    if (text.includes(key)) terms.push(key);
  }
  return [...new Set(terms)];
}

function extractDietaryGoals(text) {
  const goals = [];
  if (/(健康|清淡)/.test(text)) goals.push("healthy");
  if (/(低热量|低卡|减脂|减肥|少热量)/.test(text)) goals.push("low-calorie");
  if (/(高蛋白|蛋白质)/.test(text)) goals.push("high-protein");
  if (/(低脂|少油|少脂肪)/.test(text)) goals.push("low-fat");
  if (/(低糖|少糖|控糖)/.test(text)) goals.push("low-sugar");
  if (/(低钠|少盐|低盐)/.test(text)) goals.push("low-sodium");
  return [...new Set(goals.length ? goals : [])];
}

function extractMinutes(text) {
  const match = text.match(/(\d{1,3})\s*分钟/);
  if (match) return Math.min(Math.max(Number(match[1]), 5), 120);
  if (/(半小时|30分钟|三十分钟)/.test(text)) return 30;
  if (/(一刻钟|15分钟|十五分钟)/.test(text)) return 15;
  return null;
}

function extractMealTags(text) {
  const tags = [];
  if (text.includes("早餐")) tags.push("breakfast");
  if (text.includes("午餐")) tags.push("lunch");
  if (text.includes("晚餐") || text.includes("晚饭")) tags.push("dinner");
  if (text.includes("小吃") || text.includes("零食")) tags.push("snacks");
  return [...new Set(tags)];
}

function scenarioLabel(value) {
  return modes.find((item) => item.id === value)?.label || value;
}

function goalLabels(values) {
  const labels = new Map(dietaryGoals.map((goal) => [goal.value, goal.label]));
  return values.map((value) => labels.get(value) || value);
}

function mealLabels(values) {
  const labels = new Map(quickTags.map((tag) => [tag.value, tag.label]));
  return values.map((value) => labels.get(value) || value);
}

function scheduleFetch(delay = 300) {
  if (!autoFetchReady.value || !hasStartedChat.value) return;
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
    if (hasTimeConstraint.value && maxMinutes.value) payload.max_minutes = maxMinutes.value;
    if (selectedTags.value.length) payload.preferred_tags = selectedTags.value;
    if (selectedGoals.value.length) payload.dietary_goals = selectedGoals.value;
  }
  if (mode.value === "healthy") {
    payload.dietary_goals = selectedGoals.value;
    if (hasTimeConstraint.value && maxMinutes.value) payload.max_minutes = maxMinutes.value;
    if (selectedTags.value.length) payload.preferred_tags = selectedTags.value;
    if (splitTerms(ingredientText.value).length) payload.ingredients = toIngredientQueryTerms(ingredientText.value);
  }
  if (mode.value === "quick") {
    payload.max_minutes = maxMinutes.value;
    payload.preferred_tags = selectedTags.value;
    if (splitTerms(ingredientText.value).length) payload.ingredients = toIngredientQueryTerms(ingredientText.value);
    if (selectedGoals.value.length) payload.dietary_goals = selectedGoals.value;
  }
  if (mode.value === "explore") {
    payload.exploration = exploration.value;
  }

  return payload;
}

async function fetchRecommendations() {
  hasStartedChat.value = true;
  hasRequestedRecommendations.value = true;
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
    appendRecommendationMessage(resultInfo.value.tookMs, resultInfo.value.source);
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

function numberValue(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "" && !Number.isNaN(Number(value))) {
      return Number(value);
    }
  }
  return null;
}

function useFallbackImage(event) {
  if (event.currentTarget.src.endsWith("/recipe-covers/default.png")) return;
  event.currentTarget.src = "/recipe-covers/default.png";
}

watch(mode, () => {
  error.value = null;
  feedbackStatus.value = {};
  feedbackLoading.value = {};
  if (mode.value === "ingredients") {
    showIngredientSuggestions.value = true;
    scheduleIngredientLookup(0);
  }
});

watch(ingredientText, () => {
  if (mode.value !== "ingredients") return;
  showIngredientSuggestions.value = true;
  scheduleIngredientLookup();
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
  if (mode.value === "ingredients") {
    scheduleIngredientLookup(0);
  }
});

onUnmounted(() => {
  if (autoFetchTimer) clearTimeout(autoFetchTimer);
  if (noticeTimer) clearTimeout(noticeTimer);
  if (ingredientLookupTimer) clearTimeout(ingredientLookupTimer);
  window.removeEventListener("storage", syncCurrentUser);
  window.removeEventListener("reciperec:user-changed", syncCurrentUser);
});
</script>
