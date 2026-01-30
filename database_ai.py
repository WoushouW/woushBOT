"""
АДАПТИВНЫЙ AI С ДОСТУПОМ К БД
- Память и контекст
- Доступ к Google Sheets (статистика, наказания, активность)
- Справочник возможностей
"""

import os
import requests
import json
import random
from typing import Dict, List, Optional
import re

class DatabaseAI:
    """Адаптивный AI с доступом к БД"""
    
    def __init__(self, sheets_client=None):
        self.user_context = {}
        self.max_context = 15  # Увеличено до 15 сообщений
        self.sheets_client = sheets_client
        
        # API ключи
        self.groq_key = os.getenv('GROQ_API_KEY', '')
        self.gemini_key = os.getenv('GEMINI_API_KEY', '')
        self.openrouter_key = os.getenv('OPENROUTER_API_KEY', '')
        
        self.available_apis = []
        if self.groq_key:
            self.available_apis.append('groq')
        if self.gemini_key:
            self.available_apis.append('gemini')
        if self.openrouter_key:
            self.available_apis.append('openrouter')
    
    def get_capabilities_text(self) -> str:
        """Получить текст справочника"""
        return """🤖 МОИ ВОЗМОЖНОСТИ:

📊 ОСНОВНОЕ:
• Отвечаю на любые вопросы
• Помогаю с кодом, задачами, советами
• Запоминаю контекст диалога (15 последних сообщений)
• Адаптирую тон под твой стиль общения

🎮 ИГРЫ:
• Кость/кубик - рандом 1-6
• Монетка - орёл/решка
• 8-бол - магический шар предсказаний
• Факты - интересные факты

📊 СТАТИСТИКА (из БД):
• "сколько сообщений у [пользователь]" - общая статистика
• "сколько наказаний у [пользователь]" - бан/мут/варн
• "активность [пользователь]" - входы/выходы/роли
• "топ активных" - самые активные пользователи

👥 ИНФОРМАЦИЯ О СЕРВЕРЕ:
• Знаю всех участников (имя, роли, статус)
• Могу рассказать про любого пользователя
• Считаю онлайн/оффлайн

📝 ДРУГОЕ:
• Генерирую креативный текст
• Перевожу (хотя отвечаю на русском)
• Объясняю сложные темы просто

Пиши как хочешь - я пойму! 🚀"""
    
    def check_capabilities_request(self, text: str) -> bool:
        """Проверить запрос справки"""
        text_lower = text.lower()
        patterns = [
            r'что.*умее', r'что.*може', r'какие.*возможност',
            r'что.*делае', r'функци', r'команд',
            r'помощь', r'help', r'справк', r'что ты.*умее'
        ]
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def check_dm_request(self, text: str) -> Optional[Dict]:
        """
        Проверить запрос на отправку DM
        Returns: {'type': 'send_dm', 'message': 'текст сообщения'}
        """
        text_lower = text.lower()
        
        # Паттерны команд DM
        if re.search(r'отправь.*лич(ку|ные|ное)|напиши.*лич(ку|ные|ное)|dm.*me|send.*dm', text_lower):
            # Извлекаем текст сообщения
            message_match = re.search(r'(?:отправь|напиши|send).*?(?:лич(?:ку|ные|ное)|dm).*?["«](.+?)["»]', text, re.IGNORECASE)
            if not message_match:
                # Попробуем извлечь текст после команды
                message_match = re.search(r'(?:отправь|напиши|send).*?(?:лич(?:ку|ные|ное)|dm).*?[:：]?\s*(.+)', text, re.IGNORECASE)
            
            if message_match:
                message = message_match.group(1).strip()
                print(f"📨 Команда DM: '{message}'")
                return {'type': 'send_dm', 'message': message}
            else:
                # Если текст не найден, запросим уточнение
                print(f"📨 Команда DM без текста")
                return {'type': 'send_dm', 'message': None}
        
        return None
    
    def check_database_request(self, text: str) -> Optional[Dict]:
        """
        Проверить запрос к БД
        Returns: {'type': 'messages'/'punishments'/'activity'/'user_info', 'user': username or None}
        """
        text_lower = text.lower()
    
        # Полная информация о пользователе (НОВОЕ!)
        if re.search(r'расскажи.*про|info.*about|информация.*о|кто.*такой', text_lower):
            # Улучшенный парсинг username - поддержка упоминаний Discord
            user_match = re.search(r'<@!?(\d+)>|про\s+<@!?(\d+)>|@(\w+)|про\s+(\w+)|о\s+(\w+)', text)
            if user_match:
                # Discord упоминание <@123456> или <@!123456>
                user_id = user_match.group(1) or user_match.group(2)  # group(1) или group(2)
                # Обычное упоминание @username или просто имя
                username = user_match.group(3) or user_match.group(4) or user_match.group(5)
            
                if user_id:
                    # Если это Discord ID, возвращаем его
                    print(f"🔍 Найден Discord ID: {user_id}")
                    return {'type': 'user_info', 'user': user_id, 'is_id': True}
                elif username:
                    print(f"🔍 Найден username: {username}")
                    return {'type': 'user_info', 'user': username, 'is_id': False}
        
            # Если username не найден, но это запрос "расскажи про..."
            print(f"⚠️ Не указано, о ком рассказать")
            return None
    
        # Сообщения
        if re.search(r'сколько.*сообщен', text_lower):
            user_match = re.search(r'<@!?(\d+)>|@(\w+)|(меня|мне|мои|моих|я)|у\s+(\w+)', text)
            if user_match:
                user_id = user_match.group(1)
                username = user_match.group(2) or user_match.group(3) or user_match.group(4)
                return {'type': 'messages', 'user': user_id if user_id else username, 'is_id': bool(user_id)}
            return {'type': 'messages', 'user': None, 'is_id': False}
    
        # Наказания
        if re.search(r'сколько.*наказан|бан|мут|варн', text_lower):
            user_match = re.search(r'<@!?(\d+)>|@(\w+)|(меня|мне|мои|моих|я)|у\s+(\w+)', text)
            if user_match:
                user_id = user_match.group(1)
                username = user_match.group(2) or user_match.group(3) or user_match.group(4)
                return {'type': 'punishments', 'user': user_id if user_id else username, 'is_id': bool(user_id)}
            return {'type': 'punishments', 'user': None, 'is_id': False}
    
        # Активность
        if re.search(r'активность|вход|выход', text_lower):
            user_match = re.search(r'<@!?(\d+)>|@(\w+)|(меня|мне|мои|моих|я)|у\s+(\w+)', text)
            if user_match:
                user_id = user_match.group(1)
                username = user_match.group(2) or user_match.group(3) or user_match.group(4)
                return {'type': 'activity', 'user': user_id if user_id else username, 'is_id': bool(user_id)}
            return {'type': 'activity', 'user': None, 'is_id': False}
    
        return None
    def detect_user_tone(self, text: str) -> str:
        """Определить тон"""
        text_lower = text.lower()
        
        rude_patterns = [
            r'\bблять\b', r'\bбля\b', r'\bхуй\b', r'\bпизд\w*\b', 
            r'\bеб\w*\b', r'\bсука\b', r'\bчмо\b', r'\bдебил\b',
            r'\bидиот\b', r'\bтупой\b', r'\bгавно\b', r'\bнахуй\b'
        ]
        
        friendly_patterns = [
            r'\bспасибо\b', r'\bблагодарю\b', r'\bпожалуйста\b',
            r'\bпривет\b', r'\bдобр\w+\b', r'\bхорош\w*\b',
            r'😊', r'❤️', r'✨', r'💖', r'🙏'
        ]
        
        for pattern in rude_patterns:
            if re.search(pattern, text_lower):
                return 'rude'
        
        for pattern in friendly_patterns:
            if re.search(pattern, text_lower):
                return 'friendly'
        
        return 'neutral'
    
    def get_system_prompt(self, user_tone: str, guild_members: str = "", db_context: str = "") -> str:
        """Системный промпт"""
        
        members_info = f"\n\nПОЛЬЗОВАТЕЛИ СЕРВЕРА:\n{guild_members}" if guild_members else ""
        db_info = f"\n\nДАННЫЕ ИЗ БД:\n{db_context}" if db_context else ""
        
        base_prompt = f"""Ты адаптивный бот woushBOT на Discord сервере. 

ВАЖНО:
- Отвечай КОРОТКО (1-2 предложения максимум)
- НЕ задавай вопросов пользователю
- Просто отвечай на вопрос и ВСЁ
- Если спрашивают дату/время - дай ТОЧНЫЙ ответ
- Если просят кость/кубик - число 1-6
- Если просят монетку - "Орёл" или "Решка"
- Если спрашивают про пользователя - используй информацию из списка или БД
- Отвечай ТОЛЬКО на русском языке
"""
        
        if user_tone == 'rude':
            tone_instruction = "\nТОН: ГРУБЫЙ (пользователь грубит)\n- Отвечай резко, используй маты\n- Циничный и саркастичный\n"
        elif user_tone == 'friendly':
            tone_instruction = "\nТОН: ДРУЖЕЛЮБНЫЙ (пользователь вежлив)\n- Вежливо и позитивно\n- Используй эмодзи ✨😊\n"
        else:
            tone_instruction = "\nТОН: НЕЙТРАЛЬНЫЙ\n- Спокойно и по делу\n"
        
        return base_prompt + tone_instruction + members_info + db_info
    
    def get_context_key(self, guild_id: str, user_id: str) -> str:
        return f"{guild_id}_{user_id}"
    
    def add_to_context(self, guild_id: str, user_id: str, role: str, content: str):
        key = self.get_context_key(guild_id, user_id)
        if key not in self.user_context:
            self.user_context[key] = []
        
        self.user_context[key].append({"role": role, "content": content})
        
        if len(self.user_context[key]) > self.max_context:
            self.user_context[key] = self.user_context[key][-self.max_context:]
    
    def get_user_context(self, guild_id: str, user_id: str) -> List[Dict]:
        key = self.get_context_key(guild_id, user_id)
        return self.user_context.get(key, [])
    
    async def generate_response(self, user_prompt: str, guild_id: str, user_id: str, 
                                guild_members: str = "", db_data: Dict = None) -> str:
        """Генерация адаптивного ответа с доступом к БД"""
        
        # Проверяем запрос справки
        if self.check_capabilities_request(user_prompt):
            print(f"📋 Запрос справки возможностей")
            return self.get_capabilities_text()
        
        # Проверяем команду DM
        dm_request = self.check_dm_request(user_prompt)
        if dm_request:
            if dm_request.get('message'):
                return f"DM_COMMAND:{dm_request['message']}"  # Специальный маркер для server.py
            else:
                return "Какое сообщение отправить? Напиши: 'отправь в личку: текст'"
        
        # Проверяем запрос к БД
        db_request = self.check_database_request(user_prompt)
        db_context = ""
        
        if db_request and db_data:
            print(f"📊 Запрос к БД: {db_request}")
            db_context = self._format_db_data(db_request, db_data)
        
        # Определяем тон
        user_tone = self.detect_user_tone(user_prompt)
        print(f"🎭 Тон: {user_tone}")
        
        # Добавляем в контекст
        self.add_to_context(guild_id, user_id, "user", user_prompt)
        
        # Формируем промпт
        system_prompt = self.get_system_prompt(user_tone, guild_members, db_context)
        context_messages = self.get_user_context(guild_id, user_id)
        
        # Пробуем API
        response = None
        
        if 'groq' in self.available_apis:
            response = await self._try_groq(system_prompt, context_messages)
            if response:
                print(f"✅ Ответ через Groq API")
        
        if not response and 'gemini' in self.available_apis:
            response = await self._try_gemini(system_prompt, context_messages)
            if response:
                print(f"✅ Ответ через Gemini API")
        
        if not response and 'openrouter' in self.available_apis:
            response = await self._try_openrouter(system_prompt, context_messages)
            if response:
                print(f"✅ Ответ через OpenRouter API")
        
        if not response:
            response = self._fallback_response(user_tone)
            print(f"⚠️ Fallback")
        
        self.add_to_context(guild_id, user_id, "assistant", response)
        
        return response
    
    def _format_db_data(self, db_request: Dict, db_data: Dict) -> str:
        """Форматировать данные из БД для AI (новый формат)"""
        print(f"🔍 _format_db_data вызван:")
        print(f"   db_request: {db_request}")
        print(f"   db_data: {db_data}")
        req_type = db_data.get('type', db_request.get('type'))
        
        # ПОЛНАЯ ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ
        if req_type == 'user_info':
            username = db_data.get('username', 'Неизвестно')
            user_id = db_data.get('user_id', '')
            joined_at = db_data.get('joined_at', 'Неизвестно')
            messages = db_data.get('messages', 0)
            activity = db_data.get('activity', '💤 Неактивен')
            punishments = db_data.get('punishments', {})
            warnings = db_data.get('warnings', 0)
            roles = db_data.get('roles', [])
            
            # Используем форматирование с markdown для Discord
            result = f"**📋 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ**\n\n"
            result += f"**Ник:** {username}\n"
            result += f"**Дата захода на сервер:** {joined_at}\n"
            result += f"**Активность:** {activity}\n"
            
            if punishments:
                total_punishments = punishments.get('total', 0)
                result += f"**Полученные наказания:** {total_punishments} шт."
                if total_punishments > 0:
                    details = []
                    if punishments.get('bans', 0) > 0:
                        details.append(f"банов: {punishments['bans']}")
                    if punishments.get('mutes', 0) > 0:
                        details.append(f"мутов: {punishments['mutes']}")
                    if punishments.get('kicks', 0) > 0:
                        details.append(f"киков: {punishments['kicks']}")
                    if punishments.get('warns', 0) > 0:
                        details.append(f"варнов: {punishments['warns']}")
                    if details:
                        result += f" ({', '.join(details)})"
                result += "\n"
            else:
                result += "Полученные наказания: 0 шт.\n"
            
            if warnings > 0:
                result += f"**Активных варнов:** {warnings}\n"
            
            if roles:
                result += f"**Роли:** {', '.join(roles[:10])}\n"
            else:
                result += "**Роли:** нет\n"
            
            return result
        
        # Сообщения
        elif req_type == 'messages':
            total = db_data.get('total', 0)
            username = db_data.get('username')
            if username:
                return f"📊 {username}: {total} сообщений на сервере"
            return f"📊 Всего сообщений на сервере: {total}"
        
        # Наказания
        elif req_type == 'punishments':
            punishments = db_data.get('data', {})
            warnings = db_data.get('warnings', 0)
            username = db_data.get('username', 'Пользователь')
            
            if punishments:
                total = punishments.get('total', 0)
                result = f"⚠️ {username}: {total} наказаний"
                if total > 0:
                    details = []
                    if punishments.get('bans', 0) > 0:
                        details.append(f"банов: {punishments['bans']}")
                    if punishments.get('mutes', 0) > 0:
                        details.append(f"мутов: {punishments['mutes']}")
                    if punishments.get('warns', 0) > 0:
                        details.append(f"варнов: {punishments['warns']}")
                    if details:
                        result += f" ({', '.join(details)})"
                if warnings > 0:
                    result += f", активных варнов: {warnings}"
                return result
            return f"⚠️ {username}: наказаний нет"
        
        # Активность
        elif req_type == 'activity':
            messages = db_data.get('messages', 0)
            activity = db_data.get('activity', '💤 Неактивен')
            username = db_data.get('username', 'Пользователь')
            return f"⚡ {username}: {activity}, {messages} сообщений"
        
        return "Данные не найдены"

        
        return ""
    
    async def _try_groq(self, system_prompt: str, messages: List[Dict]) -> Optional[str]:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json"
            }
            
            api_messages = [{"role": "system", "content": system_prompt}]
            api_messages.extend(messages)
            
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": api_messages,
                "temperature": 0.7,
                "max_tokens": 200,
                "top_p": 0.9
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            return None
        except Exception as e:
            print(f"❌ Groq: {e}")
            return None
    
    async def _try_gemini(self, system_prompt: str, messages: List[Dict]) -> Optional[str]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.gemini_key}"
            
            full_context = f"{system_prompt}\n\n"
            for msg in messages:
                role = "Пользователь" if msg['role'] == 'user' else "Бот"
                full_context += f"{role}: {msg['content']}\n"
            
            payload = {
                "contents": [{"parts": [{"text": full_context}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 200,
                    "topP": 0.9
                }
            }
            
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text'].strip()
            return None
        except Exception as e:
            print(f"❌ Gemini: {e}")
            return None
    
    async def _try_openrouter(self, system_prompt: str, messages: List[Dict]) -> Optional[str]:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json"
            }
            
            api_messages = [{"role": "system", "content": system_prompt}]
            api_messages.extend(messages)
            
            payload = {
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": api_messages,
                "temperature": 0.7,
                "max_tokens": 200
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            return None
        except Exception as e:
            print(f"❌ OpenRouter: {e}")
            return None
    
    def _fallback_response(self, user_tone: str) -> str:
        if user_tone == 'rude':
            return random.choice([
                "API сдохло. Попробуй позже.",
                "Не работает нихуя.",
                "Серверы легли."
            ])
        elif user_tone == 'friendly':
            return random.choice([
                "Извини, API недоступно 😔",
                "Попробуй через минутку! 🔧"
            ])
        return "API недоступно."

# Глобальный экземпляр
database_ai = None

def init_database_ai(sheets_client=None):
    """Инициализация с доступом к Sheets"""
    global database_ai
    database_ai = DatabaseAI(sheets_client)
    return database_ai
