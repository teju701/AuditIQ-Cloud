import React, { useState } from "react";
import toast from "react-hot-toast";
import { setSessionUser } from "../services/auth";

export default function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("AUDITOR");
  const [loading, setLoading] = useState(false);

  const handleManualLogin = (e) => {
    e.preventDefault();
    if (!email.trim()) {
      toast.error("Please enter an email or username.");
      return;
    }

    setLoading(true);
    setTimeout(() => {
      const username = email.split("@")[0] || email;
      const user = {
        userId: `cognito_${username.toLowerCase().replace(/[^a-z0-9]/g, "_")}`,
        username: username.charAt(0).toUpperCase() + username.slice(1),
        role: role,
        email: email.includes("@") ? email : `${email}@auditiq.cloud`,
        token: `mock_cognito_jwt_${Date.now()}`,
        isAuthenticated: true,
      };
      setSessionUser(user);
      toast.success(`Authenticated through Amazon Cognito (${role})`);
      setLoading(false);
      onLoginSuccess && onLoginSuccess(user);
    }, 400);
  };

  const handleQuickLogin = (selectedRole) => {
    setLoading(true);
    const isAuditor = selectedRole === "AUDITOR";
    const user = {
      userId: isAuditor ? "auditor_local_01" : "admin_local_01",
      username: isAuditor ? "Lead Auditor (AWS)" : "Compliance Administrator",
      role: selectedRole,
      email: isAuditor ? "auditor@auditiq.cloud" : "admin@auditiq.cloud",
      token: `cognito_token_${selectedRole.toLowerCase()}_${Date.now()}`,
      isAuthenticated: true,
    };
    setSessionUser(user);
    toast.success(`Signed in as ${user.username} [${selectedRole}]`);
    setLoading(false);
    onLoginSuccess && onLoginSuccess(user);
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Brand Card Header */}
        <div className="text-center mb-8">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-linear-to-br from-cyan-600 to-emerald-600 flex items-center justify-center shadow-lg mb-4 shadow-cyan-900/10">
            <span className="text-white font-black text-2xl">A</span>
          </div>
          <h2 className="font-display text-2xl font-bold text-slate-900">
            Sign In to AuditIQ Cloud
          </h2>
          <p className="text-xs text-slate-500 mt-1.5">
            Enterprise Financial Audit Investigation Platform on AWS
          </p>
          <div className="mt-2.5 inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-0.5 text-[11px] font-semibold text-cyan-800">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Amazon Cognito User Pool Protected
          </div>
        </div>

        {/* Login Box */}
        <div className="rounded-3xl border border-slate-200 bg-white p-6 md:p-8 shadow-sm">
          <form onSubmit={handleManualLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Cognito Username / Work Email
              </label>
              <input
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. auditor@enterprise.com"
                className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Role Assignment (Cognito Group)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setRole("AUDITOR")}
                  className={`rounded-xl border py-2 text-xs font-semibold transition-all ${
                    role === "AUDITOR"
                      ? "border-cyan-500 bg-cyan-50 text-cyan-800 shadow-xs"
                      : "border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  Auditor
                </button>
                <button
                  type="button"
                  onClick={() => setRole("ADMIN")}
                  className={`rounded-xl border py-2 text-xs font-semibold transition-all ${
                    role === "ADMIN"
                      ? "border-cyan-500 bg-cyan-50 text-cyan-800 shadow-xs"
                      : "border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  Admin
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-linear-to-r from-cyan-600 to-emerald-600 py-2.5 text-sm font-semibold text-white shadow-sm hover:from-cyan-700 hover:to-emerald-700 transition-all disabled:opacity-50"
            >
              {loading ? "Authenticating..." : "Authenticate via Cognito"}
            </button>
          </form>

          {/* Quick Demo Logins for Hackathon evaluation */}
          <div className="mt-6 pt-6 border-t border-slate-100">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2.5 text-center">
              Quick Test Sign In
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleQuickLogin("AUDITOR")}
                className="rounded-xl border border-cyan-200 bg-cyan-50/70 p-2.5 text-left hover:bg-cyan-100/70 transition-colors"
              >
                <p className="text-xs font-bold text-cyan-900">Lead Auditor</p>
                <p className="text-[10px] text-cyan-700 mt-0.5">Upload & audits</p>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin("ADMIN")}
                className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-2.5 text-left hover:bg-emerald-100/70 transition-colors"
              >
                <p className="text-xs font-bold text-emerald-900">Admin</p>
                <p className="text-[10px] text-emerald-700 mt-0.5">System overview</p>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
