// По умолчанию запросы идут на тот же адрес, что и админка (Vite проксирует /api на backend).
const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function request(path, { method = "GET", role = "admin", apiKey, body } = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Role": role
  };
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined
  });

  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const data = await response.json();
      if (data?.detail) {
        message = data.detail;
      }
    } catch {
      // ignore parsing errors for non-json responses
    }
    throw new Error(message);
  }

  return response.json();
}

export function getApiBase() {
  return API_BASE || window.location.origin;
}

export function listProjects(role) {
  return request("/api/v1/projects", { role });
}

export function createProject(role, payload) {
  return request("/api/v1/projects", { method: "POST", role, body: payload });
}

export function updateProjectRules(role, projectId, payload) {
  return request(`/api/v1/projects/${projectId}/rules`, {
    method: "PATCH",
    role,
    body: payload
  });
}

export function listChecks(role, params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/v1/moderation/checks${suffix}`, { role });
}

export function getCheck(role, checkId) {
  return request(`/api/v1/moderation/checks/${checkId}`, { role });
}

export function submitCheck(role, payload, apiKey) {
  return request("/api/v1/moderation/checks", {
    method: "POST",
    role,
    apiKey,
    body: payload
  });
}

export function reviewCheck(role, checkId, action, comment) {
  return request(`/api/v1/moderation/checks/${checkId}/review`, {
    method: "POST",
    role,
    body: { action, comment }
  });
}

export function getAnalytics(role, projectId) {
  return request(`/api/v1/analytics?project_id=${projectId}`, { role });
}

