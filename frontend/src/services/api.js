import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach Cognito JWT Bearer token or dev session header to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("auditiq_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  const userId = localStorage.getItem("auditiq_user_id");
  if (userId) {
    config.headers["X-User-Id"] = userId;
  }

  const userRole = localStorage.getItem("auditiq_user_role");
  if (userRole) {
    config.headers["X-User-Role"] = userRole;
  }

  return config;
});

export default api;
