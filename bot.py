#!/usr/bin/env python3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext
import configparser
import json

# Загрузка данных из JSON-файла
def load_routes_data():
    with open('bot_db.json', 'r', encoding='utf-8') as file:
        return json.load(file)

# Чтение конфигурации
config = configparser.ConfigParser()
config.read('settings.ini')
tgramm_token = config['TOKEN']['token']

# Загружаем данные о маршрутах
routes_data = load_routes_data()

# Функция для обновления клавиатуры
async def update_keyboard(context: CallbackContext) -> None:
    job = context.job
    chat_id = job.chat_id

    # Получаем user_data из job.data
    user_data = job.data
    if not user_data:
        print("user_data не передан в задачу")
        return

    # Получаем message_id из user_data
    message_id = user_data.get('message_id')
    if not message_id:
        print("message_id не найден в user_data")
        return

    # Обновляем клавиатуру
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='update')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🕒 Клавиатура устарела. Нажмите /start для новой клавиатуры.",
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Ошибка при обновлении клавиатуры: {e}")


# Обработчик команды /start
async def start(update: Update, context: CallbackContext) -> None:
    # Инициализация user_data, если он не существует
    if not hasattr(context, 'user_data') or context.user_data is None:
        context.user_data = {}

    # Удаляем предыдущее сообщение, если оно существует
    if 'message_id' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.message.chat_id if update.message else update.callback_query.message.chat_id,
                message_id=context.user_data['message_id']
            )
        except Exception as e:
            print(f"Не удалось удалить сообщение: {e}")

    days = list(routes_data.keys())  # Получаем дни из данных
    keyboard = [days[i:i + 3] for i in range(0, len(days), 3)]
    keyboard = [[InlineKeyboardButton(day, callback_data=day) for day in row] for row in keyboard]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        message = await update.message.reply_text("Выберите день недели:", reply_markup=reply_markup)
    else:
        message = await update.callback_query.message.reply_text("Выберите день недели:", reply_markup=reply_markup)

    # Сохраняем ID сообщения
    context.user_data['message_id'] = message.message_id

    # Запускаем задачу для обновления клавиатуры через 5 минут
    if context.job_queue is not None:
        chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
        # Передаем user_data в задачу через context.job.data
        context.job_queue.run_once(
            update_keyboard,  # Теперь функция определена, и ошибки не будет
            300,  # 300 секунд = 5 минут
            chat_id=chat_id,
            data=context.user_data  # Передаем user_data через data
        )
    else:
        print("Job queue is not available.")


# Обработчик нажатий на кнопки инлайн-клавиатуры
async def button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'update':
        await start(update, context)
    elif query.data == 'back':
        if 'prev_step' in context.user_data:
            prev_step = context.user_data['prev_step']
            if prev_step == 'day_selection':
                days = list(routes_data.keys())  # Получаем дни из данных
                keyboard = [days[i:i + 3] for i in range(0, len(days), 3)]
                keyboard = [[InlineKeyboardButton(day, callback_data=day) for day in row] for row in keyboard]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text="Выберите день недели:", reply_markup=reply_markup)
                context.user_data['prev_step'] = None
            elif prev_step == 'route_selection':
                day = context.user_data.get('selected_day')
                if day in routes_data:
                    routes = list(routes_data[day].keys())
                    # Разбиваем маршруты на группы по 2 в каждой строке
                    keyboard = [routes[i:i + 3] for i in range(0, len(routes), 3)]
                    keyboard = [[InlineKeyboardButton(route, callback_data=f"{day}_{route}") for route in row] for row in keyboard]
                    # Добавляем кнопки "Назад" и "Отмена" в отдельную строку
                    keyboard.append([
                        InlineKeyboardButton("⬅️ Назад", callback_data='back'),
                        InlineKeyboardButton("❌ Отмена", callback_data='cancel')
                    ])
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(text=f"Выберите маршрут для {day}:", reply_markup=reply_markup)
                    context.user_data['prev_step'] = 'day_selection'
        else:
            await query.edit_message_text(text="❌ Невозможно вернуться назад. Нажмите /start, чтобы начать заново.")
    elif query.data == 'cancel':
        await query.edit_message_text(text="❌ Действие отменено. Нажмите /start, чтобы начать заново.")
    else:
        if '_' in query.data:
            day, route = query.data.split('_', maxsplit=1)
            if day in routes_data and route in routes_data[day]:
                addresses = routes_data[day][route]
                address_groups = [addresses[i:i + 5] for i in range(0, len(addresses), 5)]
                response = f"📍 Адреса для маршрута '{route}' ({day}):\n\n"
                for group in address_groups:
                    response += "\n".join(group) + "\n\n"
                keyboard = [
                    [
                        InlineKeyboardButton("⬅️ Назад", callback_data='back'),
                        InlineKeyboardButton("❌ Отмена", callback_data='cancel')
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text=response, reply_markup=reply_markup)
                context.user_data['prev_step'] = 'route_selection'
                context.user_data['selected_day'] = day
            else:
                await query.edit_message_text(text="❌ Маршрут не найден.")
        else:
            day = query.data
            if day in routes_data:
                routes = list(routes_data[day].keys())
                # Разбиваем маршруты на группы по 2 в каждой строке
                keyboard = [routes[i:i + 3] for i in range(0, len(routes), 3)]
                keyboard = [[InlineKeyboardButton(route, callback_data=f"{day}_{route}") for route in row] for row in keyboard]
                # Добавляем кнопки "Назад" и "Отмена" в отдельную строку
                keyboard.append([
                    InlineKeyboardButton("⬅️ Назад", callback_data='back'),
                    InlineKeyboardButton("❌ Отмена", callback_data='cancel')
                ])
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text=f"Выберите маршрут для {day}:", reply_markup=reply_markup)
                context.user_data['prev_step'] = 'day_selection'
                context.user_data['selected_day'] = day
            else:
                await query.edit_message_text(text="❌ День не найден.")

# Основная функция
def main() -> None:
    application = Application.builder().token(tgramm_token).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click))

    application.run_polling()


if __name__ == '__main__':
    main()