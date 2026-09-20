export const getSessionUser = () => {
  const isLoggedIn = localStorage.getItem("auditiq_logged_in") === "true";
  if (!isLoggedIn) {
    return {
      userId: "",
      username: "",
      role: "AUDITOR",
      email: "",
      token: "",
      isAuthenticated: false,
    };
  }

  const userId = localStorage.getItem("auditiq_user_id") || "auditor_local_01";
  const username = localStorage.getItem("auditiq_username") || "Lead Auditor (AWS)";
  const role = localStorage.getItem("auditiq_user_role") || "AUDITOR";
  const email = localStorage.getItem("auditiq_email") || "auditor@auditiq.cloud";
  const token = localStorage.getItem("auditiq_token") || "";

  return {
    userId,
    username,
    role,
    email,
    token,
    isAuthenticated: true,
  };
};

export const setSessionUser = (user) => {
  if (!user) return;
  localStorage.setItem("auditiq_logged_in", "true");
  if (user.userId) localStorage.setItem("auditiq_user_id", user.userId);
  if (user.username) localStorage.setItem("auditiq_username", user.username);
  if (user.role) localStorage.setItem("auditiq_user_role", user.role);
  if (user.email) localStorage.setItem("auditiq_email", user.email);
  if (user.token) localStorage.setItem("auditiq_token", user.token);
};

export const clearSessionUser = () => {
  localStorage.removeItem("auditiq_logged_in");
  localStorage.removeItem("auditiq_token");
  localStorage.removeItem("auditiq_user_id");
  localStorage.removeItem("auditiq_username");
  localStorage.removeItem("auditiq_user_role");
  localStorage.removeItem("auditiq_email");
};
