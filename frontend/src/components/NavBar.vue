<template>
  <nav class="sticky top-0 z-50 border-b border-gray-700 bg-gray-800/95 backdrop-blur">
    <div class="mx-auto max-w-[1200px] px-4 md:px-6">
      <div class="flex h-16 items-center justify-between">
        <router-link to="/" class="flex items-center">
          <img src="/logo.png" alt="今天吃什么？" class="h-10 w-auto object-contain" />
        </router-link>

        <div class="hidden items-center gap-6 text-sm md:flex">
          <router-link to="/" class="text-gray-300 hover:text-white transition-colors">首页</router-link>
          <router-link to="/recommend" class="text-emerald-300 hover:text-emerald-200 transition-colors font-medium">智能推荐</router-link>
          <router-link to="/search" class="text-gray-300 hover:text-white transition-colors">搜索</router-link>
          <router-link to="/taste-twin" class="text-gray-300 hover:text-white transition-colors">饭搭子</router-link>
        </div>

        <div class="hidden items-center gap-3 text-sm md:flex">
          <div v-if="currentUser" class="text-right">
            <div class="font-medium text-gray-200">{{ currentUser.display_name || currentUser.username }}</div>
            <div class="text-xs text-gray-500">食谱用户 {{ currentUser.user_id }}</div>
          </div>
          <router-link
            v-if="!currentUser"
            to="/login"
            class="rounded-full bg-primary-600 px-4 py-2 font-medium text-white transition-colors hover:bg-primary-500"
          >
            登录
          </router-link>
          <button
            v-else
            @click="logout"
            class="rounded-full border border-slate-700 px-4 py-2 text-slate-300 transition-colors hover:border-slate-500"
          >
            退出
          </button>
        </div>

        <button @click="mobileOpen = !mobileOpen" class="md:hidden text-gray-300 hover:text-white">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path v-if="!mobileOpen" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div v-if="mobileOpen" class="md:hidden pb-3 space-y-2">
        <router-link to="/" class="block py-2 text-gray-300 hover:text-white" @click="mobileOpen = false">首页</router-link>
        <router-link to="/recommend" class="block py-2 text-emerald-300 hover:text-emerald-200 font-medium" @click="mobileOpen = false">智能推荐</router-link>
        <router-link to="/search" class="block py-2 text-gray-300 hover:text-white" @click="mobileOpen = false">搜索</router-link>
        <router-link to="/taste-twin" class="block py-2 text-gray-300 hover:text-white" @click="mobileOpen = false">饭搭子</router-link>
        <router-link v-if="!currentUser" to="/login" class="block py-2 text-gray-300 hover:text-white" @click="mobileOpen = false">登录</router-link>
        <button v-else class="block py-2 text-left text-gray-300 hover:text-white" @click="logout">退出 {{ currentUser.display_name || currentUser.username }}</button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { clearCurrentUser, getCurrentUser } from "../utils/session";

const mobileOpen = ref(false);
const currentUser = ref(getCurrentUser());
const router = useRouter();

function syncUser() {
  currentUser.value = getCurrentUser();
}

function logout() {
  clearCurrentUser();
  currentUser.value = null;
  mobileOpen.value = false;
  router.push("/login");
}

onMounted(() => {
  window.addEventListener("storage", syncUser);
  window.addEventListener("reciperec:user-changed", syncUser);
});

onUnmounted(() => {
  window.removeEventListener("storage", syncUser);
  window.removeEventListener("reciperec:user-changed", syncUser);
});
</script>
