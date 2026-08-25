(() => {
  'use strict';

  const MODE_KEY = 'atlas_conversation_mode';
  const $ = (id) => document.getElementById(id);
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let conversationMode = false;
  let recognition = null;
  let resultReceived = false;

  function setMode(on) {
    conversationMode = Boolean(on && SpeechRecognition);
    sessionStorage.setItem(MODE_KEY, conversationMode ? '1' : '0');
    const button = $('conversationModeBtn');
    const stop = $('stopVoiceBtn');
    if (button) button.textContent = conversationMode ? 'Разговорный режим: вкл' : 'Разговорный режим: выкл';
    if (stop) stop.classList.toggle('hidden', !conversationMode);
    if (!conversationMode) {
      try { if (recognition) recognition.abort(); } catch {}
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    }
  }

  function startListening() {
    if (!conversationMode || !recognition || document.hidden) return;
    resultReceived = false;
    try { recognition.start(); } catch {}
  }

  function installSpeechLoop() {
    if (!('speechSynthesis' in window)) return;
    const synth = window.speechSynthesis;
    const originalSpeak = synth.speak.bind(synth);
    synth.speak = (utterance) => {
      const previousEnd = utterance.onend;
      const previousError = utterance.onerror;
      utterance.onend = (event) => {
        if (typeof previousEnd === 'function') previousEnd.call(utterance, event);
        if (conversationMode) window.setTimeout(startListening, 450);
      };
      utterance.onerror = (event) => {
        if (typeof previousError === 'function') previousError.call(utterance, event);
      };
      return originalSpeak(utterance);
    };
  }

  function installRecognition() {
    if (!SpeechRecognition) return;
    recognition = new SpeechRecognition();
    recognition.lang = 'ru-RU';
    recognition.interimResults = false;
    recognition.continuous = false;

    recognition.onstart = () => {
      const button = $('conversationModeBtn');
      if (button) button.textContent = 'Слушаю…';
    };
    recognition.onresult = (event) => {
      const text = event.results?.[0]?.[0]?.transcript || '';
      if (!text.trim()) return;
      resultReceived = true;
      const input = $('messageInput');
      if (!input) return;
      input.value = text.trim();
      input.dispatchEvent(new Event('input', {bubbles: true}));
    };
    recognition.onend = () => {
      const button = $('conversationModeBtn');
      if (button) button.textContent = conversationMode ? 'Разговорный режим: вкл' : 'Разговорный режим: выкл';
      if (conversationMode && resultReceived) {
        const composer = $('composer');
        window.setTimeout(() => {
          if (composer && conversationMode) composer.requestSubmit();
        }, 180);
      }
    };
    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') setMode(false);
    };
  }

  function installControls() {
    const settings = $('settingsCard')?.querySelector('.modal');
    const voiceOutput = $('voiceOutputBtn');
    if (!settings || !voiceOutput || $('conversationModeBtn')) return;

    const conversation = document.createElement('button');
    conversation.id = 'conversationModeBtn';
    conversation.type = 'button';
    conversation.textContent = SpeechRecognition ? 'Разговорный режим: выкл' : 'Разговорный режим недоступен';
    conversation.disabled = !SpeechRecognition;

    const stop = document.createElement('button');
    stop.id = 'stopVoiceBtn';
    stop.type = 'button';
    stop.className = 'danger-btn hidden';
    stop.textContent = 'Стоп голос';

    voiceOutput.insertAdjacentElement('afterend', conversation);
    conversation.insertAdjacentElement('afterend', stop);

    conversation.addEventListener('click', () => {
      if (!SpeechRecognition) return;
      const next = !conversationMode;
      if (next && voiceOutput.textContent.includes('выкл')) voiceOutput.click();
      setMode(next);
      if (next) startListening();
    });
    stop.addEventListener('click', () => setMode(false));

    const composer = $('composer');
    if (composer) composer.addEventListener('submit', () => {
      try { if (recognition) recognition.abort(); } catch {}
    });

    setMode(sessionStorage.getItem(MODE_KEY) === '1');
  }

  installSpeechLoop();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      installRecognition();
      installControls();
    }, {once: true});
  } else {
    installRecognition();
    installControls();
  }
})();