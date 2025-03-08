import asyncio
import os
import sqlite3
import logging

from random import randint

from bot.config import DB_TASK_DIRECTORY, TIMEOUT_DELAY, DB_DIRECTORY, DB_MAIN_ACCOUNTS_DIRECTORY, \
    DB_MULTI_ACCOUNTS_DIRECTORY, DB_PATTERNS_DIRECTORY, DB_OPENAI_API_KEY_DIRECTORY, DB_ARTICLES_DIRECTORY
from bot.handlers.commands.api.dtf_api import DtfApi
from bot.handlers.commands.api.openai_api import send_prompt_to_chatgpt_text, send_prompt_to_chatgpt_image
from bot.handlers.commands.api.vc_api import VcApi
from bot.handlers.commands.logging import get_task_logger
from bot.handlers.commands.commands_manager import CommandsManager
from bot.handlers.commands.posting_modes.common import mark_prompt_as_used, save_article_to_db, posting_article, \
    bot_message, get_priority_prompts, get_prompts, get_accounts, init_link_indexing_param_v1, get_account_by_mark_v2, \
    update_keys_data

task_pause_events = {}

async def remove_task_log(task_name):
    """Удаление лога задания"""

    log_path = os.path.join('bot/assets/logs', f"log_{task_name}.txt")
    logger = logging.getLogger(task_name)

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    if os.path.exists(log_path):
        os.remove(log_path)

async def pause_handler(task_name):
    """Обработчик паузы для конкретной задачи"""

    await task_pause_events[task_name].wait()

async def toggle_pause(task_name):
    """Переключить состояние паузы для конкретной задачи"""

    task_log = get_task_logger(task_name)

    if task_pause_events[task_name].is_set():
        task_pause_events[task_name].clear()  # Включить паузу
        task_log.debug(f"{task_name} приостановлено.")
    else:
        task_pause_events[task_name].set()  # Снять паузу
        task_log.debug(f"{task_name} возобновлено.")

async def is_delete(task_name: str) -> bool:
    """Проверка на существование задания"""

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM Tasks WHERE task_name = ?", (task_name,))
        task_exists = cursor.fetchone()

        if not task_exists:
            return True

    return False

async def update_article_mark_multi(db_path, article_id, account_login, article_url):
    """Обновление отметки статьи в базе данных после успешной публикации (Мульти-режим)"""

    connection = sqlite3.connect(db_path, timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE Articles SET "
        "account_login = ?, "
        "article_url = ?"
        "WHERE id = ?",
        (account_login, article_url, article_id)
    )
    connection.commit()
    connection.close()

async def check_load_all_data(task_name, DB_ACCOUNTS, task_type):
    """Проверка загрузки всех необходимых ресурсов"""

    all_resources_reload = False

    while not all_resources_reload:
        with sqlite3.connect(DB_OPENAI_API_KEY_DIRECTORY, timeout=TIMEOUT_DELAY) as conn_api:
            cursor_api = conn_api.cursor()
            cursor_api.execute("SELECT api_key FROM ApiKey WHERE id = 1")
            api_key = cursor_api.fetchone()[0]

        with sqlite3.connect(DB_ACCOUNTS, timeout=TIMEOUT_DELAY) as conn_accounts:
            cursor_accounts = conn_accounts.cursor()
            cursor_accounts.execute("SELECT COUNT(*) FROM Accounts")
            accounts_count = cursor_accounts.fetchone()[0]

        with sqlite3.connect(DB_PATTERNS_DIRECTORY, timeout=TIMEOUT_DELAY) as conn_templates:
            cursor_templates = conn_templates.cursor()
            cursor_templates.execute("SELECT COUNT(*) FROM Patterns")
            patterns_count = cursor_templates.fetchone()[0]

        connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM Prompts")
        prompts_count = cursor.fetchone()[0]
        connection.commit()
        connection.close()

        await pause_handler(task_name)

        if task_type != 'Основной':
            with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT delay, posts_count FROM Tasks WHERE task_name = ?", (task_name,))
                delay, posts_count = cursor.fetchone()

        if accounts_count == 0 or patterns_count == 0 or prompts_count == 0 or api_key == '-':
            await asyncio.sleep(5)
        elif (task_type != 'Основной') and (delay is None or posts_count is None):
            await asyncio.sleep(5)
        else:
            all_resources_reload = True

async def run_task_script(event, task_name, task_type, chat_id, choice_account) -> None:
    """Основная функция постинга статей"""

    await event.wait()

    task_pause_events[task_name] = asyncio.Event()
    task_pause_events[task_name].set()

    task_log = get_task_logger(task_name)
    DB_ACCOUNTS = DB_MAIN_ACCOUNTS_DIRECTORY if task_type == 'Основной' else DB_MULTI_ACCOUNTS_DIRECTORY

    await toggle_pause(task_name)
    await pause_handler(task_name)

    try:
        await check_load_all_data(task_name, DB_ACCOUNTS, task_type)

        indexing, indexing_obj, searchengine = await init_link_indexing_param_v1(task_name)

        priority_prompt_ids = await get_priority_prompts(task_name, DB_TASK_DIRECTORY)

        await pause_handler(task_name)

        if task_type == 'Основной':
            with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT articles_links_count FROM TasksSettings WHERE id = 1")
                posts_amount = int(cursor.fetchone()[0])

            await pause_handler(task_name)

            connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
            cursor = connection.cursor()
            cursor.execute("SELECT timeout_task_cycle, timeout_posting_articles FROM TasksSettings WHERE id = 1")
            timeout_cycle, timeout_articles = cursor.fetchone()
            connection.close()

            await pause_handler(task_name)

            with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                cursor = connection.cursor()
                if timeout_cycle == '-':
                    cursor.execute("SELECT timeout_task_cycle FROM TasksSettings WHERE id = 1")
                    timeout_cycle = cursor.fetchone()[0]
                if timeout_articles == '-':
                    cursor.execute("SELECT timeout_posting_articles FROM TasksSettings WHERE id = 1")
                    timeout_articles = cursor.fetchone()[0]

            await pause_handler(task_name)

            connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
            cursor = connection.cursor()
            cursor.execute("SELECT flag_posting_for_main FROM TasksSettings WHERE id = 1")
            flag_posting_for_main = cursor.fetchone()[0]
            connection.close()

            if flag_posting_for_main == '-':
                with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                    cursor = connection.cursor()
                    cursor.execute("SELECT flag_posting_for_main FROM TasksSettings WHERE id = 1")
                    flag_posting_for_main = cursor.fetchone()[0]
        else:
            with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT delay, posts_count FROM Tasks WHERE task_name = ?", (task_name,))
                delay, posts_count = cursor.fetchone()

        prompts = await get_prompts(DB_DIRECTORY + task_name + '.db', priority_prompt_ids)

        await pause_handler(task_name)

        if choice_account:
            accounts = await get_account_by_mark_v2(choice_account)
        else:
            accounts = await get_accounts(DB_ACCOUNTS)

        total_prompts = len(prompts)  # Всего промтов
        total_accounts = len(accounts) # Всего аккаунтов

        articles_publishing = 0  # Количество опубликованных статей
        published_combinations = set()  # Отслеживание опубликованных комбинаций
        banned_list = set() # Множество заблокированных аккаунтов
        max_combinations = total_prompts * total_accounts # Максимальное количество комбинаций/статей
        shift = 0  # Для циклического смещения

        # unmarked_articles = [] # Список для статей без отметки

        if task_type != 'Основной':
            published_articles_per_account = {account[0]: 0 for account in accounts}

        await CommandsManager.update_task_status_db(
            task=task_name,
            status=(
                f"Подготовка.\n\n"
                f"<b>Информация:</b>\n"
                f"Общее количество промтов: {total_prompts}\n"
                f"Общее количество аккаунтов: {total_accounts}\n"
                f"Отработанных статей: {len(published_combinations)} из"
                        f" {max_combinations if task_type == 'Основной' else max_combinations - int(posts_count)*total_accounts}\n"
                f"Общее количество опубликованных статей: {articles_publishing}"
            ),
        )

        await pause_handler(task_name)

        while len(published_combinations) < max_combinations:
            all_accounts_reached_limit = True

            for prompt_idx in range(total_prompts):
                account_idx = (prompt_idx + shift) % total_accounts
                account_id = accounts[account_idx][0]

                if account_id in banned_list:
                    if task_type != 'Основной':
                        published_articles_per_account[account_id] += 1
                    published_combinations.add((prompt_idx, account_idx))
                    continue

                if task_type != 'Основной':
                    if published_articles_per_account[account_id] >= int(posts_count):
                        published_combinations.add((prompt_idx, account_idx))
                        continue
                    else:
                        all_accounts_reached_limit = False

                prompt_id, prompt, prompt_theme, xlsx_id = prompts[prompt_idx]  # Текущий промт

                account_id, account_email, account_password, account_login, \
                    proxy_ip, proxy_port, proxy_login, proxy_password, accessToken, \
                    account_url = accounts[account_idx]  # Текущий аккаунт

                if task_type == 'Основной':
                    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
                    cursor = connection.cursor()
                    cursor.execute("SELECT marks FROM Prompts WHERE id = ?", (prompt_id,))
                    current_marks = cursor.fetchone()[0]
                    connection.close()
                    account_mark = f"{"vc" if "vc" in account_url.lower() else "dtf"}-{account_id}"

                    if (current_marks is not None and account_mark in current_marks and
                            not((prompt_idx, account_idx) in published_combinations)):
                        articles_publishing += 1
                        published_combinations.add((prompt_idx, account_idx))

                # Проверяем, если комбинация уже была опубликована
                if (prompt_idx, account_idx) in published_combinations:
                    continue

                await CommandsManager.update_task_status_db(
                    task=task_name,
                    status=(
                        f"Генерация текста и изображения.\n\n"
                        f"<b>Информация:</b>\n"
                        f"Общее количество промтов: {total_prompts}\n"
                        f"Общее количество аккаунтов: {total_accounts}\n"
                        f"Отработанных статей: {len(published_combinations)} из"
                        f" {max_combinations if task_type == 'Основной' 
                        else max_combinations - int(posts_count)*total_accounts}\n"
                        f"Общее количество опубликованных статей: {articles_publishing}\n\n"
                        f"<b>Текущие данные:</b>\n"
                        f"Промт (ID): {prompt_id}\n"
                        f"Аккаунт: {account_email}"
                    ),
                )

                await pause_handler(task_name)

                # Генерация текста
                result_text, result_text_info = await send_prompt_to_chatgpt_text(prompt, task_name)

                await pause_handler(task_name)

                await asyncio.sleep(randint(1, 3))

                if result_text:
                    # Генерация изображения
                    result_image, result_image_path = await send_prompt_to_chatgpt_image(prompt_theme, task_name)
                else:
                    result_image, result_image_path = False, '-'

                await pause_handler(task_name)

                if result_text and result_image:
                    await mark_prompt_as_used(task_name, prompt_id, account_id, account_url)

                    await pause_handler(task_name)

                    # Сохранение статьи
                    article_id = await save_article_to_db(
                        task_name,
                        result_text,
                        result_image_path,
                        account_id,
                        account_url
                    )

                    if task_type == 'Основной':
                        acc_mark = f"{"vc" if "vc" in account_url.lower() else "dtf"}-{account_id}"

                        with sqlite3.connect(DB_ARTICLES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                            cursor = connection.cursor()
                            cursor.execute("INSERT INTO Articles (article_text, article_image, marks) VALUES (?, ?, ?)",
                                           (result_text, result_image_path, acc_mark))
                            connection.commit()

                    # Платформа для публикации
                    platform = (VcApi if 'vc' in account_url else DtfApi)(
                        email=account_email,
                        password=account_password,
                        task=task_name,
                        task_type=task_type,
                        proxy_login=proxy_login,
                        proxy_pass=proxy_password,
                        proxy_ip=proxy_ip,
                        proxy_port=proxy_port,
                        posts_amount=posts_amount
                    )

                    if task_type != 'Основной':
                        platform.posts_amount = None

                    if task_type == 'Основной':
                        platform.is_published = True if flag_posting_for_main == 'True' else False

                    await CommandsManager.update_task_status_db(
                        task=task_name,
                        status=(
                            f"Публикация статьи.\n\n"
                            f"<b>Информация:</b>\n"
                            f"Общее количество промтов: {total_prompts}\n"
                            f"Общее количество аккаунтов: {total_accounts}\n"
                            f"Отработанных статей: {len(published_combinations)} из"
                            f" {max_combinations if task_type == 'Основной' 
                            else max_combinations - int(posts_count)*total_accounts}\n"
                            f"Общее количество опубликованных статей: {articles_publishing}\n\n"
                            f"<b>Текущие данные:</b>\n"
                            f"Статья (ID): {article_id}\n"
                            f"Аккаунт: {account_email}"
                        ),
                    )

                    await pause_handler(task_name)

                    auth, account_info, user_data, user_info, image_upload, image_info, publishing,\
                    article_url, publishing_info = await posting_article(platform,
                                                                         account_id,
                                                                         accessToken,
                                                                         DB_ACCOUNTS,
                                                                         result_text,
                                                                         result_image_path
                                                                        )

                    if auth and user_data and image_upload and publishing:
                        await pause_handler(task_name)
                        await update_keys_data(xlsx_id, article_url, account_login)
                        await pause_handler(task_name)

                        if task_type != 'Основной':
                            await update_article_mark_multi(
                                DB_DIRECTORY + task_name + ".db",
                                article_id,
                                account_login,
                                article_url
                            )

                            published_articles_per_account[account_id] += 1
                            await pause_handler(task_name)

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

                        task_log.debug(f"Статья (ID) {article_id} опубликована на {account_email}.")
                        articles_publishing += 1
                    else:
                        info = user_info if user_info == 'Аккаунт заблокирован'\
                            else (f"Результат авторизации: {account_info}\n"
                                  f"Результат получения данных пользователя: {user_info}\n"
                                  f"Результат загрузки изображения: {image_info}\n"
                                  f"Результат публикации статьи: {publishing_info}")

                        text = (f"Ошибка публикации для аккаунта {account_email}. ID Аккаунта: {account_id}. "
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

                        await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) '+text)
                        task_log.debug(text)

                        if user_info == 'Аккаунт заблокирован':
                            banned_list.add(account_id)

                            with sqlite3.connect(DB_ACCOUNTS, timeout=TIMEOUT_DELAY) as connection:
                                cursor = connection.cursor()
                                cursor.execute(
                                    "UPDATE Accounts SET "
                                    "accessToken = ?"
                                    "WHERE id = ?",
                                    ('-', account_id)
                                )
                                connection.commit()

                        if task_type != 'Основной':
                            published_articles_per_account[account_id] += 1

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

                    published_combinations.add((prompt_idx, account_idx))

                else:
                    if result_text_info == 'content_policy_violation':
                        text = (f"Ошибка генерации текста статьи для аккаунта {account_email} (ID): {account_id}.\n\n"
                                f"Промт (ID) {prompt_id} нарушает политику об отношении контента OpenAI.")
                        task_log.debug(text)
                        await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) '+text)

                    elif result_text_info == 'quota':
                        text = "Ошибка генерации текста и изображения. Проверьте баланс API-ключа OpenAI."
                        task_log.debug(text)
                        await CommandsManager.update_task_status_db(task=task_name, status=text)
                        await bot_message(chat_id=chat_id, text=text+f' (<b>{task_name}</b>)')

                        with sqlite3.connect(DB_OPENAI_API_KEY_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                            cursor = connection.cursor()
                            cursor.execute(
                                "SELECT api_key FROM ApiKey WHERE id = 1"
                            )
                            last_api_key = cursor.fetchone()[0]
                            api_key = last_api_key

                        await pause_handler(task_name)

                        while last_api_key == api_key:

                            with sqlite3.connect(DB_OPENAI_API_KEY_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                                cursor = connection.cursor()
                                cursor.execute(
                                    "SELECT api_key FROM ApiKey WHERE id = 1"
                                )
                                api_key = cursor.fetchone()[0]
                                await asyncio.sleep(5)

                            await pause_handler(task_name)
                    else:
                        if result_image_path == 'content_policy_violation_image':
                            text = (
                                f"Ошибка генерации изображения статьи для аккаунта {account_email} (ID): {account_id}.\n\n"
                                f"Тема промта (ID) {prompt_id} нарушает политику об отношении контента OpenAI.")
                            task_log.debug(text)
                            await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) '+text)
                        else:
                            text = (f"Ошибка генерации текста и изображения. "
                                    f"Промт не будет отработан для аккаунта {account_email}.\n\n"
                                    f"Ответ запроса генерации текста: {result_text_info}\n"
                                    f"Ответ запроса генерации изображения: {result_image_path}")
                            task_log.debug(text)
                            await bot_message(chat_id=chat_id, text=f'(<b>{task_name}</b>) '+text)
                            published_combinations.add((prompt_idx, account_idx))

                # Задержка перед следующей публикацией
                if task_type != 'Основной':
                    timeout_post = int(delay)
                else:
                    timeout_post = int(timeout_articles)

                if (total_accounts == 1 and task_type == 'Основной') or (task_type != 'Основной'):
                    await CommandsManager.update_task_status_db(
                        task=task_name,
                        status=(
                            f"Тайм-аут {int(timeout_post / 60)} мин.\n\n"
                            f"<b>Информация:</b>\n"
                            f"Общее количество промтов: {total_prompts}\n"
                            f"Общее количество аккаунтов: {total_accounts}\n"
                            f"Отработанных статей: {len(published_combinations)} из"
                            f" {max_combinations if task_type == 'Основной' 
                            else max_combinations - int(posts_count)*total_accounts}\n"
                            f"Общее количество опубликованных статей: {articles_publishing}"
                        ),
                    )

                prompts = await get_prompts(DB_DIRECTORY + task_name + '.db', priority_prompt_ids)

                if task_type != 'Основной':
                    await asyncio.sleep(timeout_post)
                else:
                    if total_accounts == 1:
                        await asyncio.sleep(timeout_post)

                    if choice_account:
                        accounts = await get_account_by_mark_v2(choice_account)
                    else:
                        accounts = await get_accounts(DB_ACCOUNTS)

                await pause_handler(task_name)

            shift += 1

            if task_type != 'Основной' and all_accounts_reached_limit:
                task_log.info("Все доступные аккаунты достигли лимита публикаций.")
                break

            if task_type == 'Основной':

                if len(published_combinations) < max_combinations:

                    await CommandsManager.update_task_status_db(
                        task=task_name,
                        status=(
                            f"Тайм-аут {int(int(timeout_cycle) / 60)} мин.\n\n"
                            f"<b>Информация:</b>\n"
                            f"Общее количество промтов: {total_prompts}\n"
                            f"Общее количество аккаунтов: {total_accounts}\n"
                            f"Отработанных статей: {len(published_combinations)} из {max_combinations}\n"
                            f"Общее количество опубликованных статей: {articles_publishing}"
                        ),
                    )

                    task_log.debug(f"Задержка {int(int(timeout_cycle) / 60)} мин. перед следующей серией публикаций.")
                    await asyncio.sleep(int(timeout_cycle)) # Задержка перед следующей серией публикаций

                    await pause_handler(task_name)

        await CommandsManager.update_task_status_db(
            task=task_name,
            status=(
                f"Задание завершено.\n\n"
                f"<b>Информация:</b>\n"
                f"Общее количество промтов: {total_prompts}\n"
                f"Общее количество аккаунтов: {total_accounts}\n"
                f"Отработанных статей: {len(published_combinations) if task_type == 'Основной' 
                else len(published_combinations) - int(posts_count)*total_accounts} из"
                f" {max_combinations if task_type == 'Основной' 
                else max_combinations - int(posts_count)*total_accounts}\n"
                f"Общее количество опубликованных статей: {articles_publishing}"
            ),
        )

        await bot_message(chat_id=chat_id, text=f'<b>{task_name}</b> завершено.')
        task_log.info("Задание завершено.")

    except Exception as e:
        error_message = f"Произошла ошибка при выполнении скрипта задания: {e}"
        await bot_message(chat_id=chat_id, text=error_message)
        task_log.debug(error_message)
        await CommandsManager.update_task_status_db(task=task_name, status=error_message)
        return