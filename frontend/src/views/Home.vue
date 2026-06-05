<template>
  <div class="space-y-8">
    <!-- Hero -->
    <div class="text-center py-12">
      <h1 class="text-4xl font-bold text-gray-100 mb-3">
        MovieRec
      </h1>
      <p class="text-gray-400 text-lg mb-6">
        AI-powered movie recommendations using FAISS HNSW + XGBoost
      </p>
      <div class="flex justify-center gap-4">
        <router-link
          to="/recommend"
          class="px-6 py-2.5 bg-primary-600 hover:bg-primary-500 rounded-lg text-white font-medium transition-colors"
        >
          Get Recommendations
        </router-link>
        <router-link
          to="/search"
          class="px-6 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-gray-200 font-medium transition-colors"
        >
          Search Movies
        </router-link>
      </div>
    </div>

    <!-- Stats Bar -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-gray-800 rounded-xl p-4 text-center">
        <div class="text-2xl font-bold text-primary-400">9,742</div>
        <div class="text-xs text-gray-400 mt-1">Movies</div>
      </div>
      <div class="bg-gray-800 rounded-xl p-4 text-center">
        <div class="text-2xl font-bold text-primary-400">610</div>
        <div class="text-xs text-gray-400 mt-1">Users</div>
      </div>
      <div class="bg-gray-800 rounded-xl p-4 text-center">
        <div class="text-2xl font-bold text-primary-400">100K+</div>
        <div class="text-xs text-gray-400 mt-1">Ratings</div>
      </div>
      <div class="bg-gray-800 rounded-xl p-4 text-center">
        <div class="text-2xl font-bold text-primary-400">&lt;50ms</div>
        <div class="text-xs text-gray-400 mt-1">Recall Speed</div>
      </div>
    </div>

    <!-- Popular Movies -->
    <PopularMovies :limit="20" />

    <!-- Tech Stack -->
    <div class="bg-gray-800 rounded-xl p-6">
      <h2 class="text-lg font-bold text-gray-100 mb-4">Tech Stack</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">FastAPI</div>
          <div class="text-gray-400 text-xs mt-0.5">REST API</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">FAISS + HNSW</div>
          <div class="text-gray-400 text-xs mt-0.5">ANN Retrieval</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">XGBoost</div>
          <div class="text-gray-400 text-xs mt-0.5">Ranking Model</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">Redis</div>
          <div class="text-gray-400 text-xs mt-0.5">Cache Layer</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">Matrix Factorization</div>
          <div class="text-gray-400 text-xs mt-0.5">Embeddings</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">MovieLens</div>
          <div class="text-gray-400 text-xs mt-0.5">Dataset</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">Vue 3</div>
          <div class="text-gray-400 text-xs mt-0.5">Frontend</div>
        </div>
        <div class="bg-gray-700/50 rounded-lg p-3">
          <div class="text-primary-400 font-semibold">Docker</div>
          <div class="text-gray-400 text-xs mt-0.5">Deployment</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import PopularMovies from "../components/PopularMovies.vue";
</script>
