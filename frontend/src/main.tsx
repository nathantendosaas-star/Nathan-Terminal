import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import AuthGate from "./components/AuthGate";
import "./styles.css";

// The backend uses short-lived bearer sessions. Keep the token scoped to this tab.
const originalFetch = window.fetch.bind(window);
window.fetch = (input: RequestInfo | URL, init: RequestInit = {}) => {
  const token = sessionStorage.getItem("nt_access_token");
  const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
  if (token) headers.set("Authorization", "Bearer " + token);
  return originalFetch(input, { ...init, headers });
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><AuthGate><App /></AuthGate></React.StrictMode>
);
