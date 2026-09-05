(() => {
  "use strict";

  const state = {
    auth: null,
    projects: [],
    project: null,
    history: null,
    activeBatch: 0,
    saveTimer: 0,
    pollTimer: 0,
    operationPollTimers: new Map(),
    operationIds: new Map(),
    operationStatus: new Map(),
    pinnedGeneratedBatch: null,
    generationStartedAt: 0,
    generationTimer: 0,
    activeRunId: 0,
    continuingSchemes: new Set(),
    carouselIndexes: new Map(),
    saving: false,
    savePromise: null,
    tagConfig: null,
    tagUi: { openKey: "", query: "", confirmed: new Set(), confirmationProjectId: 0, confirmationScriptType: "", lastStep: 0, roundIndex: 1, roundOpenFields: new Map() },
  };

  const V2_GENERATION_ENDPOINTS = {
    run: (projectId) => `/api/v2/projects/${projectId}/generate`,
    history: (projectId) => `/api/v2/projects/${projectId}/history`,
    runStatus: (runId) => `/api/v2/runs/${runId}`,
    adoption: (projectId) => `/api/v2/projects/${projectId}/adopt`,
    adoptionStatus: (projectId) => `/api/v2/projects/${projectId}/adoption`,
    schemeImage: (schemeId) => `/api/v2/schemes/${schemeId}/image`,
    frameImage: (schemeId, frameIndex) => `/api/v2/schemes/${schemeId}/frames/${frameIndex}/image`,
    imageAttempt: (attemptId) => `/api/v2/image-attempts/${attemptId}`,
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const els = {
    authGate: $("#authGate"), appShell: $("#appShell"), loginForm: $("#loginForm"), passwordForm: $("#passwordForm"), authMessage: $("#authMessage"), loginButton: $("#loginButton"), passwordButton: $("#passwordButton"), userBar: $("#userBar"), currentUserLabel: $("#currentUserLabel"), logout: $("#logoutButton"), adminUsersButton: $("#adminUsersButton"), adminDialog: $("#adminDialog"), closeAdminButton: $("#closeAdminButton"), adminUsersList: $("#adminUsersList"), adminUserSearch: $("#adminUserSearch"), adminRoleFilter: $("#adminRoleFilter"), openCreateUserButton: $("#openCreateUserButton"), createUserDialog: $("#createUserDialog"), closeCreateUserButton: $("#closeCreateUserButton"), cancelCreateUserButton: $("#cancelCreateUserButton"), createUserForm: $("#createUserForm"),
    empty: $("#emptyState"), workspace: $("#projectWorkspace"), list: $("#projectList"), sidebar: $("#projectSidebar"), sidebarBackdrop: $("#sidebarBackdrop"),
    search: $("#projectSearch"),
    description: $("#taskDescription"), descriptionLabel: $("#descriptionLabel"),
    aspectField: $("#aspectField"),
    tagControls: $("#tagControls"),
    saveState: $("#saveState"), generate: $("#generateButton"),
    generateTitle: $("#generateTitle"), generationHint: $("#generationHint"),
    results: $(".results-section"), resultsGrid: $("#resultsGrid"), resultsTitle: $("#resultsTitle"),
    resultsMeta: $("#resultsMeta"), batchTabs: $("#batchTabs"), stale: $("#staleResults"),
    staleBody: $("#staleResultsBody"), adoption: $("#adoptionPanel"), toast: $("#toast"),
    imageDialog: $("#imageDialog"), dialogImage: $("#dialogImage"),
    stepper: $("#stepper"), stepPosition: $("#stepPosition"), stepOutput: $("#stepOutput"),
    positionNext: $("#positionNextButton"), outputEdit: $("#outputEditButton"),
    projectMenu: $("#projectMenuButton"), outputBriefSummary: $("#outputBriefSummary"), outputModeSummary: $("#outputModeSummary"),
  };

  let currentStep = 1;

  function setProjectDrawer(open) {
    els.sidebar.classList.toggle("drawer-open", open);
    els.projectMenu.setAttribute("aria-expanded", String(open));
  }

  const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
  const displayTagLabel = (value, mode = activeTagMode()) => mode === "narrative" ? String(value ?? "").replace(/[？?]+$/, "") : String(value ?? "");

  async function api(path, options = {}) {
    const request = { ...options, headers: { ...(options.headers || {}) } };
    const method = String(request.method || "GET").toUpperCase();
    if (!["GET", "HEAD", "OPTIONS"].includes(method) && !path.includes("/auth/login")) {
      const csrf = document.cookie.split(";").map((item) => item.trim().split("=")).find(([key]) => key === "studio_csrf")?.[1];
      if (csrf) request.headers["X-CSRF-Token"] = decodeURIComponent(csrf);
    }
    const response = await fetch(path, request);
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401 && !path.includes("/auth/status") && !path.includes("/auth/login")) {
      showLogin("登录已失效，请重新登录");
    }
    if (response.status === 403) throw new Error(payload.error || "没有权限执行此操作");
    if (!response.ok || payload.success === false) throw new Error(payload.error || "请求失败");
    return payload;
  }

  function showLogin(message = "请输入账号和密码继续。") {
    state.auth = null; stopPolling();
    els.authMessage.textContent = message;
    els.loginForm.classList.remove("hidden"); els.passwordForm.classList.add("hidden");
    els.appShell.classList.add("hidden"); els.authGate.classList.remove("hidden"); els.userBar.classList.add("hidden");
  }

  function showPasswordChange() {
    els.loginForm.classList.add("hidden"); els.passwordForm.classList.remove("hidden");
    els.appShell.classList.add("hidden"); els.authGate.classList.remove("hidden");
  }

  function showApp(user) {
    state.auth = user; els.authGate.classList.add("hidden"); els.appShell.classList.remove("hidden");
    els.userBar.classList.remove("hidden"); els.currentUserLabel.textContent = user.username;
    els.adminUsersButton.classList.toggle("hidden", user.role !== "admin");
  }

  async function loadAdminUsers() {
    const payload = await api("/api/admin/users");
    const query = String(els.adminUserSearch?.value || "").trim().toLowerCase();
    const role = els.adminRoleFilter?.value || "all";
    const users = (payload.users || []).filter((user) => (!query || String(user.username).toLowerCase().includes(query)) && (role === "all" || user.role === role));
    els.adminUsersList.innerHTML = users.map((user) => `<tr><td><div class="admin-account"><span class="admin-avatar">${esc(String(user.username).slice(0, 1).toUpperCase())}</span><div><strong>${esc(user.username)}</strong><small>${esc(user.username)}</small></div></div></td><td><span class="role-pill">● ${user.role === "admin" ? "管理员" : "普通用户"}</span></td><td class="muted-cell">-</td><td class="muted-cell">${esc(user.last_login_at || "-")}</td><td><span class="status-pill ${user.is_active ? "is-active" : "is-disabled"}">● ${user.is_active ? "启用" : "停用"}</span></td><td><div class="admin-user-actions"><button class="table-action" type="button" data-user-action="edit" data-user-id="${user.id}" data-username="${esc(user.username)}">编辑</button><button class="table-action" type="button" data-user-action="reset" data-user-id="${user.id}">重置密码</button><button class="table-action" type="button" data-user-action="toggle" data-user-id="${user.id}" data-active="${user.is_active}">${user.is_active ? "禁用" : "启用"}</button><button class="table-action danger" type="button" data-user-action="delete" data-user-id="${user.id}">删除</button></div></td></tr>`).join("") || `<tr><td colspan="6" class="admin-empty">暂无匹配账号</td></tr>`;
  }

  async function enterApp(user) {
    showApp(user);
    try {
      const payload = await api("/api/tag-options"); state.tagConfig = payload.config;
      await loadProjects(); if (state.projects.length) await openProject(state.projects[0].id);
    } catch (error) { toast(error.message, true); }
  }

  function toast(message, error = false) {
    els.toast.textContent = message;
    els.toast.className = `toast show${error ? " error" : ""}`;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { els.toast.className = "toast"; }, 2300);
  }

  function splitTags(value) {
    return String(value || "").split(/[，,、\n]/).map((item) => item.trim()).filter(Boolean);
  }

  function selectWithinLimit(values, value, max) {
    const next = values.slice();
    const index = next.indexOf(value);
    if (index >= 0) { next.splice(index, 1); return next; }
    if (max <= 0 || next.length >= max) return next;
    next.push(value);
    return next;
  }

  function activeTagMode() {
    return (state.project?.script_type || $("#scriptTypeSelect")?.value || "展示类") === "展示类" ? "visual" : "narrative";
  }

  function selectedScriptType() {
    return state.project?.script_type || $("#scriptTypeSelect")?.value || "展示类";
  }

  function selectedOrLegacyOptions(options, selected) {
    const known = new Set((options || []).map((option) => String(option.label || "")));
    const legacy = (selected || []).filter((value) => !known.has(value)).map((value, index) => ({ id: `legacy-${index}`, label: value, category: "已有标签", description: "此标签来自旧项目数据" }));
    return [...legacy, ...(options || [])];
  }

  function ensureTagDraft() {
    if (!state.project) return {};
    if (!state.tagUi.draft || state.tagUi.draftProjectId !== state.project.id || state.tagUi.draftScriptType !== state.project.script_type) {
      state.tagUi.draft = normalizeTagDraft(JSON.parse(JSON.stringify(state.project.creative_tags || {})));
      state.tagUi.draftProjectId = state.project.id;
      state.tagUi.draftScriptType = state.project.script_type;
    }
    return state.tagUi.draft;
  }

  function normalizeTagDraft(draft) {
    const groups = state.tagConfig?.[activeTagMode()]?.groups || [];
    groups.forEach((group) => {
      if (group.type === "single" && Array.isArray(draft[group.key]) && draft[group.key].length > 1) draft[group.key] = draft[group.key].slice(0, 1);
      if (group.type === "style_cascade") {
        if (Array.isArray(draft.visual_art_style) && draft.visual_art_style.length > 1) draft.visual_art_style = draft.visual_art_style.slice(0, 1);
        if (Array.isArray(draft.visual_art_style_relevance) && draft.visual_art_style_relevance.length > 1) draft.visual_art_style_relevance = draft.visual_art_style_relevance.slice(0, 1);
        if (Array.isArray(draft.visual_art_style_references)) draft.visual_art_style_references = draft.visual_art_style_references.slice(0, 2);
      }
    });
    if (activeTagMode() === "visual") {
      const carousel = draft.visual_carousel?.[0] || "";
      if (carousel !== "是" && carousel !== "多画面轮播") { draft.visual_carousel_count = []; draft.visual_carousel_form = []; }
      const sellingGroup = groups.find((group) => group.key === "visual_product_selling_points");
      const displayGroup = groups.find((group) => group.key === "visual_display_contents");
      if (sellingGroup && displayGroup) {
        const selling = (draft.visual_product_selling_points || []).concat(draft.visual_secondary_product_selling_points || []);
        const relation = state.tagConfig.visual.relations?.product_display || {};
        const selectedIds = selling.map((label) => sellingGroup.options.find((option) => option.label === label)?.id).filter(Boolean);
        const allowedIds = new Set(selectedIds.flatMap((id) => relation[id] || []));
        draft.visual_display_contents = (draft.visual_display_contents || []).filter((label) => {
          const option = displayGroup.options.find((item) => item.label === label);
          return option && allowedIds.has(option.id);
        });
      }
      const styleGroup = groups.find((group) => group.key === "visual_art_style");
      if (styleGroup) {
        const relevance = draft.visual_art_style_relevance?.[0] || "";
        const style = styleGroup.options.find((option) => option.label === draft.visual_art_style?.[0]);
        if (relevance && style && style.category !== relevance) { draft.visual_art_style = []; draft.visual_art_style_references = []; }
        if (!style) draft.visual_art_style_references = [];
        const refs = style?.references || [];
        draft.visual_art_style_references = (draft.visual_art_style_references || []).filter((label) => refs.some((option) => option.label === label));
      }
    }
    return draft;
  }

  function setTagValues(key, values) {
    ensureTagDraft()[key] = values.filter(Boolean);
    renderTagControls();
    scheduleSave();
  }

  function groupOptions(group, key = group.key) {
    const draft = ensureTagDraft();
    const selected = draft[key] || [];
    return selectedOrLegacyOptions(group.options || [], selected);
  }

  function optionButton(group, option, key, { disabled = false, selected = false, role = "" } = {}) {
    const description = option.description || option.note || "查看该选项定义";
    const label = displayTagLabel(option.label);
    return `<button type="button" class="tag-option${selected ? " selected" : ""}" data-tag-key="${esc(key)}" data-tag-value="${esc(option.label)}" ${disabled ? "disabled" : ""}>
      <span class="tag-option-label">${esc(label)}${role ? `<small class="tag-role">${esc(role)}</small>` : ""}</span><span class="tag-option-check" aria-hidden="true">✓</span><span class="tag-option-info" tabindex="0" role="img" aria-label="查看${esc(label)}的定义" data-tooltip="${esc(description)}">i</span>
    </button>`;
  }

  function groupedOptions(group, key, options = groupOptions(group, key), { exclude = [], selectedOverride = null, maxOverride = null } = {}) {
    const draft = ensureTagDraft(); const selected = selectedOverride ? Array.from(selectedOverride) : (draft[key] || []); const blocked = new Set(exclude);
    const categories = new Map();
    options.filter((option) => !blocked.has(option.label)).forEach((option) => { const category = option.category || "未分组"; if (!categories.has(category)) categories.set(category, []); categories.get(category).push(option); });
    const max = maxOverride ?? group.max ?? group.main_max ?? 1;
    return Array.from(categories.entries()).map(([category, items]) => `<section class="tag-category"><div class="tag-category-header"><strong>${esc(category)}</strong><small>${items.length} 项</small></div><div class="tag-option-grid">${items.map((option) => optionButton(group, option, key, { selected: selected.includes(option.label) })).join("")}</div></section>`).join("");
  }

  function selectedHeadingText(values) {
    return values.map((value) => displayTagLabel(value)).filter(Boolean).join("、");
  }

  function groupSelectedValues(group, draft = ensureTagDraft()) {
    if (group.type === "style_cascade") return [...(draft.visual_art_style_relevance || []), ...(draft.visual_art_style || []), ...(draft.visual_art_style_references || [])];
    const values = (draft[group.key] || []).slice();
    if (group.secondary_key) values.push(...(draft[group.secondary_key] || []));
    return values;
  }

  function groupSummaryText(group, draft = ensureTagDraft()) {
    if (group.key === "visual_target_audiences" || group.key === "target_audiences") {
      return `主目标人群：${selectedHeadingText(draft[group.key] || []) || "未选择"}；副目标人群：${selectedHeadingText(draft[group.secondary_key] || []) || "未选择"}`;
    }
    return selectedHeadingText(groupSelectedValues(group, draft)) || "未选择";
  }

  function ensureTagConfirmations() {
    const draft = ensureTagDraft();
    const scriptType = selectedScriptType();
    if (state.tagUi.confirmationProjectId !== state.project?.id || state.tagUi.confirmationScriptType !== scriptType) {
      state.tagUi.confirmed.clear();
      state.tagUi.confirmationProjectId = state.project?.id || 0;
      state.tagUi.confirmationScriptType = scriptType;
      (state.tagConfig?.[activeTagMode()]?.groups || []).forEach((group) => {
        if (groupSelectedValues(group, draft).length) state.tagUi.confirmed.add(group.key);
      });
    }
    (state.tagConfig?.[activeTagMode()]?.groups || []).forEach((group) => {
      if (group.required && !groupSelectedValues(group, draft).length) state.tagUi.confirmed.delete(group.key);
    });
  }

  function renderReportTable(group, key, options, maxOverride = null, selectedOverride = null) {
    const draft = ensureTagDraft();
    const selected = selectedOverride ? new Set(selectedOverride) : new Set(draft[key] || []);
    if (!options.length) {
      return key === "visual_display_contents" ? '<p class="tag-empty-hint">请先选择产品卖点</p>' : '<p class="tag-empty-hint">暂无可选项</p>';
    }
    const categories = new Map();
    options.forEach((option) => {
      const category = option.category || "未分组";
      if (!categories.has(category)) categories.set(category, []);
      categories.get(category).push(option);
    });
    const max = maxOverride ?? group.max ?? group.main_max ?? 1;
    const columns = Array.from(categories.entries()).map(([category, items]) => `<th scope="col">${esc(category)}</th>`).join("");
    const cells = Array.from(categories.values()).map((items) => `<td><div class="report-choice-list">${items.map((option) => optionButton(group, option, key, { selected: selected.has(option.label), disabled: !selected.has(option.label) && selected.size >= max })).join("")}</div></td>`).join("");
    return `<div class="creative-position-table-scroll"><table class="creative-position-table"><tbody><tr><th scope="row">定位名称</th>${columns}</tr><tr><th scope="row">选项</th>${cells}</tr></tbody></table></div>`;
  }

  function renderReportBody(group, options, draft) {
    if (group.type === "style_cascade") return renderStyleChapter(group, draft);
    if (group.key === "visual_target_audiences" || group.key === "target_audiences") {
      const main = draft[group.key] || [];
      const secondary = draft[group.secondary_key] || [];
      const remaining = options.filter((option) => !main.includes(option.label));
      return `<div class="report-tier"><strong>主目标人群</strong>${renderReportTable(group, group.key, options, group.main_max || 1, main)}</div><div class="report-tier"><strong>副目标人群</strong>${renderReportTable(group, group.secondary_key, remaining, group.secondary_max || 1, secondary)}</div>`;
    }
    const selected = groupSelectedValues(group, draft);
    const max = group.type === "primary_secondary" ? (group.main_max || 0) + (group.secondary_max || 0) : (group.max || group.main_max || 1);
    return renderReportTable(group, group.key, options, max, selected);
  }

  function renderTagReport(chapter, index) {
    const { group, key, label, options } = chapter;
    const draft = ensureTagDraft();
    const selected = groupSelectedValues(group, draft);
    const confirmed = state.tagUi.confirmed.has(key);
    const status = groupSummaryText(group, draft);
    const hidden = group.visible_when && !((draft[group.visible_when.key] || []).some((value) => group.visible_when.values.includes(value)));
    if (hidden) return "";
    if (group.key === "visual_carousel") {
      const value = draft.visual_carousel?.[0] || "";
      return `<section class="creative-position-report" data-tag-report="${esc(key)}"><div class="creative-position-report-title"><h3>${esc(label)}</h3><div class="carousel-title-choices">${["是", "否"].map((option) => `<button type="button" class="report-confirm-button carousel-title-choice${value === option ? " selected" : ""}" data-carousel-choice="${option}" aria-pressed="${value === option}">${option}</button>`).join("")}</div><span class="creative-position-limit-hint">必选，最多选择1项</span></div></section>`;
    }
    // A completed chapter is represented only by the top summary; editing restores its report.
    if (confirmed) return "";
    const body = confirmed ? "" : renderReportBody(group, options, draft);
    const limit = group.type === "style_cascade" ? 2 : (group.main_max || group.max || 1) + (group.secondary_max || 0);
    const requirement = group.required ? "必选" : "可选";
    return `<section class="creative-position-report${confirmed ? " is-confirmed" : ""}" data-tag-report="${esc(key)}"><div class="creative-position-report-title"><h3>${esc(label)}</h3>${confirmed ? "" : `<button type="button" class="report-confirm-button" data-confirm-tag="${esc(key)}">确认</button>`}<span class="creative-position-limit-hint">${requirement}，最多选择${esc(limit)}项</span></div>${confirmed ? `<div class="report-summary-line">${esc(status)}</div>` : `<div class="creative-position-tables">${body}</div>`}</section>`;
  }

  function renderStyleChapter(group, draft) {
    const relevance = draft.visual_art_style_relevance || []; const styles = group.options.filter((option) => !relevance.length || relevance.includes(option.category)); const selectedStyle = draft.visual_art_style || []; const currentStyle = group.options.find((option) => selectedStyle.includes(option.label)); const refs = currentStyle?.references || [];
    const relevanceOptions = Array.from(new Set(group.options.map((option) => option.category)));
    return `<div class="cascade-step"><strong>1 · 与产品视觉的相关度</strong><div class="tag-option-grid">${relevanceOptions.map((value) => optionButton(group, { label: value, description: "一级相关度，用于表达与真实产品视觉的距离" }, "visual_art_style_relevance", { selected: relevance.includes(value), disabled: !relevance.includes(value) && relevance.length >= 1 })).join("")}</div></div><div class="cascade-step"><strong>2 · 具体美术风格</strong><div class="tag-option-grid">${styles.map((option) => optionButton(group, option, "visual_art_style", { selected: selectedStyle.includes(option.label), disabled: !selectedStyle.includes(option.label) && selectedStyle.length >= 1 })).join("")}</div></div>${currentStyle ? `<div class="cascade-step"><strong>3 · 参考作品 <small>可选，最多 2 项</small></strong><div class="tag-option-grid">${refs.map((option) => optionButton(group, option, "visual_art_style_references", { selected: (draft.visual_art_style_references || []).includes(option.label), disabled: !(draft.visual_art_style_references || []).includes(option.label) && (draft.visual_art_style_references || []).length >= 2 })).join("")}</div></div>` : ""}`;
  }

  function buildChapters(mode, groups) {
    const chapters = [];
    groups.forEach((group) => {
      const draft = ensureTagDraft();
      let groupOptions = group.options || [];
      if (mode === "visual" && group.key === "visual_display_contents") {
        const selling = (draft.visual_product_selling_points || []).concat(draft.visual_secondary_product_selling_points || []);
        const sellingGroup = groups.find((item) => item.key === "visual_product_selling_points");
        const selectedIds = new Set(selling.map((label) => sellingGroup?.options.find((option) => option.label === label)?.id).filter(Boolean));
        const relation = state.tagConfig.visual.relations?.product_display || {};
        const allowedIds = new Set(); selectedIds.forEach((id) => (relation[id] || []).forEach((displayId) => allowedIds.add(displayId)));
        groupOptions = allowedIds.size ? groupOptions.filter((option) => allowedIds.has(option.id)) : [];
      }
      // 两种创意类型共用同一套章节和选项交互；分类只负责在章节内部整理选项。
      chapters.push({ id: group.key, group, key: group.key, label: group.label, options: groupOptions });
    });
    return chapters;
  }

  function moveToNextChapter(chapterId) {
    const chapters = buildChapters(activeTagMode(), state.tagConfig[activeTagMode()]?.groups || []).filter((chapter) => {
      const condition = chapter.group.visible_when;
      return !condition || (ensureTagDraft()[condition.key] || []).some((value) => condition.values.includes(value));
    });
    const index = chapters.findIndex((chapter) => chapter.id === chapterId);
    state.tagUi.openKey = index >= 0 && index < chapters.length - 1 ? chapters[index + 1].id : "";
    renderTagControls();
  }

  function renderTagControls() {
    if (!state.tagConfig || !state.project) return;
    ensureTagDraft();
    const mode = activeTagMode(); const groups = state.tagConfig[mode]?.groups || []; const chapters = buildChapters(mode, groups); const draft = normalizeTagDraft(ensureTagDraft());
    const visibleChapters = chapters.filter((chapter) => !chapter.group.visible_when || (draft[chapter.group.visible_when.key] || []).some((value) => chapter.group.visible_when.values.includes(value)));
    ensureTagConfirmations();
    const summary = visibleChapters.filter((chapter) => state.tagUi.confirmed.has(chapter.key)).map((chapter) => `<div><b>${esc(chapter.label)}：</b>${esc(groupSummaryText(chapter.group, draft))}</div>`).join("");
    const editButtons = visibleChapters.filter((chapter) => state.tagUi.confirmed.has(chapter.key)).map((chapter) => `<button type="button" class="report-edit-button" data-edit-tag="${esc(chapter.key)}">修改${esc(chapter.label)}</button>`).join("");
    els.tagControls.innerHTML = `<div class="tag-script-type-field"><label>脚本类型 *<select id="scriptTypeSelect"><option value="展示类"${selectedScriptType() === "展示类" ? " selected" : ""}>展示类</option><option value="叙事类"${selectedScriptType() === "叙事类" ? " selected" : ""}>叙事类</option></select></label></div>${summary ? `<div class="selected-tag-summary"><div>${summary}</div><div class="selected-tag-actions">${editButtons}</div></div>` : ""}<div class="creative-tag-reports">${visibleChapters.map(renderTagReport).join("")}</div>${mode === "visual" ? renderCarouselRoundEditor() : ""}`;
  }

  function collectTagValues() {
    const draft = ensureTagDraft();
    return JSON.parse(JSON.stringify(draft));
  }

  function carouselCountValue(draft = ensureTagDraft()) {
    const value = draft.visual_carousel_count?.[0] || "";
    return /^([2-5])屏$/.test(value) ? Number(value[0]) : null;
  }

  function carouselFieldGroups() {
    const groups = state.tagConfig?.visual?.groups || [];
    const field = (key) => {
      const group = groups.find((item) => item.key === key) || {};
      return {
        key,
        label: group.label || key,
        max: (group.main_max || 0) + (group.secondary_max || 0) || 1,
        options: group.options || [],
        sourceKeys: [key, group.secondary_key].filter(Boolean),
      };
    };
    return [
      field("visual_target_audiences"),
      field("visual_player_desires"),
      field("visual_product_selling_points"),
      field("visual_display_contents"),
      field("visual_motif"),
      field("visual_dynamics"),
    ];
  }

  function carouselRoundOpenFields(index = state.tagUi.roundIndex || 1) {
    const stateKey = `${state.project?.id || 0}:${index}`;
    if (!state.tagUi.roundOpenFields.has(stateKey)) {
      state.tagUi.roundOpenFields.set(stateKey, new Set(["visual_motif", "visual_dynamics"]));
    }
    return state.tagUi.roundOpenFields.get(stateKey);
  }

  function ensureCarouselRounds(draft = ensureTagDraft()) {
    const count = carouselCountValue(draft);
    if (!count) { draft.visual_carousel_rounds = []; state.tagUi.roundIndex = 1; return []; }
    const fields = carouselFieldGroups();
    const topLevel = Object.fromEntries(fields.map((field) => [field.key, field.sourceKeys.flatMap((key) => draft[key] || []).slice(0, field.max)]));
    const existing = Array.isArray(draft.visual_carousel_rounds) ? draft.visual_carousel_rounds : [];
    const byIndex = new Map(existing.map((item) => [Number(item.index), item]));
    const rounds = Array.from({ length: count }, (_, offset) => {
      const index = offset + 1; const item = byIndex.get(index);
      if (item) return { index, mode: index === 1 ? "base" : (item.mode === "custom" ? "custom" : "inherit"), overrides: Object.fromEntries(fields.map((field) => [field.key, Array.isArray(item.overrides?.[field.key]) ? item.overrides[field.key].slice(0, field.max) : (index === 1 ? topLevel[field.key] : [])])) };
      return { index, mode: index === 1 ? "base" : "inherit", overrides: index === 1 ? topLevel : Object.fromEntries(fields.map((field) => [field.key, []])) };
    });
    draft.visual_carousel_rounds = rounds;
    state.tagUi.roundIndex = Math.max(1, Math.min(state.tagUi.roundIndex || 1, count));
    return rounds;
  }

  function copyCarouselRoundOverrides(source) {
    return Object.fromEntries(carouselFieldGroups().map((field) => [field.key, (source?.overrides?.[field.key] || []).slice(0, field.max)]));
  }

  function editInheritedSelection(values, value, max) {
    const next = values.slice();
    const index = next.indexOf(value);
    if (index >= 0) { next.splice(index, 1); return next; }
    if (next.length >= max) next.shift();
    next.push(value);
    return next;
  }

  function renderCarouselRoundEditor() {
    const draft = ensureTagDraft(); const count = carouselCountValue(draft);
    if (!count || draft.visual_carousel?.[0] !== "是") return "";
    const rounds = ensureCarouselRounds(draft); const current = rounds[state.tagUi.roundIndex - 1] || rounds[0];
    const fields = carouselFieldGroups(); const inherited = rounds[0];
    const openFields = carouselRoundOpenFields(current.index);
    const fieldMarkup = fields.map((field) => {
      const values = current.mode === "inherit" && current.index > 1 ? (inherited.overrides[field.key] || []) : (current.overrides[field.key] || []);
      const options = field.options;
      const isInherited = current.mode === "inherit" && current.index > 1;
      const selected = values;
      const max = field.max;
      const isOpen = openFields.has(field.key);
      return `<section class="carousel-round-field${isOpen ? " is-open" : ""}"><button type="button" class="carousel-round-field-toggle" data-carousel-field-toggle="${esc(field.key)}" aria-expanded="${isOpen}"><strong>${esc(field.label)}</strong><small>${isInherited ? "跟随第1轮" : "可选，留空由AI补全"}</small><span aria-hidden="true">⌄</span></button>${isOpen ? `<div class="tag-option-grid">${options.map((option) => optionButton(null, option, `round:${current.index}:${field.key}`, { selected: selected.includes(option.label), disabled: !selected.includes(option.label) && selected.length >= max && !isInherited })).join("")}</div>` : ""}</section>`;
    }).join("");
    return `<section class="carousel-round-editor"><div class="carousel-round-heading"><div><strong>逐轮创意定位</strong><small>固定 ${count} 屏；第2轮起默认继承第1轮，可随时改为自定义</small></div><span>仅最终生成时调用AI</span></div><div class="carousel-round-tabs">${rounds.map((round) => `<button type="button" class="${round.index === current.index ? "active" : ""}" data-carousel-round="${round.index}">第${round.index}轮${round.index > 1 && round.mode === "inherit" ? " · 继承" : ""}</button>`).join("")}</div>${current.index > 1 ? `<div class="carousel-round-mode"><button type="button" class="${current.mode === "inherit" ? "active" : ""}" data-carousel-mode="inherit">跟随第1轮</button><button type="button" class="${current.mode === "custom" ? "active" : ""}" data-carousel-mode="custom">本轮自定义</button></div>` : ""}<div class="carousel-round-fields">${fieldMarkup}</div></section>`;
  }

  function collectProject() {
    const tags = collectTagValues();
    return {
      name: state.project.name.trim() || "未命名创意",
      script_type: selectedScriptType(),
      task_description: els.description.value,
      aspect_ratio: $("[data-aspect].active")?.dataset.aspect || "16:9",
      creative_tags: tags,
    };
  }

  async function loadProjects() {
    const payload = await api(`/api/projects?search=${encodeURIComponent(els.search.value.trim())}`);
    state.projects = payload.projects;
    renderProjectList();
  }

  function renderProjectList() {
    if (!state.projects.length) {
      els.list.innerHTML = '<div style="padding:18px 10px;color:rgba(255,255,255,.4);font-size:11px">还没有创意项目</div>';
      return;
    }
    els.list.innerHTML = state.projects.map((item) => {
      const isActive = state.project?.id === item.id;
      const deleteButton = `<button type="button" class="project-delete-button" data-delete-project="${item.id}" aria-label="删除项目" title="删除项目">×</button>`;
      if (isActive) return `
        <div class="project-item-row"><div class="project-item active" data-project-id="${item.id}">
          <label class="project-item-name"><input data-project-name-input value="${esc(item.name)}" maxlength="120" aria-label="重命名当前项目"><span aria-hidden="true">编辑</span></label>
          <span><em>${esc(item.script_type)}</em><time>${esc(item.updated_at.slice(5, 16))}</time></span>
        </div>${deleteButton}</div>`;
      return `
        <div class="project-item-row"><button class="project-item" data-project-id="${item.id}">
          <strong>${esc(item.name)}</strong>
          <span><em>${esc(item.script_type)}</em><time>${esc(item.updated_at.slice(5, 16))}</time></span>
        </button>${deleteButton}</div>`;
    }).join("");
    const projectNameInput = els.list.querySelector("[data-project-name-input]");
    projectNameInput?.addEventListener("input", () => {
      state.project.name = projectNameInput.value;
      scheduleSave();
    });
  }

  async function createProject() {
    const payload = await api("/api/projects", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "未命名创意", script_type: "展示类" }),
    });
    await loadProjects();
    await openProject(payload.project.id);
    setProjectDrawer(true);
    setTimeout(() => els.list.querySelector("[data-project-name-input]")?.select(), 0);
  }

  async function openProject(projectId) {
    stopPolling();
    state.pinnedGeneratedBatch = null;
    await saveProject(true).catch(() => {});
    const payload = await api(`/api/projects/${projectId}`);
    state.project = payload.project;
    state.history = null;
    state.activeBatch = 0;
    state.tagUi.draft = null;
    state.tagUi.openKey = "";
    populateProject();
    renderProjectList();
    await loadHistory(true);
  }

  function populateProject() {
    const project = state.project;
    els.empty.classList.add("hidden");
    els.workspace.classList.remove("hidden");
    els.description.value = project.task_description || "";
    $$('[data-aspect]').forEach((button) => button.classList.toggle("active", button.dataset.aspect === project.aspect_ratio));
    renderTagControls();
    updateModeCopy();
    renderAdoption();
    els.saveState.textContent = "已保存";
    currentStep = state.history?.batches?.length ? 2 : 1;
    applyStep();
  }

  function applyStep() {
    if (!state.project) return;
    if (currentStep === 2 && state.tagUi.lastStep !== 2) { state.tagUi.openKey = ""; renderTagControls(); }
    state.tagUi.lastStep = currentStep;
    els.stepPosition.classList.toggle("hidden", currentStep !== 1);
    els.stepOutput.classList.toggle("hidden", currentStep !== 2);
    els.stepper.querySelectorAll("[data-step]").forEach((button) => {
      const step = Number(button.dataset.step);
      button.classList.toggle("active", step === currentStep);
      button.classList.toggle("done", step < currentStep);
      button.querySelector("span").textContent = step < currentStep ? "✓" : String(step);
    });
    const description = (els.description.value || "").trim();
    els.outputBriefSummary.textContent = description ? description.slice(0, 42) : "目标尚未填写";
    els.outputModeSummary.textContent = state.project.script_type || "展示类";
  }

  function scheduleSave() {
    if (!state.project) return;
    // A user edit starts a new positioning state; do not keep the prior
    // generation pinned after the user deliberately changes the inputs.
    state.pinnedGeneratedBatch = null;
    els.saveState.textContent = "保存中…";
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(() => saveProject(false).catch(() => {}), 650);
  }

  async function saveProject(quiet = false) {
    if (!state.project) return;
    if (state.saving) return state.savePromise || undefined;
    clearTimeout(state.saveTimer);
    state.saving = true;
    const savePromise = (async () => {
      try {
        const payload = await api(`/api/projects/${state.project.id}`, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectProject()),
        });
        state.project = payload.project;
        els.saveState.textContent = "已保存";
        applyStep();
        await loadProjects();
        if (!quiet) await loadHistory(false);
      } catch (error) {
        els.saveState.textContent = "保存失败";
        if (!quiet) toast(error.message, true);
        throw error;
      } finally {
        state.saving = false;
        state.savePromise = null;
      }
    })();
    state.savePromise = savePromise;
    return savePromise;
  }

  function updateModeCopy() {
    const visual = state.project?.script_type === "展示类" || $(".mode-button.active")?.dataset.scriptType === "展示类";
    els.descriptionLabel.textContent = visual ? "创意说明" : "任务描述";
    els.aspectField.classList.toggle("hidden", !visual);
    els.generateTitle.textContent = visual ? "AI视觉创意推荐" : "AI叙事创意推荐";
    els.generationHint.textContent = visual ? "每个定位最多生成2批，每批3套方案" : "每个定位最多生成2批，每批5个故事";
    els.generate.innerHTML = visual ? "<span>✦</span> 生成视觉方案" : "<span>✦</span> 生成叙事方案";
    els.resultsTitle.textContent = visual ? "视觉方案" : "叙事方案";
    if (state.project) { els.outputModeSummary.textContent = state.project.script_type; }
    applyStep();
  }

  async function loadHistory(selectLatest = false) {
    if (!state.project) return;
    const payload = await api(V2_GENERATION_ENDPOINTS.history(state.project.id));
    const history = normalizeV2History(payload?.history || payload);
    const adoptionPayload = await api(V2_GENERATION_ENDPOINTS.adoptionStatus(state.project.id));
    if (adoptionPayload?.snapshot) {
      history.adoption = {
        recommendation_kind: history.recommendation_kind,
        reference_id: String(adoptionPayload.scheme_id),
        snapshot: adoptionPayload.snapshot,
      };
    }
    const pinned = state.pinnedGeneratedBatch;
    if (pinned && !history.batches.some((batch) => Number(batch.id) === Number(pinned.id))) {
      const staleIndex = history.stale_batches.findIndex((batch) => Number(batch.id) === Number(pinned.id));
      if (staleIndex >= 0) {
        const [latestPinned] = history.stale_batches.splice(staleIndex, 1);
        history.batches = [latestPinned, ...history.batches];
        history.remaining_generations = Math.max(0, 2 - history.batches.length);
      }
    }
    state.history = history;
    if (selectLatest && history.batches.length) state.activeBatch = history.batches.length - 1;
    state.activeBatch = Math.max(0, Math.min(state.activeBatch, Math.max(0, history.batches.length - 1)));
    if (history.adoption) state.project.adoption = history.adoption;
    history.batches.forEach((batch) => (batch.items || []).forEach((item) => {
      const operation = item.operation || null;
      const operationId = Number(operation?.operation_id || 0);
      if (!operationId || ["completed", "failed", "blocked"].includes(operation.status)) return;
      state.operationIds.set(Number(item.id), operationId);
      state.operationStatus.set(Number(item.id), operation);
      state.continuingSchemes.add(Number(item.id));
      if (!state.operationPollTimers.has(Number(item.id))) {
        scheduleOperationPolling(Number(item.id), operationId);
      }
    }));
    renderHistory();
    if (history.batches.length && currentStep < 2) { currentStep = 2; applyStep(); }
  }

  function normalizeV2History(payload) {
    if (!Array.isArray(payload?.runs)) return payload;
    const runs = payload.runs.map((run) => ({
      id: run.run_id,
      run_id: run.run_id,
      batch_index: run.batch_index,
      use_case: run.use_case,
      status: run.status,
      aspect_ratio: run.aspect_ratio,
      items: (run.items || []).map((item) => ({
        ...item,
        id: item.scheme_id,
        title: item.title || `方案 ${item.scheme_index || item.item_index || ""}`,
        subtitle: item.core_idea || "",
        creative_description: item.image_description || item.ad_copy || "",
        core_subject: item.image_description || "",
        layout: item.core_idea || "",
        visual_style: item.ad_copy || "",
        image_status: item.image_state?.status,
        image_url: item.image_state?.image_url,
        image_error: item.image_state?.error_code,
        frames: (item.frames || []).map((frame) => ({
          ...frame,
          frame_index: frame.index ?? frame.frame_index,
          image_status: frame.image_state?.status,
          image_url: frame.image_state?.image_url,
          image_error: frame.image_state?.error_code,
        })),
      })),
    }));
    return {
      ...payload,
      batches: runs,
      stale_batches: [],
      remaining_generations: Math.max(0, 2 - runs.length),
      recommendation_kind: runs[0]?.use_case === "narrative" ? "narrative" : "visual",
    };
  }

  function renderHistory() {
    const history = state.history;
    if (!history) return;
    const openDetails = new Set(
      Array.from(els.resultsGrid.querySelectorAll("details[open][data-detail-key]"))
        .map((detail) => detail.dataset.detailKey)
        .filter(Boolean),
    );
    const hasAnything = history.batches.length || history.stale_batches.length;
    els.results.classList.toggle("hidden", !hasAnything);
    els.resultsMeta.textContent = `${history.batches.length} 批当前结果 · 剩余 ${history.remaining_generations} 次`;
    els.batchTabs.innerHTML = history.batches.map((batch, index) => `
      <button class="${index === state.activeBatch ? "active" : ""}" data-batch="${index}">第${batch.batch_index}批</button>`).join("");
    els.batchTabs.querySelectorAll("[data-batch]").forEach((button) => {
      button.addEventListener("click", () => { state.activeBatch = Number(button.dataset.batch); renderHistory(); });
    });
    const batch = history.batches[state.activeBatch];
    if (!batch) {
      els.resultsGrid.className = "results-grid";
      els.resultsGrid.innerHTML = '<div style="grid-column:1/-1;padding:26px;text-align:center;color:#748079">当前定位还没有结果，可生成一批新方案。</div>';
    } else if (history.recommendation_kind === "visual") {
      renderVisualBatch(batch);
    } else {
      renderNarrativeBatch(batch);
    }
    renderStale(history.stale_batches);
    renderAdoption();
    els.resultsGrid.querySelectorAll("details[data-detail-key]").forEach((detail) => {
      detail.open = openDetails.has(detail.dataset.detailKey);
    });
    updateGenerateState();
    schedulePolling();
  }

  function renderVisualBatch(batch) {
    if (batch.items.some((item) => item && typeof item.static_frame === "object")) {
      renderStaticVisualBatch(batch);
      return;
    }
    els.resultsGrid.className = "results-grid";
    els.resultsGrid.innerHTML = batch.items.map((item, index) => {
      const image = visualImageMarkup(item);
      const sources = (item.reference_sources || []).map((source) => `${esc(source.name)}：${esc(source.note)}`).join("<br>");
      const frames = Array.isArray(item.frames) ? item.frames : (Array.isArray(item.carousel?.frames) ? item.carousel.frames : []);
      const operation = state.operationStatus.get(Number(item.id)) || item.operation || null;
      const operationSummary = operation ? `<div class="operation-status">${esc(operation.status === "completed" ? "已完成" : operation.status === "blocked" ? "需要重试" : "后台生成中")} · ${esc(operation.completed_frame_count)}/${esc(operation.total_frame_count)} 张</div>` : "";
      const frameSummary = frames.length > 1 ? `<div class="display-frames"><b>画面路线（${frames.length}张）</b>${operationSummary}${frames.map((frame) => `<div class="display-frame-row"><div>第${esc(frame.frame_index)}张：${esc(frame.planned_content)} · ${displayFrameStatusLabel(frame.image_status)}</div>${frame.image_status === "success" && frame.image_url ? `<img class="display-frame-image" src="${esc(frame.image_url)}" data-image-url="${esc(frame.image_url)}" alt="第${esc(frame.frame_index)}张轮播画面">` : ""}</div>`).join("")}</div>` : "";
      return `<article class="creative-card">
        ${image}
        <div class="card-body">
          <div class="card-kicker">CONCEPT ${String(index + 1).padStart(2, "0")}</div>
          <h3>${esc(item.title)}</h3><p class="subtitle">${esc(item.subtitle)}</p>
          <p class="description">${esc(item.creative_description)}</p>
          <details class="detail-list" data-detail-key="visual:${item.id}"><summary>查看方案细节</summary>
            <p><b>核心主体：</b>${esc(item.core_subject)}</p><p><b>画面布局：</b>${esc(item.layout)}</p>
            <p><b>视觉风格：</b>${esc(item.visual_style)}</p><p><b>内容延展：</b>${esc((item.content_extensions || []).join("；"))}</p>
            <p><b>参考来源：</b><br>${sources}</p>
            ${frameSummary}
          </details>
          <div class="keywords">${(item.keywords || []).map((key) => `<span>${esc(key)}</span>`).join("")}</div>
          <div class="card-actions">
            ${imageActionMarkup(item)}
            ${frames.length > 1 ? `<button data-continue-scheme="${item.id}" ${state.continuingSchemes.has(item.id) ? "disabled" : ""}>${state.continuingSchemes.has(item.id) ? "继续生成中…" : "继续生成"}</button>` : ""}
            <button data-adopt-visual="${item.id}">${isAdopted("visual", String(item.id)) ? "已采用" : "采用此方案"}</button>
          </div>
        </div></article>`;
    }).join("");
    els.resultsGrid.querySelectorAll("[data-image-url]").forEach((image) => image.addEventListener("click", () => openImage(image.dataset.imageUrl)));
    els.resultsGrid.querySelectorAll("[data-carousel-prev], [data-carousel-next]").forEach((button) => button.addEventListener("click", () => {
      const itemId = Number(button.dataset.carouselPrev || button.dataset.carouselNext);
      const item = batch.items.find((entry) => Number(entry.id) === itemId);
      const count = item && Array.isArray(item.frames) && item.frames.length ? item.frames.length : 1;
      const current = state.carouselIndexes.get(itemId) || 0;
      const delta = button.hasAttribute("data-carousel-next") ? 1 : -1;
      state.carouselIndexes.set(itemId, (current + delta + count) % count);
      renderHistory();
    }));
    els.resultsGrid.querySelectorAll("[data-generate-image]").forEach((button) => button.addEventListener("click", () => generateSchemeImage(Number(button.dataset.generateImage), button)));
    els.resultsGrid.querySelectorAll("[data-retry-item]").forEach((button) => button.addEventListener("click", () => retryImage(Number(button.dataset.retryItem))));
    els.resultsGrid.querySelectorAll("[data-continue-scheme]").forEach((button) => button.addEventListener("click", () => continueScheme(Number(button.dataset.continueScheme))));
    els.resultsGrid.querySelectorAll("[data-adopt-visual]").forEach((button) => button.addEventListener("click", () => adoptVisual(Number(button.dataset.adoptVisual))));
  }

  function renderStaticVisualBatch(batch) {
    els.resultsGrid.className = "results-grid static-grid";
    els.resultsGrid.innerHTML = batch.items.map((item, index) => {
      const image = visualImageMarkup(item);
      const frame = item.static_frame || {};
      const copy = frame.copy || {};
      const evidence = item.evidence_ledger || {};
      const sources = (item.creative_sources || []).map((source) => `<li>${esc(source)}</li>`).join("");
      const confirmed = (evidence.confirmed || []).map((value) => `<li>${esc(value)}</li>`).join("");
      const inferred = (evidence.inferred || []).map((value) => `<li>${esc(value)}</li>`).join("");
      const toConfirm = (evidence.to_confirm || []).map((value) => `<li>${esc(value)}</li>`).join("");
      const attentionOrder = (frame.attention_order || []).map((value) => `<span>${esc(value)}</span>`).join("");
      const assets = (item.asset_plan || []).map((asset) => `<li><b>${esc(asset.asset)}</b> · ${esc(asset.status)} · ${esc(asset.fallback)}</li>`).join("");
      const risks = (item.production_risks || []).map((risk) => `<li><b>${esc(risk.risk)}</b> · ${esc(risk.mitigation)}</li>`).join("");
      return `<article class="creative-card static-creative-card">
        ${image}
        <div class="card-body">
          <div class="card-kicker">CONCEPT ${String(index + 1).padStart(2, "0")}</div>
          <h3>${esc(item.title)}</h3>
          <p class="subtitle">${esc(item.creative_summary)}</p>
          <details class="detail-list" data-detail-key="visual:${item.id}"><summary>查看方案细节</summary>
            <div class="static-positioning"><p><b>受众张力：</b>${esc(item.audience_tension)}</p><p><b>产品价值：</b>${esc(item.product_value)}</p><p><b>视觉机制：</b>${esc(item.visual_mechanism)}</p></div>
            <div><b>创意来源：</b><ul>${sources}</ul></div>
            <div class="evidence-ledger"><b>证据台账</b><p>已确认</p><ul>${confirmed}</ul><p>推断</p><ul>${inferred}</ul><p>待确认</p><ul>${toConfirm}</ul></div>
            <div class="static-frame-detail"><b>静态画面</b><p>${esc(frame.visual_event)}</p><p><b>主体：</b>${esc(frame.hero_subject)}</p><p><b>构图：</b>${esc(frame.composition)}</p><div class="attention-order">${attentionOrder}</div><p><b>媒介与美术：</b>${esc(frame.medium_and_art_direction)}</p><p><b>产品证明：</b>${esc((frame.product_proof || []).join("；"))}</p><p><b>缩小可读性：</b>${esc(frame.legibility_notes)}</p></div>
            <div class="static-copy"><b>文案</b><p>${esc(copy.headline)}</p>${copy.supporting_line ? `<p>${esc(copy.supporting_line)}</p>` : ""}<p>${esc(copy.brand_line)}</p>${copy.cta ? `<p>${esc(copy.cta)}</p>` : ""}</div>
            <div class="asset-plan"><b>素材计划</b><ul>${assets}</ul></div>
            <div class="production-risks"><b>制作风险</b><ul>${risks}</ul></div>
            <div class="review"><b>评审</b><p>${esc((item.review || {}).stop_reason)}</p><p>${esc((item.review || {}).why_make_next)}</p><p>${esc((item.review || {}).first_validation)}</p></div>
          </details>
          <div class="card-actions">
            ${imageActionMarkup(item)}
            <button data-adopt-visual="${item.id}">${isAdopted("visual", String(item.id)) ? "已采用" : "采用此方案"}</button>
          </div>
        </div></article>`;
    }).join("");
    els.resultsGrid.querySelectorAll("[data-image-url]").forEach((image) => image.addEventListener("click", () => openImage(image.dataset.imageUrl)));
    els.resultsGrid.querySelectorAll("[data-generate-image]").forEach((button) => button.addEventListener("click", () => generateSchemeImage(Number(button.dataset.generateImage), button)));
    els.resultsGrid.querySelectorAll("[data-retry-item]").forEach((button) => button.addEventListener("click", () => retryImage(Number(button.dataset.retryItem))));
    els.resultsGrid.querySelectorAll("[data-adopt-visual]").forEach((button) => button.addEventListener("click", () => adoptVisual(Number(button.dataset.adoptVisual))));
  }

  function visualImageMarkup(item) {
    const portrait = item.aspect_ratio === "9:16" ? " portrait" : "";
    const frames = Array.isArray(item.frames) && item.frames.length ? item.frames : [{ frame_index: 1, image_status: item.image_status, image_url: item.image_url, image_error: item.image_error }];
    const currentIndex = Math.min(state.carouselIndexes.get(Number(item.id)) || 0, frames.length - 1);
    const frame = frames[currentIndex];
    const image = frame.image_status === "success" && frame.image_url
      ? `<img src="${esc(frame.image_url)}" data-image-url="${esc(frame.image_url)}" alt="${esc(item.title)} 第${esc(frame.frame_index)}张画面">`
      : frame.image_status === "failed"
        ? `<div class="image-state">生成失败<br><small>${esc(frame.image_error || "可重试")}</small></div>`
        : `<div class="image-state${frame.image_status === "generating" ? " is-generating" : " is-pending"}">${frame.image_status === "generating" ? "AI参考图生成中" : "点击下方按钮生成参考图"}</div>`;
    const controls = frames.length > 1 ? `<button class="carousel-arrow prev" data-carousel-prev="${esc(item.id)}" aria-label="上一张">‹</button><span class="carousel-index">第${esc(frame.frame_index)}张 / ${frames.length}张</span><button class="carousel-arrow next" data-carousel-next="${esc(item.id)}" aria-label="下一张">›</button>` : "";
    return `<div class="image-frame${portrait} carousel-viewer">${image}${controls ? `<div class="carousel-controls">${controls}</div>` : ""}</div>`;
  }

  function imageActionMarkup(item) {
    const status = item.image_status || "pending";
    if (status === "success") return '<button class="image-action complete" type="button" disabled>参考图已完成</button>';
    if (status === "generating") return '<button class="image-action" type="button" disabled>参考图生成中…</button>';
    const label = status === "failed" ? "重试参考图" : "生成参考图";
    return `<button class="image-action" type="button" data-generate-image="${esc(item.id)}">${label}</button>`;
  }

  function renderNarrativeBatch(batch) {
    els.resultsGrid.className = "results-grid narrative-grid";
    els.resultsGrid.innerHTML = batch.items.map((item, index) => `<article class="creative-card story-card">
      <div class="card-kicker">STORY ${String(index + 1).padStart(2, "0")}</div><h3>${esc(item.story)}</h3>
      ${(item.hooks || []).map((hook, hookIndex) => `<div class="hook"><strong>钩子 ${hookIndex + 1} · ${esc(hook.text)}</strong><ol>${(hook.scenes || []).map((scene) => `<li>${esc(scene)}</li>`).join("")}</ol></div>`).join("")}
      <div class="card-actions"><button data-adopt-narrative="${item.id}">${isAdopted("narrative", String(item.id)) ? "已采用" : "采用此故事"}</button></div>
    </article>`).join("");
    els.resultsGrid.querySelectorAll("[data-adopt-narrative]").forEach((button) => button.addEventListener("click", () => {
      adoptNarrative(Number(button.dataset.adoptNarrative));
    }));
  }

  function renderStale(batches) {
    els.stale.classList.toggle("hidden", !batches.length);
    els.staleBody.innerHTML = batches.map((batch) => `<div class="stale-batch"><h4>旧定位 · 第${batch.batch_index}批 · ${esc(batch.created_at)}</h4><ul>${batch.items.map((item) => `<li>${esc(item.title || item.story || "方案")}</li>`).join("")}</ul></div>`).join("");
  }

  function isAdopted(kind, referenceId) {
    return state.project?.adoption?.recommendation_kind === kind && state.project?.adoption?.reference_id === referenceId;
  }

  function renderAdoption() {
    const adoption = state.project?.adoption;
    els.adoption.classList.toggle("hidden", !adoption);
    if (!adoption) return;
    const snapshot = adoption.snapshot || {};
    els.adoption.innerHTML = `<strong>✓ 当前采用方案</strong><p>${esc(snapshot.title || snapshot.story || "已采用方案")} · ${adoption.recommendation_kind === "visual" ? "展示类" : "叙事类"}</p>`;
  }

  function displayFrameStatusLabel(status) {
    return ({ queued: "排队中", pending: "等待中", generating: "生成中", success: "已完成", failed: "生成失败" })[status] || "处理中";
  }

  function updateGenerateState() {
    if (!state.history) return;
    els.generate.disabled = state.history.remaining_generations <= 0;
    if (state.history.remaining_generations <= 0) els.generate.textContent = "当前定位已生成2批";
    else if (state.history.batches.length) els.generate.innerHTML = `<span>✦</span> 再生成一批（剩余${state.history.remaining_generations}次）`;
    else updateModeCopy();
  }

  function formatGenerationElapsed(elapsedMs) {
    const elapsedSeconds = Math.max(0, Math.floor(elapsedMs / 1000));
    const seconds = elapsedSeconds % 60;
    const minutes = Math.floor(elapsedSeconds / 60) % 60;
    const hours = Math.floor(elapsedSeconds / 3600);
    const clock = [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
    return hours ? clock : clock.slice(3);
  }

  function updateGenerationWaitLabel() {
    if (!state.generationStartedAt) return;
    els.generate.innerHTML = `<span>✦</span> 正在生成文字方案 · 已等待 ${formatGenerationElapsed(Date.now() - state.generationStartedAt)}`;
  }

  function startGenerationWait() {
    clearInterval(state.generationTimer);
    state.generationStartedAt = Date.now();
    updateGenerationWaitLabel();
    state.generationTimer = setInterval(updateGenerationWaitLabel, 1000);
  }

  function stopGenerationWait() {
    clearInterval(state.generationTimer);
    state.generationTimer = 0;
    state.generationStartedAt = 0;
  }

  async function generate() {
    try {
      startGenerationWait();
      els.generate.disabled = true;
      await saveProject(true);
      updateGenerationWaitLabel();
      const generated = await api(V2_GENERATION_ENDPOINTS.run(state.project.id), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_description: els.description.value,
          aspect_ratio: $("[data-aspect].active")?.dataset.aspect || "16:9",
          creative_tags: collectTagValues(),
        }),
      });
      state.activeRunId = Number(generated.run?.id ?? generated.run_id ?? generated.id ?? 0);
      // The generate response already contains the validated text schemes.
      // Paint them immediately; history reload then reconciles image statuses.
      if (generated?.batches) {
        state.history = generated;
        state.activeBatch = Math.max(0, generated.batches.length - 1);
        state.pinnedGeneratedBatch = generated.batches[generated.batches.length - 1] || null;
        renderHistory();
      }
      await loadHistory(true);
      await loadProjects();
      toast("方案已生成，请点击卡片按钮生成参考图");
    } catch (error) {
      toast(error.message, true);
      await loadHistory(false).catch(() => {});
    } finally {
      stopGenerationWait();
      updateGenerateState();
    }
  }

  async function retryImage(itemId) {
    await generateSchemeImage(itemId);
  }

  async function generateSchemeImage(itemId, button = null) {
    if (state.operationIds.has(itemId)) return;
    if (button) { button.disabled = true; button.textContent = "提交中…"; }
    try {
      const payload = await api(V2_GENERATION_ENDPOINTS.schemeImage(itemId), { method: "POST" });
      const attempt = payload.attempt || payload;
      const attemptId = Number(payload.attempt_id || attempt.attempt_id || attempt.id || 0);
      await loadHistory(false);
      if (attemptId && !["success", "completed"].includes(String(payload.status || attempt.status || "").toLowerCase())) {
        state.operationIds.set(itemId, attemptId);
        state.operationStatus.set(itemId, attempt);
        pollImageAttempt(itemId, attemptId);
        toast("参考图生成中");
      } else {
        toast("参考图已完成");
      }
    } catch (error) {
      if (button) { button.disabled = false; button.textContent = "重试参考图"; }
      toast(error.message, true);
    }
  }

  async function pollImageAttempt(itemId, attemptId) {
    try {
      const payload = await api(V2_GENERATION_ENDPOINTS.imageAttempt(attemptId));
      const attempt = payload.attempt || payload;
      state.operationStatus.set(itemId, attempt);
      await loadHistory(false);
      const status = String(attempt.status || "").toLowerCase();
      if (["success", "completed", "failed", "blocked", "error"].includes(status)) {
        state.operationIds.delete(itemId);
        state.operationStatus.delete(itemId);
        state.operationPollTimers.delete(itemId);
        toast(status === "success" || status === "completed" ? "参考图已完成" : "参考图生成失败，请重试", status !== "success" && status !== "completed");
        return;
      }
      const timer = setTimeout(() => pollImageAttempt(itemId, attemptId), 1200);
      state.operationPollTimers.set(itemId, timer);
    } catch (_) {
      const timer = setTimeout(() => pollImageAttempt(itemId, attemptId), 2000);
      state.operationPollTimers.set(itemId, timer);
    }
  }

  async function continueScheme(itemId) {
    if (state.continuingSchemes.has(itemId)) return;
    state.continuingSchemes.add(itemId);
    renderHistory();
    try {
      toast("正在按方案路线生成后续画面");
      const item = state.history?.batches?.flatMap((batch) => batch.items || []).find((entry) => Number(entry.id) === Number(itemId));
      const frames = item?.frames || item?.carousel?.frames || [];
      const frame = frames.find((entry) => ["queued", "pending", "failed"].includes(entry.image_status));
      if (!frame) return;
      const frameIndex = Number(frame.frame_index ?? frame.index ?? 1);
      const payload = await api(frameIndex <= 1 ? V2_GENERATION_ENDPOINTS.schemeImage(itemId) : V2_GENERATION_ENDPOINTS.frameImage(itemId, frameIndex), { method: "POST" });
      const operationId = Number(payload.operation?.operation_id || payload.operation?.id || 0);
      if (operationId) {
        state.operationIds.set(itemId, operationId);
        state.operationStatus.set(itemId, payload.operation);
        scheduleOperationPolling(itemId, operationId);
      }
      await loadHistory(false);
    } catch (error) {
      state.continuingSchemes.delete(itemId);
      toast(error.message, true);
      await loadHistory(false).catch(() => {});
    }
  }

  async function adoptVisual(itemId) {
    try {
      const payload = await api(V2_GENERATION_ENDPOINTS.adoption(state.project.id), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scheme_id: itemId }),
      });
      state.project.adoption = { recommendation_kind: "visual", reference_id: String(itemId), snapshot: payload.snapshot };
      renderHistory(); await loadProjects();
    } catch (error) { toast(error.message, true); }
  }

  async function adoptNarrative(schemeId) {
    try {
      const payload = await api(V2_GENERATION_ENDPOINTS.adoption(state.project.id), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scheme_id: schemeId }),
      });
      state.project.adoption = { recommendation_kind: "narrative", reference_id: String(schemeId), snapshot: payload.snapshot };
      renderHistory(); await loadProjects();
    } catch (error) { toast(error.message, true); }
  }

  function schedulePolling() {
    stopImagePolling();
    if (state.activeRunId) {
      state.pollTimer = setTimeout(async () => {
        try {
          const payload = await api(V2_GENERATION_ENDPOINTS.runStatus(state.activeRunId));
          const run = payload.run || payload;
          if (["success", "completed", "failed", "error"].includes(String(run.status || "").toLowerCase())) state.activeRunId = 0;
          await loadHistory(false);
        } catch (_) { schedulePolling(); }
      }, 1500);
      return;
    }
    return;
  }

  function scheduleOperationPolling(itemId, operationId) {
    const existing = state.operationPollTimers.get(itemId);
    if (existing) clearTimeout(existing);
    const poll = async () => {
      try {
        const payload = await api(V2_GENERATION_ENDPOINTS.imageAttempt(operationId));
        const operation = payload.attempt || payload.operation || payload;
        state.operationStatus.set(itemId, operation);
        await loadHistory(false);
        if (["completed", "success", "failed", "blocked", "error"].includes(operation.status)) {
          state.continuingSchemes.delete(itemId);
          state.operationIds.delete(itemId);
          state.operationStatus.set(itemId, operation);
          state.operationPollTimers.delete(itemId);
          await loadHistory(false).catch(() => {});
          return;
        }
        const timer = setTimeout(poll, 2000);
        state.operationPollTimers.set(itemId, timer);
      } catch (_) {
        const timer = setTimeout(poll, 3000);
        state.operationPollTimers.set(itemId, timer);
      }
    };
    const timer = setTimeout(poll, 0);
    state.operationPollTimers.set(itemId, timer);
  }

  function stopPolling() {
    stopImagePolling();
    state.operationPollTimers.forEach((timer) => clearTimeout(timer));
    state.operationPollTimers.clear();
    state.operationIds.clear();
    state.operationStatus.clear();
    state.continuingSchemes.clear();
  }

  function stopImagePolling() { clearTimeout(state.pollTimer); state.pollTimer = 0; }

  async function deleteProject(projectId) {
    const index = state.projects.findIndex((item) => item.id === projectId);
    const target = state.projects[index];
    if (!target || !confirm(`确定删除“${target.name}”吗？`)) return;
    await api(`/api/projects/${projectId}`, { method: "DELETE" });
    const wasCurrent = state.project?.id === projectId;
    await loadProjects();
    if (!wasCurrent) { toast("项目已删除"); return; }
    const nextProject = state.projects[index] || null;
    const previousProject = state.projects[index - 1] || null;
    const fallbackProject = nextProject || previousProject;
    if (fallbackProject) await openProject(fallbackProject.id);
    else {
      state.project = null; state.history = null; stopPolling();
      els.workspace.classList.add("hidden"); els.empty.classList.remove("hidden");
    }
    toast("项目已删除");
  }

  function openImage(url) { els.dialogImage.src = url; els.imageDialog.showModal(); }

  function bindEvents() {
    // Keep dynamically rendered account forms aligned with the server policy.
    if (document.querySelector("#newUserPassword")) document.querySelector("#newUserPassword").minLength = 3;
    els.loginForm.addEventListener("submit", async (event) => {
      event.preventDefault(); if (els.loginButton.disabled) return; els.loginButton.disabled = true;
      try {
        const payload = await api("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: $("#loginUsername").value, password: $("#loginPassword").value }) });
        $("#loginPassword").value = "";
        if (payload.user?.must_change_password) { state.auth = payload.user; showPasswordChange(); }
        else await enterApp(payload.user);
      } catch (error) { els.authMessage.textContent = error.message; } finally { els.loginButton.disabled = false; }
    });
    els.passwordForm.addEventListener("submit", async (event) => {
      event.preventDefault(); if (els.passwordButton.disabled) return;
      if ($("#newPassword").value !== $("#confirmPassword").value) { toast("两次输入的新密码不一致", true); return; }
      els.passwordButton.disabled = true;
      try { await api("/api/auth/password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_password: $("#currentPassword").value, new_password: $("#newPassword").value }) }); $("#currentPassword").value = ""; $("#newPassword").value = ""; $("#confirmPassword").value = ""; showLogin("密码已更新，请使用新密码登录"); }
      catch (error) { toast(error.message, true); } finally { els.passwordButton.disabled = false; }
    });
    els.logout.addEventListener("click", async () => { try { await api("/api/auth/logout", { method: "POST" }); } catch (_) {} showLogin("已退出登录"); });
    els.adminUsersButton.addEventListener("click", async () => { els.adminDialog.showModal(); try { await loadAdminUsers(); } catch (error) { toast(error.message, true); } });
    els.closeAdminButton.addEventListener("click", () => els.adminDialog.close());
    els.openCreateUserButton.addEventListener("click", () => els.createUserDialog.showModal());
    [els.closeCreateUserButton, els.cancelCreateUserButton].forEach((button) => button.addEventListener("click", () => els.createUserDialog.close()));
    [els.adminUserSearch, els.adminRoleFilter].forEach((input) => input.addEventListener("input", loadAdminUsers));
    els.createUserForm.addEventListener("submit", async (event) => { event.preventDefault(); const form = els.createUserForm; const button = form.querySelector("button[type=submit]"); if ($("#newUserPassword").value !== $("#newUserPasswordConfirm").value) { toast("两次输入的密码不一致", true); return; } button.disabled = true; try { await api("/api/admin/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: $("#newUsername").value, password: $("#newUserPassword").value }) }); form.reset(); els.createUserDialog.close(); await loadAdminUsers(); toast("账号已创建"); } catch (error) { toast(error.message, true); } finally { button.disabled = false; } });
    els.adminUsersList.addEventListener("click", async (event) => { const button = event.target.closest("button[data-user-action]"); if (!button) return; const id = button.dataset.userId; const actionType = button.dataset.userAction; if (actionType === "delete" && !window.confirm("确定删除该普通账号吗？该账号的项目将变为未分配状态。")) return; button.disabled = true; try { if (actionType === "edit") { const username = window.prompt("修改登录账号", button.dataset.username || ""); if (!username || username === button.dataset.username) { button.disabled = false; return; } await api(`/api/admin/users/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username }) }); toast("账号已更新"); } else if (actionType === "delete") { await api(`/api/admin/users/${id}/delete`, { method: "POST" }); toast("账号已删除"); } else if (actionType === "toggle") { const action = button.dataset.active === "true" ? "disable" : "enable"; await api(`/api/admin/users/${id}/${action}`, { method: "POST" }); toast("账号状态已更新"); } else { const payload = await api(`/api/admin/users/${id}/reset-password`, { method: "POST" }); window.prompt("请立即保存这次显示的临时密码", payload.temporary_password || ""); } await loadAdminUsers(); } catch (error) { toast(error.message, true); } finally { button.disabled = false; } });
    $("#newProjectButton").addEventListener("click", createProject);
    $("#emptyNewButton").addEventListener("click", createProject);
    els.list.addEventListener("click", (event) => {
      const deleteButton = event.target.closest("[data-delete-project]");
      if (deleteButton) {
        event.stopPropagation();
        deleteProject(Number(deleteButton.dataset.deleteProject)).catch((error) => toast(error.message, true));
        return;
      }
      const projectButton = event.target.closest("button[data-project-id]");
      if (projectButton) openProject(Number(projectButton.dataset.projectId)).catch((error) => toast(error.message, true));
    });
    els.projectMenu.addEventListener("click", () => setProjectDrawer(!els.sidebar.classList.contains("drawer-open")));
    els.sidebarBackdrop.addEventListener("click", () => setProjectDrawer(false));
    els.positionNext.addEventListener("click", async () => { await saveProject(true).catch(() => {}); currentStep = 2; applyStep(); await loadHistory(false).catch(() => {}); });
    els.outputEdit.addEventListener("click", () => { currentStep = 1; applyStep(); });
    els.stepper.querySelectorAll("[data-step]").forEach((button) => button.addEventListener("click", () => { currentStep = Number(button.dataset.step); applyStep(); }));
    els.generate.addEventListener("click", generate);
    els.search.addEventListener("input", () => { clearTimeout(els.search.timer); els.search.timer = setTimeout(loadProjects, 250); });
    [els.description].forEach((input) => input.addEventListener("input", () => { applyStep(); scheduleSave(); }));
    els.tagControls.addEventListener("click", (event) => {
      const info = event.target.closest("[data-tooltip]");
      if (info) { event.stopPropagation(); toast(info.dataset.tooltip); return; }
      const editTag = event.target.closest("[data-edit-tag]");
      if (editTag) { state.tagUi.confirmed.delete(editTag.dataset.editTag); renderTagControls(); return; }
      const removeTag = event.target.closest("[data-remove-tag-key]");
      if (removeTag) {
        const draft = collectTagValues();
        const key = removeTag.dataset.removeTagKey;
        draft[key] = (draft[key] || []).filter((value) => value !== removeTag.dataset.removeTagValue);
        const group = (state.tagConfig[activeTagMode()]?.groups || []).find((item) => item.key === key || item.secondary_key === key);
        if (group?.secondary_key && key === group.key && !(draft[group.key] || []).length && (draft[group.secondary_key] || []).length) draft[group.key] = [draft[group.secondary_key].shift()];
        state.tagUi.draft = draft;
        if (group) state.tagUi.confirmed.delete(group.key);
        renderTagControls(); scheduleSave(); return;
      }
      const confirmTag = event.target.closest("[data-confirm-tag]");
      if (confirmTag) {
        const key = confirmTag.dataset.confirmTag;
        const group = (state.tagConfig[activeTagMode()]?.groups || []).find((item) => item.key === key);
        if (!group || (group.required && !groupSelectedValues(group).length)) { toast("请至少选择一项"); return; }
        state.tagUi.confirmed.add(key); renderTagControls(); scheduleSave(); return;
      }
      const clear = event.target.closest("[data-clear-tag]");
      if (clear) { const draft = collectTagValues(); draft[clear.dataset.clearTag] = []; state.tagUi.draft = draft; renderTagControls(); scheduleSave(); return; }
      const carouselChoice = event.target.closest("[data-carousel-choice]");
      if (carouselChoice) {
        const draft = collectTagValues(); const value = carouselChoice.dataset.carouselChoice;
        draft.visual_carousel = [value];
        if (value === "否") { draft.visual_carousel_count = []; draft.visual_carousel_form = []; draft.visual_carousel_rounds = []; }
        state.tagUi.draft = draft; state.tagUi.confirmed.delete("visual_carousel"); renderTagControls(); scheduleSave(); return;
      }
      const carouselRound = event.target.closest("[data-carousel-round]");
      if (carouselRound) { state.tagUi.roundIndex = Number(carouselRound.dataset.carouselRound); renderTagControls(); return; }
      const carouselFieldToggle = event.target.closest("[data-carousel-field-toggle]");
      if (carouselFieldToggle) {
        const openFields = carouselRoundOpenFields(); const key = carouselFieldToggle.dataset.carouselFieldToggle;
        if (openFields.has(key)) openFields.delete(key); else openFields.add(key);
        renderTagControls(); return;
      }
      const carouselMode = event.target.closest("[data-carousel-mode]");
      if (carouselMode) {
        const draft = collectTagValues(); const rounds = ensureCarouselRounds(draft); const current = rounds[state.tagUi.roundIndex - 1];
        if (current && current.index > 1) {
          const round = current;
          if (carouselMode.dataset.carouselMode === "inherit") {
            round.mode = "inherit";
            round.overrides = {};
          } else {
            round.mode = "custom";
            round.overrides = copyCarouselRoundOverrides(rounds[0]);
          }
        }
        state.tagUi.draft = draft;
        renderTagControls(); scheduleSave(); return;
      }
      const roundOption = event.target.closest("[data-tag-key^='round:'][data-tag-value]");
      if (roundOption) {
        const [, indexText, key] = roundOption.dataset.tagKey.split(":"); const index = Number(indexText); const draft = collectTagValues(); const rounds = ensureCarouselRounds(draft); const round = rounds[index - 1]; const field = carouselFieldGroups().find((item) => item.key === key);
        if (round && field) {
          const inherited = index > 1 && round.mode === "inherit";
          const sourceValues = inherited ? (rounds[0].overrides[key] || []) : (round.overrides[key] || []);
          round.overrides[key] = inherited ? editInheritedSelection(sourceValues, roundOption.dataset.tagValue, field.max) : selectWithinLimit(sourceValues, roundOption.dataset.tagValue, field.max);
          if (inherited) round.mode = "custom";
        }
        state.tagUi.draft = draft; renderTagControls(); scheduleSave(); return;
      }
      const option = event.target.closest("[data-tag-key][data-tag-value]");
      if (option) {
        const key = option.dataset.tagKey; const value = option.dataset.tagValue; const draft = collectTagValues(); const current = draft[key] || [];
        const group = (state.tagConfig[activeTagMode()]?.groups || []).find((item) => item.key === key || item.secondary_key === key);
        if (group?.type === "primary_secondary" || group?.secondary_key === key) {
          const main = draft[group.key] || []; const secondary = draft[group.secondary_key] || [];
          const mainIndex = main.indexOf(value); const secondaryIndex = secondary.indexOf(value);
          if (mainIndex >= 0) main.splice(mainIndex, 1);
          else if (secondaryIndex >= 0) secondary.splice(secondaryIndex, 1);
          else {
            if (main.length < (group.main_max || 0)) main.push(value);
            else if (secondary.length < (group.secondary_max || 0)) secondary.push(value);
          }
          if (!main.length && secondary.length) main.push(secondary.shift());
          draft[group.key] = main; draft[group.secondary_key] = secondary;
        } else {
          const max = key === "visual_art_style_references" ? 2 : (group?.max || group?.main_max || 1);
          draft[key] = selectWithinLimit(current, value, max);
        }
        if (key === "visual_art_style_relevance") { draft.visual_art_style = []; draft.visual_art_style_references = []; }
        if (key === "visual_art_style") draft.visual_art_style_references = [];
        if (key === "visual_carousel" && value === "否") { draft.visual_carousel_count = []; draft.visual_carousel_form = []; draft.visual_carousel_rounds = []; }
        if (key === "visual_product_selling_points") draft.visual_display_contents = (draft.visual_display_contents || []).filter((item) => item);
        state.tagUi.draft = draft; renderTagControls(); scheduleSave(); return;
      }
      const header = event.target.closest("[data-open-chapter]");
      if (header) { state.tagUi.openKey = state.tagUi.openKey === header.dataset.openChapter ? "" : header.dataset.openChapter; renderTagControls(); return; }
    });
    els.tagControls.addEventListener("change", (event) => {
      if (event.target.id !== "scriptTypeSelect") return;
      state.project.script_type = event.target.value;
      state.tagUi.draft = null;
      state.tagUi.confirmed.clear();
      state.tagUi.confirmationProjectId = 0;
      renderTagControls(); updateModeCopy(); scheduleSave();
    });
    $$('[data-aspect]').forEach((button) => button.addEventListener("click", () => {
      $$('[data-aspect]').forEach((item) => item.classList.toggle("active", item === button)); scheduleSave();
    }));
    $("#closeImageDialog").addEventListener("click", () => els.imageDialog.close());
    els.imageDialog.addEventListener("click", (event) => { if (event.target === els.imageDialog) els.imageDialog.close(); });
  }

  async function init() {
    bindEvents();
    try {
      const payload = await api("/api/auth/status");
      if (!payload.authenticated) { showLogin(); return; }
      if (payload.user?.must_change_password) { state.auth = payload.user; showPasswordChange(); return; }
      await enterApp(payload.user);
    } catch (error) { showLogin(error.message || "请登录"); }
  }

  init();
})();
