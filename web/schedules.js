(() => {
  'use strict';

  function openAutomation() {
    if (window.AtlasAutomationStudio?.open) {
      window.AtlasAutomationStudio.open();
      return;
    }
    if (window.AtlasStudios?.open) {
      window.AtlasStudios.open('automation');
      return;
    }
    const tab = [...document.querySelectorAll('[data-tab]')]
      .find((item) => String(item.dataset.tab || '').toLowerCase() === 'auto');
    if (tab) {
      tab.click();
      return;
    }
    window.AtlasNotice?.warn?.('Automation Studio ещё загружается. Попробуйте снова через секунду.');
  }

  function install() {
    const settings = document.querySelector('#settingsCard .modal');
    if (!settings || document.getElementById('legacyAutomationBtn')) return;
    const button = document.createElement('button');
    button.id = 'legacyAutomationBtn';
    button.type = 'button';
    button.textContent = 'Automation Studio';
    button.addEventListener('click', openAutomation);
    settings.insertBefore(button, settings.firstChild);
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', install, {once: true})
    : install();
})();
