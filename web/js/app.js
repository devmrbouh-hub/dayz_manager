// API URL
const API_URL = window.location.origin;

// WebSocket
let ws = null;
const serverLogSockets = {};
const serverLogOpen = new Set();
const serverLogStickBottom = {};
const serverChatSockets = {};
const serverChatOpen = new Set();
const serverChatStickBottom = {};
const serverChatPollTimers = {};
const serverChatLastTs = {};
const serverChatSeen = {};
const lastServerSnapshot = {};
let startupPollTimer = null;
let serverSyncTimer = null;

// ============================================================
// Toast notifications (non-blocking, no browser alert/confirm)
// ============================================================

function showToast(message, type = 'info', ms = 5000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-visible'));
    setTimeout(() => {
        toast.classList.remove('toast-visible');
        setTimeout(() => toast.remove(), 300);
    }, ms);
}

async function parseApiError(response) {
    try {
        const data = await response.json();
        if (typeof data.detail === 'string') {
            return data.detail;
        }
        if (Array.isArray(data.detail)) {
            return data.detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
        }
        if (data.detail) {
            return String(data.detail);
        }
        return response.statusText || `HTTP ${response.status}`;
    } catch (_) {
        return response.statusText || `HTTP ${response.status}`;
    }
}

// ============================================================
// Initialization
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    // Загрузить API-ключ из localStorage в поле ввода
    const savedKey = localStorage.getItem('dayz_api_key');
    if (savedKey) {
        document.getElementById('api-key-input').value = savedKey;
    }

    // Сохранять API-ключ при изменении
    document.getElementById('api-key-input').addEventListener('change', (e) => {
        localStorage.setItem('dayz_api_key', e.target.value);
    });

    refreshServers();
    connectWebSocket();
    loadLogs();
    serverSyncTimer = setInterval(() => syncServers(), 5000);
});

// ============================================================
// Servers
// ============================================================

function getServerCardEl(serverId) {
    return document.getElementById(`server-card-${serverId}`);
}

function ensureAddServerButton(container) {
    let btn = container.querySelector('.add-server-btn');
    if (!btn) {
        btn = document.createElement('button');
        btn.className = 'add-server-btn';
        btn.innerHTML = '+ Add Server';
        btn.onclick = openAddServerModal;
        container.appendChild(btn);
    }
    return btn;
}

function removeServerCard(serverId) {
    disconnectServerLog(serverId);
    disconnectServerChat(serverId);
    stopChatPoll(serverId);
    serverLogOpen.delete(serverId);
    serverChatOpen.delete(serverId);
    delete lastServerSnapshot[serverId];
    delete serverChatSeen[serverId];
    delete serverChatLastTs[serverId];
    const card = getServerCardEl(serverId);
    if (card) {
        card.remove();
    }
}

function formatPlayersCount(server) {
    const max = server.max_players;
    const maxStr = max != null ? max : '?';
    if (!server.running) {
        return `0/${maxStr}`;
    }
    if (server.rcon_players_ok === false && server.player_count === 0) {
        return `?/${maxStr}`;
    }
    return `${server.player_count ?? 0}/${maxStr}`;
}

function formatServerFps(server) {
    if (!server.running || server.server_fps == null) {
        return '—';
    }
    return String(server.server_fps);
}

function updateServerLiveStats(server) {
    const card = getServerCardEl(server.id);
    if (!card) return;

    const fpsEl = card.querySelector(`#server-fps-${server.id}`);
    if (fpsEl) {
        fpsEl.textContent = formatServerFps(server);
    }

    const playersEl = card.querySelector(`#server-players-count-${server.id}`);
    if (playersEl) {
        playersEl.textContent = formatPlayersCount(server);
    }

    const listEl = document.getElementById(`server-players-list-${server.id}`);
    if (listEl) {
        const players = server.players || [];
        if (!server.running || players.length === 0) {
            listEl.textContent = server.running ? 'Никого онлайн' : 'Сервер остановлен';
        } else {
            listEl.innerHTML = '';
            players.forEach((p) => {
                const li = document.createElement('li');
                li.textContent = p.name || `Player ${p.id}`;
                listEl.appendChild(li);
            });
        }
    }
}

function updateServerCard(server) {
    const card = getServerCardEl(server.id);
    if (!card) {
        return;
    }
    lastServerSnapshot[server.id] = { ...server };

    const status = getServerStatusDisplay(server);
    const indicator = card.querySelector('.status-indicator');
    if (indicator) {
        indicator.className = `status-indicator ${status.className}`;
        const spans = indicator.querySelectorAll('span');
        if (spans.length >= 2) {
            spans[1].textContent = status.text;
        }
    }

    const statusWrap = card.querySelector('.server-status');
    if (statusWrap) {
        let pidBadge = statusWrap.querySelector('.pid-badge');
        if (server.pid) {
            if (!pidBadge) {
                pidBadge = document.createElement('span');
                pidBadge.className = 'pid-badge';
                statusWrap.appendChild(pidBadge);
            }
            pidBadge.textContent = `PID: ${server.pid}`;
        } else if (pidBadge) {
            pidBadge.remove();
        }

        let rptBadge = statusWrap.querySelector('.rpt-badge');
        if (server.current_rpt) {
            if (!rptBadge) {
                rptBadge = document.createElement('span');
                rptBadge.className = 'rpt-badge';
                statusWrap.appendChild(rptBadge);
            }
            rptBadge.textContent = server.current_rpt;
        } else if (rptBadge) {
            rptBadge.remove();
        }
    }

    const info = card.querySelector('.server-info');
    if (info) {
        let warningEl = info.querySelector('.startup-warning');
        if (status.warning) {
            if (!warningEl) {
                warningEl = document.createElement('p');
                warningEl.className = 'startup-warning';
                info.appendChild(warningEl);
            }
            warningEl.textContent = status.warning;
        } else if (warningEl) {
            warningEl.remove();
        }
    }

    const startBtn = card.querySelector('.server-buttons .btn-success');
    const stopBtn = card.querySelector('.server-buttons .btn-danger');
    if (startBtn) {
        startBtn.disabled = !!server.running;
    }
    if (stopBtn) {
        stopBtn.disabled = !server.running;
    }

    const nextEl = document.getElementById(`next-restart-${server.id}`);
    if (nextEl) {
        nextEl.textContent = `Next: ${formatNextRestart(server.next_restart_at)}`;
    }

    const autoCb = card.querySelector('.restart-toggles .restart-toggle-row input[type="checkbox"]');
    if (autoCb) {
        autoCb.checked = !!server.auto_restart;
    }

    updateServerLiveStats(server);
}

function applyServerStatusFromWs(serverId, msg) {
    const prev = lastServerSnapshot[serverId] || { id: serverId, running: false };
    const phase = msg.phase || 'stopped';
    const merged = {
        ...prev,
        id: serverId,
        running: phase !== 'stopped',
        startup_phase: phase,
        startup_warning: msg.warning || null,
        current_rpt: msg.rpt != null ? msg.rpt : prev.current_rpt
    };
    updateServerCard(merged);
}

async function fetchServerAndUpdate(serverId) {
    const response = await fetch(`${API_URL}/api/servers/${serverId}`);
    if (!response.ok) {
        return;
    }
    const data = await response.json();
    if (!data.server) {
        return;
    }
    let card = getServerCardEl(serverId);
    if (!card) {
        await syncServers();
    } else {
        updateServerCard(data.server);
    }
}

async function syncServers() {
    try {
        const response = await fetch(`${API_URL}/api/servers`);
        const data = await response.json();

        const container = document.getElementById('servers-container');
        const addBtn = ensureAddServerButton(container);

        const emptyMsg = container.querySelector('.servers-empty-msg');

        if (!data.servers || data.servers.length === 0) {
            container.querySelectorAll('.server-card').forEach((card) => {
                removeServerCard(card.dataset.serverId);
            });
            if (!emptyMsg) {
                const p = document.createElement('p');
                p.className = 'servers-empty-msg';
                p.style.textAlign = 'center';
                p.style.color = 'var(--text-secondary)';
                p.textContent = 'No servers configured';
                container.insertBefore(p, addBtn);
            }
            updateConnectionStatus(true);
            return;
        }

        if (emptyMsg) {
            emptyMsg.remove();
        }

        const apiIds = new Set(data.servers.map((s) => s.id));
        container.querySelectorAll('.server-card').forEach((card) => {
            if (!apiIds.has(card.dataset.serverId)) {
                removeServerCard(card.dataset.serverId);
            }
        });

        data.servers.forEach((server) => {
            let card = getServerCardEl(server.id);
            if (!card) {
                card = createServerCard(server);
                container.insertBefore(card, addBtn);
                if (serverLogOpen.has(server.id)) {
                    const details = document.getElementById(`server-log-details-${server.id}`);
                    if (details) {
                        details.open = true;
                        const sock = serverLogSockets[server.id];
                        if (!sock || sock.readyState !== WebSocket.OPEN) {
                            connectServerLog(server.id);
                        }
                    }
                }
                if (serverChatOpen.has(server.id)) {
                    const chatDetails = document.getElementById(`server-chat-details-${server.id}`);
                    if (chatDetails) {
                        chatDetails.open = true;
                        const chatSock = serverChatSockets[server.id];
                        if (!chatSock || chatSock.readyState !== WebSocket.OPEN) {
                            loadServerChatHistory(server.id).then(() => {
                                connectServerChat(server.id);
                                startChatPoll(server.id);
                            });
                        } else {
                            startChatPoll(server.id);
                        }
                    }
                }
            } else {
                updateServerCard(server);
            }
        });

        updateConnectionStatus(true);
    } catch (error) {
        console.error('Failed to load servers:', error);
        updateConnectionStatus(false);
    }
}

async function refreshServers() {
    return syncServers();
}

function createServerCard(server) {
    const card = document.createElement('div');
    card.className = 'server-card';
    card.id = `server-card-${server.id}`;
    card.dataset.serverId = server.id;
    lastServerSnapshot[server.id] = { ...server };

    const status = getServerStatusDisplay(server);

    card.innerHTML = `
        <div class="server-card-top">
            <div class="server-info">
                <h3>${server.name}</h3>
                <span class="port">:${server.port}</span>

                <div class="server-status">
                    <div class="status-indicator ${status.className}">
                        <span class="dot"></span>
                        <span>${status.text}</span>
                    </div>
                    ${server.pid ? `<span class="pid-badge">PID: ${server.pid}</span>` : ''}
                    ${server.current_rpt ? `<span class="rpt-badge">${server.current_rpt}</span>` : ''}
                </div>
                ${status.warning ? `<p class="startup-warning">${status.warning}</p>` : ''}
                <div class="server-live-stats">
                    <span class="live-stat">FPS: <strong id="server-fps-${server.id}">${formatServerFps(server)}</strong></span>
                    <span class="live-stat">Игроки: <strong id="server-players-count-${server.id}">${formatPlayersCount(server)}</strong></span>
                </div>
                <details class="server-players-details" id="server-players-details-${server.id}">
                    <summary>Игроки онлайн</summary>
                    <ul class="server-players-list" id="server-players-list-${server.id}"></ul>
                </details>
            </div>

            <div class="server-actions">
                <div class="server-buttons">
                    <button class="btn btn-success btn-small" onclick="startServer('${server.id}')" ${server.running ? 'disabled' : ''}>▶ Start</button>
                    <button class="btn btn-danger btn-small" onclick="stopServer('${server.id}')" ${!server.running ? 'disabled' : ''}>⏹ Stop</button>
                    <button class="btn btn-warning btn-small" onclick="restartServer('${server.id}')">🔄 Restart</button>
                </div>
                <button class="btn btn-secondary btn-small" onclick="removeServer('${server.id}')">🗑️ Remove</button>
            </div>
        </div>

        <div class="server-restart-panel">
            <div class="server-restart-header">
                <h4>Restart</h4>
                <span class="next-restart" id="next-restart-${server.id}">
                    Next: ${formatNextRestart(server.next_restart_at)}
                </span>
            </div>

            <div class="restart-toggles">
                <div class="restart-toggle-row">
                    <label class="toggle-switch">
                        <input type="checkbox" ${server.auto_restart ? 'checked' : ''} onchange="toggleAutoRestart('${server.id}')">
                        <span class="toggle-slider"></span>
                    </label>
                    <span class="toggle-label">Auto restart</span>
                    <span class="toggle-hint">Поднять сервер, если процесс упал</span>
                </div>
            </div>

            ${buildPlannedRestartHtml(server)}
        </div>

        <details class="server-log-details" id="server-log-details-${server.id}" ontoggle="onServerLogToggle('${server.id}')">
            <summary>Server log (RPT)</summary>
            <div class="server-log-toolbar">
                <label class="server-log-filter">
                    <input type="checkbox" id="hide-weapon-${server.id}" checked onchange="onServerLogFilterChange('${server.id}')">
                    Скрыть WEAPON
                </label>
                <span class="server-log-hint">READY: [IdleMode] Entering IN - save processed</span>
            </div>
            <pre class="server-log-view" id="server-log-${server.id}"></pre>
        </details>

        <details class="server-chat-details" id="server-chat-details-${server.id}" ontoggle="onServerChatToggle('${server.id}')">
            <summary>Игровой чат</summary>
            <div class="server-chat-view" id="server-chat-${server.id}"></div>
            <div class="server-chat-compose">
                <input type="text" class="server-chat-input" id="server-chat-input-${server.id}" maxlength="235" placeholder="Сообщение всем игрокам…" onkeydown="if(event.key==='Enter')sendServerChat('${server.id}')">
                <button type="button" class="btn btn-primary btn-small" onclick="sendServerChat('${server.id}')">Отправить</button>
            </div>
        </details>
    `;

    updateServerLiveStats(server);
    return card;
}

function shouldHideWeaponLineForServer(serverId, line) {
    const cb = document.getElementById(`hide-weapon-${serverId}`);
    return shouldHideWeaponLine(cb ? cb.checked : true, line);
}

function appendServerLogLine(serverId, line, highlight) {
    if (shouldHideWeaponLineForServer(serverId, line)) {
        return;
    }
    const pre = document.getElementById(`server-log-${serverId}`);
    if (!pre) return;

    const row = document.createElement('div');
    row.className = highlight ? 'server-log-line highlight' : 'server-log-line';
    row.textContent = line;
    pre.appendChild(row);

    while (pre.children.length > MAX_SERVER_LOG_LINES) {
        pre.removeChild(pre.firstChild);
    }

    if (serverLogStickBottom[serverId] !== false) {
        pre.scrollTop = pre.scrollHeight;
    }
}

function clearServerLogView(serverId) {
    const pre = document.getElementById(`server-log-${serverId}`);
    if (pre) {
        pre.innerHTML = '';
    }
}

function disconnectServerLog(serverId) {
    const sock = serverLogSockets[serverId];
    if (sock) {
        try {
            sock.close();
        } catch (e) {
            /* ignore */
        }
        delete serverLogSockets[serverId];
    }
}

async function loadServerLogTail(serverId) {
    try {
        const response = await fetch(`${API_URL}/api/servers/${serverId}/logs/tail?lines=200`);
        if (!response.ok) return;
        const data = await response.json();
        clearServerLogView(serverId);
        (data.lines || []).forEach(line => appendServerLogLine(serverId, line, false));
    } catch (e) {
        console.error('Failed to load server log tail', e);
    }
}

function connectServerLog(serverId) {
    const existing = serverLogSockets[serverId];
    if (existing && existing.readyState === WebSocket.OPEN) {
        return;
    }
    disconnectServerLog(serverId);
    serverLogStickBottom[serverId] = true;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/servers/${serverId}/logs`;
    const sock = new WebSocket(wsUrl);
    serverLogSockets[serverId] = sock;

    let batch = [];
    let batchTimer = null;

    const flushBatch = () => {
        batch.forEach((item) => appendServerLogLine(serverId, item.m, item.h));
        batch = [];
        batchTimer = null;
    };

    sock.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.t === 'l') {
                batch.push({ m: msg.m, h: !!msg.h });
                if (!batchTimer) {
                    batchTimer = setTimeout(flushBatch, 50);
                }
            } else if (msg.t === 'r') {
                flushBatch();
                applyServerStatusFromWs(serverId, {
                    phase: 'ready',
                    warning: null,
                    rpt: msg.rpt || (lastServerSnapshot[serverId] && lastServerSnapshot[serverId].current_rpt)
                });
            } else if (msg.t === 's') {
                flushBatch();
                applyServerStatusFromWs(serverId, msg);
            }
        } catch (e) {
            appendServerLogLine(serverId, event.data, false);
        }
    };

    sock.onclose = () => {
        if (serverLogSockets[serverId] === sock) {
            delete serverLogSockets[serverId];
        }
        if (serverLogOpen.has(serverId)) {
            setTimeout(() => {
                if (serverLogOpen.has(serverId)) {
                    const details = document.getElementById(`server-log-details-${serverId}`);
                    if (details && details.open) {
                        connectServerLog(serverId);
                    }
                }
            }, 2000);
        }
    };
}

function onServerLogToggle(serverId) {
    const details = document.getElementById(`server-log-details-${serverId}`);
    if (!details) return;
    if (details.open) {
        serverLogOpen.add(serverId);
        const sock = serverLogSockets[serverId];
        if (!sock || sock.readyState !== WebSocket.OPEN) {
            clearServerLogView(serverId);
            connectServerLog(serverId);
        }
    } else {
        serverLogOpen.delete(serverId);
        disconnectServerLog(serverId);
    }
}

function applyWeaponFilterVisibility(serverId) {
    const cb = document.getElementById(`hide-weapon-${serverId}`);
    const hideChecked = cb ? cb.checked : true;
    const pre = document.getElementById(`server-log-${serverId}`);
    if (!pre) return;
    pre.querySelectorAll('.server-log-line').forEach((row) => {
        const line = row.textContent || '';
        row.style.display = shouldHideWeaponLine(hideChecked, line) ? 'none' : '';
    });
}

function onServerLogFilterChange(serverId) {
    applyWeaponFilterVisibility(serverId);
}

const MAX_SERVER_CHAT_LINES = 500;

function formatChatTime(isoTs) {
    if (!isoTs) return '';
    const date = new Date(isoTs);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function chatMessageKey(msg) {
    return `${msg.ts || ''}|${msg.player || ''}|${msg.text || ''}`;
}

function appendServerChatLine(serverId, msg) {
    const view = document.getElementById(`server-chat-${serverId}`);
    if (!view) return;

    const key = chatMessageKey(msg);
    if (!serverChatSeen[serverId]) {
        serverChatSeen[serverId] = new Set();
    }
    if (serverChatSeen[serverId].has(key)) {
        return;
    }
    serverChatSeen[serverId].add(key);
    if (msg.ts) {
        const msgTime = new Date(msg.ts).getTime();
        const now = Date.now();
        if (!Number.isNaN(msgTime) && msgTime <= now + 60_000) {
            if (!serverChatLastTs[serverId] || msg.ts > serverChatLastTs[serverId]) {
                serverChatLastTs[serverId] = msg.ts;
            }
        }
    }

    const row = document.createElement('div');
    row.className = 'server-chat-line';
    const channel = msg.channel || 'Chat';
    const shortChannel = channel.replace(/^Global$/i, 'Global').replace(/^Chat\s*-\s*/i, '');
    row.textContent = `[${formatChatTime(msg.ts)}] [${shortChannel}] ${msg.player}: ${msg.text}`;
    view.appendChild(row);

    while (view.children.length > MAX_SERVER_CHAT_LINES) {
        view.removeChild(view.firstChild);
    }

    if (serverChatStickBottom[serverId] !== false) {
        view.scrollTop = view.scrollHeight;
    }
}

function clearServerChatView(serverId) {
    const view = document.getElementById(`server-chat-${serverId}`);
    if (view) {
        view.innerHTML = '';
    }
    serverChatSeen[serverId] = new Set();
    delete serverChatLastTs[serverId];
}

function stopChatPoll(serverId) {
    const timer = serverChatPollTimers[serverId];
    if (timer) {
        clearInterval(timer);
        delete serverChatPollTimers[serverId];
    }
}

function startChatPoll(serverId) {
    stopChatPoll(serverId);
    serverChatPollTimers[serverId] = setInterval(() => pollServerChat(serverId), 5000);
}

async function pollServerChat(serverId) {
    if (!serverChatOpen.has(serverId)) {
        return;
    }
    try {
        const since = serverChatLastTs[serverId];
        const url = since
            ? `${API_URL}/api/servers/${serverId}/chat?limit=100&since=${encodeURIComponent(since)}`
            : `${API_URL}/api/servers/${serverId}/chat?limit=100`;
        const response = await fetch(url);
        if (!response.ok) return;
        const data = await response.json();
        (data.messages || []).forEach((msg) => appendServerChatLine(serverId, msg));
    } catch (e) {
        console.error('Chat poll failed', e);
    }
}

function disconnectServerChat(serverId) {
    const sock = serverChatSockets[serverId];
    if (sock) {
        try {
            sock.close();
        } catch (e) {
            /* ignore */
        }
        delete serverChatSockets[serverId];
    }
}

async function loadServerChatHistory(serverId) {
    try {
        const response = await fetch(`${API_URL}/api/servers/${serverId}/chat?limit=200`);
        if (!response.ok) return;
        const data = await response.json();
        clearServerChatView(serverId);
        (data.messages || []).forEach((msg) => appendServerChatLine(serverId, msg));
    } catch (e) {
        console.error('Failed to load chat history', e);
    }
}

function connectServerChat(serverId) {
    const existing = serverChatSockets[serverId];
    if (existing && existing.readyState === WebSocket.OPEN) {
        return;
    }
    disconnectServerChat(serverId);
    serverChatStickBottom[serverId] = true;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/servers/${serverId}/chat`;
    const sock = new WebSocket(wsUrl);
    serverChatSockets[serverId] = sock;

    sock.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.t === 'c') {
                appendServerChatLine(serverId, msg);
            }
        } catch (e) {
            appendServerChatLine(serverId, { ts: '', channel: '', player: '', text: event.data });
        }
    };

    sock.onclose = () => {
        if (serverChatSockets[serverId] === sock) {
            delete serverChatSockets[serverId];
        }
        if (serverChatOpen.has(serverId)) {
            setTimeout(() => {
                if (serverChatOpen.has(serverId)) {
                    const details = document.getElementById(`server-chat-details-${serverId}`);
                    if (details && details.open) {
                        connectServerChat(serverId);
                    }
                }
            }, 2000);
        }
    };
}

function onServerChatToggle(serverId) {
    const details = document.getElementById(`server-chat-details-${serverId}`);
    if (!details) return;
    if (details.open) {
        serverChatOpen.add(serverId);
        const sock = serverChatSockets[serverId];
        if (!sock || sock.readyState !== WebSocket.OPEN) {
            clearServerChatView(serverId);
            loadServerChatHistory(serverId).then(() => {
                connectServerChat(serverId);
                startChatPoll(serverId);
            });
        } else {
            startChatPoll(serverId);
        }
    } else {
        serverChatOpen.delete(serverId);
        stopChatPoll(serverId);
        disconnectServerChat(serverId);
    }
}

async function sendServerChat(serverId) {
    const input = document.getElementById(`server-chat-input-${serverId}`);
    if (!input) return;
    const message = input.value.trim();
    if (!message) return;

    try {
        const response = await fetch(`${API_URL}/api/servers/${serverId}/chat/say`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': getApiKey()
            },
            body: JSON.stringify({ message })
        });
        if (!response.ok) {
            showToast(`Не удалось отправить: ${await parseApiError(response)}`, 'error');
            return;
        }
        const data = await response.json();
        input.value = '';
        const chatMsg = data.chat || {
            ts: new Date().toISOString(),
            channel: 'Global',
            player: 'Admin',
            text: message
        };
        appendServerChatLine(serverId, chatMsg);
        showToast('Сообщение отправлено в игру', 'success', 3000);
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

function pollServerUntilReady(serverId, maxAttempts = 40) {
    if (startupPollTimer) {
        clearInterval(startupPollTimer);
    }
    let attempts = 0;
    startupPollTimer = setInterval(async () => {
        attempts += 1;
        try {
            const response = await fetch(`${API_URL}/api/servers/${serverId}`);
            const data = await response.json();
            const server = data.server;
            if (server) {
                updateServerCard(server);
            }
            if (server && (server.startup_phase === 'ready' || !server.running)) {
                clearInterval(startupPollTimer);
                startupPollTimer = null;
                return;
            }
            if (attempts >= maxAttempts) {
                clearInterval(startupPollTimer);
                startupPollTimer = null;
            }
        } catch (e) {
            console.error('Startup poll failed', e);
        }
    }, 3000);
}

async function startServer(serverId) {
    try {
        const response = await fetch(`${API_URL}/api/servers/${serverId}/start`, {
            method: 'POST',
            headers: {
                'X-API-Key': getApiKey()
            }
        });

        if (!response.ok) {
            showToast(`Не удалось запустить: ${await parseApiError(response)}`, 'error');
            return;
        }

        clearServerLogView(serverId);
        serverLogOpen.add(serverId);
        await fetchServerAndUpdate(serverId);
        const details = document.getElementById(`server-log-details-${serverId}`);
        if (details) {
            details.open = true;
            connectServerLog(serverId);
        }
        pollServerUntilReady(serverId);
        showToast('Сервер запускается…', 'success', 3000);
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

async function stopServer(serverId) {
    try {
        const response = await fetch(`${API_URL}/api/servers/${serverId}/stop`, {
            method: 'POST',
            headers: {
                'X-API-Key': getApiKey()
            }
        });

        if (!response.ok) {
            showToast(`Не удалось остановить: ${await parseApiError(response)}`, 'error');
            return;
        }

        serverLogOpen.delete(serverId);
        disconnectServerLog(serverId);
        await fetchServerAndUpdate(serverId);
        showToast('Сервер остановлен', 'success', 3000);
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

async function restartServer(serverId) {
    try {
        const response = await fetch(`${API_URL}/api/servers/${serverId}/restart`, {
            method: 'POST',
            headers: {
                'X-API-Key': getApiKey()
            }
        });

        if (!response.ok) {
            showToast(`Не удалось перезапустить: ${await parseApiError(response)}`, 'error');
            return;
        }

        clearServerLogView(serverId);
        serverLogOpen.add(serverId);
        await fetchServerAndUpdate(serverId);
        const details = document.getElementById(`server-log-details-${serverId}`);
        if (details) {
            details.open = true;
            connectServerLog(serverId);
        }
        pollServerUntilReady(serverId);
        showToast('Сервер перезапускается…', 'success', 3000);
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

async function toggleAutoRestart(serverId) {
    // Получить текущий статус сервера (нужно знать текущее auto_restart значение)
    try {
        const response = await fetch(`${API_URL}/api/servers/${serverId}`);
        const data = await response.json();
        const currentAutoRestart = data.server.auto_restart;

        // Обновить через PUT
        const updateResponse = await fetch(`${API_URL}/api/servers/${serverId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': getApiKey()
            },
            body: JSON.stringify({
                auto_restart: !currentAutoRestart
            })
        });

        if (!updateResponse.ok) {
            showToast(`Не удалось изменить auto restart: ${await parseApiError(updateResponse)}`, 'error');
            return;
        }

        await fetchServerAndUpdate(serverId);
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

async function removeServer(serverId) {
    try {
        const response = await fetch(`${API_URL}/api/servers/${serverId}`, {
            method: 'DELETE',
            headers: {
                'X-API-Key': getApiKey()
            }
        });

        if (!response.ok) {
            showToast(`Не удалось удалить сервер: ${await parseApiError(response)}`, 'error');
            return;
        }

        removeServerCard(serverId);
        await syncServers();
        showToast(`Сервер «${serverId}» удалён из конфига`, 'success', 3000);
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// ============================================================
// Add Server Modal
// ============================================================

function openAddServerModal() {
    document.getElementById('add-server-modal').classList.add('active');
}

function closeAddServerModal() {
    document.getElementById('add-server-modal').classList.remove('active');
    document.getElementById('add-server-form').reset();
}

async function addServer(event) {
    event.preventDefault();

    const server = {
        id: document.getElementById('server-id').value,
        name: document.getElementById('server-name').value,
        path: document.getElementById('server-path').value,
        exe: 'DayZServer_x64.exe',
        port: parseInt(document.getElementById('server-port').value),
        query_port: parseInt(document.getElementById('server-port').value) + 1,
        rcon_port: parseInt(document.getElementById('rcon-port').value),
        rcon_password: document.getElementById('rcon-password').value,
        config_file: 'Instance_1\\serverDZ.cfg',
        profiles: 'Instance_1',
        mods_file: 'mod_list.txt',
        keys_dir: 'keys',
        mods: [],
        server_mods: '',
        launch_args: ['-noupdate'],
        auto_restart: false,
        planned_restart: {
            enabled: false,
            interval_minutes: 240,
            test_mode: false
        },
        hooks: {
            beforeStart: [],
            afterStop: []
        }
    };

    try {
        const response = await fetch(`${API_URL}/api/servers`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': getApiKey()
            },
            body: JSON.stringify(server)
        });

        if (!response.ok) {
            showToast(`Не удалось добавить сервер: ${await parseApiError(response)}`, 'error');
            return;
        }

        closeAddServerModal();
        await syncServers();
        showToast('Сервер добавлен', 'success', 3000);
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// ============================================================
// Planned restart (on server card)
// ============================================================

const INTERVAL_PRESETS = {
    '2': 120,
    '3': 180,
    '4': 240,
    '6': 360,
    'custom': null,
    'test': null
};

function formatNextRestart(isoString) {
    if (!isoString) return 'Disabled';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: '2-digit'
    });
}

function buildPlannedRestartHtml(server) {
    const planned = server.planned_restart || {
        enabled: false,
        interval_minutes: 240,
        test_mode: false
    };
    const serverId = server.id;
    const preset = detectIntervalPreset(planned);
    const customHours = planned.test_mode ? '' : (planned.interval_minutes / 60);
    const testMinutes = planned.test_mode ? planned.interval_minutes : 15;

    return `
        <div class="planned-restart-block">
            <div class="restart-toggle-row">
                <label class="toggle-switch">
                    <input type="checkbox" id="pr-enabled-${serverId}" ${planned.enabled ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
                <span class="toggle-label">Planned restart</span>
                <span class="toggle-hint">Рестарт по расписанию от 00:00</span>
            </div>
        <div class="restart-form-grid">
            <div class="restart-field" id="pr-preset-field-${serverId}">
                <label for="pr-preset-${serverId}">Interval</label>
                <select id="pr-preset-${serverId}" onchange="onRestartPresetChange('${serverId}')">
                    <option value="2" ${preset === '2' ? 'selected' : ''}>Every 2 hours</option>
                    <option value="3" ${preset === '3' ? 'selected' : ''}>Every 3 hours</option>
                    <option value="4" ${preset === '4' ? 'selected' : ''}>Every 4 hours</option>
                    <option value="6" ${preset === '6' ? 'selected' : ''}>Every 6 hours</option>
                    <option value="custom" ${preset === 'custom' ? 'selected' : ''}>Custom (hours)</option>
                    <option value="test" ${preset === 'test' ? 'selected' : ''}>Test mode (minutes)</option>
                </select>
            </div>
            <div class="restart-field" id="pr-hours-field-${serverId}" style="display:${preset === 'custom' && !planned.test_mode ? 'block' : 'none'}">
                <label for="pr-hours-${serverId}">Custom hours</label>
                <input type="number" id="pr-hours-${serverId}" min="1" max="24" step="1" value="${customHours || 4}">
            </div>
            <div class="restart-field" id="pr-minutes-field-${serverId}" style="display:${preset === 'test' || planned.test_mode ? 'block' : 'none'}">
                <label for="pr-minutes-${serverId}">Test interval (minutes)</label>
                <input type="number" id="pr-minutes-${serverId}" min="10" max="59" step="1" value="${testMinutes}">
            </div>
        </div>

        <p class="restart-hint">
            Warnings at T-30, T-15, T-10 min. At T-5: say, pause 5 s, lock and kick. Requires RCON.
        </p>
        <div class="restart-actions">
            <button class="btn btn-primary btn-small" onclick="savePlannedRestart('${serverId}')">Save planned restart</button>
        </div>
        </div>
    `;
}

function detectIntervalPreset(planned) {
    if (planned.test_mode) return 'test';
    const minutes = planned.interval_minutes || 240;
    for (const [key, value] of Object.entries(INTERVAL_PRESETS)) {
        if (value === minutes) return key;
    }
    return 'custom';
}

function onRestartPresetChange(serverId) {
    const preset = document.getElementById(`pr-preset-${serverId}`).value;
    const hoursField = document.getElementById(`pr-hours-field-${serverId}`);
    const minutesField = document.getElementById(`pr-minutes-field-${serverId}`);

    if (hoursField) {
        hoursField.style.display = preset === 'custom' ? 'block' : 'none';
    }
    if (minutesField) {
        minutesField.style.display = preset === 'test' ? 'block' : 'none';
    }
}

function buildPlannedRestartPayload(serverId) {
    const enabled = document.getElementById(`pr-enabled-${serverId}`).checked;
    const preset = document.getElementById(`pr-preset-${serverId}`).value;

    let interval_minutes = 240;
    let test_mode = false;

    if (preset === 'test') {
        test_mode = true;
        interval_minutes = parseInt(document.getElementById(`pr-minutes-${serverId}`).value, 10) || 15;
    } else if (preset === 'custom') {
        const hours = parseFloat(document.getElementById(`pr-hours-${serverId}`).value) || 4;
        interval_minutes = Math.round(hours * 60);
    } else {
        interval_minutes = INTERVAL_PRESETS[preset] || 240;
    }

    return {
        planned_restart: {
            enabled,
            interval_minutes,
            test_mode
        }
    };
}

async function savePlannedRestart(serverId) {
    const payload = buildPlannedRestartPayload(serverId);

    try {
        const response = await fetch(`${API_URL}/api/servers/${serverId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': getApiKey()
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            showToast(`Не удалось сохранить restart: ${await parseApiError(response)}`, 'error');
            return;
        }

        await fetchServerAndUpdate(serverId);
        showToast('Planned restart сохранён', 'success', 3000);
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// ============================================================
// Logs
// ============================================================

async function loadLogs() {
    try {
        const response = await fetch(`${API_URL}/api/logs?limit=100`);
        const data = await response.json();

        const container = document.getElementById('logs-container');
        container.innerHTML = '';

        data.logs.forEach(log => {
            container.appendChild(createLogEntry(log));
        });

        container.scrollTop = container.scrollHeight;
    } catch (error) {
        console.error('Failed to load logs:', error);
    }
}

function createLogEntry(log) {
    const div = document.createElement('div');
    div.className = 'log-entry';

    // Parse log format: [timestamp] [LEVEL] message
    const match = log.match(/\[(.*?)\] \[(.*?)\] (.*)/);
    if (match) {
        div.innerHTML = `
            <span class="timestamp">[${match[1]}]</span>
            <span class="level ${match[2]}">[${match[2]}]</span>
            <span class="message">${match[3]}</span>
        `;
    } else {
        div.textContent = log;
    }

    return div;
}

function clearLogs() {
    document.getElementById('logs-container').innerHTML = '';
}

// ============================================================
// WebSocket
// ============================================================

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/logs`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
        updateConnectionStatus(true);
    };

    ws.onmessage = (event) => {
        const container = document.getElementById('logs-container');
        const logEntry = createLogEntry(event.data);
        container.appendChild(logEntry);
        container.scrollTop = container.scrollHeight;

        // Limit log entries in DOM
        while (container.children.length > 200) {
            container.removeChild(container.firstChild);
        }
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);

        // Reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus(false);
    };
}

// ============================================================
// Helpers
// ============================================================

function updateConnectionStatus(connected) {
    const statusDot = document.getElementById('connection-status');
    const statusText = document.getElementById('connection-text');

    if (connected) {
        statusDot.className = 'status-dot online';
        statusText.textContent = 'Connected';
    } else {
        statusDot.className = 'status-dot offline';
        statusText.textContent = 'Disconnected';
    }
}

function getApiKey() {
    // Сначала проверить поле ввода, затем localStorage
    const inputKey = document.getElementById('api-key-input')?.value;
    if (inputKey && inputKey !== 'change_this_api_key') {
        return inputKey;
    }
    return localStorage.getItem('dayz_api_key') || 'change_this_api_key';
}

// ============================================================
// Shutdown Manager
// ============================================================

async function shutdownManager() {
    showToast('Останавливаем менеджер и все серверы…', 'info', 4000);

    try {
        const response = await fetch(`${API_URL}/api/shutdown`, {
            method: 'POST',
            headers: {
                'X-API-Key': getApiKey()
            }
        });

        if (!response.ok) {
            showToast(`Shutdown failed: ${await parseApiError(response)}`, 'error');
            return;
        }

        document.getElementById('connection-text').textContent = 'Shutting down...';
    } catch (error) {
        document.getElementById('connection-text').textContent = 'Shutting down...';
    }
}
