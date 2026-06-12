import { createRouter, createWebHistory } from "vue-router";
import Home from "../views/Home.vue";
import Recommend from "../views/Recommend.vue";
import Search from "../views/Search.vue";
import MovieDetail from "../views/MovieDetail.vue";

const routes = [
  { path: "/", name: "Home", component: Home },
  { path: "/recommend/:userId?", name: "Recommend", component: Recommend },
  { path: "/search", name: "Search", component: Search },
  { path: "/recipe/:movieId", name: "RecipeDetail", component: MovieDetail },
  { path: "/movie/:movieId", redirect: to => `/recipe/${to.params.movieId}` },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
