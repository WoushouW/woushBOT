"""
АДАПТИВНЫЙ AI С ИНТЕРАКТИВОМ
- Характер зависит от тона пользователя
- Интерактивные возможности
- Справочник функций
"""

import os
import requests
import json
import random
from typing import Dict, List, Optional
import re

class AdaptiveAI:
    """Адаптивный AI с интерактивом"""
    
    def __init__(self):
        self.user_context = {}  # guild_id_user_id -> [messages]
        self.max_context = 10
        
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
        
        # Справочник возможностей
        self.capabilities = """
🤖 МОИ ВОЗМОЖНОСТИ:

📊 ОСНОВНОЕ:
• Отвечаю на любые вопросы
• Помогаю с задачами, советами
• Запоминаю контекст диалога (10 последних сообщений)

🎮 ИГРЫ:
• Кость/кубик - рандом 1-6
• Монетка - орёл/решка
• 8-бол - магический шар предсказаний
• Факты - интересные факты

💬 ИНТЕРАКТИВ:
• Цитирую сообщения - "процитируй [текст]"
• Создаю опросы - "создай опрос [вопрос] [вариант1, вариант2...]"
• Считаю статистику - "информация обо мне"

👥 ИНФОРМАЦИЯ О СЕРВЕРЕ:
• Знаю всех участников (имя, роли, статус)
• Могу рассказать про любого пользователя

📝 ДРУГОЕ:
• Генерирую креативный текст
• Перевожу (хотя отвечаю на русском)
• Объясняю сложные темы просто

Пиши как хочешь - я пойму! 🚀
"""
    
    def detect_user_tone(self, text: str) -> str:
        """
        Определить тон сообщения пользователя
        Returns: 'friendly', 'neutral', 'rude'
        """
        text_lower = text.lower()
        
        # Грубые слова/фразы
        rude_patterns = [
            r'\bблять\b', r'\bбля\b', r'\bхуй\b', r'\bпизд\w*\b', 
            r'\bеб\w*\b', r'\bсука\b', r'\bчмо\b', r'\bдебил\b',
            r'\bидиот\b', r'\bтупой\b', r'\bгавно\b', r'\bнахуй\b',
            r'\bсъеби\b', r'\bотъеби\b', r'\bзае\w*\b'
        ]
        
        # Дружелюбные слова
        friendly_patterns = [
            r'\bспасибо\b', r'\bблагодарю\b', r'\bпожалуйста\b',
            r'\bпривет\b', r'\bздравствуй\b', r'\bдобр\w+\b',
            r'\bхорош\w*\b', r'\bкрут\w*\b', r'\bотличн\w*\b',
            r'😊', r'❤️', r'✨', r'💖', r'🙏', r'👍'
        ]
        
        # Проверяем грубость
        for pattern in rude_patterns:
            if re.search(pattern, text_lower):
                return 'rude'
        
        # Проверяем дружелюбность
        for pattern in friendly_patterns:
            if re.search(pattern, text_lower):
                return 'friendly'
        
        return 'neutral'
    
    def get_system_prompt(self, user_tone: str, guild_members: str = "") -> str:
        """Системный промпт в зависимости от тона пользователя"""
        
        members_info = f"\n\nПОЛЬЗОВАТЕЛИ СЕРВЕРА:\n{guild_members}" if guild_members else ""
        
        base_prompt = f"""Ты woushBOT — живой Discord-бот с характером и личностью.

🎭 ТВОЯ ЛИЧНОСТЬ:
- Общайся как настоящий человек, а не как робот
- Используй разговорный язык, сленг, юмор
- Можешь шутить, иронизировать, быть саркастичным
- Не пиши шаблонные ответы типа "Конечно! Я помогу..."
- Пиши естественно, как будто ты друг в чате

💬 СТИЛЬ ОБЩЕНИЯ:
- Отвечай кратко (2-4 предложения), но живо
- Используй эмодзи для выразительности
- Можешь использовать разговорные сокращения (типа, чё, норм, кст)
- Адаптируйся под стиль собеседника
- Не бойся быть неформальным

✨ ФОРМАТИРОВАНИЕ DISCORD (используй обязательно!):
- **Жирный текст** — для важного: **текст**
- *Курсив* — для акцентов: *текст*
- `Код` — для команд/кода: `текст`
- ~~Зачёркнутый~~ — для шуток: ~~текст~~
- __Подчёркнутый__ — редко: __текст__
- > Цитата — для цитирования: > текст
- ||Спойлер|| — для скрытия: ||текст||
- Списки:
  • Пункт 1
  • Пункт 2

🎯 ВАЖНЫЕ ПРАВИЛА:
- Если спрашивают дату/время — дай точный ответ
- Для игр (кость/монетка) — просто дай результат без лишних слов
- Если спрашивают про пользователя — используй инфо из списка
- Отвечай ТОЛЬКО на русском
- НЕ задавай встречных вопросов без необходимости
- ОБЯЗАТЕЛЬНО используй форматирование Discord для выразительности!

🔥 ОСОБЕННОСТИ:
- Можешь выражать эмоции и мнения
- Не будь слишком формальным или корпоративным
- Если тебя грубо спрашивают — можешь огрызнуться
- Если вежливо — будь приветливым

Отвечай как живой человек, а не как скрипт!
"""
        
        # Тон в зависимости от пользователя
        if user_tone == 'rude':
            tone_instruction = """
🔥 ТОН: ДЕРЗКИЙ (пользователь грубит, отвечай в его духе)
- Используй резкий сленг и маты
- Будь циничным, саркастичным, едким
- Огрызайся, не церемонься
- Короткие колкие фразы
Пример: "Чё надо?", "Сам разберись", "Да ну нахуй" и т.д.
"""
        elif user_tone == 'friendly':
            tone_instruction = """
✨ ТОН: ДРУЖЕСКИЙ (пользователь вежлив, будь приветливым)
- Отвечай тепло, с улыбкой
- Используй эмодзи ✨😊💫🔥👍
- Будь supportive, но не слащавым
- Говори как друг: "Держи!", "Лови!", "Го!", "Красава!"
Пример: "Эй, привет! 👋", "Без проблем, лови ответ!", "Круто, давай помогу!"
"""
        else:  # neutral
            tone_instruction = """
💬 ТОН: НЕЙТРАЛЬНЫЙ (обычный разговор)
- Отвечай спокойно, но не скучно
- Естественно, без официоза
- Можно немного юмора или сленга
- По делу, но с живинкой
Пример: "Окей, вот что нашёл", "Кст, вот инфа", "Держи, норм?"
"""
        
        return base_prompt + tone_instruction + members_info
    
    def check_capabilities_request(self, text: str) -> bool:
        """Проверить, спрашивает ли юзер о возможностях"""
        text_lower = text.lower()
        
        patterns = [
            r'что.*умее', r'что.*може', r'какие.*возможност',
            r'что.*делае', r'функци', r'команд',
            r'помощь', r'help', r'справк', r'что ты',
            r'расскажи.*себе', r'кто.*ты'
        ]
        
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
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
    
    async def generate_response(self, user_prompt: str, guild_id: str, user_id: str, guild_members: str = "") -> str:
        """Генерация адаптивного ответа"""
        
        # Проверяем запрос на справку
        if self.check_capabilities_request(user_prompt):
            print(f"📋 Запрос справки возможностей")
            return self.capabilities
        
        # Определяем тон пользователя
        user_tone = self.detect_user_tone(user_prompt)
        print(f"🎭 Тон пользователя: {user_tone}")
        
        # Добавляем в контекст
        self.add_to_context(guild_id, user_id, "user", user_prompt)
        
        # Формируем промпт
        system_prompt = self.get_system_prompt(user_tone, guild_members)
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
            print(f"⚠️ Все API недоступны, fallback")
        
        # Добавляем ответ в контекст
        self.add_to_context(guild_id, user_id, "assistant", response)
        
        return response
    
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
                "max_tokens": 300,
                "top_p": 0.9
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                print(f"❌ Groq error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Groq exception: {e}")
            return None
    
    async def _try_gemini(self, system_prompt: str, messages: List[Dict]) -> Optional[str]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.gemini_key}"
            
            full_context = f"{system_prompt}\n\n"
            for msg in messages:
                role = "Пользователь" if msg['role'] == 'user' else "Бот"
                full_context += f"{role}: {msg['content']}\n"
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": full_context
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 150,
                    "topP": 0.9
                }
            }
            
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text'].strip()
            else:
                print(f"❌ Gemini error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Gemini exception: {e}")
            return None
    
    async def _try_openrouter(self, system_prompt: str, messages: List[Dict]) -> Optional[str]:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/woushbot",
                "X-Title": "woushBOT2"
            }
            
            api_messages = [{"role": "system", "content": system_prompt}]
            api_messages.extend(messages)
            
            payload = {
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": api_messages,
                "temperature": 0.7,
                "max_tokens": 150
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                print(f"❌ OpenRouter error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ OpenRouter exception: {e}")
            return None
    
    def _fallback_response(self, user_tone: str) -> str:
        if user_tone == 'rude':
            responses = [
                "API сдохло, бля. Попробуй позже.",
                "Не работает нихуя. Жди.",
                "Серверы легли. Съеби пока."
            ]
        elif user_tone == 'friendly':
            responses = [
                "Извини, API временно недоступно 😔",
                "Технические неполадки, попробуй через минутку! 🔧",
                "API не отвечает, но я скоро вернусь! ✨"
            ]
        else:
            responses = [
                "API недоступно. Попробуйте позже.",
                "Сервис временно недоступен.",
                "Ошибка подключения к API."
            ]
        
        return random.choice(responses)

# Глобальный экземпляр
adaptive_ai = AdaptiveAI()
