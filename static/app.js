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
    saving: false,
    tagConfig: null,
    tagUi: { openKey: "", query: "", confirmed: new Set(), confirmationProjectId: 0, confirmationScriptType: "", lastStep: 0, roundIndex: 1 },
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const els = {
    authGate: $("#authGate"), appShell: $("#appShell"), loginForm: $("#loginForm"), passwordForm: $("#passwordForm"), authMessage: $("#authMessage"), loginButton: $("#loginButton"), passwordButton: $("#passwordButton"), userBar: $("#userBar"), currentUserLabel: $("#currentUserLabel"), logout: $("#logoutButton"), adminUsersButton: $("#adminUsersButton"), adminDialog: $("#adminDialog"), closeAdminButton: $("#closeAdminButton"), adminUsersList: $("#adminUsersList"), createUserForm: $("#createUserForm"),
    empty: $("#emptyState"), workspace: $("#projectWorkspace"), list: $("#projectList"), sidebar: $("#projectSidebar"), sidebarBackdrop: $("#sidebarBackdrop"),
    search: $("#projectSearch"), taskType: $("#taskType"),
    description: $("#taskDescription"), descriptionLabel: $("#descriptionLabel"),
    evidence: $("#productEvidence"), aspectField: $("#aspectField"), files: $("#referenceFiles"),
    tagControls: $("#tagControls"),
    fileInput: $("#referenceFileInput"), saveState: $("#saveState"), generate: $("#generateButton"),
    generateTitle: $("#generateTitle"), generationHint: $("#generationHint"),
    results: $(".results-section"), resultsGrid: $("#resultsGrid"), resultsTitle: $("#resultsTitle"),
    resultsMeta: $("#resultsMeta"), batchTabs: $("#batchTabs"), stale: $("#staleResults"),
    staleBody: $("#staleResultsBody"), adoption: $("#adoptionPanel"), toast: $("#toast"),
    imageDialog: $("#imageDialog"), dialogImage: $("#dialogImage"),
    stepper: $("#stepper"), stepBrief: $("#stepBrief"), stepPosition: $("#stepPosition"), stepOutput: $("#stepOutput"),
    briefNext: $("#briefNextButton"), positionBack: $("#positionBackButton"), positionNext: $("#positionNextButton"), outputEdit: $("#outputEditButton"),
    projectMenu: $("#projectMenuButton"), briefSummary: $("#briefSummary"), briefProjectName: $("#briefProjectName"), briefTaskType: $("#briefTaskType"), briefDescription: $("#briefDescription"), briefScriptType: $("#briefScriptType"), briefAspect: $("#briefAspect"), outputBriefSummary: $("#outputBriefSummary"), outputModeSummary: $("#outputModeSummary"),
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
    els.adminUsersList.innerHTML = (payload.users || []).map((user) => `<div class="admin-user"><div><strong>${esc(user.username)}</strong><small>${user.is_active ? "启用" : "已停用"}</small></div><div class="admin-user-actions"><button class="ghost" data-user-action="toggle" data-user-id="${user.id}" data-active="${user.is_active}">${user.is_active ? "停用" : "启用"}</button><button class="ghost" data-user-action="reset" data-user-id="${user.id}">重置密码</button></div></div>`).join("") || "暂无普通账号";
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
        if (allowedIds.size) draft.visual_display_contents = (draft.visual_display_contents || []).filter((label) => {
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
    return Array.from(categories.entries()).map(([category, items]) => `<section class="tag-category"><div class="tag-category-header"><strong>${esc(category)}</strong><small>${items.length} 项</small></div><div class="tag-option-grid">${items.map((option) => optionButton(group, option, key, { selected: selected.includes(option.label), disabled: !selected.includes(option.label) && selected.length >= max })).join("")}</div></section>`).join("");
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
      if (!groupSelectedValues(group, draft).length) state.tagUi.confirmed.delete(group.key);
    });
  }

  function renderReportTable(group, key, options, maxOverride = null, selectedOverride = null) {
    const draft = ensureTagDraft();
    const selected = selectedOverride ? new Set(selectedOverride) : new Set(draft[key] || []);
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

  function renderSelectedChips(group, draft) {
    const keys = group.key === "visual_target_audiences" || group.key === "target_audiences" ? [group.key, group.secondary_key] : [group.key];
    const values = keys.flatMap((key) => (draft[key] || []).map((value) => `<button type="button" class="selected-report-value" data-remove-tag-key="${esc(key)}" data-remove-tag-value="${esc(value)}">${esc(displayTagLabel(value))} ×</button>`));
    return values.length ? `<div class="selected-report-values">${values.join("、")}</div>` : "";
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
    // A completed chapter is represented only by the top summary; editing restores its report.
    if (confirmed && selected.length) return "";
    const body = confirmed ? "" : `${renderSelectedChips(group, draft)}${renderReportBody(group, options, draft)}`;
    const limit = group.type === "style_cascade" ? 2 : (group.main_max || group.max || 1) + (group.secondary_max || 0);
    return `<section class="creative-position-report${confirmed ? " is-confirmed" : ""}" data-tag-report="${esc(key)}"><div class="creative-position-report-title"><h3>${esc(label)}</h3>${confirmed ? "" : `<button type="button" class="report-confirm-button" data-confirm-tag="${esc(key)}">确认</button>`}<span class="creative-position-limit-hint">最多选择${esc(limit)}项</span></div>${confirmed ? `<div class="report-summary-line">${esc(status)}</div>` : `<div class="creative-position-tables">${body}</div>`}</section>`;
  }

  function renderStyleChapter(group, draft) {
    const relevance = draft.visual_art_style_relevance || []; const styles = group.options.filter((option) => !relevance.length || relevance.includes(option.category)); const selectedStyle = draft.visual_art_style || []; const currentStyle = group.options.find((option) => selectedStyle.includes(option.label)); const refs = currentStyle?.references || [];
    return `<div class="cascade-step"><strong>1 · 与产品视觉的相关度</strong><div class="tag-option-grid">${Array.from(new Set(group.options.map((option) => option.category))).map((value) => optionButton(group, { label: value, description: "一级相关度，用于表达与真实产品视觉的距离" }, "visual_art_style_relevance", { selected: relevance.includes(value) })).join("")}</div></div><div class="cascade-step"><strong>2 · 具体美术风格</strong><div class="tag-option-grid">${styles.map((option) => optionButton(group, option, "visual_art_style", { selected: selectedStyle.includes(option.label) })).join("")}</div></div>${currentStyle ? `<div class="cascade-step"><strong>3 · 参考作品 <small>可选，最多 2 项</small></strong><div class="tag-option-grid">${refs.map((option) => optionButton(group, option, "visual_art_style_references", { selected: (draft.visual_art_style_references || []).includes(option.label), disabled: !(draft.visual_art_style_references || []).includes(option.label) && (draft.visual_art_style_references || []).length >= 2 })).join("")}</div></div>` : ""}`;
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
        if (allowedIds.size) groupOptions = groupOptions.filter((option) => allowedIds.has(option.id));
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
    const summary = visibleChapters.filter((chapter) => state.tagUi.confirmed.has(chapter.key) && groupSelectedValues(chapter.group, draft).length).map((chapter) => `<div><b>${esc(chapter.label)}：</b>${esc(groupSummaryText(chapter.group, draft))}</div>`).join("");
    const editButtons = visibleChapters.filter((chapter) => state.tagUi.confirmed.has(chapter.key) && groupSelectedValues(chapter.group, draft).length).map((chapter) => `<button type="button" class="report-edit-button" data-edit-tag="${esc(chapter.key)}">修改${esc(chapter.label)}</button>`).join("");
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
    return [
      { key: "visual_product_selling_points", label: "产品卖点", max: 2, options: groups.find((group) => group.key === "visual_product_selling_points")?.options || [] },
      { key: "visual_display_contents", label: "展示内容", max: 2, options: groups.find((group) => group.key === "visual_display_contents")?.options || [] },
      { key: "visual_motif", label: "视觉母题", max: 1, options: groups.find((group) => group.key === "visual_motif")?.options || [] },
    ];
  }

  function ensureCarouselRounds(draft = ensureTagDraft()) {
    const count = carouselCountValue(draft);
    if (!count) { draft.visual_carousel_rounds = []; state.tagUi.roundIndex = 1; return []; }
    const fields = carouselFieldGroups();
    const topLevel = Object.fromEntries(fields.map((field) => [field.key, (draft[field.key] || []).slice(0, field.max)]));
    const existing = Array.isArray(draft.visual_carousel_rounds) ? draft.visual_carousel_rounds : [];
    const byIndex = new Map(existing.map((item) => [Number(item.index), item]));
    const rounds = Array.from({ length: count }, (_, offset) => {
      const index = offset + 1; const item = byIndex.get(index);
      if (item) return { index, mode: index === 1 ? "base" : (item.mode === "custom" ? "custom" : "inherit"), overrides: Object.fromEntries(fields.map((field) => [field.key, Array.isArray(item.overrides?.[field.key]) ? item.overrides[field.key].slice(0, field.max) : []])) };
      return { index, mode: index === 1 ? "base" : "inherit", overrides: index === 1 ? topLevel : Object.fromEntries(fields.map((field) => [field.key, []])) };
    });
    draft.visual_carousel_rounds = rounds;
    state.tagUi.roundIndex = Math.max(1, Math.min(state.tagUi.roundIndex || 1, count));
    return rounds;
  }

  function renderCarouselRoundEditor() {
    const draft = ensureTagDraft(); const count = carouselCountValue(draft);
    if (!count || draft.visual_carousel?.[0] !== "是") return "";
    const rounds = ensureCarouselRounds(draft); const current = rounds[state.tagUi.roundIndex - 1] || rounds[0];
    const fields = carouselFieldGroups(); const inherited = rounds[0];
    const fieldMarkup = fields.map((field) => {
      const values = current.mode === "inherit" && current.index > 1 ? (inherited.overrides[field.key] || []) : (current.overrides[field.key] || []);
      const options = field.options;
      return `<section class="carousel-round-field"><div class="carousel-round-field-heading"><strong>${esc(field.label)}</strong><small>${current.mode === "inherit" && current.index > 1 ? "跟随第1轮" : "可选，留空由AI补全"}</small></div><div class="tag-option-grid">${options.map((option) => optionButton(null, option, `round:${current.index}:${field.key}`, { selected: values.includes(option.label), disabled: !values.includes(option.label) && values.length >= field.max })).join("")}</div></section>`;
    }).join("");
    return `<section class="carousel-round-editor"><div class="carousel-round-heading"><div><strong>逐轮创意定位</strong><small>固定 ${count} 屏；第2轮起默认继承第1轮，可随时改为自定义</small></div><span>仅最终生成时调用AI</span></div><div class="carousel-round-tabs">${rounds.map((round) => `<button type="button" class="${round.index === current.index ? "active" : ""}" data-carousel-round="${round.index}">第${round.index}轮${round.index > 1 && round.mode === "inherit" ? " · 继承" : ""}</button>`).join("")}</div>${current.index > 1 ? `<div class="carousel-round-mode"><button type="button" class="${current.mode === "inherit" ? "active" : ""}" data-carousel-mode="inherit">跟随第1轮</button><button type="button" class="${current.mode === "custom" ? "active" : ""}" data-carousel-mode="custom">本轮自定义</button></div>` : ""}<div class="carousel-round-fields">${fieldMarkup}</div></section>`;
  }

  function collectProject() {
    const tags = collectTagValues();
    return {
      name: state.project.name.trim() || "未命名创意",
      script_type: selectedScriptType(),
      task_type: els.taskType.value,
      task_description: els.description.value,
      product_evidence_summary: els.evidence.value,
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
      if (isActive) return `
        <div class="project-item active" data-project-id="${item.id}">
          <label class="project-item-name"><input data-project-name-input value="${esc(item.name)}" maxlength="120" aria-label="重命名当前项目"><span aria-hidden="true">编辑</span></label>
          <span><em>${esc(item.script_type)}</em><time>${esc(item.updated_at.slice(5, 16))}</time></span>
        </div>`;
      return `
        <button class="project-item" data-project-id="${item.id}">
          <strong>${esc(item.name)}</strong>
          <span><em>${esc(item.script_type)}</em><time>${esc(item.updated_at.slice(5, 16))}</time></span>
        </button>`;
    }).join("");
    els.list.querySelectorAll("button[data-project-id]").forEach((button) => {
      button.addEventListener("click", () => openProject(Number(button.dataset.projectId)));
    });
    const projectNameInput = els.list.querySelector("[data-project-name-input]");
    projectNameInput?.addEventListener("input", () => {
      state.project.name = projectNameInput.value;
      els.briefProjectName.textContent = projectNameInput.value.trim() || "未命名创意";
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
    els.briefProjectName.textContent = project.name;
    els.taskType.value = project.task_type || "";
    els.description.value = project.task_description || "";
    els.evidence.value = project.product_evidence_summary || "";
    $$('[data-aspect]').forEach((button) => button.classList.toggle("active", button.dataset.aspect === project.aspect_ratio));
    renderTagControls();
    renderFiles();
    updateModeCopy();
    renderAdoption();
    els.saveState.textContent = "已保存";
    currentStep = state.history?.batches?.length ? 3 : (project.task_description ? 2 : 1);
    applyStep();
  }

  function applyStep() {
    if (!state.project) return;
    if (currentStep === 2 && state.tagUi.lastStep !== 2) { state.tagUi.openKey = ""; renderTagControls(); }
    state.tagUi.lastStep = currentStep;
    els.stepBrief.classList.toggle("hidden", currentStep !== 1);
    els.stepPosition.classList.toggle("hidden", currentStep !== 2);
    els.stepOutput.classList.toggle("hidden", currentStep !== 3);
    els.briefSummary.classList.toggle("hidden", currentStep === 3);
    els.stepper.querySelectorAll("[data-step]").forEach((button) => {
      const step = Number(button.dataset.step);
      button.classList.toggle("active", step === currentStep);
      button.classList.toggle("done", step < currentStep);
      button.querySelector("span").textContent = step < currentStep ? "✓" : String(step);
    });
    const description = (els.description.value || "").trim();
    els.briefTaskType.textContent = els.taskType.value.trim() || "尚未填写";
    els.briefDescription.textContent = description || "尚未填写";
    els.briefScriptType.textContent = state.project.script_type || "展示类";
    els.briefAspect.textContent = state.project.aspect_ratio === "9:16" ? "竖版 9:16" : "横版 16:9";
    els.outputBriefSummary.textContent = description ? description.slice(0, 42) : "目标尚未填写";
    els.outputModeSummary.textContent = state.project.script_type || "展示类";
  }

  function renderFiles() {
    const files = state.project?.reference_files || [];
    els.files.innerHTML = files.map((file) => `<span class="file-chip">${esc(file.original_name)} · ${formatBytes(file.size_bytes)}</span>`).join("");
  }

  function formatBytes(value) {
    const bytes = Number(value || 0);
    return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))}KB` : `${(bytes / 1024 / 1024).toFixed(1)}MB`;
  }

  function scheduleSave() {
    if (!state.project) return;
    els.saveState.textContent = "保存中…";
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(() => saveProject(false), 650);
  }

  async function saveProject(quiet = false) {
    if (!state.project || state.saving) return;
    clearTimeout(state.saveTimer);
    state.saving = true;
    try {
      const payload = await api(`/api/projects/${state.project.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectProject()),
      });
      state.project = payload.project;
      els.saveState.textContent = "已保存";
      els.briefProjectName.textContent = state.project.name;
      applyStep();
      await loadProjects();
      if (!quiet) await loadHistory(false);
    } catch (error) {
      els.saveState.textContent = "保存失败";
      if (!quiet) toast(error.message, true);
      throw error;
    } finally {
      state.saving = false;
    }
  }

  function updateModeCopy() {
    const visual = state.project?.script_type === "展示类" || $(".mode-button.active")?.dataset.scriptType === "展示类";
    els.descriptionLabel.textContent = visual ? "创意说明" : "任务描述";
    els.aspectField.classList.toggle("hidden", !visual);
    els.generateTitle.textContent = visual ? "AI视觉创意推荐" : "AI叙事创意推荐";
    els.generationHint.textContent = visual ? "每个定位最多生成2批，每批3套方案" : "每个定位最多生成2批，每批5个故事";
    els.generate.innerHTML = visual ? "<span>✦</span> 生成视觉方案" : "<span>✦</span> 生成叙事方案";
    els.resultsTitle.textContent = visual ? "视觉方案" : "叙事方案";
    if (state.project) { els.briefScriptType.textContent = state.project.script_type; els.outputModeSummary.textContent = state.project.script_type; }
    applyStep();
  }

  async function loadHistory(selectLatest = false) {
    if (!state.project) return;
    const history = await api(`/api/projects/${state.project.id}/history`);
    state.history = history;
    if (selectLatest && history.batches.length) state.activeBatch = history.batches.length - 1;
    state.activeBatch = Math.max(0, Math.min(state.activeBatch, Math.max(0, history.batches.length - 1)));
    if (history.adoption) state.project.adoption = history.adoption;
    renderHistory();
    if (history.batches.length && currentStep < 3) { currentStep = 3; applyStep(); }
  }

  function renderHistory() {
    const history = state.history;
    if (!history) return;
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
    updateGenerateState();
    schedulePolling();
  }

  function renderVisualBatch(batch) {
    els.resultsGrid.className = "results-grid";
    els.resultsGrid.innerHTML = batch.items.map((item, index) => {
      const image = visualImageMarkup(item);
      const sources = (item.reference_sources || []).map((source) => `${esc(source.name)}：${esc(source.note)}`).join("<br>");
      const frames = Array.isArray(item.carousel_frames) && item.carousel_frames.length > 1 ? `<div class="carousel-result"><b>轮播定位</b>${item.carousel_frames.map((frame) => `<span>第${esc(frame)}轮</span>`).join("")}</div>` : "";
      const resolvedTags = item.resolved_tags && typeof item.resolved_tags === "object" ? Object.entries(item.resolved_tags).filter(([, values]) => Array.isArray(values) && values.length).map(([key, values]) => `<div><b>${esc({ visual_product_selling_points: "产品卖点", visual_display_contents: "展示内容", visual_motif: "视觉母题" }[key] || key)}：</b>${esc(values.join("、"))}</div>`).join("") : "";
      return `<article class="creative-card">
        ${image}
        <div class="card-body">
          <div class="card-kicker">CONCEPT ${String(index + 1).padStart(2, "0")}</div>
          <h3>${esc(item.title)}</h3><p class="subtitle">${esc(item.subtitle)}</p>
          <p class="description">${esc(item.creative_description)}</p>
          <details class="detail-list"><summary>查看方案细节</summary>
            <p><b>核心主体：</b>${esc(item.core_subject)}</p><p><b>画面布局：</b>${esc(item.layout)}</p>
            <p><b>视觉风格：</b>${esc(item.visual_style)}</p><p><b>内容延展：</b>${esc((item.content_extensions || []).join("；"))}</p>
            <p><b>参考来源：</b><br>${sources}</p>
            ${frames}${resolvedTags ? `<div class="resolved-tags"><b>最终定位（用户未填写项由AI补全）：</b>${resolvedTags}</div>` : ""}
          </details>
          <div class="keywords">${(item.keywords || []).map((key) => `<span>${esc(key)}</span>`).join("")}</div>
          <div class="card-actions">
            ${item.image_status === "failed" ? `<button data-retry-item="${item.id}">重新生成此图</button>` : ""}
            <button data-adopt-visual="${item.id}">${isAdopted("visual", String(item.id)) ? "已采用" : "采用此方案"}</button>
          </div>
        </div></article>`;
    }).join("");
    els.resultsGrid.querySelectorAll("[data-image-url]").forEach((image) => image.addEventListener("click", () => openImage(image.dataset.imageUrl)));
    els.resultsGrid.querySelectorAll("[data-retry-item]").forEach((button) => button.addEventListener("click", () => retryImage(Number(button.dataset.retryItem))));
    els.resultsGrid.querySelectorAll("[data-adopt-visual]").forEach((button) => button.addEventListener("click", () => adoptVisual(Number(button.dataset.adoptVisual))));
  }

  function visualImageMarkup(item) {
    const portrait = item.aspect_ratio === "9:16" ? " portrait" : "";
    if (item.image_status === "success") return `<div class="image-frame${portrait}"><img src="${esc(item.image_url)}?v=${Date.now()}" data-image-url="${esc(item.image_url)}" alt="${esc(item.title)} AI参考图"></div>`;
    if (item.image_status === "failed") return `<div class="image-frame${portrait}"><div class="image-state">生成失败<br><small>${esc(item.image_error || "可单独重试")}</small></div></div>`;
    return `<div class="image-frame${portrait}"><div class="image-state"><i></i>${item.image_status === "generating" ? "AI参考图生成中" : "AI参考图排队中"}</div></div>`;
  }

  function renderNarrativeBatch(batch) {
    els.resultsGrid.className = "results-grid narrative-grid";
    els.resultsGrid.innerHTML = batch.items.map((item, index) => `<article class="creative-card story-card">
      <div class="card-kicker">STORY ${String(index + 1).padStart(2, "0")}</div><h3>${esc(item.story)}</h3>
      ${(item.hooks || []).map((hook, hookIndex) => `<div class="hook"><strong>钩子 ${hookIndex + 1} · ${esc(hook.text)}</strong><ol>${(hook.scenes || []).map((scene) => `<li>${esc(scene)}</li>`).join("")}</ol></div>`).join("")}
      <div class="card-actions"><button data-adopt-narrative="${batch.id}:${index}">${isAdopted("narrative", `${batch.id}:${index}`) ? "已采用" : "采用此故事"}</button></div>
    </article>`).join("");
    els.resultsGrid.querySelectorAll("[data-adopt-narrative]").forEach((button) => button.addEventListener("click", () => {
      const [generationId, itemIndex] = button.dataset.adoptNarrative.split(":").map(Number);
      adoptNarrative(generationId, itemIndex);
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

  function updateGenerateState() {
    if (!state.history) return;
    els.generate.disabled = state.history.remaining_generations <= 0;
    if (state.history.remaining_generations <= 0) els.generate.textContent = "当前定位已生成2批";
    else if (state.history.batches.length) els.generate.innerHTML = `<span>✦</span> 再生成一批（剩余${state.history.remaining_generations}次）`;
    else updateModeCopy();
  }

  async function generate() {
    try {
      await saveProject(true);
      els.generate.disabled = true;
      els.generate.textContent = "正在生成文字方案…";
      state.history = await api(`/api/projects/${state.project.id}/generate`, { method: "POST" });
      state.activeBatch = Math.max(0, state.history.batches.length - 1);
      renderHistory();
      await loadProjects();
      toast("方案已生成，参考图会继续在后台完成");
    } catch (error) {
      toast(error.message, true);
      await loadHistory(false).catch(() => {});
    } finally {
      updateGenerateState();
    }
  }

  async function retryImage(itemId) {
    try {
      await api(`/api/visual-items/${itemId}/retry`, { method: "POST" });
      toast("已重新生成这张参考图");
      await loadHistory(false);
    } catch (error) { toast(error.message, true); }
  }

  async function adoptVisual(itemId) {
    try {
      const payload = await api(`/api/projects/${state.project.id}/adopt`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ recommendation_kind: "visual", item_id: itemId }),
      });
      state.project.adoption = { recommendation_kind: "visual", reference_id: String(itemId), snapshot: payload.snapshot };
      renderHistory(); await loadProjects();
    } catch (error) { toast(error.message, true); }
  }

  async function adoptNarrative(generationId, itemIndex) {
    try {
      const payload = await api(`/api/projects/${state.project.id}/adopt`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ recommendation_kind: "narrative", generation_id: generationId, item_index: itemIndex }),
      });
      state.project.adoption = { recommendation_kind: "narrative", reference_id: `${generationId}:${itemIndex}`, snapshot: payload.snapshot };
      renderHistory(); await loadProjects();
    } catch (error) { toast(error.message, true); }
  }

  function schedulePolling() {
    stopPolling();
    const batch = state.history?.batches?.[state.activeBatch];
    if (state.history?.recommendation_kind !== "visual" || !batch) return;
    if (batch.items.some((item) => ["queued", "generating"].includes(item.image_status))) {
      state.pollTimer = setTimeout(async () => {
        try { await loadHistory(false); } catch (_) { schedulePolling(); }
      }, 2000);
    }
  }

  function stopPolling() { clearTimeout(state.pollTimer); state.pollTimer = 0; }

  async function uploadFiles(files) {
    for (const file of files) {
      try {
        await api(`/api/projects/${state.project.id}/files`, {
          method: "POST", headers: { "Content-Type": file.type || "application/octet-stream", "X-File-Name": encodeURIComponent(file.name) }, body: file,
        });
        toast(`已添加 ${file.name}`);
      } catch (error) { toast(`${file.name}：${error.message}`, true); }
    }
    const payload = await api(`/api/projects/${state.project.id}`);
    state.project = payload.project; renderFiles();
  }

  async function deleteProject() {
    if (!state.project || !confirm(`确定删除“${state.project.name}”吗？`)) return;
    await api(`/api/projects/${state.project.id}`, { method: "DELETE" });
    state.project = null; state.history = null; stopPolling();
    els.workspace.classList.add("hidden"); els.empty.classList.remove("hidden");
    await loadProjects(); toast("项目已删除");
  }

  function openImage(url) { els.dialogImage.src = `${url}?v=${Date.now()}`; els.imageDialog.showModal(); }

  function bindEvents() {
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
    els.createUserForm.addEventListener("submit", async (event) => { event.preventDefault(); const button = event.currentTarget.querySelector("button[type=submit]"); button.disabled = true; try { await api("/api/admin/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: $("#newUsername").value, password: $("#newUserPassword").value }) }); event.currentTarget.reset(); await loadAdminUsers(); toast("账号已创建"); } catch (error) { toast(error.message, true); } finally { button.disabled = false; } });
    els.adminUsersList.addEventListener("click", async (event) => { const button = event.target.closest("button[data-user-action]"); if (!button) return; const id = button.dataset.userId; button.disabled = true; try { if (button.dataset.userAction === "toggle") { const action = button.dataset.active === "true" ? "disable" : "enable"; await api(`/api/admin/users/${id}/${action}`, { method: "POST" }); toast("账号状态已更新"); } else { const payload = await api(`/api/admin/users/${id}/reset-password`, { method: "POST" }); window.prompt("请立即保存这次显示的临时密码", payload.temporary_password || ""); } await loadAdminUsers(); } catch (error) { toast(error.message, true); } finally { button.disabled = false; } });
    $("#newProjectButton").addEventListener("click", createProject);
    $("#emptyNewButton").addEventListener("click", createProject);
    $("#deleteProjectButton").addEventListener("click", deleteProject);
    els.projectMenu.addEventListener("click", () => setProjectDrawer(!els.sidebar.classList.contains("drawer-open")));
    els.sidebarBackdrop.addEventListener("click", () => setProjectDrawer(false));
    els.briefNext.addEventListener("click", () => { currentStep = 2; applyStep(); });
    els.positionBack.addEventListener("click", () => { currentStep = 1; applyStep(); });
    els.positionNext.addEventListener("click", async () => { await saveProject(true).catch(() => {}); currentStep = 3; applyStep(); await loadHistory(false).catch(() => {}); });
    els.outputEdit.addEventListener("click", () => { currentStep = 2; applyStep(); });
    els.stepper.querySelectorAll("[data-step]").forEach((button) => button.addEventListener("click", () => { currentStep = Number(button.dataset.step); applyStep(); }));
    els.generate.addEventListener("click", generate);
    els.search.addEventListener("input", () => { clearTimeout(els.search.timer); els.search.timer = setTimeout(loadProjects, 250); });
    [els.taskType, els.description, els.evidence].forEach((input) => input.addEventListener("input", () => { applyStep(); scheduleSave(); }));
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
        if (!group || !groupSelectedValues(group).length) { toast("请至少选择一项"); return; }
        state.tagUi.confirmed.add(key); renderTagControls(); scheduleSave(); return;
      }
      const clear = event.target.closest("[data-clear-tag]");
      if (clear) { const draft = collectTagValues(); draft[clear.dataset.clearTag] = []; state.tagUi.draft = draft; renderTagControls(); scheduleSave(); return; }
      const carouselRound = event.target.closest("[data-carousel-round]");
      if (carouselRound) { state.tagUi.roundIndex = Number(carouselRound.dataset.carouselRound); renderTagControls(); return; }
      const carouselMode = event.target.closest("[data-carousel-mode]");
      if (carouselMode) {
        const draft = collectTagValues(); const rounds = ensureCarouselRounds(draft); const current = rounds[state.tagUi.roundIndex - 1];
        if (current && current.index > 1) { current.mode = carouselMode.dataset.carouselMode; if (current.mode === "inherit") current.overrides = Object.fromEntries(carouselFieldGroups().map((field) => [field.key, []])); }
        state.tagUi.draft = draft;
        if (group && groupSelectedValues(group, draft).length) state.tagUi.confirmed.add(group.key);
        renderTagControls(); scheduleSave(); return;
      }
      const roundOption = event.target.closest("[data-tag-key^='round:'][data-tag-value]");
      if (roundOption) {
        const [, indexText, key] = roundOption.dataset.tagKey.split(":"); const index = Number(indexText); const draft = collectTagValues(); const rounds = ensureCarouselRounds(draft); const round = rounds[index - 1]; const field = carouselFieldGroups().find((item) => item.key === key);
        if (round && field && (index === 1 || round.mode === "custom")) { const values = round.overrides[key] || []; const position = values.indexOf(roundOption.dataset.tagValue); if (position >= 0) values.splice(position, 1); else if (values.length < field.max) { if (field.max === 1) values.splice(0, values.length, roundOption.dataset.tagValue); else values.push(roundOption.dataset.tagValue); } round.overrides[key] = values; }
        state.tagUi.draft = draft; renderTagControls(); scheduleSave(); return;
      }
      const option = event.target.closest("[data-tag-key][data-tag-value]");
      if (option) {
        const key = option.dataset.tagKey; const value = option.dataset.tagValue; const draft = collectTagValues(); const current = draft[key] || [];
        const index = current.indexOf(value); const group = (state.tagConfig[activeTagMode()]?.groups || []).find((item) => item.key === key || item.secondary_key === key);
        if (group?.type === "primary_secondary" || group?.secondary_key === key) {
          const main = draft[group.key] || []; const secondary = draft[group.secondary_key] || [];
          const mainIndex = main.indexOf(value); const secondaryIndex = secondary.indexOf(value);
          if (mainIndex >= 0) main.splice(mainIndex, 1);
          else if (secondaryIndex >= 0) secondary.splice(secondaryIndex, 1);
          else {
            const totalMax = (group.main_max || 0) + (group.secondary_max || 0);
            if (main.length + secondary.length < totalMax) (main.length ? secondary : main).push(value);
          }
          if (!main.length && secondary.length) main.push(secondary.shift());
          draft[group.key] = main; draft[group.secondary_key] = secondary;
        } else {
          const max = group?.max || group?.main_max || 1;
          if (index >= 0) current.splice(index, 1); else if (current.length < max) { if (max === 1) current.splice(0, current.length, value); else current.push(value); }
          draft[key] = current;
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
    els.fileInput.addEventListener("change", () => { if (els.fileInput.files?.length) uploadFiles(Array.from(els.fileInput.files)); els.fileInput.value = ""; });
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
