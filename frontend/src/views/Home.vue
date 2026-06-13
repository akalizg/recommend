<template>
  <div class="space-y-16">
    <section class="grid min-h-[520px] items-center gap-10 py-8 lg:grid-cols-[1.05fr_0.95fr]">
      <div>
        <p class="mb-4 text-xs font-semibold uppercase tracking-[0.08em] text-gray-500">Food.com Recipe Intelligence</p>
        <h1 class="max-w-4xl text-5xl leading-[1.05] text-gray-100 md:text-6xl">
          像和助手聊天一样，找到今天真正想吃的菜。
        </h1>
        <p class="mt-6 max-w-2xl text-base leading-7 text-gray-400">
          系统把 Food.com 的食谱、交互、营养、图片和向量召回组织成一个中文对话式推荐体验，支持食材、健康、快手和探索发现等场景。
        </p>
        <div class="mt-8 flex flex-wrap gap-3">
          <router-link
            to="/recommend"
            class="rounded-full bg-primary-600 px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-primary-500"
          >
            开始对话推荐
          </router-link>
          <router-link
            to="/search"
            class="rounded-full border border-slate-700 px-5 py-3 text-sm font-medium text-gray-100 transition-colors hover:border-slate-500"
          >
            搜索菜谱库
          </router-link>
        </div>
      </div>

      <div class="rounded-[24px] border border-slate-700 bg-slate-900 p-6 shadow-lg">
        <div class="space-y-4">
          <div class="rounded-xl border border-slate-700 bg-slate-800 p-4">
            <p class="text-xs font-semibold uppercase tracking-[0.08em] text-gray-500">User request</p>
            <p class="mt-2 text-lg text-gray-100">我有鸡肉和土豆，想做 30 分钟内的高蛋白晚餐。</p>
          </div>
          <div class="rounded-xl border border-slate-700 bg-slate-800 p-4">
            <p class="text-xs font-semibold uppercase tracking-[0.08em] text-gray-500">Assistant</p>
            <p class="mt-2 text-sm leading-6 text-gray-400">
              已切换到食材场景，并加入快手和高蛋白目标。系统会先召回候选，再用排序模型和模板理由解释每道菜为什么适合你。
            </p>
          </div>
          <div class="grid grid-cols-3 gap-3 text-center">
            <div class="rounded-xl border border-slate-700 bg-slate-800 p-4">
              <div class="text-2xl text-primary-400">178K</div>
              <div class="mt-1 text-xs text-gray-400">菜谱</div>
            </div>
            <div class="rounded-xl border border-slate-700 bg-slate-800 p-4">
              <div class="text-2xl text-primary-400">25K</div>
              <div class="mt-1 text-xs text-gray-400">用户</div>
            </div>
            <div class="rounded-xl border border-slate-700 bg-slate-800 p-4">
              <div class="text-2xl text-primary-400">0.980</div>
              <div class="mt-1 text-xs text-gray-400">AUC</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <PopularMovies :limit="20" />

    <section class="space-y-5">
      <div>
        <p class="text-xs font-semibold uppercase tracking-[0.08em] text-gray-500">System stack</p>
        <h2 class="mt-2 text-4xl text-gray-100">推荐链路</h2>
      </div>
      <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div v-for="item in stackItems" :key="item.name" class="rounded-xl border border-slate-700 bg-gray-800 p-5">
          <div class="text-base font-medium text-gray-100">{{ item.name }}</div>
          <p class="mt-2 text-sm leading-6 text-gray-400">{{ item.desc }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import PopularMovies from "../components/PopularMovies.vue";

const stackItems = [
  { name: "Spark 离线批处理", desc: "生成用户画像、食谱画像、召回候选和排序特征。" },
  { name: "FAISS + LightGCN", desc: "支持相似食谱和图召回，让推荐不止依赖热门结果。" },
  { name: "LightGBM 排序", desc: "在多路召回基础上选择更适合当前用户和场景的菜谱。" },
  { name: "对话式前端", desc: "把食材、健康、时间和探索需求解析成可执行的推荐参数。" },
];
</script>
