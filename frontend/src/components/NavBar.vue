<template>
  <nav class="bg-gray-800 border-b border-gray-700 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4">
      <div class="flex items-center justify-between h-14">
        <!-- Logo -->
        <router-link to="/" class="flex items-center gap-2 text-primary-400 font-bold text-lg">
          <span>RecipeRec</span>
        </router-link>

        <!-- Links -->
        <div class="flex items-center gap-6 text-sm">
          <router-link to="/" class="text-gray-300 hover:text-white transition-colors">
            Home
          </router-link>
          <router-link to="/recommend" class="text-gray-300 hover:text-white transition-colors">
            Recipes
          </router-link>
          <router-link to="/search" class="text-gray-300 hover:text-white transition-colors">
            Search
          </router-link>
        </div>

        <!-- Mobile menu button -->
        <button
          @click="mobileOpen = !mobileOpen"
          class="md:hidden text-gray-300 hover:text-white"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path v-if="!mobileOpen" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M4 6h16M4 12h16M4 18h16" />
            <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Mobile menu -->
      <div v-if="mobileOpen" class="md:hidden pb-3 space-y-2">
        <router-link to="/" class="block py-2 text-gray-300 hover:text-white" @click="mobileOpen = false">
          Home
        </router-link>
        <router-link to="/recommend" class="block py-2 text-gray-300 hover:text-white" @click="mobileOpen = false">
          Recipes
        </router-link>
        <router-link to="/search" class="block py-2 text-gray-300 hover:text-white" @click="mobileOpen = false">
          Search
        </router-link>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref } from "vue";

const mobileOpen = ref(false);
</script>

