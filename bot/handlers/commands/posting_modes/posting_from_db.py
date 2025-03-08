import asyncio
import sqlite3

from bot.config import TIMEOUT_DELAY, DB_MAIN_ACCOUNTS_DIRECTORY, DB_TASK_DIRECTORY
from bot.handlers.commands.api.dtf_api import DtfApi
from bot.handlers.commands.api.vc_api import VcApi
from bot.handlers.commands.logging import log
from bot.handlers.commands.posting_modes.common import update_status_db, bot_message, data_upload_v3, \
    init_link_indexing_param_v2, posting_article_db


async def publishing_db(event, account_mark, source_mark, blacklist_articles, chat_id: int):
    """Публикация ранее сгенерированных статей из общей базы данных"""

    await event.wait()

    timeout_articles, flag, account, articles = await data_upload_v3(account_mark, source_mark, blacklist_articles)

    await event.wait()

    indexing, indexing_obj, searchengine = await init_link_indexing_param_v2()

    await event.wait()

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT articles_links_count FROM TasksSettings WHERE id = 1")
        posts_amount = int(cursor.fetchone()[0])

    await event.wait()

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
        proxy_port=proxy_port,
        posts_amount=posts_amount
    )

    platform.is_published = True if flag == 'True' else False

    for article in articles:
        text = f"Статья (ID) {article_id} публикуется на {account_email}. Аккаунт (ID): {account_id}."

        log.debug(text)
        await update_status_db(text)

        await event.wait()

        article_id, article_text, article_image = article

        auth, account_info, user_data, user_info, image_upload, image_info, publishing, \
            article_url, publishing_info = await posting_article_db(platform,
                                                                 account_id,
                                                                 accessToken,
                                                                 DB_MAIN_ACCOUNTS_DIRECTORY,
                                                                 article_text,
                                                                 article_image
                                                                 )

        await event.wait()

        if auth and user_data and publishing and image_upload:
            if indexing:
                for search in searchengine.split('+'):
                    await event.wait()

                    indexing_post, indexing_info = indexing_obj.link_indexing(article_url, search)
                    if not indexing_post:
                        text = (f'<a href="{article_url}">Ссылка</a> не отправлена на индексацию.\n\n'
                                f'<b>Поисковик:</b> {search}\n'
                                f'<b>Причина:</b> {indexing_info}')
                        await bot_message(chat_id=chat_id, text=text)
                        log.debug(text)
                    await asyncio.sleep(2)
                    await event.wait()
            text = f"Статья (ID) {article_id} опубликована на {account_email}. Аккаунт (ID): {account_id}."
            log.debug(text)
            await update_status_db(text)
            await event.wait()
        else:
            info = user_info if user_info == 'Аккаунт заблокирован' \
                else (f"Результат авторизации: {account_info}\n"
                      f"Результат получения данных пользователя: {user_info}\n"
                      f"Результат загрузки изображения: {image_info}\n"
                      f"Результат публикации статьи: {publishing_info}")

            text = (f"Ошибка публикации статьи из БД для аккаунта {account_email}. "
                    f"Аккаунт (ID): {account_id}. Статья (ID): {article_id}\n\n"
                    f"Информация:\n" + info)

            await bot_message(chat_id=chat_id, text=text)
            log.debug(text)
            await event.wait()

            if user_info == 'Аккаунт заблокирован':
                with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        "UPDATE Accounts SET "
                        "accessToken = ?"
                        "WHERE id = ?",
                        ('-', account_id)
                    )
                    connection.commit()
                await bot_message(chat_id=chat_id,
                                  text='Процесс публикации статей из базы данных завершён из-за критической ошибки: '
                                       'аккаунт заблокирован.')
                return

        await event.wait()
        await asyncio.sleep(int(timeout_articles))
        await event.wait()

    await bot_message(chat_id=chat_id, text='Процесс публикации статей из базы данных завершён.')