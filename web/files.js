(() => {
  'use strict';

  const ACTIVE_PROJECT = 'atlas_active_project_id';
  const DEFAULT_PROJECT = 'project-general';
  const baseFetch = window.fetch.bind(window);

  function projectId() {
    return localStorage.getItem(ACTIVE_PROJECT) || DEFAULT_PROJECT;
  }

  function storageKey() {
    return 'atlas_selected_files:' + projectId();
  }

  function selectedIds() {
    try {
      const ids = JSON.parse(sessionStorage.getItem(storageKey()) || '[]');
      return Array.isArray(ids) ? ids.filter(Boolean).slice(0, 4) : [];
    } catch {
      return [];
    }
  }

  function saveSelected(ids) {
    sessionStorage.setItem(storageKey(), JSON.stringify(Array.from(new Set(ids)).slice(0, 4)));
    window.dispatchEvent(new CustomEvent('atlas-files-changed'));
  }

  async function fileAttachment(id) {
    const response = await baseFetch(
      '/app-files/' + encodeURIComponent(id) + '?project_id=' + encodeURIComponent(projectId())
    );
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.file) throw new Error(data.detail || 'Файл недоступен');
    return {
      name: String(data.file.name || 'file'),
      media_type: String(data.file.media_type || 'application/octet-stream'),
      data: String(data.file.data || ''),
    };
  }

  window.atlasFileCenter = {
    selectedIds,
    isSelected(id) {
      return selectedIds().includes(String(id));
    },
    select(id) {
      const ids = selectedIds();
      id = String(id || '');
      if (!id || ids.includes(id)) return;
      if (ids.length >= 4) throw new Error('Можно выбрать максимум 4 файла');
      saveSelected(ids.concat(id));
    },
    unselect(id) {
      saveSelected(selectedIds().filter((item) => item !== String(id)));
    },
    clear() {
      saveSelected([]);
    },
  };

  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    const isTask = method === 'POST' && (/\/app-jobs\/?$/.test(url) || /\/app-task\/?$/.test(url));
    const ids = isTask ? selectedIds() : [];

    if (ids.length && init && typeof init.body === 'string') {
      try {
        const body = JSON.parse(init.body);
        const current = Array.isArray(body.attachments) ? body.attachments : [];
        const room = Math.max(0, 4 - current.length);
        if (room > 0) {
          const attachments = await Promise.all(ids.slice(0, room).map(fileAttachment));
          init = Object.assign({}, init, {
            body: JSON.stringify(Object.assign({}, body, {
              attachments: current.concat(attachments),
            })),
          });
        }
      } catch (error) {
        window.dispatchEvent(new CustomEvent('atlas-file-error', {detail: error.message}));
        throw error;
      }
    }

    const response = await baseFetch(input, init);
    if (isTask && response.ok && ids.length) saveSelected([]);
    return response;
  };
})();