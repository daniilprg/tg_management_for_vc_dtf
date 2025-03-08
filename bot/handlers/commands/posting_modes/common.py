import asyncio
import re
import sqlite3
from random import randint

from bot.app import bot
from bot.config import TIMEOUT_DELAY, DB_MAIN_ACCOUNTS_DIRECTORY, DB_DIRECTORY, DB_ARTICLES_DIRECTORY, \
    DB_TASK_DIRECTORY, DB_XLSX_DIRECTORY
from bot.handlers.commands.api.link_indexing_api import LinkIndexing
from bot.handlers.commands.logging import log

async def posting_article(platform,
                         account_id,
                         accessToken,
                         DB_ACCOUNTS,
                         result_text,
                         result_image_path
                         ):
    if accessToken == '-':
        auth, account_info, platform_accessToken = platform.platform_authorization()

        with sqlite3.connect(DB_ACCOUNTS, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()
    else:
        auth = True
        account_info = ''
        platform.accessToken = accessToken

    await asyncio.sleep(randint(1, 3))

    user_data, user_info = platform.platform_get_user_data()

    if not user_data:
        await asyncio.sleep(randint(2, 3))

        auth, account_info, platform_accessToken = platform.platform_authorization()

        with sqlite3.connect(DB_ACCOUNTS, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()

        if auth:
            await asyncio.sleep(randint(2, 3))
            user_data, user_info = platform.platform_get_user_data()

    await asyncio.sleep(randint(1, 3))

    image_upload, image_info = platform.platform_image_upload(result_image_path)

    if not image_upload:
        await asyncio.sleep(randint(1, 3))
        image_upload, image_info = platform.platform_image_upload(result_image_path)

    await asyncio.sleep(randint(1, 3))

    publishing, article_url, publishing_info = await platform.platform_publishing(result_text)

    if (not publishing) and ('401' in str(publishing_info)):
        await asyncio.sleep(60)

        auth, account_info, platform_accessToken = platform.platform_authorization()

        if not user_data:
            await asyncio.sleep(randint(2, 3))
            user_data, user_info = platform.platform_get_user_data()

        with sqlite3.connect(DB_ACCOUNTS, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()

        publishing, article_url, publishing_info = await platform.platform_publishing(result_text)

    return (auth,
            account_info,
            user_data,
            user_info,
            image_upload,
            image_info,
            publishing,
            article_url,
            publishing_info)

async def posting_article_db(platform,
                         account_id,
                         accessToken,
                         DB_ACCOUNTS,
                         result_text,
                         result_image_path
                         ):
    if accessToken == '-':
        auth, account_info, platform_accessToken = platform.platform_authorization_v2()

        with sqlite3.connect(DB_ACCOUNTS, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()
    else:
        auth = True
        account_info = ''
        platform.accessToken = accessToken

    await asyncio.sleep(randint(1, 3))

    user_data, user_info = platform.platform_get_user_data()

    if not user_data:
        await asyncio.sleep(randint(2, 3))

        auth, account_info, platform_accessToken = platform.platform_authorization_v2()

        with sqlite3.connect(DB_ACCOUNTS, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()

        if auth:
            await asyncio.sleep(randint(2, 3))
            user_data, user_info = platform.platform_get_user_data()

    await asyncio.sleep(randint(1, 3))

    image_upload, image_info = platform.platform_image_upload(result_image_path)

    if not image_upload:
        await asyncio.sleep(randint(1, 3))
        image_upload, image_info = platform.platform_image_upload(result_image_path)

    await asyncio.sleep(randint(1, 3))

    publishing, article_url, publishing_info = await platform.platform_publishing(result_text)

    if (not publishing) and ('401' in str(publishing_info)):
        await asyncio.sleep(60)

        auth, account_info, platform_accessToken = platform.platform_authorization_v2()

        if not user_data:
            await asyncio.sleep(randint(2, 3))
            user_data, user_info = platform.platform_get_user_data()

        with sqlite3.connect(DB_ACCOUNTS, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()

        publishing, article_url, publishing_info = await platform.platform_publishing(result_text)

    return (auth,
            account_info,
            user_data,
            user_info,
            image_upload,
            image_info,
            publishing,
            article_url,
            publishing_info)

async def posting_article_v2(platform,
                             account_id,
                             article_id,
                             accessToken,
                             currents_replace,
                             new_replace,
                             ):

    platform_accessToken = accessToken

    if accessToken == '-':
        auth, account_info, platform_accessToken = await platform.platform_authorization_v2()

        with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()
    else:
        auth = True
        account_info = ''
        platform.accessToken = accessToken

    await asyncio.sleep(randint(1, 3))

    article_get, article_data, article_info = platform.platform_get_exist_article(article_id)

    if not article_get:
        await asyncio.sleep(randint(2, 3))
        auth, account_info, platform_accessToken = await platform.platform_authorization_v2()

        with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()

        if auth:
            await asyncio.sleep(randint(2, 3))
            article_get, article_data, article_info = platform.platform_get_exist_article(article_id)
        else:
            return False, None, None, None

    await asyncio.sleep(randint(1, 3))

    publishing, article_url, publishing_info = platform.platform_article_edit(article_data, currents_replace, new_replace)

    if (not publishing) and ('401' in str(publishing_info)):
        await asyncio.sleep(60)

        auth, account_info, platform_accessToken = await platform.platform_authorization_v2()
        with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()
        await asyncio.sleep(randint(1, 3))
        publishing, article_url, publishing_info = platform.platform_article_edit(article_data, currents_replace, new_replace)

    if not publishing:
        return False, None, None, None

    return (auth,
            article_get,
            publishing,
            platform_accessToken
            )

async def get_account_by_mark(account_mark) -> list:
   """Получение данных аккаунта по ID из базы данных"""

   match_re = re.search(r'\d+', account_mark)
   account_id = int(match_re.group())

   with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as conn:
      cursor = conn.cursor()
      cursor.execute("""SELECT id, account_email, account_password, account_login,
      proxy_ip, proxy_port, proxy_login, proxy_password,
      accessToken, account_url FROM Accounts WHERE id = ?""", (account_id, ))
      account = cursor.fetchone()

   return account

async def get_account_by_mark_v2(account_mark) -> list:
   """Получение данных аккаунта по ID из базы данных"""

   match_re = re.search(r'\d+', account_mark)
   account_id = int(match_re.group())

   with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as conn:
      cursor = conn.cursor()
      cursor.execute("""SELECT id, account_email, account_password, account_login,
      proxy_ip, proxy_port, proxy_login, proxy_password,
      accessToken, account_url FROM Accounts WHERE id = ?""", (account_id, ))
      account = cursor.fetchall()

   return account

async def get_articles_by_ids(task_name, account_mark):
   """Получение ранее сгенерированных статей аккаунта по ID"""

   conn = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
   cursor = conn.cursor()
   cursor.execute("""SELECT id, article_text, article_image, xlsx_id FROM Articles WHERE marks = ?""", (account_mark,))
   articles = cursor.fetchall()
   conn.close()

   return articles

async def get_all_prompts(task_name):
   """Получение промтов"""

   conn = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
   cursor = conn.cursor()
   cursor.execute("""SELECT id, prompt, prompt_theme, marks, xlsx_id FROM Prompts""")
   prompts = cursor.fetchall()
   conn.close()

   return prompts

async def mark_prompt_as_used(task_name, prompt_id, account_id, account_url):
   """Отметка аккаунта у промта с префиксом в зависимости от account_url"""

   mark = f"{"vc" if "vc" in account_url.lower() else "dtf"}-{account_id}"

   connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
   cursor = connection.cursor()
   cursor.execute("SELECT marks FROM Prompts WHERE id = ?", (prompt_id,))
   current_marks = cursor.fetchone()[0]

   if current_marks:
      marks_set = list(current_marks.splitlines())
   else:
      marks_set = list()

   marks_set.append(mark)

   updated_marks = "\n".join(marks_set)
   cursor.execute(
      "UPDATE Prompts SET marks = ? WHERE id = ?",
      (updated_marks, prompt_id)
   )
   connection.commit()
   connection.close()

async def save_article_to_db(task_name, text, image, account_id, account_url):
   """Сохранение статьи в базу данных."""

   mark = f"{"vc" if "vc" in account_url.lower() else "dtf"}-{account_id}"

   connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
   cursor = connection.cursor()
   cursor.execute(
      """
      INSERT INTO Articles (article_text, article_image, marks)
      VALUES (?, ?, ?)
      """,
      (text, image, mark),
   )
   article_id = cursor.lastrowid
   connection.commit()
   connection.close()

   return article_id

async def bot_message(chat_id: int, text: str):
   try:
      await bot.send_message(chat_id=chat_id, text=text)
   except Exception as e:
      await asyncio.sleep(10)
      try:
         await bot.send_message(chat_id=chat_id, text=text)
      except Exception as e:
         pass

async def get_accounts(db_path: str) -> list:
    """Получение всех аккаунтов из базы данных"""

    with sqlite3.connect(db_path, timeout=TIMEOUT_DELAY) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, account_email, account_password, account_login,"
                       " proxy_ip, proxy_port, proxy_login, proxy_password, accessToken, account_url FROM Accounts")
        accounts = cursor.fetchall()

    return accounts

async def get_priority_prompts(task_name, db_path):
    """Получение приоритетных промтов"""

    with sqlite3.connect(db_path, timeout=TIMEOUT_DELAY) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT priority_prompts FROM Tasks WHERE task_name = ?", (task_name,))
        priority_prompts = cursor.fetchone()

        if priority_prompts:
            priority_prompts = priority_prompts[0]

            if priority_prompts == "-":
                return []
            else:
                start, end = map(int, priority_prompts.split('-'))
                return list(range(start, end + 1))

        return []

async def get_prompts(db_path, priority_prompt_ids=None) -> list:
    """Получение промтов из базы данных"""

    conn = sqlite3.connect(db_path, timeout=TIMEOUT_DELAY)
    cursor = conn.cursor()
    cursor.execute("SELECT id, prompt, prompt_theme, xlsx_id FROM Prompts")
    prompts = cursor.fetchall()

    if priority_prompt_ids:
        prompts = sorted(prompts, key=lambda x: (x[0] not in priority_prompt_ids, x[0]))

    conn.close()

    return prompts

async def update_keys_data(xlsx_id, article_url, account_login):

    try:
        with sqlite3.connect(DB_XLSX_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()

            cursor.execute("SELECT urls_accounts FROM Xlsx WHERE id = ?", (int(xlsx_id),))
            row = cursor.fetchone()

            new_entry = f"{article_url} {account_login}"

            if row and row[0]:
                updated_value = f"{row[0]} | {new_entry}"
            else:
                updated_value = new_entry

            # Обновляем поле
            cursor.execute("UPDATE Xlsx SET urls_accounts = ? WHERE id = ?", (updated_value, int(xlsx_id)))
            connection.commit()
    except Exception as e:
        log.debug(f"Произошла ошибка при обновлении данных ключа в базе данных: {str(e)}")

async def update_status_db(status: str):
    """Обновление статуса в базе данных"""

    try:
        with sqlite3.connect(DB_ARTICLES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE ArticlesStatus SET status = ? WHERE id = 1",
                (status,)
            )
            connection.commit()
    except Exception as e:
        log.debug(f"Произошла ошибка при обновлении статуса в базе данных: {str(e)}")

async def get_generated_articles(account_mark, blacklist_articles):
    """Получение ранее сгенерированных статей аккаунта с учетом черного списка"""

    blacklist_ids = [int(id_) for id_ in blacklist_articles.splitlines() if id_.strip().isdigit()]

    with sqlite3.connect(DB_ARTICLES_DIRECTORY, timeout=TIMEOUT_DELAY) as conn:
        cursor = conn.cursor()

        query = """SELECT id, article_text, article_image 
                   FROM Articles 
                   WHERE marks = ?"""
        params = [account_mark]

        if blacklist_ids:
            placeholders = ",".join("?" * len(blacklist_ids))
            query += f" AND id NOT IN ({placeholders})"
            params.extend(blacklist_ids)

        cursor.execute(query, params)
        articles = cursor.fetchall()

    return articles

async def data_upload_v1(task_name, account_mark, list_articles):
   """Загрузка необходимых данных"""

   account = await get_account_by_mark(account_mark)
   articles = await get_articles_by_ids(task_name, account_mark)
   white_list_articles = list(map(int, list_articles.strip().split("\n")))

   connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
   cursor = connection.cursor()
   cursor.execute("SELECT timeout_posting_articles, flag_posting_db FROM TasksSettings WHERE id = 1")
   timeout_articles, flag = cursor.fetchone()
   connection.close()

   if timeout_articles == '-':
       with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
          cursor = connection.cursor()
          cursor.execute("SELECT timeout_posting_articles FROM TasksSettings WHERE id = 1")
          timeout_articles = cursor.fetchone()[0]

   if flag == '-':
      with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
         cursor = connection.cursor()
         cursor.execute("SELECT flag_posting_db FROM TasksSettings WHERE id = 1")
         flag = cursor.fetchone()[0]

   return account, articles, white_list_articles, timeout_articles, flag

async def data_upload_v2(task_name, account_mark, list_skip_prompts):
   account = await get_account_by_mark(account_mark)
   prompts = await get_all_prompts(task_name)
   white_list_skip_prompts = list(map(int, list_skip_prompts.strip().split("\n")))

   connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
   cursor = connection.cursor()
   cursor.execute("SELECT timeout_posting_articles FROM TasksSettings WHERE id = 1")
   timeout_articles = cursor.fetchone()[0]
   connection.close()

   with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
      cursor = connection.cursor()
      if timeout_articles == '-':
         cursor.execute("SELECT timeout_posting_articles FROM TasksSettings WHERE id = 1")
         timeout_articles = cursor.fetchone()[0]

   connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
   cursor = connection.cursor()
   cursor.execute("SELECT flag_posting_db FROM TasksSettings WHERE id = 1")
   flag = cursor.fetchone()[0]
   connection.close()

   if flag == '-':
      with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
         cursor = connection.cursor()
         cursor.execute("SELECT flag_posting_db FROM TasksSettings WHERE id = 1")
         flag = cursor.fetchone()[0]

   return account, prompts, white_list_skip_prompts, timeout_articles, flag

async def data_upload_v3(account_mark, source_mark, blacklist_articles):
    """Получение необходимых ресурсов"""

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT timeout_posting_articles FROM TasksSettings WHERE id = 1")
        timeout_articles = int(cursor.fetchone()[0])
        cursor.execute("SELECT flag_posting_db FROM TasksSettings WHERE id = 1")
        flag = cursor.fetchone()[0]

    account = await get_account_by_mark(account_mark)
    articles = await get_generated_articles(source_mark, blacklist_articles)

    return timeout_articles, flag, account, articles

async def posting_article_server(platform,
                                 account_id,
                                 accessToken,
                                 article_path,
                                 currents_replace,
                                 new_replace
                                ):
    if accessToken == '-':
        auth, account_info, platform_accessToken = platform.platform_authorization_v2()

        with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()
    else:
        auth = True
        account_info = ''
        platform.accessToken = accessToken

    await asyncio.sleep(randint(1, 3))

    user_data, user_info = platform.platform_get_user_data()

    if not user_data:
        await asyncio.sleep(randint(2, 3))

        auth, account_info, platform_accessToken = platform.platform_authorization_v2()

        with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()

        if auth:
            await asyncio.sleep(randint(2, 3))
            user_data, user_info = platform.platform_get_user_data()

    await asyncio.sleep(randint(1, 3))

    publishing, article_url, publishing_info = await platform.platform_publishing_server(article_path, currents_replace, new_replace)

    if (not publishing) and ('401' in str(publishing_info)):
        await asyncio.sleep(60)

        auth, account_info, platform_accessToken = platform.platform_authorization_v2()

        if not user_data:
            await asyncio.sleep(randint(2, 3))
            user_data, user_info = platform.platform_get_user_data()

        with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Accounts SET "
                "accessToken = ?"
                "WHERE id = ?",
                (platform_accessToken, account_id)
            )
            connection.commit()

        publishing, article_url, publishing_info = await platform.platform_publishing_server(article_path, currents_replace, new_replace)

    return (auth,
            account_info,
            user_data,
            user_info,
            publishing,
            article_url,
            publishing_info)

async def init_link_indexing_param_v1(task_name):
    """Инициализация параметров индексации"""

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT indexing FROM TasksSettings WHERE id = 1")
    indexing = cursor.fetchone()[0]
    connection.close()

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()

        if indexing == '-':
            cursor.execute("SELECT indexing FROM TasksSettings WHERE id = 1")
            indexing = cursor.fetchone()[0]

    indexing = True if indexing == 'True' else False
    indexing_obj = None
    searchengine = None

    if indexing:
        connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
        cursor = connection.cursor()
        cursor.execute("SELECT user_id, api_key, searchengine, se_type FROM TasksSettings WHERE id = 1")
        user_id, api_key, searchengine, se_type = cursor.fetchone()
        connection.close()

        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()

            if user_id == '-':
                cursor.execute("SELECT user_id FROM TasksSettings WHERE id = 1")
                user_id = cursor.fetchone()[0]

            if api_key == '-':
                cursor.execute("SELECT api_key FROM TasksSettings WHERE id = 1")
                api_key = cursor.fetchone()[0]

            if searchengine == '-':
                cursor.execute("SELECT searchengine FROM TasksSettings WHERE id = 1")
                searchengine = cursor.fetchone()[0]

            if se_type == '-':
                cursor.execute("SELECT se_type FROM TasksSettings WHERE id = 1")
                se_type = cursor.fetchone()[0]

        indexing_obj = LinkIndexing(api_key=api_key,
                                    user_id=user_id,
                                    se_type=se_type,
                                    task=task_name)

    return indexing, indexing_obj, searchengine

async def init_link_indexing_param_v2():
    """Инициализация параметров индексации"""

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT indexing FROM TasksSettings WHERE id = 1")
        indexing = cursor.fetchone()[0]

    indexing = True if indexing == 'True' else False
    indexing_obj = None
    searchengine = None

    if indexing:
        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT user_id, api_key, searchengine, se_type FROM TasksSettings WHERE id = 1")
            user_id, api_key, searchengine, se_type = cursor.fetchone()

        indexing_obj = LinkIndexing(api_key=api_key,
                                    user_id=user_id,
                                    se_type=se_type,
                                    task='-')

    return indexing, indexing_obj, searchengine