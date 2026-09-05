const state = {
  csrfToken: '',
  project: null,
  projects: [],
  tagConfig: null,
  tagGroups: [],
  run: null,
};

const $ = (selector) => document.querySelector(selector);
const loginPanel = $('#login-panel');
const workspace = $('#workspace');
const loginForm = $('#login-form');
const inputForm = $('#input-form');
const results = $('#results');
const statusLine = $('#status');
const projectSelect = $('#project-select');

function setStatus(message, tone = '') {
  statusLine.textContent = message;
  statusLine.dataset.tone = tone;
}

function cookieValue(name) {
  const entry = document.cookie.split('; ').find((value) => value.startsWith(`${name}=`));
  return entry ? decodeURIComponent(entry.slice(name.length + 1)) : '';
}

function csrfHeaders() {
  const token = cookieValue('studio_csrf') || state.csrfToken;
  return { 'Content-Type': 'application/json', 'X-CSRF-Token': token };
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let payload = {};
  try { payload = await response.json(); } catch (_) { payload = {}; }
  if (response.status === 401) showLogin('登录已失效，请重新登录。');
  if (!response.ok) {
    const error = new Error(payload.error_code || payload.error || '请求失败，请稍后重试');
    error.status = response.status;
    throw error;
  }
  return payload;
}

function showLogin(message = '') {
  state.project = null;
  state.projects = [];
  loginPanel.hidden = false;
  workspace.hidden = true;
  inputForm.hidden = true;
  results.replaceChildren();
  $('#login-message').textContent = message || '使用本机工作台账号登录。';
}

function showWorkspace() {
  loginPanel.hidden = true;
  workspace.hidden = false;
}

function selectedTags() {
  const tags = {};
  document.querySelectorAll('[data-tag-group]').forEach((group) => {
    const values = [...group.querySelectorAll('input:checked')].map((input) => input.value);
    if (values.length) tags[group.dataset.tagGroup] = values;
  });
  return tags;
}

function updateConditionalGroups() {
  const selected = selectedTags();
  state.tagGroups.forEach((group) => {
    const element = document.querySelector(`[data-group-key="${CSS.escape(group.key)}"]`);
    if (!element) return;
    const rule = group.visible_when;
    element.hidden = Boolean(rule && !(selected[rule.key] || []).some((value) => rule.values.includes(value)));
  });
}

function renderTags(config) {
  const root = $('#tag-groups');
  root.replaceChildren();
  const mode = state.project?.script_type === '叙事类' ? config?.narrative : config?.visual;
  state.tagGroups = Array.isArray(mode?.groups) ? mode.groups : [];
  state.tagGroups.forEach((group) => {
    const field = document.createElement('details');
    field.className = 'tag-group';
    field.dataset.groupKey = group.key;
    field.open = Boolean(group.required);
    const heading = document.createElement('summary');
    heading.className = 'tag-heading';
    const title = document.createElement('strong');
    title.textContent = group.label || group.key;
    heading.append(title);
    if (group.required) {
      const required = document.createElement('small');
      required.textContent = '必选';
      heading.append(required);
    }
    field.append(heading);
    const optionsRoot = document.createElement('div');
    optionsRoot.className = 'tag-options';
    const options = Array.isArray(group.options) ? group.options : [];
    const inputType = group.type === 'single' ? 'radio' : 'checkbox';
    options.forEach((option) => {
      const label = document.createElement('label');
      label.className = 'tag-option';
      const input = document.createElement('input');
      input.type = inputType;
      input.name = group.key;
      input.value = option.label || '';
      input.addEventListener('change', updateConditionalGroups);
      const text = document.createElement('span');
      text.textContent = option.label || '';
      label.append(input, text);
      optionsRoot.append(label);
    });
    field.append(optionsRoot);
    root.append(field);
  });
  updateConditionalGroups();
}

function renderProjects() {
  projectSelect.replaceChildren();
  state.projects.forEach((project) => {
    const option = document.createElement('option');
    option.value = String(project.id);
    option.textContent = `${project.name || '未命名项目'} · ${project.script_type || '展示类'}`;
    projectSelect.append(option);
  });
  if (!state.projects.length) {
    state.project = null;
    projectSelect.disabled = true;
    inputForm.hidden = true;
    $('#project-message').textContent = '还没有项目，请先新建一个项目。';
    return;
  }
  projectSelect.disabled = false;
  const selected = state.project && state.projects.find((item) => item.id === state.project.id);
  state.project = selected || state.projects[0];
  projectSelect.value = String(state.project.id);
  inputForm.hidden = false;
  $('#project-message').textContent = '';
  renderTags(state.tagConfig || {});
}

async function loadProjects() {
  const payload = await api('/api/projects');
  state.projects = Array.isArray(payload.projects) ? payload.projects : [];
  renderProjects();
}

async function loadTags() {
  const payload = await api('/api/tag-options');
  state.tagConfig = payload.config || {};
  renderTags(state.tagConfig);
}

async function loadWorkspace() {
  showWorkspace();
  await loadProjects();
  await loadTags();
}

async function createProject() {
  const name = $('#project-name').value.trim() || '未命名创意';
  const scriptType = $('#project-kind').value;
  const payload = await api('/api/projects', {
    method: 'POST',
    headers: csrfHeaders(),
    body: JSON.stringify({ name, script_type: scriptType }),
  });
  $('#project-name').value = '';
  state.project = payload.project || null;
  await loadProjects();
  await loadTags();
  setStatus('项目已创建');
}

function imageControl(item, index, useCase) {
  const wrapper = document.createElement('div');
  wrapper.className = 'image-control';
  const frame = useCase === 'carousel' ? item.frames?.find((candidate) => candidate.index === index) : null;
  const imageState = (frame || item).image_state || { status: 'pending' };
  const status = document.createElement('span');
  status.className = `image-status image-status-${imageState.status}`;
  status.textContent = imageState.status === 'success' ? '图片已生成' : imageState.status === 'failed' ? '上次生成失败，可重试' : '尚未生成图片';
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = imageState.status === 'success' ? '已完成' : imageState.status === 'failed' ? '重试图片' : useCase === 'carousel' ? `生成第 ${index} 帧` : '生成图片';
  button.disabled = imageState.status === 'success';
  button.addEventListener('click', () => requestImage(item.scheme_id, useCase === 'carousel' ? index : null, button));
  wrapper.append(status, button);
  if (imageState.image_url) {
    const image = document.createElement('img');
    image.alt = useCase === 'carousel' ? `第 ${index} 帧` : '生成图片';
    image.src = imageState.image_url;
    wrapper.append(image);
  }
  return wrapper;
}

function renderRun(run) {
  state.run = run;
  results.replaceChildren();
  (run.items || []).forEach((item, itemIndex) => {
    const card = document.createElement('article');
    card.className = 'scheme';
    const title = document.createElement('h2');
    title.textContent = item.title || item.story || `方案 ${itemIndex + 1}`;
    card.append(title);
    const labels = { core_idea: '核心创意', ad_copy: '广告文案', image_description: '画面描述', story: '故事梗概' };
    ['core_idea', 'ad_copy', 'image_description', 'story'].forEach((key) => {
      if (typeof item[key] === 'string') {
        const field = document.createElement('div');
        field.className = 'scheme-field';
        const label = document.createElement('span');
        label.className = 'scheme-label';
        label.textContent = labels[key];
        const text = document.createElement('p');
        text.textContent = item[key];
        field.append(label, text);
        card.append(field);
      }
    });
    if (Array.isArray(item.hooks)) {
      item.hooks.forEach((hook) => {
        const field = document.createElement('div');
        field.className = 'scheme-field';
        const label = document.createElement('span');
        label.className = 'scheme-label';
        label.textContent = '开场钩子';
        const text = document.createElement('p');
        text.textContent = hook.text || '';
        field.append(label, text);
        card.append(field);
      });
    }
    if (Array.isArray(item.frames)) {
      item.frames.forEach((frame) => {
        const text = document.createElement('p');
        text.textContent = `${frame.index}. ${frame.description || ''}`;
        card.append(text);
      });
      const next = item.frames.find((frame) => frame.image_state?.status !== 'success');
      if (next) card.append(imageControl(item, next.index, 'carousel'));
    } else if (item.scheme_id) {
      card.append(imageControl(item, 1, run.use_case));
    }
    results.append(card);
  });
}

async function requestImage(schemeId, frameIndex, button) {
  button.disabled = true;
  const path = frameIndex == null ? `/api/v2/schemes/${schemeId}/image` : `/api/v2/schemes/${schemeId}/frames/${frameIndex}/image`;
  try {
    const payload = await api(path, { method: 'POST', headers: csrfHeaders(), body: '{}' });
    setStatus(payload.status === 'success' ? '图片已完成' : '图片处理中');
    if (payload.status !== 'success') window.setTimeout(() => pollAttempt(payload.attempt_id), 700);
    else await refreshRun();
  } catch (error) {
    setStatus(error.message, 'error');
    button.disabled = false;
  }
}

async function pollAttempt(attemptId) {
  try {
    const payload = await api(`/api/v2/image-attempts/${attemptId}`);
    if (payload.status === 'generating' || payload.status === 'pending') window.setTimeout(() => pollAttempt(attemptId), 900);
    else await refreshRun();
  } catch (error) {
    setStatus(error.message, 'error');
  }
}

async function refreshRun() {
  if (!state.run?.run_id) return;
  try {
    const payload = await api(`/api/v2/runs/${state.run.run_id}`);
    renderRun(payload);
  } catch (error) {
    setStatus(error.message, 'error');
  }
}

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  setStatus('正在登录');
  try {
    const payload = await api('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: $('#login-username').value, password: $('#login-password').value }),
    });
    state.csrfToken = payload.csrf_token || '';
    await loadWorkspace();
    setStatus('已登录');
  } catch (error) {
    $('#login-message').textContent = error.message;
    setStatus(error.message, 'error');
  }
});

projectSelect.addEventListener('change', async () => {
  state.project = state.projects.find((project) => String(project.id) === projectSelect.value) || null;
  state.run = null;
  results.replaceChildren();
  try { await loadTags(); } catch (error) { setStatus(error.message, 'error'); }
});

$('#create-project').addEventListener('click', async () => {
  try { await createProject(); } catch (error) { setStatus(error.message, 'error'); }
});

inputForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!state.project) {
    setStatus('请先选择项目', 'error');
    return;
  }
  const body = {
    task_description: $('#task-description').value.trim(),
    aspect_ratio: $('#aspect-ratio').value,
    creative_tags: selectedTags(),
  };
  $('#generate-button').disabled = true;
  setStatus('正在生成文字方案');
  try {
    const payload = await api(`/api/v2/projects/${state.project.id}/generate`, {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify(body),
    });
    renderRun(payload);
    setStatus('文字方案已完成');
  } catch (error) {
    setStatus(error.message, 'error');
  } finally {
    $('#generate-button').disabled = false;
  }
});

async function bootstrap() {
  try {
    const payload = await api('/api/auth/status');
    state.csrfToken = payload.csrf_token || '';
    if (!payload.authenticated) {
      showLogin();
      return;
    }
    await loadWorkspace();
    setStatus('已连接');
  } catch (error) {
    showLogin(error.message);
    setStatus(error.message, 'error');
  }
}

bootstrap();
