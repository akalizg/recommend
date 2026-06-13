import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

// ---- Recommendation API ----

export function getRecommendations(userId, topK = 20) {
  return api.get(`/recommend/${userId}`, { params: { top_k: topK } });
}

export function getOfflineRecommendations(userId, limit = 20) {
  return api.get(`/offline/recommendations/${userId}`, { params: { limit } });
}

export function getScenarioRecommendations(payload) {
  return api.post("/recipes/scenario-recommend", payload);
}

export function getColdStartRecipes(payload) {
  return api.post("/recipes/cold-start", payload);
}

export function getRecipeIngredients(params = {}) {
  return api.get("/recipes/ingredients", { params });
}

export function submitFeedback(payload) {
  return api.post("/feedback", payload);
}

export function submitRecommendationExposure(payload) {
  return api.post("/recommendation-exposure", payload);
}

export function registerUser(payload) {
  return api.post("/auth/register", payload);
}

export function loginUser(payload) {
  return api.post("/auth/login", payload);
}

export function getOfflineMetrics() {
  return api.get("/offline/metrics");
}

export function getOfflineAblation() {
  return api.get("/offline/ablation");
}

export function getOfflineUserProfile(userId) {
  return api.get(`/offline/user-profile/${userId}`);
}

export function getOfflineMovieProfile(movieId) {
  return api.get(`/offline/movie-profile/${movieId}`);
}

export function getOfflinePopularRecipes(limit = 20) {
  return api.get("/offline/popular-recipes", { params: { limit } });
}

export function getPopular(limit = 50) {
  return api.get("/popular", { params: { limit } });
}

export function getMovieDetail(movieId) {
  return api.get(`/movie/${movieId}`);
}

export function getSimilarRecipes(movieId, limit = 8) {
  return api.get(`/recipe/${movieId}/similar`, { params: { limit } });
}

export function getUserProfile(userId) {
  return api.get(`/user/${userId}/profile`);
}

export function searchMovies(query, limit = 20) {
  return api.get("/search", { params: { q: query, limit } });
}

export function rebuildIndex() {
  return api.post("/rebuild-index");
}

export function healthCheck() {
  return api.get("/health");
}

export default api;
