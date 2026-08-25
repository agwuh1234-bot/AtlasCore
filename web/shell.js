(() => {
  'use strict';

  const ACTIVE_PROJECT = 'atlas_active_project_id';
  const TAB_KEY = 'atlas_active_tab';
  const DEFAULT_PROJECT = 'project-general';
  const $ = (id) => document.getElementById(id);
  const app = document.querySelector('.app-shell');
  let activeTab = localStorage.getItem(TAB_KEY) || 'chat';
  let authenticated = false;
  let baselineHeight = window.innerHeight;

  const tabs = [
    ['chat', '⌁', 'Чат'],
    ['projects', '▦', 'Проекты'],
    ['memory', '◉', 'Память'],
    ['files', '▤', 'Файлы'],
    ['auto', '◷', 'Авто'],
    ['actions', '✓', 'Действия'],
    ['plugins', '◇', 'Плагины'],
  ];

  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  }

  async function request(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) throw new Error('Войдите в Atlas');
    if (!response.ok) throw new Error(data.detail || data.error || 'Ошибка Atlas');
    return data;
  }

  function projectId() {
    return localStorage.getItem(ACTIVE_PROJECT) || DEFAULT_PROJECT;
  }

  function formatDate(value) {
    if (!value) return '';
    const date = new Date(Number(value) * 1000);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function setViewportHeight() {
    const viewport = window.visualViewport;
    const height = viewport ? viewport.height : window.innerHeight;
    document.documentElement.style.setProperty('--atlas-height', Math.round(height) + 'px');
    const keyboardOpen = baselineHeight - height > 120;
    document.body.classList.toggle('keyboard-open', keyboardOpen);
  }

  function installComposerTray() {
    const composer = $('composer');
    const attach = $('attachBtn');
    const write = $('writeModeBtn');
    const claude = $('claudeReviewBtn');
    if (!composer || !attach || !write || !claude || $('toolTrayBtn')) return;

    const tray = node('div', 'composer-tools');
    tray.id = 'composerTools';
    tray.append(attach, write, claude);

    const toggle = node('button', 'icon-btn', '⋯');
    toggle.id = 'toolTrayBtn';
    toggle.type = 'button';
    toggle.setAttribute('aria-label', 'Инструменты');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.addEventListener('click', () => {
      const open = !tray.classList.contains('open');
      tray.classList.toggle('open', open);
      toggle.classList.toggle('active', open);
      toggle.setAttribute('aria-expanded', String(open));
    });

    for (const button of [attach, write, claude]) {
      button.addEventListener('click', () => {
        window.setTimeout(() => {
          tray.classList.remove('open');
          toggle.classList.remove('active');
          toggle.setAttribute('aria-expanded', 'false');
        }, 120);
      });
    }

    composer.prepend(toggle);
    composer.append(tray);
  }

  function installTabs() {
    if (!app || $('bottomTabs')) return;
    const panels = node('main', 'workspace-panels');
    panels.id = 'workspacePanels';
    panels.setAttribute('aria-live', 'polite');

    for (const [id] of tabs.filter(([id]) => id !== 'chat')) {
      const panel = node('section', 'workspace-panel hidden');
      panel.id = 'panel-' + id;
      panel.dataset.loaded = '0';
      const inner = node('div', 'workspace-panel-inner');
      panel.append(inner);
      panels.append(panel);
    }

    const composer = $('composerWrap');
    app.insertBefore(panels, composer || null);

    const nav = node('nav', 'bottom-tabs hidden');
    nav.id = 'bottomTabs';
    nav.setAttribute('aria-label', 'Разделы Atlas');

    for (const [id, icon, label] of tabs) {
      const button = node('button', 'tab-button');
      button.type = 'button';
      button.dataset.tab = id;
      button.setAttribute('aria-label', label);
      const iconNode = node('span', 'tab-icon', icon);
      const labelNode = node('span', 'tab-label', label);
      button.append(iconNode, labelNode);
      button.addEventListener('click', () => activateTab(id));
      nav.append(button);
    }
    app.append(nav);
  }

  function syncAuthUi() {
    const nav = $('bottomTabs');
    const chat = $('chatCard');
    authenticated = Boolean(chat && !chat.classList.contains('hidden'));
    if (nav) nav.classList.toggle('hidden', !authenticated);
    if (!authenticated && activeTab !== 'chat') activateTab('chat', false);
  }

  function activateTab(id, persist = true) {
    if (!tabs.some(([tab]) => tab === id)) id = 'chat';
    activeTab = id;
    if (persist) localStorage.setItem(TAB_KEY, id);
    if (app) app.dataset.activeTab = id;

    document.querySelectorAll('.tab-button').forEach((button) => {
      const on = button.dataset.tab === id;
      button.classList.toggle('active', on);
      button.setAttribute('aria-current', on ? 'page' : 'false');
    });
    document.querySelectorAll('.workspace-panel').forEach((panel) => {
      panel.classList.toggle('hidden', panel.id !== 'panel-' + id);
    });
    if (id !== 'chat' && authenticated) loadPanel(id);
    if (id === 'chat') window.setTimeout(() => {
      const list = $('chatList');
      if (list) list.scrollTop = list.scrollHeight;
    }, 40);
  }

  function heading(title, subtitle, action) {
    const wrap = node('div', 'workspace-heading');
    const copy = node('div');
    copy.append(node('h2', '', title), node('p', '', subtitle));
    wrap.append(copy);
    if (action) wrap.append(action);
    return wrap;
  }

  function panelInner(id) {
    const panel = $('panel-' + id);
    return panel && panel.querySelector('.workspace-panel-inner');
  }

  function showPanelError(inner, error) {
    inner.replaceChildren();
    const card = node('div', 'atlas-card');
    card.append(node('h3', '', 'Не удалось загрузить'), node('p', '', error.message || String(error)));
    inner.append(card);
  }

  async function loadProjects() {
    const inner = panelInner('projects');
    if (!inner) return;
    inner.replaceChildren();
    const add = node('button', 'panel-action', '＋ Проект');
    add.type = 'button';
    add.addEventListener('click', createProject);
    inner.append(heading('Проекты', 'У каждого — собственные чат, память и задачи.', add));

    try {
      const data = await request('/app-projects');
      const projects = data.projects || [];
      for (const project of projects) {
        const id = String(project.id || '');
        const card = node('button', 'atlas-card');
        card.type = 'button';
        card.style.width = '100%';
        card.style.textAlign = 'left';
        card.style.color = 'inherit';
        card.style.cursor = 'pointer';
        const row = node('div', 'atlas-card-row');
        const copy = node('div');
        copy.append(node('h3', '', String(project.name || id)));
        copy.append(node('p', '', id === projectId() ? 'Текущий проект' : 'Открыть проект'));
        row.append(copy);
        if (id === projectId()) row.append(node('span', 'status-pill connected', 'Активен'));
        card.append(row);
        card.addEventListener('click', () => {
          if (id && id !== projectId()) {
            localStorage.setItem(ACTIVE_PROJECT, id);
            localStorage.setItem(TAB_KEY, 'chat');
            location.reload();
          } else {
            activateTab('chat');
          }
        });
        inner.append(card);
      }
    } catch (error) {
      showPanelError(inner, error);
    }
  }

  async function createProject() {
    const name = window.prompt('Название проекта');
    if (!name || !name.trim()) return;
    try {
      const data = await request('/app-projects', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name.trim()}),
      });
      const project = data.project || {};
      if (project.id) localStorage.setItem(ACTIVE_PROJECT, project.id);
      localStorage.setItem(TAB_KEY, 'chat');
      location.reload();
    } catch (error) {
      window.alert(error.message);
    }
  }

  async function loadMemory() {
    const inner = panelInner('memory');
    if (!inner) return;
    inner.replaceChildren();
    inner.append(heading('Память', 'Сохраняется в PostgreSQL и не зависит от телефона.'));

    const form = node('form', 'panel-form');
    const kind = node('select', 'panel-input');
    for (const [value, label] of [
      ['note', 'Заметка'],
      ['decision', 'Решение'],
      ['preference', 'Предпочтение'],
      ['goal', 'Цель'],
      ['constraint', 'Ограничение'],
    ]) {
      const option = node('option', '', label);
      option.value = value;
      kind.append(option);
    }
    const input = node('textarea', 'panel-input');
    input.rows = 3;
    input.placeholder = 'Что Atlas должен помнить?';
    const submit = node('button', 'panel-action', 'Сохранить в память');
    submit.type = 'submit';
    form.append(kind, input, submit);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const content = input.value.trim();
      if (!content) return;
      submit.disabled = true;
      try {
        await request('/app-projects/' + encodeURIComponent(projectId()) + '/memory', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({kind: kind.value, content}),
        });
        input.value = '';
        await loadMemory();
      } catch (error) {
        window.alert(error.message);
      } finally {
        submit.disabled = false;
      }
    });
    inner.append(form);

    try {
      const data = await request('/app-projects/' + encodeURIComponent(projectId()) + '/memory');
      const memories = data.memories || [];
      if (!memories.length) {
        inner.append(node('div', 'empty-state', 'Память проекта пока пуста.'));
        return;
      }
      for (const memory of memories) {
        const card = node('article', 'atlas-card');
        const row = node('div', 'atlas-card-row');
        const copy = node('div');
        copy.append(node('div', 'memory-kind', String(memory.kind || 'note')));
        copy.append(node('p', '', String(memory.content || '')));
        const remove = node('button', 'panel-action secondary', 'Удалить');
        remove.type = 'button';
        remove.addEventListener('click', async () => {
          if (!confirm('Удалить эту запись из памяти?')) return;
          try {
            await request(
              '/app-projects/' + encodeURIComponent(projectId()) + '/memory/' + encodeURIComponent(memory.id),
              {method: 'DELETE'}
            );
            await loadMemory();
          } catch (error) {
            window.alert(error.message);
          }
        });
        row.append(copy, remove);
        card.append(row);
        const date = formatDate(memory.updated_at);
        if (date) card.append(node('div', 'action-meta', date));
        inner.append(card);
      }
    } catch (error) {
      showPanelError(inner, error);
    }
  }

  function fileSize(value) {
    const size = Number(value || 0);
    if (size < 1024) return size + ' Б';
    if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' КБ';
    return (size / (1024 * 1024)).toFixed(1) + ' МБ';
  }

  async function loadFiles() {
    const inner = panelInner('files');
    if (!inner) return;
    inner.replaceChildren();
    inner.append(heading('Файлы', 'Вложения сохраняются в проекте и доступны после перезапуска.'));

    const selected = window.atlasFileCenter?.selectedIds() || [];
    if (selected.length) {
      const selectedCard = node('div', 'atlas-card selected-files-card');
      selectedCard.append(node('h3', '', 'Для следующей команды: ' + selected.length + ' из 4'));
      selectedCard.append(node('p', '', 'Откройте чат и отправьте команду — выбранные файлы добавятся автоматически.'));
      const clear = node('button', 'panel-action secondary', 'Очистить выбор');
      clear.type = 'button';
      clear.addEventListener('click', () => {
        window.atlasFileCenter?.clear();
        loadFiles();
      });
      selectedCard.append(clear);
      inner.append(selectedCard);
    }

    try {
      const data = await request('/app-files?project_id=' + encodeURIComponent(projectId()));
      const files = data.files || [];
      if (!files.length) {
        inner.append(node('div', 'empty-state', 'Отправьте PDF, фото или таблицу в чате — Atlas сохранит файл здесь.'));
        return;
      }
      for (const file of files) {
        const card = node('article', 'atlas-card');
        const row = node('div', 'atlas-card-row');
        const copy = node('div');
        copy.append(node('h3', '', String(file.name || 'Файл')));
        copy.append(node('p', '', String(file.media_type || 'file') + ' · ' + fileSize(file.size_bytes)));
        const actions = node('div', 'file-actions');
        const isSelected = window.atlasFileCenter?.isSelected(file.id);
        const use = node('button', 'panel-action ' + (isSelected ? 'secondary' : ''), isSelected ? 'Убрать' : 'Использовать');
        use.type = 'button';
        use.addEventListener('click', () => {
          try {
            if (isSelected) window.atlasFileCenter?.unselect(file.id);
            else window.atlasFileCenter?.select(file.id);
            loadFiles();
          } catch (error) {
            window.alert(error.message);
          }
        });
        const remove = node('button', 'panel-action secondary file-delete', 'Удалить');
        remove.type = 'button';
        remove.addEventListener('click', async () => {
          if (!confirm('Удалить файл «' + String(file.name || 'Файл') + '» из проекта?')) return;
          try {
            await request(
              '/app-files/' + encodeURIComponent(file.id) + '?project_id=' + encodeURIComponent(projectId()),
              {method: 'DELETE'}
            );
            window.atlasFileCenter?.unselect(file.id);
            await loadFiles();
          } catch (error) {
            window.alert(error.message);
          }
        });
        actions.append(use, remove);
        row.append(copy, actions);
        card.append(row);
        const date = formatDate(file.updated_at);
        if (date) card.append(node('div', 'action-meta', date));
        inner.append(card);
      }
    } catch (error) {
      showPanelError(inner, error);
    }
  }

  function scheduleLabel(item) {
    if (item.frequency === 'once') return 'Один раз';
    if (item.frequency === 'daily') return 'Каждый день · ' + item.time_local;
    const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
    const days = (item.weekdays || []).map((day) => dayNames[Number(day)]).filter(Boolean).join(', ');
    return days + ' · ' + item.time_local;
  }

  async function loadSchedules() {
    const inner = panelInner('auto');
    if (!inner) return;
    inner.replaceChildren();
    inner.append(heading('Автоматизации', 'Безопасные задачи по времени Europe/Berlin. Результат придёт через Push.'));

    const form = node('form', 'panel-form schedule-form');
    const name = node('input', 'panel-input');
    name.placeholder = 'Название, например «Утренний отчёт»';
    name.maxLength = 100;
    const task = node('textarea', 'panel-input');
    task.rows = 3;
    task.placeholder = 'Что Atlas должен сделать?';
    const frequency = node('select', 'panel-input');
    for (const [value, label] of [['daily', 'Каждый день'], ['weekly', 'По дням недели'], ['once', 'Один раз']]) {
      const option = node('option', '', label);
      option.value = value;
      frequency.append(option);
    }
    const timeInput = node('input', 'panel-input');
    timeInput.type = 'time';
    timeInput.value = '09:00';
    const onceInput = node('input', 'panel-input hidden');
    onceInput.type = 'datetime-local';
    const weekdayWrap = node('div', 'weekday-picker hidden');
    const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
    dayNames.forEach((label, index) => {
      const item = node('label', 'weekday-chip');
      const input = node('input');
      input.type = 'checkbox';
      input.value = String(index);
      if (index < 5) input.checked = true;
      item.append(input, node('span', '', label));
      weekdayWrap.append(item);
    });
    const submit = node('button', 'panel-action', 'Создать автоматизацию');
    submit.type = 'submit';

    const syncFields = () => {
      const once = frequency.value === 'once';
      const weekly = frequency.value === 'weekly';
      timeInput.classList.toggle('hidden', once);
      onceInput.classList.toggle('hidden', !once);
      weekdayWrap.classList.toggle('hidden', !weekly);
    };
    frequency.addEventListener('change', syncFields);
    form.append(name, task, frequency, timeInput, onceInput, weekdayWrap, submit);
    syncFields();
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const weekdays = Array.from(weekdayWrap.querySelectorAll('input:checked')).map((input) => Number(input.value));
      const payload = {
        project_id: projectId(),
        name: name.value.trim(),
        task: task.value.trim(),
        frequency: frequency.value,
        timezone: 'Europe/Berlin',
        time_local: timeInput.value || '09:00',
        weekdays,
        run_at: onceInput.value || null,
      };
      if (!payload.name || !payload.task) return;
      submit.disabled = true;
      try {
        await request('/app-schedules', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload),
        });
        name.value = '';
        task.value = '';
        await loadSchedules();
      } catch (error) {
        window.alert(error.message);
      } finally {
        submit.disabled = false;
      }
    });
    inner.append(form);

    try {
      const data = await request('/app-schedules?project_id=' + encodeURIComponent(projectId()));
      const schedules = data.schedules || [];
      if (!schedules.length) {
        inner.append(node('div', 'empty-state', 'Автоматизаций пока нет. Создайте первую выше.'));
        return;
      }
      for (const schedule of schedules) {
        const card = node('article', 'atlas-card');
        const row = node('div', 'atlas-card-row');
        const copy = node('div');
        copy.append(node('h3', '', String(schedule.name || 'Автоматизация')));
        copy.append(node('p', '', scheduleLabel(schedule)));
        const status = node('span', 'status-pill ' + (schedule.enabled ? 'connected' : 'disconnected'), schedule.enabled ? 'Активна' : 'Пауза');
        row.append(copy, status);
        card.append(row);
        card.append(node('p', 'schedule-task', String(schedule.task || '')));
        const meta = node('div', 'action-meta');
        if (schedule.next_run_at) meta.append(node('span', '', 'Следующий запуск: ' + formatDate(schedule.next_run_at)));
        if (schedule.last_run_at) meta.append(node('span', '', 'Последний: ' + formatDate(schedule.last_run_at)));
        card.append(meta);
        const controls = node('div', 'schedule-actions');
        const toggle = node('button', 'panel-action secondary', schedule.enabled ? 'Пауза' : 'Возобновить');
        toggle.type = 'button';
        toggle.addEventListener('click', async () => {
          try {
            await request('/app-schedules/' + encodeURIComponent(schedule.id), {
              method: 'PATCH',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({project_id: projectId(), enabled: !schedule.enabled}),
            });
            await loadSchedules();
          } catch (error) { window.alert(error.message); }
        });
        const remove = node('button', 'panel-action secondary file-delete', 'Удалить');
        remove.type = 'button';
        remove.addEventListener('click', async () => {
          if (!confirm('Удалить автоматизацию «' + String(schedule.name || '') + '»?')) return;
          try {
            await request('/app-schedules/' + encodeURIComponent(schedule.id) + '?project_id=' + encodeURIComponent(projectId()), {method: 'DELETE'});
            await loadSchedules();
          } catch (error) { window.alert(error.message); }
        });
        controls.append(toggle, remove);
        card.append(controls);
        inner.append(card);
      }
    } catch (error) {
      showPanelError(inner, error);
    }
  }

  async function loadActions() {
    const inner = panelInner('actions');
    if (!inner) return;
    inner.replaceChildren();
    const refresh = node('button', 'panel-action secondary', 'Обновить');
    refresh.type = 'button';
    refresh.addEventListener('click', loadActions);
    inner.append(heading('Действия', 'Реальные вызовы инструментов — без скрытых рассуждений.', refresh));

    try {
      const data = await request('/app-actions?project_id=' + encodeURIComponent(projectId()));
      const actions = data.actions || [];
      if (!actions.length) {
        inner.append(node('div', 'empty-state', 'В этом проекте действий пока нет.'));
        return;
      }
      for (const action of actions) {
        const card = node('article', 'atlas-card');
        const row = node('div', 'atlas-card-row');
        const copy = node('div');
        copy.append(node('h3', '', String(action.tool || 'Atlas')));
        copy.append(node('p', '', action.status === 'success' ? 'Выполнено' : 'Ошибка'));
        row.append(copy, node('span', 'status-pill ' + (action.status === 'success' ? 'connected' : 'disconnected'), String(action.status || 'unknown')));
        card.append(row);
        const meta = node('div', 'action-meta');
        const date = formatDate(action.created_at);
        if (date) meta.append(node('span', '', date));
        if (action.duration_ms !== null && action.duration_ms !== undefined) {
          meta.append(node('span', '', String(action.duration_ms) + ' мс'));
        }
        card.append(meta);
        inner.append(card);
      }
    } catch (error) {
      showPanelError(inner, error);
    }
  }

  async function loadPlugins() {
    const inner = panelInner('plugins');
    if (!inner) return;
    inner.replaceChildren();
    const refresh = node('button', 'panel-action secondary', 'Проверить');
    refresh.type = 'button';
    refresh.addEventListener('click', loadPlugins);
    inner.append(heading('Системы и плагины', 'Состояние подключений и реальные уровни разрешений.', refresh));

    try {
      const [statusData, permissionData, data] = await Promise.all([
        request('/app-system-status'),
        request('/app-permissions'),
        request('/app-plugins'),
      ]);

      const systemTitle = node('h3', 'panel-section-title', 'Состояние систем');
      inner.append(systemTitle);
      const systemGrid = node('div', 'system-grid');
      for (const system of statusData.systems || []) {
        const card = node('article', 'system-card');
        const mark = node('span', 'system-mark ' + String(system.status || 'not-configured'), system.connected ? '✓' : '—');
        const copy = node('div');
        copy.append(node('strong', '', String(system.name || system.id)));
        copy.append(node('small', '', String(system.detail || '')));
        card.append(mark, copy);
        systemGrid.append(card);
      }
      inner.append(systemGrid);

      inner.append(node('h3', 'panel-section-title', 'Разрешения'));
      for (const level of permissionData.levels || []) {
        const card = node('article', 'atlas-card permission-card');
        const row = node('div', 'atlas-card-row');
        const copy = node('div');
        copy.append(node('h3', '', String(level.name || level.id)));
        copy.append(node('p', '', String(level.description || '')));
        row.append(copy, node('span', 'status-pill ' + (level.automatic ? 'connected' : 'confirmation'), level.automatic ? 'Авто' : 'Подтверждение'));
        card.append(row);
        inner.append(card);
      }

      inner.append(node('h3', 'panel-section-title', 'Плагины'));
      for (const plugin of data.plugins || []) {
        const card = node('article', 'atlas-card');
        const row = node('div', 'atlas-card-row');
        const lead = node('div', 'atlas-card-row');
        lead.style.justifyContent = 'flex-start';
        const icon = node('div', 'plugin-icon', String(plugin.name || '?').slice(0, 1));
        const copy = node('div');
        copy.append(node('h3', '', String(plugin.name || plugin.id)));
        copy.append(node('p', '', String(plugin.description || '')));
        lead.append(icon, copy);
        const pill = node('span', 'status-pill ' + String(plugin.status || 'disconnected'), statusLabel(plugin.status));
        row.append(lead, pill);
        card.append(row);
        const permission = node('div', 'action-meta');
        permission.append(node('span', '', 'Доступ: ' + permissionLabel(plugin.permission)));
        if (plugin.requires_confirmation) permission.append(node('span', '', 'Изменения — с подтверждением'));
        card.append(permission);
        inner.append(card);
      }
    } catch (error) {
      showPanelError(inner, error);
    }
  }

  function statusLabel(status) {
    return ({
      connected: 'Подключён',
      available: 'Готов',
      'knowledge-ready': 'Обучен',
      disconnected: 'Не подключён',
      healthy: 'Работает',
      'not-configured': 'Не настроен',
    })[status] || String(status || 'Неизвестно');
  }

  function permissionLabel(permission) {
    return ({
      'read-only': 'чтение',
      'read-write': 'чтение и запись',
      'confirm-writes': 'запись с подтверждением',
      budgeted: 'в пределах лимита',
    })[permission] || String(permission || 'не указан');
  }

  async function loadPanel(id) {
    if (id === 'projects') return loadProjects();
    if (id === 'memory') return loadMemory();
    if (id === 'files') return loadFiles();
    if (id === 'auto') return loadSchedules();
    if (id === 'actions') return loadActions();
    if (id === 'plugins') return loadPlugins();
  }

  async function detectSession() {
    try {
      const data = await request('/app-session');
      authenticated = Boolean(data.authenticated);
    } catch {
      authenticated = false;
    }
    syncAuthUi();
    activateTab(authenticated ? activeTab : 'chat', false);
  }

  function init() {
    installComposerTray();
    installTabs();
    setViewportHeight();

    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', setViewportHeight);
      window.visualViewport.addEventListener('scroll', setViewportHeight);
    }
    window.addEventListener('orientationchange', () => {
      baselineHeight = window.innerHeight;
      window.setTimeout(setViewportHeight, 120);
    });

    const chat = $('chatCard');
    if (chat) new MutationObserver(syncAuthUi).observe(chat, {
      attributes: true,
      attributeFilter: ['class'],
    });
    const login = $('loginBtn');
    if (login) login.addEventListener('click', () => window.setTimeout(detectSession, 700));
    const logout = $('logoutBtn');
    if (logout) logout.addEventListener('click', () => {
      localStorage.setItem(TAB_KEY, 'chat');
    });

    window.addEventListener('atlas-files-changed', () => {
      if (activeTab === 'files' && authenticated) loadFiles();
    });
    window.addEventListener('atlas-file-error', (event) => {
      window.alert(event.detail || 'Не удалось добавить сохранённый файл');
    });

    detectSession();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once: true});
  } else {
    init();
  }
})();
