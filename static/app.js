(() => {
  "use strict";

  const state = {
    projects: [],
    project: null,
    history: null,
    activeBatch: 0,
    saveTimer: 0,
    pollTimer: 0,
    saving: false,
    tagConfig: null,
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const els = {
    empty: $("#emptyState"), workspace: $("#projectWorkspace"), list: $("#projectList"),
    search: $("#projectSearch"), name: $("#projectName"), taskType: $("#taskType"),
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
    projectMenu: $("#projectMenuButton"), projectMenuName: $("#projectMenuName"), briefSummary: $("#briefSummary"), briefProjectName: $("#briefProjectName"), briefTaskType: $("#briefTaskType"), briefDescription: $("#briefDescription"), briefScriptType: $("#briefScriptType"), briefAspect: $("#briefAspect"), outputBriefSummary: $("#outputBriefSummary"), outputModeSummary: $("#outputModeSummary"),
  };

  let currentStep = 1;

  const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);

  async function api(path, options = {}) {
    const response = await fetch(path, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) throw new Error(payload.error || "请求失败");
    return payload;
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
    return ($(".mode-button.active")?.dataset.scriptType || state.project?.script_type) === "展示类" ? "visual" : "narrative";
  }

  function selectedValues(select) {
    if (!select) return [];
    return Array.from(select.options).filter((option) => option.selected).map((option) => option.value).filter(Boolean);
  }

  function optionMarkup(options, selected, { multiple = false, emptyLabel = "请选择" } = {}) {
    const selectedSet = new Set(selected || []);
    const categories = new Map();
    (options || []).forEach((option) => {
      const category = String(option.category || "未分组");
      if (!categories.has(category)) categories.set(category, []);
      categories.get(category).push(option);
    });
    const empty = multiple ? "" : `<option value="">${esc(emptyLabel)}</option>`;
    const body = Array.from(categories.entries()).map(([category, items]) => {
      const optionsHtml = items.map((option) => {
        const value = String(option.label || "");
        const hint = option.description || option.note || "";
        return `<option value="${esc(value)}" data-option-id="${esc(option.id)}" title="${esc(hint)}" ${selectedSet.has(value) ? "selected" : ""}>${esc(value)}</option>`;
      }).join("");
      return categories.size > 1 ? `<optgroup label="${esc(category)}">${optionsHtml}</optgroup>` : optionsHtml;
    }).join("");
    return empty + body;
  }

  function selectedOrLegacyOptions(options, selected) {
    const known = new Set((options || []).map((option) => String(option.label || "")));
    const legacy = (selected || []).filter((value) => !known.has(value)).map((value, index) => ({ id: `legacy-${index}`, label: value, category: "已有标签", description: "此标签来自旧项目数据" }));
    return [...legacy, ...(options || [])];
  }

  function renderPrimarySecondary(group, tags) {
    const main = selectedOrLegacyOptions(group.options, tags[group.key] || []);
    const secondary = selectedOrLegacyOptions(group.options, tags[group.secondary_key] || []);
    const mainLimit = group.main_max ? `最多${group.main_max}项` : "可选";
    const secondaryLimit = group.secondary_max ? `最多${group.secondary_max}项` : "可选";
    return `<div class="tag-group" data-tag-group="${esc(group.key)}">
      <div class="tag-group-header"><strong>${esc(group.label)}</strong><small>主选${esc(mainLimit)} · 辅助${esc(secondaryLimit)}</small></div>
      <label>主选<select data-tag-select="${esc(group.key)}">${optionMarkup(main, tags[group.key] || [])}</select></label>
      <label>辅助<select data-tag-select="${esc(group.secondary_key)}" data-tag-max="${esc(group.secondary_max || 0)}" multiple size="4">${optionMarkup(secondary, tags[group.secondary_key] || [], { multiple: true })}</select></label>
      <p class="tag-hint">按住 Ctrl（或 Command）可选择多个辅助标签；选项定义可悬停查看。</p>
    </div>`;
  }

  function renderTagControls() {
    if (!state.tagConfig || !state.project) return;
    const mode = activeTagMode();
    const tags = state.project.creative_tags || {};
    const groups = state.tagConfig[mode]?.groups || [];
    els.tagControls.innerHTML = groups.map((group) => {
      if (group.type === "primary_secondary") return renderPrimarySecondary(group, tags);
      if (group.type === "style_cascade") {
        const relevance = tags.visual_art_style_relevance || [];
        const styleOptions = selectedOrLegacyOptions(group.options, tags.visual_art_style || []);
        const selectedStyle = tags.visual_art_style || [];
        const currentStyle = group.options.find((option) => option.label === selectedStyle[0]);
        const relevanceOptions = Array.from(new Set(group.options.map((option) => option.category))).map((label, index) => ({ id: `relevance-${index}`, label, category: "相关度" }));
        const selectedRelevance = relevance.length ? relevance : (currentStyle ? [currentStyle.category] : []);
        const refs = currentStyle?.references || [];
        const selectedRefs = tags.visual_art_style_references || [];
        return `<div class="tag-group" data-tag-group="${esc(group.key)}">
          <div class="tag-group-header"><strong>${esc(group.label)}</strong><small>一级、二级必选 · 三级参考最多2项</small></div>
          <label>一级相关度<select data-tag-select="visual_art_style_relevance">${optionMarkup(relevanceOptions, selectedRelevance)}</select></label>
          <label>二级风格<select data-tag-select="visual_art_style" data-style-options>${optionMarkup(styleOptions, selectedStyle)}</select></label>
          <label>三级参考<select data-tag-select="visual_art_style_references" data-tag-max="2" data-style-ref-options multiple size="4">${optionMarkup(refs, selectedRefs, { multiple: true })}</select></label>
          <p class="tag-hint">三级参考用于建立视觉共识，不等于照搬作品；每个风格最多选择2项。</p>
        </div>`;
      }
      const selected = tags[group.key] || [];
      const options = selectedOrLegacyOptions(group.options, selected);
      const visible = group.visible_when ? " hidden" : "";
      return `<div class="tag-group${visible}" data-tag-group="${esc(group.key)}" data-visible-key="${esc(group.visible_when?.key || "")}" data-visible-values="${esc((group.visible_when?.values || []).join("|"))}">
        <div class="tag-group-header"><strong>${esc(group.label)}</strong><small>必选1项</small></div>
        <label>选择<select data-tag-select="${esc(group.key)}">${optionMarkup(options, selected)}</select></label>
      </div>`;
    }).join("");
    updateTagDependencies();
  }

  function refreshSelectOptions(select, options, selected) {
    const selectedValuesSet = new Set(selected || []);
    select.innerHTML = optionMarkup(selectedOrLegacyOptions(options, selected), selected, { multiple: select.multiple });
    Array.from(select.options).forEach((option) => { option.selected = selectedValuesSet.has(option.value); });
  }

  function updateTagDependencies() {
    const mode = activeTagMode();
    if (mode !== "visual") return;
    const groups = state.tagConfig?.visual?.groups || [];
    const tags = collectTagValues();
    const carousel = tags.visual_carousel?.[0] || "";
    $$('[data-visible-key]').forEach((group) => {
      const values = (group.dataset.visibleValues || "").split("|").filter(Boolean);
      const hidden = values.length > 0 && !values.includes(carousel);
      group.classList.toggle("hidden", hidden);
      if (hidden) group.querySelectorAll("[data-tag-select]").forEach((select) => {
        if (select.multiple) Array.from(select.options).forEach((option) => { option.selected = false; });
        else select.value = "";
      });
    });
    const displayGroup = groups.find((group) => group.key === "visual_display_contents");
    const displaySelect = $('[data-tag-select="visual_display_contents"]');
    if (displayGroup && displaySelect) {
      const sellGroup = groups.find((group) => group.key === "visual_product_selling_points");
      const selectedSellIds = new Set((tags.visual_product_selling_points || []).concat(tags.visual_secondary_product_selling_points || []).map((label) => sellGroup?.options.find((option) => option.label === label)?.id).filter(Boolean));
      const relation = state.tagConfig.visual.relations?.product_display || {};
      const allowedIds = new Set();
      selectedSellIds.forEach((id) => (relation[id] || []).forEach((displayId) => allowedIds.add(displayId)));
      const options = allowedIds.size ? displayGroup.options.filter((option) => allowedIds.has(option.id)) : displayGroup.options;
      const current = selectedValues(displaySelect);
      refreshSelectOptions(displaySelect, options, current.filter((value) => options.some((option) => option.label === value)));
      displaySelect.disabled = !options.length;
    }
    const styleGroup = groups.find((group) => group.key === "visual_art_style");
    const styleSelect = $('[data-tag-select="visual_art_style"]');
    const relevanceSelect = $('[data-tag-select="visual_art_style_relevance"]');
    const refsSelect = $('[data-tag-select="visual_art_style_references"]');
    if (styleGroup && styleSelect && relevanceSelect && refsSelect) {
      const relevance = relevanceSelect.value;
      const styleOptions = relevance ? styleGroup.options.filter((option) => option.category === relevance) : styleGroup.options;
      const currentStyle = styleSelect.value;
      refreshSelectOptions(styleSelect, styleOptions, styleOptions.some((option) => option.label === currentStyle) ? [currentStyle] : []);
      const style = styleOptions.find((option) => option.label === styleSelect.value);
      refreshSelectOptions(refsSelect, style?.references || [], selectedValues(refsSelect));
    }
  }

  function collectTagValues() {
    const tags = {};
    $$('[data-tag-select]').forEach((select) => { tags[select.dataset.tagSelect] = selectedValues(select); });
    return tags;
  }

  function limitMultiSelect(select) {
    if (!select?.multiple) return;
    const max = Number(select.dataset.tagMax || 0);
    if (!max) return;
    const selected = Array.from(select.options).filter((option) => option.selected);
    if (selected.length <= max) return;
    selected.slice(max).forEach((option) => { option.selected = false; });
    toast(`最多选择${max}项辅助标签`);
  }

  function collectProject() {
    const tags = collectTagValues();
    return {
      name: els.name.value.trim() || "未命名创意",
      script_type: $(".mode-button.active")?.dataset.scriptType || "展示类",
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
    els.list.innerHTML = state.projects.map((item) => `
      <button class="project-item ${state.project?.id === item.id ? "active" : ""}" data-project-id="${item.id}">
        <strong>${esc(item.name)}</strong>
        <span><em>${esc(item.script_type)}</em><time>${esc(item.updated_at.slice(5, 16))}</time></span>
      </button>`).join("");
    els.list.querySelectorAll("[data-project-id]").forEach((button) => {
      button.addEventListener("click", () => openProject(Number(button.dataset.projectId)));
    });
  }

  async function createProject() {
    const payload = await api("/api/projects", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "未命名创意", script_type: "展示类" }),
    });
    await loadProjects();
    await openProject(payload.project.id);
    setTimeout(() => els.name.select(), 0);
  }

  async function openProject(projectId) {
    stopPolling();
    await saveProject(true).catch(() => {});
    const payload = await api(`/api/projects/${projectId}`);
    state.project = payload.project;
    state.history = null;
    els.list.closest(".sidebar")?.classList.remove("drawer-open");
    state.activeBatch = 0;
    populateProject();
    renderProjectList();
    await loadHistory(true);
  }

  function populateProject() {
    const project = state.project;
    els.empty.classList.add("hidden");
    els.workspace.classList.remove("hidden");
    els.name.value = project.name;
    els.projectMenuName.textContent = project.name;
    els.briefProjectName.textContent = project.name;
    els.taskType.value = project.task_type || "";
    els.description.value = project.task_description || "";
    els.evidence.value = project.product_evidence_summary || "";
    $$(".mode-button").forEach((button) => button.classList.toggle("active", button.dataset.scriptType === project.script_type));
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
      els.projectMenuName.textContent = state.project.name;
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
    $("#newProjectButton").addEventListener("click", createProject);
    $("#emptyNewButton").addEventListener("click", createProject);
    $("#deleteProjectButton").addEventListener("click", deleteProject);
    els.projectMenu.addEventListener("click", () => els.list.closest(".sidebar")?.classList.toggle("drawer-open"));
    els.briefNext.addEventListener("click", () => { currentStep = 2; applyStep(); });
    els.positionBack.addEventListener("click", () => { currentStep = 1; applyStep(); });
    els.positionNext.addEventListener("click", async () => { await saveProject(true).catch(() => {}); currentStep = 3; applyStep(); await loadHistory(false).catch(() => {}); });
    els.outputEdit.addEventListener("click", () => { currentStep = 2; applyStep(); });
    els.stepper.querySelectorAll("[data-step]").forEach((button) => button.addEventListener("click", () => { currentStep = Number(button.dataset.step); applyStep(); }));
    els.generate.addEventListener("click", generate);
    els.search.addEventListener("input", () => { clearTimeout(els.search.timer); els.search.timer = setTimeout(loadProjects, 250); });
    [els.name, els.taskType, els.description, els.evidence].forEach((input) => input.addEventListener("input", () => { applyStep(); scheduleSave(); }));
    els.tagControls.addEventListener("change", (event) => {
      if (!event.target.matches("[data-tag-select]")) return;
      limitMultiSelect(event.target);
      updateTagDependencies();
      scheduleSave();
    });
    $$(".mode-button").forEach((button) => button.addEventListener("click", () => {
      $$(".mode-button").forEach((item) => item.classList.toggle("active", item === button));
      state.project.script_type = button.dataset.scriptType; renderTagControls(); updateModeCopy(); scheduleSave();
    }));
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
      const payload = await api("/api/tag-options");
      state.tagConfig = payload.config;
      await loadProjects();
      if (state.projects.length) await openProject(state.projects[0].id);
    } catch (error) { toast(error.message, true); }
  }

  init();
})();
