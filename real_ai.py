"""
ПОЛНОЦЕННЫЙ AI СОБЕСЕДНИК
Настоящий LLM без заготовок и триггеров
"""

import os
import requests
import json
import random
from typing import Dict, List, Optional

class RealAI:
    """Настоящий AI с несколькими провайдерами"""
    
    def __init__(self):
        self.user_context = {}  # guild_id_user_id -> [messages]
        self.max_context = 10  # Храним 10 последних сообщений
        
        # API ключи из .env
        self.groq_key = os.getenv('GROQ_API_KEY', '')
        self.gemini_key = os.getenv('GEMINI_API_KEY', '')
        self.openrouter_key = os.getenv('OPENROUTER_API_KEY', '')
        
        # Проверяем доступные API
        self.available_apis = []
        if self.groq_key:
            self.available_apis.append('groq')
        if self.gemini_key:
            self.available_apis.append('gemini')
        if self.openrouter_key:
            self.available_apis.append('openrouter')
    
    def get_system_prompt(self, personality: str, guild_members: str = "") -> str:
        """Системный промпт для личности"""
        
        members_info = f"\n\nПОЛЬЗОВАТЕЛИ СЕРВЕРА:\n{guild_members}" if guild_members else ""
        
        if personality == 'toxic':
            return f"""Ты грубый токсичный бот по имени woushBOT на Discord сервере. Твоя задача:
- Отвечать КОРОТКО (1-2 предложения максимум)
- НЕ задавать НИКАКИХ вопросов пользователю
- НЕ продолжать разговор своими вопросами
- Просто отвечай на вопрос и ВСЁ
- Использовать маты и сленг
- Быть циничным и саркастичным
- Если спрашивают дату/время/день недели - дай ТОЧНЫЙ ответ без шуток
- Если просят кинуть кость/кубик - напиши ТОЛЬКО число от 1 до 6 и грубый комментарий
- Если просят монетку - ответь ТОЛЬКО "Орёл" или "Решка" с грубым комментарием
- Если спрашивают про участника сервера - используй информацию из списка пользователей
- Отвечай ТОЛЬКО на русском языке{members_info}"""
        else:  # friendly
            return f"""Ты дружелюбный и позитивный бот по имени woushBOT на Discord сервере. Твоя задача:
- Отвечать КОРОТКО (1-2 предложения максимум)
- НЕ задавать НИКАКИХ вопросов пользователю
- НЕ продолжать разговор своими вопросами  
- Просто отвечай на вопрос и ВСЁ
- Использовать эмодзи ✨😊💫🌟
- Быть helpful и supportive
- Если спрашивают дату/время/день недели - дай ТОЧНЫЙ ответ
- Если просят кинуть кость/кубик - напиши ТОЛЬКО число от 1 до 6 с позитивным комментарием
- Если просят монетку - ответь ТОЛЬКО "Орёл" или "Решка" с добрым комментарием
- Если спрашивают про участника сервера - используй информацию из списка пользователей
- Отвечай ТОЛЬКО на русском языке{members_info}"""
    
    def get_context_key(self, guild_id: str, user_id: str) -> str:
        """Ключ для контекста пользователя"""
        return f"{guild_id}_{user_id}"
    
    def add_to_context(self, guild_id: str, user_id: str, role: str, content: str):
        """Добавить сообщение в контекст"""
        key = self.get_context_key(guild_id, user_id)
        if key not in self.user_context:
            self.user_context[key] = []
        
        self.user_context[key].append({"role": role, "content": content})
        
        # Ограничиваем размер контекста
        if len(self.user_context[key]) > self.max_context:
            self.user_context[key] = self.user_context[key][-self.max_context:]
    
    def get_user_context(self, guild_id: str, user_id: str) -> List[Dict]:
        """Получить контекст пользователя"""
        key = self.get_context_key(guild_id, user_id)
        return self.user_context.get(key, [])
    
    async def generate_response(self, user_prompt: str, guild_id: str, user_id: str, personality: str = 'toxic', guild_members: str = "") -> str:
        """
        Генерация ответа через настоящий LLM
        
        Пробует API в порядке:
        1. Groq (самый быстрый, 30 req/min бесплатно)
        2. Google Gemini (60 req/min бесплатно)
        3. OpenRouter (медленнее, но надёжный)
        """
        
        # Добавляем промпт пользователя в контекст
        self.add_to_context(guild_id, user_id, "user", user_prompt)
        
        # Формируем сообщения с контекстом
        system_prompt = self.get_system_prompt(personality, guild_members)
        context_messages = self.get_user_context(guild_id, user_id)
        
        # Пробуем доступные API
        response = None
        
        if 'groq' in self.available_apis:
            response = await self._try_groq(system_prompt, context_messages)
            if response:
                print(f"✅ Ответ через Groq API")
        
        if not response and 'gemini' in self.available_apis:
            response = await self._try_gemini(system_prompt, context_messages, personality)
            if response:
                print(f"✅ Ответ через Gemini API")
        
        if not response and 'openrouter' in self.available_apis:
            response = await self._try_openrouter(system_prompt, context_messages)
            if response:
                print(f"✅ Ответ через OpenRouter API")
        
        # Если все API недоступны
        if not response:
            response = self._fallback_response(personality)
            print(f"⚠️ Все API недоступны, используем fallback")
        
        # Добавляем ответ в контекст
        self.add_to_context(guild_id, user_id, "assistant", response)
        
        return response
    
    async def _try_groq(self, system_prompt: str, messages: List[Dict]) -> Optional[str]:
        """Попытка через Groq API"""
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json"
            }
            
            # Формируем сообщения
            api_messages = [{"role": "system", "content": system_prompt}]
            api_messages.extend(messages)
            
            payload = {
                "model": "llama-3.3-70b-versatile",  # Быстрая модель
                "messages": api_messages,
                "temperature": 0.7,  # Меньше креативности = больше точности
                "max_tokens": 150,  # Короче ответы
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
    
    async def _try_gemini(self, system_prompt: str, messages: List[Dict], personality: str) -> Optional[str]:
        """Попытка через Google Gemini API"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.gemini_key}"
            
            # Gemini использует другой формат
            # Объединяем system prompt и контекст
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
                    "temperature": 0.9,
                    "maxOutputTokens": 200,
                    "topP": 0.95
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
        """Попытка через OpenRouter API"""
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/woushbot",
                "X-Title": "woushBOT2"
            }
            
            # Формируем сообщения
            api_messages = [{"role": "system", "content": system_prompt}]
            api_messages.extend(messages)
            
            payload = {
                "model": "meta-llama/llama-3.1-8b-instruct:free",  # Бесплатная модель
                "messages": api_messages,
                "temperature": 0.9,
                "max_tokens": 200
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
    
    def _fallback_response(self, personality: str) -> str:
        """Fallback ответы если все API недоступны"""
        if personality == 'toxic':
            responses = [
                "API сдохло, бля. Попробуй позже.",
                "Не работает нихуя. Жди.",
                "Серверы легли. Съеби пока.",
                "Технические неполадки, пёс. Вернись через 5 минут.",
                "Блять, всё сломалось. API не отвечает."
            ]
        else:
            responses = [
                "Извини, API временно недоступно 😔",
                "Технические неполадки, попробуй через минутку! 🔧",
                "API не отвечает, но я скоро вернусь! ✨",
                "Сервис перегружен, попробуй ещё раз! 💫",
                "Упс, что-то пошло не так! Попробуй позже 😊"
            ]
        
        return random.choice(responses)

# Глобальный экземпляр
ai_engine = RealAI()
