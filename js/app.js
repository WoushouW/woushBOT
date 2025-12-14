// Discord Bot Dashboard - Unified App
let currentGuildId = null;
let autoRefreshInterval = null;
let cachedData = { guilds: [], members: [], channels: [], roles: [], botInfo: null };
const settings = { autoRefresh: true, notifications: true, refreshInterval: 60 };

document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('authToken');
    if (!token) {
        window.location.href = 'login.html';
        return;
    }
    
    // Применяем ограничения доступа в зависимости от роли
    const userRole = localStorage.getItem('userRole') || 'admin';
    applyRoleRestrictions(userRole);
    
    console.log('🚀 Инициализация...');
    showLoadingScreen();
    loadSettings();
    initNavigation();
    initMobileMenu();
    initForms();
    await initializeBot();
    hideLoadingScreen();
});

async function initializeBot(retryCount = 0) {
    try {
        console.log('🔌 Подключение к боту...');
        const botInfo = await api.getBotInfo();
        cachedData.botInfo = botInfo;
        updateBotInfo(botInfo);
        
        const guilds = await api.getGuilds();
        cachedData.guilds = guilds;
        populateServerSelect(guilds);
        
        if (guilds.length > 0) {
            await selectGuild(guilds[0].id);
        } else {
            showToast('Бот не добавлен ни на один сервер', 'warning');
        }
        
        showToast('Бот подключен!', 'success');
    } catch (error) {
        console.error('❌ Ошибка инициализации:', error);
        
        // Если бот ещё не готов (status 503), повторяем
        if (retryCount < 5 && error.status === 503) {
            console.log(`⏳ Бот ещё загружается... Попытка ${retryCount + 1}/5`);
            showToast(`Бот загружается... (попытка ${retryCount + 1})`, 'warning');
            setTimeout(() => initializeBot(retryCount + 1), 2000);
        } else {
            showToast('Не удалось подключиться к боту', 'error');
        }
    }
}

function updateBotInfo(botInfo) {
    document.getElementById('botName').textContent = botInfo.username;
    document.getElementById('botStatus').innerHTML = '<i class="fas fa-circle"></i> Онлайн';
    if (botInfo.avatar) {
        document.getElementById('botAvatar').innerHTML = `<img src="${botInfo.avatar}" alt="Bot Avatar" style="width: 100%; height: 100%; border-radius: 50%;">`;
    }
    document.getElementById('botUptime').textContent = botInfo.uptime || '-';
    if (document.getElementById('settingsBotName')) {
        document.getElementById('settingsBotName').textContent = botInfo.username;
        document.getElementById('settingsBotId').textContent = botInfo.id;
        document.getElementById('settingsBotGuilds').textContent = botInfo.guilds_count;
        document.getElementById('settingsBotUptime').textContent = botInfo.uptime || '-';
    }
}

function populateServerSelect(guilds) {
    const select = document.getElementById('serverSelect');
    select.innerHTML = '';
    guilds.forEach(guild => {
        const option = document.createElement('option');
        option.value = guild.id;
        option.textContent = guild.name;
        select.appendChild(option);
    });
    // Автоматически выбираем первый сервер
    if (guilds.length > 0) {
        select.value = guilds[0].id;
    }
    select.addEventListener('change', async (e) => {
        if (e.target.value) await selectGuild(e.target.value);
    });
}

async function selectGuild(guildId) {
    try {
        showAutoRefreshIndicator();
        currentGuildId = guildId;
        console.log('🎯 Загрузка сервера:', guildId);
        
        // Используем новый endpoint /full для одного запроса вместо 4-х
        const response = await fetch(`${api.baseURL}/api/guilds/${guildId}/full`, {
            headers: { 'Authorization': `Bearer ${api.token}` }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        cachedData.currentGuild = data.guild;
        cachedData.members = data.members;
        cachedData.channels = data.channels;
        cachedData.roles = data.roles;
        
        // Обновляем select
        document.getElementById('serverSelect').value = guildId;
        
        await refreshAllData();
        startAutoRefresh();
        hideAutoRefreshIndicator();
        showToast('Сервер загружен', 'success');
    } catch (error) {
        console.error('Ошибка загрузки сервера:', error);
        showToast('Ошибка загрузки данных: ' + error.message, 'error');
        hideAutoRefreshIndicator();
    }
}

async function refreshAllData() {
    if (!currentGuildId) return;
    try {
        updateDashboardStats();
        populateChannelSelects();
        populateMemberSelects();
        populateRoleSelects();
        displayRolesList();
        displayChannelsList();
        await displayActivityFeed();
        await displayRecentActivity();
        await displayReactionRolesList();
        await displayWelcomesList();
        await loadReactionMessages();
        await loadRREditMessages();
        
        // Обновляем модерацию только если находимся на странице модерации
        if (getCurrentPage() === 'moderation') {
            await displayModerationHistory();
            await displayActivePunishments();
        }
    } catch (error) {
        console.error('Ошибка обновления:', error);
    }
}

function updateDashboardStats() {
    if (!cachedData.currentGuild) return;
    const humanMembers = cachedData.members.filter(m => !m.bot);
    // Считаем всех кроме offline
    const onlineMembers = humanMembers.filter(m => m.status && m.status !== 'offline');
    document.getElementById('totalMembers').textContent = cachedData.currentGuild.member_count || cachedData.members.length;
    document.getElementById('onlineMembers').textContent = onlineMembers.length;
    document.getElementById('totalChannels').textContent = cachedData.channels.length;
    document.getElementById('totalRoles').textContent = cachedData.roles.length;
}

function populateChannelSelects() {
    const textChannels = cachedData.channels.filter(c => c.type === 0);
    const selects = ['messageChannel', 'deleteChannel', 'reactionChannel', 'warnLogChannel', 'muteLogChannel', 'kickLogChannel', 'banLogChannel', 'welcomeSourceChannel', 'welcomeTargetChannel'];
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;
        select.innerHTML = '<option value="">Выберите канал</option>';
        textChannels.forEach(channel => {
            const option = document.createElement('option');
            option.value = channel.id;
            option.textContent = `# ${channel.name}`;
            select.appendChild(option);
        });
    });
}

function populateMemberSelects() {
    const humanMembers = cachedData.members.filter(m => !m.bot);
    const selects = ['muteUser', 'kickUser', 'banUser', 'roleUser', 'warnUser', 'userInfoSelect'];
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;
        select.innerHTML = '<option value="">Выберите пользователя</option>';
        humanMembers.forEach(member => {
            const option = document.createElement('option');
            option.value = member.id;
            option.textContent = member.username;
            select.appendChild(option);
        });
    });
}

function populateRoleSelects() {
    const selects = ['roleSelect'];
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;
        select.innerHTML = '<option value="">Выберите роль</option>';
        cachedData.roles.forEach(role => {
            const option = document.createElement('option');
            option.value = role.id;
            option.textContent = role.name;
            const color = role.color ? `#${role.color.toString(16).padStart(6, '0')}` : '#99AAB5';
            option.style.color = color;
            select.appendChild(option);
        });
    });
}

function displayUserRoles() {
    const userId = document.getElementById('roleUser')?.value;
    const display = document.getElementById('userRolesDisplay');
    const list = document.getElementById('currentUserRolesList');
    
    if (!userId || !display || !list) {
        if (display) display.style.display = 'none';
        return;
    }
    
    const member = cachedData.members.find(m => m.id === userId);
    if (!member || !member.roles) {
        display.style.display = 'none';
        return;
    }
    
    const memberRoles = cachedData.roles.filter(role => member.roles.includes(role.id));
    
    if (memberRoles.length === 0) {
        list.innerHTML = '<p class="text-muted">У пользователя нет ролей</p>';
    } else {
        list.innerHTML = memberRoles.map(role => {
            const color = role.color ? `#${role.color.toString(16).padStart(6, '0')}` : '#99AAB5';
            return `
                <div class="role-badge" style="border-left: 3px solid ${color};">
                    <span style="color: ${color}; font-weight: 600;">${role.name}</span>
                </div>
            `;
        }).join('');
    }
    
    display.style.display = 'block';
}

function displayRolesList() {
    const container = document.getElementById('rolesList');
    if (!container) return;
    if (cachedData.roles.length === 0) {
        container.innerHTML = '<p class="loading-text">Нет ролей</p>';
        return;
    }
    container.innerHTML = cachedData.roles.map(role => {
        const color = role.color ? `#${role.color.toString(16).padStart(6, '0')}` : '#99AAB5';
        // Проверяем, что это не системная роль (@everyone)
        const isEveryoneRole = role.name === '@everyone';
        const deleteBtn = isEveryoneRole ? '' : `
            <div class="item-actions">
                <button class="icon-btn" onclick="confirmDeleteRole('${role.id}', '${role.name.replace(/'/g, "\\'").replace(/"/g, '&quot;')}')" title="Удалить роль">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        return `
            <div class="role-item">
                <div class="role-item-info">
                    <div class="role-color" style="background-color: ${color}"></div>
                    <span class="role-name">${role.name}</span>
                    <span class="role-members" style="color: var(--text-muted); font-size: 13px;">${role.members} участников</span>
                </div>
                ${deleteBtn}
            </div>
        `;
    }).join('');
}

function displayChannelsList() {
    const container = document.getElementById('channelsList');
    if (!container) return;
    if (cachedData.channels.length === 0) {
        container.innerHTML = '<p class="loading-text">Нет каналов</p>';
        return;
    }
    
    // ✅ Сортируем по position (как на сервере)
    const sortedChannels = [...cachedData.channels].sort((a, b) => a.position - b.position);
    const getChannelIcon = (type) => {
        switch(type) {
            case 0: return 'hashtag';
            case 2: return 'volume-up';
            case 4: return 'folder';
            default: return 'question';
        }
    };
    const getChannelType = (type) => {
        switch(type) {
            case 0: return 'Текстовый';
            case 2: return 'Голосовой';
            case 4: return 'Категория';
            default: return 'Неизвестно';
        }
    };
    container.innerHTML = sortedChannels.map(channel => `
        <div class="channel-item">
            <div class="channel-item-info">
                <i class="fas fa-${getChannelIcon(channel.type)}"></i>
                <div>
                    <div class="channel-name">${channel.name}</div>
                    <div class="channel-type">${getChannelType(channel.type)}</div>
                </div>
            </div>
            <div class="item-actions">
                <button class="icon-btn" onclick="confirmDeleteChannel('${channel.id}', '${channel.name}')" title="Удалить канал">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

async function displayActivityFeed() {
    const container = document.getElementById('activityFeed');
    if (!container) return;
    const filter = document.getElementById('activityFilter')?.value || 'all';
    try {
        const activities = await api.getActivity(filter, 100);
        console.log(`🔍 Фильтр "${filter}": получено ${activities.length} записей`);
        
        // Обновляем заголовок с количеством
        const pageTitle = document.querySelector('.content-section.active h1');
        if (pageTitle && pageTitle.textContent.includes('Активность')) {
            pageTitle.textContent = `Активность (записей: ${activities.length})`;
        }
        
        if (activities.length === 0) {
            container.innerHTML = '<p class="loading-text">Нет событий для выбранного фильтра</p>';
            return;
        }
        container.innerHTML = activities.map(activity => {
            let timeStr = activity.time || '';
            try {
                if (timeStr) {
                    const date = new Date(timeStr);
                    if (!isNaN(date.getTime())) {
                        timeStr = date.toLocaleString('ru-RU');
                    }
                }
            } catch (e) {}
            
            return `
            <div class="activity-item ${activity.type || ''}">
                <div class="activity-icon" style="background: ${activity.color || 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'}">
                    <i class="${activity.icon || 'fas fa-circle'}"></i>
                </div>
                <div class="activity-content">
                    <h4>${activity.title || 'Событие'}</h4>
                    <p>${activity.description || ''}</p>
                    <span class="activity-time">${timeStr}</span>
                </div>
            </div>
        `;
        }).join('');
    } catch (error) {
        console.error('Ошибка загрузки активности:', error);
    }
}

async function displayRecentActivity() {
    const container = document.getElementById('recentActivity');
    if (!container) return;
    try {
        const activities = await api.getActivity('all', 5);
        if (activities.length === 0) {
            container.innerHTML = '<p class="loading-text">Нет активности</p>';
            return;
        }
        container.innerHTML = activities.map(activity => {
            let timeStr = activity.time || '';
            try {
                if (timeStr) {
                    const date = new Date(timeStr);
                    if (!isNaN(date.getTime())) {
                        timeStr = date.toLocaleString('ru-RU');
                    }
                }
            } catch (e) {}
            
            return `
            <div class="activity-item ${activity.type || ''}">
                <div class="activity-icon" style="background: ${activity.color || 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'}">
                    <i class="${activity.icon || 'fas fa-circle'}"></i>
                </div>
                <div class="activity-content">
                    <h4>${activity.title || 'Событие'}</h4>
                    <p>${activity.description || ''}</p>
                    <span class="activity-time">${timeStr}</span>
                </div>
            </div>
        `;
        }).join('');
    } catch (error) {
        console.error('Ошибка активности:', error);
    }
}

async function displayModerationHistory() {
    // Проверяем что мы на странице модерации
    const moderationPage = document.getElementById('moderationPage');
    if (!moderationPage || !moderationPage.classList.contains('active')) {
        return; // Не обновляем если страница не активна
    }
    
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

async function displayActivePunishments() {
    // Проверяем что мы на странице модерации
    const moderationPage = document.getElementById('moderationPage');
    if (!moderationPage || !moderationPage.classList.contains('active')) {
        return; // Не обновляем если страница не активна
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
                        <p>До: ${new Date(data.until).toLocaleString('ru-RU')}</p>
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
                                <p style="font-size: 12px; color: var(--text-secondary);">${new Date(w.time).toLocaleString('ru-RU')}</p>
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

async function unmuteMember(userId, userName) {
    if (!confirm(`Снять мут с ${userName}?`)) return;
    try {
        await api.unmuteUser(currentGuildId, userId);
        showToast(`Мут снят с ${userName}`, 'success');
        if (getCurrentPage() === 'moderation') {
            await displayActivePunishments();
            await displayModerationHistory();
        }
    } catch (error) {
        showToast('Ошибка снятия мута', 'error');
    }
}

async function unbanMember(userId, userName) {
    if (!confirm(`Разбанить ${userName}?`)) return;
    try {
        await api.unbanUser(currentGuildId, userId);
        showToast(`${userName} разбанен`, 'success');
        if (getCurrentPage() === 'moderation') {
            await displayActivePunishments();
            await displayModerationHistory();
        }
    } catch (error) {
        showToast('Ошибка разбана', 'error');
    }
}

async function clearUserWarnings(userId, userName) {
    if (!confirm(`Очистить все предупреждения у ${userName}?`)) return;
    try {
        // ✅ Получаем log_channel_id из формы варна
        const logChannelId = document.getElementById('warnLogChannel')?.value || null;
        console.log(`🔍 CLEAR WARNINGS: logChannelId = ${logChannelId}`);
        
        await api.clearWarnings(currentGuildId, userId, logChannelId);
        showToast(`Предупреждения ${userName} очищены`, 'success');
        await displayActivePunishments();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка очистки предупреждений', 'error');
    }
}

async function confirmDeleteChannel(channelId, channelName) {
    if (!confirm(`Удалить канал "${channelName}"?`)) return;
    try {
        await api.deleteChannel(channelId);
        showToast(`Канал "${channelName}" удалён`, 'success');
        cachedData.channels = await api.getChannels(currentGuildId);
        displayChannelsList();
        populateChannelSelects();
    } catch (error) {
        showToast('Ошибка удаления канала', 'error');
    }
}

async function confirmDeleteRole(roleId, roleName) {
    if (!confirm(`Удалить роль "${roleName}"?\n\nВнимание: Это действие нельзя отменить!`)) return;
    try {
        await api.deleteRole(roleId);
        showToast(`Роль "${roleName}" удалена`, 'success');
        cachedData.roles = await api.getRoles(currentGuildId);
        displayRolesList();
        populateRoleSelects();
    } catch (error) {
        showToast('Ошибка удаления роли', 'error');
        console.error('Error deleting role:', error);
    }
}

async function confirmDeleteReactionRole(messageId) {
    if (!confirm('Удалить эту систему?')) return;
    try {
        await api.deleteReactionRole(messageId);
        showToast('Система удалена', 'success');
        await displayReactionRolesList();
    } catch (error) {
        showToast('Ошибка удаления', 'error');
    }
}

async function editReactionRole(messageId) {
    try {
        const rr = await api.getReactionRoles(currentGuildId);
        const roleData = rr[messageId];
        if (!roleData) {
            showToast('Система не найдена', 'error');
            return;
        }
        navigateTo('reaction-roles');
        setTimeout(() => {
            const editSection = document.getElementById('rrEditSection');
            if (editSection) {
                editSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                const messageSelect = document.getElementById('editRRMessageSelect');
                if (messageSelect) {
                    messageSelect.value = messageId;
                    loadRREditDetails(messageId);
                }
            }
            showToast('Можно редактировать роли', 'info');
        }, 300);
    } catch (error) {
        console.error('Error loading reaction role:', error);
        showToast('Ошибка загрузки данных', 'error');
    }
}

function initForms() {
    document.getElementById('sendMessageForm')?.addEventListener('submit', handleSendMessage);
    document.getElementById('deleteMessagesForm')?.addEventListener('submit', handleDeleteMessages);
    document.getElementById('muteForm')?.addEventListener('submit', handleMute);
    document.getElementById('kickForm')?.addEventListener('submit', handleKick);
    document.getElementById('banForm')?.addEventListener('submit', handleBan);
    document.getElementById('assignRoleForm')?.addEventListener('submit', handleAssignRole);
    document.getElementById('reactionRoleForm')?.addEventListener('submit', handleCreateReactionRole);
    document.getElementById('editReactionRoleForm')?.addEventListener('submit', handleEditReactionRole);
    document.getElementById('welcomeForm')?.addEventListener('submit', handleCreateWelcome);
    document.getElementById('createChannelForm')?.addEventListener('submit', handleCreateChannel);
    document.getElementById('warnForm')?.addEventListener('submit', handleWarn);
    
    // Обновление счётчика предупреждений при выборе пользователя
    document.getElementById('warnUser')?.addEventListener('change', async (e) => {
        if (e.target.value) {
            await updateWarningsCount(e.target.value);
        }
    });
    document.querySelectorAll('input[name="messageType"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'embed') {
                document.getElementById('normalMessageFields').style.display = 'none';
                document.getElementById('embedMessageFields').style.display = 'block';
            } else {
                document.getElementById('normalMessageFields').style.display = 'block';
                document.getElementById('embedMessageFields').style.display = 'none';
            }
        });
    });
    document.getElementById('activityFilter')?.addEventListener('change', displayActivityFeed);
}

async function handleSendMessage(e) {
    e.preventDefault();
    const channelId = document.getElementById('messageChannel').value;
    const messageType = document.querySelector('input[name="messageType"]:checked').value;
    try {
        let data = {};
        if (messageType === 'embed') {
            const color = parseInt(document.getElementById('embedColor').value.replace('#', ''), 16);
            data.embed = {
                title: document.getElementById('embedTitle').value,
                description: document.getElementById('embedDescription').value,
                color: color
            };
        } else {
            data.content = document.getElementById('messageContent').value;
        }
        await api.sendMessage(channelId, data);
        showToast('Сообщение отправлено', 'success');
        e.target.reset();
        await displayActivityFeed();
        await displayRecentActivity();
    } catch (error) {
        showToast('Ошибка отправки', 'error');
    }
}

async function handleDeleteMessages(e) {
    e.preventDefault();
    const channelId = document.getElementById('deleteChannel').value;
    const amount = parseInt(document.getElementById('deleteAmount').value);
    if (!confirm(`Удалить ${amount} сообщений?`)) return;
    try {
        const result = await api.bulkDelete(channelId, amount);
        showToast(`Удалено ${result.deleted} сообщений`, 'success');
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка удаления', 'error');
    }
}

async function handleMute(e) {
    e.preventDefault();
    const userId = document.getElementById('muteUser').value;
    const duration = parseInt(document.getElementById('muteDuration').value);
    const reason = document.getElementById('muteReason').value;
    const logChannelId = document.getElementById('muteLogChannel').value;
    try {
        await api.muteUser(currentGuildId, userId, duration, reason, logChannelId || null);
        const userName = document.getElementById('muteUser').selectedOptions[0].text;
        showToast(`${userName} замучен на ${duration}с`, 'success');
        e.target.reset();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка мута', 'error');
    }
}

async function handleKick(e) {
    e.preventDefault();
    const userId = document.getElementById('kickUser').value;
    const reason = document.getElementById('kickReason').value;
    const logChannelId = document.getElementById('kickLogChannel').value;
    const userName = document.getElementById('kickUser').selectedOptions[0].text;
    if (!confirm(`Кикнуть ${userName}?`)) return;
    try {
        await api.kickUser(currentGuildId, userId, reason, logChannelId || null);
        showToast(`${userName} кикнут`, 'success');
        e.target.reset();
        await selectGuild(currentGuildId);
        updateDashboardStats();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка кика', 'error');
    }
}

async function handleBan(e) {
    e.preventDefault();
    const userId = document.getElementById('banUser').value;
    const reason = document.getElementById('banReason').value;
    const deleteDays = parseInt(document.getElementById('banDeleteDays').value);
    const logChannelId = document.getElementById('banLogChannel').value;
    const userName = document.getElementById('banUser').selectedOptions[0].text;
    if (!confirm(`Забанить ${userName}?`)) return;
    try {
        await api.banUser(currentGuildId, userId, reason, deleteDays, logChannelId || null);
        showToast(`${userName} забанен`, 'success');
        e.target.reset();
        // Обновляем данные
        await selectGuild(currentGuildId);
        updateDashboardStats();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка бана', 'error');
    }
}

async function handleWarn(e) {
    e.preventDefault();
    const userId = document.getElementById('warnUser').value;
    const reason = document.getElementById('warnReason').value;
    const logChannelId = document.getElementById('warnLogChannel').value;
    const userName = document.getElementById('warnUser').selectedOptions[0].text;
    
    if (!userId || !reason) {
        showToast('Заполните все поля', 'warning');
        return;
    }
    
    try {
        const result = await api.warnUser(currentGuildId, userId, reason, logChannelId || null);
        
        if (result.auto_banned) {
            showToast(`${userName} получил 3 предупреждения и забанен на 24ч!`, 'error');
        } else {
            showToast(`Предупреждение выдано ${userName} (${result.warnings}/3)`, 'warning');
        }
        
        e.target.reset();
        document.getElementById('currentWarnings').textContent = '0';
        await displayActivityFeed();
        if (getCurrentPage() === 'moderation') {
            await displayModerationHistory();
            await displayActivePunishments();
        }
    } catch (error) {
        console.error('Ошибка выдачи предупреждения:', error);
        showToast('Ошибка выдачи предупреждения', 'error');
    }
}

async function updateWarningsCount(userId) {
    if (!userId || !currentGuildId) return;
    try {
        const data = await api.getUserWarnings(currentGuildId, userId);
        const badge = document.getElementById('currentWarnings');
        if (badge) {
            badge.textContent = data.warnings || 0;
            // Меняем цвет в зависимости от количества
            badge.className = 'badge';
            if (data.warnings === 0) {
                badge.classList.add('badge-success');
            } else if (data.warnings === 1) {
                badge.classList.add('badge-warning');
            } else if (data.warnings === 2) {
                badge.classList.add('badge-danger');
            } else if (data.warnings >= 3) {
                badge.classList.add('badge-dark');
            }
        }
    } catch (error) {
        console.error('Ошибка получения предупреждений:', error);
    }
}

async function handleAssignRole(e) {
    e.preventDefault();
    const userId = document.getElementById('roleUser').value;
    const roleId = document.getElementById('roleSelect').value;
    const userName = document.getElementById('roleUser').selectedOptions[0].text;
    const roleName = document.getElementById('roleSelect').selectedOptions[0].text;
    try {
        await api.addRole(currentGuildId, userId, roleId);
        showToast(`Роль ${roleName} выдана ${userName}`, 'success');
        e.target.reset();
        // Обновляем данные через /full endpoint
        await selectGuild(currentGuildId);
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка выдачи роли', 'error');
    }
}

async function removeRole() {
    const userId = document.getElementById('roleUser').value;
    const roleId = document.getElementById('roleSelect').value;
    if (!userId || !roleId) {
        showToast('Выберите пользователя и роль', 'warning');
        return;
    }
    const userName = document.getElementById('roleUser').selectedOptions[0].text;
    const roleName = document.getElementById('roleSelect').selectedOptions[0].text;
    try {
        await api.removeRole(currentGuildId, userId, roleId);
        showToast(`Роль ${roleName} забрана у ${userName}`, 'success');
        document.getElementById('assignRoleForm').reset();
        // Обновляем данные через /full endpoint
        await selectGuild(currentGuildId);
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка удаления роли', 'error');
    }
}

let reactionFieldsCount = 0;
function addReactionField() {
    const container = document.getElementById('reactionsList');
    if (!container) return;
    const fieldId = `reaction-${reactionFieldsCount++}`;
    const fieldHTML = `
        <div class="reaction-field" id="${fieldId}">
            <div class="form-group">
                <label>Эмодзи</label>
                <input type="text" class="form-control reaction-emoji" placeholder="✅" required>
            </div>
            <div class="form-group">
                <label>Роль</label>
                <select class="form-control reaction-role" required>
                    <option value="">Выберите роль</option>
                    ${cachedData.roles.map(role => `<option value="${role.id}">${role.name}</option>`).join('')}
                </select>
            </div>
            <button type="button" class="btn-remove" onclick="removeReactionField('${fieldId}')">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', fieldHTML);
}

function removeReactionField(fieldId) {
    document.getElementById(fieldId)?.remove();
}

async function handleCreateReactionRole(e) {
    e.preventDefault();
    const channelId = document.getElementById('reactionChannel').value;
    const message = document.getElementById('reactionMessage').value;
    const fields = document.querySelectorAll('.reaction-field');
    const reactions = [];
    fields.forEach(field => {
        const emoji = field.querySelector('.reaction-emoji').value;
        const roleId = field.querySelector('.reaction-role').value;
        if (emoji && roleId) {
            reactions.push({ emoji, role_id: roleId });
        }
    });
    if (reactions.length === 0) {
        showToast('Добавьте хотя бы одну реакцию', 'warning');
        return;
    }
    try {
        await api.createReactionRole(currentGuildId, {
            channel_id: channelId,
            message: message,
            reactions: reactions
        });
        showToast('Система создана!', 'success');
        e.target.reset();
        document.getElementById('reactionsList').innerHTML = '';
        reactionFieldsCount = 0;
        addReactionField();
        await displayReactionRolesList();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка создания системы', 'error');
    }
}

async function loadReactionMessages() {
    try {
        const reactionRoles = await api.getReactionRoles(currentGuildId);
        const select = document.getElementById('welcomeMessageSelect');
        if (!select) return;
        
        select.innerHTML = '<option value="">Выберите сообщение</option>';
        
        for (const [messageId, data] of Object.entries(reactionRoles)) {
            const channel = cachedData.channels.find(c => c.id === data.channel_id);
            const option = document.createElement('option');
            option.value = messageId;
            const status = data.unconfigured ? '[Не настроено]' : '';
            option.textContent = `#${channel?.name || 'удалён'} - ${data.message.substring(0, 30)}... ${status}`;
            select.appendChild(option);
        }
    } catch (error) {
        console.error('Ошибка загрузки сообщений:', error);
    }
}

function loadReactionDetails(messageId) {
    if (!messageId) {
        document.getElementById('reactionDetailsSection').style.display = 'none';
        return;
    }
    
    // Показываем раздел настроек
    document.getElementById('reactionDetailsSection').style.display = 'block';
    
    // Загружаем инфо о сообщении
    api.getReactionRoles(currentGuildId).then(reactionRoles => {
        const data = reactionRoles[messageId];
        if (!data) return;
        
        const channel = cachedData.channels.find(c => c.id === data.channel_id);
        const reactions = data.reactions.map(r => r.emoji).join(' ');
        
        document.getElementById('messageInfo').innerHTML = `
            <p><strong>Канал:</strong> #${channel?.name || 'удалён'}</p>
            <p><strong>Текст:</strong> ${data.message}</p>
            <p><strong>Реакции:</strong> ${reactions}</p>
        `;
    });
}

async function handleCreateWelcome(e) {
    e.preventDefault();
    const messageId = document.getElementById('welcomeMessageSelect').value;
    const targetChannelId = document.getElementById('welcomeTargetChannel').value;
    const welcomeMessage = document.getElementById('welcomeMessage').value;
    
    if (!messageId) {
        showToast('Выберите сообщение', 'warning');
        return;
    }
    
    try {
        // Используем существующее сообщение
        await api.createWelcome(currentGuildId, {
            message_id: messageId,
            target_channel_id: targetChannelId,
            welcome_message: welcomeMessage
        });
        showToast('Действие настроено!', 'success');
        e.target.reset();
        document.getElementById('reactionDetailsSection').style.display = 'none';
        await displayWelcomesList();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка сохранения', 'error');
    }
}

// === REACTION ROLES EDIT ===
async function loadRREditMessages() {
    try {
        const reactionRoles = await api.getReactionRoles(currentGuildId);
        const select = document.getElementById('editRRMessageSelect');
        if (!select) return;
        
        select.innerHTML = '<option value="">Выберите сообщение</option>';
        
        for (const [messageId, data] of Object.entries(reactionRoles)) {
            const channel = cachedData.channels.find(c => c.id === data.channel_id);
            const option = document.createElement('option');
            option.value = messageId;
            option.textContent = `#${channel?.name || 'удалён'} - ${data.message.substring(0, 30)}...`;
            select.appendChild(option);
        }
    } catch (error) {
        console.error('Ошибка загрузки:', error);
    }
}

function loadRREditDetails(messageId) {
    if (!messageId) {
        document.getElementById('rrEditSection').style.display = 'none';
        return;
    }
    
    document.getElementById('rrEditSection').style.display = 'block';
    
    api.getReactionRoles(currentGuildId).then(reactionRoles => {
        const data = reactionRoles[messageId];
        if (!data) return;
        
        const channel = cachedData.channels.find(c => c.id === data.channel_id);
        const reactions = data.reactions;
        
        document.getElementById('rrEditInfo').innerHTML = `
            <p><strong>Канал:</strong> #${channel?.name || 'удалён'}</p>
            <p><strong>Текст:</strong> ${data.message}</p>
            <p><strong>Реакций:</strong> ${reactions.length}</p>
        `;
        
        // Генерируем поля для каждой реакции
        let html = '';
        reactions.forEach((reaction, index) => {
            html += `
                <div class="reaction-edit-item" style="display: flex; gap: 10px; margin: 10px 0; align-items: center;">
                    <span style="font-size: 24px;">${reaction.emoji}</span>
                    <select id="rrEditRole_${index}" class="form-control" style="flex: 1;">
                        <option value="">Не назначена</option>
                        ${cachedData.roles.map(role => `
                            <option value="${role.id}" ${reaction.role_id === role.id ? 'selected' : ''}>
                                ${role.name}
                            </option>
                        `).join('')}
                    </select>
                </div>
            `;
        });
        
        document.getElementById('rrEditReactionsList').innerHTML = html;
    });
}

async function handleEditReactionRole(e) {
    e.preventDefault();
    const messageId = document.getElementById('editRRMessageSelect').value;
    
    if (!messageId) {
        showToast('Выберите сообщение', 'warning');
        return;
    }
    
    try {
        const reactionRoles = await api.getReactionRoles(currentGuildId);
        const data = reactionRoles[messageId];
        
        // Собираем новые значения
        const updatedReactions = data.reactions.map((reaction, index) => {
            const roleId = document.getElementById(`rrEditRole_${index}`).value;
            return {
                emoji: reaction.emoji,
                role_id: roleId || null
            };
        });
        
        // Отправляем обновление
        await api.updateReactionRole(messageId, { reactions: updatedReactions });
        
        showToast('Роли обновлены!', 'success');
        e.target.reset();
        document.getElementById('rrEditSection').style.display = 'none';
        await displayReactionRolesList();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка обновления', 'error');
    }
}

// === USER INFO ===
async function loadUserInfo(userId) {
    if (!userId) {
        document.getElementById('userInfoContent').style.display = 'none';
        return;
    }
    
    document.getElementById('userInfoContent').style.display = 'block';
    
    try {
        console.log('Loading user info for userId:', userId);
        console.log('Total members in cache:', cachedData.members.length);
        
        // Получаем данные о пользователе
        const member = cachedData.members.find(m => m.id === userId);
        if (!member) {
            console.error('Member not found in cache:', userId);
            document.getElementById('userInfoContent').innerHTML = '<p class="error">Пользователь не найден в кэше</p>';
            return;
        }
        console.log('Member found:', member);
        
        // Дата регистрации Discord
        const createdTimestamp = parseInt(userId) / 4194304 + 1420070400000;
        const createdDate = new Date(createdTimestamp);
        document.getElementById('userCreatedAt').textContent = createdDate.toLocaleDateString('ru-RU') + ' (' + Math.floor((Date.now() - createdTimestamp) / (1000*60*60*24)) + ' дней назад)';
        
        // Дата присоединения
        if (member.joined_at) {
            const joinedDate = new Date(member.joined_at);
            document.getElementById('userJoinedAt').textContent = joinedDate.toLocaleDateString('ru-RU') + ' (' + Math.floor((Date.now() - joinedDate.getTime()) / (1000*60*60*24)) + ' дней назад)';
        } else {
            document.getElementById('userJoinedAt').textContent = 'Данные недоступны';
        }
        
        // Роли
        const userRoles = member.roles.map(roleId => cachedData.roles.find(r => r.id === roleId)).filter(r => r);
        const rolesHtml = userRoles.length > 0 ? userRoles.map(role => {
            const color = role.color ? `#${role.color.toString(16).padStart(6, '0')}` : '#99aab5';
            return `
                <div class="role-badge" style="border-left: 4px solid ${color}; background: #2c2f33; padding: 10px 15px; margin: 5px 0; border-radius: 5px;">
                    <span style="color: ${color}; font-weight: 600;">${role.name}</span>
                </div>
            `;
        }).join('') : '<p class="no-data">Нет ролей</p>';
        document.getElementById('userRolesList').innerHTML = rolesHtml;
        
        // Статистика по наказаниям и история
        try {
            console.log(`Loading user info for guild=${currentGuildId}, user=${userId}`);
            const userInfo = await api.getUserInfo(currentGuildId, userId);
            console.log('User info received:', userInfo);
            document.getElementById('userPunishments').textContent = userInfo.punishments_count || 0;
            document.getElementById('userWarnings').textContent = userInfo.warnings_count || 0;
            
            // История модерации из API
            if (userInfo.moderation_history && userInfo.moderation_history.length > 0) {
                const historyHtml = userInfo.moderation_history.map(action => `
                    <div class="moderation-item ${action.action}">
                        <div class="moderation-icon">
                            <i class="${action.icon}"></i>
                        </div>
                        <div class="moderation-content">
                            <h4>${action.action.toUpperCase()}</h4>
                            <p>${action.reason || 'Нет причины'}</p>
                            <small>Модератор: ${action.moderator} • ${action.timestamp}</small>
                        </div>
                    </div>
                `).join('');
                document.getElementById('userModerationHistory').innerHTML = historyHtml;
            } else {
                document.getElementById('userModerationHistory').innerHTML = '<p class="loading-text">История пуста</p>';
            }
        } catch (error) {
            console.error('Error loading user info:', error);
            document.getElementById('userPunishments').textContent = 'Ошибка';
            document.getElementById('userWarnings').textContent = 'Ошибка';
            document.getElementById('userModerationHistory').innerHTML = '<p class="error">Ошибка загрузки</p>';
        }

    } catch (error) {
        console.error('Ошибка загрузки инфо:', error);
        showToast('Ошибка загрузки информации', 'error');
    }
}

async function displayWelcomesList() {
    try {
        const welcomes = await api.getWelcomes(currentGuildId);
        const container = document.getElementById('welcomesList');
        if (!container) return;
        
        if (Object.keys(welcomes).length === 0) {
            container.innerHTML = '<p class="no-data">Нет активных систем приветствий</p>';
            return;
        }
        
        let html = '<div class="list-container">';
        for (const [messageId, config] of Object.entries(welcomes)) {
            const sourceChannel = cachedData.channels.find(c => c.id === config.source_channel_id);
            const targetChannel = cachedData.channels.find(c => c.id === config.target_channel_id);
            html += `
                <div class="list-item">
                    <div class="item-content">
                        <div class="item-title">${config.emoji} Триггер: #${sourceChannel?.name || 'удалён'}</div>
                        <div class="item-description">Приветствия в: #${targetChannel?.name || 'удалён'}</div>
                        <div class="item-details">${config.message}</div>
                    </div>
                    <button class="btn btn-danger btn-sm" onclick="deleteWelcome('${messageId}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
        }
        html += '</div>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Ошибка загрузки приветствий:', error);
    }
}

async function deleteWelcome(messageId) {
    if (!confirm('Удалить систему приветствий?')) return;
    try {
        await api.deleteWelcome(messageId);
        showToast('Система удалена', 'success');
        await displayWelcomesList();
    } catch (error) {
        showToast('Ошибка удаления', 'error');
    }
}

async function handleCreateChannel(e) {
    e.preventDefault();
    const type = parseInt(document.getElementById('channelType').value);
    const name = document.getElementById('channelName').value;
    const topic = document.getElementById('channelTopic').value;
    try {
        await api.createChannel(currentGuildId, { type, name, topic: topic || null });
        showToast(`Канал ${name} создан`, 'success');
        e.target.reset();
        cachedData.channels = await api.getChannels(currentGuildId);
        displayChannelsList();
        populateChannelSelects();
        updateDashboardStats();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка создания канала', 'error');
    }
}

function setDeleteAmount(amount) {
    document.getElementById('deleteAmount').value = amount;
}

function setMuteDuration(duration) {
    document.getElementById('muteDuration').value = duration;
}

// Глобальная переменная для отслеживания текущей страницы
let currentPageName = 'dashboard';

function getCurrentPage() {
    return currentPageName;
}

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item[data-page]');
    const pages = document.querySelectorAll('.page');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const pageName = item.dataset.page;
            currentPageName = pageName; // Сохраняем текущую страницу
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            pages.forEach(page => page.classList.remove('active'));
            document.getElementById(`${pageName}Page`)?.classList.add('active');
            document.getElementById('pageTitle').textContent = item.querySelector('span').textContent;
            closeMobileMenu();
            
            // Обновляем модерацию при переходе на страницу
            if (pageName === 'moderation') {
                displayModerationHistory();
                displayActivePunishments();
            }
            // Обновляем активность при переходе
            if (pageName === 'activity') {
                displayActivityFeed();
            }
            // Загружаем статистику активности
            if (pageName === 'activityStats') {
                loadActivityStats();
            }
            // Загружаем подозрительную активность
            if (pageName === 'suspicious') {
                loadSuspicious();
            }
            // Загружаем настройки временных комнат
            if (pageName === 'temp-rooms') {
                loadTempRoomSettings();
            }

        });
    });
}

function navigateTo(pageName) {
    const navItem = document.querySelector(`[data-page="${pageName}"]`);
    if (navItem) navItem.click();
}

function initMobileMenu() {
    const mobileBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    mobileBtn?.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        document.body.classList.toggle('menu-open');
        if (sidebar.classList.contains('open')) {
            const overlay = document.createElement('div');
            overlay.className = 'sidebar-overlay active';
            overlay.addEventListener('click', closeMobileMenu);
            document.body.appendChild(overlay);
        } else {
            document.querySelector('.sidebar-overlay')?.remove();
        }
    });
}

function closeMobileMenu() {
    document.getElementById('sidebar')?.classList.remove('open');
    document.body.classList.remove('menu-open');
    document.querySelector('.sidebar-overlay')?.remove();
}

function startAutoRefresh() {
    if (autoRefreshInterval) clearInterval(autoRefreshInterval);
    if (!settings.autoRefresh) return;
    autoRefreshInterval = setInterval(async () => {
        if (!currentGuildId) return;
        console.log('🔄 Автообновление...');
        showAutoRefreshIndicator();
        try {
            const [members, channels, roles, botInfo] = await Promise.all([
                api.getMembers(currentGuildId),
                api.getChannels(currentGuildId),
                api.getRoles(currentGuildId),
                api.getBotInfo()
            ]);
            cachedData.members = members;
            cachedData.channels = channels;
            cachedData.roles = roles;
            cachedData.botInfo = botInfo;
            updateBotInfo(botInfo);
            await refreshAllData();
        } catch (error) {
            console.error('Ошибка автообновления:', error);
        } finally {
            hideAutoRefreshIndicator();
        }
    }, settings.refreshInterval * 1000);
    console.log(`✅ Автообновление запущено (${settings.refreshInterval}с)`);
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        console.log('⏸️ Автообновление остановлено');
    }
}

async function forceRefresh() {
    if (!currentGuildId) {
        showToast('Сначала выберите сервер', 'warning');
        return;
    }
    showAutoRefreshIndicator();
    showToast('Обновление...', 'info');
    try {
        await selectGuild(currentGuildId);
        showToast('Данные обновлены!', 'success');
    } catch (error) {
        showToast('Ошибка обновления', 'error');
    } finally {
        hideAutoRefreshIndicator();
    }
}

function clearCache() {
    cachedData = {
        guilds: cachedData.guilds,
        botInfo: cachedData.botInfo,
        members: [],
        channels: [],
        roles: [],
        currentGuild: null
    };
    if (currentGuildId) forceRefresh();
    showToast('Кэш очищен', 'success');
}

async function reconnectBot() {
    showLoadingScreen();
    stopAutoRefresh();
    await initializeBot();
    hideLoadingScreen();
    showToast('Бот переподключен', 'success');
}

function saveSettings() {
    settings.autoRefresh = document.getElementById('autoRefreshToggle').checked;
    settings.notifications = document.getElementById('notificationsToggle').checked;
    settings.refreshInterval = parseInt(document.getElementById('refreshInterval').value);
    localStorage.setItem('dashboardSettings', JSON.stringify(settings));
    if (settings.autoRefresh) startAutoRefresh();
    else stopAutoRefresh();
    showToast('Настройки сохранены', 'success');
}

function loadSettings() {
    const saved = localStorage.getItem('dashboardSettings');
    if (saved) Object.assign(settings, JSON.parse(saved));
    document.getElementById('autoRefreshToggle')?.setAttribute('checked', settings.autoRefresh);
    document.getElementById('notificationsToggle')?.setAttribute('checked', settings.notifications);
    document.getElementById('refreshInterval')?.setAttribute('value', settings.refreshInterval);
}

function logout() {
    if (confirm('Выйти?')) {
        localStorage.removeItem('authToken');
        window.location.href = 'login.html';
    }
}

function showLoadingScreen() {
    document.getElementById('loadingScreen')?.classList.remove('hidden');
}

function hideLoadingScreen() {
    setTimeout(() => {
        document.getElementById('loadingScreen')?.classList.add('hidden');
    }, 500);
}

function showAutoRefreshIndicator() {
    document.getElementById('autoRefreshIndicator')?.classList.add('active');
}

function hideAutoRefreshIndicator() {
    document.getElementById('autoRefreshIndicator')?.classList.remove('active');
}

// Ограничение доступа по роли
function applyRoleRestrictions(role) {
    console.log('🔑 Роль пользователя:', role);
    
    if (role === 'room_manager') {
        // Менеджер комнат - СКРЫВАЕМ ТОЛЬКО НАВИГАЦИЮ (не всю sidebar!)
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.style.display = 'none';
        }
        
        // Убираем margin-left у основного контента
        const mainContent = document.querySelector('.main-content');
        if (mainContent) {
            mainContent.style.marginLeft = '0';
            mainContent.style.width = '100%';
        }
        
        // Скрываем кнопку мобильного меню
        const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
        if (mobileMenuBtn) {
            mobileMenuBtn.style.display = 'none';
        }
        
        // Скрываем заголовок страницы (оставляем только выбор сервера)
        const pageTitle = document.getElementById('pageTitle');
        if (pageTitle) {
            pageTitle.style.display = 'none';
        }
        
        // Автоматически переключаемся на temp-rooms
        setTimeout(() => {
            navigateTo('temp-rooms');
        }, 100);
        
        console.log('✅ Применены ограничения для room_manager - виден только выбор сервера');
    } else {
        console.log('✅ Полный доступ (админ)');
    }
}

function showToast(message, type = 'info') {
    if (!settings.notifications) return;
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    toast.innerHTML = `
        <i class="fas ${icons[type] || icons.info}"></i>
        <span>${message}</span>
    `;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Активность пользователей
async function loadActivityStats() {
    const period = document.getElementById('activityPeriod').value;
    const container = document.getElementById('activityStatsContent');
    
    try {
        container.innerHTML = '<p class="loading-text">Загрузка...</p>';
        
        // Загружаем статистику с сервера
        const response = await fetch(`/api/guilds/${currentGuildId}/activity-stats?period=${period}`, {
            headers: { 'Authorization': `Bearer ${api.token}` }
        });
        
        if (!response.ok) throw new Error('Failed to load stats');
        const stats = await response.json();
        
        // Формируем HTML
        let html = '<div class="activity-stats-grid">';
        
        // Сортируем по общей активности
        const sortedUsers = Object.entries(stats.users).sort((a, b) => 
            (b[1].messages + b[1].reactions) - (a[1].messages + a[1].reactions)
        );
        
        sortedUsers.forEach(([userId, data], index) => {
            const member = cachedData.members.find(m => m.id === userId);
            if (!member || member.bot) return;
            
            const totalActivity = data.messages + data.reactions;
            const rank = index + 1;
            const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;
            
            html += `
                <div class="activity-user-card">
                    <div class="activity-rank">${medal}</div>
                    <div class="activity-user-info">
                        <strong>${member.nick || member.username}</strong>
                        <div class="activity-stats-inline">
                            <span>💬 ${data.messages} сообщ.</span>
                            <span>❤️ ${data.reactions} реак.</span>
                        </div>
                    </div>
                    <div class="activity-total">${totalActivity}</div>
                </div>
            `;
        });
        
        html += '</div>';
        
        if (sortedUsers.length === 0) {
            html = '<p class="no-data">Нет данных за выбранный период</p>';
        }
        
        container.innerHTML = html;
    } catch (error) {
        console.error('Error loading activity stats:', error);
        container.innerHTML = '<p class="error">Ошибка загрузки статистики</p>';
    }
}

// === SUSPICIOUS ACTIVITY ===
let allSuspiciousMessages = [];

// === SUSPICIOUS CONFIG ===
let suspiciousConfig = { triggers: [], excluded_channels: [], default_triggers: [] };

async function loadSuspiciousConfig() {
    try {
        const response = await fetch(`/api/guilds/${currentGuildId}/suspicious-config`, {
            headers: { 'Authorization': `Bearer ${api.token}` }
        });
        
        if (!response.ok) throw new Error('Failed to load config');
        suspiciousConfig = await response.json();
        
        // Обновляем UI
        displayTriggers();
        displayExcludedChannels();
        populateChannelSelect();
    } catch (error) {
        console.error('Error loading suspicious config:', error);
    }
}

function displayTriggers() {
    const container = document.getElementById('triggersList');
    const triggers = suspiciousConfig.triggers;
    
    if (triggers.length === 0) {
        container.innerHTML = `
            <p style="color: #99aab5; font-size: 13px;">Используются базовые триггеры (${suspiciousConfig.default_triggers.length} слов)</p>
        `;
    } else {
        container.innerHTML = triggers.map(word => `
            <div style="display: flex; justify-content: space-between; align-items: center; background: #23272a; padding: 8px 12px; margin: 5px 0; border-radius: 5px;">
                <span>${word}</span>
                <button onclick="removeTriggerWord('${word}')" class="icon-btn" style="color: #ed4245;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `).join('');
    }
}

function displayExcludedChannels() {
    const container = document.getElementById('excludedChannelsList');
    const excluded = suspiciousConfig.excluded_channels;
    
    if (excluded.length === 0) {
        container.innerHTML = '<p style="color: #99aab5; font-size: 13px;">Нет исключенных каналов</p>';
    } else {
        container.innerHTML = excluded.map(channelId => {
            const channel = cachedData.channels.find(c => c.id === channelId);
            const channelName = channel ? `#${channel.name}` : `ID: ${channelId}`;
            return `
                <div style="display: flex; justify-content: space-between; align-items: center; background: #23272a; padding: 8px 12px; margin: 5px 0; border-radius: 5px;">
                    <span>${channelName}</span>
                    <button onclick="removeExcludedChannel('${channelId}')" class="icon-btn" style="color: #ed4245;">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
        }).join('');
    }
}

function populateChannelSelect() {
    const select = document.getElementById('excludedChannelSelect');
    select.innerHTML = '<option value="">Выберите канал</option>';
    
    cachedData.channels.filter(c => c.type === 0).forEach(channel => {
        select.innerHTML += `<option value="${channel.id}">#${channel.name}</option>`;
    });
}

async function addTriggerWord() {
    const input = document.getElementById('newTriggerWord');
    const word = input.value.trim();
    
    if (!word) {
        showToast('Введите слово', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/guilds/${currentGuildId}/suspicious-config/triggers`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${api.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ word })
        });
        
        if (!response.ok) throw new Error('Failed to add trigger');
        
        input.value = '';
        showToast(`Триггер "${word}" добавлен`, 'success');
        await loadSuspiciousConfig();
    } catch (error) {
        showToast('Ошибка добавления', 'error');
    }
}

async function removeTriggerWord(word) {
    if (!confirm(`Удалить триггер "${word}"?`)) return;
    
    try {
        const response = await fetch(`/api/guilds/${currentGuildId}/suspicious-config/triggers/${encodeURIComponent(word)}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${api.token}` }
        });
        
        if (!response.ok) throw new Error('Failed to remove trigger');
        
        showToast('Триггер удалён', 'success');
        await loadSuspiciousConfig();
    } catch (error) {
        showToast('Ошибка удаления', 'error');
    }
}

async function addExcludedChannel() {
    const select = document.getElementById('excludedChannelSelect');
    const channelId = select.value;
    
    if (!channelId) {
        showToast('Выберите канал', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/guilds/${currentGuildId}/suspicious-config/excluded-channels`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${api.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ channel_id: channelId })
        });
        
        if (!response.ok) throw new Error('Failed to add channel');
        
        select.value = '';
        showToast('Канал добавлен в исключения', 'success');
        await loadSuspiciousConfig();
    } catch (error) {
        showToast('Ошибка добавления', 'error');
    }
}

async function removeExcludedChannel(channelId) {
    if (!confirm('Удалить канал из исключений?')) return;
    
    try {
        const response = await fetch(`/api/guilds/${currentGuildId}/suspicious-config/excluded-channels/${channelId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${api.token}` }
        });
        
        if (!response.ok) throw new Error('Failed to remove channel');
        
        showToast('Канал удалён из исключений', 'success');
        await loadSuspiciousConfig();
    } catch (error) {
        showToast('Ошибка удаления', 'error');
    }
}

async function loadSuspicious() {
    const container = document.getElementById('suspiciousContent');
    
    try {
        // Загружаем конфигурацию
        await loadSuspiciousConfig();
        
        container.innerHTML = '<p class="loading-text">Загрузка...</p>';
        
        // Загружаем сообщения с сервера
        const response = await fetch(`/api/guilds/${currentGuildId}/suspicious-messages`, {
            headers: { 'Authorization': `Bearer ${api.token}` }
        });
        
        if (!response.ok) throw new Error('Failed to load suspicious messages');
        allSuspiciousMessages = await response.json();
        
        console.log(`✅ Loaded ${allSuspiciousMessages.length} suspicious messages`);
        filterSuspicious();
    } catch (error) {
        console.error('Error loading suspicious:', error);
        container.innerHTML = '<p class="error">Ошибка загрузки</p>';
    }
}

function filterSuspicious() {
    const query = document.getElementById('suspiciousFilter').value.trim();
    const container = document.getElementById('suspiciousContent');
    
    let filtered = allSuspiciousMessages;
    
    if (query) {
        try {
            // Пробуем как regex
            const regex = new RegExp(query, 'i');
            filtered = allSuspiciousMessages.filter(msg => regex.test(msg.content));
        } catch {
            // Если не regex, то простой поиск по запятой
            const keywords = query.toLowerCase().split(',').map(k => k.trim());
            filtered = allSuspiciousMessages.filter(msg => 
                keywords.some(kw => msg.content.toLowerCase().includes(kw))
            );
        }
    }
    
    // Группируем по пользователям
    const byUser = {};
    filtered.forEach(msg => {
        if (!byUser[msg.user_id]) {
            byUser[msg.user_id] = {
                username: msg.username,
                avatar: msg.avatar,
                messages: []
            };
        }
        byUser[msg.user_id].messages.push(msg);
    });
    
    // Сортируем по количеству нарушений
    const sortedUsers = Object.entries(byUser).sort((a, b) => b[1].messages.length - a[1].messages.length);
    
    let html = '<div class="suspicious-users-grid">';
    
    sortedUsers.forEach(([userId, data]) => {
        html += `
            <div class="suspicious-user-card">
                <div class="suspicious-user-header" onclick="toggleSuspiciousDetails('${userId}')">
                    <div class="suspicious-user-info">
                        <strong>${data.username}</strong>
                        <span class="badge badge-danger">${data.messages.length} нарушений</span>
                    </div>
                    <i class="fas fa-chevron-down toggle-icon" id="toggle-${userId}"></i>
                </div>
                <div class="suspicious-details" id="details-${userId}" style="display: none;">
        `;
        
        data.messages.forEach(msg => {
            html += `
                <div class="suspicious-message">
                    <div class="message-time">${new Date(msg.timestamp).toLocaleString('ru-RU')}</div>
                    <div class="message-content">${escapeHtml(msg.content)}</div>
                    <div class="message-channel">#${msg.channel_name || 'неизвестный канал'}</div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    if (sortedUsers.length === 0) {
        html = '<p class="no-data">Нет подозрительных сообщений</p>';
    }
    
    container.innerHTML = html;
}

function toggleSuspiciousDetails(userId) {
    const details = document.getElementById(`details-${userId}`);
    const icon = document.getElementById(`toggle-${userId}`);
    
    if (details.style.display === 'none') {
        details.style.display = 'block';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
    } else {
        details.style.display = 'none';
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
    }
}

// Утилита: экранирование HTML
function escapeHtml(text) {
    if (!text) return '';
    if (typeof text !== 'string') text = String(text);
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ============================================
// ВРЕМЕННЫЕ КОМНАТЫ
// ============================================

async function loadTempRoomSettings() {
    if (!currentGuildId) return;
    // Заполняем селект каналов
    populateTempRoomChannelSelect();
    // Загружаем активные комнаты
    await loadActiveRooms();
}

function populateTempRoomChannelSelect() {
    const textChannels = cachedData.channels.filter(c => c.type === 0);
    const select = document.getElementById('tempRoomChannelSelect');
    if (!select) return;
    
    select.innerHTML = '<option value="">Выберите канал...</option>';
    textChannels.forEach(channel => {
        const option = document.createElement('option');
        option.value = channel.id;
        option.textContent = `# ${channel.name}`;
        select.appendChild(option);
    });
}

async function loadChannelMessages(channelId) {
    if (!channelId) {
        document.getElementById('channelMessagesContainer').style.display = 'none';
        return;
    }
    
    const container = document.getElementById('channelMessagesContainer');
    const messagesList = document.getElementById('channelMessagesList');
    const channelNameSpan = document.getElementById('selectedChannelName');
    
    // Находим название канала
    const channel = cachedData.channels.find(c => c.id === channelId);
    channelNameSpan.textContent = channel ? `#${channel.name}` : '';
    
    container.style.display = 'block';
    messagesList.innerHTML = '<p class="text-muted"><i class="fas fa-spinner fa-spin"></i> Загрузка сообщений...</p>';
    
    try {
        const response = await fetch(`${api.baseURL}/api/channels/${channelId}/messages?limit=50`, {
            headers: { 'Authorization': `Bearer ${api.token}` }
        });
        
        if (response.ok) {
            const messages = await response.json();
            console.log('📨 Загружено сообщений:', messages.length);
            if (messages.length > 0) {
                console.log('🔍 Первое сообщение:', messages[0]);
            }
            displayChannelMessages(messages, channelId);
        } else {
            messagesList.innerHTML = '<p class="text-muted">Ошибка загрузки сообщений</p>';
        }
    } catch (error) {
        console.error('Ошибка загрузки сообщений:', error);
        messagesList.innerHTML = '<p class="text-muted">Ошибка загрузки сообщений</p>';
    }
}

function displayChannelMessages(messages, channelId) {
    const messagesList = document.getElementById('channelMessagesList');
    
    if (!messages || messages.length === 0) {
        messagesList.innerHTML = '<p class="text-muted">В этом канале пока нет сообщений</p>';
        return;
    }
    
    messagesList.innerHTML = messages.map(msg => {
        const timestamp = new Date(msg.timestamp).toLocaleString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const content = escapeHtml(msg.content || '[Пустое сообщение]');
        // Обрабатываем author - может быть строкой или объектом
        let authorName = '';
        if (typeof msg.author === 'string') {
            authorName = msg.author;
        } else if (typeof msg.author === 'object' && msg.author !== null) {
            authorName = msg.author.username || msg.author.name || 'Unknown';
        } else {
            authorName = 'Unknown';
        }
        const author = escapeHtml(authorName);
        
        const authorId = msg.author_id || 'unknown';
        
        // Отладка: проверяем наличие author_id
        if (!msg.author_id || msg.author_id === 'unknown') {
            console.warn('⚠️ Сообщение без author_id:', {
                id: msg.id,
                author: msg.author,
                author_id: msg.author_id,
                full_msg: msg
            });
        }
        
        
        // Используем data-атрибуты вместо onclick параметров для избежания проблем с экранированием
        return `
            <div class="message-item" 
                 data-message-id="${msg.id}"
                 data-channel-id="${channelId}"
                 data-author-name="${author}"
                 data-author-id="${authorId}"
                 data-message-text="${escapeHtml(msg.content || '')}">
                <div class="message-header">
                    <span class="message-author">
                        <i class="fas fa-user"></i> ${author}
                    </span>
                    <span class="message-time">
                        <i class="fas fa-clock"></i> ${timestamp}
                    </span>
                </div>
                <div class="message-content">${content}</div>
                <div class="message-id-badge">
                    <i class="fas fa-hashtag"></i> ID: ${msg.id}
                </div>
            </div>
        `;
    }).join('');
    
    // Добавляем обработчики кликов на сообщения
    setTimeout(() => {
        document.querySelectorAll('.message-item').forEach(item => {
            item.addEventListener('click', function() {
                const messageId = this.dataset.messageId;
                const channelId = this.dataset.channelId;
                const authorName = this.dataset.authorName;
                const authorId = this.dataset.authorId;
                const messageText = this.dataset.messageText;
                selectMessage(messageId, channelId, authorName, authorId, messageText);
            });
        });
    }, 100);
}

function selectMessage(messageId, channelId, authorName, authorId, messageText) {
    // Проверяем, что authorId корректный
    if (!authorId || authorId === 'unknown' || authorId === 'null' || authorId === 'undefined') {
        showToast('Не удалось определить ID пользователя. Попробуйте обновить список сообщений.', 'error');
        return;
    }
    
    // Убираем выделение со всех сообщений
    document.querySelectorAll('.message-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    // Выделяем кликнутое сообщение
    const selectedItem = document.querySelector(`[data-message-id="${messageId}"]`);
    if (selectedItem) {
        selectedItem.classList.add('selected');
    }
    
    // Открываем форму создания комнаты
    document.getElementById('createRoomForm').style.display = 'block';
    document.getElementById('selectedUserName').textContent = authorName || 'Неизвестно';
    document.getElementById('selectedMessageId').value = messageId;
    document.getElementById('selectedUserId').value = authorId;
    document.getElementById('selectedChannelId').value = channelId;
    document.getElementById('selectedMessageText').value = messageText || '';  // Сохраняем текст сообщения
    
    // Прокручиваем к форме
    document.getElementById('createRoomForm').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    
    console.log(`Выбрано сообщение: ${messageId} от ${authorName} (${authorId})`);
    showToast(`Сообщение выбрано. Заполните форму`, 'success');
}

function cancelRoomCreation() {
    document.getElementById('createRoomForm').style.display = 'none';
    document.getElementById('tempRoomForm').reset();
    document.querySelectorAll('.message-item').forEach(item => {
        item.classList.remove('selected');
    });
    showToast('Создание комнаты отменено', 'info');
}

// === TEMPORARY ROOMS SYSTEM ===

async function createTempRoom(event) {
    event.preventDefault();
    
    const roomName = document.getElementById('roomName').value.trim();
    const duration = parseInt(document.getElementById('roomDuration').value);
    const userLimit = parseInt(document.getElementById('roomLimit').value);
    const messageId = document.getElementById('selectedMessageId').value;
    const userId = document.getElementById('selectedUserId').value;
    const channelId = document.getElementById('selectedChannelId').value;
    const messageText = document.getElementById('selectedMessageText').value;
    
    if (!roomName || !duration || !userLimit || !userId) {
        showToast('Заполните все поля', 'error');
        return;
    }
    
    if (duration > 90 || duration < 1) {
        showToast('Время должно быть от 1 до 90 минут', 'error');
        return;
    }
    
    if (userLimit > 50 || userLimit < 1) {
        showToast('Лимит должен быть от 1 до 50 человек', 'error');
        return;
    }
    
    try {
        showLoadingScreen();
        
        const response = await fetch(`${api.baseURL}/api/guilds/${currentGuildId}/temp-rooms`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${api.token}`
            },
            body: JSON.stringify({
                room_name: roomName,
                duration_minutes: duration,
                user_limit: userLimit,
                user_id: userId,
                message_id: messageId,
                channel_id: channelId,
                message_text: messageText
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showToast(`Комната "${roomName}" создана!`, 'success');
            
            // Очищаем форму
            document.getElementById('tempRoomForm').reset();
            document.getElementById('createRoomForm').style.display = 'none';
            
            // Обновляем список активных комнат
            await loadActiveRooms();
        } else {
            showToast(result.error || 'Ошибка создания комнаты', 'error');
        }
    } catch (error) {
        console.error('Error creating temp room:', error);
        showToast('Ошибка создания комнаты', 'error');
    } finally {
        hideLoadingScreen();
    }
}

async function loadActiveRooms() {
    const container = document.getElementById('activeRoomsList');
    
    try {
        container.innerHTML = '<p class="loading-text">Загрузка...</p>';
        
        const response = await fetch(`${api.baseURL}/api/guilds/${currentGuildId}/temp-rooms`, {
            headers: { 'Authorization': `Bearer ${api.token}` }
        });
        
        if (!response.ok) throw new Error('Failed to load rooms');
        
        const rooms = await response.json();
        
        if (rooms.length === 0) {
            container.innerHTML = '<p class="no-data">Нет активных временных комнат</p>';
            return;
        }
        
        let html = '<div class="list-container">';
        
        rooms.forEach(room => {
            const createdAt = new Date(room.created_at);
            const expiresAt = new Date(room.expires_at);
            const now = new Date();
            const timeLeft = Math.max(0, Math.floor((expiresAt - now) / 1000 / 60));
            
            const progress = Math.max(0, Math.min(100, (timeLeft / room.duration) * 100));
            const progressColor = progress > 50 ? '#43b581' : progress > 25 ? '#faa61a' : '#ed4245';
            
            html += `
                <div class="list-item" style="border-left: 4px solid ${progressColor};">
                    <div class="item-content">
                        <div class="item-title">
                            <i class="fas fa-door-open"></i> Private_${escapeHtml(room.room_name)}
                        </div>
                        <div class="item-description">
                            <i class="fas fa-user"></i> Создатель: ${escapeHtml(room.owner_name)}
                        </div>
                        <div class="item-details">
                            <span><i class="fas fa-users"></i> Лимит: ${room.user_limit} чел.</span>
                            <span style="margin-left: 15px;">
                                <i class="fas fa-clock"></i> Осталось: ${timeLeft} мин.
                            </span>
                        </div>
                        <div style="margin-top: 8px; background: #1e2124; border-radius: 4px; height: 6px; overflow: hidden;">
                            <div style="width: ${progress}%; height: 100%; background: ${progressColor}; transition: width 0.3s;"></div>
                        </div>
                    </div>
                    <button class="btn btn-danger btn-sm" onclick="deleteTempRoom('${room.channel_id}', '${escapeHtml(room.room_name)}')">
                        <i class="fas fa-trash"></i> Удалить
                    </button>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading active rooms:', error);
        container.innerHTML = '<p class="error">Ошибка загрузки активных комнат</p>';
    }
}

async function deleteTempRoom(channelId, roomName) {
    if (!confirm(`Удалить комнату "Private_${roomName}"?\n\nКомната и роль будут удалены с сервера.`)) {
        return;
    }
    
    try {
        showLoadingScreen();
        
        const response = await fetch(`${api.baseURL}/api/guilds/${currentGuildId}/temp-rooms/${channelId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${api.token}` }
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showToast(`Комната "Private_${roomName}" удалена`, 'success');
            await loadActiveRooms();
        } else {
            showToast(result.error || 'Ошибка удаления комнаты', 'error');
        }
    } catch (error) {
        console.error('Error deleting temp room:', error);
        showToast('Ошибка удаления комнаты', 'error');
    } finally {
        hideLoadingScreen();
    }
}

console.log('✅ Discord Bot Dashboard готов!');
