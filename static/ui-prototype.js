(() => {
  "use strict";

  const variants = {
    A: "三栏工作台",
    B: "分步创作流",
    C: "结果优先画板",
  };

  const projects = [
    { name: "剑侠传奇 · 新版本视觉", type: "展示类", time: "刚刚", status: "3 个方案" },
    { name: "情人节限定时装", type: "展示类", time: "18 分钟前", status: "生成中" },
    { name: "门派恩怨剧情钩子", type: "叙事类", time: "昨天", status: "已采用" },
    { name: "新服预约素材", type: "展示类", time: "周一", status: "6 个方案" },
    { name: "大侠回归故事线", type: "叙事类", time: "8 月 26 日", status: "草稿" },
    { name: "帮会战玩法演示", type: "展示类", time: "8 月 22 日", status: "已采用" },
  ];

  const concepts = [
    {
      no: "01",
      title: "一剑开天门",
      subtitle: "用极端尺度差，把新版本的力量升级变成第一眼冲击",
      tags: ["角色主导", "宏大场景", "实力证明"],
      hook: "巨剑劈开云海，地图与敌阵在剑锋下同时显现。",
      art: "art-one",
      score: "92",
    },
    {
      no: "02",
      title: "百派争锋录",
      subtitle: "以门派群像建立内容丰度，适合轮播和多卖点承载",
      tags: ["群像", "门派差异", "内容丰度"],
      hook: "六大门派在同一张英雄长卷中依次亮相。",
      art: "art-two",
      score: "88",
    },
    {
      no: "03",
      title: "江湖在掌中",
      subtitle: "从真实 UI 与装备细节切入，让视觉承诺落到产品证据",
      tags: ["UI 融合", "装备展示", "可玩性"],
      hook: "人物立于实机界面前，装备与地图像机关般逐层展开。",
      art: "art-three",
      score: "85",
    },
  ];

  const params = new URLSearchParams(window.location.search);
  const requestedVariant = String(params.get("variant") || "A").toUpperCase();
  const state = {
    variant: variants[requestedVariant] ? requestedVariant : "A",
    projectIndex: 0,
    mode: "展示类",
    selectedConcept: 0,
    adoptedConcept: null,
    inspector: "创意要求",
    step: 2,
    bView: "grid",
    bProjectOpen: false,
    bTaskFamily: "展示类",
    bTaskType: "新版本首曝素材",
    bProjectName: "剑侠传奇 · 新版本视觉",
    bGeneration: ["done", "done", "failed"],
    drawerOpen: true,
    batch: 1,
    tagCount: 5,
  };

  const root = document.querySelector("#prototypeRoot");
  const toastEl = document.querySelector("#prototypeToast");
  const variantLabel = document.querySelector("#variantLabel");
  const prototypeState = document.querySelector("#prototypeState");

  const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);

  const iconPaths = {
    sparkles: '<path d="m12 3-1.2 3.3L7.5 7.5l3.3 1.2L12 12l1.2-3.3 3.3-1.2-3.3-1.2L12 3Z"/><path d="m5 13-.8 2.2L2 16l2.2.8L5 19l.8-2.2L8 16l-2.2-.8L5 13Z"/><path d="m18 13-1 2.7-2.7 1 2.7 1L18 20l1-2.3 2.7-1-2.7-1L18 13Z"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    folder: '<path d="M3 6.5A2.5 2.5 0 0 1 5.5 4H9l2 2h7.5A2.5 2.5 0 0 1 21 8.5v8A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5v-10Z"/>',
    history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9" r="1.5"/><path d="m21 15-5-5L5 20"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    chevron: '<path d="m9 18 6-6-6-6"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    layers: '<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/>',
    upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
    close: '<path d="M6 6l12 12M18 6 6 18"/>',
    bolt: '<path d="m13 2-9 12h8l-1 8 9-12h-8l1-8Z"/>',
  };

  function icon(name, size = 18) {
    return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.sparkles}</svg>`;
  }

  function brand(compact = false) {
    return `<div class="brand-lockup${compact ? " compact" : ""}">
      <span class="brand-symbol">${icon("sparkles", 18)}</span>
      <span><strong>造境</strong><small>AI CREATIVE STUDIO</small></span>
    </div>`;
  }

  function modeSwitch(className = "") {
    return `<div class="mode-segment ${className}" role="tablist" aria-label="创意类型">
      ${["展示类", "叙事类"].map((mode) => `<button type="button" data-mode="${mode}" class="${state.mode === mode ? "active" : ""}">${mode === "展示类" ? icon("image", 15) : icon("file", 15)}${mode}</button>`).join("")}
    </div>`;
  }

  function projectItems(prefix = "") {
    return projects.map((project, index) => `<button type="button" data-project="${index}" class="project-row ${state.projectIndex === index ? "active" : ""}">
      <span class="project-thumb thumb-${(index % 3) + 1}">${index < 3 ? String(index + 1).padStart(2, "0") : icon("file", 14)}</span>
      <span class="project-copy"><strong>${esc(project.name)}</strong><small>${esc(project.type)} · ${esc(project.time)}</small></span>
      ${prefix === "status" ? `<em>${esc(project.status)}</em>` : ""}
    </button>`).join("");
  }

  function chips(items, tone = "") {
    return `<div class="chip-row">${items.map((item, index) => `<button type="button" data-action="tag" class="tag-chip ${tone} ${index < 2 ? "active" : ""}">${esc(item)}${index < 2 ? icon("check", 12) : ""}</button>`).join("")}</div>`;
  }

  function art(concept, wide = false) {
    return `<div class="concept-art ${concept.art} ${wide ? "wide" : ""}">
      <div class="art-grid"></div><div class="art-orb"></div><div class="art-figure"></div>
      <span class="art-index">${concept.no}</span><span class="art-type">AI 参考构图</span>
    </div>`;
  }

  function conceptCard(concept, index, style = "standard") {
    const selected = state.selectedConcept === index;
    const adopted = state.adoptedConcept === index;
    return `<article class="concept-card ${style} ${selected ? "selected" : ""}" data-concept="${index}" tabindex="0">
      ${art(concept, style === "gallery")}
      <div class="concept-body">
        <div class="concept-meta"><span>方向 ${concept.no}</span><em>匹配度 ${concept.score}</em></div>
        <h3>${esc(concept.title)}</h3>
        <p>${esc(concept.subtitle)}</p>
        <div class="concept-tags">${concept.tags.map((tag) => `<span>${esc(tag)}</span>`).join("")}</div>
        <div class="concept-actions">
          <button type="button" class="text-button" data-action="detail" data-concept="${index}">查看详情 ${icon("arrow", 14)}</button>
          <button type="button" class="adopt-button ${adopted ? "adopted" : ""}" data-action="adopt" data-concept="${index}">${adopted ? icon("check", 14) + "已采用" : "采用方向"}</button>
        </div>
      </div>
    </article>`;
  }

  function bConceptCard(concept, index) {
    const selected = state.selectedConcept === index;
    const adopted = state.adoptedConcept === index;
    const status = state.bGeneration[index] || "idle";
    const statusText = { idle: "待生成", queued: "排队中", generating: "生成中", done: "已完成", failed: "生成失败" }[status];
    return `<article class="b-result-card ${selected ? "selected" : ""} ${adopted ? "adopted" : ""}" data-concept="${index}" tabindex="0">
      <div class="b-result-art">${art(concept, true)}${status !== "done" && status !== "idle" ? `<div class="b-job-status ${status}"><span>${status === "failed" ? icon("close", 15) : icon("bolt", 15)}</span>${statusText}${status === "failed" ? `<button type="button" data-action="retry" data-concept="${index}">重试</button>` : ""}</div>` : ""}</div>
      <div class="b-result-body"><div class="b-result-kicker"><span>方向 ${concept.no}</span><em>${adopted ? "已采用" : statusText}</em></div><h3>${esc(concept.title)}</h3><p>${esc(concept.subtitle)}</p><button type="button" class="adopt-button ${adopted ? "adopted" : ""}" data-action="adopt" data-concept="${index}">${adopted ? icon("check", 14) + "已采用" : "采用方向"}</button></div>
    </article>`;
  }

  function inspectorContent() {
    if (state.inspector === "创意定位") {
      return `<div class="inspector-section">
        <div class="field-head"><label>产品卖点</label><span>主选 1 · 辅助 2</span></div>
        ${chips(["新职业登场", "门派对抗", "自由交易", "装备养成"])}
      </div>
      <div class="inspector-section">
        <div class="field-head"><label>展示内容</label><span>已按卖点过滤</span></div>
        ${chips(["职业技能", "门派群像", "实机战斗", "装备界面"], "soft")}
      </div>
      <div class="inspector-section">
        <div class="field-head"><label>美术方向</label><span>三级参考</span></div>
        <select aria-label="美术方向"><option>国风写意 · 电影感</option><option>新中式 · 极简留白</option></select>
        <div class="reference-pills"><span>英雄长卷 ×</span><span>东方奇观 ×</span></div>
      </div>`;
    }
    return `<div class="inspector-section">
      <label>任务类型</label>
      <input value="新版本首曝素材" aria-label="任务类型">
    </div>
    <div class="inspector-section">
      <label>一句话目标</label>
      <textarea rows="4" aria-label="一句话目标">突出新职业的压迫感和门派差异，让玩家第一眼感到版本内容量巨大。</textarea>
      <small class="field-note">建议只写一个传播目标，具体证据放到下方。</small>
    </div>
    <div class="inspector-section">
      <div class="field-head"><label>目标画幅</label><span>用于参考图</span></div>
      <div class="ratio-pills"><button type="button" class="active">16:9 横版</button><button type="button">9:16 竖版</button></div>
    </div>
    <div class="inspector-section evidence-box">
      <div>${icon("upload", 17)}<strong>添加产品证据</strong></div>
      <small>PNG、JPG、PDF · 仅显示假状态</small>
      <span class="file-pill">新职业技能截图.png <b>×</b></span>
    </div>`;
  }

  function variantA() {
    const project = projects[state.projectIndex];
    return `<div class="variant variant-a">
      <aside class="a-sidebar">
        ${brand()}
        <button type="button" class="primary-button full" data-action="new-project">${icon("plus", 17)}新建创意</button>
        <label class="sidebar-search">${icon("search", 16)}<input data-project-search placeholder="搜索项目"></label>
        <nav class="sidebar-nav"><button class="active">${icon("grid", 17)}全部项目<span>6</span></button><button>${icon("history", 17)}最近采用<span>2</span></button></nav>
        <div class="sidebar-section-title"><span>最近项目</span><button type="button">${icon("more", 16)}</button></div>
        <div class="project-scroll">${projectItems()}</div>
        <div class="local-status"><i></i><span><strong>本地工作区</strong><small>数据未离开此电脑</small></span>${icon("settings", 16)}</div>
      </aside>

      <main class="a-main">
        <header class="a-topbar">
          <div class="breadcrumb"><span>所有项目</span>${icon("chevron", 14)}<strong>${esc(project.name)}</strong></div>
          <div class="top-actions"><span class="saved-dot">已自动保存</span><button type="button" class="icon-button">${icon("more", 18)}</button></div>
        </header>
        <section class="a-workspace-head">
          <div><span class="overline">CREATIVE PROJECT</span><h1>${esc(project.name)}</h1><p>把版本卖点转成可供投放测试的视觉方向</p></div>
          <div class="head-actions">${modeSwitch()}<button type="button" class="primary-button" data-action="generate">${icon("sparkles", 17)}生成第 ${state.batch + 1} 批</button></div>
        </section>

        <div class="a-layout">
          <section class="a-canvas">
            <div class="canvas-head"><div><h2>方案画布</h2><p>基于当前定位生成 · 第 ${state.batch} 批，共 3 套</p></div><div class="canvas-tools"><button class="active">卡片</button><button>对比</button><button>${icon("sliders", 15)}</button></div></div>
            <div class="concept-grid">${concepts.map((concept, index) => conceptCard(concept, index)).join("")}</div>
            <button type="button" class="history-row"><span>${icon("history", 16)}查看基于旧定位的 2 批方案</span>${icon("chevron", 15)}</button>
          </section>

          <aside class="a-inspector">
            <div class="inspector-head"><div><span class="overline">INPUT</span><h2>生成配置</h2></div><span class="quality-ring">86<small>完整度</small></span></div>
            <div class="inspector-tabs">${["创意要求", "创意定位"].map((tab) => `<button type="button" data-inspector="${tab}" class="${state.inspector === tab ? "active" : ""}">${tab}</button>`).join("")}</div>
            <div class="inspector-scroll">${inspectorContent()}</div>
            <div class="inspector-foot"><div><span>每批固定生成 3 套</span><small>当前定位还可生成 ${2 - Math.min(state.batch, 2)} 批</small></div><button type="button" class="primary-button full" data-action="generate">${icon("sparkles", 17)}生成视觉方案</button></div>
          </aside>
        </div>
      </main>
    </div>`;
  }

  function summaryCard() {
    return `<aside class="brief-summary">
      <div class="summary-title"><span>实时创意简报</span><em>86% 完整</em></div>
      <h3>新职业首曝视觉</h3>
      <dl><div><dt>核心目标</dt><dd>让玩家感到版本内容量巨大</dd></div><div><dt>主要卖点</dt><dd>新职业登场</dd></div><div><dt>画幅</dt><dd>横版 16:9</dd></div><div><dt>美术方向</dt><dd>国风写意 · 电影感</dd></div></dl>
      <div class="summary-files"><span>${icon("file", 15)}新职业技能截图.png</span><span>${icon("file", 15)}版本卖点说明.pdf</span></div>
      <p>${icon("bolt", 15)}填完当前步骤即可生成，不必一次完成所有辅助项。</p>
    </aside>`;
  }

  function bBrief() {
    return `<aside class="b-brief"><div class="b-brief-head"><span>实时创意简报</span><strong>已保存</strong></div><h3>${esc(state.bProjectName)}</h3><dl><div><dt>任务</dt><dd>${esc(state.bTaskType)}</dd></div><div><dt>目标</dt><dd>让玩家第一眼感到版本内容量巨大</dd></div><div><dt>卖点</dt><dd>新职业登场</dd></div><div><dt>画幅 / 风格</dt><dd>横版 16:9 · 国风写意</dd></div></dl><p>当前步骤完成后即可继续，辅助项可后补。</p></aside>`;
  }

  function bProjectPanel() {
    return `<div class="b-project-overlay ${state.bProjectOpen ? "open" : ""}" data-action="close-projects"></div><aside class="b-project-panel ${state.bProjectOpen ? "open" : ""}"><div class="b-project-panel-head">${brand(true)}<button type="button" class="icon-button" data-action="close-projects">${icon("close", 17)}</button></div><button type="button" class="primary-button full" data-action="new-project">${icon("plus", 16)}新建创意</button><label class="b-project-search">${icon("search", 15)}<input data-project-search placeholder="搜索项目"></label><div class="b-project-label">最近项目</div><div class="b-project-list">${projectItems("status")}</div></aside>`;
  }

  function bStepContent() {
    if (state.step === 1) {
      return `<div class="step-copy"><span>STEP 01 · BRIEF</span><h2>先写清这次要完成的任务</h2><p>只保留任务类型和任务描述，后面的定位会围绕这段说明展开。</p></div><div class="large-form b-brief-form"><label>任务类型<div class="b-task-family"><button type="button" class="${state.bTaskFamily === "展示类" ? "active" : ""}" data-task-family="展示类">${icon("image", 15)}展示类</button><button type="button" class="${state.bTaskFamily === "叙事类" ? "active" : ""}" data-task-family="叙事类">${icon("file", 15)}叙事类</button></div><select data-task-type><option>${esc(state.bTaskType)}</option><option>常规效果测试</option><option>版本活动素材</option></select></label><label>任务描述<textarea rows="7">突出新职业的压迫感和门派差异，让玩家第一眼感到版本内容量巨大。</textarea><small class="field-note">项目名将根据任务自动生成，也可以在顶部修改。</small></label></div>`;
    }
    if (state.step === 2) {
      return `<div class="step-copy"><span>STEP 02</span><h2>选择这次创意的表达坐标</h2><p>先选主项，再补辅助项。系统只展示与卖点相关的内容，不让标签变成一堵墙。</p></div>
      <div class="position-block"><div class="position-label"><span>01</span><div><strong>产品卖点</strong><small>主选 1 项 · 辅助最多 2 项</small></div><em>必选</em></div>${chips(["新职业登场", "门派对抗", "自由交易", "装备养成", "大世界探索"])}</div>
      <div class="position-block"><div class="position-label"><span>02</span><div><strong>展示内容</strong><small>已根据「新职业登场」过滤</small></div><em>必选</em></div>${chips(["职业技能", "角色立绘", "实机战斗", "装备界面"], "soft")}</div>
      <div class="position-block"><div class="position-label"><span>03</span><div><strong>视觉风格</strong><small>按层级逐步选择</small></div><em>必选</em></div><div class="cascade-row"><select><option>高相关度</option></select>${icon("chevron", 14)}<select><option>国风写意 · 电影感</option></select>${icon("chevron", 14)}<select><option>英雄长卷</option></select></div></div>`;
    }
    if (state.step === 3) {
      const body = state.bView === "compare" ? `<div class="b-compare"><div class="b-compare-thumbs">${concepts.map((c, i) => `<button type="button" data-concept="${i}" class="${state.selectedConcept === i ? "selected" : ""}">${art(c, true)}<span>${c.no} · ${esc(c.title)}</span></button>`).join("")}</div><div class="b-compare-grid"><div class="b-compare-row head"><span>比较维度</span>${concepts.map((c) => `<strong>${c.no}</strong>`).join("")}</div>${[["第一眼冲击","强","中","中"],["卖点表达","中","强","强"],["产品可信度","中","中","强"],["制作适配性","强","中","中"]].map((row) => `<div class="b-compare-row"><span>${row[0]}</span>${row.slice(1).map((v) => `<b>${v}</b>`).join("")}</div>`).join("")}</div></div>` : `<div class="b-results">${concepts.map((concept, index) => bConceptCard(concept, index)).join("")}</div>${state.selectedConcept !== null ? `<section class="b-expanded"><div class="b-expanded-label">已选方向 ${concepts[state.selectedConcept].no}</div><h3>${esc(concepts[state.selectedConcept].title)}</h3><p>${esc(concepts[state.selectedConcept].hook)}</p><p>${esc(concepts[state.selectedConcept].subtitle)}</p></section>` : ""}`;
      return `<div class="step-copy compact"><span>STEP 03 · OUTPUT</span><div class="b-output-head"><div><h2>生成与采用</h2><p>固定生成 3 套。可直接采用，也可以切换对比视图。</p></div><div class="b-view-toggle"><button type="button" class="${state.bView === "grid" ? "active" : ""}" data-b-view="grid">方案网格</button><button type="button" class="${state.bView === "compare" ? "active" : ""}" data-b-view="compare">对比视图</button></div></div></div>${body}`;
    }
    return "";
  }

  function variantB() {
    const steps = ["任务说明", "创意定位", "生成与采用"];
    const canGenerate = state.step === 3;
    return `<div class="variant variant-b ${state.bProjectOpen ? "projects-open" : ""}">
      <header class="b-header">${brand(true)}<button type="button" class="b-project-switch" data-action="open-projects"><span>当前项目</span><strong>${esc(state.bProjectName)}</strong>${icon("chevron", 14)}</button><div class="b-header-actions"><span class="b-save-state"><i></i>已保存</span><button type="button" class="secondary-button" data-action="open-projects">${icon("folder", 16)}所有项目</button></div></header>
      <main class="b-main">
        <div class="b-title-row"><div><span class="overline">GUIDED CREATION</span><h1>从任务说明到可采用方向</h1><p>一次只处理一个决定，完成定位后直接生成并采用。</p></div>${modeSwitch("light")}</div>
        <nav class="b-stepper" aria-label="创作步骤">${steps.map((step, index) => `<button type="button" data-step="${index + 1}" class="${state.step === index + 1 ? "active" : ""} ${state.step > index + 1 ? "done" : ""}"><span>${state.step > index + 1 ? icon("check", 16) : index + 1}</span><strong>${step}</strong><small>${["Brief", "Position", "Output"][index]}</small></button>${index < steps.length - 1 ? "<i></i>" : ""}`).join("")}</nav>
        ${state.step === 3 ? `<div class="b-output-summary"><span>当前简报</span><strong>目标：让玩家感到版本内容量巨大</strong><span>卖点：新职业登场</span><span>16:9 · 国风写意</span><button type="button" class="text-button" data-step="2">修改配置</button></div>` : `<div class="b-content"><section class="step-panel">${bStepContent()}<div class="step-actions"><button type="button" class="secondary-button" data-action="prev-step" ${state.step === 1 ? "disabled" : ""}>← 上一步</button><span>第 ${state.step} / 3 步</span><button type="button" class="primary-button" data-action="next-step">${state.step === 2 ? "确认定位，生成方案" : "继续下一步"}${icon("arrow", 16)}</button></div></section>${bBrief()}</div>`}
        ${state.step === 3 ? `<section class="b-output-panel">${bStepContent()}<div class="step-actions"><button type="button" class="secondary-button" data-action="prev-step">← 修改定位</button><span>第 3 / 3 步</span><button type="button" class="primary-button" data-action="generate">${icon("sparkles", 16)}再生成 3 套</button></div></section>` : ""}
      </main>${bProjectPanel()}</div>`;
  }

  function variantC() {
    const selected = concepts[state.selectedConcept];
    return `<div class="variant variant-c ${state.drawerOpen ? "drawer-open" : ""}">
      <aside class="c-rail">${brand(true)}<nav><button class="active" title="创意画板">${icon("layers", 19)}</button><button title="项目">${icon("folder", 19)}</button><button title="历史">${icon("history", 19)}</button></nav><button class="rail-bottom" title="设置">${icon("settings", 18)}</button></aside>
      <main class="c-main">
        <header class="c-topbar"><button type="button" class="project-picker">${icon("folder", 16)}<span>${esc(projects[state.projectIndex].name)}</span>${icon("chevron", 14)}</button><div class="c-top-actions"><span class="saved-dot">已保存</span>${modeSwitch("compact")}<button type="button" class="secondary-button" data-action="toggle-drawer">${icon("sliders", 16)}创意配置</button><button type="button" class="primary-button" data-action="generate">${icon("sparkles", 17)}再生成 3 套</button></div></header>
        <section class="c-board-head"><div><span class="overline">VISUAL BOARD · BATCH ${state.batch}</span><h1>先看方向，再谈细节</h1><p>同一份创意简报生成的三种表达策略。点击方案查看完整解释。</p></div><div class="board-metrics"><span><b>3</b>本批方案</span><span><b>${state.batch}</b>已生成批次</span><span><b>${state.adoptedConcept === null ? 0 : 1}</b>已采用</span></div></section>
        <section class="c-gallery">${concepts.map((concept, index) => conceptCard(concept, index, "gallery")).join("")}</section>
        <section class="direction-detail"><div class="detail-number">${selected.no}</div><div><span class="overline">SELECTED DIRECTION</span><h2>${esc(selected.title)}</h2><p>${esc(selected.hook)}</p></div><dl><div><dt>策略</dt><dd>${esc(selected.tags[0])}</dd></div><div><dt>重点证据</dt><dd>${esc(selected.tags[2])}</dd></div><div><dt>匹配度</dt><dd>${selected.score} / 100</dd></div></dl><button type="button" class="primary-button" data-action="adopt" data-concept="${state.selectedConcept}">${state.adoptedConcept === state.selectedConcept ? icon("check", 15) + "已采用此方向" : "采用此方向"}</button></section>
      </main>
      <aside class="c-drawer" aria-label="创意配置抽屉"><div class="drawer-head"><div><span class="overline">CREATIVE BRIEF</span><h2>创意配置</h2></div><button type="button" class="icon-button" data-action="toggle-drawer">${icon("close", 19)}</button></div><div class="drawer-progress"><span style="width:86%"></span></div><div class="drawer-scroll">${inspectorContent()}<div class="drawer-divider"></div><div class="field-head"><label>当前标签</label><span>${state.tagCount} 项</span></div>${chips(["新职业", "门派群像", "国风写意", "电影感"])}<button type="button" class="secondary-button full">编辑全部定位 ${icon("arrow", 15)}</button></div><div class="drawer-foot"><span>配置完成度 86%</span><button type="button" class="primary-button full" data-action="generate">${icon("sparkles", 16)}应用配置并生成</button></div></aside>
    </div>`;
  }

  function render() {
    root.innerHTML = state.variant === "A" ? variantA() : state.variant === "B" ? variantB() : variantC();
    variantLabel.textContent = `${state.variant} — ${variants[state.variant]}`;
    document.querySelectorAll("[data-variant]").forEach((button) => button.classList.toggle("active", button.dataset.variant === state.variant));
    const visibleState = {
      variant: state.variant,
      project: projects[state.projectIndex].name,
      mode: state.mode,
      step: state.variant === "B" ? state.step : undefined,
      selected: concepts[state.selectedConcept].title,
      adopted: state.adoptedConcept === null ? null : concepts[state.adoptedConcept].title,
      batch: state.batch,
      configPanel: state.variant === "C" ? state.drawerOpen : state.inspector,
    };
    prototypeState.textContent = JSON.stringify(visibleState);
  }

  function setVariant(next) {
    if (!variants[next]) return;
    state.variant = next;
    const url = new URL(window.location.href);
    url.searchParams.set("variant", next);
    history.replaceState({}, "", url);
    render();
  }

  function cycleVariant(direction) {
    const keys = Object.keys(variants);
    const current = keys.indexOf(state.variant);
    setVariant(keys[(current + direction + keys.length) % keys.length]);
  }

  function toast(message) {
    toastEl.textContent = message;
    toastEl.classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => toastEl.classList.remove("show"), 2200);
  }

  document.addEventListener("click", (event) => {
    const variantButton = event.target.closest("[data-variant]");
    if (variantButton) return setVariant(variantButton.dataset.variant);
    const directionButton = event.target.closest("[data-variant-direction]");
    if (directionButton) return cycleVariant(directionButton.dataset.variantDirection === "next" ? 1 : -1);
    const projectButton = event.target.closest("[data-project]");
    if (projectButton) {
      state.projectIndex = Number(projectButton.dataset.project);
      state.mode = projects[state.projectIndex].type;
      state.bProjectName = projects[state.projectIndex].name;
      state.bProjectOpen = false;
      render();
      return toast(`已切换到「${projects[state.projectIndex].name}」· 假数据`);
    }
    const modeButton = event.target.closest("[data-mode]");
    if (modeButton) {
      state.mode = modeButton.dataset.mode;
      render();
      return toast(`已切换为${state.mode} · 原型未调用 API`);
    }
    const conceptButton = event.target.closest("[data-concept]");
    if (conceptButton && !event.target.closest("[data-action]")) {
      state.selectedConcept = Number(conceptButton.dataset.concept);
      render();
      return;
    }
    const inspectorButton = event.target.closest("[data-inspector]");
    if (inspectorButton) {
      state.inspector = inspectorButton.dataset.inspector;
      render();
      return;
    }
    const stepButton = event.target.closest("[data-step]");
    if (stepButton) {
      state.step = Number(stepButton.dataset.step);
      render();
      return;
    }
    const viewButton = event.target.closest("[data-b-view]");
    if (viewButton) {
      state.bView = viewButton.dataset.bView;
      render();
      return;
    }
    const familyButton = event.target.closest("[data-task-family]");
    if (familyButton) {
      state.bTaskFamily = familyButton.dataset.taskFamily;
      state.bTaskType = state.bTaskFamily === "叙事类" ? "剧情钩子创作" : "新版本首曝素材";
      render();
      return;
    }
    const actionButton = event.target.closest("[data-action]");
    if (!actionButton) return;
    const action = actionButton.dataset.action;
    if (action === "open-projects") {
      state.bProjectOpen = true;
      render();
    } else if (action === "close-projects") {
      state.bProjectOpen = false;
      render();
    } else if (action === "generate") {
      state.batch = Math.min(2, state.batch + 1);
      state.bGeneration = ["queued", "queued", "queued"];
      render();
      toast("已生成 3 套假方案 · 未调用真实 AI");
      setTimeout(() => { state.bGeneration = ["done", "done", "failed"]; render(); }, 650);
    } else if (action === "retry") {
      const index = Number(actionButton.dataset.concept);
      state.bGeneration[index] = "generating";
      render();
      setTimeout(() => { state.bGeneration[index] = "done"; render(); }, 550);
    } else if (action === "adopt") {
      state.selectedConcept = Number(actionButton.dataset.concept);
      state.adoptedConcept = state.selectedConcept;
      render();
      toast(`已采用「${concepts[state.adoptedConcept].title}」· 仅原型状态`);
    } else if (action === "detail") {
      state.selectedConcept = Number(actionButton.dataset.concept);
      render();
      toast("已展开方案上下文；正式版可使用详情侧栏");
    } else if (action === "toggle-drawer") {
      state.drawerOpen = !state.drawerOpen;
      render();
    } else if (action === "next-step") {
      if (state.step < 3) state.step += 1;
      else toast("当前项目已完成 · 仅原型状态");
      render();
    } else if (action === "prev-step") {
      state.step = Math.max(1, state.step - 1);
      render();
    } else if (action === "tag") {
      state.tagCount += actionButton.classList.contains("active") ? -1 : 1;
      actionButton.classList.toggle("active");
      const check = actionButton.querySelector("svg");
      if (check) check.remove(); else actionButton.insertAdjacentHTML("beforeend", icon("check", 12));
      prototypeState.textContent = prototypeState.textContent.replace(/"configPanel".*$/, `"tagCount":${state.tagCount}}`);
    } else {
      toast("这是只读 UI 原型，不会执行真实操作");
    }
  });

  document.addEventListener("input", (event) => {
    if (!event.target.matches("[data-project-search]")) return;
    const query = event.target.value.trim().toLowerCase();
    document.querySelectorAll(".project-row").forEach((row) => {
      row.hidden = !row.textContent.toLowerCase().includes(query);
    });
  });

  window.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    const target = event.target;
    if (target.matches("input, textarea, select, [contenteditable='true']")) return;
    event.preventDefault();
    cycleVariant(event.key === "ArrowRight" ? 1 : -1);
  });

  render();
})();
