import api from "./index";

export function saveOnboardingPreferences(userId, payload) {
  return api.post(`/users/${userId}/onboarding-preferences`, payload);
}
