import os
import json
import threading
import asyncio
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import discord
from discord.ext import commands
from dotenv import load_dotenv

# --- CONFIG ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN", "MTQ0NzY0ODc5NDg0OTA1MDY4Nw.G-5CcA.szHm3gZfWJBwxPicnldQV2jgpjlYcomRKxMDPg")
ADMIN_PIN = os.getenv("ADMIN_PIN", "110603")
PORT = int(os.getenv("PORT", 5000))

# --- BOT SETUP ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- DATA STORAGE ---
reaction_roles_db = {}
activity_log = []
moderation_log = []
active_punishments = {
    "mutes": {},  # user_id: {guild_id, reason, until, moderator}
    "bans": {}    # user_id: {guild_id, reason, moderator}
}
bot_start_time = None

# Загрузка данных
if os.path.exists("reaction_roles.json"):
    try:
        with open("reaction_roles.json", "r", encoding='utf-8') as f:
            reaction_roles_db = json.load(f)
    except:
        reaction_roles_db = {}

if os.path.exists("activity_log.json"):
    try:
        with open("activity_log.json", "r", encoding='utf-8') as f:
            activity_log = json.load(f)
    except:
        activity_log = []

if os.path.exists("moderation_log.json"):
    try:
        with open("moderation_log.json", "r", encoding='utf-8') as f:
            moderation_log = json.load(f)
    except:
        moderation_log = []

if os.path.exists("active_punishments.json"):
    try:
        with open("active_punishments.json", "r", encoding='utf-8') as f:
            active_punishments = json.load(f)
    except:
        active_punishments = {"mutes": {}, "bans": {}}

# Функции сохранения
def save_rr_db():
    with open("reaction_roles.json", "w", encoding='utf-8') as f:
        json.dump(reaction_roles_db, f, ensure_ascii=False, indent=2)

def save_activity_log():
    with open("activity_log.json", "w", encoding='utf-8') as f:
        json.dump(activity_log[-1000:], f, ensure_ascii=False, indent=2)  # Последние 1000

def save_moderation_log():
    with open("moderation_log.json", "w", encoding='utf-8') as f:
        json.dump(moderation_log[-500:], f, ensure_ascii=False, indent=2)  # Последние 500

def save_punishments():
    with open("active_punishments.json", "w", encoding='utf-8') as f:
        json.dump(active_punishments, f, ensure_ascii=False, indent=2)

# Логирование событий
def log_event(event_type, title, description, icon, color):
    """Логирование событий активности"""
    event = {
        "type": event_type,
        "title": title,
        "description": description,
        "icon": icon,
        "color": color,
        "time": datetime.now().isoformat()
    }
    activity_log.insert(0, event)
    save_activity_log()
    return event

def log_moderation(action, user_name, user_id, reason, moderator, duration=None):
    """Логирование действий модерации"""
    entry = {
        "action": action,
        "user": user_name,
        "user_id": user_id,
        "reason": reason,
        "moderator": moderator,
        "duration": duration,
        "time": datetime.now().isoformat(),
        "icon": {
            "mute": "fas fa-volume-mute",
            "kick": "fas fa-user-slash",
            "ban": "fas fa-ban",
            "unmute": "fas fa-volume-up",
            "unban": "fas fa-user-check"
        }.get(action, "fas fa-shield-alt")
    }
    moderation_log.insert(0, entry)
    save_moderation_log()
    return entry

# --- DISCORD BOT EVENTS ---
@bot.event
async def on_ready():
    global bot_start_time
    bot_start_time = datetime.now()
    print(f'✅ Bot запущен: {bot.user.name} ({bot.user.id})')
    print(f'🌐 Серверов: {len(bot.guilds)}')
    log_event("system", "Бот запущен", f"Бот {bot.user.name} успешно подключен", "fas fa-power-off", "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)")

@bot.event
async def on_member_join(member):
    """Логирование входа участника"""
    log_event("members", "Участник присоединился", 
              f"{member.name} присоединился к серверу {member.guild.name}",
              "fas fa-user-plus", "linear-gradient(135deg, #667eea 0%, #764ba2 100%)")

@bot.event
async def on_member_remove(member):
    """Логирование выхода участника"""
    log_event("members", "Участник покинул сервер",
              f"{member.name} покинул сервер {member.guild.name}",
              "fas fa-user-minus", "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)")

@bot.event
async def on_member_update(before, after):
    """Отслеживание изменений ролей"""
    if before.roles != after.roles:
        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        
        for role in added:
            log_event("roles", "Роль выдана",
                     f"Роль {role.name} выдана пользователю {after.name}",
                     "fas fa-user-tag", "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)")
        
        for role in removed:
            log_event("roles", "Роль забрана",
                     f"Роль {role.name} забрана у пользователя {after.name}",
                     "fas fa-user-minus", "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)")

@bot.event
async def on_guild_channel_create(channel):
    """Логирование создания канала"""
    channel_type = {0: "текстовый", 2: "голосовой", 4: "категория"}.get(channel.type.value, "неизвестный")
    log_event("channels", "Канал создан",
              f"Создан {channel_type} канал: {channel.name}",
              "fas fa-plus", "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)")

@bot.event
async def on_guild_channel_delete(channel):
    """Логирование удаления канала"""
    log_event("channels", "Канал удалён",
              f"Удалён канал: {channel.name}",
              "fas fa-trash", "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)")

@bot.event
async def on_raw_reaction_add(payload):
    """Обработка реакций для ролей"""
    if payload.user_id == bot.user.id:
        return
    
    key = f"{payload.message_id}"
    if key in reaction_roles_db:
        rr_data = reaction_roles_db[key]
        
        # Поддержка множественных реакций
        for reaction in rr_data.get("reactions", []):
            if str(payload.emoji) == reaction["emoji"]:
                guild = bot.get_guild(payload.guild_id)
                if guild:
                    member = guild.get_member(payload.user_id)
                    role = guild.get_role(int(reaction["role_id"]))
                    
                    if member and role:
                        await member.add_roles(role)
                        log_event("roles", "Роль выдана через реакцию",
                                 f"{member.name} получил роль {role.name} через реакцию {payload.emoji}",
                                 "fas fa-smile", "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)")
                break

@bot.event
async def on_raw_reaction_remove(payload):
    """Снятие роли при удалении реакции"""
    key = f"{payload.message_id}"
    if key in reaction_roles_db:
        rr_data = reaction_roles_db[key]
        
        for reaction in rr_data.get("reactions", []):
            if str(payload.emoji) == reaction["emoji"]:
                guild = bot.get_guild(payload.guild_id)
                if guild:
                    member = guild.get_member(payload.user_id)
                    role = guild.get_role(int(reaction["role_id"]))
                    
                    if member and role:
                        await member.remove_roles(role)
                        log_event("roles", "Роль забрана через реакцию",
                                 f"{member.name} потерял роль {role.name} при удалении реакции",
                                 "fas fa-frown", "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)")
                break

# --- FLASK APP ---
app = Flask(__name__, static_folder='.')
CORS(app)

# Middleware для проверки авторизации
def require_auth(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f"Bearer {ADMIN_PIN}":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# --- ROUTES ---

# Главная страница
@app.route('/')
def index():
    return send_from_directory('.', 'login.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

# Авторизация
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    pin = data.get('pin', '')
    
    if pin == ADMIN_PIN:
        return jsonify({"success": True, "token": ADMIN_PIN})
    else:
        return jsonify({"success": False, "error": "Неверный пароль"}), 401

# Информация о боте
@app.route('/api/bot/info', methods=['GET'])
@require_auth
def bot_info():
    uptime = None
    if bot_start_time:
        delta = datetime.now() - bot_start_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime = f"{days}д {hours}ч {minutes}м" if days > 0 else f"{hours}ч {minutes}м"
    
    return jsonify({
        "id": str(bot.user.id) if bot.user else None,
        "username": bot.user.name if bot.user else "Загрузка...",
        "discriminator": bot.user.discriminator if bot.user else "0000",
        "avatar": str(bot.user.avatar.url) if bot.user and bot.user.avatar else None,
        "guilds_count": len(bot.guilds),
        "uptime": uptime
    })

# Список серверов
@app.route('/api/guilds', methods=['GET'])
@require_auth
def get_guilds():
    guilds = [{
        "id": str(g.id),
        "name": g.name,
        "icon": str(g.icon.url) if g.icon else None,
        "member_count": g.member_count
    } for g in bot.guilds]
    return jsonify(guilds)

# Информация о сервере
@app.route('/api/guilds/<guild_id>', methods=['GET'])
@require_auth
def get_guild(guild_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    return jsonify({
        "id": str(guild.id),
        "name": guild.name,
        "icon": str(guild.icon.url) if guild.icon else None,
        "member_count": guild.member_count,
        "owner_id": str(guild.owner_id)
    })

# Участники сервера
@app.route('/api/guilds/<guild_id>/members', methods=['GET'])
@require_auth
def get_members(guild_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    members = [{
        "id": str(m.id),
        "username": m.name,
        "discriminator": m.discriminator,
        "nick": m.nick,
        "avatar": str(m.avatar.url) if m.avatar else None,
        "bot": m.bot,
        "roles": [str(r.id) for r in m.roles if r.name != "@everyone"]
    } for m in guild.members]
    
    return jsonify(members)

# Каналы сервера
@app.route('/api/guilds/<guild_id>/channels', methods=['GET'])
@require_auth
def get_channels(guild_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    channels = [{
        "id": str(c.id),
        "name": c.name,
        "type": c.type.value,
        "position": c.position,
        "topic": getattr(c, 'topic', None)
    } for c in guild.channels]
    
    return jsonify(sorted(channels, key=lambda x: x['position']))

# Роли сервера
@app.route('/api/guilds/<guild_id>/roles', methods=['GET'])
@require_auth
def get_roles(guild_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    roles = [{
        "id": str(r.id),
        "name": r.name,
        "color": r.color.value,
        "position": r.position,
        "members": len(r.members)
    } for r in guild.roles if r.name != "@everyone"]
    
    return jsonify(sorted(roles, key=lambda x: -x['position']))

# Отправка сообщения
@app.route('/api/channels/<channel_id>/messages', methods=['POST'])
@require_auth
def send_message(channel_id):
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({"error": "Канал не найден"}), 404
    
    data = request.json
    content = data.get('content')
    embed_data = data.get('embed')
    
    async def send():
        if embed_data:
            embed = discord.Embed(
                title=embed_data.get('title'),
                description=embed_data.get('description'),
                color=embed_data.get('color', 0x5865F2)
            )
            msg = await channel.send(embed=embed)
        else:
            msg = await channel.send(content)
        
        log_event("messages", "Сообщение отправлено",
                 f"Сообщение отправлено в #{channel.name}",
                 "fas fa-paper-plane", "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)")
        return msg
    
    future = asyncio.run_coroutine_threadsafe(send(), bot.loop)
    msg = future.result(timeout=10)
    
    return jsonify({"id": str(msg.id), "success": True})

# Массовое удаление сообщений
@app.route('/api/channels/<channel_id>/messages/bulk-delete', methods=['POST'])
@require_auth
def bulk_delete(channel_id):
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({"error": "Канал не найден"}), 404
    
    data = request.json
    limit = data.get('limit', 10)
    
    async def delete():
        deleted = await channel.purge(limit=limit)
        log_event("messages", "Сообщения удалены",
                 f"Удалено {len(deleted)} сообщений в #{channel.name}",
                 "fas fa-trash", "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)")
        return len(deleted)
    
    future = asyncio.run_coroutine_threadsafe(delete(), bot.loop)
    count = future.result(timeout=30)
    
    return jsonify({"deleted": count, "success": True})

# Мут участника
@app.route('/api/guilds/<guild_id>/members/<user_id>/timeout', methods=['POST'])
@require_auth
def timeout_member(guild_id, user_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    member = guild.get_member(int(user_id))
    if not member:
        return jsonify({"error": "Участник не найден"}), 404
    
    data = request.json
    duration = data.get('duration', 60)  # секунды
    reason = data.get('reason', 'Нарушение правил')
    
    async def mute():
        until = discord.utils.utcnow() + timedelta(seconds=duration)
        await member.timeout(until, reason=reason)
        
        # Сохраняем в активные наказания
        active_punishments["mutes"][str(user_id)] = {
            "guild_id": str(guild_id),
            "reason": reason,
            "until": until.isoformat(),
            "moderator": "Admin Panel",
            "member_name": member.name
        }
        save_punishments()
        
        log_moderation("mute", member.name, str(user_id), reason, "Admin Panel", f"{duration}с")
        log_event("moderation", "Мут выдан",
                 f"{member.name} замучен на {duration}с",
                 "fas fa-volume-mute", "linear-gradient(135deg, #faa81a 0%, #f5576c 100%)")
    
    future = asyncio.run_coroutine_threadsafe(mute(), bot.loop)
    future.result(timeout=10)
    
    return jsonify({"success": True})

# Снятие мута
@app.route('/api/guilds/<guild_id>/members/<user_id>/untimeout', methods=['POST'])
@require_auth
def untimeout_member(guild_id, user_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    member = guild.get_member(int(user_id))
    if not member:
        return jsonify({"error": "Участник не найден"}), 404
    
    async def unmute():
        await member.timeout(None)
        
        # Удаляем из активных наказаний
        if str(user_id) in active_punishments["mutes"]:
            del active_punishments["mutes"][str(user_id)]
            save_punishments()
        
        log_moderation("unmute", member.name, str(user_id), "Мут снят", "Admin Panel")
        log_event("moderation", "Мут снят",
                 f"С {member.name} снят мут",
                 "fas fa-volume-up", "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)")
    
    future = asyncio.run_coroutine_threadsafe(unmute(), bot.loop)
    future.result(timeout=10)
    
    return jsonify({"success": True})

# Кик участника
@app.route('/api/guilds/<guild_id>/members/<user_id>/kick', methods=['POST'])
@require_auth
def kick_member(guild_id, user_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    member = guild.get_member(int(user_id))
    if not member:
        return jsonify({"error": "Участник не найден"}), 404
    
    data = request.json
    reason = data.get('reason', 'Нарушение правил')
    
    async def kick():
        member_name = member.name
        await member.kick(reason=reason)
        log_moderation("kick", member_name, str(user_id), reason, "Admin Panel")
        log_event("moderation", "Кик выполнен",
                 f"{member_name} кикнут с сервера",
                 "fas fa-user-slash", "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)")
    
    future = asyncio.run_coroutine_threadsafe(kick(), bot.loop)
    future.result(timeout=10)
    
    return jsonify({"success": True})

# Бан участника
@app.route('/api/guilds/<guild_id>/members/<user_id>/ban', methods=['POST'])
@require_auth
def ban_member(guild_id, user_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    data = request.json
    reason = data.get('reason', 'Нарушение правил')
    delete_days = data.get('delete_message_days', 0)
    
    async def ban():
        user = await bot.fetch_user(int(user_id))
        await guild.ban(user, reason=reason, delete_message_days=delete_days)
        
        # Сохраняем в активные наказания
        active_punishments["bans"][str(user_id)] = {
            "guild_id": str(guild_id),
            "reason": reason,
            "moderator": "Admin Panel",
            "user_name": user.name
        }
        save_punishments()
        
        log_moderation("ban", user.name, str(user_id), reason, "Admin Panel")
        log_event("moderation", "Бан выполнен",
                 f"{user.name} забанен",
                 "fas fa-ban", "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)")
    
    future = asyncio.run_coroutine_threadsafe(ban(), bot.loop)
    future.result(timeout=10)
    
    return jsonify({"success": True})

# Разбан участника
@app.route('/api/guilds/<guild_id>/bans/<user_id>', methods=['DELETE'])
@require_auth
def unban_member(guild_id, user_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    async def unban():
        user = await bot.fetch_user(int(user_id))
        await guild.unban(user)
        
        # Удаляем из активных наказаний
        if str(user_id) in active_punishments["bans"]:
            del active_punishments["bans"][str(user_id)]
            save_punishments()
        
        log_moderation("unban", user.name, str(user_id), "Бан снят", "Admin Panel")
        log_event("moderation", "Бан снят",
                 f"С {user.name} снят бан",
                 "fas fa-user-check", "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)")
    
    future = asyncio.run_coroutine_threadsafe(unban(), bot.loop)
    future.result(timeout=10)
    
    return jsonify({"success": True})

# Получить активные наказания
@app.route('/api/guilds/<guild_id>/punishments', methods=['GET'])
@require_auth
def get_punishments(guild_id):
    guild_mutes = {k: v for k, v in active_punishments["mutes"].items() if v["guild_id"] == str(guild_id)}
    guild_bans = {k: v for k, v in active_punishments["bans"].items() if v["guild_id"] == str(guild_id)}
    
    return jsonify({
        "mutes": guild_mutes,
        "bans": guild_bans
    })

# Выдача роли
@app.route('/api/guilds/<guild_id>/members/<user_id>/roles/<role_id>', methods=['PUT'])
@require_auth
def add_role(guild_id, user_id, role_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    member = guild.get_member(int(user_id))
    role = guild.get_role(int(role_id))
    
    if not member or not role:
        return jsonify({"error": "Участник или роль не найдены"}), 404
    
    async def add():
        await member.add_roles(role)
        log_event("roles", "Роль выдана",
                 f"Роль {role.name} выдана {member.name}",
                 "fas fa-user-tag", "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)")
    
    future = asyncio.run_coroutine_threadsafe(add(), bot.loop)
    future.result(timeout=10)
    
    return jsonify({"success": True})

# Забирание роли
@app.route('/api/guilds/<guild_id>/members/<user_id>/roles/<role_id>', methods=['DELETE'])
@require_auth
def remove_role(guild_id, user_id, role_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    member = guild.get_member(int(user_id))
    role = guild.get_role(int(role_id))
    
    if not member or not role:
        return jsonify({"error": "Участник или роль не найдены"}), 404
    
    async def remove():
        await member.remove_roles(role)
        log_event("roles", "Роль забрана",
                 f"Роль {role.name} забрана у {member.name}",
                 "fas fa-user-minus", "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)")
    
    future = asyncio.run_coroutine_threadsafe(remove(), bot.loop)
    future.result(timeout=10)
    
    return jsonify({"success": True})

# Создание канала
@app.route('/api/guilds/<guild_id>/channels', methods=['POST'])
@require_auth
def create_channel(guild_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    data = request.json
    name = data.get('name')
    channel_type = discord.ChannelType(data.get('type', 0))
    topic = data.get('topic')
    
    async def create():
        if channel_type == discord.ChannelType.text:
            channel = await guild.create_text_channel(name, topic=topic)
        elif channel_type == discord.ChannelType.voice:
            channel = await guild.create_voice_channel(name)
        elif channel_type == discord.ChannelType.category:
            channel = await guild.create_category(name)
        else:
            return None
        
        log_event("channels", "Канал создан",
                 f"Создан канал {channel.name}",
                 "fas fa-plus", "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)")
        return channel
    
    future = asyncio.run_coroutine_threadsafe(create(), bot.loop)
    channel = future.result(timeout=10)
    
    if channel:
        return jsonify({"id": str(channel.id), "success": True})
    else:
        return jsonify({"error": "Не удалось создать канал"}), 400

# Удаление канала
@app.route('/api/channels/<channel_id>', methods=['DELETE'])
@require_auth
def delete_channel(channel_id):
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({"error": "Канал не найден"}), 404
    
    async def delete():
        channel_name = channel.name
        await channel.delete()
        log_event("channels", "Канал удалён",
                 f"Канал {channel_name} удалён",
                 "fas fa-trash", "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)")
    
    future = asyncio.run_coroutine_threadsafe(delete(), bot.loop)
    future.result(timeout=10)
    
    return jsonify({"success": True})

# Создание роли за реакцию (множественные)
@app.route('/api/guilds/<guild_id>/reaction-roles', methods=['POST'])
@require_auth
def create_reaction_role(guild_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    data = request.json
    channel_id = data.get('channel_id')
    message_text = data.get('message')
    reactions = data.get('reactions', [])  # [{emoji, role_id}, ...]
    
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({"error": "Канал не найден"}), 404
    
    async def create():
        # Отправка сообщения
        message = await channel.send(message_text)
        
        # Добавление реакций
        for reaction in reactions:
            await message.add_reaction(reaction['emoji'])
        
        # Сохранение в БД
        reaction_roles_db[str(message.id)] = {
            "channel_id": str(channel_id),
            "guild_id": str(guild_id),
            "message": message_text,
            "reactions": reactions
        }
        save_rr_db()
        
        log_event("roles", "Система ролей за реакции создана",
                 f"Создано {len(reactions)} реакций в #{channel.name}",
                 "fas fa-smile", "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)")
        
        return message
    
    future = asyncio.run_coroutine_threadsafe(create(), bot.loop)
    message = future.result(timeout=10)
    
    return jsonify({"message_id": str(message.id), "success": True})

# Получить роли за реакции
@app.route('/api/guilds/<guild_id>/reaction-roles', methods=['GET'])
@require_auth
def get_reaction_roles(guild_id):
    guild_rr = {k: v for k, v in reaction_roles_db.items() if v.get("guild_id") == str(guild_id)}
    return jsonify(guild_rr)

# Удалить роль за реакцию
@app.route('/api/reaction-roles/<message_id>', methods=['DELETE'])
@require_auth
def delete_reaction_role(message_id):
    if message_id in reaction_roles_db:
        del reaction_roles_db[message_id]
        save_rr_db()
        return jsonify({"success": True})
    return jsonify({"error": "Не найдено"}), 404

# Лента активности
@app.route('/api/activity', methods=['GET'])
@require_auth
def get_activity():
    limit = request.args.get('limit', 100, type=int)
    event_type = request.args.get('type', 'all')
    
    if event_type == 'all':
        return jsonify(activity_log[:limit])
    else:
        filtered = [e for e in activity_log if e.get('type') == event_type]
        return jsonify(filtered[:limit])

# История модерации
@app.route('/api/moderation/history', methods=['GET'])
@require_auth
def get_moderation_history():
    limit = request.args.get('limit', 50, type=int)
    return jsonify(moderation_log[:limit])

# --- START SERVER ---
def run_flask():
    app.run(host='0.0.0.0', port=PORT, debug=False)

def run_bot():
    bot.run(TOKEN)

if __name__ == '__main__':
    print("🚀 Запуск Discord Bot Dashboard...")
    print(f"📌 Admin PIN: {ADMIN_PIN}")
    print(f"🌐 Flask Port: {PORT}")
    
    # Запуск бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Ждем пока бот подключится
    import time
    time.sleep(5)
    
    # Запуск Flask
    print("✅ Flask сервер запускается...")
    run_flask()
