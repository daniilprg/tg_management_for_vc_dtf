import asyncio
import sqlite3
from random import randint

from bot.config import TIMEOUT_DELAY, DB_MAIN_ACCOUNTS_DIRECTORY, DB_DIRECTORY, DB_OPENAI_API_KEY_DIRECTORY, \
   DB_ARTICLES_DIRECTORY, DB_TASK_DIRECTORY
from bot.handlers.commands.api.dtf_api import DtfApi
from bot.handlers.commands.api.openai_api import send_prompt_to_chatgpt_text, send_prompt_to_chatgpt_image
from bot.handlers.commands.api.vc_api import VcApi
from bot.handlers.commands.logging import get_task_logger
from bot.handlers.commands.posting_modes.common import (bot_message, mark_prompt_as_used,
                                                        save_article_to_db, posting_article,
                                                        data_upload_v2, data_upload_v1, init_link_indexing_param_v1,
                                                        update_keys_data)


async def additional_public_db(event, task_name, account_mark, list_articles, chat_id):
   """Публикация ранее с генерированных статей из базы данных Задания."""

   await event.wait()

   task_log = get_task_logger(task_name)

   account, articles, white_list_articles, timeout_articles, flag = await data_upload_v1(task_name,
                                                                                         account_mark,
                                                                                         list_articles)
   await event.wait()

   with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
      cursor = connection.cursor()
      cursor.execute("SELECT articles_links_count FROM TasksSettings WHERE id = 1")
      posts_amount = int(cursor.fetchone()[0])

   await event.wait()

   indexing, indexing_obj, searchengine = await init_link_indexing_param_v1(task_name)

   await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) ' + f'Режим постинга из БД запущен.\n\n'
                                                   f'<b>Полученные данные:</b>\n'
                                                   f'Выбрано статей: {len(white_list_articles)}\n\n'
                                                   f'Информация будет приходить в виде сообщений.')
   await event.wait()

   articles_publishing = 0

   account_id, account_email, account_password, account_login,\
   proxy_ip, proxy_port, proxy_login, proxy_password,\
   accessToken, account_url = account

   platform = (VcApi if 'vc' in account_url else DtfApi)(
      email=account_email,
      password=account_password,
      task=task_name,
      task_type='Основной',
      proxy_login=proxy_login,
      proxy_pass=proxy_password,
      proxy_ip=proxy_ip,
      proxy_port=proxy_port,
      posts_amount=posts_amount
   )

   platform.is_published = True if flag == 'True' else False

   # Публикация ранее сгенерированных статей на изменённый аккаунт по ID
   for article in articles:
      await event.wait()
      try:
         article_id, article_text, article_image, xlsx_id = article

         if not int(article_id) in white_list_articles:
            continue

         auth, account_info, user_data, user_info, image_upload, image_info, publishing, \
            article_url, publishing_info = await posting_article(platform,
                                                                 account_id,
                                                                 accessToken,
                                                                 DB_MAIN_ACCOUNTS_DIRECTORY,
                                                                 article_text,
                                                                 article_image
                                                                 )
         await event.wait()

         if auth and user_data and publishing and image_upload:
            await event.wait()
            await update_keys_data(xlsx_id, article_url, account_login)
            await event.wait()
            if indexing:
               for search in searchengine.split('+'):
                  await event.wait()
                  indexing_post, indexing_info = indexing_obj.link_indexing(article_url, search)
                  if not indexing_post:
                     text = (f'<a href="{article_url}">Ссылка</a> не отправлена на индексацию.\n\n'
                             f'<b>Поисковик:</b> {search}\n'
                             f'<b>Причина:</b> {indexing_info}')
                     await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) ' + text)
                     task_log.debug(text)
                  await asyncio.sleep(2)
                  await event.wait()
            task_log.debug(f"Статья (ID) {article_id} опубликована на {account_email} в режиме постинга из БД.")
            articles_publishing += 1
         else:
            info = user_info if user_info == 'Аккаунт заблокирован' \
               else (f"Результат авторизации: {account_info}\n"
                     f"Результат получения данных пользователя: {user_info}\n"
                     f"Результат загрузки изображения: {image_info}\n"
                     f"Результат публикации статьи: {publishing_info}")

            text = (f"Ошибка публикации в режиме постинга из БД для аккаунта {account_email}. ID Аккаунта: {account_id}. "
                    f"Статья (ID): {article_id}\n\n"
                    f"Информация:\n" + info)

            connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
            cursor = connection.cursor()
            cursor.execute(
               "UPDATE Articles SET "
               "status = ?"
               "WHERE id = ?",
               (text, article_id)
            )
            connection.commit()
            connection.close()

            await event.wait()

            await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) '+text)
            task_log.debug(text)
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

      except Exception as e:
         text = f"Ошибка публикации статьи (ID) {article_id} для аккаунта (ID) {account_id} в режиме постинга из БД: {e}"
         task_log.debug(text)
         await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) '+text)
         await event.wait()

      await event.wait()
      await asyncio.sleep(int(timeout_articles))
      await event.wait()

   await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) постинг из БД завершён. '
                                           f'На аккаунт {account_email} опубликовано статей в количестве: <b>{articles_publishing}</b> шт.')

async def additional_public_prompts_skip(event, task_name, list_skip_prompts, account_mark, chat_id: int):
   """Генерация пропусков"""

   await event.wait()

   task_log = get_task_logger(task_name)

   account, prompts, white_list_skip_prompts, timeout_articles, flag = await data_upload_v2(task_name,
                                                                                            account_mark,
                                                                                            list_skip_prompts)
   await event.wait()
   indexing, indexing_obj, searchengine = await init_link_indexing_param_v1(task_name)
   await event.wait()

   with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
      cursor = connection.cursor()
      cursor.execute("SELECT articles_links_count FROM TasksSettings WHERE id = 1")
      posts_amount = int(cursor.fetchone()[0])
   await event.wait()


   await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) ' + f'Режим генерации пропусков.\n\n'
                                                   f'<b>Полученные данные:</b>\n'
                                                   f'Выбрано статей: {len(white_list_skip_prompts)}\n\n'
                                                   f'Информация будет приходить в виде сообщений.')
   await event.wait()

   articles_publishing = 0

   account_id, account_email, account_password, account_login,\
   proxy_ip, proxy_port, proxy_login, proxy_password,\
   accessToken, account_url = account

   platform = (VcApi if 'vc' in account_url else DtfApi)(
      email=account_email,
      password=account_password,
      task=task_name,
      task_type='Основной',
      proxy_login=proxy_login,
      proxy_pass=proxy_password,
      proxy_ip=proxy_ip,
      proxy_port=proxy_port,
      posts_amount=posts_amount
   )

   platform.is_published = True if flag == 'True' else False

   for prompt in prompts:
      await event.wait()
      prompt_id, prompt_text, prompt_theme, prompt_marks, xlsx_id = prompt

      if not int(prompt_id) in white_list_skip_prompts:
         continue

      if prompt_marks is None or account_mark not in prompt_marks:
         try:
            # Генерация текста
            result_text, result_text_info = await send_prompt_to_chatgpt_text(prompt_text, task_name)
            await event.wait()
            await asyncio.sleep(randint(1, 3))

            if result_text:
               # Генерация изображения
               result_image, result_image_path = await send_prompt_to_chatgpt_image(prompt_theme, task_name)
               await event.wait()
            else:
               result_image, result_image_path = False, '-'

            if result_text and result_image:
               await mark_prompt_as_used(task_name, prompt_id, account_id, account_url)
               await event.wait()

               # Сохранение статьи
               article_id = await save_article_to_db(
                  task_name,
                  result_text,
                  result_image_path,
                  account_id,
                  account_url
               )
               await event.wait()

               acc_mark = f"{"vc" if "vc" in account_url.lower() else "dtf"}-{account_id}"

               with sqlite3.connect(DB_ARTICLES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                  cursor = connection.cursor()
                  cursor.execute("INSERT INTO Articles (article_text, article_image, marks) VALUES (?, ?, ?)",
                                 (result_text, result_image_path, acc_mark))
                  connection.commit()

               await event.wait()

               auth, account_info, user_data, user_info, image_upload, image_info, publishing, \
                  article_url, publishing_info = await posting_article(platform,
                                                                       account_id,
                                                                       accessToken,
                                                                       DB_MAIN_ACCOUNTS_DIRECTORY,
                                                                       result_text,
                                                                       result_image_path
                                                                       )
               await event.wait()

               if auth and user_data and publishing and image_upload:
                  await event.wait()
                  await update_keys_data(xlsx_id, article_url, account_login)
                  await event.wait()

                  if indexing:
                     for search in searchengine.split('+'):
                        indexing_post, indexing_info = indexing_obj.link_indexing(article_url, search)
                        if not indexing_post:
                           text = (f'<a href="{article_url}">Ссылка</a> не отправлена на индексацию.\n\n'
                                   f'<b>Поисковик:</b> {search}\n'
                                   f'<b>Причина:</b> {indexing_info}')
                           await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) ' + text)
                           task_log.debug(text)
                        await asyncio.sleep(2)
                        await event.wait()
                  task_log.debug(f"Статья (ID) {article_id} опубликована на {account_email} в режиме генерации пропусков.")
                  articles_publishing += 1
               else:
                  info = user_info if user_info == 'Аккаунт заблокирован' \
                     else (f"Результат авторизации: {account_info}\n"
                           f"Результат получения данных пользователя: {user_info}\n"
                           f"Результат загрузки изображения: {image_info}\n"
                           f"Результат публикации статьи: {publishing_info}")

                  text = (f"Ошибка публикации в режиме генерации пропусков для аккаунта {account_email}. "
                          f"Аккаунт (ID): {account_id}. Статья (ID): {article_id}\n\n"
                          f"Информация:\n" + info)

                  connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
                  cursor = connection.cursor()
                  cursor.execute(
                     "UPDATE Articles SET "
                     "status = ?"
                     "WHERE id = ?",
                     (text, article_id)
                  )
                  connection.commit()
                  connection.close()
                  await event.wait()

                  await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) '+text)
                  task_log.debug(text)
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
                                          text='Процесс генерации пропусков завершён из-за критической ошибки: '
                                               'аккаунт заблокирован.')
                        return

               connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
               cursor = connection.cursor()
               cursor.execute(
                  "UPDATE Articles SET "
                  "xlsx_id = ?"
                  "WHERE id = ?",
                  (str(xlsx_id), article_id)
               )
               connection.commit()
               connection.close()

            else:
               if result_text_info == 'content_policy_violation':
                  text = (f"Ошибка генерации текста статьи для аккаунта {account_email} (ID): "
                          f"{account_id} в режиме генерации пропусков.\n\n"
                          f"Промт (ID) {prompt_id} нарушает политику об отношении контента OpenAI.")
                  task_log.debug(text)
                  await bot_message(chat_id=chat_id, text=text+f' (<b>{task_name}</b>)')
                  await event.wait()

               elif result_text_info == 'quota':
                  text = "Ошибка генерации текста и изображения. Проверьте баланс API-ключа OpenAI."
                  task_log.debug(text)
                  await bot_message(chat_id=chat_id, text=text+f' (<b>{task_name}</b>)')
                  await event.wait()

                  with sqlite3.connect(DB_OPENAI_API_KEY_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                     cursor = connection.cursor()
                     cursor.execute(
                        "SELECT api_key FROM ApiKey WHERE id = 1"
                     )
                     last_api_key = cursor.fetchone()[0]
                     api_key = last_api_key
                  await event.wait()

                  while last_api_key == api_key:

                     with sqlite3.connect(DB_OPENAI_API_KEY_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                        cursor = connection.cursor()
                        cursor.execute(
                           "SELECT api_key FROM ApiKey WHERE id = 1"
                        )
                        api_key = cursor.fetchone()[0]
                        await asyncio.sleep(5)
                     await event.wait()
               else:
                  if result_image_path == 'content_policy_violation_image':
                     text = (
                        f"Ошибка генерации изображения статьи для аккаунта {account_email} (ID): "
                        f"{account_id} в режиме генерации пропусков.\n\n"
                        f"Тема промта (ID) {prompt_id} нарушает политику об отношении контента OpenAI.")
                     task_log.debug(text)
                     await bot_message(chat_id=chat_id, text=text+f' (<b>{task_name}</b>)')
                     await event.wait()
                  else:
                     text = (
                        f"Ошибка генерации текста и изображения в режиме генерации пропусков.\n\n"
                        f"Ответ запроса генерации текста: {result_text_info}\n"
                        f"Ответ запроса генерации изображения: {result_image_path}")
                     task_log.debug(text)
                     await bot_message(chat_id=chat_id, text=text+f' (<b>{task_name}</b>)')
                     await event.wait()

         except Exception as e:
            text = f"Ошибка публикации статьи для аккаунта (ID) {account_id} в режиме генерации пропусков: {e}"
            task_log.debug(text)
            await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) '+text)

      text = f"Задержка {int(timeout_articles) / 60} мин. перед следующим аккаунтом. Режим генерации пропусков."
      task_log.debug(text)
      await event.wait()
      await asyncio.sleep(int(timeout_articles))
      await event.wait()

   await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) Генерация пропусков завершена. '
                                           f'На аккаунт {account_email} опубликовано статей в количестве: <b>{articles_publishing}</b> шт.')