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
TOKEN = os.getenv("DISCORD_TOKEN")
PIN = os.getenv("ADMIN_PIN")
# Render выдает порт через переменную окружения PORT
PORT = int(os.getenv("PORT", 5000))

# --- BOT SETUP ---
intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

reaction_roles_db = {}
activity_log = []
moderation_log = []

# Примечание: На Render бесплатном тарифе файлы json сбрасываются при перезагрузке.
# Для сохранения данных навсегда нужна база данных (MongoDB/PostgreSQL).
if os.path.exists("reaction_roles.json"):
    try:
        with open("reaction_roles.json", "r", encoding='utf-8') as f:
            reaction_roles_db = json.load(f)
    except: reaction_roles_db = {}

def save_rr_db():
    with open("reaction_roles.json", "w", encoding='utf-8') as f:
        json.dump(reaction_roles_db, f, ensure_ascii=False)

def log_event(action, details, icon="activity", type="general"):
    event = {
        "action": action,
        "details": details,
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%d.%m.%Y"),
        "icon": icon
    }
    
    if type == "moderation":
        moderation_log.insert(0, event)
        if len(moderation_log) > 50: moderation_log.pop()
    
    activity_log.insert(0, event)
    if len(activity_log) > 100: activity_log.pop()

# --- DISCORD EVENTS ---

@client.event
async def on_ready():
    print(f'✅ Bot active: {client.user}')
    log_event("System", "Бот запущен на сервере", "zap")

@client.event
async def on_audit_log_entry_create(entry):
    if entry.user.bot: return
    if entry.action == discord.AuditLogAction.kick:
        log_event("Ручной Кик", f"{entry.user.name} кикнул {entry.target.name}", "user-x")
    elif entry.action == discord.AuditLogAction.ban:
        log_event("Ручной Бан", f"{entry.user.name} забанил {entry.target.name}", "gavel")
    elif entry.action == discord.AuditLogAction.unban:
        log_event("Ручной Разбан", f"{entry.user.name} разбанил {entry.target.name}", "unlock")
    elif entry.action == discord.AuditLogAction.member_update:
        if hasattr(entry.after, 'timed_out_until'):
            if entry.after.timed_out_until:
                log_event("Ручной Мут", f"{entry.user.name} замутил {entry.target.name}", "mic-off")
            else:
                log_event("Снятие Мута", f"{entry.user.name} размутил {entry.target.name}", "mic")

@client.event
async def on_member_join(member):
    log_event("Вход", f"{member.name}", "user-plus")

@client.event
async def on_member_remove(member):
    log_event("Выход", f"{member.name}", "user-minus")

@client.event
async def on_message_delete(message):
    if message.author.bot: return
    log_event("Удаление", f"Сообщение от {message.author.name}", "trash")

@client.event
async def on_raw_reaction_add(payload):
    msg_id = str(payload.message_id)
    if msg_id in reaction_roles_db:
        entry = reaction_roles_db[msg_id]
        if str(payload.emoji) == entry['emoji'] or payload.emoji.name == entry['emoji']:
            guild = client.get_guild(payload.guild_id)
            role = guild.get_role(int(entry['role_id']))
            member = guild.get_member(payload.user_id)
            if role and member and not member.bot:
                await member.add_roles(role)

@client.event
async def on_raw_reaction_remove(payload):
    msg_id = str(payload.message_id)
    if msg_id in reaction_roles_db:
        entry = reaction_roles_db[msg_id]
        if str(payload.emoji) == entry['emoji'] or payload.emoji.name == entry['emoji']:
            guild = client.get_guild(payload.guild_id)
            role = guild.get_role(int(entry['role_id']))
            member = guild.get_member(payload.user_id)
            if role and member and not member.bot:
                await member.remove_roles(role)

# --- FLASK ---
app = Flask(__name__, static_folder='.')
CORS(app)

@app.route('/')
def index(): return send_from_directory('.', 'index.html')
@app.route('/<path:path>')
def static_files(path): return send_from_directory('.', path)

@app.route('/api/auth', methods=['POST'])
def auth():
    if str(request.json.get('pin')) == str(PIN): return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route('/api/init', methods=['GET'])
def init_data():
    guilds = [{"id": str(g.id), "name": g.name} for g in client.guilds]
    return jsonify({
        "bot": {"name": client.user.name, "avatar": str(client.user.avatar.url) if client.user.avatar else None},
        "guilds": guilds
    })

@app.route('/api/guild/<guild_id>/full', methods=['GET'])
def guild_full(guild_id):
    guild = client.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Not found"}), 404
    
    members = []
    active_mutes = []
    
    for m in guild.members:
        if not m.bot:
            members.append({
                "id": str(m.id),
                "name": m.name,
                "avatar": str(m.avatar.url) if m.avatar else None,
                "joined": m.joined_at.strftime("%Y-%m-%d"),
                "created": m.created_at.strftime("%Y-%m-%d"),
                "roles": [{"name": r.name, "color": str(r.color)} for r in m.roles if r.name != "@everyone"]
            })
            if m.timed_out_until and m.timed_out_until > datetime.now(m.timed_out_until.tzinfo):
                active_mutes.append({"id": str(m.id), "name": m.name, "until": m.timed_out_until.strftime("%H:%M")})

    channels = [{"id": str(c.id), "name": c.name, "type": "text" if isinstance(c, discord.TextChannel) else "voice"} for c in guild.channels]
    roles = [{"id": str(r.id), "name": r.name, "color": str(r.color)} for r in guild.roles if r.name != "@everyone"]
    
    return jsonify({
        "members": members,
        "channels": channels,
        "roles": roles,
        "mutes": active_mutes,
        "activity": activity_log,
        "stats": {
            "members": guild.member_count,
            "roles": len(guild.roles),
            "channels": len(guild.channels)
        }
    })

@app.route('/api/guild/<guild_id>/bans', methods=['GET'])
def get_bans(guild_id):
    guild = client.get_guild(int(guild_id))
    async def fetch():
        try:
            bans = [entry async for entry in guild.bans()]
            return [{"user": {"id": str(b.user.id), "name": b.user.name}, "reason": b.reason} for b in bans]
        except: return []
    
    future = asyncio.run_coroutine_threadsafe(fetch(), client.loop)
    try: return jsonify(future.result())
    except: return jsonify([])

@app.route('/api/action/moderation', methods=['POST'])
def mod_action():
    data = request.json
    guild = client.get_guild(int(data['guild_id']))
    
    async def execute():
        log_ch_id = data.get('log_channel')
        log_ch = guild.get_channel(int(log_ch_id)) if log_ch_id else None
        
        if data['type'] == 'unban':
            user = await client.fetch_user(int(data['user_id']))
            await guild.unban(user)
            log_event("Разбан", f"{user.name} разбанен", "unlock")
            if log_ch: await log_ch.send(embed=discord.Embed(title="🔓 User Unbanned", description=f"User: {user.name}\nAdmin: Panel", color=0x00ff00))
            
        elif data['type'] == 'unmute':
            member = guild.get_member(int(data['user_id']))
            await member.timeout(None)
            log_event("Снятие мута", f"{member.name} размучен", "mic")
            if log_ch: await log_ch.send(embed=discord.Embed(title="🎤 User Unmuted", description=f"User: {member.name}\nAdmin: Panel", color=0x00ff00))

        else:
            member = guild.get_member(int(data['user_id']))
            reason = data.get('reason', 'Admin Panel')
            
            if data['type'] == 'kick':
                await member.kick(reason=reason)
                log_event("Кик", f"{member.name}", "user-x")
                if log_ch: await log_ch.send(embed=discord.Embed(title="👢 Kicked", description=f"User: {member.name}\nReason: {reason}", color=0xffa500))
            
            elif data['type'] == 'ban':
                await member.ban(reason=reason)
                log_event("Бан", f"{member.name}", "gavel")
                if log_ch: await log_ch.send(embed=discord.Embed(title="🔨 Banned", description=f"User: {member.name}\nReason: {reason}", color=0xff0000))
            
            elif data['type'] == 'mute':
                await member.timeout(timedelta(minutes=int(data.get('duration', 10))), reason=reason)
                log_event("Мут", f"{member.name} ({data.get('duration')}m)", "mic-off")
                if log_ch: await log_ch.send(embed=discord.Embed(title="🔇 Muted", description=f"User: {member.name}\nTime: {data.get('duration')}m", color=0xffff00))

    asyncio.run_coroutine_threadsafe(execute(), client.loop)
    return jsonify({"success": True})

@app.route('/api/action/send', methods=['POST'])
def send_msg():
    data = request.json
    channel = client.get_channel(int(data['channel_id']))
    async def send():
        embed = None
        if data.get('embed'):
            embed = discord.Embed(title=data['embed']['title'], description=data['embed']['description'], color=int(data['embed']['color'].replace('#',''), 16))
            if data['embed'].get('image'): embed.set_image(url=data['embed']['image'])
        await channel.send(content=data.get('content'), embed=embed)
    asyncio.run_coroutine_threadsafe(send(), client.loop)
    return jsonify({"success": True})

@app.route('/api/action/poll', methods=['POST'])
def create_poll():
    data = request.json
    channel = client.get_channel(int(data['channel_id']))
    question = data['question']
    options = data['options']
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    async def process():
        desc = ""
        for i, opt in enumerate(options):
            desc += f"{emojis[i]} {opt}\n"
        embed = discord.Embed(title=f"📊 {question}", description=desc, color=0x3b82f6)
        msg = await channel.send(embed=embed)
        for i in range(len(options)):
            await msg.add_reaction(emojis[i])
    asyncio.run_coroutine_threadsafe(process(), client.loop)
    return jsonify({"success": True})

@app.route('/api/action/reaction_role', methods=['POST'])
def rr_action():
    data = request.json
    channel = client.get_channel(int(data['channel_id']))
    async def create():
        msg = await channel.send(data['text'])
        await msg.add_reaction(data['emoji'])
        reaction_roles_db[str(msg.id)] = {"role_id": data['role_id'], "emoji": data['emoji']}
        save_rr_db()
    asyncio.run_coroutine_threadsafe(create(), client.loop)
    return jsonify({"success": True})

@app.route('/api/action/role_manage', methods=['POST'])
def role_manage():
    guild = client.get_guild(int(request.json['guild_id']))
    member = guild.get_member(int(request.json['user_id']))
    role = guild.get_role(int(request.json['role_id']))
    async def act():
        if request.json['action'] == 'add': await member.add_roles(role)
        else: await member.remove_roles(role)
    asyncio.run_coroutine_threadsafe(act(), client.loop)
    return jsonify({"success": True})

@app.route('/api/action/channel_delete', methods=['POST'])
def del_channel():
    channel = client.get_channel(int(request.json['channel_id']))
    async def delete(): await channel.delete()
    asyncio.run_coroutine_threadsafe(delete(), client.loop)
    return jsonify({"success": True})

# --- RUNNER ---
def run_flask():
    # Важно: host='0.0.0.0' делает сайт доступным извне
    app.run(host='0.0.0.0', port=PORT, use_reloader=False)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    client.run(TOKEN)
