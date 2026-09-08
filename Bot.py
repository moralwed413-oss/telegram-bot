import re
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Токен бота (замени на свой)
BOT_TOKEN = 8667816838:AAH6kTOb3vJCPMHTSmrPyAr8PeFToGOF0ZA

# Хранилище активных битв
battles = {}

# Функция проверки фрагмента через API
async def check_fragment(username: str) -> int:
    """
    Проверяет, продавался ли юзернейм на фрагменте
    Возвращает оценку от 0 до 10
    """
    try:
        # Запрос к API Fragments (используем публичный эндпоинт)
        url = f"https://fragment.com/api/username/{username}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Проверяем, есть ли информация о продаже
                    if data.get('sale') and data['sale'].get('price'):
                        price = data['sale']['price']
                        
                        # Конвертируем цену в доллары (примерный курс)
                        price_usd = price / 1000000000  # TON в USD (приблизительно)
                        
                        if price_usd >= 50:
                            return 10
                        elif price_usd >= 20:
                            return 7
                        elif price_usd >= 5:
                            return 5
                        else:
                            return 3
                    else:
                        # Не продавался или нет данных
                        return 0
                else:
                    return 0
    except Exception as e:
        print(f"Ошибка проверки фрагмента: {e}")
        return 0

# Оценка юзернейма
async def rate_username(username: str) -> dict:
    username = username.strip("@")
    length = len(username)
    
    # 1. Оценка по длине
    if length >= 10:
        length_score = 0
    elif length >= 7:
        length_score = 5
    elif length == 6:
        length_score = 7
    elif length == 5:
        length_score = 8.5
    elif length <= 4:
        length_score = 10
    else:
        length_score = 0
    
    # 2. Оценка по фрагменту (реальная проверка)
    fragment_score = await check_fragment(username)
    
    # 3. Красота и читаемость
    if re.match(r'^[a-zA-Z]+$', username):  # Только буквы
        if username.islower() and len(set(username)) > 3:
            beauty_score = 8
        else:
            beauty_score = 6
    else:
        if '_' in username or any(c.isdigit() for c in username):
            beauty_score = 4
        else:
            beauty_score = 5
    
    # Проверка на читаемость (гласные/согласные)
    vowels = sum(1 for c in username if c in 'aeiouyAEIOUY')
    if len(username) > 4 and vowels / len(username) < 0.2:
        beauty_score = max(2, beauty_score - 3)
    
    # Если юзернейм красивый и читается легко
    if re.match(r'^[a-zA-Z]+$', username) and len(username) <= 6 and vowels / len(username) >= 0.3:
        beauty_score = max(7, beauty_score)
    
    # Итоговый средний балл
    final_score = round((length_score + fragment_score + beauty_score) / 3, 1)
    
    return {
        "length": length_score,
        "fragment": fragment_score,
        "beauty": beauty_score,
        "final": final_score
    }

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Добавить бота в чат", url="https://t.me/ваш_юзернейм_бота?startgroup=true")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 Пожалуйста, добавь бота в свою группу или чат, чтобы начать битву юзернеймов!",
        reply_markup=reply_markup
    )

# Обработка сообщений в группах
async def group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if message.new_chat_members:
        for member in message.new_chat_members:
            if member.id == context.bot.id:
                await message.reply_text(
                    "✅ Бот активен! Чтобы начать битву, ответь на сообщение участника командой:\n\n`.мог`"
                )
        return

# Обработка команды .мог
async def battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if not message.reply_to_message:
        await message.reply_text("❌ Ответь на сообщение участника командой `.мог`")
        return
    
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply_text("❌ Битва доступна только в группах!")
        return
    
    player1 = message.from_user
    player2 = message.reply_to_message.from_user
    
    if player1.id == player2.id:
        await message.reply_text("❌ Нельзя сражаться с самим собой!")
        return
    
    # Отправляем сообщение о начале оценки
    waiting_msg = await message.reply_text("⏳ Оцениваем юзернеймы...")
    
    u1 = player1.username or player1.first_name
    u2 = player2.username or player2.first_name
    
    # Оценка (асинхронная)
    score1 = await rate_username(u1)
    score2 = await rate_username(u2)
    
    # Формируем результат
    result = (
        f"⚔️ **БИТВА ЮЗЕРНЕЙМОВ** ⚔️\n\n"
        f"👤 {player1.first_name}: @{u1}\n"
        f"   📏 Длина: {score1['length']}/10\n"
        f"   💎 Фрагмент: {score1['fragment']}/10\n"
        f"   🎨 Красота: {score1['beauty']}/10\n"
        f"   **⭐ Итог: {score1['final']}/10**\n\n"
        f"👤 {player2.first_name}: @{u2}\n"
        f"   📏 Длина: {score2['length']}/10\n"
        f"   💎 Фрагмент: {score2['fragment']}/10\n"
        f"   🎨 Красота: {score2['beauty']}/10\n"
        f"   **⭐ Итог: {score2['final']}/10**\n\n"
    )
    
    if score1["final"] > score2["final"]:
        result += f"🏆 **Победил: {player1.first_name}!**"
    elif score2["final"] > score1["final"]:
        result += f"🏆 **Победил: {player2.first_name}!**"
    else:
        result += "🤝 **Ничья!**"
    
    await waiting_msg.delete()
    await message.reply_text(result, parse_mode="Markdown")

# Обработка текстовых сообщений
async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if message.reply_to_message and message.text and message.text.lower() == ".мог":
        await battle(update, context)

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    
    print("🤖 Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
