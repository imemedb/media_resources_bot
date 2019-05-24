import json
import logging

import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters

from config import *

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


ALLOWED_ALGORITHMS = ["tfidf", "textrank", "topicrank", "yake"]


updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher


def start(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.message.chat_id,
        text="Добрый день! Я демостранционный бот суммаризации групп вк и выделения ключевых слов.\n"
        "Чтобы выделить ключевые слова какого-то текста на русском, пришли мне сообщение\n"
        "Чтобы вывести список доступных алгоритмов набери /list_algorithms\n"
        "Чтобы сменить алгоритм выделения ключевых слов набери /keywords_algorithm `algo_name`\n"
        "Чтобы задать количество ключевых слов набери /n_keywords `5`\n"
        "Чтобы создать суммаризацию группы набери /summarize_group `apiclub`, где название группы из https://vk.com/apiclub",
    )


def set_algorithm(update: Update, context: CallbackContext):
    algorithm = context.args[0] if len(context.args) else None
    if algorithm is None:
        message = (
            f"Вы не указали алгоритм, по умолчанию используется yake\n"
            f"Возможны следующие алгоритмы: {ALLOWED_ALGORITHMS}"
        )
    elif algorithm not in ALLOWED_ALGORITHMS:
        message = (
            f"Указынный алгоритм не поддерживается\n"
            f"Возможны следующие алгоритмы: {ALLOWED_ALGORITHMS}"
        )
    else:
        message = f"Теперь при извлечении ключевых слов используется алгоритм {algorithm}"
        context.user_data["algorithm"] = algorithm

    context.bot.send_message(chat_id=update.message.chat_id, text=message)


def set_n_keywords(update: Update, context: CallbackContext):
    n_keywords = 10
    try:
        n_keywords = abs(int(context.args[0])) if len(context.args) else 10
    except (TypeError, ValueError):
        pass

    context.user_data["n_keywords"] = n_keywords

    context.bot.send_message(
        chat_id=update.message.chat_id,
        text=f"Количество извлекаемых ключевых слов равно {n_keywords}",
    )


def list_algorithms(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.message.chat_id, text=str(ALLOWED_ALGORITHMS))


def __get_keywords(text, algorithm, n_keywords):
    keywords = requests.post(
        "http://127.0.0.1:5050/v0/keywords",
        data=json.dumps({"text": text, "algorithm": algorithm, "n_keywords": n_keywords}),
        headers={"Content-type": "application/json"},
    ).json()

    keywords = keywords.get("keywords", keywords.get("error"))

    return keywords


def get_keywords(update: Update, context: CallbackContext):
    text = update.message.text
    algorithm = context.user_data.get("algorithm", "yake")
    n_keywords = context.user_data.get("n_keywords", 10)

    keywords = __get_keywords(text, algorithm, n_keywords)

    context.bot.send_message(chat_id=update.message.chat_id, text=f"{keywords}")


def generate_post_link(group_id, post_id):
    return f"https://vk.com/wall-{group_id}_{post_id}"


def summarize_group(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        message = "Вы забыли передать название группы. Команда выглядит /summarize_group group_name"
        context.bot.send_message(chat_id=update.message.chat_id, text=message)
    else:
        algorithm = context.user_data.get("algorithm", "yake")
        n_keywords = context.user_data.get("n_keywords", 10)

        group_name = context.args[0]
        requests.post(
            "http://127.0.0.1:5055/v0/update_group",
            data=json.dumps({"group_name": group_name}),
            headers={"Content-type": "application/json"},
        )

        posts = requests.get(
            "http://127.0.0.1:5055/v0/get_posts",
            data=json.dumps({"group_name": group_name}),
            headers={"Content-type": "application/json"},
        ).json()

        text = "\n".join((post["text"] for post in posts))

        keywords = __get_keywords(text, algorithm, n_keywords)

        context.bot.send_message(chat_id=update.message.chat_id, text=f"{keywords}")

        for post in posts:
            text = post["text"]
            post_url = generate_post_link(abs(post["from_id"]), post["id"])

            keywords = __get_keywords(text, algorithm, n_keywords)

            context.bot.send_message(chat_id=update.message.chat_id, text=f"{keywords}\n{post_url}")


start_handler = CommandHandler("start", start)
keywords_handler = CommandHandler(
    "keywords_algorithm", set_algorithm, pass_args=True, pass_user_data=True
)
n_keywords = CommandHandler("n_keywords", set_n_keywords, pass_args=True, pass_user_data=True)
list_algorithms_handler = CommandHandler("list_algorithms", list_algorithms)
summarize_group_handler = CommandHandler(
    "summarize_group", summarize_group, pass_args=True, pass_user_data=True
)
conv_handler = MessageHandler(filters=Filters.text, callback=get_keywords, pass_user_data=True)

dispatcher.add_handler(start_handler)
dispatcher.add_handler(keywords_handler)
dispatcher.add_handler(list_algorithms_handler)
dispatcher.add_handler(conv_handler)
dispatcher.add_handler(summarize_group_handler)


updater.start_polling()
