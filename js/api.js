// API Module for Discord Bot Dashboard

class API {
    constructor() {
        this.baseURL = window.location.origin;
        this.token = localStorage.getItem('authToken');
        this.checkSession();
    }

    // Проверка срока действия сессии
    checkSession() {
        const expiry = localStorage.getItem('sessionExpiry');
        if (!expiry) return; // Если нет срока, полагаемся на ответ сервера 401

        const now = new Date().getTime();
        if (now > parseInt(expiry)) {
            console.warn('Сессия истекла');
            this.logout();
        }
    }

    logout() {
        localStorage.removeItem('authToken');
        localStorage.removeItem('sessionExpiry');
        window.location.href = 'login.html';
    }

    getHeaders() {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.token}`
        };
    }

    async request(endpoint, method = 'GET', body = null) {
        // Проверяем сессию перед каждым запросом
        this.checkSession();

        const options = {
            method,
            headers: this.getHeaders()
        };

        if (body) {
            options.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, options);
            
            if (response.status === 401) {
                // Unauthorized - redirect to login
                this.logout();
                return null;
            }

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            if (response.status === 204) {
                return { success: true };
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${method} ${endpoint}]:`, error);
            throw error;
        }
    }

    // Остальные методы API остаются без изменений
    // (Auth, Bot Info, Guilds, Members, Channels и т.д. - копируй их из старого api.js)
    
    // Auth (Login используется только для получения токена, проверка в login.html)
    async login(pin) {
        const response = await fetch(`${this.baseURL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin })
        });
        return await response.json();
    }

    // Bot Info
    async getBotInfo() {
        return await this.request('/api/bot/info');
    }

    // Guilds
    async getGuilds() {
        return await this.request('/api/guilds');
    }

    async getGuild(guildId) {
        return await this.request(`/api/guilds/${guildId}`);
    }

    // Members
    async getMembers(guildId) {
        return await this.request(`/api/guilds/${guildId}/members`);
    }

    // Channels
    async getChannels(guildId) {
        return await this.request(`/api/guilds/${guildId}/channels`);
    }

    async createChannel(guildId, data) {
        return await this.request(`/api/guilds/${guildId}/channels`, 'POST', data);
    }

    async deleteChannel(channelId) {
        return await this.request(`/api/channels/${channelId}`, 'DELETE');
    }

    // Roles
    async getRoles(guildId) {
        return await this.request(`/api/guilds/${guildId}/roles`);
    }

    async addRole(guildId, userId, roleId) {
        return await this.request(`/api/guilds/${guildId}/members/${userId}/roles/${roleId}`, 'PUT');
    }

    async removeRole(guildId, userId, roleId) {
        return await this.request(`/api/guilds/${guildId}/members/${userId}/roles/${roleId}`, 'DELETE');
    }

    // Messages
    async sendMessage(channelId, data) {
        return await this.request(`/api/channels/${channelId}/messages`, 'POST', data);
    }

    async bulkDelete(channelId, limit) {
        return await this.request(`/api/channels/${channelId}/messages/bulk-delete`, 'POST', { limit });
    }

    // Moderation
    async muteUser(guildId, userId, duration, reason) {
        return await this.request(`/api/guilds/${guildId}/members/${userId}/timeout`, 'POST', { duration, reason });
    }

    async unmuteUser(guildId, userId) {
        return await this.request(`/api/guilds/${guildId}/members/${userId}/untimeout`, 'POST');
    }

    async kickUser(guildId, userId, reason) {
        return await this.request(`/api/guilds/${guildId}/members/${userId}/kick`, 'POST', { reason });
    }

    async banUser(guildId, userId, reason, deleteMessageDays = 0) {
        return await this.request(`/api/guilds/${guildId}/members/${userId}/ban`, 'POST', { 
            reason, 
            delete_message_days: deleteMessageDays 
        });
    }

    async unbanUser(guildId, userId) {
        return await this.request(`/api/guilds/${guildId}/bans/${userId}`, 'DELETE');
    }

    async getPunishments(guildId) {
        return await this.request(`/api/guilds/${guildId}/punishments`);
    }

    // Reaction Roles
    async createReactionRole(guildId, data) {
        return await this.request(`/api/guilds/${guildId}/reaction-roles`, 'POST', data);
    }

    async getReactionRoles(guildId) {
        return await this.request(`/api/guilds/${guildId}/reaction-roles`);
    }

    async deleteReactionRole(messageId) {
        return await this.request(`/api/reaction-roles/${messageId}`, 'DELETE');
    }

    // Activity
    async getActivity(type = 'all', limit = 100) {
        return await this.request(`/api/activity?type=${type}&limit=${limit}`);
    }

    // Moderation History
    async getModerationHistory(limit = 50) {
        return await this.request(`/api/moderation/history?limit=${limit}`);
    }
}

// Create global API instance
window.api = new API();