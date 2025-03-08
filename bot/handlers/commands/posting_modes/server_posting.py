import asyncio
import os
import re
import sqlite3
from uuid import uuid4

from aiogram.types import FSInputFile

from bot.app import bot
from bot.config import TIMEOUT_DELAY, DB_MAIN_ACCOUNTS_DIRECTORY, DB_TASK_DIRECTORY
from bot.handlers.commands.api.dtf_api import DtfApi
from bot.handlers.commands.api.vc_api import VcApi
from bot.handlers.commands.logging import log
from bot.handlers.commands.posting_modes.common import bot_message, get_account_by_mark, posting_article_server, \
   init_link_indexing_param_v2

async def data_upload(account_mark):
   """Загрузка необходимых данных"""
   account = await get_account_by_mark(account_mark)
   with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
      cursor = connection.cursor()
      cursor.execute("SELECT timeout_posting_articles, flag_posting_for_main FROM TasksSettings WHERE id = 1")
      timeout_articles, flag = cursor.fetchone()
   return account, timeout_articles, flag

async def send_articles_list(chat_id: int, unpublished_articles: list[str]):
   """Отправка неопубликованных статей в txt-файле"""
   file_path = f"{uuid4()}.txt"
   with open(file_path, "w", encoding="utf-8") as file:
      file.write("\n".join(map(str, unpublished_articles)))
   await bot.send_document(chat_id, FSInputFile(file_path), caption="Список неопубликованных статей.")

async def server_articles_publishing(event, account_mark, articles_path, chat_id: int):
   """Публикация статей с внешнего сервера."""

   await event.wait()
   account, timeout_articles, flag = await data_upload(account_mark)
   await event.wait()
   indexing, indexing_obj, searchengine = await init_link_indexing_param_v2()
   await event.wait()

   with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
      cursor = connection.cursor()
      cursor.execute("SELECT currents_replace, new_replace FROM TasksSettings WHERE id = 1")
      currents_replace, new_replace = cursor.fetchone()
   await event.wait()
   with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
      cursor = connection.cursor()
      cursor.execute("SELECT articles_links_count FROM TasksSettings WHERE id = 1")
      posts_amount = int(cursor.fetchone()[0])

   await event.wait()

   if currents_replace != 'None':
      currents_replace = currents_replace.strip().split('\n')

   await bot_message(chat_id=chat_id, text=f'Режим публикации статей с внешнего сервера запущен.\n\n'
                                           f'<b>Полученные данные:</b>\n'
                                           f'Выбрано статей: {len(articles_path)} шт.\n\n'
                                           f'Информация будет приходить в виде сообщений.')
   await event.wait()

   articles_publishing = 0
   unpublished_articles = []

   account_id, account_email, account_password, account_login,\
   proxy_ip, proxy_port, proxy_login, proxy_password,\
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

   for article_path in articles_path:
      await event.wait()

      try:

         auth, account_info, user_data, user_info, publishing, article_url, publishing_info = \
            await posting_article_server(platform,
                                         account_id,
                                         accessToken,
                                         article_path,
                                         currents_replace,
                                         new_replace
                                         )
         await event.wait()

         if auth and user_data and publishing:
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
            log.debug(f"Статья (Path) {article_path} опубликована на {account_email} в режиме публикации статей с внешнего сервера.")
            articles_publishing += 1
         else:
            match = re.search(r"/([^/]+)\.json$", article_path)
            article_id = match.group(1)
            unpublished_articles.append(article_id)

            info = user_info if user_info == 'Аккаунт заблокирован' \
               else (f"Результат авторизации: {account_info}\n"
                     f"Результат получения данных пользователя: {user_info}\n"
                     f"Результат публикации статьи: {publishing_info}")

            text = (f"Ошибка публикации в режиме постинга с внешнего сервера для аккаунта {account_email}. ID Аккаунта: {account_id}. "
                    f"Статья (Path): {article_path}\n\n"
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
                                    text='Процесс публикации статей с внешнего сервера завершён из-за критической ошибки: '
                                         'аккаунт заблокирован.')
                  return

      except Exception as e:
         match = re.search(r"/([^/]+)\.json$", article_path)
         article_id = match.group(1)
         unpublished_articles.append(article_id)
         text = f"Ошибка публикации статьи (Path) {article_path} для аккаунта (ID) {account_id} в режиме постинга с внешнего сервера: {e}"
         log.debug(text)
         await bot_message(chat_id=chat_id, text=text)
         await event.wait()

      os.remove(article_path)
      await event.wait()
      await asyncio.sleep(int(timeout_articles))
      await event.wait()

   await bot_message(chat_id=chat_id, text=f'На аккаунт {account_email} опубликовано статей с внешнего сервера в количестве: <b>{articles_publishing}</b> шт.')

   if unpublished_articles:
      await send_articles_list(chat_id=chat_id, unpublished_articles=unpublished_articles)