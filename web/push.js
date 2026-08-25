(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  let busy = false;

  function supported() {
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  }

  function standalone() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  }

  function applicationKey(value) {
    const padding = '='.repeat((4 - value.length % 4) % 4);
    const raw = atob((value + padding).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, (char) => char.charCodeAt(0));
  }

  async function jsonRequest(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.error || 'Ошибка уведомлений');
    return data;
  }

  async function saveSubscription(subscription) {
    await jsonRequest('/app-push/subscribe', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(subscription.toJSON()),
    });
  }

  async function syncStatus() {
    const button = $('notificationBtn');
    if (!button) return;
    if (!supported()) {
      button.textContent = 'Push недоступен в этом браузере';
      button.disabled = true;
      return;
    }
    if (!standalone()) {
      button.textContent = 'Установите Atlas для Push';
      return;
    }
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await saveSubscription(subscription);
        button.textContent = 'Push-уведомления: включены';
        button.dataset.pushEnabled = '1';
      } else {
        button.textContent = 'Включить Push-уведомления';
        button.dataset.pushEnabled = '0';
      }
    } catch {
      button.textContent = 'Включить Push-уведомления';
    }
  }

  async function togglePush(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    const button = $('notificationBtn');
    if (!button || busy) return;
    if (!supported()) {
      button.textContent = 'Push недоступен в этом браузере';
      return;
    }
    if (!standalone()) {
      button.textContent = 'Сначала добавьте Atlas на экран Домой';
      return;
    }

    busy = true;
    button.disabled = true;
    try {
      const registration = await navigator.serviceWorker.ready;
      const current = await registration.pushManager.getSubscription();
      if (current) {
        const endpoint = current.endpoint;
        await current.unsubscribe();
        await jsonRequest('/app-push/subscribe', {
          method: 'DELETE',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({endpoint}),
        });
        button.textContent = 'Включить Push-уведомления';
        button.dataset.pushEnabled = '0';
        return;
      }

      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        button.textContent = 'Push запрещён в настройках iPhone';
        return;
      }
      const config = await jsonRequest('/app-push/config');
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationKey(config.public_key),
      });
      await saveSubscription(subscription);
      button.textContent = 'Push-уведомления: включены';
      button.dataset.pushEnabled = '1';
      await jsonRequest('/app-push/test', {method: 'POST'});
    } catch (error) {
      button.textContent = error.message || 'Не удалось включить Push';
    } finally {
      busy = false;
      button.disabled = false;
    }
  }

  function init() {
    const button = $('notificationBtn');
    if (!button || button.dataset.pushBound) return;
    button.dataset.pushBound = '1';
    button.addEventListener('click', togglePush);
    const login = $('loginBtn');
    if (login) login.addEventListener('click', () => window.setTimeout(syncStatus, 1000));
    syncStatus();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once: true});
  } else {
    init();
  }
})();