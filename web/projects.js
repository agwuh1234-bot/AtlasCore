(() => {
  'use strict';

  const ACTIVE_PROJECT = 'atlas_active_project_id';
  const DEFAULT_PROJECT = 'project-general';
  const SCOPED_KEYS = new Set([
    'atlas_chat_history',
    'atlas_response_id',
    'atlas_active_job_id',
    'atlas_safe_job_recovery',
    'atlas_chat_threads',
    'atlas_active_thread_id',
  ]);
  const rawGet = Storage.prototype.getItem;
  const rawSet = Storage.prototype.setItem;
  const rawRemove = Storage.prototype.removeItem;

  let activeProject = rawGet.call(localStorage, ACTIVE_PROJECT) || DEFAULT_PROJECT;

  const scopedKey = (key) => SCOPED_KEYS.has(String(key))
    ? String(key) + ':' + activeProject
    : String(key);

  if (activeProject === DEFAULT_PROJECT) {
    for (const key of SCOPED_KEYS) {
      const target = key + ':' + activeProject;
      const legacy = rawGet.call(localStorage, key);
      if (rawGet.call(localStorage, target) === null && legacy !== null) {
        rawSet.call(localStorage, target, legacy);
      }
    }
  }

  Storage.prototype.getItem = function getProjectItem(key) {
    return rawGet.call(this, this === localStorage ? scopedKey(key) : key);
  };
  Storage.prototype.setItem = function setProjectItem(key, value) {
    return rawSet.call(this, this === localStorage ? scopedKey(key) : key, value);
  };
  Storage.prototype.removeItem = function removeProjectItem(key) {
    return rawRemove.call(this, this === localStorage ? scopedKey(key) : key);
  };

  const baseFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    if (method === 'POST' && (url.endsWith('/app-jobs') || url.endsWith('/app-task'))) {
      const body = init && typeof init.body === 'string' ? safeJson(init.body) : null;
      if (body && !body.project_id) {
        init = Object.assign({}, init, {
          body: JSON.stringify(Object.assign({}, body, { project_id: activeProject })),
        });
      }
    }
    return baseFetch(input, init);
  };

  function safeJson(value) {
    try { return JSON.parse(value); } catch { return null; }
  }

  function projectId(project) {
    return String((project && (project.id || project.project_id)) || '');
  }

  function projectName(project) {
    return String((project && (project.name || project.title)) || projectId(project));
  }

  function setActiveProject(id) {
    if (!id || id === activeProject) return;
    rawSet.call(localStorage, ACTIVE_PROJECT, id);
    try {
      const url = new URL(window.location.href);
      if (url.searchParams.has('project')) {
        url.searchParams.delete('project');
        window.history.replaceState(null, '', url.pathname + (url.search || '') + (url.hash || ''));
      }
    } catch {
      // URL cleanup is optional; project persistence is the source of truth.
    }
    window.location.reload();
  }

  function showError(message) {
    const text = message || 'Не удалось выполнить действие.';
    if (window.AtlasNotice?.error) {
      window.AtlasNotice.error(text, { title: 'Не удалось выполнить' });
      return;
    }
    window.alert(text);
  }

  function showSuccess(message) {
    if (window.AtlasNotice?.success) {
      window.AtlasNotice.success(message);
      return;
    }
    window.alert(message);
  }

  async function askText(options, fallbackMessage, fallbackValue = '') {
    if (window.AtlasDialog?.prompt) {
      return await window.AtlasDialog.prompt(options);
    }
    return window.prompt(fallbackMessage, fallbackValue);
  }

  async function jsonRequest(url, options) {
    const response = await window.fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.error || 'Ошибка Atlas');
    return data;
  }

  function installUi() {
    if (document.getElementById('projectSelect')) return;
    const header = document.querySelector('.topbar');
    if (!header) return;

    const bar = document.createElement('section');
    bar.className = 'project-switcher';
    bar.setAttribute('aria-label', 'Текущий проект');
    bar.innerHTML = '<span class="project-label">Проект</span><select id="projectSelect" aria-label="Выбрать проект"></select><button id="addProjectBtn" class="ghost-btn" type="button" aria-label="Создать проект">＋</button>';
    header.insertAdjacentElement('afterend', bar);

    const settings = document.querySelector('#settingsCard .modal');
    if (settings) {
      const anchor = document.getElementById('exportChatBtn');
      const memory = document.createElement('button');
      memory.id = 'projectMemoryBtn';
      memory.type = 'button';
      memory.textContent = 'Запомнить для проекта';
      const budget = document.createElement('p');
      budget.id = 'budgetStatus';
      budget.className = 'settings-status';
      budget.textContent = 'Бюджет: загрузка…';
      settings.insertBefore(memory, anchor || settings.lastElementChild);
      settings.insertBefore(budget, anchor || settings.lastElementChild);
    }

    document.getElementById('projectSelect').addEventListener('change', (event) => {
      setActiveProject(event.target.value);
    });
    document.getElementById('addProjectBtn').addEventListener('click', createProject);
    const memoryButton = document.getElementById('projectMemoryBtn');
    if (memoryButton) memoryButton.addEventListener('click', rememberForProject);
    const settingsButton = document.getElementById('settingsBtn');
    if (settingsButton) settingsButton.addEventListener('click', loadBudget);
    const loginButton = document.getElementById('loginBtn');
    if (loginButton) {
      loginButton.addEventListener('click', () => {
        for (const delay of [900, 2500]) {
          window.setTimeout(() => {
            loadProjects();
            loadBudget();
            hydrateHistory();
          }, delay);
        }
      });
    }
  }

  async function loadProjects() {
    const select = document.getElementById('projectSelect');
    if (!select) return;
    try {
      const data = await jsonRequest('/app-projects');
      const projects = Array.isArray(data) ? data : (data.projects || []);
      if (!projects.length) return;
      select.replaceChildren();
      for (const project of projects) {
        const id = projectId(project);
        if (!id) continue;
        const option = document.createElement('option');
        option.value = id;
        option.textContent = projectName(project);
        option.selected = id === activeProject;
        select.append(option);
      }
      const found = Array.from(select.options).some((option) => option.value === activeProject);
      if (!found) setActiveProject((select.options[0] && select.options[0].value) || DEFAULT_PROJECT);
    } catch (error) {
      if (!String(error.message).includes('Unauthorized')) select.title = error.message;
    }
  }

  async function createProject() {
    const name = await askText({
      eyebrow: 'ATLAS · PROJECTS',
      title: 'Новый проект',
      message: 'У проекта будут отдельные чаты, память, файлы и задачи.',
      label: 'Название проекта',
      placeholder: 'Например, Shopify Launch',
      confirmLabel: 'Создать',
      cancelLabel: 'Отмена',
      maxLength: 80,
    }, 'Название нового проекта');
    if (!name || !name.trim()) return;
    try {
      const data = await jsonRequest('/app-projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }),
      });
      const project = data.project || data;
      await loadProjects();
      setActiveProject(projectId(project));
    } catch (error) {
      showError(error.message);
    }
  }

  async function rememberForProject() {
    const content = await askText({
      eyebrow: 'ATLAS · MEMORY',
      title: 'Запомнить для проекта',
      message: 'Сохраняйте устойчивые решения, цели и контекст. Секреты и API-ключи не добавляйте.',
      label: 'Память',
      placeholder: 'Что Atlas должен помнить?',
      confirmLabel: 'Запомнить',
      cancelLabel: 'Отмена',
      maxLength: 200,
    }, 'Что Atlas должен помнить в этом проекте?');
    if (!content || !content.trim()) return;
    try {
      await jsonRequest('/app-projects/' + encodeURIComponent(activeProject) + '/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'note', content: content.trim() }),
      });
      showSuccess('Сохранено в памяти проекта.');
    } catch (error) {
      showError(error.message);
    }
  }

  async function loadBudget() {
    const node = document.getElementById('budgetStatus');
    if (!node) return;
    try {
      const data = await jsonRequest('/app-budget');
      const spent = Number(data.spent_usd ?? data.today_spent_usd ?? data.spent ?? 0);
      const reserved = Number(data.reserved_usd ?? data.today_reserved_usd ?? data.reserved ?? 0);
      const limit = Number(data.daily_limit_usd ?? data.daily_limit ?? 0);
      if (limit > 0) {
        node.textContent = 'Бюджет сегодня: $' + spent.toFixed(2) + ' + $' + reserved.toFixed(2) + ' резерв / $' + limit.toFixed(2);
      } else {
        node.textContent = 'Бюджет сегодня: $' + spent.toFixed(2);
      }
    } catch (error) {
      node.textContent = 'Бюджет: ' + error.message;
    }
  }

  async function hydrateHistory() {
    const historyKey = 'atlas_chat_history:' + activeProject;
    const marker = 'atlas_history_hydrated:' + activeProject;
    if (rawGet.call(localStorage, historyKey) || rawGet.call(localStorage, marker)) return;
    try {
      const data = await jsonRequest('/app-projects/' + encodeURIComponent(activeProject) + '/history');
      const jobs = Array.isArray(data) ? data : (data.jobs || data.history || []);
      rawSet.call(localStorage, marker, '1');
      if (!jobs.length) return;
      const history = [];
      for (const job of jobs) {
        if (job.task) history.push({ role: 'user', text: String(job.task) });
        if (job.status === 'done' && (job.answer || job.result)) {
          history.push({ role: 'assistant', text: String(job.answer || job.result) });
        }
      }
      if (!history.length) return;
      rawSet.call(localStorage, historyKey, JSON.stringify(history.slice(-100)));
      const last = jobs.slice().reverse().find((job) => job.response_id);
      if (last) {
        rawSet.call(localStorage, 'atlas_response_id:' + activeProject, String(last.response_id));
      }
      window.location.reload();
    } catch {
      // Login may not have completed yet.
    }
  }

  installUi();
  loadProjects();
  hydrateHistory();
})();
