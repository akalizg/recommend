<template>
  <div class="mx-auto max-w-md space-y-5">
    <div>
      <h1 class="text-2xl font-bold text-gray-100">{{ isRegister ? "创建账号" : "登录" }}</h1>
      <p class="mt-2 text-sm text-gray-400">
        使用本地演示账号绑定稳定的 Food.com 用户，用于个性化推荐和反馈闭环。
      </p>
    </div>

    <div class="rounded-lg border border-slate-700 bg-slate-900 p-5 shadow-lg shadow-black/20">
      <div class="mb-4 grid grid-cols-2 gap-2">
        <button @click="isRegister = false" class="h-9 rounded-lg border text-sm transition-colors" :class="!isRegister ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100' : 'border-slate-700 bg-slate-800 text-slate-300'">登录</button>
        <button @click="isRegister = true" class="h-9 rounded-lg border text-sm transition-colors" :class="isRegister ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100' : 'border-slate-700 bg-slate-800 text-slate-300'">注册</button>
      </div>

      <form class="space-y-4" @submit.prevent="submit">
        <label class="block">
          <span class="mb-1 block text-sm text-gray-400">用户名</span>
          <input v-model.trim="username" type="text" autocomplete="username" class="h-10 w-full rounded-lg border border-gray-600 bg-gray-800 px-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </label>

        <label class="block">
          <span class="mb-1 block text-sm text-gray-400">密码</span>
          <input v-model="password" type="password" autocomplete="current-password" class="h-10 w-full rounded-lg border border-gray-600 bg-gray-800 px-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </label>

        <label v-if="isRegister" class="block">
          <span class="mb-1 block text-sm text-gray-400">显示名称</span>
          <input v-model.trim="displayName" type="text" class="h-10 w-full rounded-lg border border-gray-600 bg-gray-800 px-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </label>

        <label v-if="isRegister" class="block">
          <span class="mb-1 block text-sm text-gray-400">Food.com 用户 ID</span>
          <input v-model.number="recipeUserId" type="number" min="1" class="h-10 w-full rounded-lg border border-gray-600 bg-gray-800 px-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </label>

        <div v-if="isRegister" class="flex flex-wrap gap-2">
          <button v-for="uid in demoUsers" :key="uid" type="button" @click="recipeUserId = uid" class="rounded px-2 py-1 text-xs transition-colors" :class="recipeUserId === uid ? 'bg-primary-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'">{{ uid }}</button>
        </div>

        <button type="submit" :disabled="loading" class="h-10 w-full rounded-lg bg-primary-600 font-medium text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:bg-gray-600">
          {{ loading ? "请稍候..." : isRegister ? "创建并登录" : "登录" }}
        </button>
      </form>

      <div v-if="error" class="mt-4 rounded border border-red-500/30 bg-red-950/30 px-3 py-2 text-sm text-red-200">{{ error }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { loginUser, registerUser } from "../api";
import { setCurrentUser } from "../utils/session";

const demoUsers = [1535, 2310, 2312, 3288, 4291, 4439, 4470, 5060, 6258, 6357, 6546, 8688];
const router = useRouter();
const isRegister = ref(false);
const username = ref("");
const password = ref("");
const displayName = ref("");
const recipeUserId = ref(demoUsers[0]);
const loading = ref(false);
const error = ref(null);

async function submit() {
  error.value = null;
  if (!username.value || password.value.length < 6) {
    error.value = "请输入用户名，并确保密码至少 6 位";
    return;
  }

  loading.value = true;
  try {
    const payload = { username: username.value, password: password.value };
    const { data } = isRegister.value
      ? await registerUser({ ...payload, display_name: displayName.value || username.value, recipe_user_id: recipeUserId.value })
      : await loginUser(payload);

    setCurrentUser(data);
    const onboardingDone = data?.onboarding_done || data?.user?.onboarding_done || data?.onboarding_preferences;
    if (isRegister.value || !onboardingDone) {
      router.push("/onboarding");
    } else {
      router.push("/recommend");
    }
  } catch (e) {
    error.value = e.response?.data?.detail || "登录或注册失败";
  } finally {
    loading.value = false;
  }
}
</script>
