// Discord Bot Dashboard - Main Application

// Global State
let currentGuildId = null;
let autoRefreshInterval = null;
let cachedData = {
    guilds: [],
    members: [],
    channels: [],
    roles: [],
    botInfo: null
};

// Settings
const settings = {
    autoRefresh: true,
    notifications: true,
    refreshInterval: 60
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
    // Check auth
    const token = localStorage.getItem('authToken');
    if (!token) {
        window.location.href = 'login.html';
        return;
    }

    console.log('🚀 Инициализация Discord Bot Dashboard...');
    showLoadingScreen();

    // Load settings
    loadSettings();

    // Init navigation
    initNavigation();
    initMobileMenu();
    initForms();

    // Initialize bot
    await initializeBot();

    hideLoadingScreen();
});

// --- BOT INITIALIZATION ---
async function initializeBot() {
    try {
        console.log('🔌 Подключение к боту...');

        // Get bot info
        const botInfo = await api.getBotInfo();
        cachedData.botInfo = botInfo;

        updateBotInfo(botInfo);

        // Get guilds
        const guilds = await api.getGuilds();
        cachedData.guilds = guilds;

        populateServerSelect(guilds);

        // Auto-select first guild
        if (guilds.length > 0) {
            await selectGuild(guilds[0].id);
        }

        showToast('Бот успешно подключен!', 'success');
    } catch (error) {
        console.error('❌ Ошибка инициализации:', error);
        showToast('Не удалось подключиться к боту', 'error');
    }
}

// --- UI UPDATES ---
function updateBotInfo(botInfo) {
    document.getElementById('botName').textContent = botInfo.username;
    document.getElementById('botStatus').innerHTML = '<i class="fas fa-circle"></i> Онлайн';

    if (botInfo.avatar) {
        document.getElementById('botAvatar').innerHTML = 
            `<img src="${botInfo.avatar}" alt="Bot Avatar" style="width: 100%; height: 100%; border-radius: 50%;">`;
    }

    // Update settings
    document.getElementById('settingsBotName').textContent = botInfo.username;
    document.getElementById('settingsBotId').textContent = botInfo.id;
    document.getElementById('settingsBotGuilds').textContent = botInfo.guilds_count;
    document.getElementById('settingsBotUptime').textContent = botInfo.uptime || '-';

    // Update dashboard uptime
    document.getElementById('botUptime').textContent = botInfo.uptime || '-';
}

function populateServerSelect(guilds) {
    const select = document.getElementById('serverSelect');
    select.innerHTML = '<option value="">Выберите сервер</option>';

    guilds.forEach(guild => {
        const option = document.createElement('option');
        option.value = guild.id;
        option.textContent = guild.name;
        select.appendChild(option);
    });

    select.addEventListener('change', async (e) => {
        if (e.target.value) {
            await selectGuild(e.target.value);
        }
    });
}

async function selectGuild(guildId) {
    try {
        showAutoRefreshIndicator();
        currentGuildId = guildId;

        console.log('🎯 Загрузка данных сервера:', guildId);

        // Load all data in parallel
        const [guild, members, channels, roles] = await Promise.all([
            api.getGuild(guildId),
            api.getMembers(guildId),
            api.getChannels(guildId),
            api.getRoles(guildId)
        ]);

        // Cache data
        cachedData.currentGuild = guild;
        cachedData.members = members;
        cachedData.channels = channels;
        cachedData.roles = roles;

        // Update UI
        await refreshAllData();

        // Start auto-refresh
        startAutoRefresh();

        hideAutoRefreshIndicator();
        showToast('Сервер загружен успешно', 'success');
    } catch (error) {
        console.error('Ошибка загрузки сервера:', error);
        showToast('Ошибка загрузки данных сервера', 'error');
        hideAutoRefreshIndicator();
    }
}

async function refreshAllData() {
    if (!currentGuildId) return;

    try {
        // Update stats
        updateDashboardStats();

        // Update selects
        populateChannelSelects();
        populateMemberSelects();
        populateRoleSelects();

        // Update lists
        displayRolesList();
        displayChannelsList();
        await displayActivityFeed();
        await displayRecentActivity();
        await displayModerationHistory();
        await displayActivePunishments();
        await displayReactionRolesList();
    } catch (error) {
        console.error('Ошибка обновления данных:', error);
    }
}

function updateDashboardStats() {
    if (!cachedData.currentGuild) return;

    const humanMembers = cachedData.members.filter(m => !m.bot);

    document.getElementById('totalMembers').textContent = cachedData.currentGuild.member_count || cachedData.members.length;
    document.getElementById('onlineMembers').textContent = humanMembers.length;
    document.getElementById('totalChannels').textContent = cachedData.channels.length;
    document.getElementById('totalRoles').textContent = cachedData.roles.length;
}

// --- SELECTS POPULATION ---
function populateChannelSelects() {
    const textChannels = cachedData.channels.filter(c => c.type === 0);

    const selects = ['messageChannel', 'deleteChannel', 'reactionChannel'];

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

    const selects = ['muteUser', 'kickUser', 'banUser', 'roleUser'];

    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;

        select.innerHTML = '<option value="">Выберите пользователя</option>';
        humanMembers.forEach(member => {
            const option = document.createElement('option');
            option.value = member.id;
            option.textContent = member.username;
            option.dataset.roles = JSON.stringify(member.roles);
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

// --- DISPLAY USER ROLES ---
function displayUserRoles() {
    const select = document.getElementById('roleUser');
    const userId = select.value;

    if (!userId) {
        document.getElementById('userRolesDisplay').style.display = 'none';
        return;
    }

    const member = cachedData.members.find(m => m.id === userId);
    if (!member) return;

    const userRoleIds = member.roles;
    const userRoles = cachedData.roles.filter(r => userRoleIds.includes(r.id));

    const display = document.getElementById('userRolesDisplay');
    const list = document.getElementById('userRolesList');

    if (userRoles.length === 0) {
        list.innerHTML = '<p style="color: var(--text-muted);">У пользователя нет ролей</p>';
    } else {
        list.innerHTML = userRoles.map(role => {
            const color = role.color ? `#${role.color.toString(16).padStart(6, '0')}` : '#99AAB5';
            return `
                <div class="user-role-badge" style="border-left-color: ${color}">
                    <div style="width: 12px; height: 12px; border-radius: 50%; background: ${color};"></div>
                    <span>${role.name}</span>
                </div>
            `;
        }).join('');
    }

    display.style.display = 'block';
}

// --- DISPLAY FUNCTIONS ---
function displayRolesList() {
    const container = document.getElementById('rolesList');

    if (cachedData.roles.length === 0) {
        container.innerHTML = '<p class="loading-text">Нет ролей</p>';
        return;
    }

    container.innerHTML = cachedData.roles.map(role => {
        const color = role.color ? `#${role.color.toString(16).padStart(6, '0')}` : '#99AAB5';
        return `
            <div class="role-item">
                <div class="role-item-info">
                    <div class="role-color" style="background-color: ${color}"></div>
                    <span class="role-name">${role.name}</span>
                    <span class="role-members" style="color: var(--text-muted); font-size: 13px;">${role.members} участников</span>
                </div>
            </div>
        `;
    }).join('');
}

function displayChannelsList() {
    const container = document.getElementById('channelsList');

    if (cachedData.channels.length === 0) {
        container.innerHTML = '<p class="loading-text">Нет каналов</p>';
        return;
    }

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

    container.innerHTML = cachedData.channels.map(channel => `
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
    const filter = document.getElementById('activityFilter').value;

    try {
        const activities = await api.getActivity(filter, 100);

        if (activities.length === 0) {
            container.innerHTML = '<p class="loading-text">Нет событий</p>';
            return;
        }

        container.innerHTML = activities.map(activity => `
            <div class="activity-item ${activity.type}">
                <div class="activity-icon" style="background: ${activity.color}">
                    <i class="${activity.icon}"></i>
                </div>
                <div class="activity-content">
                    <h4>${activity.title}</h4>
                    <p>${activity.description}</p>
                    <span class="activity-time">${new Date(activity.time).toLocaleString('ru-RU')}</span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки активности:', error);
    }
}

async function displayRecentActivity() {
    const container = document.getElementById('recentActivity');

    try {
        const activities = await api.getActivity('all', 5);

        if (activities.length === 0) {
            container.innerHTML = '<p class="loading-text">Нет активности</p>';
            return;
        }

        container.innerHTML = activities.map(activity => `
            <div class="activity-item ${activity.type}">
                <div class="activity-icon" style="background: ${activity.color}">
                    <i class="${activity.icon}"></i>
                </div>
                <div class="activity-content">
                    <h4>${activity.title}</h4>
                    <p>${activity.description}</p>
                    <span class="activity-time">${new Date(activity.time).toLocaleString('ru-RU')}</span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки активности:', error);
    }
}

async function displayModerationHistory() {
    const container = document.getElementById('moderationHistory');

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
                    <h4>${action.action}</h4>
                    <p>Пользователь: ${action.user}</p>
                    ${action.reason ? `<p>Причина: ${action.reason}</p>` : ''}
                    ${action.duration ? `<p>Длительность: ${action.duration}</p>` : ''}
                    <span class="activity-time">${new Date(action.time).toLocaleString('ru-RU')}</span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки истории:', error);
    }
}

async function displayActivePunishments() {
    try {
        const punishments = await api.getPunishments(currentGuildId);

        // Display mutes
        const mutesContainer = document.getElementById('activeMutes');
        const mutes = Object.entries(punishments.mutes);

        if (mutes.length === 0) {
            mutesContainer.innerHTML = '<p class="loading-text">Нет активных мутов</p>';
        } else {
            mutesContainer.innerHTML = mutes.map(([userId, data]) => `
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

        // Display bans
        const bansContainer = document.getElementById('activeBans');
        const bans = Object.entries(punishments.bans);

        if (bans.length === 0) {
            bansContainer.innerHTML = '<p class="loading-text">Нет активных банов</p>';
        } else {
            bansContainer.innerHTML = bans.map(([userId, data]) => `
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
    } catch (error) {
        console.error('Ошибка загрузки наказаний:', error);
    }
}

function switchPunishmentTab(tab) {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(t => t.classList.remove('active'));

    event.target.closest('.tab-btn').classList.add('active');

    document.getElementById('activeMutes').style.display = tab === 'mutes' ? 'flex' : 'none';
    document.getElementById('activeBans').style.display = tab === 'bans' ? 'flex' : 'none';
}

// Unmute
async function unmuteMember(userId, userName) {
    if (!confirm(`Снять мут с ${userName}?`)) return;

    try {
        await api.unmuteUser(currentGuildId, userId);
        showToast(`Мут снят с ${userName}`, 'success');
        await displayActivePunishments();
        await displayModerationHistory();
    } catch (error) {
        showToast('Ошибка снятия мута', 'error');
    }
}

// Unban
async function unbanMember(userId, userName) {
    if (!confirm(`Разбанить ${userName}?`)) return;

    try {
        await api.unbanUser(currentGuildId, userId);
        showToast(`${userName} разбанен`, 'success');
        await displayActivePunishments();
        await displayModerationHistory();
    } catch (error) {
        showToast('Ошибка разбана', 'error');
    }
}

// --- REACTION ROLES (MULTIPLE) ---
let reactionFieldsCount = 0;

function addReactionField() {
    const container = document.getElementById('reactionsList');
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
    document.getElementById(fieldId).remove();
}

async function displayReactionRolesList() {
    const container = document.getElementById('reactionRolesList');

    try {
        const rr = await api.getReactionRoles(currentGuildId);
        const entries = Object.entries(rr);

        if (entries.length === 0) {
            container.innerHTML = '<p class="loading-text">Нет активных систем</p>';
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
                <button class="icon-btn" onclick="confirmDeleteReactionRole('${messageId}')" title="Удалить">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки reaction roles:', error);
    }
}

async function confirmDeleteReactionRole(messageId) {
    if (!confirm('Удалить эту систему ролей за реакции?')) return;

    try {
        await api.deleteReactionRole(messageId);
        showToast('Система удалена', 'success');
        await displayReactionRolesList();
    } catch (error) {
        showToast('Ошибка удаления', 'error');
    }
}

// --- CHANNEL DELETE CONFIRMATION ---
async function confirmDeleteChannel(channelId, channelName) {
    if (!confirm(`Вы уверены что хотите удалить канал "${channelName}"?\n\nЭто действие нельзя отменить!`)) return;

    try {
        await api.deleteChannel(channelId);
        showToast(`Канал "${channelName}" удалён`, 'success');

        // Refresh channels
        cachedData.channels = await api.getChannels(currentGuildId);
        displayChannelsList();
        populateChannelSelects();
    } catch (error) {
        showToast('Ошибка удаления канала', 'error');
    }
}

// --- FORM HANDLERS ---
function initForms() {
    // Send message
    document.getElementById('sendMessageForm').addEventListener('submit', handleSendMessage);

    // Delete messages
    document.getElementById('deleteMessagesForm').addEventListener('submit', handleDeleteMessages);

    // Moderation
    document.getElementById('muteForm').addEventListener('submit', handleMute);
    document.getElementById('kickForm').addEventListener('submit', handleKick);
    document.getElementById('banForm').addEventListener('submit', handleBan);

    // Roles
    document.getElementById('assignRoleForm').addEventListener('submit', handleAssignRole);

    // Reaction roles
    document.getElementById('reactionRoleForm').addEventListener('submit', handleCreateReactionRole);

    // Channels
    document.getElementById('createChannelForm').addEventListener('submit', handleCreateChannel);

    // Message type toggle
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

    // Activity filter
    document.getElementById('activityFilter').addEventListener('change', displayActivityFeed);

    // Add first reaction field
    addReactionField();
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
        showToast('Ошибка отправки сообщения', 'error');
    }
}

async function handleDeleteMessages(e) {
    e.preventDefault();

    const channelId = document.getElementById('deleteChannel').value;
    const amount = parseInt(document.getElementById('deleteAmount').value);

    if (!confirm(`Удалить ${amount} сообщений? Это действие нельзя отменить!`)) return;

    try {
        const result = await api.bulkDelete(channelId, amount);
        showToast(`Удалено ${result.deleted} сообщений`, 'success');
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка удаления сообщений', 'error');
    }
}

async function handleMute(e) {
    e.preventDefault();

    const userId = document.getElementById('muteUser').value;
    const duration = parseInt(document.getElementById('muteDuration').value);
    const reason = document.getElementById('muteReason').value;

    try {
        await api.muteUser(currentGuildId, userId, duration, reason);
        const userName = document.getElementById('muteUser').selectedOptions[0].text;
        showToast(`${userName} замучен на ${duration}с`, 'success');
        e.target.reset();
        await displayActivePunishments();
        await displayModerationHistory();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка выдачи мута', 'error');
    }
}

async function handleKick(e) {
    e.preventDefault();

    const userId = document.getElementById('kickUser').value;
    const reason = document.getElementById('kickReason').value;
    const userName = document.getElementById('kickUser').selectedOptions[0].text;

    if (!confirm(`Кикнуть ${userName}?`)) return;

    try {
        await api.kickUser(currentGuildId, userId, reason);
        showToast(`${userName} кикнут`, 'success');
        e.target.reset();

        // Refresh members
        cachedData.members = await api.getMembers(currentGuildId);
        populateMemberSelects();
        updateDashboardStats();
        await displayModerationHistory();
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
    const userName = document.getElementById('banUser').selectedOptions[0].text;

    if (!confirm(`Забанить ${userName}?`)) return;

    try {
        await api.banUser(currentGuildId, userId, reason, deleteDays);
        showToast(`${userName} забанен`, 'success');
        e.target.reset();

        // Refresh members
        cachedData.members = await api.getMembers(currentGuildId);
        populateMemberSelects();
        updateDashboardStats();
        await displayActivePunishments();
        await displayModerationHistory();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка бана', 'error');
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
        document.getElementById('userRolesDisplay').style.display = 'none';

        // Refresh members to update roles
        cachedData.members = await api.getMembers(currentGuildId);
        populateMemberSelects();
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
        document.getElementById('userRolesDisplay').style.display = 'none';

        // Refresh members
        cachedData.members = await api.getMembers(currentGuildId);
        populateMemberSelects();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка удаления роли', 'error');
    }
}

async function handleCreateReactionRole(e) {
    e.preventDefault();

    const channelId = document.getElementById('reactionChannel').value;
    const message = document.getElementById('reactionMessage').value;

    // Get all reaction fields
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

        showToast('Система ролей за реакции создана!', 'success');
        e.target.reset();

        // Clear reaction fields and add one
        document.getElementById('reactionsList').innerHTML = '';
        reactionFieldsCount = 0;
        addReactionField();

        await displayReactionRolesList();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка создания системы', 'error');
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

        // Refresh channels
        cachedData.channels = await api.getChannels(currentGuildId);
        displayChannelsList();
        populateChannelSelects();
        updateDashboardStats();
        await displayActivityFeed();
    } catch (error) {
        showToast('Ошибка создания канала', 'error');
    }
}

// --- HELPERS ---
function setDeleteAmount(amount) {
    document.getElementById('deleteAmount').value = amount;
}

function setMuteDuration(duration) {
    document.getElementById('muteDuration').value = duration;
}

// --- NAVIGATION ---
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item[data-page]');
    const pages = document.querySelectorAll('.page');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const pageName = item.dataset.page;

            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            pages.forEach(page => page.classList.remove('active'));
            document.getElementById(`${pageName}Page`).classList.add('active');

            document.getElementById('pageTitle').textContent = item.querySelector('span').textContent;

            closeMobileMenu();
        });
    });
}

function navigateTo(pageName) {
    const navItem = document.querySelector(`[data-page="${pageName}"]`);
    if (navItem) {
        navItem.click();
    }
}

// --- MOBILE MENU ---
function initMobileMenu() {
    const mobileBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');

    mobileBtn.addEventListener('click', () => {
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
    document.getElementById('sidebar').classList.remove('open');
    document.body.classList.remove('menu-open');
    document.querySelector('.sidebar-overlay')?.remove();
}

// --- AUTO REFRESH ---
function startAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }

    if (!settings.autoRefresh) return;

    autoRefreshInterval = setInterval(async () => {
        if (!currentGuildId) return;

        console.log('🔄 Автообновление данных...');
        showAutoRefreshIndicator();

        try {
            // Refresh all data
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

    console.log(`✅ Автообновление запущено (интервал: ${settings.refreshInterval}с)`);
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
    showToast('Обновление данных...', 'info');

    try {
        await selectGuild(currentGuildId);
        showToast('Данные обновлены!', 'success');
    } catch (error) {
        showToast('Ошибка обновления данных', 'error');
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

    if (currentGuildId) {
        forceRefresh();
    }

    showToast('Кэш очищен', 'success');
}

async function reconnectBot() {
    showLoadingScreen();
    stopAutoRefresh();

    await initializeBot();

    hideLoadingScreen();
    showToast('Бот переподключен', 'success');
}

// --- SETTINGS ---
function saveSettings() {
    settings.autoRefresh = document.getElementById('autoRefreshToggle').checked;
    settings.notifications = document.getElementById('notificationsToggle').checked;
    settings.refreshInterval = parseInt(document.getElementById('refreshInterval').value);

    localStorage.setItem('dashboardSettings', JSON.stringify(settings));

    if (settings.autoRefresh) {
        startAutoRefresh();
    } else {
        stopAutoRefresh();
    }

    showToast('Настройки сохранены', 'success');
}

function loadSettings() {
    const saved = localStorage.getItem('dashboardSettings');
    if (saved) {
        Object.assign(settings, JSON.parse(saved));
    }

    document.getElementById('autoRefreshToggle').checked = settings.autoRefresh;
    document.getElementById('notificationsToggle').checked = settings.notifications;
    document.getElementById('refreshInterval').value = settings.refreshInterval;
}

// --- LOGOUT ---
function logout() {
    if (confirm('Выйти из панели управления?')) {
        localStorage.removeItem('authToken');
        window.location.href = 'login.html';
    }
}

// --- UI HELPERS ---
function showLoadingScreen() {
    document.getElementById('loadingScreen').classList.remove('hidden');
}

function hideLoadingScreen() {
    setTimeout(() => {
        document.getElementById('loadingScreen').classList.add('hidden');
    }, 500);
}

function showAutoRefreshIndicator() {
    document.getElementById('autoRefreshIndicator').classList.add('active');
}

function hideAutoRefreshIndicator() {
    document.getElementById('autoRefreshIndicator').classList.remove('active');
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

console.log('✅ Discord Bot Dashboard готов к работе!');
