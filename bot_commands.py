# -*- coding: utf-8 -*-
"""
Простая система команд woushBOT
AI распознаёт команды, скрипты выполняют запросы к БД
"""

from db_functions import get_user_messages_count, get_user_reactions_count, get_weekly_activity, get_user_punishments


def detect_command_intent(text, message=None):
    """
    AI определяет намерение пользователя
    Возвращает: ('command_type', confidence)
    """
    text_lower = text.lower()
    
    # СНАЧАЛА проверяем упоминания!
    if message and message.mentions:
        # ИСКЛЮЧАЕМ упоминание самого бота!
        real_mentions = [m for m in message.mentions if not m.bot]
        
        if real_mentions:
            # Если есть упоминание РЕАЛЬНОГО пользователя + ключевые слова → информация о другом пользователе
            if any(phrase in text_lower for phrase in [
                'расскажи', 'статистика', 'информация', 'кто такой', 'инфа', 'про'
            ]):
                print(f"✅ Обнаружено упоминание: {real_mentions[0].display_name}")
                return ('user_info_mention', 0.95)
    
    # Команда 1: Полная информация обо мне
    if any(phrase in text_lower for phrase in [
        'информация обо мне', 'моя статистика', 'расскажи обо мне',
        'кто я', 'мой профиль', 'мои данные', 'моя инфа'
    ]):
        return ('user_full_info', 0.9)
    
    # Команда 2: Только активность
    if any(phrase in text_lower for phrase in [
        'моя активность', 'какая у меня активность', 'насколько я активен'
    ]):
        return ('user_activity', 0.9)
    
    # Команда 3: Только наказания
    if any(phrase in text_lower for phrase in [
        'мои наказания', 'сколько у меня наказаний', 'мои варны', 'мои баны'
    ]):
        return ('user_punishments', 0.9)
    
    # Команда 4: Удалить эту проверку (уже проверяем в начале)
    
    # Не команда — обычное общение
    return (None, 0.0)


def format_full_user_info(member, guild_id, gc):
    """
    Форматирует полную информацию о пользователе
    """
    user_id = str(member.id)
    username = member.display_name
    
    # Получаем данные
    messages_data = get_user_messages_count(gc, guild_id, user_id=user_id, username=username)
    reactions_data = get_user_reactions_count(gc, guild_id, user_id=user_id, username=username)
    weekly_data = get_weekly_activity(gc, guild_id, user_id=user_id, username=username)
    punishments_data = get_user_punishments(gc, guild_id, username=username)
    
    # Дата захода
    if member.joined_at:
        joined_date = member.joined_at.strftime('%d.%m.%Y')
        from datetime import datetime
        days_on_server = (datetime.now(member.joined_at.tzinfo) - member.joined_at).days
        joined_info = f"{joined_date} (на сервере {days_on_server} дней)"
    else:
        joined_info = "Неизвестно"
    
    # Роли
    roles = [role.name for role in member.roles if role.name != '@everyone'][:10]
    roles_text = ', '.join(roles) if roles else 'нет'
    
    # Формируем ответ
    response = f"""**📊 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ**

**Ник:** {username}
**ID:** {user_id}
**Дата захода на сервер:** {joined_info}

**📈 Активность:**
  • Всего сообщений: {messages_data['total_messages']}
  • Всего реакций: {reactions_data['total_reactions']}
  • Недельная активность: {weekly_data['icon']} {weekly_data['score']:.1f} ({weekly_data['status']})
    ├ Сообщений за неделю: {weekly_data['messages']}
    └ Реакций за неделю: {weekly_data['reactions']}

**⚠️ Наказания:** {punishments_data['total']} шт."""
    
    if punishments_data['total'] > 0:
        response += f"\n  ├ Баны: {punishments_data['bans']}"
        response += f"\n  ├ Муты: {punishments_data['mutes']}"
        response += f"\n  ├ Кики: {punishments_data['kicks']}"
        response += f"\n  └ Варны: {punishments_data['warns']}"
    
    response += f"\n\n**🎭 Роли:** {roles_text}"
    
    return response


def format_user_activity(member, guild_id, gc):
    """
    Форматирует только активность пользователя
    """
    user_id = str(member.id)
    username = member.display_name
    
    messages_data = get_user_messages_count(gc, guild_id, user_id=user_id, username=username)
    reactions_data = get_user_reactions_count(gc, guild_id, user_id=user_id, username=username)
    weekly_data = get_weekly_activity(gc, guild_id, user_id=user_id, username=username)
    
    response = f"""**📈 АКТИВНОСТЬ ПОЛЬЗОВАТЕЛЯ {username}**

**Всего сообщений:** {messages_data['total_messages']}
**Всего реакций:** {reactions_data['total_reactions']}

**Недельная активность:** {weekly_data['icon']} {weekly_data['score']:.1f} — {weekly_data['status']}
  ├ Сообщений за неделю: {weekly_data['messages']}
  └ Реакций за неделю: {weekly_data['reactions']}"""
    
    return response


def format_user_punishments(member, guild_id, gc):
    """
    Форматирует только наказания пользователя
    """
    username = member.display_name
    punishments_data = get_user_punishments(gc, guild_id, username=username)
    
    if punishments_data['total'] == 0:
        return f"У вас нет наказаний."
    
    response = f"""**⚠️ ВАШИ НАКАЗАНИЯ**

**Всего наказаний:** {punishments_data['total']} шт.
  ├ Баны: {punishments_data['bans']}
  ├ Муты: {punishments_data['mutes']}
  ├ Кики: {punishments_data['kicks']}
  └ Варны: {punishments_data['warns']}"""
    
    return response


def execute_command(command_type, message, guild_obj, gc):
    """
    Выполняет команду и возвращает ответ
    
    Args:
        command_type (str): Тип команды
        message: Discord Message объект
        guild_obj: Discord Guild объект
        gc: Google Sheets клиент
    
    Returns:
        str: Ответ бота или None (если не команда)
    """
    if not command_type:
        return None
    
    guild_id = str(guild_obj.id)
    
    try:
        # Команда 1: Полная информация
        if command_type == 'user_full_info':
            member = guild_obj.get_member(message.author.id)
            if not member:
                return "❌ Не удалось найти вашу информацию на сервере"
            return format_full_user_info(member, guild_id, gc)
        
        # Команда 2: Только активность
        elif command_type == 'user_activity':
            member = guild_obj.get_member(message.author.id)
            if not member:
                return "❌ Не удалось найти вашу информацию на сервере"
            return format_user_activity(member, guild_id, gc)
        
        # Команда 3: Только наказания
        elif command_type == 'user_punishments':
            member = guild_obj.get_member(message.author.id)
            if not member:
                return "❌ Не удалось найти вашу информацию на сервере"
            return format_user_punishments(member, guild_id, gc)
        
        # Команда 4: Информация о другом пользователе
        elif command_type == 'user_info_mention':
            if not message.mentions:
                return "❌ Укажите пользователя через упоминание (@пользователь)"
            
            target_member = message.mentions[0]
            return format_full_user_info(target_member, guild_id, gc)
        
        return None
    
    except Exception as e:
        print(f"❌ Ошибка выполнения команды {command_type}: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Ошибка выполнения команды: {e}"
