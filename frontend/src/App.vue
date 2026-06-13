<template>
  <div class="min-h-screen bg-gray-900">
    <NavBar />
    <main class="mx-auto max-w-[1440px] px-4 pb-12 pt-5 md:px-6 md:pb-16 md:pt-6">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import NavBar from "./components/NavBar.vue";
</script>
