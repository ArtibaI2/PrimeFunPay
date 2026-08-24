import asyncio
import os
import sys
import re
from pathlib import Path

# Ensure UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

async def test_funpay_key(golden_key: str, user_agent: str, proxy: str = None):
    """Tests if the provided golden_key is valid by fetching FunPay profile."""
    from funpay.client import FunPayClient
    client = FunPayClient(golden_key=golden_key, user_agent=user_agent, proxy=proxy or None)
    profile = await client.check_auth()
    await client.close()
    return profile

async def test_telegram_token(token: str):
    """Tests if Telegram bot token is valid and gets bot info."""
    from aiogram import Bot
    try:
        bot = Bot(token=token)
        me = await bot.get_me()
        await bot.session.close()
        return me
    except Exception:
        return None

def print_header():
    print("=" * 68)
    print("🤖   МАСТЕР НАСТРОЙКИ И РЕГИСТРАЦИИ FUNPAY BOT (PRODUCTION READY)")
    print("=" * 68)
    print("Этот мастер поможет быстро настроить все ключи для запуска на ПК")
    print("или удаленном сервере (VPS / Docker).\n")

def main():
    print_header()

    env_path = Path(".env")
    current_values = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    current_values[k.strip()] = v.strip().strip('"').strip("'")

    # 1. FunPay Golden Key
    print("━" * 68)
    print("🔑 1. FUNPAY GOLDEN_KEY (ОБЯЗАТЕЛЬНО)")
    print("━" * 68)
    print("Как получить:")
    print("  1. Откройте сайт https://funpay.com в браузере и авторизуйтесь.")
    print("  2. Нажмите F12 (DevTools) -> вкладка 'Application' (Приложение) или 'Storage'.")
    print("  3. Слева выберите Cookies -> https://funpay.com.")
    print("  4. Найдите строку 'golden_key' и скопируйте её 32-значное значение.\n")

    current_gk = current_values.get("FUNPAY_GOLDEN_KEY", "")
    if current_gk and current_gk != "your_golden_key_here":
        print(f"Текущее значение: {current_gk[:8]}...{current_gk[-4:]}")
    
    gk_input = input("👉 Введите golden_key: ").strip()
    golden_key = gk_input if gk_input else current_gk

    user_agent = current_values.get(
        "FUNPAY_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    # 2. FunPay Proxy (Optional)
    print("\n" + "━" * 68)
    print("🌐 2. ПРОКСИ ДЛЯ FUNPAY (НЕОБЯЗАТЕЛЬНО)")
    print("━" * 68)
    print("Если вы хостите бота на зарубежном сервере или хотите скрыть IP.")
    print("Форматы: http://user:pass@ip:port или socks5://ip:port (или оставьте пустым)")
    current_proxy = current_values.get("FUNPAY_PROXY", "")
    proxy_input = input(f"👉 Введите прокси [{current_proxy or 'Без прокси'}]: ").strip()
    proxy = proxy_input if proxy_input else current_proxy

    # Verify FunPay credentials live
    if golden_key and golden_key != "your_golden_key_here":
        print("\n⏳ Проверяем авторизацию на FunPay...")
        try:
            profile = asyncio.run(test_funpay_key(golden_key, user_agent, proxy))
            if profile and profile.is_authenticated:
                avail_info = f", доступно к выводу: {profile.balance_available_rub} ₽" if profile.balance_available_rub != profile.balance_rub else ""
                print(f"   ✅ Успешно! Аккаунт: {profile.username} (ID: {profile.user_id}, Баланс: {profile.balance_rub} ₽{avail_info})")
            else:
                print("   ⚠️ Внимание: Не удалось войти с этим golden_key. Проверьте правильность значения.")
        except Exception as e:
            print(f"   ⚠️ Ошибка при проверке FunPay: {e}")

    # 3. Telegram Bot Token
    print("\n" + "━" * 68)
    print("🤖 3. TELEGRAM BOT TOKEN (ОБЯЗАТЕЛЬНО ДЛЯ УПРАВЛЕНИЯ)")
    print("━" * 68)
    print("Как получить:")
    print("  1. Откройте Telegram и найдите бота @BotFather.")
    print("  2. Отправьте команду /newbot и следуйте инструкциям.")
    print("  3. Скопируйте полученный токен (вида: 1234567890:ABCdefGHI...)\n")

    current_tg = current_values.get("TELEGRAM_BOT_TOKEN", "")
    if current_tg and current_tg != "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz":
        print(f"Текущее значение: {current_tg[:12]}...")
    tg_input = input("👉 Введите Telegram Bot Token: ").strip()
    tg_token = tg_input if tg_input else current_tg

    if tg_token and tg_token != "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz":
        print("\n⏳ Проверяем Telegram токен...")
        bot_info = asyncio.run(test_telegram_token(tg_token))
        if bot_info:
            print(f"   ✅ Бот успешно подключен: @{bot_info.username} ({bot_info.first_name})")
        else:
            print("   ⚠️ Не удалось подключиться к Telegram боту. Проверьте токен.")

    # 4. Telegram Admin IDs
    print("\n" + "━" * 68)
    print("👑 4. ВАШ TELEGRAM USER ID (АДМИНИСТРАТОР)")
    print("━" * 68)
    print("Чтобы бот слушался только вас, укажите ваш числовой Telegram ID.")
    print("Узнать свой ID можно в боте @userinfobot или @raw_data_bot.\n")
    current_admin = current_values.get("TELEGRAM_ADMIN_IDS", "")
    admin_input = input(f"👉 Введите ваш Telegram ID [{current_admin or 'Не указан'}]: ").strip()
    admin_ids = admin_input if admin_input else current_admin

    # 5. AI API Key (Optional)
    print("\n" + "━" * 68)
    print("🧠 5. AI API KEY ДЛЯ НЕЙРО-САППОРТА (НЕОБЯЗАТЕЛЬНО)")
    print("━" * 68)
    print("Ключ API для умных автоответов покупателям (OpenAI / OpenRouter / DeepSeek / Gemini).")
    print("ℹ️ БЕЗ ЭТОГО КЛЮЧА БОТ ПОЛНОСТЬЮ РАБОТАЕТ на встроенных шаблонах и правилах,")
    print("   но функции с генерацией нейросетью будут отключены.")
    current_ai = current_values.get("AI_API_KEY", "")
    if current_ai and current_ai != "your_openai_api_key_here":
        print(f"Текущее значение: {current_ai[:8]}...")
    ai_input = input(f"👉 Введите AI API Key [{current_ai or 'Пропустить (Enter)'}]: ").strip()
    ai_key = ai_input if ai_input else current_ai

    ai_model = current_values.get("AI_MODEL", "gpt-4o-mini")

    # 6. Web Dashboard Settings
    print("\n" + "━" * 68)
    print("🌐 6. НАСТРОЙКИ WEB-ПАНЕЛИ (DASHBOARD)")
    print("━" * 68)
    current_port = current_values.get("WEBAPP_PORT", "8080")
    port_input = input(f"👉 Порт Web-панели [{current_port}]: ").strip()
    webapp_port = port_input if port_input else current_port

    current_webapp_url = current_values.get("WEBAPP_URL", "")
    url_input = input(f"👉 Публичный HTTPS URL (для WebApp в Telegram) [{current_webapp_url or 'Пропустить'}]: ").strip()
    webapp_url = url_input if url_input else current_webapp_url

    # Save to .env
    env_content = f"""# ==========================================
# FunPay Bot Configuration (Production)
# ==========================================

# FunPay Account Credentials
FUNPAY_GOLDEN_KEY={golden_key}
FUNPAY_USER_AGENT={user_agent}
FUNPAY_PROXY={proxy}

# Telegram Bot Management
TELEGRAM_BOT_TOKEN={tg_token}
TELEGRAM_ADMIN_IDS={admin_ids}

# Automation Modules
ENABLE_AUTO_DELIVERY=True
ENABLE_AUTO_RAISE=True
ENABLE_AUTO_RESPONSE=True
ENABLE_STOCK_SYNC=True
ENABLE_SMART_PRICING=False
ENABLE_AI_SUPPORT={'True' if ai_key else 'False'}
ENABLE_UPSELL=True
ENABLE_NIGHT_SURGE=False
NIGHT_SURGE_PERCENT=15.0

# AI Customer Support (Optional)
AI_API_KEY={ai_key}
AI_MODEL={ai_model}

# Web Dashboard
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT={webapp_port}
WEBAPP_URL={webapp_url}

# Timers & Intervals
AUTO_RAISE_INTERVAL=7200
POLL_INTERVAL=3.0

# Auto-Response Messages
AUTO_RESPONSE_GREETING="Здравствуйте! Спасибо за обращение. Если у вас возник вопрос по заказу, напишите детали, я скоро отвечу."
AUTO_RESPONSE_AFTER_PURCHASE="Спасибо за покупку! Ваш заказ успешно выдан. Пожалуйста, проверьте товар и подтвердите заказ."

# Storage & Logs
DATABASE_URL=sqlite+aiosqlite:///storage/sqlite.db
GOODS_DIR=storage/goods
LOG_DIR=storage/logs
LOG_LEVEL=INFO
"""

    with open(".env", "w", encoding="utf-8") as f:
        f.write(env_content)

    print("\n" + "=" * 68)
    print("🎉 ВСЕ НАСТРОЙКИ УСПЕШНО СОХРАНЕНЫ В .env!")
    print("=" * 68)
    print("\n🚀 КАК ЗАПУСТИТЬ ПРОЕКТ:")
    print("  1. Локально на Windows:")
    print("     • Дважды кликните по: start.bat")
    print("     • Или в консоли: .venv\\Scripts\\python main.py\n")
    print("  2. На сервере через Docker (Рекомендуется):")
    print("     • docker compose up -d\n")
    print("  3. На сервере через Systemd / Python:")
    print("     • bash deploy.sh\n")

if __name__ == "__main__":
    main()
