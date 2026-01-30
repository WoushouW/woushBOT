# -*- coding: utf-8 -*-
"""
Функции для работы с Google Sheets БД
"""

from datetime import datetime, timedelta


def get_user_messages_count(sheets_client, guild_id, user_id=None, username=None):
    """Получить общее количество сообщений пользователя"""
    try:
        if not sheets_client:
            return {'total_messages': 0}
        
        messages_sheet = sheets_client.worksheet('Messages')
        records = messages_sheet.get_all_records(expected_headers=[])
        
        count = 0
        for r in records:
            if str(r.get('Guild ID')) != str(guild_id):
                continue
            
            sent_by = str(r.get('Sent By', ''))
            
            # Поиск по ID (приоритет)
            if user_id and str(user_id) in sent_by:
                count += 1
            # Поиск по username (fallback)
            elif username and username.lower() in sent_by.lower():
                count += 1
        
        return {'total_messages': count}
    except Exception as e:
        print(f"❌ Ошибка get_user_messages_count: {e}")
        return {'total_messages': 0}


def get_user_reactions_count(sheets_client, guild_id, user_id=None, username=None):
    """Получить количество реакций пользователя"""
    try:
        if not sheets_client:
            return {'total_reactions': 0}
        
        activity_sheet = sheets_client.worksheet('Activity')
        records = activity_sheet.get_all_records(expected_headers=[])
        
        count = 0
        for r in records:
            # Проверяем Guild ID
            if str(r.get('Guild ID')) != str(guild_id):
                continue
            
            # ТОЛЬКО реакции (Event Type = 'add_reaction')
            if r.get('Event Type') != 'add_reaction':
                continue
            
            # Проверяем User ID (так же, как в веб-интерфейсе!)
            reaction_user_id = str(r.get('User ID', ''))
            
            if user_id and str(user_id) == reaction_user_id:
                count += 1
            elif username and username.lower() in reaction_user_id.lower():
                count += 1
        
        return {'total_reactions': count}
    except Exception as e:
        print(f"❌ Ошибка get_user_reactions_count: {e}")
        return {'total_reactions': 0}


def get_weekly_activity(sheets_client, guild_id, user_id=None, username=None):
    """
    Получить недельную активность: сообщения (1 балл) + реакции (0.5 балла)
    Возвращает: {score: N, messages: N, reactions: N, icon: '🔥', status: 'Очень активен'}
    """
    try:
        if not sheets_client:
            return {'score': 0, 'messages': 0, 'reactions': 0, 'icon': '💤', 'status': 'Неактивен'}
        
        # Дата 7 дней назад
        week_ago = datetime.now() - timedelta(days=7)
        
        messages_sheet = sheets_client.worksheet('Messages')
        records = messages_sheet.get_all_records(expected_headers=[])
        
        weekly_messages = 0
        weekly_reactions = 0
        
        for r in records:
            if str(r.get('Guild ID')) != str(guild_id):
                continue
            
            # Проверяем дату
            timestamp = r.get('Timestamp', '')
            try:
                msg_date = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                if msg_date < week_ago:
                    continue
            except:
                continue
            
            sent_by = str(r.get('Sent By', ''))
            
            # Проверяем пользователя
            is_user = False
            if user_id and str(user_id) in sent_by:
                is_user = True
            elif username and username.lower() in sent_by.lower():
                is_user = True
            
            if is_user:
                weekly_messages += 1
        
        # Реакции за неделю (из Activity)
        try:
            activity_sheet = sheets_client.worksheet('Activity')
            activity_records = activity_sheet.get_all_records(expected_headers=[])
            
            for r in activity_records:
                if str(r.get('Guild ID')) != str(guild_id):
                    continue
                
                # ТОЛЬКО реакции (Event Type = 'add_reaction')
                if r.get('Event Type') != 'add_reaction':
                    continue
                
                # Проверяем дату
                timestamp = r.get('Timestamp', '')
                try:
                    action_date = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    if action_date < week_ago:
                        continue
                except:
                    continue
                
                # Проверяем User ID (так же, как в веб-интерфейсе!)
                reaction_user_id = str(r.get('User ID', ''))
                
                is_user = False
                if user_id and str(user_id) == reaction_user_id:
                    is_user = True
                elif username and username.lower() in reaction_user_id.lower():
                    is_user = True
                
                if is_user:
                    weekly_reactions += 1
        except:
            pass
        
        # Считаем баллы: сообщения * 1 + реакции * 0.5
        score = weekly_messages + (weekly_reactions * 0.5)
        
        # Определяем статус и иконку
        if score >= 50:
            icon = '🔥'
            status = 'Очень активен'
        elif score >= 20:
            icon = '⚡'
            status = 'Активен'
        elif score >= 5:
            icon = '✨'
            status = 'Средняя активность'
        else:
            icon = '💤'
            status = 'Малоактивен'
        
        return {
            'score': score,
            'messages': weekly_messages,
            'reactions': weekly_reactions,
            'icon': icon,
            'status': status
        }
    except Exception as e:
        print(f"❌ Ошибка get_weekly_activity: {e}")
        import traceback
        traceback.print_exc()
        return {'score': 0, 'messages': 0, 'reactions': 0, 'icon': '💤', 'status': 'Неактивен'}


def get_user_punishments(sheets_client, guild_id, username=None):
    """Получить количество наказаний пользователя"""
    try:
        if not sheets_client:
            return {'total': 0, 'bans': 0, 'mutes': 0, 'kicks': 0, 'warns': 0}
        
        punishments_sheet = sheets_client.worksheet('Punishments')
        records = punishments_sheet.get_all_records(expected_headers=[])
        
        bans = mutes = kicks = warns = 0
        
        for r in records:
            if str(r.get('Guild ID')) != str(guild_id):
                continue
            
            target_user = str(r.get('Target User', ''))
            if not username or username.lower() not in target_user.lower():
                continue
            
            action = str(r.get('Action', '')).lower()
            
            if 'ban' in action:
                bans += 1
            elif 'mute' in action:
                mutes += 1
            elif 'kick' in action:
                kicks += 1
            elif 'warn' in action:
                warns += 1
        
        total = bans + mutes + kicks + warns
        
        return {
            'total': total,
            'bans': bans,
            'mutes': mutes,
            'kicks': kicks,
            'warns': warns
        }
    except Exception as e:
        print(f"❌ Ошибка get_user_punishments: {e}")
        return {'total': 0, 'bans': 0, 'mutes': 0, 'kicks': 0, 'warns': 0}
