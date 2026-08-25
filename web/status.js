(function () {
  'use strict';

  var F = window.fetch.bind(window);
  var bar = null;
  var label = null;
  var timer = 0;
  var lastText = '';

  function ensureBar() {
    if (bar) return;
    var composerWrap = document.getElementById('composerWrap');
    var composer = document.getElementById('composer');
    if (!composerWrap || !composer || !composer.parentNode) return;

    bar = document.createElement('div');
    bar.id = 'taskStatusBar';
    bar.className = 'attachment-bar hidden';
    bar.setAttribute('aria-live', 'polite');

    var chip = document.createElement('div');
    chip.className = 'chip';

    label = document.createElement('span');
    chip.appendChild(label);
    bar.appendChild(chip);
    composer.parentNode.insertBefore(bar, composer);
  }

  function clearTimer() {
    if (timer) {
      clearTimeout(timer);
      timer = 0;
    }
  }

  function setStatus(text, autoHideMs) {
    if (autoHideMs === void 0) autoHideMs = 0;
    ensureBar();
    clearTimer();

    if (!bar || !label) return;

    if (!text) {
      bar.classList.add('hidden');
      lastText = '';
      label.textContent = '';
      return;
    }

    lastText = String(text);
    label.textContent = lastText;
    bar.classList.remove('hidden');

    if (autoHideMs > 0) {
      var current = lastText;
      timer = window.setTimeout(function () {
        if (lastText === current) {
          setStatus('');
        }
      }, autoHideMs);
    }
  }

  function isAppJobsPost(input, method) {
    return method === 'POST' && typeof input === 'string' && /\/app-jobs\/?$/.test(input);
  }

  function isAppJobItem(input, method) {
    return (method === 'GET' || method === 'DELETE') && typeof input === 'string' && /\/app-jobs\/[^/]+\/?$/.test(input);
  }

  window.fetch = function (input, init) {
    var method = ((init && init.method) || 'GET').toUpperCase();
    var isStringInput = typeof input === 'string';
    var url = isStringInput ? input : (input && input.url) || '';

    if (isAppJobsPost(url, method)) {
      setStatus('Отправляю задачу…');
      return F(input, init).then(function (response) {
        if (response && response.ok) {
          setStatus('Задача в очереди…');
        } else {
          setStatus('Не удалось запустить задачу', 3500);
        }
        return response;
      });
    }

    if (isAppJobItem(url, method) && method === 'GET') {
      return F(input, init).then(function (response) {
        var clone = response.clone();
        return clone.json().then(function (data) {
          var status = data && data.status;
          if (status === 'queued') {
            setStatus('Задача в очереди…');
          } else if (status === 'running' && data.recovering) {
            setStatus('Восстанавливаю соединение…');
          } else if (status === 'running') {
            setStatus('Atlas работает…');
          } else if (status === 'done') {
            setStatus('Готово', 1800);
          } else if (status === 'error') {
            setStatus('Ошибка задачи', 3500);
          } else if (status === 'cancelled') {
            setStatus('Задача остановлена', 2500);
          }
          return response;
        }).catch(function () {
          return response;
        });
      }).catch(function (err) {
        setStatus('Нет связи — пытаюсь восстановить…');
        throw err;
      });
    }

    if (isAppJobItem(url, method) && method === 'DELETE') {
      setStatus('Останавливаю задачу…');
      return F(input, init).then(function (response) {
        if (response && response.ok) {
          setStatus('Задача остановлена', 1800);
        }
        return response;
      });
    }

    return F(input, init);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureBar, { once: true });
  } else {
    ensureBar();
  }
}());
