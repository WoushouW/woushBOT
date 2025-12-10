const API_URL = "http://localhost:5000/api";
let currentPin = "";
let currentGuildId = null;
let staticData = null; 

// --- AUTH ---
async function checkSession() {
    const session = JSON.parse(localStorage.getItem('admin_session'));
    const isTelegram = window.Telegram?.WebApp?.initDataUnsafe?.user;
    
    if (isTelegram) {
        const tgSession = JSON.parse(localStorage.getItem('tg_session'));
        if (tgSession && tgSession.uid === isTelegram.id && (Date.now() - tgSession.time < 24 * 60 * 60 * 1000)) {
            startApp(); return;
        }
    }
    
    if (session && (Date.now() - session.time < 2 * 60 * 60 * 1000)) {
        startApp(); return;
    }
    document.getElementById('login-screen').classList.remove('hidden');
}

async function inputPin(num) {
    if (currentPin.length < 6) {
        currentPin += num;
        renderPinDots();
        if (currentPin.length === 6) await verifyPin();
    }
}

function renderPinDots() {
    const c = document.getElementById('pin-dots'); c.innerHTML = '';
    for(let i=0; i<6; i++) c.innerHTML += `<div class="w-3 h-3 rounded-full border border-white/20 transition ${i<currentPin.length ? 'bg-violet-500 shadow-[0_0_15px_#8b5cf6] scale-110' : 'bg-white/5'}"></div>`;
}

function deletePin() { currentPin = currentPin.slice(0, -1); renderPinDots(); }

async function verifyPin() {
    try {
        const res = await fetch(`${API_URL}/auth`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pin:currentPin})});
        if((await res.json()).success) {
            localStorage.setItem('admin_session', JSON.stringify({time: Date.now()}));
            if (window.Telegram?.WebApp?.initDataUnsafe?.user) {
                localStorage.setItem('tg_session', JSON.stringify({time: Date.now(), uid: window.Telegram.WebApp.initDataUnsafe.user.id}));
            }
            startApp();
        } else {
            document.getElementById('login-error').innerText = "ACCESS DENIED"; currentPin = ""; renderPinDots();
        }
    } catch(e) { document.getElementById('login-error').innerText = "Server Offline"; }
}

function startApp() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('dashboard-layout').classList.remove('hidden');
    initApp();
}

// --- INIT ---
async function initApp() {
    const res = await fetch(`${API_URL}/init`);
    const data = await res.json();
    document.getElementById('bot-name').innerText = data.bot.name;
    if(data.bot.avatar) document.getElementById('bot-avatar').src = data.bot.avatar;
    
    const sel = document.getElementById('guild-selector');
    sel.innerHTML = '';
    data.guilds.forEach(g => sel.innerHTML += `<option value="${g.id}">${g.name}</option>`);
    
    if(data.guilds.length > 0) {
        currentGuildId = data.guilds[0].id;
        await loadStaticData();
        loadPage('dashboard');
        setInterval(updateActivity, 3000); 
    }
    
    sel.addEventListener('change', async (e) => {
        currentGuildId = e.target.value;
        await loadStaticData();
        loadPage('dashboard');
    });
}

async function loadStaticData() {
    const res = await fetch(`${API_URL}/guild/${currentGuildId}/full`);
    staticData = await res.json();
}

async function updateActivity() {
    if (!currentGuildId) return;
    const res = await fetch(`${API_URL}/guild/${currentGuildId}/full`);
    const data = await res.json();
    
    const active = document.querySelector('.sidebar-btn.active')?.dataset.tab;
    
    // Обновляем логи если мы на вкладке дашборда или активности
    if(active === 'dashboard' || active === 'activity') {
        renderActivityFeed(document.getElementById('activity-feed'), data.activity);
    }
    // Обновляем списки банов/мутов если мы на вкладке модерации
    if(active === 'moderation') {
        renderModLists(data.mutes); // Вспомогательная функция для обновления списков
    }
    
    staticData.activity = data.activity;
    staticData.mutes = data.mutes;
}

// --- NAVIGATION ---
function loadPage(page) {
    document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`[data-tab="${page}"]`);
    if(btn) btn.classList.add('active');
    
    document.getElementById('page-title').innerText = page.replace('tool_', '').replace('_', ' ').toUpperCase();
    
    const content = document.getElementById('content-area');
    content.innerHTML = '<div class="animate-fade"></div>';
    const c = content.firstChild;
    
    const renderers = {
        'dashboard': renderDashboard,
        'messages': renderMessages,
        'moderation': renderModeration,
        'reaction': renderReaction,
        'roles': renderRoles,
        'channels': renderChannels,
        'settings': renderSettings,
        'tool_embed': renderEmbedBuilder, // Теперь тут и опросы
        'tool_user': renderUserLookup
    };
    
    if(renderers[page]) renderers[page](c);
    lucide.createIcons();
}

// --- RENDERERS ---

function renderDashboard(c) {
    c.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="glass-card"><p class="label">Total Members</p><p class="val">${staticData.stats.members}</p></div>
            <div class="glass-card"><p class="label">Roles</p><p class="val text-purple-400">${staticData.stats.roles}</p></div>
            <div class="glass-card"><p class="label">Channels</p><p class="val text-blue-400">${staticData.stats.channels}</p></div>
        </div>
        <div class="glass-card h-96 flex flex-col">
            <h3 class="title mb-4"><i data-lucide="activity"></i> Global Activity Log</h3>
            <div id="activity-feed" class="flex-1 overflow-y-auto custom-scrollbar space-y-2">Loading...</div>
        </div>
    `;
    renderActivityFeed(document.getElementById('activity-feed'), staticData.activity);
}

function renderActivityFeed(c, logs) {
    if(!c) return;
    c.innerHTML = logs.map(a => `
        <div class="flex items-center gap-3 p-3 bg-white/5 rounded border-l-2 border-violet-500/30">
            <div class="p-2 bg-black/20 rounded-full"><i data-lucide="${a.icon}" class="w-4 h-4 text-slate-300"></i></div>
            <div class="flex-1">
                <div class="text-sm font-bold text-white">${a.action}</div>
                <div class="text-xs text-slate-400">${a.details}</div>
            </div>
            <div class="text-[10px] text-slate-500 font-mono text-right">
                <div>${a.time}</div>
            </div>
        </div>
    `).join('') || '<div class="text-center text-slate-500">Log is empty</div>';
    lucide.createIcons();
}

async function renderModeration(c) {
    const users = staticData.members.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
    // Каналы для логов
    const channels = staticData.channels.filter(ch => ch.type === 'text').map(ch => `<option value="${ch.id}">#${ch.name}</option>`).join('');

    c.innerHTML = `
        <div class="glass-card mb-6">
            <h3 class="title mb-2">Настройки Логирования</h3>
            <div class="flex items-center gap-4">
                <span class="text-sm text-slate-400">Отправлять отчеты в канал:</span>
                <select id="mod-log-channel" class="neon-input flex-1">
                    <option value="">-- Не выбрано --</option>
                    ${channels}
                </select>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <div class="glass-card border-t-4 border-yellow-500">
                <h3 class="title"><i data-lucide="mic-off"></i> Mute</h3>
                <select id="mute-user" class="neon-input mb-2"><option value="">User...</option>${users}</select>
                <input id="mute-reason" class="neon-input mb-2" placeholder="Reason">
                <input id="mute-dur" type="number" class="neon-input mb-2" placeholder="Minutes (10)">
                <button onclick="doMod('mute')" class="neon-btn btn-warning w-full">Mute</button>
            </div>
            <div class="glass-card border-t-4 border-orange-500">
                <h3 class="title"><i data-lucide="user-x"></i> Kick</h3>
                <select id="kick-user" class="neon-input mb-2"><option value="">User...</option>${users}</select>
                <input id="kick-reason" class="neon-input mb-2" placeholder="Reason">
                <button onclick="doMod('kick')" class="neon-btn btn-danger w-full">Kick</button>
            </div>
            <div class="glass-card border-t-4 border-red-500">
                <h3 class="title"><i data-lucide="gavel"></i> Ban</h3>
                <select id="ban-user" class="neon-input mb-2"><option value="">User...</option>${users}</select>
                <input id="ban-reason" class="neon-input mb-2" placeholder="Reason">
                <button onclick="doMod('ban')" class="neon-btn btn-danger w-full">Ban</button>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="glass-card h-80 flex flex-col">
                <h3 class="title mb-4">Активные Муты</h3>
                <div id="mutes-list" class="flex-1 overflow-y-auto custom-scrollbar space-y-2">Loading...</div>
            </div>
            <div class="glass-card h-80 flex flex-col">
                <h3 class="title mb-4">Активные Баны</h3>
                <div id="bans-list" class="flex-1 overflow-y-auto custom-scrollbar space-y-2">Loading...</div>
            </div>
        </div>
    `;
    
    // Инициализация списков
    renderModLists(staticData.mutes);
}

// Отдельная функция для обновления списков (вызывается из updateActivity)
async function renderModLists(mutes) {
    const mutesList = document.getElementById('mutes-list');
    const bansList = document.getElementById('bans-list');
    
    if(mutesList) {
        mutesList.innerHTML = mutes.map(m => `
            <div class="flex justify-between items-center p-2 bg-white/5 rounded">
                <span>${m.name} <span class="text-xs text-slate-500">до ${m.until}</span></span>
                <button onclick="doUnmute('${m.id}')" class="text-green-400 text-xs font-bold hover:text-green-300">СНЯТЬ</button>
            </div>
        `).join('') || '<div class="text-slate-500 text-center text-sm mt-4">Нет активных мутов</div>';
    }

    if(bansList) {
        // Баны грузим отдельно, так как это тяжелый запрос
        try {
            const bans = (await (await fetch(`${API_URL}/guild/${currentGuildId}/bans`)).json());
            bansList.innerHTML = bans.map(b => `
                <div class="flex justify-between items-center p-2 bg-white/5 rounded">
                    <div><div class="font-bold text-sm">${b.user.name}</div><div class="text-[10px] text-slate-400">${b.reason || 'No reason'}</div></div>
                    <button onclick="doUnban('${b.user.id}')" class="text-green-400 text-xs font-bold hover:text-green-300">РАЗБАНИТЬ</button>
                </div>
            `).join('') || '<div class="text-slate-500 text-center text-sm mt-4">Нет активных банов</div>';
        } catch(e) { console.error(e); }
    }
}

function renderUserLookup(c) {
    const users = staticData.members.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
    
    c.innerHTML = `
        <div class="glass-card max-w-xl mx-auto">
            <h3 class="title mb-4">User Lookup</h3>
            <select id="lookup-select" class="neon-input mb-6" onchange="lookupUser()"><option value="">Select User...</option>${users}</select>
            
            <div id="lookup-res" class="hidden text-center animate-fade">
                <img id="lu-avatar" class="w-32 h-32 rounded-full mx-auto mb-4 border-4 border-violet-500">
                <h2 id="lu-name" class="text-2xl font-bold text-white">Name</h2>
                <p id="lu-id" class="text-xs text-slate-500 font-mono mb-6">ID</p>
                
                <div class="grid grid-cols-2 gap-4 text-left bg-black/20 p-4 rounded-lg mb-4">
                    <div><p class="label">Joined</p><p id="lu-joined" class="text-white">-</p></div>
                    <div><p class="label">Created</p><p id="lu-created" class="text-white">-</p></div>
                </div>
                
                <div class="text-left">
                    <p class="label mb-2">Roles</p>
                    <div id="lu-roles" class="flex flex-wrap gap-2"></div>
                </div>
            </div>
        </div>
    `;
}

function lookupUser() {
    const uid = document.getElementById('lookup-select').value;
    const user = staticData.members.find(m => m.id === uid);
    if(!user) return;
    
    document.getElementById('lookup-res').classList.remove('hidden');
    document.getElementById('lu-avatar').src = user.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png';
    document.getElementById('lu-name').innerText = user.name;
    document.getElementById('lu-id').innerText = user.id;
    document.getElementById('lu-joined').innerText = user.joined;
    document.getElementById('lu-created').innerText = user.created;
    document.getElementById('lu-roles').innerHTML = user.roles.map(r => `<span class="px-2 py-1 rounded text-xs font-bold bg-white/10" style="color:${r.color}">${r.name}</span>`).join('');
}

function renderEmbedBuilder(c) {
    const channels = staticData.channels.filter(c => c.type === 'text').map(c => `<option value="${c.id}">#${c.name}</option>`).join('');
    
    c.innerHTML = `
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fade">
            <div class="glass-card">
                <div class="flex gap-4 border-b border-white/10 pb-4 mb-4">
                    <button onclick="toggleToolTab('message')" id="tab-btn-message" class="text-white font-bold border-b-2 border-violet-500 pb-1 transition">Message</button>
                    <button onclick="toggleToolTab('poll')" id="tab-btn-poll" class="text-slate-400 hover:text-white pb-1 transition">Poll Maker</button>
                </div>

                <!-- MESSAGE MODE -->
                <div id="tool-mode-message">
                    <h3 class="title mb-2">Embed Config</h3>
                    <select id="msg-channel" class="neon-input mb-4">${channels}</select>
                    <div class="space-y-3">
                        <input id="embed-title" class="neon-input" placeholder="Title" oninput="updatePreview()">
                        <textarea id="embed-desc" class="neon-input h-24" placeholder="Description" oninput="updatePreview()"></textarea>
                        <input id="embed-img" class="neon-input" placeholder="Image URL" oninput="updatePreview()">
                        <input id="embed-color" type="color" value="#5865F2" class="w-full h-10 bg-transparent rounded cursor-pointer" oninput="updatePreview()">
                    </div>
                    <button onclick="sendMsg(true)" class="neon-btn btn-primary mt-4">Send Embed</button>
                </div>

                <!-- POLL MODE -->
                <div id="tool-mode-poll" class="hidden">
                    <h3 class="title mb-2">Create Poll</h3>
                    <select id="poll-channel" class="neon-input mb-4">${channels}</select>
                    <input id="poll-question" class="neon-input mb-4" placeholder="Poll Question?" oninput="updatePollPreview()">
                    
                    <div id="poll-options-list" class="space-y-2 mb-4">
                        <input class="neon-input poll-opt" placeholder="Option 1" oninput="updatePollPreview()">
                        <input class="neon-input poll-opt" placeholder="Option 2" oninput="updatePollPreview()">
                    </div>
                    
                    <div class="flex gap-2 mb-4">
                        <button onclick="addPollOption()" class="text-xs bg-white/10 px-2 py-1 rounded hover:bg-white/20">+ Add Option</button>
                    </div>
                    
                    <button onclick="createPoll()" class="neon-btn btn-success">Create Poll</button>
                </div>
            </div>

            <div>
                <h3 class="label mb-2">Live Preview</h3>
                <div id="preview-box" class="bg-[#36393f] p-4 rounded-lg border border-black/20"></div>
            </div>
        </div>
    `;
    updatePreview(); // Init preview
}

function toggleToolTab(mode) {
    document.getElementById('tool-mode-message').classList.add('hidden');
    document.getElementById('tool-mode-poll').classList.add('hidden');
    document.getElementById('tab-btn-message').className = "text-slate-400 hover:text-white pb-1 transition";
    document.getElementById('tab-btn-poll').className = "text-slate-400 hover:text-white pb-1 transition";
    
    document.getElementById(`tool-mode-${mode}`).classList.remove('hidden');
    document.getElementById(`tab-btn-${mode}`).className = "text-white font-bold border-b-2 border-violet-500 pb-1 transition";
    
    if(mode === 'message') updatePreview();
    else updatePollPreview();
}

function addPollOption() {
    const list = document.getElementById('poll-options-list');
    if(list.children.length >= 10) return showToast("Max 10 options");
    const input = document.createElement('input');
    input.className = "neon-input poll-opt";
    input.placeholder = `Option ${list.children.length + 1}`;
    input.oninput = updatePollPreview;
    list.appendChild(input);
}

function renderMessages(c) {
    // This function is now mostly replaced by Embed Builder in functionality, 
    // but kept for simple messages tab if needed.
    const channels = staticData.channels.filter(c => c.type === 'text').map(c => `<option value="${c.id}">#${c.name}</option>`).join('');
    c.innerHTML = `
        <div class="glass-card max-w-2xl mx-auto animate-fade">
            <h3 class="title">Quick Message</h3>
            <select id="msg-channel" class="neon-input mb-4">${channels}</select>
            <textarea id="msg-content" class="neon-input h-32 mb-4" placeholder="Simple text message..."></textarea>
            <button onclick="sendMsg(false)" class="neon-btn btn-primary">Send</button>
        </div>
    `;
}

function renderChannels(c) {
    c.innerHTML = `
        <div class="glass-card animate-fade">
            <h3 class="title mb-4">Manage Channels</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                ${staticData.channels.map(c => `
                    <div class="glass-card p-4 flex justify-between items-center group">
                        <div class="flex items-center gap-3"><i data-lucide="${c.type==='text'?'hash':'mic'}" class="text-slate-400"></i> ${c.name}</div>
                        <button onclick="deleteCh('${c.id}', '${c.name}')" class="text-red-500 opacity-0 group-hover:opacity-100 transition"><i data-lucide="trash-2"></i></button>
                    </div>`).join('')}
            </div>
        </div>
    `;
}

function renderReaction(c) {
    const channels = staticData.channels.filter(c => c.type === 'text').map(c => `<option value="${c.id}">#${c.name}</option>`).join('');
    const roles = staticData.roles.map(r => `<option value="${r.id}">${r.name}</option>`).join('');
    c.innerHTML = `
        <div class="glass-card max-w-2xl mx-auto animate-fade">
            <h3 class="title">Reaction Role Setup</h3>
            <div class="space-y-4">
                <select id="rr-channel" class="neon-input">${channels}</select>
                <textarea id="rr-text" class="neon-input h-24" placeholder="Message..."></textarea>
                <div class="grid grid-cols-2 gap-4">
                    <input id="rr-emoji" class="neon-input" placeholder="Emoji (✅)">
                    <select id="rr-role" class="neon-input">${roles}</select>
                </div>
                <button onclick="createRR()" class="neon-btn btn-success">Create</button>
            </div>
        </div>
    `;
}

function renderRoles(c) {
    const users = staticData.members.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
    const roles = staticData.roles.map(r => `<option value="${r.id}" style="color:${r.color}">${r.name}</option>`).join('');
    c.innerHTML = `
        <div class="glass-card max-w-xl mx-auto animate-fade">
            <h3 class="title">Manage User Roles</h3>
            <div class="space-y-4">
                <select id="role-user" class="neon-input">${users}</select>
                <select id="role-select" class="neon-input">${roles}</select>
                <div class="flex gap-4">
                    <button onclick="roleAct('add')" class="neon-btn btn-success">Add Role</button>
                    <button onclick="roleAct('remove')" class="neon-btn btn-danger">Remove Role</button>
                </div>
            </div>
        </div>
    `;
}

function renderSettings(c) {
    c.innerHTML = `<div class="glass-card"><h3 class="title">Settings</h3><p class="text-slate-400">Settings module...</p></div>`;
}

// --- ACTIONS ---

async function doMod(type) {
    const uid = document.getElementById(`${type}-user`).value;
    const r = document.getElementById(`${type}-reason`).value;
    const dur = document.getElementById('mute-dur')?.value;
    const logCh = document.getElementById('mod-log-channel')?.value;
    
    if(!uid) return showToast("Select a user!");

    await fetch(`${API_URL}/action/moderation`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            guild_id:currentGuildId, user_id:uid, reason:r, type:type, duration:dur, log_channel: logCh
        })
    });
    showToast(`${type} executed`);
    loadPage('moderation');
}

async function doUnban(uid) {
    const logCh = document.getElementById('mod-log-channel')?.value;
    await fetch(`${API_URL}/action/moderation`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({guild_id:currentGuildId, user_id:uid, type:'unban', log_channel: logCh})
    });
    showToast("Unbanned");
    // Подождем чуть-чуть чтобы API успело обновиться
    setTimeout(() => {
        const active = document.querySelector('.sidebar-btn.active').dataset.tab;
        if(active === 'moderation') loadPage('moderation');
    }, 1000);
}

async function doUnmute(uid) {
    const logCh = document.getElementById('mod-log-channel')?.value;
    await fetch(`${API_URL}/action/moderation`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({guild_id:currentGuildId, user_id:uid, type:'unmute', log_channel: logCh})
    });
    showToast("Unmuted");
    setTimeout(() => {
        const active = document.querySelector('.sidebar-btn.active').dataset.tab;
        if(active === 'moderation') loadPage('moderation');
    }, 1000);
}

async function sendMsg(embed) {
    const payload = { channel_id: document.getElementById('msg-channel').value };
    if(embed) {
        payload.embed = {
            title: document.getElementById('embed-title').value,
            description: document.getElementById('embed-desc').value,
            color: document.getElementById('embed-color').value,
            image: document.getElementById('embed-img').value
        };
    } else {
        payload.content = document.getElementById('msg-content').value;
    }
    await fetch(`${API_URL}/action/send`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    showToast("Sent!");
}

async function createPoll() {
    const channelId = document.getElementById('poll-channel').value;
    const question = document.getElementById('poll-question').value;
    const options = Array.from(document.querySelectorAll('.poll-opt')).map(i => i.value).filter(v => v);
    
    if(!question || options.length < 2) return showToast("Question and at least 2 options required");
    
    await fetch(`${API_URL}/action/poll`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            channel_id: channelId,
            question: question,
            options: options
        })
    });
    showToast("Poll Created!");
}

async function createRR() {
    await fetch(`${API_URL}/action/reaction_role`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            channel_id: document.getElementById('rr-channel').value,
            role_id: document.getElementById('rr-role').value,
            text: document.getElementById('rr-text').value,
            emoji: document.getElementById('rr-emoji').value
        })
    });
    showToast("Created!");
}

async function roleAct(act) {
    await fetch(`${API_URL}/action/role_manage`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            guild_id: currentGuildId,
            user_id: document.getElementById('role-user').value,
            role_id: document.getElementById('role-select').value,
            action: act
        })
    });
    showToast(`Role ${act}ed`);
}

async function deleteCh(id, name) {
    if(!confirm(`Delete channel ${name}?`)) return;
    await fetch(`${API_URL}/action/channel_delete`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({channel_id: id})
    });
    showToast("Deleted"); await loadStaticData(); loadPage('channels');
}

// --- UTILS ---
function updatePreview() {
    const box = document.getElementById('preview-box'); if(!box) return;
    const t = document.getElementById('embed-title')?.value;
    const d = document.getElementById('embed-desc')?.value;
    const c = document.getElementById('embed-color')?.value;
    const i = document.getElementById('embed-img')?.value;
    
    let h = `<div class="flex gap-3"><div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs text-white font-bold">B</div><div><div class="flex items-baseline gap-2"><span class="font-bold text-white text-sm">Bot</span><span class="text-xs text-slate-400">Today</span></div>`;
    h += `<div class="mt-1 bg-[#2f3136] border-l-4 rounded p-3 text-sm" style="border-left-color:${c}">
            ${t ? `<div class="font-bold text-white">${t}</div>` : ''}
            ${d ? `<div class="text-slate-300 whitespace-pre-wrap">${d}</div>` : ''}
            ${i ? `<img src="${i}" class="mt-2 rounded max-h-40">` : ''}
          </div></div></div>`;
    box.innerHTML = h;
}

function updatePollPreview() {
    const box = document.getElementById('preview-box'); if(!box) return;
    const q = document.getElementById('poll-question').value || "Poll Question";
    const opts = Array.from(document.querySelectorAll('.poll-opt')).map(i => i.value).filter(v => v);
    const emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"];
    
    let h = `<div class="flex gap-3"><div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs text-white font-bold">B</div><div><div class="flex items-baseline gap-2"><span class="font-bold text-white text-sm">Bot</span><span class="text-xs text-slate-400">Today</span></div>`;
    h += `<div class="mt-1 bg-[#2f3136] border-l-4 rounded p-3 text-sm" style="border-left-color:#3b82f6">
            <div class="font-bold text-white mb-2">📊 ${q}</div>
            <div class="space-y-1">
                ${opts.map((o, i) => `<div class="text-slate-300">${emojis[i]} ${o}</div>`).join('')}
            </div>
          </div></div></div>`;
    box.innerHTML = h;
}

function showToast(msg) {
    const t = document.createElement('div'); t.className = 'toast'; t.innerHTML = msg;
    document.getElementById('toast-container').appendChild(t); setTimeout(()=>t.remove(), 3000);
}

checkSession();
renderPinDots();
