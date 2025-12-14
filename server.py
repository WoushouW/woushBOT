import os
import json
import threading
import asyncio
import time
import re
import traceback
import requests
from datetime import datetime, timedelta
import datetime as dt
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG ---
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_PIN = os.getenv("ADMIN_PIN")
ROOM_MANAGER_PIN = os.getenv("ROOM_MANAGER_PIN", "110011")
PORT = int(os.getenv("PORT", 5000))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "DiscordBotLogs")
REQUEST_CHANNEL_ID = os.getenv("REQUEST_CHANNEL_ID")
ROOM_CATEGORY_ID = os.getenv("ROOM_CATEGORY_ID")

# Google Service Account credentials from environment
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY")
GOOGLE_CLIENT_EMAIL = os.getenv("GOOGLE_CLIENT_EMAIL")

if not TOKEN or not ADMIN_PIN:
    print("❌ ОШИБКА: Не найден DISCORD_TOKEN или ADMIN_PIN")
    exit(1)

# --- GOOGLE SHEETS SETUP ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
try:
    # Создаём credentials из переменных окружения
    if GOOGLE_PRIVATE_KEY and GOOGLE_CLIENT_EMAIL:
        credentials_info = {
            "type": "service_account",
            "project_id": GOOGLE_PROJECT_ID,
            "private_key": GOOGLE_PRIVATE_KEY.replace('\\n', '\n'),  # Исправляем экранирование
            "client_email": GOOGLE_CLIENT_EMAIL,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        print("✅ Google Sheets credentials загружены из .env")
    else:
        # Fallback на JSON файл если переменные не заданы
        creds = Credentials.from_service_account_file('service_account.json', scopes=SCOPES)
        print("✅ Google Sheets credentials загружены из service_account.json")
    
    gs_client = gspread.authorize(creds)
    print("✅ Google Sheets авторизация успешна")
    
    # Открываем/создаём таблицу
    try:
        spreadsheet = gs_client.open(GOOGLE_SHEET_NAME)
        print(f"✅ Открыта таблица: {GOOGLE_SHEET_NAME}")
    except gspread.SpreadsheetNotFound:
        spreadsheet = gs_client.create(GOOGLE_SHEET_NAME)
        spreadsheet.share('', perm_type='anyone', role='reader')  # Публичный доступ на чтение
        print(f"✅ Создана новая таблица: {GOOGLE_SHEET_NAME}")
    
    # Список всех необходимых листов (НЕ УДАЛЯЕМ ничего)
    REQUIRED_SHEETS = [
        'Activity', 'Moderation', 'Punishments', 'Messages', 'ReactionRoles', 
        'Warnings', 'Welcomes', 'Suspicious', 'Config', 'Channels'
    ]
    print(f"✅ Список обязательных листов: {REQUIRED_SHEETS}")
    
    # Автоудаление ОТКЛЮЧЕНО (по запросу пользователя)
    
    # Создаём/пересоздаём нужные листы с правильными заголовками
    def get_or_create_sheet(name, headers):
        try:
            ws = spreadsheet.worksheet(name)
            # Проверяем первую строку - если заголовки неправильные, удаляем и пересоздаём
            try:
                first_row = ws.row_values(1)
                if first_row != headers:
                    # ОБНОВЛЯЕМ заголовки вместо пересоздания
                    print(f"⚠️ Лист '{name}' имеет неправильные заголовки, обновляем...")
                    # Удаляем только первую строку и добавляем новые заголовки
                    ws.delete_rows(1)
                    ws.insert_row(headers, 1)
                    print(f"✅ Заголовки листа '{name}' обновлены (данные сохранены)")
                else:
                    print(f"✅ Лист '{name}' уже существует с правильными заголовками")
            except:
                # Пустой лист, добавляем заголовки
                ws.clear()
                ws.append_row(headers)
                print(f"✅ Заголовки добавлены в лист '{name}'")
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
            ws.append_row(headers)
            print(f"✅ Создан лист: {name}")
        return ws
    
    activity_sheet = get_or_create_sheet('Activity', 
        ['Timestamp', 'Event Type', 'User ID', 'Username', 'Details', 'Guild ID', 'Guild Name'])
    
    moderation_sheet = get_or_create_sheet('Moderation',
        ['Timestamp', 'Action', 'Target User ID', 'Target Username', 'Moderator', 'Reason', 'Duration', 'Guild ID', 'Guild Name'])
    
    punishments_sheet = get_or_create_sheet('Punishments',
        ['User ID', 'Username', 'Punishment Type', 'Reason', 'Start Time', 'End Time', 'Guild ID', 'Guild Name', 'Status'])
    
    messages_sheet = get_or_create_sheet('Messages',
        ['Timestamp', 'Guild ID', 'Guild Name', 'Channel', 'Sent By', 'Content'])
    
    reaction_roles_sheet = get_or_create_sheet('ReactionRoles',
        ['Message ID', 'Channel ID', 'Channel Name', 'Emoji', 'Role ID', 'Role Name', 'Created At', 'Guild ID', 'Guild Name'])
    
    warnings_sheet = get_or_create_sheet('Warnings',
        ['Timestamp', 'User ID', 'Username', 'Moderator', 'Reason', 'Warning Count', 'Guild ID', 'Guild Name', 'Status', 'Log Channel ID'])
    
    welcomes_sheet = get_or_create_sheet('Welcomes',
        ['Guild ID', 'Guild Name', 'Message ID', 'Channel ID', 'Target Channel ID', 'Target Channel Name', 'Welcome Message', 'Created At'])
    
    suspicious_sheet = get_or_create_sheet('Suspicious',
        ['Timestamp', 'Guild ID', 'Guild Name', 'Channel', 'User ID', 'Username', 'Content', 'Type'])
    
    config_sheet = get_or_create_sheet('Config',
        ['Guild ID', 'Config Type', 'Value'])
    
    # 📊 Лист для каналов (0=текстовый, 2=голосовой, 4=категория)
    channels_sheet = get_or_create_sheet('Channels',
        ['Guild ID', 'Guild Name', 'Channel ID', 'Channel Name', 'Type', 'Position', 'Category ID', 'Last Updated'])
    
    # 🚩 Лист для временных комнат
    temp_rooms_sheet = get_or_create_sheet('TempRooms',
        ['Channel ID', 'Room Name', 'Owner ID', 'Owner Name', 'Role ID', 'Duration', 'User Limit', 'Created At', 'Expires At', 'Guild ID', 'Guild Name', 'Status'])
    
    SHEETS_ENABLED = True
    print(f"✅ Все листы готовы к работе")
    print(f"🔗 Ссылка на таблицу: {spreadsheet.url}")
    
except Exception as e:
    print(f"⚠️ Google Sheets не настроен: {e}")
    SHEETS_ENABLED = False
    activity_sheet = None
    moderation_sheet = None
    punishments_sheet = None
    messages_sheet = None
    reaction_roles_sheet = None
    warnings_sheet = None
    welcomes_sheet = None
    suspicious_sheet = None
    config_sheet = None
    channels_sheet = None
    temp_rooms_sheet = None

# --- BOT SETUP ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- DATA STORAGE (Fallback) ---
reaction_roles_db = {}
activity_log = []
moderation_log = []
active_punishments = {"mutes": {}, "bans": {}}
bot_start_time = None

# Словари для защиты от спама
user_last_message = {}  # {user_id: timestamp}
user_message_count = {}  # {user_id: [(timestamp, count_in_window)]}
SPAM_THRESHOLD = 5  # сообщений за
SPAM_WINDOW = 10  # секунд

# Загрузка локальных данных
if os.path.exists("reaction_roles.json"):
    try:
        with open("reaction_roles.json", "r", encoding='utf-8') as f:
            reaction_roles_db = json.load(f)
    except: pass

if os.path.exists("active_punishments.json"):
    try:
        with open("active_punishments.json", "r", encoding='utf-8') as f:
            active_punishments = json.load(f)
    except: pass

# --- LOGGING FUNCTIONS ---
def log_to_activity_sheet(event_type, user_id, username, details, guild_id, guild_name):
    """Логирование в Google Sheets - Activity"""
    if SHEETS_ENABLED and activity_sheet:
        try:
            activity_sheet.append_row([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                event_type,
                str(user_id) if user_id else '',
                username if username else '',
                details,
                str(guild_id) if guild_id else '',
                guild_name if guild_name else ''
            ])
        except Exception as e:
            print(f"⚠️ Ошибка записи в Activity: {e}")
    
    # Fallback в локальный лог
    activity_log.insert(0, {
        "type": event_type,
        "user_id": str(user_id) if user_id else None,
        "username": username,
        "details": details,
        "guild_id": str(guild_id) if guild_id else None,
        "guild_name": guild_name,
        "time": datetime.now().isoformat()
    })
    if len(activity_log) > 1000:
        activity_log.pop()

def log_to_moderation_sheet(action, target_user_id, target_username, moderator, reason, duration, guild_id, guild_name):
    """Логирование в Google Sheets - Moderation"""
    if SHEETS_ENABLED and moderation_sheet:
        try:
            moderation_sheet.append_row([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                action,
                str(target_user_id),
                target_username,
                moderator,
                reason,
                duration if duration else '',
                str(guild_id) if guild_id else '',
                guild_name if guild_name else ''
            ])
        except Exception as e:
            print(f"⚠️ Ошибка записи в Moderation: {e}")
    
    # Fallback
    moderation_log.insert(0, {
        "action": action,
        "user_id": str(target_user_id),
        "username": target_username,
        "moderator": moderator,
        "reason": reason,
        "duration": duration,
        "guild_id": str(guild_id) if guild_id else None,
        "guild_name": guild_name,
        "time": datetime.now().isoformat()
    })
    if len(moderation_log) > 500:
        moderation_log.pop()

# === CONFIG MANAGEMENT ===
def get_trigger_words(guild_id):
    """Получить список триггер-слов для гильдии"""
    if not SHEETS_ENABLED or not config_sheet:
        return []
    try:
        records = config_sheet.get_all_records()
        triggers = [r['Value'] for r in records 
                   if str(r.get('Guild ID')) == str(guild_id) 
                   and r.get('Config Type') == 'trigger_word']
        return triggers
    except:
        return []

def get_excluded_channels(guild_id):
    """Получить список исключённых каналов"""
    if not SHEETS_ENABLED or not config_sheet:
        return []
    try:
        records = config_sheet.get_all_records()
        channels = [r['Value'] for r in records 
                   if str(r.get('Guild ID')) == str(guild_id) 
                   and r.get('Config Type') == 'excluded_channel']
        return channels
    except:
        return []

def add_trigger_word(guild_id, word):
    """Добавить триггер-слово"""
    if SHEETS_ENABLED and config_sheet:
        try:
            config_sheet.append_row([str(guild_id), 'trigger_word', word.lower()])
            return True
        except:
            return False
    return False

def remove_trigger_word(guild_id, word):
    """Удалить триггер-слово"""
    if SHEETS_ENABLED and config_sheet:
        try:
            records = config_sheet.get_all_records()
            for i, r in enumerate(records, start=2):
                if (str(r.get('Guild ID')) == str(guild_id) 
                    and r.get('Config Type') == 'trigger_word' 
                    and r.get('Value').lower() == word.lower()):
                    config_sheet.delete_rows(i)
                    return True
            return False
        except:
            return False
    return False

def add_excluded_channel(guild_id, channel_id):
    """Добавить канал в исключения"""
    if SHEETS_ENABLED and config_sheet:
        try:
            config_sheet.append_row([str(guild_id), 'excluded_channel', str(channel_id)])
            return True
        except:
            return False
    return False

def remove_excluded_channel(guild_id, channel_id):
    """Удалить канал из исключений"""
    if SHEETS_ENABLED and config_sheet:
        try:
            records = config_sheet.get_all_records()
            for i, r in enumerate(records, start=2):
                if (str(r.get('Guild ID')) == str(guild_id) 
                    and r.get('Config Type') == 'excluded_channel' 
                    and str(r.get('Value')) == str(channel_id)):
                    config_sheet.delete_rows(i)
                    return True
            return False
        except:
            return False
    return False

# Базовые триггеры (будут использоваться, если нет в Config)
DEFAULT_TRIGGERS = [
    'fuck', 'shit', 'bitch', 'ass', 'damn', 'crap', 'piss', 'dick', 'cock', 'pussy',
    'whore', 'slut', 'bastard', 'asshole', 'motherfucker', 'nigga', 'nigger', 'faggot',
    'cunt', 'twat', 'blyat', 'blyad', 'cyka', 'suka', 'pidaras', 'pidoras', 'pizda',
    'хуй', 'бляд', 'блять', 'пизда', 'пиздец', 'ебать', 'ебаный', 'ебало',
    'сука', 'суки', 'пидор', 'пидар', 'говно', 'говнюк', 'мудак', 'мудила',
    'дебил', 'идиот', 'уебок', 'дурак', 'тупой', 'лох', 'чмо', 'урод'
]

def log_to_messages_sheet(channel_id, channel_name, message_type, content, guild_id, guild_name):
    """Логирование в Google Sheets - Messages"""
    if SHEETS_ENABLED and messages_sheet:
        try:
            messages_sheet.append_row([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                str(channel_id),
                channel_name,
                message_type,
                content[:500],  # Ограничение длины
                'Admin Panel',
                str(guild_id) if guild_id else '',
                guild_name if guild_name else ''
            ])
        except Exception as e:
            print(f"⚠️ Ошибка записи в Messages: {e}")

def sync_punishments_to_sheet():
    """Синхронизация активных наказаний с Google Sheets"""
    if SHEETS_ENABLED and punishments_sheet:
        try:
            # Очищаем лист (кроме заголовков)
            punishments_sheet.clear()
            punishments_sheet.append_row(['User ID', 'Username', 'Punishment Type', 'Reason', 'Start Time', 'End Time', 'Guild ID', 'Guild Name', 'Status'])
            
            # Муты
            for user_id, data in active_punishments.get("mutes", {}).items():
                punishments_sheet.append_row([
                    str(user_id),
                    data.get('member_name', ''),
                    'mute',
                    data.get('reason', ''),
                    data.get('start_time', ''),
                    data.get('until', ''),
                    data.get('guild_id', ''),
                    '',  # guild_name можно добавить
                    'active'
                ])
            
            # Баны
            for user_id, data in active_punishments.get("bans", {}).items():
                punishments_sheet.append_row([
                    str(user_id),
                    data.get('user_name', ''),
                    'ban',
                    data.get('reason', ''),
                    data.get('start_time', ''),
                    '',  # Перманентный бан
                    data.get('guild_id', ''),
                    '',
                    'active'
                ])
        except Exception as e:
            print(f"⚠️ Ошибка синхронизации Punishments: {e}")
    
    # Локальное сохранение
    with open("active_punishments.json", "w", encoding='utf-8') as f:
        json.dump(active_punishments, f, ensure_ascii=False, indent=2)

def save_rr_db():
    with open("reaction_roles.json", "w", encoding='utf-8') as f:
        json.dump(reaction_roles_db, f, ensure_ascii=False, indent=2)

async def send_moderation_log(guild, channel_id, action_type, member, reason, duration=None, moderator="Admin Panel"):
    """Отправка лога модерации в канал"""
    if not channel_id:
        return
    
    channel = guild.get_channel(int(channel_id))
    if not channel:
        return
    
    colors = {
        'mute': discord.Color.orange(),
        'unmute': discord.Color.green(),
        'kick': discord.Color.red(),
        'ban': discord.Color.dark_red(),
        'unban': discord.Color.green(),
        'warning': discord.Color.gold()
    }
    
    titles = {
        'mute': '🔇 Мут',
        'unmute': '🔊 Снятие мута',
        'kick': '🚪 Кик',
        'ban': '🚫 Бан',
        'unban': '✅ Разбан',
        'warning': '⚠️ Предупреждение'
    }
    
    try:
        embed = discord.Embed(
            title=titles.get(action_type, '🛡️ Модерация'),
            description=f"Пользователь {member.mention if hasattr(member, 'mention') else member}",
            color=colors.get(action_type, discord.Color.blue()),
            timestamp=datetime.now()
        )
        embed.add_field(name="Причина", value=reason, inline=False)
        if duration:
            embed.add_field(name="Длительность", value=duration, inline=True)
        embed.set_footer(text=f"Модератор: {moderator}")
        await channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ Ошибка отправки лога: {e}")


# ==================== SYNC CHANNELS TO EXCEL ====================

def sync_channels_to_excel(guild):
    """Синхронизировать все каналы сервера в Excel"""
    print(f"🔍 DEBUG: SHEETS_ENABLED = {SHEETS_ENABLED}")
    print(f"🔍 DEBUG: channels_sheet = {channels_sheet}")
    
    if not SHEETS_ENABLED or not channels_sheet:
        print(f"❌ Channels sheet не включен! SHEETS_ENABLED={SHEETS_ENABLED}, channels_sheet={channels_sheet}")
        return
    
    try:
        print(f"📊 Синхронизация каналов для guild {guild.name} (ID: {guild.id})...")
        
        # Получаем все каналы
        all_channels = guild.channels
        
        # Очищаем старые записи этого сервера
        existing_records = channels_sheet.get_all_records()
        rows_to_delete = []
        for idx, record in enumerate(existing_records, start=2):
            if str(record.get('Guild ID')) == str(guild.id):
                rows_to_delete.append(idx)
        
        # Удаляем в обратном порядке (чтобы индексы не сбивались)
        for row_idx in reversed(rows_to_delete):
            channels_sheet.delete_rows(row_idx)
        
        print(f"🗑️ Удалено {len(rows_to_delete)} старых записей каналов")
        
        # Добавляем новые записи
        new_rows = []
        for channel in all_channels:
            # Определяем тип канала
            channel_type = None
            if hasattr(channel, 'type'):
                if channel.type == discord.ChannelType.text:
                    channel_type = 0  # Текстовый
                elif channel.type == discord.ChannelType.voice:
                    channel_type = 2  # Голосовой
                elif channel.type == discord.ChannelType.category:
                    channel_type = 4  # Категория
            
            if channel_type is None:
                continue  # Пропускаем неизвестные типы
            
            # Получаем category_id
            category_id = ''
            if hasattr(channel, 'category') and channel.category:
                category_id = str(channel.category.id)
            
            # Добавляем строку
            new_rows.append([
                str(guild.id),
                guild.name,
                str(channel.id),
                channel.name,
                str(channel_type),
                str(channel.position) if hasattr(channel, 'position') else '0',
                category_id,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        # Массово добавляем все строки
        if new_rows:
            channels_sheet.append_rows(new_rows)
            print(f"✅ Синхронизировано {len(new_rows)} каналов:")
            
            # Подсчёт по типам
            text_count = sum(1 for row in new_rows if row[4] == '0')
            voice_count = sum(1 for row in new_rows if row[4] == '2')
            category_count = sum(1 for row in new_rows if row[4] == '4')
            
            print(f"   📝 Текстовых: {text_count}")
            print(f"   🔊 Голосовых: {voice_count}")
            print(f"   📂 Категорий: {category_count}")
        else:
            print("⚠️ Нет каналов для синхронизации")
    
    except Exception as e:
        print(f"❌ Ошибка синхронизации каналов: {e}")
        traceback.print_exc()

def get_text_channels_from_excel(guild_id):
    """Получить список текстовых каналов из Excel"""
    if not SHEETS_ENABLED or not channels_sheet:
        print("⚠️ Channels sheet не включен")
        return []
    
    try:
        records = channels_sheet.get_all_records()
        print(f"🔍 DEBUG: Всего записей в Channels: {len(records)}")
        
        # Debug: показываем первую запись
        if records:
            print(f"🔍 DEBUG: Первая запись: {records[0]}")
        
        # Debug: ищем записи для guild
        guild_records = [r for r in records if str(r.get('Guild ID')) == str(guild_id)]
        print(f"🔍 DEBUG: Записей для guild {guild_id}: {len(guild_records)}")
        
        # Debug: показываем типы
        if guild_records:
            print(f"🔍 DEBUG: Типы каналов: {[r.get('Type') for r in guild_records[:5]]}")
        
        text_channels = [
            {
                'id': record['Channel ID'],
                'name': record['Channel Name'],
                'type': int(record['Type']) if record['Type'] else 0,
                'position': int(record.get('Position', 0))
            }
            for record in records
            if str(record.get('Guild ID')) == str(guild_id) and str(record.get('Type')) == '0'
        ]
        
        # Сортируем по position
        text_channels.sort(key=lambda x: x['position'])
        
        print(f"📝 Загружено {len(text_channels)} текстовых каналов из Excel")
        return text_channels
    
    except Exception as e:
        print(f"❌ Ошибка чтения каналов из Excel: {e}")
        return []

# ==================== END SYNC CHANNELS ====================

def get_user_warnings(user_id, guild_id):
    """Получить количество активных предупреждений пользователя"""
    if SHEETS_ENABLED and warnings_sheet:
        try:
            all_records = warnings_sheet.get_all_records()
            # Считаем активные предупреждения
            active_warnings = [
                r for r in all_records
                if str(r.get('User ID')) == str(user_id) 
                and str(r.get('Guild ID')) == str(guild_id)
                and r.get('Status') == 'active'
            ]
            return len(active_warnings)
        except Exception as e:
            print(f"⚠️ Ошибка чтения Warnings: {e}")
    return 0

def add_warning(user_id, username, moderator, reason, guild_id, guild_name, log_channel_id=None):
    """Добавить предупреждение пользователю"""
    if SHEETS_ENABLED and warnings_sheet:
        try:
            warnings_count = get_user_warnings(user_id, guild_id) + 1
            warnings_sheet.append_row([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                str(user_id),
                username,
                moderator,
                reason,
                str(warnings_count),
                str(guild_id),
                guild_name,
                'active',
                str(log_channel_id) if log_channel_id else ''  # ✅ Сохраняем log_channel_id
            ])
            return warnings_count
        except Exception as e:
            print(f"⚠️ Ошибка записи в Warnings: {e}")
    return 1

def clear_user_warnings(user_id, guild_id):
    """Очистить все предупреждения пользователя (при бане)"""
    if SHEETS_ENABLED and warnings_sheet:
        try:
            all_records = warnings_sheet.get_all_records()
            # Находим все строки с активными предупреждениями
            for idx, record in enumerate(all_records, start=2):  # +2 потому что заголовки в строке 1
                if (str(record.get('User ID')) == str(user_id) 
                    and str(record.get('Guild ID')) == str(guild_id)
                    and record.get('Status') == 'active'):
                    # Меняем статус на 'cleared'
                    warnings_sheet.update_cell(idx, 9, 'cleared')  # Колонка Status (№9)
            print(f"✅ Предупреждения очищены для user_id={user_id}")
        except Exception as e:
            print(f"⚠️ Ошибка очистки Warnings: {e}")

# --- DISCORD BOT EVENTS ---
async def scan_reaction_messages():
    """Сканирование сообщений бота с реакциями для автообнаружения"""
    print("🔍 Сканирование сообщений с реакциями...")
    found_count = 0
    
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                # Проверяем последние 50 сообщений в каждом канале
                async for message in channel.history(limit=50):
                    # Только сообщения бота с реакциями
                    if message.author == bot.user and message.reactions:
                        message_id = str(message.id)
                        
                        # Пропускаем уже известные сообщения
                        if message_id in reaction_roles_db or message_id in welcome_configs:
                            continue
                        
                        # Добавляем как ненастроенное сообщение с реакциями
                        reactions_data = []
                        for reaction in message.reactions:
                            reactions_data.append({
                                "emoji": str(reaction.emoji),
                                "role_id": None  # Не настроена
                            })
                        
                        reaction_roles_db[message_id] = {
                            "channel_id": str(channel.id),
                            "guild_id": str(guild.id),
                            "message": message.content or "[Без текста]",
                            "reactions": reactions_data,
                            "unconfigured": True  # Маркер ненастроенного сообщения
                        }
                        found_count += 1
                        print(f"  ✅ Найдено: #{channel.name} - {len(reactions_data)} реакций")
            except Exception as e:
                continue  # Пропускаем каналы без доступа
    
    if found_count > 0:
        save_rr_db()
        print(f"✅ Автообнаружение: найдено {found_count} сообщений с реакциями")
    else:
        print("ℹ️ Новых сообщений с реакциями не найдено")

@bot.event
async def on_ready():
    global bot_start_time
    bot_start_time = datetime.now()
    print(f'✅ Bot запущен: {bot.user.name} ({bot.user.id})')
    print(f'🌐 Серверов: {len(bot.guilds)}')
    for guild in bot.guilds:
        print(f'  - {guild.name} (ID: {guild.id})')
    
    # Автообнаружение сообщений с реакциями
    await scan_reaction_messages()
    
    # 📊 АВТОМАТИЧЕСКАЯ СИНХРОНИЗАЦИЯ КАНАЛОВ В EXCEL!
    print("\n📊 Синхронизирую все каналы в Excel...")
    for guild in bot.guilds:
        sync_channels_to_excel(guild)
    print("✅ Синхронизация каналов завершена!\n")
    
    # 🚩 ЗАГРУЗКА АКТИВНЫХ ВРЕМЕННЫХ КОМНАТ
    print("🚩 Загружаю активные временные комнаты из Google Sheets...")
    load_active_rooms_from_sheet()
    
    log_to_activity_sheet("system", None, "System", f"Бот {bot.user.name} запущен", None, None)

@bot.event
async def on_message(message):
    """Логирование всех сообщений от пользователей (не ботов)"""
    # Игнорируем сообщения от самого бота
    if message.author.bot:
        return
    
    user_id = str(message.author.id)
    guild_id = str(message.guild.id) if message.guild else None
    current_time = datetime.now()
    
    # === ЗАЩИТА ОТ СПАМА (для Activity Stats) ===
    # Засчитываем только 1 сообщение в 5 секунд
    should_log_activity = True
    if user_id in user_last_message:
        time_diff = (current_time - user_last_message[user_id]).total_seconds()
        if time_diff < 5:
            should_log_activity = False
    
    if should_log_activity:
        user_last_message[user_id] = current_time
    
    # === ДЕТЕКЦИЯ СПАМА (быстрая отправка) ===
    is_spam = False
    if user_id not in user_message_count:
        user_message_count[user_id] = []
    
    # Удаляем старые записи (старше SPAM_WINDOW секунд)
    user_message_count[user_id] = [
        (ts, c) for ts, c in user_message_count[user_id]
        if (current_time - ts).total_seconds() < SPAM_WINDOW
    ]
    
    # Добавляем текущее сообщение
    user_message_count[user_id].append((current_time, 1))
    
    # Проверяем, превышен ли порог
    if len(user_message_count[user_id]) > SPAM_THRESHOLD:
        is_spam = True
    
    # Логируем в Messages sheet для Activity Stats (только если не спам)
    if should_log_activity and SHEETS_ENABLED and messages_sheet:
        try:
            sent_by = f"{message.author.name} ({message.author.id})"
            messages_sheet.append_row([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Timestamp
                str(message.guild.id) if message.guild else 'DM',  # Guild ID
                message.guild.name if message.guild else 'Direct Message',  # Guild Name
                message.channel.name if hasattr(message.channel, 'name') else 'DM',  # Channel
                sent_by,  # Sent By (Username (ID))
                message.content[:500]  # Content (обрезаем до 500 символов)
            ])
        except Exception as e:
            print(f"❌ Error logging message: {e}")
    
    # Логируем в Activity sheet
    log_to_activity_sheet(
        "message", 
        message.author.id, 
        message.author.name,
        f"Отправил сообщение в #{message.channel.name if hasattr(message.channel, 'name') else 'DM'}",
        message.guild.id if message.guild else None,
        message.guild.name if message.guild else None
    )
    
    # === ПРОВЕРКА НА ПОДОЗРИТЕЛЬНОСТЬ ===
    if SHEETS_ENABLED and suspicious_sheet and guild_id:
        try:
            # Проверяем, не исключён ли канал
            excluded_channels = get_excluded_channels(guild_id)
            channel_id_str = str(message.channel.id) if hasattr(message.channel, 'id') else None
            
            if channel_id_str not in excluded_channels:
                content_lower = message.content.lower()
                
                # Получаем триггеры из Config или используем базовые
                triggers = get_trigger_words(guild_id)
                if not triggers:
                    triggers = DEFAULT_TRIGGERS
                
                # Проверяем триггеры (в любой части текста)
                found_trigger = None
                for trigger in triggers:
                    if trigger.lower() in content_lower:
                        found_trigger = trigger
                        break
                
                # Логируем, если нашли триггер ИЛИ спам
                if found_trigger or is_spam:
                    suspicious_type = 'trigger' if found_trigger else 'spam'
                    suspicious_sheet.append_row([
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        str(message.guild.id) if message.guild else 'DM',
                        message.guild.name if message.guild else 'Direct Message',
                        message.channel.name if hasattr(message.channel, 'name') else 'DM',
                        str(message.author.id),
                        message.author.name,
                        message.content[:500],
                        suspicious_type
                    ])
                    
                    if found_trigger:
                        print(f"⚠️ Trigger '{found_trigger}' found from {message.author.name}: {message.content[:50]}...")
                    if is_spam:
                        print(f"⚠️ Spam detected from {message.author.name}: {len(user_message_count[user_id])} messages in {SPAM_WINDOW}s")
        except Exception as e:
            print(f"❌ Error logging suspicious message: {e}")
    
    # Обрабатываем команды
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    log_to_activity_sheet("member_join", member.id, member.name, 
                          f"Присоединился к серверу", member.guild.id, member.guild.name)

@bot.event
async def on_member_remove(member):
    log_to_activity_sheet("member_leave", member.id, member.name,
                          f"Покинул сервер", member.guild.id, member.guild.name)

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        for role in added:
            log_to_activity_sheet("role_add", after.id, after.name,
                                 f"Получил роль: {role.name}", after.guild.id, after.guild.name)
        for role in removed:
            log_to_activity_sheet("role_remove", after.id, after.name,
                                 f"Потерял роль: {role.name}", after.guild.id, after.guild.name)

@bot.event
async def on_guild_channel_create(channel):
    channel_type = {0: "текстовый", 2: "голосовой", 4: "категория"}.get(channel.type.value, "неизвестный")
    log_to_activity_sheet("channel_create", None, None,
                         f"Создан {channel_type} канал: {channel.name}", channel.guild.id, channel.guild.name)

@bot.event
async def on_guild_channel_delete(channel):
    log_to_activity_sheet("channel_delete", None, None,
                         f"Удалён канал: {channel.name}", channel.guild.id, channel.guild.name)

@bot.event
async def on_raw_reaction_remove(payload):
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
                        log_to_activity_sheet("reaction_role_remove", member.id, member.name,
                                             f"Потерял роль {role.name} при удалении реакции", guild.id, guild.name)
                break

# Система приветствий по реакциям
welcome_configs = {}  # {message_id: {"guild_id": ..., "target_channel_id": ..., "message": ...}}

def save_welcome_db():
    with open("welcomes.json", "w", encoding='utf-8') as f:
        json.dump(welcome_configs, f, ensure_ascii=False, indent=2)

if os.path.exists("welcomes.json"):
    try:
        with open("welcomes.json", "r", encoding='utf-8') as f:
            welcome_configs = json.load(f)
    except: pass

@bot.event
async def on_raw_reaction_add(payload):
    # Игнорируем реакции бота
    if payload.user_id == bot.user.id:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    
    member = guild.get_member(payload.user_id)
    if not member:
        return
    
    # ЛОГИРУЕМ ВСЕ РЕАКЦИИ ДЛЯ СТАТИСТИКИ
    log_to_activity_sheet("add_reaction", member.id, member.name,
                         f"Добавил реакцию {payload.emoji}", guild.id, guild.name)
    
    # Проверяем систему приветствий
    if str(payload.message_id) in welcome_configs:
        config = welcome_configs[str(payload.message_id)]
        target_channel = bot.get_channel(int(config["target_channel_id"]))
        if target_channel:
            welcome_msg = config["message"].replace("{user}", member.mention).replace("{username}", member.name)
            await target_channel.send(welcome_msg)
            log_to_activity_sheet("welcome_sent", member.id, member.name,
                                 f"Отправлено приветствие в #{target_channel.name}", guild.id, guild.name)
    
    # Роли за реакции
    key = f"{payload.message_id}"
    if key in reaction_roles_db:
        rr_data = reaction_roles_db[key]
        for reaction in rr_data.get("reactions", []):
            if str(payload.emoji) == reaction["emoji"]:
                role = guild.get_role(int(reaction["role_id"]))
                if role:
                    await member.add_roles(role)
                    log_to_activity_sheet("reaction_role_add", member.id, member.name,
                                         f"Получил роль {role.name} за реакцию", guild.id, guild.name)
                break

# --- FLASK APP ---
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, resources={r"/*": {"origins": "*"}})

def require_auth(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        # Проверяем оба пароля
        if not auth_header or (auth_header != f"Bearer {ADMIN_PIN}" and auth_header != f"Bearer {ROOM_MANAGER_PIN}"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# --- ROUTES ---
@app.route('/')
def index():
    return send_file('login.html')

@app.route('/login.html')
def login_page():
    return send_file('login.html')

@app.route('/index.html')
def dashboard():
    return send_file('index.html')

@app.route('/room-manager.html')
def room_manager():
    return send_file('room-manager.html')

@app.route('/js/<path:path>')
def send_js(path):
    return send_file(f'js/{path}')

@app.route('/css/<path:path>')
def send_css(path):
    return send_file(f'css/{path}')

@app.route('/keep_alive_ping')
def keep_alive_ping():
    return jsonify({"status": "alive", "timestamp": datetime.now().isoformat()}), 200

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    pin = data.get('pin', '')
    if pin == ADMIN_PIN:
        return jsonify({"success": True, "token": ADMIN_PIN, "role": "admin"})
    elif pin == ROOM_MANAGER_PIN:
        return jsonify({"success": True, "token": ROOM_MANAGER_PIN, "role": "room_manager"})
    else:
        return jsonify({"success": False, "error": "Неверный пароль"}), 401

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

@app.route('/api/guilds', methods=['GET'])
@require_auth
def get_guilds():
    if not bot.is_ready():
        return jsonify({"error": "Бот ещё не готов", "retry": True}), 503
    
    guilds = [{
        "id": str(g.id),
        "name": g.name,
        "icon": str(g.icon.url) if g.icon else None,
        "member_count": g.member_count
    } for g in bot.guilds]
    return jsonify(guilds)

@app.route('/api/guilds/<guild_id>/full', methods=['GET'])
@require_auth
def get_guild_full(guild_id):
    # Проверка готовности бота
    if not bot.is_ready():
        return jsonify({"error": "Бот ещё не готов", "retry": True}), 503
    
    guild = bot.get_guild(int(guild_id))
    if not guild:
        # Дебаг: покажем все доступные сервера
        available_guilds = [f"{g.name} ({g.id})" for g in bot.guilds]
        print(f"⚠️ Сервер {guild_id} не найден. Доступные: {available_guilds}")
        return jsonify({"error": "Сервер не найден", "available": available_guilds}), 404
    
    members = [{
        "id": str(m.id),
        "username": m.name,
        "discriminator": m.discriminator,
        "nick": m.nick,
        "avatar": str(m.avatar.url) if m.avatar else None,
        "bot": m.bot,
        "roles": [str(r.id) for r in m.roles if r.name != "@everyone"],
        "status": str(m.status),
        "joined_at": m.joined_at.isoformat() if m.joined_at else None
    } for m in guild.members]
    
    channels = [{
        "id": str(c.id),
        "name": c.name,
        "type": c.type.value,
        "position": c.position,
        "topic": getattr(c, 'topic', None)
    } for c in guild.channels]
    
    roles = [{
        "id": str(r.id),
        "name": r.name,
        "color": r.color.value,
        "position": r.position,
        "members": len(r.members)
    } for r in guild.roles if r.name != "@everyone"]
    
    return jsonify({
        "guild": {
            "id": str(guild.id),
            "name": guild.name,
            "icon": str(guild.icon.url) if guild.icon else None,
            "member_count": guild.member_count
        },
        "members": members,
        "channels": sorted(channels, key=lambda x: x['position']),
        "roles": sorted(roles, key=lambda x: -x['position'])
    })

@app.route('/api/guilds/<guild_id>/members', methods=['GET'])
@require_auth
def get_guild_members(guild_id):
    """Получить список участников сервера"""
    if not bot.is_ready():
        return jsonify({"error": "Бот ещё не готов", "retry": True}), 503
    
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
        "roles": [str(r.id) for r in m.roles if r.name != "@everyone"],
        "status": str(m.status),
        "joined_at": m.joined_at.isoformat() if m.joined_at else None
    } for m in guild.members]
    
    return jsonify(members), 200

@app.route('/api/guilds/<guild_id>/roles', methods=['GET'])
@require_auth
def get_guild_roles(guild_id):
    """Получить список ролей сервера"""
    if not bot.is_ready():
        return jsonify({"error": "Бот ещё не готов", "retry": True}), 503
    
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
    
    return jsonify(sorted(roles, key=lambda x: -x['position'])), 200

@app.route('/api/channels/<channel_id>/messages', methods=['GET'])
@require_auth
def get_messages(channel_id):
    """Получить сообщения из канала"""
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({"error": "Канал не найден"}), 404
    
    # Получаем параметр limit (по умолчанию 20, макс 100)
    limit = min(int(request.args.get('limit', 20)), 100)
    
    async def fetch_messages():
        messages_list = []
        async for message in channel.history(limit=limit):
            # Пропускаем сообщения от ботов (опционально)
            # if message.author.bot:
            #     continue
            
            messages_list.append({
                "id": str(message.id),
                "content": message.content,
                "author": message.author.name,
                "author_id": str(message.author.id),
                "timestamp": message.created_at.isoformat(),
                "attachments": len(message.attachments),
                "embeds": len(message.embeds),
                "channel_id": str(message.channel.id)
            })
        return messages_list
    
    try:
        future = asyncio.run_coroutine_threadsafe(fetch_messages(), bot.loop)
        messages = future.result(timeout=10)
        return jsonify(messages), 200
    except Exception as e:
        print(f"❌ Ошибка загрузки сообщений: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/channels/<channel_id>/messages', methods=['POST'])
@require_auth
def send_message(channel_id):
    channel = bot.get_channel(int(channel_id))
    if not channel: return jsonify({"error": "Канал не найден"}), 404
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
            log_to_messages_sheet(channel.id, channel.name, 'embed',
                                 f"{embed_data.get('title', '')}: {embed_data.get('description', '')[:100]}",
                                 channel.guild.id, channel.guild.name)
        else:
            msg = await channel.send(content)
            log_to_messages_sheet(channel.id, channel.name, 'normal', content,
                                 channel.guild.id, channel.guild.name)
        
        log_to_activity_sheet("message_sent", None, "Admin Panel",
                             f"Сообщение отправлено в #{channel.name}", channel.guild.id, channel.guild.name)
        return msg
    
    future = asyncio.run_coroutine_threadsafe(send(), bot.loop)
    msg = future.result(timeout=10)
    return jsonify({"id": str(msg.id), "success": True})

@app.route('/api/channels/<channel_id>/messages/bulk-delete', methods=['POST'])
@require_auth
def bulk_delete(channel_id):
    channel = bot.get_channel(int(channel_id))
    if not channel: return jsonify({"error": "Канал не найден"}), 404
    data = request.json
    limit = data.get('limit', 10)
    
    async def delete():
        deleted = await channel.purge(limit=limit)
        log_to_activity_sheet("message_bulk_delete", None, "Admin Panel",
                             f"Удалено {len(deleted)} сообщений в #{channel.name}",
                             channel.guild.id, channel.guild.name)
        return len(deleted)
    
    future = asyncio.run_coroutine_threadsafe(delete(), bot.loop)
    count = future.result(timeout=30)
    return jsonify({"deleted": count, "success": True})

@app.route('/api/guilds/<guild_id>/members/<user_id>/timeout', methods=['POST'])
@require_auth
def timeout_member(guild_id, user_id):
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    member = guild.get_member(int(user_id))
    if not member: return jsonify({"error": "Участник не найден"}), 404
    data = request.json
    duration = data.get('duration', 60)
    reason = data.get('reason', 'Нарушение правил')
    log_channel_id = data.get('log_channel_id')
    
    async def mute():
        until = discord.utils.utcnow() + timedelta(seconds=duration)
        await member.timeout(until, reason=reason)
        
        active_punishments["mutes"][str(user_id)] = {
            "guild_id": str(guild_id),
            "reason": reason,
            "until": until.isoformat(),
            "start_time": datetime.now().isoformat(),
            "moderator": "Admin Panel",
            "member_name": member.name,
            "log_channel_id": log_channel_id  # Сохраняем канал для уведомления
        }
        print(f"✅ MUTE: Сохранён log_channel_id = {log_channel_id} для user_id = {user_id}")
        sync_punishments_to_sheet()
        log_to_moderation_sheet("mute", user_id, member.name, "Admin Panel", reason, f"{duration}s", guild_id, guild.name)
        log_to_activity_sheet("mute", member.id, member.name, f"Замучен на {duration}с. Причина: {reason}", guild.id, guild.name)
        
        # Отправляем лог в канал
        if log_channel_id:
            await send_moderation_log(guild, log_channel_id, 'mute', member, reason, f"{duration}с")
    
    future = asyncio.run_coroutine_threadsafe(mute(), bot.loop)
    future.result(timeout=10)
    return jsonify({"success": True})

@app.route('/api/guilds/<guild_id>/members/<user_id>/untimeout', methods=['POST'])
@require_auth
def untimeout_member(guild_id, user_id):
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    member = guild.get_member(int(user_id))
    if not member: return jsonify({"error": "Участник не найден"}), 404
    
    async def unmute():
        await member.timeout(None)
        
        # Получаем log_channel_id из сохранённых данных
        log_channel_id = None
        if str(user_id) in active_punishments["mutes"]:
            log_channel_id = active_punishments["mutes"][str(user_id)].get("log_channel_id")
            print(f"🔍 UNMUTE: log_channel_id = {log_channel_id}")
            del active_punishments["mutes"][str(user_id)]
            sync_punishments_to_sheet()
        else:
            print(f"⚠️ UNMUTE: user_id {user_id} не найден в active_punishments['mutes']")
        
        log_to_moderation_sheet("unmute", user_id, member.name, "Admin Panel", "Мут снят", None, guild_id, guild.name)
        log_to_activity_sheet("unmute", member.id, member.name, "Мут снят", guild.id, guild.name)
        
        # Отправляем уведомление в тот же канал
        if log_channel_id:
            print(f"✅ UNMUTE: Отправляем уведомление в канал {log_channel_id}")
            await send_moderation_log(guild, log_channel_id, 'unmute', member, 'Мут снят', None)
        else:
            print(f"❌ UNMUTE: log_channel_id пустой, уведомление не отправлено")
    
    future = asyncio.run_coroutine_threadsafe(unmute(), bot.loop)
    future.result(timeout=10)
    return jsonify({"success": True})

@app.route('/api/guilds/<guild_id>/members/<user_id>/kick', methods=['POST'])
@require_auth
def kick_member(guild_id, user_id):
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    member = guild.get_member(int(user_id))
    if not member: return jsonify({"error": "Участник не найден"}), 404
    data = request.json
    reason = data.get('reason', 'Нарушение правил')
    log_channel_id = data.get('log_channel_id')
    
    async def kick():
        member_name = member.name
        member_obj = member  # Сохраняем до кика
        await member.kick(reason=reason)
        log_to_moderation_sheet("kick", user_id, member_name, "Admin Panel", reason, None, guild_id, guild.name)
        log_to_activity_sheet("kick", user_id, member_name, f"Кикнут. Причина: {reason}", guild.id, guild.name)
        
        # Отправляем лог
        if log_channel_id:
            await send_moderation_log(guild, log_channel_id, 'kick', member_obj, reason)
    
    future = asyncio.run_coroutine_threadsafe(kick(), bot.loop)
    future.result(timeout=10)
    return jsonify({"success": True})

@app.route('/api/guilds/<guild_id>/members/<user_id>/ban', methods=['POST'])
@require_auth
def ban_member(guild_id, user_id):
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    data = request.json
    reason = data.get('reason', 'Нарушение правил')
    delete_days = data.get('delete_message_days', 0)
    log_channel_id = data.get('log_channel_id')
    
    async def ban():
        user = await bot.fetch_user(int(user_id))
        await guild.ban(user, reason=reason, delete_message_days=delete_days)
        
        active_punishments["bans"][str(user_id)] = {
            "guild_id": str(guild_id),
            "reason": reason,
            "start_time": datetime.now().isoformat(),
            "moderator": "Admin Panel",
            "user_name": user.name,
            "log_channel_id": log_channel_id
        }
        print(f"✅ BAN: Сохранён log_channel_id = {log_channel_id} для user_id = {user_id}")
        sync_punishments_to_sheet()
        log_to_moderation_sheet("ban", user_id, user.name, "Admin Panel", reason, None, guild_id, guild.name)
        log_to_activity_sheet("ban", user.id, user.name, f"Забанен. Причина: {reason}", guild.id, guild.name)
        # Очищаем предупреждения при бане
        clear_user_warnings(user_id, guild_id)
        
        # Отправляем лог
        if log_channel_id:
            await send_moderation_log(guild, log_channel_id, 'ban', user, reason)
    
    future = asyncio.run_coroutine_threadsafe(ban(), bot.loop)
    future.result(timeout=10)
    return jsonify({"success": True})

@app.route('/api/guilds/<guild_id>/bans/<user_id>', methods=['DELETE'])
@require_auth
def unban_member(guild_id, user_id):
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    
    async def unban():
        user = await bot.fetch_user(int(user_id))
        await guild.unban(user)
        
        # Получаем log_channel_id
        log_channel_id = None
        if str(user_id) in active_punishments["bans"]:
            log_channel_id = active_punishments["bans"][str(user_id)].get("log_channel_id")
            print(f"🔍 UNBAN: log_channel_id = {log_channel_id}")
            del active_punishments["bans"][str(user_id)]
            sync_punishments_to_sheet()
        else:
            print(f"⚠️ UNBAN: user_id {user_id} не найден в active_punishments['bans']")
        
        log_to_moderation_sheet("unban", user_id, user.name, "Admin Panel", "Бан снят", None, guild_id, guild.name)
        log_to_activity_sheet("unban", user.id, user.name, "Бан снят", guild.id, guild.name)
        
        # Отправляем уведомление
        if log_channel_id:
            print(f"✅ UNBAN: Отправляем уведомление в канал {log_channel_id}")
            await send_moderation_log(guild, log_channel_id, 'unban', user, 'Бан снят', None)
        else:
            print(f"❌ UNBAN: log_channel_id пустой, уведомление не отправлено")
    
    future = asyncio.run_coroutine_threadsafe(unban(), bot.loop)
    future.result(timeout=10)
    return jsonify({"success": True})

@app.route('/api/guilds/<guild_id>/members/<user_id>/warnings', methods=['DELETE'])
@require_auth
def clear_warnings(guild_id, user_id):
    """Очистить все предупреждения пользователя"""
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    member = guild.get_member(int(user_id))
    
    # ✅ Берём log_channel_id из тела запроса (приоритет) или из Excel
    data = request.json or {}
    log_channel_id = data.get('log_channel_id')
    print(f"🔍 CLEAR WARNINGS: log_channel_id из запроса = {log_channel_id}")
    
    # Если не передан, берём из Excel
    if not log_channel_id and SHEETS_ENABLED and warnings_sheet:
        try:
            all_records = warnings_sheet.get_all_records()
            user_warnings = [
                r for r in all_records
                if str(r.get('User ID')) == str(user_id)
                and str(r.get('Guild ID')) == str(guild_id)
                and r.get('Status') == 'active'
            ]
            if user_warnings:
                last_warn = user_warnings[-1]
                log_channel_id = last_warn.get('Log Channel ID')
                print(f"✅ CLEAR WARNINGS: Нашёл log_channel_id = {log_channel_id} из Excel")
        except Exception as e:
            print(f"❌ CLEAR WARNINGS: Ошибка чтения Excel: {e}")
    
    print(f"🎯 CLEAR WARNINGS: Итоговый log_channel_id = {log_channel_id}")
    
    clear_user_warnings(user_id, guild_id)
    log_to_activity_sheet("warnings_cleared", user_id, "User", "Все предупреждения очищены (Admin Panel)", guild_id, None)
    
    # ✅ Отправляем уведомление
    if log_channel_id and member:
        async def send_clear_notification():
            print(f"✅ CLEAR WARNINGS: Отправляем уведомление в канал {log_channel_id}")
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                embed = discord.Embed(
                    title="✅ Предупреждения очищены",
                    description=f"Пользователь {member.mention}",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Причина", value="Все предупреждения сняты", inline=False)
                embed.set_footer(text="Модератор: Admin Panel")
                await channel.send(embed=embed)
        
        asyncio.run_coroutine_threadsafe(send_clear_notification(), bot.loop)
    else:
        print(f"❌ CLEAR WARNINGS: log_channel_id пустой или member не найден")
    
    return jsonify({"success": True})

@app.route('/api/guilds/<guild_id>/members/<user_id>/warn', methods=['POST'])
@require_auth
def warn_member(guild_id, user_id):
    """Выдать предупреждение пользователю"""
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    member = guild.get_member(int(user_id))
    if not member: return jsonify({"error": "Участник не найден"}), 404
    
    data = request.json
    reason = data.get('reason', 'Нарушение правил')
    log_channel_id = data.get('log_channel_id')  # ID канала для логирования
    
    # Добавляем предупреждение
    warnings_count = add_warning(user_id, member.name, "Admin Panel", reason, guild_id, guild.name, log_channel_id)
    
    # Логирование
    log_to_moderation_sheet("warning", user_id, member.name, "Admin Panel", reason, None, guild_id, guild.name)
    log_to_activity_sheet("warning", member.id, member.name, f"Предупреждение ({warnings_count}/3). Причина: {reason}", guild.id, guild.name)
    
    async def send_log_and_check():
        # Отправляем сообщение в канал логов
        if log_channel_id:
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                embed = discord.Embed(
                    title="⚠️ Предупреждение",
                    description=f"Пользователь {member.mention} получил предупреждение",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Причина", value=reason, inline=False)
                embed.add_field(name="Количество предупреждений", value=f"{warnings_count}/3", inline=True)
                embed.set_footer(text=f"Модератор: Admin Panel")
                await channel.send(embed=embed)
        
        # Проверяем: если 3 предупреждения - бан на сутки
        if warnings_count >= 3:
            ban_duration = 86400  # 24 часа в секундах
            ban_until = datetime.now() + timedelta(seconds=ban_duration)
            
            await member.ban(reason=f"Автобан: 3 предупреждения")
            
            active_punishments["bans"][str(user_id)] = {
                "guild_id": str(guild_id),
                "reason": "Автобан: 3 предупреждения",
                "start_time": datetime.now().isoformat(),
                "until": ban_until.isoformat(),
                "moderator": "Auto (Admin Panel)",
                "user_name": member.name,
                "log_channel_id": log_channel_id  # Сохраняем для уведомления
            }
            sync_punishments_to_sheet()
            log_to_moderation_sheet("ban", user_id, member.name, "Auto (Admin Panel)", "Автобан: 3 предупреждения", "24h", guild_id, guild.name)
            log_to_activity_sheet("ban", member.id, member.name, f"Автобан на 24ч: 3 предупреждения", guild.id, guild.name)
            clear_user_warnings(user_id, guild_id)
            
            if log_channel_id:
                channel = guild.get_channel(int(log_channel_id))
                if channel:
                    embed = discord.Embed(
                        title="🚫 Автобан",
                        description=f"{member.mention} забанен на 24 часа",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Причина", value="3 предупреждения", inline=False)
                    embed.add_field(name="Длительность", value="24 часа", inline=True)
                    await channel.send(embed=embed)
            
            return {"auto_banned": True, "warnings": warnings_count}
        
        return {"auto_banned": False, "warnings": warnings_count}
    
    future = asyncio.run_coroutine_threadsafe(send_log_and_check(), bot.loop)
    result = future.result(timeout=10)
    return jsonify({"success": True, **result})

@app.route('/api/guilds/<guild_id>/members/<user_id>/warnings', methods=['GET'])
@require_auth
def get_member_warnings(guild_id, user_id):
    """Получить количество предупреждений пользователя"""
    warnings_count = get_user_warnings(user_id, guild_id)
    return jsonify({"warnings": warnings_count})

@app.route('/api/guilds/<guild_id>/punishments', methods=['GET'])
@require_auth
def get_punishments(guild_id):
    guild_mutes = {k: v for k, v in active_punishments["mutes"].items() if v["guild_id"] == str(guild_id)}
    guild_bans = {k: v for k, v in active_punishments["bans"].items() if v["guild_id"] == str(guild_id)}
    
    # Добавляем активные варны
    warnings = {}
    if SHEETS_ENABLED and warnings_sheet:
        try:
            all_records = warnings_sheet.get_all_records()
            for record in all_records:
                if (str(record.get('Guild ID')) == str(guild_id) 
                    and record.get('Status') == 'active'):
                    user_id = str(record.get('User ID'))
                    if user_id not in warnings:
                        warnings[user_id] = {
                            'username': record.get('Username'),
                            'warnings': [],
                            'count': 0
                        }
                    warnings[user_id]['warnings'].append({
                        'reason': record.get('Reason'),
                        'time': record.get('Timestamp'),
                        'moderator': record.get('Moderator')
                    })
                    warnings[user_id]['count'] = len(warnings[user_id]['warnings'])
        except Exception as e:
            print(f"⚠️ Ошибка чтения варнов: {e}")
    
    return jsonify({"mutes": guild_mutes, "bans": guild_bans, "warnings": warnings})

@app.route('/api/guilds/<guild_id>/members/<user_id>/roles/<role_id>', methods=['PUT'])
@require_auth
def add_role(guild_id, user_id, role_id):
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    member = guild.get_member(int(user_id))
    role = guild.get_role(int(role_id))
    if not member or not role: return jsonify({"error": "Участник или роль не найдены"}), 404
    
    async def add():
        await member.add_roles(role)
        log_to_activity_sheet("role_add", member.id, member.name, f"Роль {role.name} выдана (Admin Panel)", guild.id, guild.name)
    
    future = asyncio.run_coroutine_threadsafe(add(), bot.loop)
    future.result(timeout=10)
    return jsonify({"success": True})

@app.route('/api/guilds/<guild_id>/members/<user_id>/roles/<role_id>', methods=['DELETE'])
@require_auth
def remove_role(guild_id, user_id, role_id):
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    member = guild.get_member(int(user_id))
    role = guild.get_role(int(role_id))
    if not member or not role: return jsonify({"error": "Участник или роль не найдены"}), 404
    
    async def remove():
        await member.remove_roles(role)
        log_to_activity_sheet("role_remove", member.id, member.name, f"Роль {role.name} забрана (Admin Panel)", guild.id, guild.name)
    
    future = asyncio.run_coroutine_threadsafe(remove(), bot.loop)
    future.result(timeout=10)
    return jsonify({"success": True})



@app.route('/api/guilds/<guild_id>/channels', methods=['GET'])
@require_auth
def get_guild_channels(guild_id):
    """Возвращает список каналов сервера"""
    try:
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({'error': 'Guild not found'}), 404
        
        channels = []
        for channel in guild.channels:
            channels.append({
                'id': str(channel.id),
                'name': channel.name,
                'type': channel.type.value,  # 0 - text, 2 - voice, 4 - category, etc.
                'position': channel.position,
                'category_id': str(channel.category_id) if channel.category_id else None
            })
        
        # Сортируем по позиции как в дискорде
        channels.sort(key=lambda c: c['position'])
        
        print(f"📡 Возвращено {len(channels)} каналов для guild {guild_id}")
        return jsonify(channels), 200
    
    except Exception as e:
        print(f"❌ Get Channels Error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/guilds/<guild_id>/channels/excel', methods=['GET'])
@require_auth
def get_channels_from_excel(guild_id):
    try:
        print(f"📊 GET /api/guilds/{guild_id}/channels/excel")
        
        # Получаем каналы из Excel
        text_channels = get_text_channels_from_excel(guild_id)
        
        return jsonify(text_channels), 200
    except Exception as e:
        print(f"❌ Error getting channels from Excel: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/guilds/<guild_id>/channels/sync', methods=['POST'])
@require_auth
def sync_channels_api(guild_id):
    """Синхронизировать каналы сервера в Excel (вручную)"""
    try:
        print(f"📊 POST /api/guilds/{guild_id}/channels/sync")
        
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({'error': 'Guild not found'}), 404
        
        # Синхронизируем каналы
        sync_channels_to_excel(guild)
        
        return jsonify({'success': True, 'message': 'Каналы синхронизированы'}), 200
    except Exception as e:
        print(f"❌ Error syncing channels: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/guilds/<guild_id>/channels', methods=['POST'])
@require_auth
def create_channel(guild_id):
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
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
        log_to_activity_sheet("channel_create", None, "Admin Panel", f"Создан канал {channel.name}", guild.id, guild.name)
        return channel
    
    future = asyncio.run_coroutine_threadsafe(create(), bot.loop)
    channel = future.result(timeout=10)
    if channel:
        return jsonify({"id": str(channel.id), "success": True})
    else:
        return jsonify({"error": "Не удалось создать канал"}), 400

@app.route('/api/channels/<channel_id>', methods=['DELETE'])
@require_auth
def delete_channel(channel_id):
    channel = bot.get_channel(int(channel_id))
    if not channel: return jsonify({"error": "Канал не найден"}), 404
    
    async def delete():
        channel_name = channel.name
        guild_id = channel.guild.id
        guild_name = channel.guild.name
        await channel.delete()
        log_to_activity_sheet("channel_delete", None, "Admin Panel", f"Канал {channel_name} удалён", guild_id, guild_name)
    
    future = asyncio.run_coroutine_threadsafe(delete(), bot.loop)
    future.result(timeout=10)
    return jsonify({"success": True})

@app.route('/api/roles/<role_id>', methods=['DELETE'])
@require_auth
def delete_role(role_id):
    """Delete a role from the guild"""
    try:
        # Находим роль во всех гильдиях
        role = None
        guild = None
        for g in bot.guilds:
            r = g.get_role(int(role_id))
            if r:
                role = r
                guild = g
                break
        
        if not role:
            return jsonify({"error": "Роль не найдена"}), 404
        
        # Проверяем, что это не @everyone
        if role.is_default():
            return jsonify({"error": "Нельзя удалить роль @everyone"}), 400
        
        # Проверяем, что роль бота не выше удаляемой
        if role >= guild.me.top_role:
            return jsonify({"error": "Роль бота ниже удаляемой роли"}), 403
        
        async def delete():
            role_name = role.name
            guild_id = guild.id
            guild_name = guild.name
            await role.delete(reason="Удалено через Admin Panel")
            log_to_activity_sheet("role_delete", None, "Admin Panel", f"Роль {role_name} удалена", guild_id, guild_name)
        
        future = asyncio.run_coroutine_threadsafe(delete(), bot.loop)
        future.result(timeout=10)
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Ошибка удаления роли: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/guilds/<guild_id>/reaction-roles', methods=['POST'])
@require_auth
def create_reaction_role(guild_id):
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    data = request.json
    channel_id = data.get('channel_id')
    message_text = data.get('message')
    reactions = data.get('reactions', [])
    channel = bot.get_channel(int(channel_id))
    if not channel: return jsonify({"error": "Канал не найден"}), 404
    
    async def create():
        message = await channel.send(message_text)
        for reaction in reactions:
            await message.add_reaction(reaction['emoji'])
            
            # Логируем в ReactionRoles sheet
            if SHEETS_ENABLED and reaction_roles_sheet:
                try:
                    role = guild.get_role(int(reaction['role_id']))
                    reaction_roles_sheet.append_row([
                        str(message.id),
                        str(channel.id),
                        channel.name,
                        reaction['emoji'],
                        reaction['role_id'],
                        role.name if role else '',
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        str(guild.id),
                        guild.name
                    ])
                except Exception as e:
                    print(f"⚠️ Ошибка записи ReactionRole: {e}")
        
        reaction_roles_db[str(message.id)] = {
            "channel_id": str(channel_id),
            "guild_id": str(guild_id),
            "message": message_text,
            "reactions": reactions
        }
        save_rr_db()
        log_to_activity_sheet("reaction_role_create", None, "Admin Panel",
                             f"Создана система ролей за реакции ({len(reactions)} реакций) в #{channel.name}",
                             guild.id, guild.name)
        return message
    
    future = asyncio.run_coroutine_threadsafe(create(), bot.loop)
    message = future.result(timeout=10)
    return jsonify({"message_id": str(message.id), "success": True})

@app.route('/api/guilds/<guild_id>/reaction-roles', methods=['GET'])
@require_auth
def get_reaction_roles(guild_id):
    guild_rr = {k: v for k, v in reaction_roles_db.items() if v.get("guild_id") == str(guild_id)}
    return jsonify(guild_rr)

@app.route('/api/reaction-roles/<message_id>', methods=['PUT'])
@require_auth
def update_reaction_role(message_id):
    """Обновить роли для реакций"""
    if message_id not in reaction_roles_db:
        return jsonify({"error": "Сообщение не найдено"}), 404
    
    data = request.json
    new_reactions = data.get('reactions', [])
    
    # Обновляем реакции
    reaction_roles_db[message_id]['reactions'] = new_reactions
    reaction_roles_db[message_id]['unconfigured'] = False  # Теперь настроено
    save_rr_db()
    
    # Логирование в Google Sheets
    if SHEETS_ENABLED and reaction_roles_sheet:
        try:
            guild_id = reaction_roles_db[message_id]['guild_id']
            channel_id = reaction_roles_db[message_id]['channel_id']
            guild = bot.get_guild(int(guild_id))
            channel = bot.get_channel(int(channel_id))
            
            for reaction in new_reactions:
                if reaction['role_id']:
                    role = guild.get_role(int(reaction['role_id'])) if guild else None
                    reaction_roles_sheet.append_row([
                        message_id,
                        channel_id,
                        channel.name if channel else '',
                        reaction['emoji'],
                        reaction['role_id'],
                        role.name if role else '',
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        guild_id,
                        guild.name if guild else ''
                    ])
        except Exception as e:
            print(f"⚠️ Ошибка записи ReactionRole: {e}")
    
    return jsonify({"success": True})

@app.route('/api/reaction-roles/<message_id>', methods=['DELETE'])
@require_auth
def delete_reaction_role(message_id):
    if message_id in reaction_roles_db:
        del reaction_roles_db[message_id]
        save_rr_db()
        return jsonify({"success": True})
    return jsonify({"error": "Не найдено"}), 404

# === WELCOME SYSTEM ===
@app.route('/api/guilds/<guild_id>/welcomes', methods=['POST'])
@require_auth
def create_welcome(guild_id):
    """Настроить действие по реакции на существующее сообщение"""
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Сервер не найден"}), 404
    data = request.json
    message_id = data.get('message_id')  # ID существующего сообщения
    target_channel_id = data.get('target_channel_id')  # Канал для отправки
    welcome_message = data.get('welcome_message', '🎉 Добро пожаловать, {user}!')
    
    if not message_id or message_id not in reaction_roles_db:
        return jsonify({"error": "Сообщение не найдено"}), 404
    
    target_channel = bot.get_channel(int(target_channel_id))
    if not target_channel:
        return jsonify({"error": "Канал не найден"}), 404
    
    # Получаем инфо о сообщении
    rr_data = reaction_roles_db[message_id]
    source_channel = bot.get_channel(int(rr_data["channel_id"]))
    
    # Сохраняем конфигурацию действия
    welcome_configs[message_id] = {
        "guild_id": str(guild_id),
        "source_channel_id": rr_data["channel_id"],
        "target_channel_id": str(target_channel_id),
        "message": welcome_message
    }
    save_welcome_db()
    
    # Запись в Google Sheets
    if SHEETS_ENABLED and welcomes_sheet:
        try:
            welcomes_sheet.append_row([
                str(guild.id),
                guild.name,
                message_id,
                rr_data["channel_id"],
                str(target_channel_id),
                target_channel.name,
                welcome_message,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        except Exception as e:
            print(f"⚠️ Ошибка записи Welcome: {e}")
    
    log_to_activity_sheet("welcome_action_create", None, "Admin Panel",
                         f"Настроено действие: #{source_channel.name if source_channel else 'удалён'} → #{target_channel.name}",
                         guild.id, guild.name)
    
    return jsonify({"message_id": message_id, "success": True})

@app.route('/api/guilds/<guild_id>/welcomes', methods=['GET'])
@require_auth
def get_welcomes(guild_id):
    """Получить список приветствий"""
    guild_welcomes = {k: v for k, v in welcome_configs.items() if v.get("guild_id") == str(guild_id)}
    return jsonify(guild_welcomes)

@app.route('/api/welcomes/<message_id>', methods=['DELETE'])
@require_auth
def delete_welcome(message_id):
    """Удалить систему приветствий"""
    if message_id in welcome_configs:
        del welcome_configs[message_id]
        save_welcome_db()
        return jsonify({"success": True})
    return jsonify({"error": "Не найдено"}), 404

# === TEMPORARY ROOMS API ===
# (Эндпоинт /api/channels/<channel_id>/messages уже определён выше в строке 1079)

@app.route('/api/activity', methods=['GET'])
@require_auth
def get_activity():
    """Получение активности из Google Sheets или локального лога"""
    filter_type = request.args.get('type', 'all')  # Получаем фильтр
    limit = request.args.get('limit', 100, type=int)
    
    if SHEETS_ENABLED and activity_sheet:
        try:
            all_records = activity_sheet.get_all_records()
            print(f"📊 Activity: загружено {len(all_records)} записей из Google Sheets")
            if len(all_records) > 0:
                print(f"🔍 Первая запись: {all_records[-1]}")
            
            # Фильтруем по типу
            if filter_type != 'all':
                # Маппинг фильтров на типы событий
                filter_mapping = {
                    'members': ['member_join', 'member_leave'],
                    'roles': ['role_add', 'role_remove', 'reaction_role_add', 'reaction_role_remove'],
                    'moderation': ['mute', 'unmute', 'kick', 'ban', 'unban'],
                    'channels': ['channel_create', 'channel_delete'],
                    'messages': ['message_sent', 'message_bulk_delete'],
                    'system': ['system']
                }
                allowed_types = filter_mapping.get(filter_type, [])
                filtered_records = [r for r in all_records if r.get('Event Type') in allowed_types]
                print(f"🔍 Фильтр '{filter_type}': найдено {len(filtered_records)} записей")
            else:
                filtered_records = all_records
                print(f"🔍 Фильтр 'all': показано {len(filtered_records)} записей")
            
            # Преобразуем в формат фронтенда
            formatted = []
            for record in filtered_records[-limit:][::-1]:  # Последние N в обратном порядке
                event_type = record.get('Event Type', '')
                username = record.get('Username', '')
                details = record.get('Details', '')
                
                # Создаём title и description
                if username:
                    title = f"{username}"
                    description = details
                else:
                    title = event_type.replace('_', ' ').title()
                    description = details
                
                # Иконки и цвета по типу
                icon_map = {
                    "member_join": "fas fa-user-plus",
                    "member_leave": "fas fa-user-minus",
                    "role_add": "fas fa-user-tag",
                    "role_remove": "fas fa-user-minus",
                    "channel_create": "fas fa-plus",
                    "channel_delete": "fas fa-trash",
                    "reaction_role_add": "fas fa-smile",
                    "reaction_role_remove": "fas fa-frown",
                    "message_sent": "fas fa-paper-plane",
                    "message_bulk_delete": "fas fa-trash",
                    "mute": "fas fa-volume-mute",
                    "unmute": "fas fa-volume-up",
                    "kick": "fas fa-user-slash",
                    "ban": "fas fa-ban",
                    "unban": "fas fa-user-check",
                    "system": "fas fa-power-off"
                }
                
                color_map = {
                    "member_join": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                    "member_leave": "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)",
                    "role_add": "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
                    "role_remove": "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)",
                    "channel_create": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
                    "channel_delete": "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)",
                    "reaction_role_add": "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
                    "reaction_role_remove": "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)",
                    "message_sent": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
                    "message_bulk_delete": "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)",
                    "mute": "linear-gradient(135deg, #faa81a 0%, #f5576c 100%)",
                    "unmute": "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
                    "kick": "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)",
                    "ban": "linear-gradient(135deg, #ed4245 0%, #f5576c 100%)",
                    "unban": "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
                    "system": "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)"
                }
                
                formatted.append({
                    "type": event_type,
                    "title": title,
                    "description": description,
                    "icon": icon_map.get(event_type, "fas fa-circle"),
                    "color": color_map.get(event_type, "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"),
                    "user_id": record.get('User ID', ''),
                    "username": username,
                    "guild_id": record.get('Guild ID', ''),
                    "guild_name": record.get('Guild Name', ''),
                    "time": record.get('Timestamp', '')
                })
            return jsonify(formatted)
        except Exception as e:
            print(f"⚠️ Ошибка чтения Activity: {e}")
    
    # Fallback на локальный лог
    limit = request.args.get('limit', 100, type=int)
    return jsonify(activity_log[:limit])

@app.route('/api/moderation/history', methods=['GET'])
@require_auth
def get_moderation_history():
    """Получение истории модерации из Google Sheets или локального лога"""
    if SHEETS_ENABLED and moderation_sheet:
        try:
            all_records = moderation_sheet.get_all_records()
            # Преобразуем в формат фронтенда
            formatted = []
            for record in all_records[-50:][::-1]:  # Последние 50
                formatted.append({
                    "action": record.get('Action', ''),
                    "user_id": record.get('Target User ID', ''),
                    "username": record.get('Target Username', ''),
                    "moderator": record.get('Moderator', ''),
                    "reason": record.get('Reason', ''),
                    "duration": record.get('Duration', ''),
                    "guild_id": record.get('Guild ID', ''),
                    "guild_name": record.get('Guild Name', ''),
                    "time": record.get('Timestamp', ''),
                    "icon": {
                        "mute": "fas fa-volume-mute",
                        "kick": "fas fa-user-slash",
                        "ban": "fas fa-ban",
                        "unmute": "fas fa-volume-up",
                        "unban": "fas fa-user-check"
                    }.get(record.get('Action', ''), "fas fa-shield-alt")
                })
            return jsonify(formatted)
        except Exception as e:
            print(f"⚠️ Ошибка чтения Moderation: {e}")
    
    # Fallback
    limit = request.args.get('limit', 50, type=int)
    return jsonify(moderation_log[:limit])

# === USER INFO ===
@app.route('/api/guilds/<guild_id>/members/<user_id>/info', methods=['GET'])
@require_auth
def get_user_info(guild_id, user_id):
    """Получить полную информацию о пользователе"""
    print(f"🔍 Get user info: guild={guild_id}, user={user_id}")
    try:
        punishments_count = 0
        warnings_count = 0
        moderation_history = []
        
        if SHEETS_ENABLED and moderation_sheet:
            try:
                print("✅ Sheets enabled, loading moderation records...")
                records = moderation_sheet.get_all_records()
                print(f"📊 Total moderation records: {len(records)}")
                user_records = [r for r in records if str(r.get('Target User ID')) == str(user_id)]
                punishments_count = len(user_records)
                print(f"✅ User {user_id}: found {punishments_count} punishments")
                
                # Формируем историю модерации
                for r in user_records:
                    moderation_history.append({
                        'action': r.get('Action', ''),
                        'reason': r.get('Reason', ''),
                        'moderator': r.get('Moderator', ''),
                        'timestamp': r.get('Timestamp', ''),
                        'duration': r.get('Duration', ''),
                        'icon': {
                            'mute': 'fas fa-volume-mute',
                            'kick': 'fas fa-user-slash',
                            'ban': 'fas fa-ban',
                            'unmute': 'fas fa-volume-up',
                            'unban': 'fas fa-user-check',
                            'warn': 'fas fa-exclamation-triangle'
                        }.get(r.get('Action', '').lower(), 'fas fa-shield-alt')
                    })
                
                if len(user_records) > 0:
                    print(f"Sample: {user_records[0]}")
            except Exception as e:
                print(f"❌ Error counting punishments: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("⚠️ Sheets not enabled or moderation_sheet is None")
        if SHEETS_ENABLED and warnings_sheet:
            try:
                print("✅ Loading warnings records...")
                records = warnings_sheet.get_all_records()
                print(f"📊 Total warning records: {len(records)}")
                user_warnings = [r for r in records if str(r.get('User ID')) == str(user_id) and r.get('Status') == 'Active']
                warnings_count = len(user_warnings)
                print(f"✅ User {user_id}: found {warnings_count} active warnings")
                if len(user_warnings) > 0:
                    print(f"Sample: {user_warnings[0]}")
            except Exception as e:
                print(f"❌ Error counting warnings: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("⚠️ Sheets not enabled or warnings_sheet is None")
        result = {
            "punishments_count": punishments_count, 
            "warnings_count": warnings_count,
            "moderation_history": moderation_history
        }
        print(f"✅ Returning: punishments={punishments_count}, warnings={warnings_count}, history={len(moderation_history)} items")
        return jsonify(result)
    except Exception as e:
        print(f"❌ Error getting user info: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"punishments_count": 0, "warnings_count": 0})

@app.route('/api/guilds/<guild_id>/activity-stats', methods=['GET'])
@require_auth
def get_activity_stats(guild_id):
    """Получить статистику активности пользователей"""
    print(f"📊 Loading activity stats for guild {guild_id}")
    
    try:
        period = request.args.get('period', '30')
        
        # Вычисляем дату начала периода
        if period != 'all':
            days = int(period)
            start_date = dt.datetime.now() - dt.timedelta(days=days)
        else:
            start_date = None
        
        user_stats = {}
        
        # 1. Считаем сообщения из Messages sheet
        if SHEETS_ENABLED and messages_sheet:
            try:
                print("✅ Loading messages from Google Sheets...")
                records = messages_sheet.get_all_records()
                
                for record in records:
                    # Проверяем Guild ID
                    if str(record.get('Guild ID')) != str(guild_id):
                        continue
                    
                    # Проверяем дату
                    if start_date:
                        try:
                            msg_date = dt.datetime.strptime(record.get('Timestamp', ''), '%Y-%m-%d %H:%M:%S')
                            if msg_date < start_date:
                                continue
                        except:
                            continue
                    
                    # Получаем User ID из "Sent By" (формат: "Username (ID)")
                    sent_by = record.get('Sent By', '')
                    if '(' in sent_by and ')' in sent_by:
                        user_id = sent_by.split('(')[-1].split(')')[0]
                        
                        if user_id not in user_stats:
                            user_stats[user_id] = {'messages': 0, 'reactions': 0}
                        
                        user_stats[user_id]['messages'] += 1
                
                print(f"✅ Processed {len(records)} message records")
            except Exception as e:
                print(f"❌ Error loading messages: {e}")
        
        # 2. Считаем реакции из Activity sheet
        if SHEETS_ENABLED and activity_sheet:
            try:
                print("✅ Loading reactions from Activity sheet...")
                records = activity_sheet.get_all_records()
                
                for record in records:
                    # Проверяем Guild ID
                    if str(record.get('Guild ID')) != str(guild_id):
                        continue
                    
                    # Только реакции
                    if record.get('Event Type') != 'add_reaction':
                        continue
                    
                    # Проверяем дату
                    if start_date:
                        try:
                            event_date = dt.datetime.strptime(record.get('Timestamp', ''), '%Y-%m-%d %H:%M:%S')
                            if event_date < start_date:
                                continue
                        except:
                            continue
                    
                    user_id = str(record.get('User ID', ''))
                    if user_id:
                        if user_id not in user_stats:
                            user_stats[user_id] = {'messages': 0, 'reactions': 0}
                        
                        user_stats[user_id]['reactions'] += 1
                
                print(f"✅ Processed {len(records)} activity records")
            except Exception as e:
                print(f"❌ Error loading reactions: {e}")
        
        print(f"✅ Total users with activity: {len(user_stats)}")
        
        return jsonify({
            "users": user_stats,
            "period": period
        })
        
    except Exception as e:
        print(f"❌ Error getting activity stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"users": {}, "period": period}), 500

SWEAR_WORDS = [
    r'\b(bl[yi]a?t|blyad|fuck|shi[t]+|cyka|suka|pidaras|pidoras|p[ie]zd[aey]|hui|хуй|бляд|пизд|ебан|еб[ауоы]|сук[аи]|пидор|говн|мудак)\b'
]

# === SUSPICIOUS ACTIVITY CONFIG ===
@app.route('/api/guilds/<guild_id>/suspicious-config', methods=['GET'])
@require_auth
def get_suspicious_config(guild_id):
    """Получить конфигурацию подозрительной активности"""
    return jsonify({
        'triggers': get_trigger_words(guild_id),
        'excluded_channels': get_excluded_channels(guild_id),
        'default_triggers': DEFAULT_TRIGGERS
    })

@app.route('/api/guilds/<guild_id>/suspicious-config/triggers', methods=['POST'])
@require_auth
def add_suspicious_trigger(guild_id):
    """Добавить триггер-слово"""
    data = request.json
    word = data.get('word', '').strip()
    if not word:
        return jsonify({'error': 'Слово не может быть пустым'}), 400
    
    if add_trigger_word(guild_id, word):
        print(f"✅ Added trigger word '{word}' for guild {guild_id}")
        return jsonify({'success': True, 'word': word})
    else:
        return jsonify({'error': 'Ошибка добавления'}), 500

@app.route('/api/guilds/<guild_id>/suspicious-config/triggers/<word>', methods=['DELETE'])
@require_auth
def delete_suspicious_trigger(guild_id, word):
    """Удалить триггер-слово"""
    if remove_trigger_word(guild_id, word):
        print(f"✅ Removed trigger word '{word}' for guild {guild_id}")
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Слово не найдено'}), 404

@app.route('/api/guilds/<guild_id>/suspicious-config/excluded-channels', methods=['POST'])
@require_auth
def add_suspicious_excluded_channel(guild_id):
    """Добавить канал в исключения"""
    data = request.json
    channel_id = data.get('channel_id', '').strip()
    if not channel_id:
        return jsonify({'error': 'Канал не указан'}), 400
    
    if add_excluded_channel(guild_id, channel_id):
        print(f"✅ Added excluded channel {channel_id} for guild {guild_id}")
        return jsonify({'success': True, 'channel_id': channel_id})
    else:
        return jsonify({'error': 'Ошибка добавления'}), 500

@app.route('/api/guilds/<guild_id>/suspicious-config/excluded-channels/<channel_id>', methods=['DELETE'])
@require_auth
def delete_suspicious_excluded_channel(guild_id, channel_id):
    """Удалить канал из исключений"""
    if remove_excluded_channel(guild_id, channel_id):
        print(f"✅ Removed excluded channel {channel_id} for guild {guild_id}")
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Канал не найден'}), 404

@app.route('/api/guilds/<guild_id>/suspicious-messages', methods=['GET'])
@require_auth
def get_suspicious_messages(guild_id):
    """Получить подозрительные сообщения (мат, оскорбления)"""
    print(f"🔍 Loading suspicious messages for guild {guild_id}")
    
    suspicious = []
    
    # Читаем из отдельного листа Suspicious
    if SHEETS_ENABLED and suspicious_sheet:
        try:
            records = suspicious_sheet.get_all_records()
            print(f"📊 Total suspicious messages in sheet: {len(records)}")
            
            for record in records:
                if str(record.get('Guild ID')) != str(guild_id):
                    continue
                
                suspicious.append({
                    'user_id': str(record.get('User ID', '')),
                    'username': record.get('Username', ''),
                    'content': record.get('Content', ''),
                    'channel_name': record.get('Channel', ''),
                    'timestamp': record.get('Timestamp', ''),
                    'avatar': None
                })
            
            print(f"✅ Found {len(suspicious)} suspicious messages for guild {guild_id}")
        except Exception as e:
            print(f"❌ Error loading suspicious messages: {e}")
            import traceback
            traceback.print_exc()
    
    return jsonify(suspicious)

# --- SELF-PING ---

# ==================== TEMPORARY ROOMS API ====================

# Хранилище активных временных комнат
temp_rooms = {}  # {channel_id: {info}}
temp_room_tasks = {}  # {channel_id: asyncio.Task}

# Функции для работы с Google Sheets
def save_temp_room_to_sheet(room_info):
    """Сохранить временную комнату в Google Sheets"""
    if SHEETS_ENABLED and temp_rooms_sheet:
        try:
            temp_rooms_sheet.append_row([
                room_info['channel_id'],
                room_info['room_name'],
                room_info['owner_id'],
                room_info['owner_name'],
                room_info['role_id'],
                room_info['duration'],
                room_info['user_limit'],
                room_info['created_at'],
                room_info['expires_at'],
                room_info['guild_id'],
                room_info.get('guild_name', ''),
                'active'
            ])
            print(f"📊 Комната {room_info['full_name']} сохранена в Google Sheets")
        except Exception as e:
            print(f"⚠️ Ошибка сохранения в Sheets: {e}")

def update_temp_room_status(channel_id, status):
    """Обновить статус комнаты в Google Sheets"""
    if SHEETS_ENABLED and temp_rooms_sheet:
        try:
            records = temp_rooms_sheet.get_all_records()
            for idx, record in enumerate(records, start=2):
                if str(record.get('Channel ID')) == str(channel_id):
                    temp_rooms_sheet.update_cell(idx, 12, status)  # Колонка Status
                    print(f"📊 Статус комнаты {channel_id} обновлён: {status}")
                    break
        except Exception as e:
            print(f"⚠️ Ошибка обновления статуса в Sheets: {e}")

def load_active_rooms_from_sheet():
    """Загрузить активные комнаты из Google Sheets при запуске"""
    if not SHEETS_ENABLED or not temp_rooms_sheet:
        return
    
    try:
        records = temp_rooms_sheet.get_all_records()
        active_count = 0
        
        for record in records:
            if record.get('Status') == 'active':
                channel_id = str(record.get('Channel ID', ''))
                
                # Проверяем, существует ли канал
                try:
                    channel_int = int(channel_id)
                    channel = bot.get_channel(channel_int)
                    
                    if channel:
                        # Канал существует, восстанавливаем в память
                        temp_rooms[channel_id] = {
                            'channel_id': channel_id,
                            'room_name': record.get('Room Name', ''),
                            'full_name': f"Private_{record.get('Room Name', '')}",
                            'owner_id': str(record.get('Owner ID', '')),
                            'owner_name': record.get('Owner Name', ''),
                            'role_id': str(record.get('Role ID', '')),
                            'duration': int(record.get('Duration', 60)),
                            'user_limit': int(record.get('User Limit', 10)),
                            'created_at': record.get('Created At', ''),
                            'expires_at': record.get('Expires At', ''),
                            'guild_id': str(record.get('Guild ID', '')),
                            'guild_name': record.get('Guild Name', '')
                        }
                        
                        # Запускаем таймер удаления
                        expires_at = datetime.fromisoformat(record.get('Expires At', ''))
                        now = datetime.now()
                        remaining_seconds = max(0, int((expires_at - now).total_seconds()))
                        
                        if remaining_seconds > 0:
                            role_id = int(record.get('Role ID', 0))
                            task = asyncio.create_task(auto_delete_room(channel_int, role_id, remaining_seconds))
                            temp_room_tasks[channel_id] = task
                            active_count += 1
                            print(f"⚙️ Восстановлена комната: {temp_rooms[channel_id]['full_name']} (осталось {remaining_seconds//60} мин)")
                        else:
                            # Время истекло, удаляем
                            print(f"⏰ Комната {channel_id} просрочена, удаляем...")
                            asyncio.create_task(cleanup_expired_room(channel_int, int(record.get('Role ID', 0))))
                    else:
                        # Канал не существует, обновляем статус
                        update_temp_room_status(channel_id, 'deleted')
                        print(f"🗑️ Канал {channel_id} не найден, помечен как удалённый")
                except ValueError:
                    print(f"⚠️ Некорректный ID канала: {channel_id}")
        
        if active_count > 0:
            print(f"✅ Восстановлено {active_count} активных комнат из Google Sheets")
    except Exception as e:
        print(f"❌ Ошибка загрузки комнат из Sheets: {e}")
        import traceback
        traceback.print_exc()

async def cleanup_expired_room(channel_id, role_id):
    """Очистка просроченной комнаты"""
    try:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.delete(reason="Просроченная комната")
        
        for guild in bot.guilds:
            role = guild.get_role(role_id)
            if role:
                await role.delete(reason="Удаление роли просроченной комнаты")
                break
        
        update_temp_room_status(str(channel_id), 'expired')
    except Exception as e:
        print(f"❌ Ошибка очистки комнаты: {e}")

@app.route('/api/guilds/<guild_id>/temp-rooms', methods=['POST'])
@require_auth
def create_temp_room(guild_id):
    """Создать временную голосовую комнату"""
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    data = request.json
    room_name = data.get('room_name', '').strip()
    duration = int(data.get('duration_minutes', 60))  # в минутах
    user_limit = int(data.get('user_limit', 10))
    user_id = data.get('user_id')
    message_id = data.get('message_id')
    channel_id = data.get('channel_id')
    message_text = data.get('message_text', '')  # Текст сообщения для поиска упоминаний
    
    # Валидация
    if not room_name or len(room_name) > 30:
        return jsonify({"error": "Некорректное название (1-30 символов)"}), 400
    
    if duration < 1 or duration > 90:
        return jsonify({"error": "Время должно быть от 1 до 90 минут"}), 400
    
    if user_limit < 1 or user_limit > 50:
        return jsonify({"error": "Лимит должен быть от 1 до 50"}), 400
    
    if not user_id or user_id == 'unknown':
        return jsonify({"error": "Не указан ID пользователя"}), 400
    
    try:
        # Проверяем что user_id - это число
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            return jsonify({"error": f"Некорректный ID пользователя: {user_id}"}), 400
        
        # Получаем пользователя
        user = guild.get_member(user_id_int)
        if not user:
            return jsonify({"error": "Пользователь не найден на сервере"}), 404
        
        # Получаем категорию
        category = guild.get_channel(int(ROOM_CATEGORY_ID))
        if not category:
            return jsonify({"error": "Категория для комнат не найдена"}), 404
        
        # Новая система именования: канал - просто название, роль - Room(название)
        voice_channel_name = room_name
        role_name = f"Room({room_name})"
        
        async def create_room():
            # Создаём роль
            role = await guild.create_role(
                name=role_name,
                mentionable=True,
                hoist=False,
                reason=f"Роль-ключ для временной комнаты {voice_channel_name}"
            )
            
            # Выдаём роль владельцу
            await user.add_roles(role)
            
            # Ищем упоминания пользователей в сообщении и выдаём им роль
            invited_users = []
            if message_id and channel_id:
                try:
                    request_channel = bot.get_channel(int(channel_id))
                    if request_channel:
                        original_message = await request_channel.fetch_message(int(message_id))
                        # Ищем всех упомянутых пользователей
                        for mentioned_user in original_message.mentions:
                            if mentioned_user.id != user.id:  # Не добавляем владельца повторно
                                await mentioned_user.add_roles(role)
                                invited_users.append(mentioned_user.name)
                                print(f"✅ Роль {role_name} выдана {mentioned_user.name}")
                except Exception as e:
                    print(f"⚠️ Ошибка при выдаче ролей упомянутым: {e}")
            
            # Создаём голосовой канал
            # Видимость: все видят, но подключиться могут только с ролью
            # Владелец получает право управлять ролями
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False),
                role: discord.PermissionOverwrite(connect=True, view_channel=True, speak=True),
                user: discord.PermissionOverwrite(connect=True, view_channel=True, speak=True, manage_roles=True),
                guild.me: discord.PermissionOverwrite(connect=True, view_channel=True, manage_channels=True, manage_roles=True)
            }
            
            voice_channel = await guild.create_voice_channel(
                name=voice_channel_name,
                category=category,
                user_limit=user_limit,
                overwrites=overwrites,
                reason=f"Временная комната для {user.name}"
            )
            
            # Отправляем личное сообщение пользователю (видимо только ему)
            try:
                # Формируем список пользователей с доступом
                access_list = [user.name]
                if invited_users:
                    access_list.extend(invited_users)
                access_text = ", ".join(access_list)
                
                dm_message = (
                    f"👋 **Привет, {user.name}!**\n\n"
                    f"🚀 Твоя приватная комната **{voice_channel_name}** готова!\n\n"
                    f"📊 **Информация:**\n"
                    f"⏰ Время: {duration} минут\n"
                    f"👥 Лимит: {user_limit} человек\n"
                    f"🔑 Кто имеет доступ: {access_text}\n\n"
                    f"⚠️ *Комната автоматически удалится через {duration} минут*\n\n"
                    f"ℹ️ У тебя и твоих друзей есть права подключаться к комнате **{voice_channel_name}**"
                )
                await user.send(dm_message)
                print(f"✉️ Личное сообщение отправлено {user.name}")
            except discord.Forbidden:
                print(f"⚠️ Не удалось отправить DM {user.name} (закрыты личные сообщения)")
                # Отправляем в канал заявок как запасной вариант
                if channel_id and message_id:
                    request_channel = bot.get_channel(int(REQUEST_CHANNEL_ID))
                    if request_channel:
                        try:
                            original_message = await request_channel.fetch_message(int(message_id))
                            await original_message.reply(
                                f"{user.mention} твоя комната **{full_room_name}** готова! ⏰ {duration}мин",
                                delete_after=60
                            )
                        except Exception as e:
                            print(f"⚠️ Ошибка отправки реплая: {e}")
            except Exception as e:
                print(f"⚠️ Ошибка отправки уведомления: {e}")
            
            # Сохраняем инфо о комнате
            created_at = datetime.now()
            expires_at = created_at + timedelta(minutes=duration)
            
            room_info = {
                'channel_id': str(voice_channel.id),
                'room_name': room_name,
                'full_name': voice_channel_name,
                'owner_id': str(user_id),
                'owner_name': user.name,
                'role_id': str(role.id),
                'role_name': role_name,
                'duration': duration,
                'user_limit': user_limit,
                'created_at': created_at.isoformat(),
                'expires_at': expires_at.isoformat(),
                'guild_id': str(guild_id),
                'guild_name': guild.name
            }
            
            temp_rooms[str(voice_channel.id)] = room_info
            
            # Сохраняем в Google Sheets
            save_temp_room_to_sheet(room_info)
            
            # Запускаем таймер удаления
            task = asyncio.create_task(auto_delete_room(voice_channel.id, role.id, duration * 60))
            temp_room_tasks[str(voice_channel.id)] = task
            
            print(f"✅ Создана временная комната: {voice_channel_name} (ID: {voice_channel.id}, Роль: {role_name})")
            
            return voice_channel.id, role.id
        
        future = asyncio.run_coroutine_threadsafe(create_room(), bot.loop)
        voice_channel_id, role_id = future.result(timeout=15)
        
        return jsonify({
            "success": True,
            "channel_id": str(voice_channel_id),
            "role_id": str(role_id),
            "room_name": voice_channel_name
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка создания временной комнаты: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/guilds/<guild_id>/temp-rooms', methods=['GET'])
@require_auth
def get_temp_rooms(guild_id):
    """Получить список активных временных комнат"""
    guild_rooms = [room for room in temp_rooms.values() if room['guild_id'] == guild_id]
    return jsonify(guild_rooms), 200

@app.route('/api/guilds/<guild_id>/temp-rooms/<channel_id>', methods=['DELETE'])
@require_auth
def delete_temp_room(guild_id, channel_id):
    """Удалить временную комнату досрочно"""
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "Сервер не найден"}), 404
    
    room_info = temp_rooms.get(channel_id)
    if not room_info:
        return jsonify({"error": "Комната не найдена"}), 404
    
    try:
        async def remove_room():
            # Отменяем таймер
            if channel_id in temp_room_tasks:
                temp_room_tasks[channel_id].cancel()
                del temp_room_tasks[channel_id]
            
            # Удаляем канал
            voice_channel = guild.get_channel(int(channel_id))
            if voice_channel:
                await voice_channel.delete(reason="Досрочное удаление администратором")
            
            # Удаляем роль
            role = guild.get_role(int(room_info['role_id']))
            if role:
                await role.delete(reason="Удаление роли временной комнаты")
            
            # Обновляем статус в Google Sheets
            update_temp_room_status(channel_id, 'deleted_by_admin')
            
            # Удаляем из списка
            if channel_id in temp_rooms:
                del temp_rooms[channel_id]
            
            print(f"🗑️ Удалена временная комната: {room_info['full_name']}")
        
        future = asyncio.run_coroutine_threadsafe(remove_room(), bot.loop)
        future.result(timeout=10)
        
        return jsonify({"success": True}), 200
        
    except Exception as e:
        print(f"❌ Ошибка удаелния комнаты: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

async def auto_delete_room(channel_id, role_id, delay_seconds):
    """Автоматическое удаление комнаты по таймеру"""
    try:
        await asyncio.sleep(delay_seconds)
        
        channel_id_str = str(channel_id)
        
        # Удаляем канал
        voice_channel = bot.get_channel(channel_id)
        if voice_channel:
            await voice_channel.delete(reason="Время истекло")
        
        # Удаляем роль
        for guild in bot.guilds:
            role = guild.get_role(role_id)
            if role:
                await role.delete(reason="Удаление роли временной комнаты")
                break
        
        # Обновляем статус в Google Sheets
        update_temp_room_status(channel_id_str, 'expired')
        
        # Удаляем из списка
        if channel_id_str in temp_rooms:
            room_name = temp_rooms[channel_id_str]['full_name']
            del temp_rooms[channel_id_str]
            print(f"⏰ Автоудаление: {room_name} (время истекло)")
        
        if channel_id_str in temp_room_tasks:
            del temp_room_tasks[channel_id_str]
            
    except asyncio.CancelledError:
        print(f"🚫 Таймер комнаты {channel_id} отменён")
    except Exception as e:
        print(f"❌ Ошибка автоудаления комнаты: {e}")

# ==================== ROOM RENTAL API (EXCEL ONLY) ====================

def run_self_ping():
    if not RENDER_EXTERNAL_URL:
        print("⚠️ WARNING: RENDER_EXTERNAL_URL не задан")
        return
    print(f"⏰ Self-Ping сервис запущен: {RENDER_EXTERNAL_URL}")
    while True:
        try:
            time.sleep(300)
            response = requests.get(f"{RENDER_EXTERNAL_URL}/keep_alive_ping")
            if response.status_code == 200:
                print(f"✅ Self-Ping: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"❌ Self-Ping ошибка: {e}")
# --- START ---
def run_flask():
    app.run(host='0.0.0.0', port=PORT, debug=False)

def run_bot():
    bot.run(TOKEN)

# === SUSPICIOUS ACTIVITY ===
if __name__ == '__main__':
    print("🚀 Запуск Discord Bot Dashboard...")
    print(f"🌐 Flask Port: {PORT}")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    ping_thread = threading.Thread(target=run_self_ping, daemon=True)
    ping_thread.start()
    
    time.sleep(5)
    print("✅ Flask сервер запускается...")
    run_flask()

# === USER INFO ===

