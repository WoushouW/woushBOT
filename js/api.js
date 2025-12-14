// API Module for Discord Bot Dashboard
class API {
    constructor() {
        this.baseURL = window.location.origin;
        this.token = localStorage.getItem('authToken');
        this.checkSession();
    }

    checkSession() {
        const expiry = localStorage.getItem('sessionExpiry');
        if (!expiry) return;
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
        this.checkSession();
        const options = { method, headers: this.getHeaders() };
        if (body) options.body = JSON.stringify(body);

        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, options);
            if (response.status === 401) {
                this.logout();
                return null;
            }
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                const errorMsg = error.error || `HTTP ${response.status}`;
                const err = new Error(errorMsg);
                err.status = response.status;  // Сохраняем код статуса
                throw err;
            }
            if (response.status === 204) return { success: true };
            return await response.json();
        } catch (error) {
            console.error(`API Error [${method} ${endpoint}]:`, error);
            throw error;
        }
    }

    async login(pin) {
        const response = await fetch(`${this.baseURL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin })
        });
        return await response.json();
    }

    async getBotInfo() { return await this.request('/api/bot/info'); }
    async getGuilds() { return await this.request('/api/guilds'); }
    async getGuild(guildId) { return await this.request(`/api/guilds/${guildId}`); }
    async getMembers(guildId) { return await this.request(`/api/guilds/${guildId}/members`); }
    async getChannels(guildId) { return await this.request(`/api/guilds/${guildId}/channels`); }
    async createChannel(guildId, data) { return await this.request(`/api/guilds/${guildId}/channels`, 'POST', data); }
    async deleteChannel(channelId) { return await this.request(`/api/channels/${channelId}`, 'DELETE'); }
    async getRoles(guildId) { return await this.request(`/api/guilds/${guildId}/roles`); }
    async deleteRole(roleId) { return await this.request(`/api/roles/${roleId}`, 'DELETE'); }
    async addRole(guildId, userId, roleId) { return await this.request(`/api/guilds/${guildId}/members/${userId}/roles/${roleId}`, 'PUT'); }
    async removeRole(guildId, userId, roleId) { return await this.request(`/api/guilds/${guildId}/members/${userId}/roles/${roleId}`, 'DELETE'); }
    async sendMessage(channelId, data) { return await this.request(`/api/channels/${channelId}/messages`, 'POST', data); }
    async bulkDelete(channelId, limit) { return await this.request(`/api/channels/${channelId}/messages/bulk-delete`, 'POST', { limit }); }
    async muteUser(guildId, userId, duration, reason, logChannelId) { return await this.request(`/api/guilds/${guildId}/members/${userId}/timeout`, 'POST', { duration, reason, log_channel_id: logChannelId }); }
    async unmuteUser(guildId, userId) { return await this.request(`/api/guilds/${guildId}/members/${userId}/untimeout`, 'POST'); }
    async kickUser(guildId, userId, reason, logChannelId) { return await this.request(`/api/guilds/${guildId}/members/${userId}/kick`, 'POST', { reason, log_channel_id: logChannelId }); }
    async banUser(guildId, userId, reason, deleteMessageDays = 0, logChannelId) { return await this.request(`/api/guilds/${guildId}/members/${userId}/ban`, 'POST', { reason, delete_message_days: deleteMessageDays, log_channel_id: logChannelId }); }
    async unbanUser(guildId, userId) { return await this.request(`/api/guilds/${guildId}/bans/${userId}`, 'DELETE'); }
    async getPunishments(guildId) { return await this.request(`/api/guilds/${guildId}/punishments`); }
    async createReactionRole(guildId, data) { return await this.request(`/api/guilds/${guildId}/reaction-roles`, 'POST', data); }
    async getReactionRoles(guildId) { return await this.request(`/api/guilds/${guildId}/reaction-roles`); }
    async updateReactionRole(messageId, data) { return await this.request(`/api/reaction-roles/${messageId}`, 'PUT', data); }
    async deleteReactionRole(messageId) { return await this.request(`/api/reaction-roles/${messageId}`, 'DELETE'); }
    // Welcome system
    async createWelcome(guildId, data) { return await this.request(`/api/guilds/${guildId}/welcomes`, 'POST', data); }
    async getWelcomes(guildId) { return await this.request(`/api/guilds/${guildId}/welcomes`); }
    async deleteWelcome(messageId) { return await this.request(`/api/welcomes/${messageId}`, 'DELETE'); }
    async getActivity(type = 'all', limit = 100) { return await this.request(`/api/activity?type=${type}&limit=${limit}`); }
    async getModerationHistory(limit = 50) { return await this.request(`/api/moderation/history?limit=${limit}`); }
    async warnUser(guildId, userId, reason, logChannelId) { 
        return await this.request(`/api/guilds/${guildId}/members/${userId}/warn`, 'POST', { 
            reason, 
            log_channel_id: logChannelId 
        }); 
    }
    async getUserWarnings(guildId, userId) { 
        return await this.request(`/api/guilds/${guildId}/members/${userId}/warnings`); 
    }
    async clearWarnings(guildId, userId, logChannelId = null) {
        const body = logChannelId ? { log_channel_id: logChannelId } : {};
        return await this.request(`/api/guilds/${guildId}/members/${userId}/warnings`, 'DELETE', body);
    }
    async getGuildFull(guildId) {
        return await this.request(`/api/guilds/${guildId}/full`);
    }
    async getUserInfo(guildId, userId) {
        return await this.request(`/api/guilds/${guildId}/members/${userId}/info`);
    }
}

window.api = new API();
