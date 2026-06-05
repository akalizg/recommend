import { createRouter, createWebHistory } from "vue-router";
import Home from "../views/Home.vue";
import Recommend from "../views/Recommend.vue";
import Search from "../views/Search.vue";
import MovieDetail from "../views/MovieDetail.vue";

const routes = [
  { path: "/", name: "Home", component: Home },
  { path: "/recommend/:userId?", name: "Recommend", component: Recommend },
  { path: "/search", name: "Search", component: Search },
  { path: "/movie/:movieId", name: "MovieDetail", component: MovieDetail },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
