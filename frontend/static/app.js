/**
 * Enterprise Document Intelligence — Frontend Application
 * Vanilla JS, no dependencies
 */

const API = '';  // Same-origin; FastAPI serves this file

// ─── State ────────────────────────────────────────────────────────────────────
const state = {
  token: localStorage.getItem('edi_token') || null,
  user: JSON.parse(localStorage.getItem('edi_user') || 'null'),
  currentPage: 'dashboard',
  documents: [],
  conversations: [],
  currentConversationId: null,
  health: {},
};

// ─── Utilities ────────────────────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }
function $q(sel, el = document) { return el.querySelector(sel); }
function $qa(sel, el = document) { return [...el.querySelectorAll(sel)]; }

function toast(msg, type = 'info', duration = 3500) {
  const container = $('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

async function apiFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  if (opts.body instanceof FormData) delete headers['Content-Type'];

  const res = await fetch(`${API}${path}`, { ...opts, headers });
  if (res.status === 401) {
    logout();
    throw new Error('Session expired');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(text || ''));
  return d.innerHTML;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatDateTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function statusBadge(status) {
  return `<span class="badge badge-${status}">${status}</span>`;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────
function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem('edi_token');
  localStorage.removeItem('edi_user');
  showAuthScreen();
}

function showAuthScreen() {
  $('auth-screen').style.display = 'flex';
  $('app').style.display = 'none';
}

function showApp() {
  $('auth-screen').style.display = 'none';
  $('app').style.display = 'flex';
  updateUserBadge();
  navigateTo('dashboard');
}

function updateUserBadge() {
  if (!state.user) return;
  const initials = (state.user.name || state.user.email || 'U').slice(0, 2).toUpperCase();
  $('user-initials').textContent = initials;
  $('user-name-badge').textContent = state.user.name || state.user.email;
  $('user-email-badge').textContent = state.user.email;
}

async function handleLogin(email, password) {
  const btn = $('login-btn');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Signing in…';
  try {
    const data = await apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    state.token = data.access_token;
    state.user = { email: data.email, id: data.user_id, name: data.email.split('@')[0] };
    localStorage.setItem('edi_token', state.token);
    localStorage.setItem('edi_user', JSON.stringify(state.user));
    toast('Welcome back!', 'success');
    showApp();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign In';
  }
}

async function handleRegister(name, email, password) {
  const btn = $('register-btn');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Creating account…';
  try {
    const data = await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    });
    state.token = data.access_token;
    state.user = { email: data.email, id: data.user_id, name };
    localStorage.setItem('edi_token', state.token);
    localStorage.setItem('edi_user', JSON.stringify(state.user));
    toast('Account created!', 'success');
    showApp();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Create Account';
  }
}

// ─── Navigation ───────────────────────────────────────────────────────────────
function navigateTo(page) {
  state.currentPage = page;
  $qa('.page').forEach(p => p.classList.remove('active'));
  $qa('.nav-item').forEach(n => n.classList.remove('active'));

  const pageEl = $(`page-${page}`);
  if (pageEl) pageEl.classList.add('active');

  const navEl = document.querySelector(`.nav-item[data-page="${page}"]`);
  if (navEl) navEl.classList.add('active');

  // Load data for page
  switch (page) {
    case 'dashboard': loadDashboard(); break;
    case 'documents': loadDocuments(); break;
    case 'search':    break;
    case 'ask':       loadConversationList(); break;
    case 'health':    loadHealth(); break;
  }
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const [docsData, healthData] = await Promise.allSettled([
      apiFetch('/documents?limit=5'),
      apiFetch('/health'),
    ]);

    const docs = docsData.status === 'fulfilled' ? docsData.value : { documents: [], total: 0 };
    const health = healthData.status === 'fulfilled' ? healthData.value : {};

    $('dash-total-docs').textContent = docs.total || 0;

    const processed = (docs.documents || []).filter(d => d.status === 'processed').length;
    $('dash-processed').textContent = processed;

    const services = Object.values(health).filter(Boolean).length;
    $('dash-services').textContent = `${services}/${Object.keys(health).length || 6}`;

    // Recent docs
    const recentEl = $('dash-recent-docs');
    if (!docs.documents || docs.documents.length === 0) {
      recentEl.innerHTML = `<div class="empty-state"><div class="empty-icon">📄</div><h3>No documents yet</h3><p>Upload your first document to get started.</p></div>`;
    } else {
      recentEl.innerHTML = docs.documents.map(d => docItemHtml(d)).join('');
    }
  } catch (e) {
    console.error('Dashboard load error:', e);
  }
}

// ─── Documents ────────────────────────────────────────────────────────────────
async function loadDocuments() {
  const listEl = $('doc-list');
  listEl.innerHTML = `<div class="empty-state"><div class="spinner dark"></div></div>`;
  try {
    const data = await apiFetch('/documents?limit=50');
    state.documents = data.documents || [];
    renderDocumentList(state.documents);
  } catch (e) {
    listEl.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><h3>Failed to load documents</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}

function docItemHtml(doc) {
  const ext = (doc.filename || '').split('.').pop().toUpperCase();
  const icons = { PDF: '📕', DOCX: '📘', DOC: '📘', TXT: '📄', PNG: '🖼️', JPG: '🖼️', JPEG: '🖼️' };
  const icon = icons[ext] || '📄';
  return `
    <div class="doc-item" data-id="${escapeHtml(doc.id)}">
      <div class="doc-icon">${icon}</div>
      <div class="doc-info">
        <div class="doc-name" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</div>
        <div class="doc-meta">${formatDate(doc.created_at)} · ID: ${doc.id?.slice(0, 8)}…</div>
      </div>
      <div class="doc-actions">
        ${statusBadge(doc.status)}
        ${doc.status === 'uploaded' || doc.status === 'failed'
          ? `<button class="btn btn-primary" onclick="processDoc('${doc.id}', this)">⚙️ Process</button>`
          : `<button class="btn btn-secondary" onclick="askAboutDoc('${doc.id}')">💬 Ask</button>`
        }
      </div>
    </div>`;
}

function renderDocumentList(docs) {
  const listEl = $('doc-list');
  if (!docs || docs.length === 0) {
    listEl.innerHTML = `<div class="empty-state"><div class="empty-icon">📁</div><h3>No documents yet</h3><p>Upload a PDF, Word document, or image to get started.</p></div>`;
  } else {
    listEl.innerHTML = docs.map(d => docItemHtml(d)).join('');
  }
}

async function processDoc(docId, btn) {
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div>';
  try {
    await apiFetch(`/documents/${docId}/process`, { method: 'POST' });
    toast('Processing started…', 'info');
    setTimeout(loadDocuments, 2000);
  } catch (e) {
    toast(`Processing failed: ${e.message}`, 'error');
    btn.innerHTML = orig;
    btn.disabled = false;
  }
}

function askAboutDoc(docId) {
  navigateTo('ask');
  $('doc-filter').value = docId;
}

// ─── Upload ───────────────────────────────────────────────────────────────────
function setupUpload() {
  const zone = $('upload-zone');
  const fileInput = $('file-input');

  zone.addEventListener('click', () => fileInput.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const files = [...e.dataTransfer.files];
    if (files.length > 0) uploadFiles(files);
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) uploadFiles([...fileInput.files]);
  });
}

async function uploadFiles(files) {
  const progress = $('upload-progress');
  progress.style.display = 'block';
  progress.innerHTML = '';

  for (const file of files) {
    const rowId = `up-${Math.random().toString(36).slice(2)}`;
    progress.insertAdjacentHTML('beforeend', `
      <div id="${rowId}" class="doc-item" style="margin-bottom:.5rem">
        <div class="doc-icon">⏳</div>
        <div class="doc-info"><div class="doc-name">${escapeHtml(file.name)}</div><div class="doc-meta">Uploading…</div></div>
      </div>`);

    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API}/documents/upload`, {
        method: 'POST',
        headers: state.token ? { Authorization: `Bearer ${state.token}` } : {},
        body: fd,
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed');
      const data = await res.json();
      const row = $(rowId);
      row.querySelector('.doc-icon').textContent = '✅';
      row.querySelector('.doc-meta').textContent = `Uploaded · ID: ${data.id?.slice(0, 8)}…`;
      toast(`${file.name} uploaded!`, 'success');
    } catch (e) {
      const row = $(rowId);
      row.querySelector('.doc-icon').textContent = '❌';
      row.querySelector('.doc-meta').textContent = e.message;
      toast(`Upload failed: ${e.message}`, 'error');
    }
  }

  setTimeout(() => {
    progress.style.display = 'none';
    loadDocuments();
  }, 2000);
}

// ─── Search ───────────────────────────────────────────────────────────────────
let searchTimeout = null;

async function runSearch() {
  const query = $('search-query').value.trim();
  if (!query) return;

  const mode = $('search-mode').value;
  const topK = parseInt($('search-topk').value) || 5;
  const resultsEl = $('search-results');

  resultsEl.innerHTML = `<div class="empty-state"><div class="spinner dark" style="margin:0 auto"></div></div>`;

  const endpoint = mode === 'keyword' ? '/search/keyword'
                 : mode === 'semantic' ? '/search/semantic'
                 : '/search/hybrid';

  try {
    const data = await apiFetch(endpoint, {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK }),
    });

    const results = data.results || data;
    if (!results || results.length === 0) {
      resultsEl.innerHTML = `<div class="empty-state"><div class="empty-icon">🔍</div><h3>No results found</h3><p>Try a different query or search mode.</p></div>`;
      return;
    }

    const terms = query.toLowerCase().split(/\s+/);
    resultsEl.innerHTML = results.map((r, i) => {
      let text = escapeHtml(r.text || r.content || '');
      // Highlight terms
      terms.forEach(t => {
        if (t.length > 2) {
          text = text.replace(new RegExp(`(${t})`, 'gi'), '<mark>$1</mark>');
        }
      });
      return `
        <div class="result-card">
          <div class="result-meta">
            <span class="result-score">Score: ${(r.score || 0).toFixed(3)}</span>
            <span class="result-source">${r.source || mode}</span>
            ${r.page_number ? `<span class="badge badge-uploaded">Page ${r.page_number}</span>` : ''}
            ${r.chunk_index != null ? `<span class="result-source">Chunk #${r.chunk_index}</span>` : ''}
          </div>
          <div class="result-text">${text}</div>
        </div>`;
    }).join('');
  } catch (e) {
    resultsEl.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><h3>Search failed</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}

// ─── Ask / Q&A ────────────────────────────────────────────────────────────────
async function loadConversationList() {
  try {
    const convs = await apiFetch('/query/conversations?limit=20');
    state.conversations = convs || [];
    renderConversationList();
  } catch (e) {
    console.error('Conversation load error:', e);
  }
}

function renderConversationList() {
  const el = $('conv-list');
  if (!state.conversations || state.conversations.length === 0) {
    el.innerHTML = `<div style="padding:.75rem;font-size:.8rem;color:var(--sidebar-text);opacity:.6">No conversations yet</div>`;
    return;
  }
  el.innerHTML = state.conversations.map(c => `
    <div class="nav-item" onclick="loadConversation('${c.id}')" style="border-radius:.375rem;margin:.1rem .5rem;">
      <span class="icon">💬</span>
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(c.title || 'Chat')}</span>
    </div>`).join('');
}

async function loadConversation(convId) {
  state.currentConversationId = convId;
  $('chat-messages').innerHTML = `<div class="empty-state"><div class="spinner dark" style="margin:0 auto"></div></div>`;
  try {
    const data = await apiFetch(`/query/conversations/${convId}`);
    const msgs = data.messages || [];
    $('chat-messages').innerHTML = '';
    msgs.forEach(m => appendMessage(m.role === 'user' ? 'user' : 'ai', m.content, []));
  } catch (e) {
    toast('Failed to load conversation', 'error');
  }
}

function newConversation() {
  state.currentConversationId = null;
  $('chat-messages').innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">🤖</div>
      <h3>Ask anything about your documents</h3>
      <p>I'll search across all your processed documents and answer with citations.</p>
    </div>`;
}

function appendMessage(role, text, citations = []) {
  const el = $('chat-messages');
  // Remove empty state
  const empty = el.querySelector('.empty-state');
  if (empty) empty.remove();

  const avatar = role === 'user' ? '👤' : '🤖';
  const citHtml = citations && citations.length > 0 ? `
    <div class="citations">
      <div class="citations-label">Sources</div>
      ${citations.map(c => `
        <span class="citation-chip" title="${escapeHtml(c.text_snippet || '')}">
          📄 Page ${c.page_number || '?'} · ${c.document_id?.slice(0, 6)}…
        </span>`).join('')}
    </div>` : '';

  const msgHtml = `
    <div class="msg ${role}">
      <div class="msg-avatar">${avatar}</div>
      <div class="msg-bubble">
        <div class="msg-text">${escapeHtml(text).replace(/\n/g, '<br>')}</div>
        ${citHtml}
      </div>
    </div>`;

  el.insertAdjacentHTML('beforeend', msgHtml);
  el.scrollTop = el.scrollHeight;
}

function appendThinking() {
  const el = $('chat-messages');
  const div = document.createElement('div');
  div.className = 'msg ai';
  div.id = 'thinking-msg';
  div.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-bubble" style="display:flex;align-items:center;gap:.5rem;color:var(--text-muted)">
      <div class="spinner dark"></div> Thinking…
    </div>`;
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
}

async function sendMessage() {
  const textarea = $('chat-input');
  const question = textarea.value.trim();
  if (!question) return;

  textarea.value = '';
  textarea.style.height = '';

  appendMessage('user', question);
  appendThinking();

  const docFilter = $('doc-filter').value.trim();

  const sendBtn = $('send-btn');
  sendBtn.disabled = true;

  try {
    const body = {
      question,
      top_k: 5,
      conversation_id: state.currentConversationId || null,
    };
    if (docFilter) body.document_ids = [docFilter];

    const data = await apiFetch('/query/ask', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    // Remove thinking
    const thinking = $('thinking-msg');
    if (thinking) thinking.remove();

    state.currentConversationId = data.conversation_id;
    appendMessage('ai', data.answer, data.citations || []);

    // Refresh conversation list
    loadConversationList();
  } catch (e) {
    const thinking = $('thinking-msg');
    if (thinking) thinking.remove();
    appendMessage('ai', `Sorry, I encountered an error: ${e.message}`);
    toast(e.message, 'error');
  } finally {
    sendBtn.disabled = false;
  }
}

// ─── Health ───────────────────────────────────────────────────────────────────
async function loadHealth() {
  const el = $('health-grid');
  el.innerHTML = `<div class="empty-state"><div class="spinner dark" style="margin:0 auto"></div></div>`;
  try {
    const data = await apiFetch('/health');
    state.health = data;
    const services = [
      { key: 'postgres', label: 'PostgreSQL', icon: '🗄️' },
      { key: 'qdrant', label: 'Qdrant (Vector DB)', icon: '⚡' },
      { key: 'redis', label: 'Redis (Cache)', icon: '🔴' },
      { key: 'minio', label: 'MinIO (Storage)', icon: '📦' },
      { key: 'neo4j', label: 'Neo4j (Graph DB)', icon: '🕸️' },
      { key: 'elasticsearch', label: 'Elasticsearch', icon: '🔍' },
      { key: 'llm', label: 'LLM Provider', icon: '🤖' },
    ];
    el.innerHTML = services.map(s => {
      const val = data.services ? data.services[s.key] : data[s.key];
      const str = String(val || '');
      const up = str === 'true' || str.includes('healthy') || str.startsWith('available');
      const dot = val === undefined ? 'unknown' : (up ? 'up' : 'down');
      const label = val === undefined ? 'Not checked' : (up ? str.replace('healthy', 'Healthy') : `⚠ ${str.slice(0, 40)}`); 
      return `
        <div class="health-item">
          <div style="font-size:1.25rem">${s.icon}</div>
          <div>
            <div class="health-name">${s.label}</div>
            <div class="health-state" style="display:flex;align-items:center;gap:.375rem">
              <div class="health-dot ${dot}"></div>${label}
            </div>
          </div>
        </div>`;
    }).join('');

    // Show overall status
    const svcData = data.services || {};
    const upCount = services.filter(s => {
      const v = String(svcData[s.key] || '');
      return v.includes('healthy') || v.startsWith('available');
    }).length;
    const total = services.filter(s => svcData[s.key] !== undefined).length;
    $('health-summary').textContent = `${upCount}/${total || services.length} services healthy`;
  } catch (e) {
    el.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><h3>Health check failed</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}

// ─── Bootstrap ────────────────────────────────────────────────────────────────
function init() {
  // Auth tabs
  $qa('.auth-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      $qa('.auth-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      $('login-form').style.display = tab.dataset.tab === 'login' ? 'block' : 'none';
      $('register-form').style.display = tab.dataset.tab === 'register' ? 'block' : 'none';
    });
  });

  // Login form
  $('login-form').addEventListener('submit', e => {
    e.preventDefault();
    handleLogin($('login-email').value, $('login-password').value);
  });

  // Register form
  $('register-form').addEventListener('submit', e => {
    e.preventDefault();
    handleRegister($('reg-name').value, $('reg-email').value, $('reg-password').value);
  });

  // Nav items
  $qa('.nav-item[data-page]').forEach(item => {
    item.addEventListener('click', () => navigateTo(item.dataset.page));
  });

  // Logout
  $('logout-btn').addEventListener('click', logout);

  // Upload
  setupUpload();

  // Search
  $('search-btn').addEventListener('click', runSearch);
  $('search-query').addEventListener('keydown', e => {
    if (e.key === 'Enter') runSearch();
  });

  // Chat
  $('send-btn').addEventListener('click', sendMessage);
  $('chat-input').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  $('chat-input').addEventListener('input', function() {
    this.style.height = '';
    this.style.height = Math.min(this.scrollHeight, 112) + 'px';
  });

  $('new-conv-btn').addEventListener('click', newConversation);
  $('health-refresh').addEventListener('click', loadHealth);

  // Start with auth or app
  if (state.token && state.user) {
    showApp();
  } else {
    showAuthScreen();
  }
}

document.addEventListener('DOMContentLoaded', init);
