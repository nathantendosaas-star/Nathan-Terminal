import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import AuthGate from "./components/AuthGate";
import "./styles.css";

// The backend uses short-lived bearer sessions. Keep the token scoped to this tab.
const originalFetch = window.fetch.bind(window);
const API_ORIGIN = import.meta.env.VITE_API_BASE_URL || "";
const API_BASE = API_ORIGIN.endsWith("/") ? API_ORIGIN.slice(0, -1) : API_ORIGIN;
window.fetch = (input: RequestInfo | URL, init: RequestInit = {}) => {
  const token = sessionStorage.getItem("nt_access_token");
  const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
  if (token) headers.set("Authorization", "Bearer " + token);
  const target = typeof input === "string" && input.startsWith("/api/") && API_BASE ? API_BASE + input : input;
  return originalFetch(target, { ...init, headers }).then(response => {
    if (response.status === 401 && !String(target).includes("/api/v1/auth/")) {
      sessionStorage.removeItem("nt_access_token");
      window.location.reload();
    }
    return response;
  });
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><AuthGate><App /></AuthGate></React.StrictMode>
);
