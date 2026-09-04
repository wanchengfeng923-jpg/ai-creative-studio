const state = { tags: {}, run: null };
const form = document.querySelector('#input-form');
const results = document.querySelector('#results');
const statusLine = document.querySelector('#status');

function setStatus(message, tone = '') {
  statusLine.textContent = message;
  statusLine.dataset.tone = tone;
}

function selectedTags() {
  const tags = {};
  document.querySelectorAll('[data-tag-group]').forEach((group) => {
    const values = [...group.querySelectorAll('input:checked')].map((input) => input.value);
    if (values.length) tags[group.dataset.tagGroup] = values;
  });
  return tags;
}

function renderTags(groups = {}) {
  const root = document.querySelector('#tag-groups');
  root.replaceChildren();
  Object.entries(groups).forEach(([name, values]) => {
    const field = document.createElement('div');
    field.dataset.tagGroup = name;
    field.className = 'tag-group';
    const title = document.createElement('strong');
    title.textContent = name;
    field.append(title);
    (Array.isArray(values) ? values : []).forEach((value) => {
      const label = document.createElement('label');
      label.className = 'tag-option';
      label.innerHTML = `<input type="checkbox" value="${String(value).replaceAll('"', '&quot;')}"><span>${value}</span>`;
      field.append(label);
    });
    root.append(field);
  });
}

function imageButton(item, index, useCase) {
  const wrapper = document.createElement('div');
  wrapper.className = 'image-control';
  if (useCase === 'carousel') {
    const frame = item.frames?.find((candidate) => candidate.index === index);
    const imageState = frame?.image_state || { status: 'pending' };
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = imageState.status === 'success' ? '已完成' : imageState.status === 'failed' ? '重试当前帧' : `生成第 ${index} 帧`;
    button.disabled = imageState.status === 'success';
    button.addEventListener('click', () => requestImage(item.scheme_id, index, button));
    wrapper.append(button);
    if (imageState.image_url) wrapper.insertAdjacentHTML('beforeend', `<img alt="第 ${index} 帧" src="${imageState.image_url}">`);
  } else {
    const imageState = item.image_state || { status: 'pending' };
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = imageState.status === 'success' ? '已完成' : imageState.status === 'failed' ? '重试图片' : '生成图片';
    button.disabled = imageState.status === 'success';
    button.addEventListener('click', () => requestImage(item.scheme_id, null, button));
    wrapper.append(button);
    if (imageState.image_url) wrapper.insertAdjacentHTML('beforeend', `<img alt="生成图片" src="${imageState.image_url}">`);
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
    ['core_idea', 'ad_copy', 'image_description', 'story'].forEach((key) => {
      if (typeof item[key] === 'string') {
        const p = document.createElement('p');
        p.textContent = item[key];
        card.append(p);
      }
    });
    if (Array.isArray(item.hooks)) item.hooks.forEach((hook) => { const p = document.createElement('p'); p.textContent = hook.text || ''; card.append(p); });
    if (Array.isArray(item.frames)) {
      item.frames.forEach((frame) => { const p = document.createElement('p'); p.textContent = `${frame.index}. ${frame.description || ''}`; card.append(p); });
      const next = item.frames.find((frame) => frame.image_state?.status !== 'success');
      if (next) card.append(imageButton(item, next.index, 'carousel'));
    } else if (item.scheme_id) card.append(imageButton(item, 1, run.use_case));
    results.append(card);
  });
}

async function requestImage(schemeId, frameIndex, button) {
  button.disabled = true;
  const path = frameIndex == null ? `/api/v2/schemes/${schemeId}/image` : `/api/v2/schemes/${schemeId}/frames/${frameIndex}/image`;
  try {
    const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error_code || 'image request failed');
    setStatus(payload.status === 'success' ? '图片已完成' : '图片处理中');
    if (payload.status !== 'success') window.setTimeout(() => pollAttempt(payload.attempt_id), 700);
    else await refreshRun();
  } catch (error) {
    setStatus(error.message, 'error');
    button.disabled = false;
  }
}

async function pollAttempt(attemptId) {
  const response = await fetch(`/api/v2/image-attempts/${attemptId}`);
  if (!response.ok) return;
  const payload = await response.json();
  if (payload.status === 'generating' || payload.status === 'pending') window.setTimeout(() => pollAttempt(attemptId), 900);
  else await refreshRun();
}

async function refreshRun() {
  if (!state.run?.run_id) return;
  const response = await fetch(`/api/v2/runs/${state.run.run_id}`);
  if (response.ok) renderRun(await response.json());
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  setStatus('正在生成文字');
  const body = {
    task_description: document.querySelector('#task-description').value,
    aspect_ratio: document.querySelector('#aspect-ratio').value,
    creative_tags: selectedTags(),
  };
  try {
    const response = await fetch('/api/v2/projects/1/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error_code || 'generation failed');
    renderRun(payload);
    setStatus('文字方案已完成');
  } catch (error) { setStatus(error.message, 'error'); }
});

renderTags({});

