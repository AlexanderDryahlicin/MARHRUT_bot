from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters
import configparser
import json

# Загрузка данных из JSON-файлов
def load_routes_data():
    with open('bot_db.json', 'r', encoding='utf-8') as file:
        return json.load(file)

def load_comments_data():
    try:
        with open('comments_db.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}  # Если файл не найден, возвращаем пустой словарь

def save_comments_data(comments_data):
    with open('comments_db.json', 'w', encoding='utf-8') as file:
        json.dump(comments_data, file, ensure_ascii=False, indent=4)

# Чтение конфигурации
config = configparser.ConfigParser()
config.read('settings.ini')
tgramm_token = config['TOKEN']['token']

# Загружаем данные о маршрутах и комментариях
routes_data = load_routes_data()
comments_data = load_comments_data()

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

# Обработчик команды /comment
async def comment(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /comment <адрес> <комментарий>")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Использование: /comment <адрес> <комментарий>")
        return

    address = context.args[0]
    comment_text = ' '.join(context.args[1:])

    # Сохраняем комментарий
    comments_data[address] = comment_text
    save_comments_data(comments_data)

    await update.message.reply_text(f"Комментарий для адреса '{address}' успешно добавлен.")

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
    elif query.data.startswith('address_'):
        # Обработка нажатия на адрес
        address = query.data.replace('address_', '')
        comment = comments_data.get(address, None)

        # Формируем клавиатуру
        keyboard = []

        # Если комментарий есть, показываем его
        if comment:
            text = f"📍 Адрес: {address}\n\n💬  {comment}"
        else:
            # Если комментария нет, предлагаем добавить
            text = f"📍 Адрес: {address}\n\n💬  Комментарий отсутствует."
            keyboard.append([InlineKeyboardButton("💬 Добавить комментарий", callback_data=f"add_comment_{address}")])

        # Добавляем кнопку "Назад" под кнопкой "Добавить комментарий"
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup
        )
    elif query.data.startswith('add_comment_'):
        # Обработка нажатия на "Добавить комментарий"
        address = query.data.replace('add_comment_', '')
        context.user_data['address_for_comment'] = address

        # Формируем клавиатуру с кнопкой "Назад"
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data=f"address_{address}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем сообщение с запросом комментария и сохраняем его message_id
        message = await query.edit_message_text(
            text=f"Введите комментарий для адреса '{address}':",
            reply_markup=reply_markup
        )
        context.user_data['comment_request_message_id'] = message.message_id
        # Устанавливаем состояние ожидания комментария
        context.user_data['waiting_for_comment'] = True
    else:
        if '_' in query.data:
            day, route = query.data.split('_', maxsplit=1)
            if day in routes_data and route in routes_data[day]:
                addresses = routes_data[day][route]
                # Формируем текст и клавиатуру
                response = f"📍 Адреса для маршрута '{route}' ({day}):\n\n"
                keyboard = []
                for address in addresses:
                    # Каждый адрес — это отдельная кнопка
                    keyboard.append([InlineKeyboardButton(address, callback_data=f"address_{address}")])
                # Добавляем кнопки "Назад" и "Отмена"
                keyboard.append([
                    InlineKeyboardButton("⬅️ Назад", callback_data='back'),
                    InlineKeyboardButton("❌ Отмена", callback_data='cancel')
                ])
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

# Обработчик текстовых сообщений (для комментариев)
async def handle_message(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('waiting_for_comment'):
        address = context.user_data.get('address_for_comment')
        comment_text = update.message.text

        # Сохраняем комментарий
        comments_data[address] = comment_text
        save_comments_data(comments_data)

        # Удаляем сообщение с запросом комментария
        if 'comment_request_message_id' in context.user_data:
            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=context.user_data['comment_request_message_id']
                )
            except Exception as e:
                print(f"Не удалось удалить сообщение с запросом комментария: {e}")

        # Удаляем сообщение пользователя с комментарием
        try:
            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
        except Exception as e:
            print(f"Не удалось удалить сообщение пользователя: {e}")

        # Формируем клавиатуру с кнопкой "Назад"
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data=f"address_{address}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Комментарий для адреса '{address}' успешно добавлен.",
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_comment'] = False
        context.user_data['address_for_comment'] = None
        context.user_data['comment_request_message_id'] = None

# Основная функция
def main() -> None:
    application = Application.builder().token(tgramm_token).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('comment', comment))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()