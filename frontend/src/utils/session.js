const STORAGE_KEY = "reciperec_user";

export function getCurrentUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setCurrentUser(user) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  window.dispatchEvent(new CustomEvent("reciperec:user-changed", { detail: user }));
}

export function clearCurrentUser() {
  localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new CustomEvent("reciperec:user-changed", { detail: null }));
}
