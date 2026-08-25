(() => {
  'use strict';
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Автоматизации';
  button.addEventListener('click', () => window.alert('Раздел расписаний готовится.'));
  const settings = document.querySelector('#settingsCard .modal');
  if (settings) settings.insertBefore(button, settings.firstChild);
})();
