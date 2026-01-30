// ========== MODERATION PAGE - STANDALONE ==========
let currentGuildId = null;
let authToken = null;
let api = null;

// ========== ИНИЦИАЛИЗАЦИЯ ==========
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 Панель модерации загружается...');
    
    // Проверка авторизации
    authToken = localStorage.getItem('authToken');
    const userRole = localStorage.getItem('userRole');
    
    if (!authToken) {
        console.warn('⚠️ Токен отсутствует, редирект на login');
        window.location.href = 'login.html';
        return;
    }
    
    // Проверка прав
    if (userRole !== 'moderator' && userRole !== 'admin') {
        console.warn('⚠️ Недостаточно прав:', userRole);
        showToast('Недостаточно прав для модерации', 'error');
        setTimeout(() => window.location.href = 'index.html', 2000);
        return;
    }
    
    console.log('✅ Авторизация успешна, роль:', userRole);
    
    // Используем глобальный API из api.js
    api = window.api || new API();
    
    // Инициализация
    try {
        await loadGuilds();
        initializeEventHandlers();
        hideLoading();
        showToast('Подключение успешно!', 'success');
    } catch (error) {
        console.error('❌ Ошибка инициализации:', error);
        showToast('Ошибка подключения к боту', 'error');
        hideLoading();
    }
});

// ========== ЗАГРУЗКА СЕРВЕРОВ ==========
async function loadGuilds() {
    try {
        const guilds = await api.getGuilds();
        console.log('✅ Серверы загружены:', guilds.length);
        
        const guildSelect = document.getElementById('guildSelect');
        if (!guildSelect) {
            console.error('❌ #guildSelect не найден!');
            return;
        }
        
        guildSelect.innerHTML = '<option value="">Выберите сервер...</option>';
        
        guilds.forEach(guild => {
            const option = document.createElement('option');
            option.value = guild.id;
            option.textContent = guild.name;
            guildSelect.appendChild(option);
        });
        
        // Автовыбор первого сервера
        if (guilds.length > 0) {
            guildSelect.value = guilds[0].id;
            await onGuildChange();
        } else {
            showToast('Бот не добавлен ни на один сервер', 'warning');
        }
    } catch (error) {
        console.error('❌ Ошибка загрузки серверов:', error);
        throw error;
    }
}

// ========== СМЕНА СЕРВЕРА ==========
async function onGuildChange() {
    const guildSelect = document.getElementById('guildSelect');
    currentGuildId = guildSelect.value;
    
    if (!currentGuildId) return;
    
    console.log('🔄 Переключение на сервер:', currentGuildId);
    
    try {
        // Загружаем участников и каналы
        const [members, channels] = await Promise.all([
            api.getMembers(currentGuildId),
            api.getChannels(currentGuildId)
        ]);
        
        console.log('✅ Загружено:', members.length, 'участников,', channels.length, 'каналов');
        
        // Заполняем селекты
        populateMemberSelects(members);
        populateLogChannelSelects(channels);
        
        // Загружаем наказания
        await Promise.all([
            displayActivePunishments(),
            displayModerationHistory()
        ]);
        
        showToast('Данные загружены', 'success');
    } catch (error) {
        console.error('❌ Ошибка загрузки данных сервера:', error);
        showToast('Ошибка загрузки данных сервера', 'error');
    }
}

// ========== ЗАПОЛНЕНИЕ СЕЛЕКТОВ ==========
function populateMemberSelects(members) {
    const selects = ['muteUser', 'kickUser', 'banUser', 'warnUser'];
    
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) {
            console.warn(`⚠️ #${selectId} не найден`);
            return;
        }
        
        select.innerHTML = '<option value="">Выберите пользователя</option>';
        
        members.forEach(member => {
            const option = document.createElement('option');
            option.value = member.id;
            option.textContent = member.username || member.name;
            select.appendChild(option);
        });
    });
}

function populateLogChannelSelects(channels) {
    const textChannels = channels.filter(c => c.type === 'text' || c.type === 0);
    const selects = ['muteLogChannel', 'kickLogChannel', 'banLogChannel', 'warnLogChannel'];
    
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) {
            console.warn(`⚠️ #${selectId} не найден`);
            return;
        }
        
        select.innerHTML = '<option value="">Не выбран</option>';
        
        textChannels.forEach(channel => {
            const option = document.createElement('option');
            option.value = channel.id;
            option.textContent = `# ${channel.name}`;
            select.appendChild(option);
        });
    });
}

// ========== ОБРАБОТЧИКИ СОБЫТИЙ ==========
function initializeEventHandlers() {
    // Смена сервера
    document.getElementById('guildSelect')?.addEventListener('change', onGuildChange);
    
    // Формы модерации
    document.getElementById('muteForm')?.addEventListener('submit', handleMute);
    document.getElementById('kickForm')?.addEventListener('submit', handleKick);
    document.getElementById('banForm')?.addEventListener('submit', handleBan);
    document.getElementById('warnForm')?.addEventListener('submit', handleWarn);
    
    // Кнопки быстрого выбора длительности мута
    document.querySelectorAll('.duration-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const duration = btn.dataset.duration;
            document.getElementById('muteDuration').value = duration;
        });
    });
    
    // Табы активных наказаний
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            
            btn.classList.add('active');
            const target = document.getElementById(btn.dataset.tab);
            if (target) target.classList.add('active');
        });
    });
}

// ========== ОБРАБОТЧИКИ ФОРМ ==========
async function handleMute(e) {
    e.preventDefault();
    const userId = document.getElementById('muteUser').value;
    const duration = parseInt(document.getElementById('muteDuration').value);
    const reason = document.getElementById('muteReason').value;
    const logChannelId = document.getElementById('muteLogChannel').value;
    
    if (!userId || !duration) {
        showToast('Заполните все поля', 'warning');
        return;
    }
    
    try {
        await api.muteUser(currentGuildId, userId, duration, reason, logChannelId || null);
        const userName = document.getElementById('muteUser').selectedOptions[0].text;
        showToast(`${userName} замучен на ${duration}с`, 'success');
        e.target.reset();
        await displayActivePunishments();
        await displayModerationHistory();
    } catch (error) {
        console.error('❌ Ошибка мута:', error);
        showToast('Ошибка мута', 'error');
    }
}

async function handleKick(e) {
    e.preventDefault();
    const userId = document.getElementById('kickUser').value;
    const reason = document.getElementById('kickReason').value;
    const logChannelId = document.getElementById('kickLogChannel').value;
    
    if (!userId) {
        showToast('Выберите пользователя', 'warning');
        return;
    }
    
    try {
        await api.kickUser(currentGuildId, userId, reason, logChannelId || null);
        const userName = document.getElementById('kickUser').selectedOptions[0].text;
        showToast(`${userName} кикнут`, 'success');
        e.target.reset();
        await displayModerationHistory();
    } catch (error) {
        console.error('❌ Ошибка кика:', error);
        showToast('Ошибка кика', 'error');
    }
}

async function handleBan(e) {
    e.preventDefault();
    const userId = document.getElementById('banUser').value;
    const reason = document.getElementById('banReason').value;
    const deleteMessages = document.getElementById('banDeleteMessages')?.checked ? 1 : 0;
    const logChannelId = document.getElementById('banLogChannel').value;
    
    if (!userId) {
        showToast('Выберите пользователя', 'warning');
        return;
    }
    
    try {
        await api.banUser(currentGuildId, userId, reason, deleteMessages, logChannelId || null);
        const userName = document.getElementById('banUser').selectedOptions[0].text;
        showToast(`${userName} забанен`, 'success');
        e.target.reset();
        await displayActivePunishments();
        await displayModerationHistory();
    } catch (error) {
        console.error('❌ Ошибка бана:', error);
        showToast('Ошибка бана', 'error');
    }
}

async function handleWarn(e) {
    e.preventDefault();
    const userId = document.getElementById('warnUser').value;
    const reason = document.getElementById('warnReason').value;
    const logChannelId = document.getElementById('warnLogChannel').value;
    
    if (!userId || !reason) {
        showToast('Заполните все поля', 'warning');
        return;
    }
    
    try {
        await api.warnUser(currentGuildId, userId, reason, logChannelId || null);
        const userName = document.getElementById('warnUser').selectedOptions[0].text;
        showToast(`${userName} предупреждён`, 'success');
        e.target.reset();
        await displayActivePunishments();
        await displayModerationHistory();
    } catch (error) {
        console.error('❌ Ошибка варна:', error);
        showToast('Ошибка варна', 'error');
    }
}

// ========== UNMUTE/UNBAN ==========
async function unmuteMember(userId, userName) {
    if (!confirm(`Размутить ${userName}?`)) return;
    
    try {
        await api.unmuteUser(currentGuildId, userId);
        showToast(`${userName} размучен`, 'success');
        await displayActivePunishments();
        await displayModerationHistory();
    } catch (error) {
        console.error('❌ Ошибка размута:', error);
        showToast('Ошибка размута', 'error');
    }
}

async function unbanMember(userId, userName) {
    if (!confirm(`Разбанить ${userName}?`)) return;
    
    try {
        await api.unbanUser(currentGuildId, userId);
        showToast(`${userName} разбанен`, 'success');
        await displayActivePunishments();
        await displayModerationHistory();
    } catch (error) {
        console.error('❌ Ошибка разбана:', error);
        showToast('Ошибка разбана', 'error');
    }
}

// ========== ЗАГРУЗКА НАКАЗАНИЙ ==========
async function displayActivePunishments() {
    // Проверяем наличие currentGuildId
    if (!currentGuildId) {
        console.warn('⚠️ Нет выбранного сервера');
        return;
    }
    
    const mutesCont = document.getElementById('activeMutes');
    const bansCont = document.getElementById('activeBans');
    const warnsCont = document.getElementById('activeWarnings');
    if (!mutesCont || !bansCont || !warnsCont) return;
    try {
        const punishments = await api.getPunishments(currentGuildId);
        const mutes = Object.entries(punishments.mutes);
        if (mutes.length === 0) {
            mutesCont.innerHTML = '<p class="loading-text">Нет активных мутов</p>';
        } else {
            mutesCont.innerHTML = mutes.map(([userId, data]) => `
                <div class="punishment-item mute">
                    <div class="punishment-info">
                        <h4>${data.member_name}</h4>
                        <p>Причина: ${data.reason || 'Не указана'}</p>
                        <p>До: ${data.until ? new Date(data.until).toLocaleString('ru-RU') : 'Не указано'}</p>
                    </div>
                    <button class="btn btn-success btn-sm" onclick="unmuteMember('${userId}', '${data.member_name}')">
                        <i class="fas fa-volume-up"></i> Снять мут
                    </button>
                </div>
            `).join('');
        }
        const bans = Object.entries(punishments.bans);
        if (bans.length === 0) {
            bansCont.innerHTML = '<p class="loading-text">Нет активных банов</p>';
        } else {
            bansCont.innerHTML = bans.map(([userId, data]) => `
                <div class="punishment-item ban">
                    <div class="punishment-info">
                        <h4>${data.user_name}</h4>
                        <p>Причина: ${data.reason || 'Не указана'}</p>
                        <p>ID: ${userId}</p>
                    </div>
                    <button class="btn btn-success btn-sm" onclick="unbanMember('${userId}', '${data.user_name}')">
                        <i class="fas fa-user-check"></i> Разбанить
                    </button>
                </div>
            `).join('');
        }
        // Варны
        const warnings = Object.entries(punishments.warnings || {});
        if (warnings.length === 0) {
            warnsCont.innerHTML = '<p class="loading-text">Нет активных предупреждений</p>';
        } else {
            warnsCont.innerHTML = warnings.map(([userId, data]) => `
                <div class="punishment-item warning">
                    <div class="punishment-info">
                        <h4>${data.username} <span class="badge badge-warning">${data.count}/3</span></h4>
                        ${data.warnings.map(w => `
                            <div style="margin: 5px 0; padding: 8px; background: var(--bg-tertiary); border-radius: 4px;">
                                <p><strong>Причина:</strong> ${w.reason}</p>
                                <p style="font-size: 12px; color: var(--text-secondary);">${w.time ? new Date(w.time).toLocaleString('ru-RU') : 'Неизвестно'}</p>
                            </div>
                        `).join('')}
                    </div>
                    <button class="btn btn-success btn-sm" onclick="clearUserWarnings('${userId}', '${data.username}')">
                        <i class="fas fa-eraser"></i> Очистить
                    </button>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Ошибка наказаний:', error);
    }
}

async function displayModerationHistory() {
    const container = document.getElementById('moderationHistory');
    if (!container) return;
    try {
        const history = await api.getModerationHistory(50);
        if (history.length === 0) {
            container.innerHTML = '<p class="loading-text">История пуста</p>';
            return;
        }
        container.innerHTML = history.map(action => `
            <div class="activity-item moderation">
                <div class="activity-icon" style="background: linear-gradient(135deg, #faa81a 0%, #f5576c 100%)">
                    <i class="${action.icon}"></i>
                </div>
                <div class="activity-content">
                    <h4>${action.action || 'Модерация'}</h4>
                    <p>Пользователь: ${action.username || action.user || 'Unknown'}</p>
                    ${action.moderator ? `<p>Модератор: ${action.moderator}</p>` : ''}
                    ${action.reason ? `<p>Причина: ${action.reason}</p>` : ''}
                    ${action.duration ? `<p>Длительность: ${action.duration}</p>` : ''}
                    <span class="activity-time">${new Date(action.time).toLocaleString('ru-RU')}</span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка истории:', error);
    }
}

async function displayReactionRolesList() {
    const container = document.getElementById('reactionRolesList');
    if (!container) return;
    try {
        const rr = await api.getReactionRoles(currentGuildId);
        const entries = Object.entries(rr);
        if (entries.length === 0) {
            container.innerHTML = '<p class="loading-text">Нет систем</p>';
            return;
        }
        container.innerHTML = entries.map(([messageId, data]) => `
            <div class="reaction-role-item">
                <div>
                    <strong>Сообщение ID: ${messageId}</strong>
                    <p style="color: var(--text-muted); margin: 5px 0;">${data.message}</p>
                    <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px;">
                        ${data.reactions.map(r => {
                            const role = cachedData.roles.find(role => role.id === r.role_id);
                            return `<span style="background: var(--bg-tertiary); padding: 5px 10px; border-radius: 12px;">${r.emoji} → ${role ? role.name : 'Unknown'}</span>`;
                        }).join('')}
                    </div>
                </div>
                <div style="display: flex; gap: 10px;">
                    <button class="icon-btn" onclick="editReactionRole('${messageId}')" title="Редактировать">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="icon-btn" onclick="confirmDeleteReactionRole('${messageId}')" title="Удалить">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка reaction roles:', error);
    }
}

function switchPunishmentTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
    event.target.closest('.tab-btn').classList.add('active');
    document.getElementById('activeMutes').style.display = tab === 'mutes' ? 'flex' : 'none';
    document.getElementById('activeBans').style.display = tab === 'bans' ? 'flex' : 'none';
    document.getElementById('activeWarnings').style.display = tab === 'warnings' ? 'flex' : 'none';
}

// Адаптер для совместимости с app.js

// ========== УТИЛИТЫ ==========
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) {
        console.warn('⚠️ #toastContainer не найден');
        return;
    }
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icon = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    }[type] || 'fa-info-circle';
    
    toast.innerHTML = `
        <i class="fas ${icon}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function hideLoading() {
    const loadingScreen = document.getElementById('loadingScreen');
    if (loadingScreen) {
        loadingScreen.style.display = 'none';
    }
}

console.log('✅ moderation.js загружен');

// ========== УТИЛИТЫ ДЛЯ HTML ==========
function setMuteDuration(duration) {
    document.getElementById('muteDuration').value = duration;
}

function switchPunishmentTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
    event.target.closest('.tab-btn').classList.add('active');
    document.getElementById('activeMutes').style.display = tab === 'mutes' ? 'flex' : 'none';
    document.getElementById('activeBans').style.display = tab === 'bans' ? 'flex' : 'none';
    document.getElementById('activeWarnings').style.display = tab === 'warnings' ? 'flex' : 'none';
}

console.log('✅ Утилиты для HTML загружены');
