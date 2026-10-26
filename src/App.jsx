import { useEffect, useState } from "react";
import {
  createProject,
  getAnalytics,
  getApiBase,
  getCheck,
  listChecks,
  listProjects,
  reviewCheck,
  submitCheck,
  updateProjectRules
} from "./api.js";

const EMPTY_ANALYTICS = {
  total_checks: 0,
  by_status: {},
  top_risk_signals: []
};

// Подписи для экрана. Значения-ключи совпадают с тем, что приходит из API и уходит в него.
const STATUS_LABELS = {
  approved: "Одобрено",
  manual_review: "На ручной проверке",
  rejected: "Отклонено",
  pending: "В обработке",
  escalated: "Передано старшему"
};

const ACTION_LABELS = {
  approve: "Одобрить",
  reject: "Отклонить",
  send_to_manual_review: "Отправить на ручную проверку",
  escalate: "Передать старшему"
};

const SEVERITY_LABELS = {
  critical: "критичная",
  high: "высокая",
  medium: "средняя",
  low: "низкая"
};

const SIGNAL_LABELS = {
  BANNED_CATEGORY: "Запрещённая категория",
  BANNED_KEYWORDS: "Запрещённые формулировки",
  CERTIFICATE_REQUIRED: "Нет сертификата",
  RISKY_KEYWORDS: "Рискованные формулировки",
  MISSING_REQUIRED_FIELDS: "Не заполнены обязательные атрибуты",
  RISKY_IMAGE_MARKER: "Подозрительные изображения"
};

const REVIEW_ACTIONS = ["approve", "reject", "escalate"];

const TABS = [
  { id: "queue", label: "Очередь" },
  { id: "rules", label: "Правила" },
  { id: "submit", label: "Проверить карточку" },
  { id: "analytics", label: "Аналитика" }
];

function labelFor(labels, value) {
  return labels[value] ?? value;
}

function csvToArray(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function arrayToCsv(values) {
  return (values || []).join(", ");
}

function rulesToDraft(rules) {
  return {
    risk_threshold: String(rules?.risk_threshold ?? 55),
    banned_categories: arrayToCsv(rules?.banned_categories),
    banned_keywords: arrayToCsv(rules?.banned_keywords),
    risky_keywords: arrayToCsv(rules?.risky_keywords),
    required_fields: arrayToCsv(rules?.required_fields),
    certificate_required_categories: arrayToCsv(rules?.certificate_required_categories)
  };
}

function draftToRules(draft) {
  return {
    risk_threshold: Number(draft.risk_threshold || 55),
    banned_categories: csvToArray(draft.banned_categories),
    banned_keywords: csvToArray(draft.banned_keywords),
    risky_keywords: csvToArray(draft.risky_keywords),
    required_fields: csvToArray(draft.required_fields),
    certificate_required_categories: csvToArray(draft.certificate_required_categories)
  };
}

function statusClass(status) {
  if (status === "approved") return "status approved";
  if (status === "rejected") return "status rejected";
  if (status === "manual_review") return "status review";
  if (status === "pending") return "status pending";
  if (status === "escalated") return "status escalated";
  return "status";
}

export default function App() {
  const [role, setRole] = useState("admin");
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [checks, setChecks] = useState([]);
  const [selectedCheck, setSelectedCheck] = useState(null);
  const [analytics, setAnalytics] = useState(EMPTY_ANALYTICS);
  const [statusFilter, setStatusFilter] = useState("");
  const [activeTab, setActiveTab] = useState("queue");

  const [projectDraft, setProjectDraft] = useState({ name: "", description: "" });
  const [ruleDraft, setRuleDraft] = useState(rulesToDraft({}));
  const [submission, setSubmission] = useState({
    content_type: "product_card",
    mode: "sync",
    external_content_id: "",
    title: "",
    description: "",
    category: "",
    brand: "",
    price: "",
    country_of_origin: "",
    certificate_number: "",
    has_certificate: false,
    image_urls: ""
  });
  const [reviewComment, setReviewComment] = useState("");

  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const selectedProject = projects.find((project) => project.id === selectedProjectId);

  async function loadProjects() {
    const data = await listProjects(role);
    setProjects(data);
    if (!data.length) {
      setSelectedProjectId("");
      return;
    }
    if (!selectedProjectId || !data.some((project) => project.id === selectedProjectId)) {
      setSelectedProjectId(data[0].id);
    }
  }

  async function loadChecksAndAnalytics(projectId, roleValue = role, filter = statusFilter) {
    if (!projectId) return;
    const params = { project_id: projectId };
    if (filter) {
      params.status = filter;
    }
    const [checksData, analyticsData] = await Promise.all([
      listChecks(roleValue, params),
      getAnalytics(roleValue, projectId)
    ]);
    setChecks(checksData);
    setAnalytics(analyticsData);
  }

  useEffect(() => {
    setError("");
    setMessage("");
    loadProjects().catch((err) => setError(err.message));
  }, [role]);

  useEffect(() => {
    if (!selectedProjectId) return;
    const currentProject = projects.find((project) => project.id === selectedProjectId);
    if (currentProject) {
      setRuleDraft(rulesToDraft(currentProject.rules));
    }
    loadChecksAndAnalytics(selectedProjectId).catch((err) => setError(err.message));
  }, [selectedProjectId, statusFilter, projects]);

  async function onCreateProject(event) {
    event.preventDefault();
    if (role !== "admin") {
      setError("Создавать проект может только роль admin");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = {
        name: projectDraft.name,
        description: projectDraft.description,
        rules: draftToRules(ruleDraft)
      };
      await createProject(role, payload);
      setProjectDraft({ name: "", description: "" });
      await loadProjects();
      setMessage("Проект создан");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function onSaveRules(event) {
    event.preventDefault();
    if (!selectedProjectId) return;
    if (role !== "admin") {
      setError("Изменять правила может только роль admin");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = { rules: draftToRules(ruleDraft) };
      await updateProjectRules(role, selectedProjectId, payload);
      await loadProjects();
      await loadChecksAndAnalytics(selectedProjectId);
      setMessage("Правила обновлены");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function onSubmitCheck(event) {
    event.preventDefault();
    if (!selectedProject) return;

    const attributes = {};
    ["brand", "price", "country_of_origin", "certificate_number"].forEach((key) => {
      if (submission[key]) {
        attributes[key] = submission[key];
      }
    });
    if (submission.has_certificate) {
      attributes.has_certificate = true;
    }

    const payload = {
      content_type: submission.content_type,
      mode: submission.mode,
      external_content_id: submission.external_content_id || null,
      title: submission.title,
      description: submission.description,
      category: submission.category,
      attributes,
      image_urls: csvToArray(submission.image_urls)
    };

    setLoading(true);
    setError("");
    try {
      const result = await submitCheck(role, payload, selectedProject.api_key);
      setMessage(`Проверка отправлена, статус: ${labelFor(STATUS_LABELS, result.status)}`);
      await loadChecksAndAnalytics(selectedProject.id);
      const details = await getCheck(role, result.check_id);
      setSelectedCheck(details);
      setActiveTab("queue");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function openCheck(checkId) {
    setError("");
    try {
      const details = await getCheck(role, checkId);
      setSelectedCheck(details);
    } catch (err) {
      setError(err.message);
    }
  }

  async function onManualAction(action) {
    if (!selectedCheck) return;
    if (!["admin", "moderator"].includes(role)) {
      setError("Ручные решения доступны только ролям admin и moderator");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const updated = await reviewCheck(role, selectedCheck.id, action, reviewComment);
      setSelectedCheck({ ...selectedCheck, ...updated });
      await loadChecksAndAnalytics(selectedProjectId);
      setMessage(`Решение сохранено: ${labelFor(ACTION_LABELS, action)}`);
      setReviewComment("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="hero">
        <div>
          <h1>Модерация карточек</h1>
          <p>
            API-first сервис для предмодерации карточек и объявлений: правила, ручной разбор,
            история решений и аналитика.
          </p>
        </div>
        <div className="hero-meta">
          <div>
            <span>Backend API</span>
            <strong>{getApiBase()}</strong>
          </div>
          <div>
            <span>Текущая роль</span>
            <select value={role} onChange={(event) => setRole(event.target.value)}>
              <option value="admin">admin</option>
              <option value="moderator">moderator</option>
              <option value="integrator">integrator</option>
            </select>
          </div>
        </div>
      </header>

      {message ? <p className="notice success">{message}</p> : null}
      {error ? <p className="notice error">{error}</p> : null}

      <section className="grid grid-2">
        <article className="card">
          <h2>Проект</h2>
          <label>Выбор проекта</label>
          <select
            value={selectedProjectId}
            onChange={(event) => setSelectedProjectId(event.target.value)}
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
          {selectedProject ? (
            <div className="small-list">
              <p>
                <strong>API key:</strong> {selectedProject.api_key}
              </p>
              <p>
                <strong>Threshold:</strong> {selectedProject.rules.risk_threshold}
              </p>
            </div>
          ) : (
            <p className="muted">Нет доступных проектов.</p>
          )}
        </article>

        <article className="card">
          <h2>Новый проект</h2>
          <form onSubmit={onCreateProject} className="form">
            <label>Название</label>
            <input
              value={projectDraft.name}
              onChange={(event) =>
                setProjectDraft((prev) => ({ ...prev, name: event.target.value }))
              }
              required
            />
            <label>Описание</label>
            <textarea
              value={projectDraft.description}
              onChange={(event) =>
                setProjectDraft((prev) => ({ ...prev, description: event.target.value }))
              }
            />
            <button disabled={loading || role !== "admin"} type="submit">
              Создать проект
            </button>
          </form>
        </article>
      </section>

      {selectedProject ? (
        <>
          <section className="project-head">
            <h2>{selectedProject.name}</h2>
            <nav className="tabs" role="tablist">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  className={activeTab === tab.id ? "tab active" : "tab"}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </section>

          {activeTab === "queue" ? (
            <section className="grid grid-2" role="tabpanel">
              <article className="card">
                <h2>Очередь проверок</h2>
                <div className="form">
                  <label>Статус</label>
                  <select
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value)}
                  >
                    <option value="">Все</option>
                    {Object.entries(STATUS_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Тип</th>
                        <th>Статус</th>
                        <th>Риск</th>
                        <th>Версия</th>
                        <th>Создано</th>
                      </tr>
                    </thead>
                    <tbody>
                      {checks.map((item) => (
                        <tr key={item.id} onClick={() => openCheck(item.id)}>
                          <td>{item.id.slice(0, 8)}</td>
                          <td>{item.content_type}</td>
                          <td>
                            <span className={statusClass(item.status)}>
                              {labelFor(STATUS_LABELS, item.status)}
                            </span>
                          </td>
                          <td>{item.risk_score}</td>
                          <td>v{item.version}</td>
                          <td>{new Date(item.created_at).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>

              <article className="card">
                <h2>Карточка проверки</h2>
                {selectedCheck ? (
                  <div className="details">
                    <p>
                      <strong>ID:</strong> {selectedCheck.id}
                    </p>
                    <p>
                      <strong>Статус:</strong>{" "}
                      <span className={statusClass(selectedCheck.status)}>
                        {labelFor(STATUS_LABELS, selectedCheck.status)}
                      </span>
                    </p>
                    <p>
                      <strong>Рекомендация:</strong>{" "}
                      {labelFor(ACTION_LABELS, selectedCheck.recommended_action)}
                    </p>
                    <p>
                      <strong>Риск:</strong> {selectedCheck.risk_score}
                    </p>
                    <p>
                      <strong>Категория:</strong> {selectedCheck.category || "n/a"}
                    </p>
                    <p>
                      <strong>Описание:</strong> {selectedCheck.description || "n/a"}
                    </p>

                    <h3>Сработавшие правила</h3>
                    {selectedCheck.triggered_rules.length ? (
                      <ul>
                        {selectedCheck.triggered_rules.map((signal) => (
                          <li key={`${signal.code}-${signal.message}`}>
                            {signal.message}
                            <div className="hint">
                              {signal.code} · {labelFor(SEVERITY_LABELS, signal.severity)}
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">Нарушения не найдены.</p>
                    )}

                    <h3>История версий</h3>
                    {selectedCheck.related_versions.length ? (
                      <ul>
                        {selectedCheck.related_versions.map((item) => (
                          <li key={item.id}>
                            v{item.version} - {labelFor(STATUS_LABELS, item.status)} -{" "}
                            {new Date(item.created_at).toLocaleString()}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">История пока отсутствует.</p>
                    )}

                    <h3>Ручное решение</h3>
                    <textarea
                      value={reviewComment}
                      onChange={(event) => setReviewComment(event.target.value)}
                      placeholder="Комментарий модератора"
                    />
                    <div className="actions">
                      {REVIEW_ACTIONS.map((action) => (
                        <button
                          key={action}
                          disabled={loading}
                          onClick={() => onManualAction(action)}
                          type="button"
                        >
                          {labelFor(ACTION_LABELS, action)}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="muted">Выберите проверку из таблицы слева.</p>
                )}
              </article>
            </section>
          ) : null}

          {activeTab === "rules" ? (
            <section className="grid" role="tabpanel">
              <article className="card">
                <h2>Правила проекта</h2>
                <form onSubmit={onSaveRules} className="form">
                  <label>Порог риска (0–100)</label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={ruleDraft.risk_threshold}
                    onChange={(event) =>
                      setRuleDraft((prev) => ({ ...prev, risk_threshold: event.target.value }))
                    }
                  />
                  <p className="hint">
                    Карточка с оценкой риска не ниже порога уходит на ручную проверку
                  </p>
                  <label>Запрещенные категории</label>
                  <textarea
                    value={ruleDraft.banned_categories}
                    onChange={(event) =>
                      setRuleDraft((prev) => ({ ...prev, banned_categories: event.target.value }))
                    }
                  />
                  <p className="hint">Значения через запятую, регистр не важен</p>
                  <label>Запрещенные формулировки</label>
                  <textarea
                    value={ruleDraft.banned_keywords}
                    onChange={(event) =>
                      setRuleDraft((prev) => ({ ...prev, banned_keywords: event.target.value }))
                    }
                  />
                  <p className="hint">Значения через запятую, регистр не важен</p>
                  <label>Рискованные формулировки</label>
                  <textarea
                    value={ruleDraft.risky_keywords}
                    onChange={(event) =>
                      setRuleDraft((prev) => ({ ...prev, risky_keywords: event.target.value }))
                    }
                  />
                  <p className="hint">Значения через запятую, регистр не важен</p>
                  <label>Обязательные атрибуты</label>
                  <textarea
                    value={ruleDraft.required_fields}
                    onChange={(event) =>
                      setRuleDraft((prev) => ({ ...prev, required_fields: event.target.value }))
                    }
                  />
                  <p className="hint">Ключи атрибутов, например: brand, price, country_of_origin</p>
                  <label>Категории, где нужен сертификат</label>
                  <textarea
                    value={ruleDraft.certificate_required_categories}
                    onChange={(event) =>
                      setRuleDraft((prev) => ({
                        ...prev,
                        certificate_required_categories: event.target.value
                      }))
                    }
                  />
                  <p className="hint">Значения через запятую, регистр не важен</p>
                  <button disabled={loading || role !== "admin"} type="submit">
                    Сохранить правила
                  </button>
                </form>
              </article>
            </section>
          ) : null}

          {activeTab === "submit" ? (
            <section className="grid" role="tabpanel">
              <article className="card">
                <h2>Отправка контента на проверку</h2>
                <form onSubmit={onSubmitCheck} className="form">
                  <label>Тип контента</label>
                  <select
                    value={submission.content_type}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, content_type: event.target.value }))
                    }
                  >
                    <option value="product_card">Карточка товара</option>
                    <option value="announcement">Объявление</option>
                  </select>
                  <label>Режим</label>
                  <select
                    value={submission.mode}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, mode: event.target.value }))
                    }
                  >
                    <option value="sync">Сразу</option>
                    <option value="async">В фоне</option>
                  </select>
                  <label>ID карточки в вашей системе</label>
                  <input
                    value={submission.external_content_id}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, external_content_id: event.target.value }))
                    }
                    placeholder="SKU-001"
                  />
                  <label>Заголовок</label>
                  <input
                    value={submission.title}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, title: event.target.value }))
                    }
                  />
                  <label>Описание</label>
                  <textarea
                    value={submission.description}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, description: event.target.value }))
                    }
                  />
                  <label>Категория</label>
                  <input
                    value={submission.category}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, category: event.target.value }))
                    }
                  />
                  <label>Бренд</label>
                  <input
                    value={submission.brand}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, brand: event.target.value }))
                    }
                  />
                  <label>Цена</label>
                  <input
                    value={submission.price}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, price: event.target.value }))
                    }
                  />
                  <label>Страна производства</label>
                  <input
                    value={submission.country_of_origin}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, country_of_origin: event.target.value }))
                    }
                  />
                  <label>Номер сертификата</label>
                  <input
                    value={submission.certificate_number}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, certificate_number: event.target.value }))
                    }
                  />
                  <label>Ссылки на изображения (через запятую)</label>
                  <textarea
                    value={submission.image_urls}
                    onChange={(event) =>
                      setSubmission((prev) => ({ ...prev, image_urls: event.target.value }))
                    }
                    placeholder="https://cdn.shop/item.jpg, https://cdn.shop/weapon-demo.jpg"
                  />
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={submission.has_certificate}
                      onChange={(event) =>
                        setSubmission((prev) => ({ ...prev, has_certificate: event.target.checked }))
                      }
                    />
                    Подтвержден сертификат
                  </label>
                  <button disabled={loading} type="submit">
                    Запустить проверку
                  </button>
                </form>
              </article>
            </section>
          ) : null}

          {activeTab === "analytics" ? (
            <section className="grid" role="tabpanel">
              <article className="card">
                <h2>Аналитика проекта</h2>
                <div className="metrics">
                  <div className="metric">
                    <span>Всего проверок</span>
                    <strong>{analytics.total_checks}</strong>
                  </div>
                  {Object.entries(analytics.by_status).map(([key, value]) => (
                    <div className="metric" key={key}>
                      <span>{labelFor(STATUS_LABELS, key)}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
                <h3>Частые причины</h3>
                <div className="signals">
                  {analytics.top_risk_signals.length ? (
                    analytics.top_risk_signals.map((item) => (
                      <div key={item.code} className="signal-row">
                        <span>{labelFor(SIGNAL_LABELS, item.code)}</span>
                        <div className="bar">
                          <i style={{ width: `${Math.min(100, item.count * 12)}%` }} />
                        </div>
                        <strong>{item.count}</strong>
                      </div>
                    ))
                  ) : (
                    <p className="muted">Пока нет срабатываний правил.</p>
                  )}
                </div>
              </article>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
