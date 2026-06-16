<template>
  <div class="space-y-6">
    <section class="rounded-lg border border-slate-700 bg-slate-900 p-5">
      <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p class="text-sm font-medium text-emerald-300">Taste Twin</p>
          <h1 class="mt-1 text-3xl font-bold text-gray-100">我的记录</h1>
          <p class="mt-2 text-sm text-slate-400">这里保留饭搭子收藏，也展示之前的喜欢、讨厌、避雷和评分记录；你可以手动删除并同步数据。</p>
        </div>
        <router-link to="/taste-twin" class="rounded-full border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:border-emerald-400">
          返回饭搭子
        </router-link>
      </div>

      <div class="mt-5 flex flex-wrap gap-2">
        <button
          v-for="item in filters"
          :key="item.value"
          class="rounded-full border px-4 py-2 text-sm transition-colors"
          :class="recordType === item.value ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100' : 'border-slate-700 bg-slate-800 text-slate-300 hover:border-emerald-400'"
          @click="setFilter(item.value)"
        >
          {{ item.label }}
        </button>
      </div>
    </section>

    <section v-if="!currentUser" class="rounded-lg border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-100">
      请先登录后查看记录。
    </section>

    <section v-else-if="loading" class="grid min-h-[240px] place-items-center rounded-lg border border-dashed border-slate-700 bg-slate-900">
      <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-700 border-t-emerald-400"></div>
    </section>

    <section v-else-if="error" class="rounded-lg border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-100">
      {{ error }}
    </section>

    <section v-else class="rounded-lg border border-slate-700 bg-slate-900 p-5">
      <div class="flex items-center justify-between">
        <p class="text-sm text-slate-400">共 {{ total }} 条</p>
        <div class="flex items-center gap-2">
          <button class="rounded-full border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:cursor-not-allowed disabled:text-slate-500" :disabled="page <= 1 || loading" @click="loadRecords(page - 1)">
            上一页
          </button>
          <span class="text-sm text-slate-400">第 {{ page }} 页</span>
          <button class="rounded-full border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:cursor-not-allowed disabled:text-slate-500" :disabled="!hasMore || loading" @click="loadRecords(page + 1)">
            下一页
          </button>
        </div>
      </div>

      <div v-if="records.length" class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div v-for="record in records" :key="record.id" class="space-y-2">
          <MovieCard :movie="record.recipe">
            <div class="absolute inset-x-2 bottom-2 rounded-md border border-emerald-300/40 bg-slate-900/70 px-2.5 py-2 shadow-lg shadow-black/40 backdrop-blur-md ring-1 ring-white/10">
              <div class="flex items-center justify-between gap-2">
                <span class="rounded bg-emerald-300 px-2 py-0.5 text-xs font-semibold text-slate-950 shadow-sm">{{ recordTag(record) }}</span>
                <span class="shrink-0 rounded bg-slate-950/55 px-1.5 py-0.5 text-[11px] font-medium text-slate-50">{{ dateText(record.created_at) }}</span>
              </div>
            </div>
          </MovieCard>
          <div>
            <button
              class="w-full rounded-full bg-slate-700 px-3 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-slate-600 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-400"
              :disabled="deletingId === record.id"
              @click="deleteRecord(record)"
            >
              {{ deletingId === record.id ? "正在同步..." : cancelActionText(record) }}
            </button>
          </div>
        </div>
      </div>
      <p v-else class="mt-4 rounded-lg border border-slate-700 p-4 text-sm text-slate-400">暂无记录。</p>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import MovieCard from "../components/MovieCard.vue";
import { deleteTasteTwinRecord, getTasteTwinRecords } from "../api";
import { getCurrentUser } from "../utils/session";

const filters = [
  { label: "全部", value: "all" },
  { label: "收藏", value: "collection" },
  { label: "喜欢", value: "like" },
  { label: "不喜欢", value: "dislike" },
  { label: "避雷", value: "not_interested" },
  { label: "评分", value: "rating" },
];

const currentUser = ref(getCurrentUser());
const records = ref([]);
const recordType = ref("all");
const page = ref(1);
const total = ref(0);
const hasMore = ref(false);
const loading = ref(false);
const error = ref("");
const deletingId = ref("");

function dateText(value) {
  if (!value) return "";
  return String(value).replace("T", " ").slice(0, 16);
}

function recordTag(record) {
  if (record.record_type === "rating" && record.feedback_value) return `评分 ${record.feedback_value}`;
  return record.label;
}

function cancelActionText(record) {
  return `取消${record.label}`;
}

async function loadRecords(nextPage = 1) {
  if (!currentUser.value?.user_id) return;
  loading.value = true;
  error.value = "";
  try {
    const { data } = await getTasteTwinRecords(currentUser.value.user_id, recordType.value, nextPage, 12);
    records.value = data.records || [];
    page.value = data.page;
    total.value = data.total;
    hasMore.value = data.has_more;
  } catch (err) {
    error.value = err?.response?.data?.detail || "加载记录失败";
  } finally {
    loading.value = false;
  }
}

async function deleteRecord(record) {
  if (!currentUser.value?.user_id) return;
  deletingId.value = record.id;
  error.value = "";
  try {
    await deleteTasteTwinRecord(currentUser.value.user_id, record.id);
    const nextPage = records.value.length === 1 && page.value > 1 ? page.value - 1 : page.value;
    await loadRecords(nextPage);
  } catch (err) {
    error.value = err?.response?.data?.detail || "同步记录失败";
  } finally {
    deletingId.value = "";
  }
}

function setFilter(value) {
  recordType.value = value;
  loadRecords(1);
}

onMounted(() => loadRecords());
</script>
