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

// ---- Taste Twin API ----

export function getTasteTwinSettings(userId) {
  return api.get(`/taste-twin/settings/${userId}`);
}

export function updateTasteTwinSettings(userId, payload) {
  return api.patch(`/taste-twin/settings/${userId}`, payload);
}

export function getTasteTwinMatches(userId, limit = 10) {
  return api.get(`/taste-twin/${userId}/matches`, { params: { limit } });
}

export function getTasteTwinProfile(userId, twinUserId, highPage = 1, lowPage = 1, pageSize = 12) {
  return api.get(`/taste-twin/${userId}/profiles/${twinUserId}`, { params: { high_page: highPage, low_page: lowPage, page_size: pageSize } });
}

export function copyTasteTwinRecipe(userId, movieId) {
  return api.post(`/taste-twin/${userId}/copy/${movieId}`);
}

export function rateTasteTwinRecipe(userId, movieId, rating) {
  return api.post(`/taste-twin/${userId}/rate/${movieId}`, { rating });
}

export function getTasteTwinJointMenu(userId, twinUserId, offset = 0) {
  return api.get(`/taste-twin/${userId}/joint-menu/${twinUserId}`, { params: { offset } });
}



export function createDemoTasteTwins(userId, count = 5) {
  return api.post(`/taste-twin/${userId}/demo-twins`, null, { params: { count } });
}

export function getTasteTwinRecords(userId, recordType = "all", page = 1, pageSize = 12) {
  return api.get(`/taste-twin/${userId}/records`, { params: { record_type: recordType, page, page_size: pageSize } });
}

export function deleteTasteTwinRecord(userId, recordId) {
  return api.delete(`/taste-twin/${userId}/records`, { params: { record_id: recordId } });
}
