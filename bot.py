from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    MessageHandler,
    filters,
)
import configparser
import json
import os

# Создание папки для фотографий, если она не существует
if not os.path.exists("photos"):
    os.makedirs("photos")

# Загрузка данных из JSON-файлов
def load_routes_data():
    try:
        with open("bot_db.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def load_comments_data():
    try:
        with open("comments_db.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def save_comments_data(comments_data):
    try:
        with open("comments_db.json", "w", encoding="utf-8") as file:
            json.dump(comments_data, file, ensure_ascii=False, indent=4)
    except Exception:
        pass

# Чтение конфигурации
config = configparser.ConfigParser()
config.read("settings.ini")
tgramm_token = config["TOKEN"]["token"]

# Загружаем данные о маршрутах и комментариях
routes_data = load_routes_data()
comments_data = load_comments_data()

# Функция для обновления клавиатуры
async def update_keyboard(context: CallbackContext) -> None:
    job = context.job
    chat_id = job.chat_id
    user_data = job.data

    if not user_data:
        return

    message_id = user_data.get("message_id")
    if not message_id:
        return

    keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data="update")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🕒 Клавиатура устарела. Нажмите /start для новой клавиатуры.",
            reply_markup=reply_markup,
        )
    except Exception:
        pass

# Обработчик команды /start
async def start(update: Update, context: CallbackContext) -> None:
    if not hasattr(context, "user_data") or context.user_data is None:
        context.user_data = {}

    if "message_id" in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.message.chat_id if update.message else update.callback_query.message.chat_id,
                message_id=context.user_data["message_id"],
            )
        except Exception:
            pass

    days = list(routes_data.keys())
    keyboard = [days[i : i + 3] for i in range(0, len(days), 3)]
    keyboard = [[InlineKeyboardButton(day, callback_data=day) for day in row] for row in keyboard]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        message = await update.message.reply_text("Выберите день недели:", reply_markup=reply_markup)
    else:
        message = await update.callback_query.message.reply_text("Выберите день недели:", reply_markup=reply_markup)

    context.user_data["message_id"] = message.message_id

    if context.job_queue is not None:
        chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
        context.job_queue.run_once(
            update_keyboard,
            300,
            chat_id=chat_id,
            data=context.user_data,
        )

# Обработчик команды /comment
async def comment(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /comment <адрес> <комментарий>")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Использование: /comment <адрес> <комментарий>")
        return

    address = context.args[0]
    comment_text = " ".join(context.args[1:])

    if address not in comments_data:
        comments_data[address] = {"comment": comment_text, "photo": None}
    else:
        comments_data[address]["comment"] = comment_text
    save_comments_data(comments_data)

    await update.message.reply_text(f"Комментарий для адреса '{address}' успешно добавлен.")

# Обработчик нажатий на кнопки инлайн-клавиатуры
async def button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        return

    if query.data == "update":
        await start(update, context)
    elif query.data == "back":
        if context.user_data.get("on_address_screen"):
            day = context.user_data.get("selected_day")
            route = context.user_data.get("selected_route")
            if day and route:
                addresses = routes_data[day][route]
                response = f"📍 Адреса для маршрута '{route}' ({day}):\n\n"
                keyboard = []
                for address in addresses:
                    keyboard.append([InlineKeyboardButton(address, callback_data=f"address_{address}")])
                keyboard.append(
                    [
                        InlineKeyboardButton("⬅️ Назад", callback_data="back"),
                        InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
                    ]
                )
                reply_markup = InlineKeyboardMarkup(keyboard)

                try:
                    await context.bot.delete_message(
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id,
                    )
                except Exception:
                    pass

                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=response,
                    reply_markup=reply_markup,
                )

                context.user_data["on_address_screen"] = False
        elif "prev_step" in context.user_data:
            prev_step = context.user_data["prev_step"]
            if prev_step == "day_selection":
                days = list(routes_data.keys())
                keyboard = [days[i : i + 3] for i in range(0, len(days), 3)]
                keyboard = [[InlineKeyboardButton(day, callback_data=day) for day in row] for row in keyboard]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text="Выберите день недели:", reply_markup=reply_markup)
                context.user_data["prev_step"] = None
            elif prev_step == "route_selection":
                day = context.user_data.get("selected_day")
                if day in routes_data:
                    routes = list(routes_data[day].keys())
                    keyboard = [routes[i : i + 3] for i in range(0, len(routes), 3)]
                    keyboard = [[InlineKeyboardButton(route, callback_data=f"{day}_{route}") for route in row] for row in keyboard]
                    keyboard.append(
                        [
                            InlineKeyboardButton("⬅️ Назад", callback_data="back"),
                            InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
                        ]
                    )
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(text=f"Выберите маршрут для {day}:", reply_markup=reply_markup)
                    context.user_data["prev_step"] = "day_selection"
        else:
            await query.edit_message_text(text="❌ Невозможно вернуться назад. Нажмите /start, чтобы начать заново.")
    elif query.data == "cancel":
        await query.edit_message_text(text="❌ Действие отменено. Нажмите /start, чтобы начать заново.")
    elif query.data.startswith("address_"):
        address = query.data.replace("address_", "")
        comment_data = comments_data.get(address, {"comment": None, "photo": None})
        comment = comment_data.get("comment", None)
        photo = comment_data.get("photo", None)

        context.user_data["on_address_screen"] = True
        context.user_data["current_address"] = address

        keyboard = []

        if comment:
            text = f"📍 Адрес: {address}\n\n💬  {comment}"
            if not photo:
                keyboard.append([InlineKeyboardButton("📷 Добавить фото", callback_data=f"add_photo_{address}")])
        else:
            text = f"📍 Адрес: {address}\n\n💬  Комментарий отсутствует."
            keyboard.append([InlineKeyboardButton("💬 Добавить комментарий", callback_data=f"add_comment_{address}")])

        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        if photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=open(photo, "rb"), caption=text),
                reply_markup=reply_markup
            )
            context.user_data["has_photo"] = True
        else:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup
            )
            context.user_data["has_photo"] = False
    elif query.data.startswith("add_comment_"):
        address = query.data.replace("add_comment_", "")
        context.user_data["address_for_comment"] = address

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=f"address_{address}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        comment_data = comments_data.get(address, {"comment": None, "photo": None})
        photo = comment_data.get("photo", None)

        if photo:
            await query.edit_message_caption(
                caption=f"Введите комментарий для адреса '{address}':",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                text=f"Введите комментарий для адреса '{address}':",
                reply_markup=reply_markup
            )

        context.user_data["comment_request_message_id"] = query.message.message_id
        context.user_data["waiting_for_comment"] = True
    elif query.data.startswith("add_photo_"):
        address = query.data.replace("add_photo_", "")
        context.user_data["address_for_photo"] = address

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=f"address_{address}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        comment_data = comments_data.get(address, {"comment": None, "photo": None})
        photo = comment_data.get("photo", None)

        if photo:
            await query.edit_message_caption(
                caption=f"Отправьте фото для адреса '{address}':",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                text=f"Отправьте фото для адреса '{address}':",
                reply_markup=reply_markup
            )

        context.user_data["photo_request_message_id"] = query.message.message_id
        context.user_data["waiting_for_photo"] = True
    else:
        if "_" in query.data:
            day, route = query.data.split("_", maxsplit=1)
            if day in routes_data and route in routes_data[day]:
                addresses = routes_data[day][route]
                response = f"📍 Адреса для маршрута '{route}' ({day}):\n\n"
                keyboard = []
                for address in addresses:
                    keyboard.append([InlineKeyboardButton(address, callback_data=f"address_{address}")])
                keyboard.append(
                    [
                        InlineKeyboardButton("⬅️ Назад", callback_data="back"),
                        InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
                    ]
                )
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text=response, reply_markup=reply_markup)
                context.user_data["prev_step"] = "route_selection"
                context.user_data["selected_day"] = day
                context.user_data["selected_route"] = route
            else:
                await query.edit_message_text(text="❌ Маршрут не найден.")
        else:
            day = query.data
            if day in routes_data:
                routes = list(routes_data[day].keys())
                keyboard = [routes[i : i + 3] for i in range(0, len(routes), 3)]
                keyboard = [[InlineKeyboardButton(route, callback_data=f"{day}_{route}") for route in row] for row in keyboard]
                keyboard.append(
                    [
                        InlineKeyboardButton("⬅️ Назад", callback_data="back"),
                        InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
                    ]
                )
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text=f"Выберите маршрут для {day}:", reply_markup=reply_markup)
                context.user_data["prev_step"] = "day_selection"
                context.user_data["selected_day"] = day
            else:
                await query.edit_message_text(text="❌ День не найден.")

# Обработчик текстовых сообщений (для комментариев)
async def handle_message(update: Update, context: CallbackContext) -> None:
    if context.user_data.get("waiting_for_comment"):
        address = context.user_data.get("address_for_comment")
        comment_text = update.message.text

        if address not in comments_data:
            comments_data[address] = {"comment": comment_text, "photo": None}
        else:
            comments_data[address]["comment"] = comment_text
        save_comments_data(comments_data)

        if "comment_request_message_id" in context.user_data:
            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=context.user_data["comment_request_message_id"],
                )
            except Exception:
                pass

        try:
            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=update.message.message_id,
            )
        except Exception:
            pass

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=f"address_{address}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Комментарий для адреса '{address}' успешно добавлен.", reply_markup=reply_markup
        )
        context.user_data["waiting_for_comment"] = False
        context.user_data["address_for_comment"] = None
        context.user_data["comment_request_message_id"] = None

# Обработчик загрузки фотографий
async def handle_photo(update: Update, context: CallbackContext) -> None:
    if context.user_data.get("waiting_for_photo"):
        address = context.user_data.get("address_for_photo")
        try:
            photo_file = await update.message.photo[-1].get_file()
            photo_path = f"photos/{address}.jpg"
            await photo_file.download_to_drive(photo_path)

            if address not in comments_data:
                comments_data[address] = {"comment": None, "photo": photo_path}
            else:
                comments_data[address]["photo"] = photo_path
            save_comments_data(comments_data)

            if "photo_request_message_id" in context.user_data:
                try:
                    await context.bot.delete_message(
                        chat_id=update.message.chat_id,
                        message_id=context.user_data["photo_request_message_id"],
                    )
                except Exception:
                    pass

            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=update.message.message_id,
                )
            except Exception:
                pass

            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=f"address_{address}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"Фото для адреса '{address}' успешно добавлено.", reply_markup=reply_markup
            )
        except Exception:
            await update.message.reply_text("Произошла ошибка при обработке фото.")
        finally:
            context.user_data["waiting_for_photo"] = False
            context.user_data["address_for_photo"] = None
            context.user_data["photo_request_message_id"] = None

# Основная функция
def main() -> None:
    application = Application.builder().token(tgramm_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("comment", comment))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    application.run_polling()

if __name__ == "__main__":
    main()