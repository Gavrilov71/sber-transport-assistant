const form = document.querySelector('#chat-form');
const input = document.querySelector('#message');
const send = document.querySelector('#send');
const messages = document.querySelector('#messages');
const health = document.querySelector('#health');
const root = document.documentElement;
const home = document.querySelector('#home');
const chat = document.querySelector('#chat');
const homeComposer = document.querySelector('#home-composer');
const chatComposer = document.querySelector('#chat-composer');
const resetDisplay = document.querySelector('#reset-display');
const newDialog = document.querySelector('#new-dialog');
const contrastToggle = document.querySelector('#contrast-toggle');
const voiceModal = document.querySelector('#voice-modal');
const voiceState = document.querySelector('#voice-state');
const voiceText = document.querySelector('#voice-text');
const DISPLAY_KEY = 'transport-assistant-display';
const CONVERSATION_KEY = 'transport-assistant-conversation';
let conversationId = sessionStorage.getItem(CONVERSATION_KEY) || null;
let busy = false;
let recognition = null;
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

function escapeHtml(value = '') {
  return String(value).replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}
function safeUrl(value) {
  try { const url = new URL(value); return url.protocol === 'https:' ? url.href : null; } catch (_) { return null; }
}
function loadDisplayPrefs() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(DISPLAY_KEY) || '{}'); } catch (_) {}
  const theme = ['light', 'dark', 'contrast'].includes(saved.theme) ? saved.theme : 'light';
  const scale = ['normal', 'large', 'xlarge'].includes(saved.scale) ? saved.scale : 'normal';
  applyDisplayPrefs(theme, scale, false);
}
function saveDisplayPrefs() {
  try { localStorage.setItem(DISPLAY_KEY, JSON.stringify({theme: root.dataset.theme, scale: root.dataset.scale})); } catch (_) {}
}
function applyDisplayPrefs(theme, scale, persist = true) {
  root.dataset.theme = theme; root.dataset.scale = scale;
  document.querySelectorAll('[data-theme-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.themeChoice === theme)));
  document.querySelectorAll('[data-scale-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.scaleChoice === scale)));
  contrastToggle.setAttribute('aria-pressed', String(theme === 'contrast'));
  if (persist) saveDisplayPrefs();
}
function showChat() {
  if (!chat.hidden) return;
  home.hidden = true; chat.hidden = false; chatComposer.appendChild(form);
  window.scrollTo({top: 0, behavior: 'instant'});
}
function showHome() {
  chat.hidden = true; home.hidden = false; homeComposer.appendChild(form);
  window.scrollTo({top: 0, behavior: 'instant'});
}
function renderStatus(status, routeResolution) {
  const actual = routeResolution?.status === 'not_found' ? 'not_found' : status;
  const labels = {answered:'Ответ по вашему запросу',clarify:'Нужно уточнение',no_data:'Нет подтверждённых данных',not_found:'Маршрут не найден',service_error:'Временная ошибка сервиса'};
  return actual ? `<div class="answer-status ${escapeHtml(actual)}">${escapeHtml(labels[actual] || labels.no_data)}</div>` : '';
}
function renderSourceCard(source, index) {
  const title = escapeHtml(source.title || `Источник ${index + 1}`);
  const url = safeUrl(source.url);
  return `<div class="source-card"><span class="source-card__eyebrow">Официальный источник</span><strong>${title}</strong>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Открыть источник →</a>` : ''}</div>`;
}
function renderAuthorityCard(authority) {
  if (!authority || !authority.name) return '';
  const appeal = safeUrl(authority.appeal_url);
  const website = safeUrl(authority.website_url);
  const phone = authority.phone ? `<p class="authority-card__phone">Телефон: ${escapeHtml(authority.phone)}</p>` : '';
  const links = [appeal ? `<a class="primary-link" href="${escapeHtml(appeal)}" target="_blank" rel="noopener noreferrer">Подать обращение →</a>` : '', website ? `<a class="secondary-link" href="${escapeHtml(website)}" target="_blank" rel="noopener noreferrer">Официальный сайт →</a>` : ''].join('');
  return `<section class="authority-card" aria-label="Куда обратиться"><span class="authority-card__eyebrow">Основной адресат по этой проблеме</span><h3>Куда обратиться · ${escapeHtml(authority.name)}</h3>${authority.reason ? `<p><strong>Почему сюда:</strong> ${escapeHtml(authority.reason)}</p>` : ''}${phone}<div class="authority-card__links">${links}</div><div class="authority-card__prep"><strong>Что подготовить</strong><ul><li>Номер маршрута</li><li>Дату, время и место</li><li>Госномер или бортовой номер, если известен</li></ul></div></section>`;
}
function renderClarification(answer, routeResolution) {
  const text = String(answer || '').toLowerCase();
  const missing = routeResolution?.missing_fields || [];
  let choices = [];
  if (missing.includes('card_type') || /какая карта|банковск.*тройк|социальн.*карт/.test(text)) choices = [['Банковская карта','Банковская'],['Тройка','Тройка'],['Социальная карта','Социальная']];
  else if (missing.includes('municipality') || /каком городе|каком населен|каком муниципалитет/.test(text)) choices = [['Тула','Тула'],['Новомосковск','Новомосковск'],['Другой город','']];
  else if (missing.includes('route_number') || /номер маршрут|каком маршрут/.test(text)) choices = [['Указать маршрут','']];
  if (!choices.length) return '';
  return `<div class="clarification" aria-label="Варианты уточнения">${choices.map(([label,value]) => `<button type="button" data-clarify="${escapeHtml(value)}">${escapeHtml(label)}</button>`).join('')}</div>`;
}
function renderMessage(role, answer, meta = {}) {
  const article = document.createElement('article');
  article.className = `message ${role}`;
  const body = escapeHtml(answer || '').replace(/\n/g, '<br>');
  const sources = Array.isArray(meta.sources) ? meta.sources.map(renderSourceCard).join('') : '';
  const authority = role === 'assistant' ? renderAuthorityCard(meta.authority) : '';
  const status = role === 'assistant' ? renderStatus(meta.status, meta.route_resolution) : '';
  const clarify = role === 'assistant' && meta.status === 'clarify' ? renderClarification(answer, meta.route_resolution) : '';
  article.innerHTML = `${role === 'assistant' ? '<div class="assistant-label">Помощник</div>' : ''}<div class="bubble"><p>${body}</p>${status}${clarify}${meta.demo_mode ? '<div class="debug-meta">Тестовый режим без подключения модели</div>' : ''}</div>${authority}${sources ? `<div class="sources">${sources}</div>` : ''}`;
  messages.appendChild(article);
  article.scrollIntoView({behavior:'smooth',block:'nearest'});
  return article;
}
function setBusy(value) {
  busy = value; send.disabled = value; input.disabled = value;
  send.setAttribute('aria-label', value ? 'Ожидание ответа' : 'Отправить вопрос');
}
async function ask(question) {
  if (busy || !question.trim()) return;
  showChat();
  renderMessage('user', question);
  setBusy(true);
  const loading = document.createElement('article');
  loading.className = 'message assistant loading';
  loading.innerHTML = '<div class="assistant-label">Помощник</div><div class="bubble"><span class="loading-dots" aria-hidden="true"><i></i><i></i><i></i></span>Ищу информацию в официальных источниках…</div>';
  messages.appendChild(loading);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 75000);
  try {
    const response = await fetch('/api/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:question,conversation_id:conversationId}),signal:controller.signal});
    let data;
    try { data = await response.json(); } catch (_) { throw new Error('INVALID_JSON'); }
    if (!response.ok || !data || !['answered','clarify','no_data','service_error','not_found'].includes(data.status)) throw new Error('INVALID_RESPONSE');
    if (data.conversation_id) { conversationId = data.conversation_id; sessionStorage.setItem(CONVERSATION_KEY, conversationId); }
    loading.remove(); renderMessage('assistant', data.answer, data);
  } catch (_) {
    loading.remove();
    renderMessage('assistant','Сервис сейчас не смог обработать запрос. Попробуйте ещё раз через несколько секунд.',{status:'service_error'});
  } finally { clearTimeout(timeout); setBusy(false); input.focus(); }
}
form.addEventListener('submit', event => { event.preventDefault(); const value = input.value.trim(); if (value) { input.value = ''; ask(value); } });
input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); } });
document.querySelectorAll('[data-q]').forEach(button => button.addEventListener('click', () => ask(button.dataset.q)));
messages.addEventListener('click', event => { const button = event.target.closest('[data-clarify]'); if (!button) return; const value = button.dataset.clarify; if (value) ask(value); else input.focus(); });
document.querySelectorAll('[data-theme-choice]').forEach(button => button.addEventListener('click', () => applyDisplayPrefs(button.dataset.themeChoice, root.dataset.scale || 'normal')));
document.querySelectorAll('[data-scale-choice]').forEach(button => button.addEventListener('click', () => applyDisplayPrefs(root.dataset.theme || 'light', button.dataset.scaleChoice)));
contrastToggle.addEventListener('click', () => applyDisplayPrefs(root.dataset.theme === 'contrast' ? 'light' : 'contrast', root.dataset.scale || 'normal'));
resetDisplay.addEventListener('click', () => { localStorage.removeItem(DISPLAY_KEY); applyDisplayPrefs('light','normal',false); });
function resetConversation() {
  const oldId = conversationId; conversationId = null; sessionStorage.removeItem(CONVERSATION_KEY);
  messages.replaceChildren(); input.value = ''; showHome(); input.focus();
  if (oldId) fetch(`/api/conversations/${encodeURIComponent(oldId)}`,{method:'DELETE'}).catch(() => {});
}
newDialog.addEventListener('click', resetConversation);
document.querySelector('#home-link').addEventListener('click', event => { event.preventDefault(); showHome(); });
function setVoiceState(state, message) { voiceModal.dataset.state = state; voiceState.textContent = message; }
function stopRecognition() { if (recognition) { recognition.abort(); recognition = null; } }
function startVoice() {
  if (!Recognition) { setVoiceState('error','Этот браузер не поддерживает распознавание речи. Напишите вопрос ниже.'); return; }
  stopRecognition(); recognition = new Recognition(); recognition.lang = 'ru-RU'; recognition.interimResults = false; recognition.maxAlternatives = 1;
  recognition.onresult = event => { voiceText.value = event.results[0][0].transcript; setVoiceState('recognized','Проверьте распознанный текст перед отправкой.'); };
  recognition.onerror = event => setVoiceState('error', event.error === 'not-allowed' ? 'Разрешите доступ к микрофону в браузере.' : 'Не удалось распознать речь. Попробуйте ещё раз или напишите вопрос.');
  recognition.onend = () => { if (voiceModal.dataset.state === 'listening') setVoiceState('error','Речь не распознана. Попробуйте ещё раз.'); };
  try { recognition.start(); setVoiceState('listening','Слушаю ваш вопрос…'); } catch (_) { setVoiceState('error','Не удалось начать запись. Напишите вопрос.'); }
}
document.querySelector('#mic').addEventListener('click', () => { voiceText.value = ''; setVoiceState('idle','Голосовой ввод доступен, если браузер поддерживает распознавание речи.'); voiceModal.showModal(); startVoice(); });
document.querySelector('#voice-close').addEventListener('click', () => voiceModal.close());
voiceModal.addEventListener('close', stopRecognition);
document.querySelector('#voice-retry').addEventListener('click', () => { voiceText.value = ''; startVoice(); });
document.querySelector('#voice-send').addEventListener('click', () => { const text = voiceText.value.trim(); if (!text) { setVoiceState('error','Сначала произнесите или напишите вопрос.'); return; } voiceModal.close(); ask(text); });
homeComposer.appendChild(form); loadDisplayPrefs();
function updatePlaceholder() { input.placeholder = window.innerWidth <= 600 ? 'Напишите вопрос' : 'Например: почему карта не проходит в автобусе?'; }
window.addEventListener('resize', updatePlaceholder);
updatePlaceholder();
fetch('/api/health').then(r => r.json()).then(data => {
  health.textContent = data.agent_ready && data.rag_ready && !data.demo_mode ? 'Система готова · официальная база знаний подключена' : data.demo_mode ? 'Система готова · работает тестовая база знаний' : 'Система запущена · требуется построить базу знаний';
}).catch(() => { health.textContent = 'Сервер временно недоступен'; });

