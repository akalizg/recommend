<template>
  <div class="space-y-8">
    <div class="text-center py-12">
      <h1 class="text-4xl font-bold text-gray-100 mb-3">
        食谱推荐系统
      </h1>
      <p class="text-gray-400 text-lg mb-6">
        基于 Food.com 数据集的智能食谱推荐平台，支持个性化推荐、冰箱食材、健康饮食、快手菜和探索发现等场景
      </p>
      <div class="flex justify-center gap-4">
        <router-link
          to="/recommend"
          class="px-6 py-2.5 bg-primary-600 hover:bg-primary-500 rounded-lg text-white font-medium transition-colors"
        >
          打开推荐
        </router-link>
        <router-link
          to="/search"
          class="px-6 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-gray-200 font-medium transition-colors"
        >
          搜索菜谱
        </router-link>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-gray-800 rounded-xl p-4 text-center">
        <div class="text-2xl font-bold text-primary-400">178K</div>
        <div class="text-xs text-gray-400 mt-1">菜谱规模</div>
      </div>
      <div class="bg-gray-800 rounded-xl p-4 text-center">
        <div class="text-2xl font-bold text-primary-400">25K</div>
        <div class="text-xs text-gray-400 mt-1">用户规模</div>
      </div>
      <div class="bg-gray-800 rounded-xl p-4 text-center">
        <div class="text-2xl font-bold text-primary-400">250K</div>
        <div class="text-xs text-gray-400 mt-1">最终推荐结果</div>
      </div>
      <div class="bg-gray-800 rounded-xl p-4 text-center">
        <div class="text-2xl font-bold text-primary-400">0.980</div>
        <div class="text-xs text-gray-400 mt-1">排序模型 AUC</div>
      </div>
    </div>

    <PopularMovies :limit="20" />

    <div class="bg-gray-800 rounded-xl p-6">
      <h2 class="text-lg font-bold text-gray-100 mb-4">技术栈</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">FastAPI</div>
          <div class="text-gray-400 text-xs mt-0.5">后端接口</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">Spark</div>
          <div class="text-gray-400 text-xs mt-0.5">离线批处理</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">FAISS + HNSW</div>
          <div class="text-gray-400 text-xs mt-0.5">相似菜谱召回</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">LightGBM</div>
          <div class="text-gray-400 text-xs mt-0.5">主排序模型</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">Redis</div>
          <div class="text-gray-400 text-xs mt-0.5">缓存层</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">Elasticsearch</div>
          <div class="text-gray-400 text-xs mt-0.5">菜谱搜索</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">Vue 3</div>
          <div class="text-gray-400 text-xs mt-0.5">前端页面</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">Food.com</div>
          <div class="text-gray-400 text-xs mt-0.5">实验数据集</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import PopularMovies from "../components/PopularMovies.vue";
</script>

