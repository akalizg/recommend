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

export function getPopular(limit = 50) {
  return api.get("/popular", { params: { limit } });
}

export function getMovieDetail(movieId) {
  return api.get(`/movie/${movieId}`);
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
