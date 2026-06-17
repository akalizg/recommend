import { createRouter, createWebHistory } from "vue-router";
import Home from "../views/Home.vue";
import Recommend from "../views/Recommend.vue";
import Search from "../views/Search.vue";
import MovieDetail from "../views/MovieDetail.vue";
import Login from "../views/Login.vue";
import TasteTwin from "../views/TasteTwin.vue";
import TasteTwinProfile from "../views/TasteTwinProfile.vue";
import TasteTwinRecords from "../views/TasteTwinRecords.vue";
import ChatRecommend from "../views/ChatRecommend.vue";
import OnboardingGuide from "../views/OnboardingGuide.vue";

const routes = [
  { path: "/", name: "Home", component: Home },
  { path: "/recommend/:userId?", name: "Recommend", component: Recommend },
  { path: "/search", name: "Search", component: Search },
  { path: "/login", name: "Login", component: Login },
  { path: "/onboarding", name: "OnboardingGuide", component: OnboardingGuide },
  { path: "/taste-twin", name: "TasteTwin", component: TasteTwin },
  { path: "/taste-twin/records", name: "TasteTwinRecords", component: TasteTwinRecords },
  { path: "/taste-twin/:userId", name: "TasteTwinProfile", component: TasteTwinProfile },
  { path: "/chat/recommend/:userId?", name: "ChatRecommend", component: ChatRecommend },
  { path: "/recipe/:movieId", name: "RecipeDetail", component: MovieDetail },
  { path: "/movie/:movieId", redirect: to => `/recipe/${to.params.movieId}` },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
