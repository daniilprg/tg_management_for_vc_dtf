import asyncio
import os
import re
import sqlite3

from bot.config import DB_TASK_DIRECTORY, TIMEOUT_DELAY
from bot.handlers.commands.api.dtf_api import DtfApi
from bot.handlers.commands.api.vc_api import VcApi
from bot.handlers.commands.logging import log
from bot.handlers.commands.posting_modes.common import posting_article_v2, bot_message
from bot.handlers.commands.posting_modes.server_posting import data_upload


async def articles_editor_run(event, account_mark, urls_path, chat_id) -> None:

    await event.wait()

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT currents_replace, new_replace FROM TasksSettings WHERE id = 1")
        currents_replace, new_replace = cursor.fetchone()

    await event.wait()

    currents_replace = currents_replace.strip().split('\n')

    account, timeout_articles, flag = await data_upload(account_mark)

    await event.wait()

    article_ids = []

    with open(urls_path, "r", encoding="utf-8") as file:
        for url in file:
            url = url.strip()
            match = re.search(r'/(\d+)-[^/]+$', url)
            if match:
                article_id = match.group(1)
                article_ids.append(article_id)
    os.remove(urls_path)

    if len(article_ids) == 0:
        log.debug('ArticlesEditor: ошибка! Посты не найдены.')
        return

    await bot_message(chat_id=chat_id, text=f'Режим редактирования статей.\n\n'
                                            f'<b>Полученные данные:</b>\n'
                                            f'Выбрано статей: {len(article_ids)}\n\n'
                                            f'Информация будет приходить в виде сообщений.')

    await event.wait()

    log.debug('ArticlesEditor: получено постов -', len(article_ids), 'шт.\n')

    account_id, account_email, account_password, account_login, \
        proxy_ip, proxy_port, proxy_login, proxy_password, \
        accessToken, account_url = account

    platform = (VcApi if 'vc' in account_url else DtfApi)(
        email=account_email,
        password=account_password,
        task='-',
        task_type='Основной',
        proxy_login=proxy_login,
        proxy_pass=proxy_password,
        proxy_ip=proxy_ip,
        proxy_port=proxy_port
    )
    platform.is_published = True

    goods = 0

    remaining_articles = set(article_ids)
    error_count = 0

    while remaining_articles:
        await event.wait()

        for article_id in list(remaining_articles):
            await event.wait()
            auth, article_get, publishing, platform_accessToken = posting_article_v2(
                platform, account_id, article_id, accessToken, currents_replace, new_replace
            )
            await event.wait()

            accessToken = platform_accessToken

            if auth and article_get and publishing:
                remaining_articles.remove(article_id)
                goods += 1
            else:
                error_count += 1
                log.debug(f"ArticlesEditor: ошибка при редактировании статьи {article_id}")

                if error_count == 1:
                    log.debug("ArticlesEditor: первая ошибка, пауза на 3 минуты")
                    await event.wait()
                    await asyncio.sleep(180)
                    await event.wait()
                else:
                    log.debug(f"ArticlesEditor: ошибка {error_count}, пауза на 1 минуту")
                    await event.wait()
                    await asyncio.sleep(60)
                    await event.wait()

            await event.wait()
            await asyncio.sleep(8)
            await event.wait()

        error_count = 0

    message = (f"Редактирование статей завершено.\n\n"
               f"<b>Отредактировано статей:</b> {goods} шт.")
    await bot_message(chat_id=chat_id, text=message)
