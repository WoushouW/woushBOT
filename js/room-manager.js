// Room Manager - Специальный интерфейс для менеджера комнат
let currentGuildId = null;
let selectedChannelId = null;
let selectedMessageId = null;
let selectedUserId = null;
let selectedMessageText = '';
let cachedChannels = [];
const baseURL = window.location.origin;
let authToken = null;

// Проверка авторизации при загрузке
document.addEventListener('DOMContentLoaded', async () => {
    authToken = localStorage.getItem('authToken');
    const userRole = localStorage.getItem('userRole');
    const sessionExpiry = localStorage.getItem('sessionExpiry');
    
    // Проверяем сессию
    if (!authToken || !sessionExpiry || new Date().getTime() > parseInt(sessionExpiry)) {
        // Сессия истекла или нет токена
        localStorage.clear();
        window.location.href = 'login.html';
        return;
    }
    
    // Проверяем что это именно room_manager
    if (userRole !== 'room_manager') {
        console.warn('⚠️ Не роль room_manager, перенаправляем на основную панель');
        window.location.href = 'index.html';
        return;
    }
    
    console.log('🚀 Room Manager загружается...');
    await initializeManager();
});

async function initializeManager() {
    try {
        console.log('🔌 Подключение к боту...');
        
        // Загружаем серверы
        const guilds = await apiRequest('/api/guilds');
        console.log('✅ Серверы загружены:', guilds.length);
        
        populateServerSelect(guilds);
        
        if (guilds.length > 0) {
            await selectGuild(guilds[0].id);
        } else {
            showToast('Бот не добавлен ни на один сервер', 'error');
        }
        
        showToast('Подключение успешно!', 'success');
    } catch (error) {
        console.error('❌ Ошибка инициализации:', error);
        showToast('Не удалось подключиться к боту', 'error');
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
    
    if (guilds.length > 0) {
        select.value = guilds[0].id;
    }
    
    select.addEventListener('change', async (e) => {
        if (e.target.value) {
            await selectGuild(e.target.value);
        }
    });
}

async function selectGuild(guildId) {
    try {
        currentGuildId = guildId;
        console.log('🎯 Выбран сервер:', guildId);
        
        // Загружаем каналы
        const channels = await apiRequest(`/api/guilds/${guildId}/channels`);
        cachedChannels = channels;
        
        console.log('✅ Загружено:', channels.length, 'каналов');
        
        // Отображаем список каналов
        displayChannelsList(channels);
        
        // Загружаем активные комнаты
        await loadActiveRooms();
        
        showToast('Сервер загружен', 'success');
    } catch (error) {
        console.error('❌ Ошибка загрузки сервера:', error);
        showToast('Ошибка загрузки данных сервера', 'error');
    }
}

function displayChannelsList(channels) {
    const container = document.getElementById('channelsList');
    
    // Только текстовые каналы
    const textChannels = channels.filter(ch => ch.type === 0);
    
    if (textChannels.length === 0) {
        container.innerHTML = '<div class="empty-state">Нет доступных каналов</div>';
        return;
    }
    
    let html = '';
    textChannels.forEach(channel => {
        html += `
            <div class="channel-item" onclick="loadChannelMessages('${channel.id}')">
                <span style="font-size: 18px;">#</span>
                <span>${escapeHtml(channel.name)}</span>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

async function loadChannelMessages(channelId) {
    try {
        selectedChannelId = channelId;
        const channel = cachedChannels.find(c => c.id === channelId);
        
        console.log('📨 Загрузка сообщений из канала:', channel ? channel.name : channelId);
        
        const messagesList = document.getElementById('messagesList');
        messagesList.style.display = 'block';
        messagesList.innerHTML = '<div class="empty-state">Загрузка сообщений...</div>';
        
        // Удаляем selection с других каналов
        document.querySelectorAll('.channel-item').forEach(item => {
            item.classList.remove('selected');
        });
        event.target.closest('.channel-item').classList.add('selected');
        
        const messages = await apiRequest(`/api/channels/${channelId}/messages?limit=50`);
        
        if (!messages || messages.length === 0) {
            messagesList.innerHTML = '<div class="empty-state">В канале нет сообщений</div>';
            return;
        }
        
        displayMessages(messages);
        
    } catch (error) {
        console.error('❌ Ошибка загрузки сообщений:', error);
        const messagesList = document.getElementById('messagesList');
        messagesList.innerHTML = '<div class="empty-state">Ошибка загрузки сообщений</div>';
    }
}

function displayMessages(messages) {
    const container = document.getElementById('messagesList');
    
    let html = '';
    messages.forEach((msg, index) => {
        const timestamp = new Date(msg.timestamp).toLocaleString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        let authorName = 'Неизвестный';
        let authorId = null;
        
        if (msg.author) {
            if (typeof msg.author === 'string') {
                authorName = msg.author;
            } else if (typeof msg.author === 'object') {
                authorName = msg.author.username || msg.author.name || 'Неизвестный';
                authorId = msg.author.id || msg.author_id;
            }
        }
        
        if (!authorId && msg.author_id) {
            authorId = msg.author_id;
        }
        
        const messageContent = escapeHtml(msg.content || '').substring(0, 200);
        
        html += `
            <div class="message-item" data-message-id="${msg.id}" data-author-id="${authorId || ''}" data-content="${escapeHtml(msg.content || '')}" onclick="selectMessage(this)">
                <div class="message-author">${escapeHtml(authorName)}</div>
                <div class="message-content">${messageContent}${msg.content && msg.content.length > 200 ? '...' : ''}</div>
                <div class="message-time">${timestamp}</div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function selectMessage(element) {
    selectedMessageId = element.getAttribute('data-message-id');
    selectedUserId = element.getAttribute('data-author-id');
    selectedMessageText = element.getAttribute('data-content');
    
    console.log('✅ Выбрано сообщение:', {
        messageId: selectedMessageId,
        userId: selectedUserId,
        text: selectedMessageText
    });
    
    // Показываем форму создания комнаты
    document.getElementById('roomForm').style.display = 'block';
    document.getElementById('selectedMessageId').value = selectedMessageId;
    document.getElementById('selectedUserId').value = selectedUserId;
    document.getElementById('selectedChannelId').value = selectedChannelId;
    document.getElementById('messageText').value = selectedMessageText;
    
    // Удаляем selection с других сообщений
    document.querySelectorAll('.message-item').forEach(item => {
        item.style.background = '#f9f9f9';
    });
    element.style.background = '#e8ebff';
    
    showToast('Сообщение выбрано. Заполните форму', 'info');
}

function cancelForm() {
    document.getElementById('roomForm').style.display = 'none';
    document.getElementById('roomName').value = '';
    document.getElementById('roomDuration').value = '60';
    document.getElementById('roomLimit').value = '5';
    
    // Снимаем выделение
    document.querySelectorAll('.message-item').forEach(item => {
        item.style.background = '#f9f9f9';
    });
}

async function createRoom() {
    const roomName = document.getElementById('roomName').value.trim();
    const duration = parseInt(document.getElementById('roomDuration').value);
    const userLimit = parseInt(document.getElementById('roomLimit').value);
    const messageId = document.getElementById('selectedMessageId').value;
    const userId = document.getElementById('selectedUserId').value;
    const channelId = document.getElementById('selectedChannelId').value;
    const messageText = document.getElementById('messageText').value;
    
    // Валидация
    if (!roomName) {
        showToast('Введите название комнаты', 'error');
        return;
    }
    
    if (duration < 1 || duration > 90) {
        showToast('Продолжительность должна быть от 1 до 90 минут', 'error');
        return;
    }
    
    if (userLimit < 1 || userLimit > 50) {
        showToast('Лимит участников должен быть от 1 до 50', 'error');
        return;
    }
    
    if (!messageId || !userId) {
        showToast('Выберите сообщение из списка', 'error');
        return;
    }
    
    try {
        showToast('Создание комнаты...', 'info');
        
        const response = await apiRequest(`/api/guilds/${currentGuildId}/temp-rooms`, 'POST', {
            room_name: roomName,
            duration_minutes: duration,
            user_limit: userLimit,
            message_id: messageId,
            user_id: userId,
            channel_id: channelId,
            message_text: messageText
        });
        
        console.log('✅ Комната создана:', response);
        showToast('Комната успешно создана!', 'success');
        
        // Сбрасываем форму
        cancelForm();
        
        // Обновляем список активных комнат
        await loadActiveRooms();
        
    } catch (error) {
        console.error('❌ Ошибка создания комнаты:', error);
        showToast(error.message || 'Ошибка создания комнаты', 'error');
    }
}

async function loadActiveRooms() {
    const container = document.getElementById('activeRoomsList');
    
    try {
        container.innerHTML = '<div class="empty-state">Загрузка...</div>';
        
        const rooms = await apiRequest(`/api/guilds/${currentGuildId}/temp-rooms`);
        
        console.log('📊 Загружено комнат:', rooms);
        console.log('📊 Тип данных:', Array.isArray(rooms) ? 'Array' : typeof rooms);
        
        if (!rooms || rooms.length === 0) {
            container.innerHTML = '<div class="empty-state">Нет активных комнат</div>';
            return;
        }
        
        let html = '';
        
        rooms.forEach((room, idx) => {
            const channelId = room.channel_id;
            console.log(`🔍 Комната #${idx}: ID=${channelId}, Name=${room.room_name}`);
            const expiresAt = new Date(room.expires_at);
            const now = new Date();
            const remainingMs = expiresAt - now;
            const remainingMin = Math.max(0, Math.floor(remainingMs / 60000));
            const remainingSec = Math.max(0, Math.floor((remainingMs % 60000) / 1000));
            
            const totalMs = room.duration * 60 * 1000;
            const progress = Math.max(0, Math.min(100, (remainingMs / totalMs) * 100));
            
            let progressColor = '#43b581';
            if (remainingMin < 2) progressColor = '#f04747';
            else if (remainingMin < 5) progressColor = '#faa61a';
            
            html += `
                <div class="room-card">
                    <div class="room-header">
                        <div class="room-name">🔊 ${escapeHtml(room.room_name)}</div>
                        <button class="btn btn-danger" onclick="deleteRoom('${channelId}', '${room.role_id}')" title="Удалить комнату">
                            🗑️ Удалить
                        </button>
                    </div>
                    <div class="room-info">
                        <div class="room-info-item">
                            <span class="room-info-label">👤 Владелец:</span>
                            <span class="room-info-value">${escapeHtml(room.owner_name)}</span>
                        </div>
                        <div class="room-info-item">
                            <span class="room-info-label">👥 Лимит:</span>
                            <span class="room-info-value">${room.user_limit} чел.</span>
                        </div>
                        <div class="room-info-item">
                            <span class="room-info-label">⏰ Осталось:</span>
                            <span class="room-info-value timer-display">${remainingMin}:${remainingSec.toString().padStart(2, '0')}</span>
                        </div>
                        <div class="room-info-item">
                            <span class="room-info-label">🆔 ID канала:</span>
                            <span class="room-info-value" style="font-family: monospace; font-weight: bold; color: #00d4ff;">${channelId}</span>
                        </div>
                    </div>
                    <div class="room-progress">
                        <div class="room-progress-bar" style="width: ${progress}%; background: ${progressColor};"></div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        startTimerUpdates(rooms);
        
    } catch (error) {
        console.error('❌ Ошибка загрузки комнат:', error);
        container.innerHTML = '<div class="empty-state">Ошибка загрузки комнат</div>';
    }
}

let timerInterval = null;

function startTimerUpdates(rooms) {
    if (timerInterval) clearInterval(timerInterval);
    
    timerInterval = setInterval(() => {
        const timerDisplays = document.querySelectorAll('.timer-display');
        let hasExpired = false;
        
        rooms.forEach((room, index) => {
            const expiresAt = new Date(room.expires_at);
            const now = new Date();
            const remainingMs = expiresAt - now;
            
            if (remainingMs <= 0) {
                hasExpired = true;
                return;
            }
            
            const remainingMin = Math.floor(remainingMs / 60000);
            const remainingSec = Math.floor((remainingMs % 60000) / 1000);
            
            if (timerDisplays[index]) {
                timerDisplays[index].textContent = `${remainingMin}:${remainingSec.toString().padStart(2, '0')}`;
            }
        });
        
        if (hasExpired) {
            loadActiveRooms();
        }
    }, 1000);
}

async function deleteRoom(channelId, roleId) {
    if (!confirm('Удалить эту комнату?')) {
        return;
    }
    
    try {
        showToast('Удаление комнаты...', 'info');
        
        // DELETE запрос без body (только URL parameters)
        await apiRequest(`/api/guilds/${currentGuildId}/temp-rooms/${channelId}?role_id=${roleId}`, 'DELETE');
        
        showToast('Комната успешно удалена', 'success');
        
        // Обновляем список
        await loadActiveRooms();
        
    } catch (error) {
        console.error('❌ Ошибка удаления комнаты:', error);
        showToast(error.message || 'Ошибка удаления комнаты', 'error');
    }
}

// Утилиты
async function apiRequest(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
        }
    };
    
    if (body) {
        options.body = JSON.stringify(body);
    }
    
    const response = await fetch(`${baseURL}${endpoint}`, options);
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || 'Ошибка запроса');
    }
    
    return response.json();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function logout() {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('sessionExpiry');
    window.location.href = 'login.html';
}
