<template>
  <div class="mx-auto max-w-[1600px] space-y-6 px-2 md:px-4">
    <section class="overflow-hidden rounded-2xl border border-slate-700 bg-slate-900 shadow-lg shadow-black/20">
      <div class="border-b border-slate-700 px-5 py-5 md:px-8 md:py-6">
        <p class="text-sm font-medium text-emerald-300">智能对话推荐</p>
        <h1 class="mt-1 text-3xl font-bold text-gray-100">DeepSeek + 知识图谱食谱助手</h1>
        <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
          直接告诉系统你的口味、食材、热量目标或做饭时间，系统会结合知识图谱与大语言模型给出推荐摘要、推荐理由和候选菜谱卡片。
        </p>
      </div>

      <div class="p-3 md:p-4 lg:p-6">
        <div class="mx-auto flex h-[calc(100vh-190px)] min-h-[760px] w-full max-w-[1300px] flex-col rounded-2xl border border-slate-700 bg-slate-950/60">
          <div ref="messageListRef" class="flex-1 space-y-4 overflow-y-auto p-4 md:p-5">
            <div v-for="msg in messages" :key="msg.id" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
              <div v-if="msg.role === 'assistant'" class="mr-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary-600 text-xs font-semibold text-white">AI</div>
              <div class="max-w-[92%] rounded-2xl border px-4 py-3 text-sm leading-6 shadow-sm md:max-w-[85%]" :class="msg.role === 'user' ? 'border-slate-700 bg-primary-600 text-white' : 'border-slate-700 bg-slate-800 text-slate-200'">
                <p class="whitespace-pre-wrap">{{ msg.content }}</p>
                <div v-if="msg.recommendations && msg.recommendations.length" class="mt-4 space-y-4">
                  <div v-for="item in msg.recommendations" :key="item.recipe_id" class="overflow-hidden rounded-xl border border-slate-700 bg-slate-900">
                    <div class="grid gap-0 md:grid-cols-[180px_1fr]">
                      <div class="relative h-44 overflow-hidden bg-slate-800 md:h-full">
                        <img v-if="item.image_url" :src="item.image_url" :alt="item.title" class="h-full w-full object-cover" />
                        <div v-else class="flex h-full w-full items-center justify-center text-xs text-slate-500">暂无图片</div>
                        <div class="absolute left-3 top-3 rounded-full bg-black/60 px-2 py-1 text-xs text-white">{{ item.rank ? `#${item.rank}` : '推荐' }}</div>
                      </div>
                      <div class="p-4">
                        <div class="flex items-start justify-between gap-3">
                          <div>
                            <h3 class="text-base font-semibold text-gray-100">{{ item.title }}</h3>
                            <p class="mt-1 text-xs text-slate-500">Recipe ID: {{ item.recipe_id }}</p>
                          </div>
                          <span class="shrink-0 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-200">
                            {{ Number(item.score || 0).toFixed(4) }}
                          </span>
                        </div>

                        <div class="mt-3 flex flex-wrap gap-2 text-xs text-slate-300">
                          <span v-if="item.ready_in_display" class="rounded-full bg-slate-800 px-3 py-1">{{ item.ready_in_display }}</span>
                          <span v-if="item.avg_rating" class="rounded-full bg-slate-800 px-3 py-1">评分 {{ item.avg_rating }}</span>
                          <span v-if="item.rating_count" class="rounded-full bg-slate-800 px-3 py-1">{{ item.rating_count }} 评价</span>
                        </div>

                        <div v-if="item.match_points && item.match_points.length" class="mt-3 flex flex-wrap gap-2">
                          <span v-for="tag in item.match_points" :key="tag" class="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">{{ tag }}</span>
                        </div>

                        <div class="mt-4 rounded-lg border border-slate-700 bg-slate-950/60 p-3">
                          <p class="text-xs font-medium uppercase tracking-wide text-emerald-300">推荐理由</p>
                          <p class="mt-2 text-sm leading-6 text-slate-300">{{ item.reason }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="loading" class="flex justify-start">
              <div class="mr-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary-600 text-xs font-semibold text-white">AI</div>
              <div class="rounded-2xl border border-slate-700 bg-slate-800 px-4 py-3 text-sm text-slate-300">正在帮你整理更合适的菜谱推荐...</div>
            </div>
          </div>

          <div class="border-t border-slate-700 p-4 md:p-5">
            <form class="flex flex-col gap-3 md:flex-row" @submit.prevent="sendMessage">
              <textarea v-model.trim="input" rows="2" placeholder="例如：推荐一些低卡高蛋白的鸡肉菜" class="min-h-[52px] flex-1 resize-none rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-gray-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
              <button type="submit" :disabled="!input || loading" class="rounded-xl bg-primary-600 px-6 py-3 text-sm font-medium text-white transition hover:bg-primary-500 disabled:cursor-not-allowed disabled:bg-slate-600">
                发送
              </button>
            </form>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { chatRecommend } from "../api/chat_recommend";
import { getCurrentUser } from "../utils/session";
import { recipeImage, recipeTitle } from "../utils/recipeCover";

const route = useRoute();
const input = ref("推荐一些低卡高蛋白的鸡肉菜");
const loading = ref(false);
const statusText = ref("准备就绪");
const messageListRef = ref(null);
const messages = ref([
  {
    id: 1,
    role: "assistant",
    content: "你好，我可以帮你找更合适的菜谱。你可以直接告诉我口味、食材、时间或营养目标，我会帮你整理推荐。",
  },
]);
const samples = [
  "推荐一些低卡高蛋白的鸡肉菜",
  "我想要 30 分钟内能做完的晚餐",
  "给我找几个适合减脂的快手菜",
  "推荐一些素食、健康、好做的菜谱",
];

const scrollToBottom = async () => {
  await nextTick();
  const el = messageListRef.value;
  if (el) el.scrollTop = el.scrollHeight;
};

const normalizeItem = (item = {}) => ({
  ...item,
  title: item.title || item.name || recipeTitle(item),
  image_url: recipeImage({
    ...item,
    movie_id: item.movie_id || item.recipe_id,
    movieId: item.movieId || item.recipe_id,
    genres: item.genres || item.tags || "",
  }),
  reason: item.reason || item.final_reason || "这道菜和你的需求比较匹配。",
  match_points: Array.isArray(item.match_points) ? item.match_points : [],
});

const sendMessage = async () => {
  if (!input.value || loading.value) return;
  const userText = input.value;
  const user = getCurrentUser();
  const userId = Number(route.params.userId || user?.user_id || 1);
  messages.value.push({ id: Date.now(), role: "user", content: userText });
  input.value = "";
  loading.value = true;
  statusText.value = "正在调用 DeepSeek + 知识图谱...";
  await scrollToBottom();

  try {
    const { data } = await chatRecommend({ user_id: userId, message: userText });
    messages.value.push({
      id: Date.now() + 1,
      role: "assistant",
      content: data.summary || "已生成推荐结果。",
      recommendations: (data.recommendations || []).map((item, index) => ({ ...normalizeItem(item), rank: index + 1 })),
    });
    statusText.value = data.llm_enabled ? "DeepSeek 已启用" : "当前使用规则兜底模式";
  } catch (error) {
    messages.value.push({
      id: Date.now() + 1,
      role: "assistant",
      content: `请求失败：${error?.response?.data?.detail || error.message || "未知错误"}`,
    });
    statusText.value = "请求失败，请稍后重试";
  } finally {
    loading.value = false;
    await scrollToBottom();
  }
};

onMounted(async () => {
  await scrollToBottom();
});
</script>
