import api from "./index";

export function chatRecommend(payload) {
  return api.post("/chat/recommend", payload, { timeout: 60000 });
}
