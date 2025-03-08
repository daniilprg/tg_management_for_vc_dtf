import asyncio
import os
import re
import sqlite3
import uuid

import aiogram.exceptions
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, Message

from bot.config import DB_TASK_DIRECTORY, TIMEOUT_DELAY, DB_DIRECTORY
from bot.handlers.commands.admins_filter import AdminFilter
from bot.handlers.commands.posting_modes.extra_posting import additional_public_db, additional_public_prompts_skip
from bot.handlers.commands.logging import log, get_task_logger
from bot.handlers.commands.commands_manager import CommandsManager
from bot.handlers.commands.posting_modes.main_posting import toggle_pause, remove_task_log
from bot.handlers.commands.task_manager import manager
from bot.handlers.routers.control_panel import tasks
from bot.keyboards.keyboards import task_panel_keyboard, tasks_list, generate_pagination_keyboard, get_accounts_from_db

router_tasks_panel = Router(name=__name__)

class CountMessage(StatesGroup):
    message = State()

class DelayMessage(StatesGroup):
    message = State()

class AccountsMessage(StatesGroup):
    message_articles = State()

class AccountsPromptsMessage(StatesGroup):
    message_prompts = State()

class ModelTask(StatesGroup):
    message = State()

class TaskTimeoutCycle(StatesGroup):
    message = State()

class TaskTimeoutPost(StatesGroup):
    message = State()

class TaskFlagPost(StatesGroup):
    message = State()

class TaskKeyWord(StatesGroup):
    message = State()

class TaskIndexing(StatesGroup):
    message = State()

tasks_db, tasks_skips = {}, {}

async def back_to_task(task_name):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
    ])
    return keyboard

async def task_delete(task_name):
    try:
        log_message = f"{task_name} было удалено."
        log.debug(log_message)
        await remove_task_log(task_name)
    except Exception as e:
        pass

async def get_data_task(task_name: str):
    """Получение статуса задания"""

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT status, task_type FROM Tasks WHERE task_name = ?", (task_name,))
        status, task_type = cursor.fetchone()
        connection.commit()

    action = InlineKeyboardButton(text='⏸️ Пауза', callback_data=f'pause-{task_name}') if status != 'Приостановлено' \
        else InlineKeyboardButton(text='▶️ Продолжить', callback_data=f'continue-{task_name}')

    return status, task_type, action

async def task_panel_view(task_name, message, type_answer):
    status, task_type, action = await get_data_task(task_name)
    keyboard = await task_panel_keyboard(task_name, task_type, action)

    text = (f"⚙️ Панель управления (<b>{task_name}</b>):\n\n"
            f"<b>Режим работы:</b> {task_type}\n\n"
            f"<b>Статус:</b> {status}")

    if type_answer == 'edit_text':
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('self-task-'), AdminFilter())
async def task_panel_callback_query(call: CallbackQuery, state: FSMContext):
    """Панель задания"""
    task_name = call.data[10:]
    await task_panel_view(task_name=task_name, message=call.message, type_answer='edit_text')
    await state.set_state(None)
    await state.clear()

@router_tasks_panel.callback_query(lambda call: call.data.startswith('update-status-'), AdminFilter())
async def task_log_callback_query(call: CallbackQuery):
    """Обновление статуса в панели задания"""

    task_name = call.data[14:]

    try:
        status, task_type, action = await get_data_task(task_name)

        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT last_status FROM Tasks WHERE task_name = ?", (task_name,))
            last_status = cursor.fetchone()[0]
            connection.commit()

        if (status != last_status) and (status != 'Приостановлено'):

            keyboard = await task_panel_keyboard(task_name, task_type, action)
            await call.message.edit_text(f"⚙️ Панель управления (<b>{task_name}</b>):\n\n"
                                    f"<b>Режим работы:</b> {task_type}\n\n"
                                    f"<b>Статус:</b> {status}", reply_markup=keyboard)

            with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "UPDATE Tasks SET last_status = ? WHERE task_name = ?",
                    (status, task_name)
                )
                connection.commit()

    except aiogram.exceptions.TelegramBadRequest:
        pass

    except Exception as e:
        task_log = get_task_logger(task_name)
        task_log.debug(f"Произошла ошибка при обновлении статуса задания: {str(e)}.")


@router_tasks_panel.callback_query(lambda call: call.data.startswith('log-'), AdminFilter())
async def task_log_callback_query(call: CallbackQuery):
    """Выгрузка лога задания"""

    task_name = call.data[4:]
    file_path = f'bot/assets/logs/log_{task_name}.txt'
    await call.message.answer_document(FSInputFile(file_path), caption=f"Лог-файл")

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-delete-'), AdminFilter())
async def self_task_delete_callback_query(call: CallbackQuery):
    """Подтверждение удаления задания"""

    task_name = call.data[12:]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Да', callback_data=f'del-{task_name}'),
         InlineKeyboardButton(text='Нет', callback_data=f'self-task-{task_name}')]
    ])

    await call.message.edit_text(f"Вы уверены, что хотите удалить <b>{task_name}</b>?", reply_markup=keyboard)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('del-'), AdminFilter())
async def task_delete_callback_query(call: CallbackQuery):
    """Удаление задания и связанные с ним ресурсы"""

    task_name = call.data[4:]

    if task_name in tasks:
        tasks[task_name].cancel()
        del tasks[task_name]

    if task_name in tasks_db:
        tasks_db[task_name].cancel()
        del tasks_db[task_name]

    if task_name in tasks_skips:
        tasks_skips[task_name].cancel()
        del tasks_skips[task_name]

    try:
        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM Tasks WHERE task_name = ?", (task_name,))
            connection.commit()

        await call.message.edit_text(f"✅ <b>{task_name}</b> успешно удалено!")

    except Exception as e:
        try:
            await call.message.edit_text(f"✅ <b>{task_name}</b> успешно удалено!")
            asyncio.create_task(task_delete(task_name))
        except Exception as e:
            log.debug(f'Произошла ошибка: {str(e)}')

    keyboard = await tasks_list()
    await call.message.answer("Выберите задание или добавьте новое:", reply_markup=keyboard)

    try:
        await asyncio.sleep(10)
        os.remove(DB_DIRECTORY + task_name + '.db')
    except Exception as e:
        pass

@router_tasks_panel.callback_query(lambda call: call.data.startswith('pause-'), AdminFilter())
async def task_pause_callback_query(call: CallbackQuery):
    """Приостановка задания"""

    task_name = call.data[6:]

    await toggle_pause(task_name)

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT status, task_type FROM Tasks WHERE task_name = ?", (task_name,))
        status, task_type = cursor.fetchone()
        connection.commit()

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE Tasks SET last_status = ? WHERE task_name = ?",
            (status, task_name)
        )
        connection.commit()

    await CommandsManager.update_task_status_db(task=task_name, status='Приостановлено')

    action = InlineKeyboardButton(text='▶️ Продолжить', callback_data=f'continue-{task_name}')

    keyboard = await task_panel_keyboard(task_name, task_type, action)
    await call.message.edit_text(f"⚙️ Панель управления (<b>{task_name}</b>):\n\n"
                                f"<b>Режим работы:</b> {task_type}\n\n"
                                f"<b>Статус:</b> Приостановлено", reply_markup=keyboard)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('continue-'), AdminFilter())
async def task_continue_callback_query(call: CallbackQuery):
    """Воспроизведение задания"""

    task_name = call.data[9:]

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT last_status, task_type FROM Tasks WHERE task_name = ?", (task_name,))
        last_status, task_type = cursor.fetchone()
        connection.commit()

    if not manager.tasks[task_name]['event'].is_set():
        await call.message.answer("❌ Невозможно возобновить задание.\n\n"
                                  "<b>Причина:</b> выполняется задача с более высоким приоритетом.")
        action = InlineKeyboardButton(text='▶️ Продолжить', callback_data=f'continue-{task_name}')
        keyboard = await task_panel_keyboard(task_name, task_type, action)
        await call.message.answer(f"⚙️ Панель управления (<b>{task_name}</b>):\n\n"
                                     f"<b>Режим работы:</b> {task_type}\n\n"
                                     f"<b>Статус:</b> Приостановлено", reply_markup=keyboard)
        return

    await toggle_pause(task_name)

    await CommandsManager.update_task_status_db(task=task_name, status=last_status)

    action = InlineKeyboardButton(text='⏸️ Пауза', callback_data=f'pause-{task_name}')

    keyboard = await task_panel_keyboard(task_name, task_type, action)
    await call.message.edit_text(f"⚙️ Панель управления (<b>{task_name}</b>):\n\n"
                                f"<b>Режим работы:</b> {task_type}\n\n"
                                f"<b>Статус:</b> {last_status}", reply_markup=keyboard)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('count-posts-'), AdminFilter())
async def count_posts_callback_query(call: CallbackQuery, state: FSMContext):
    """Настройка добавления количества постов для Мульти-режима"""

    task_name = call.data[12:]
    await call.message.edit_text('Отправьте количество постов, которое должно добавляться на аккаунт.', reply_markup=await back_to_task(task_name))
    await state.update_data(task_name=task_name)
    await state.set_state(CountMessage.message)


@router_tasks_panel.message(CountMessage.message, AdminFilter())
async def count_posts_handler(message: Message, state: FSMContext):
    """Обновление настройки количества постов для Мульти-режима"""
    prompt_data = await state.get_data()
    task_name = prompt_data.get('task_name')

    if re.fullmatch(r'\d+', message.text):

        if int(message.text) <= 0:
            await message.answer("❌ Пожалуйста, введите корректное число.", reply_markup=await back_to_task(task_name))
            return

        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Tasks SET posts_count = ? WHERE task_name = ?",
                (message.text, task_name)
            )
            connection.commit()

        await message.answer(f"Количество постов для аккаунтов обновлено. (<b>{task_name}</b>)")
        await task_panel_view(task_name=task_name, message=message, type_answer='answer')
        await state.set_state(None)
        await state.clear()
    else:
        await message.answer("❌ Пожалуйста, введите корректное число.", reply_markup=await back_to_task(task_name))

@router_tasks_panel.callback_query(lambda call: call.data.startswith('delay-'), AdminFilter())
async def delay_callback_query(call: CallbackQuery, state: FSMContext):
    """Настройка добавления задержки между постами для Мульти-режима"""

    task_name = call.data[6:]
    await call.message.edit_text('Отправьте задержку между постами в минутах.', reply_markup=await back_to_task(task_name))
    await state.update_data(task_name=task_name)
    await state.set_state(DelayMessage.message)


@router_tasks_panel.message(DelayMessage.message, AdminFilter())
async def delay_handler(message: Message, state: FSMContext):
    """Обновление настройки задержки между постами для Мульти-режима"""

    prompt_data = await state.get_data()
    task_name = prompt_data.get('task_name')

    if re.fullmatch(r'\d+', message.text):

        if int(message.text) <= 0:
            await message.answer("❌ Пожалуйста, введите корректное число.", reply_markup=await back_to_task(task_name))
            return

        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE Tasks SET delay = ? WHERE task_name = ?",
                (str(int(message.text)*60), task_name)
            )
            connection.commit()

        await message.answer(f"✅ Задержка между постами обновлена. (<b>{task_name}</b>)")
        await task_panel_view(task_name=task_name, message=message, type_answer='answer')
        await state.set_state(None)
        await state.clear()
    else:
        await message.answer("❌ Пожалуйста, введите корректное число.", reply_markup=await back_to_task(task_name))

@router_tasks_panel.callback_query(lambda call: call.data.startswith('posting-many-func-'), AdminFilter())
async def posting_many_types_callback_query(call: CallbackQuery):
    """Режимы для изменённых аккаунтов задания"""

    task_name = call.data[18:]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Постинг из БД', callback_data=f'posting-from-db-{task_name}')],
        [InlineKeyboardButton(text='Постинг пропусков', callback_data=f'posting-prompts-skips-{task_name}')],
        [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
    ])

    await call.message.edit_text("Выберите режим:", reply_markup=keyboard)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('posting-from-db-'), AdminFilter())
async def posting_from_db_callback_query(call: CallbackQuery, state: FSMContext):
    """Постинг из БД для изменённых аккаунтов задания"""

    task_name = call.data[16:]

    if task_name not in tasks_db or tasks_db[task_name].done():
        if task_name in manager.tasks and len(manager.tasks[task_name]['accounts']) > 1:
            accounts = get_accounts_from_db()
            keyboard = generate_pagination_keyboard(accounts=accounts, page=0, type_selected='select_account_task_posting_db')
            await call.message.edit_text(f"Выберите аккаунт, на который нужно опубликовать статьи:", reply_markup=keyboard)
            await state.update_data(task_name=task_name,
                                    accounts=accounts,
                                    type_selected='select_account_task_posting_db',
                                    page=0)
        else:
            await call.message.edit_text(
                "Отправьте список ID статей, которые нужно опубликовать на аккаунте, в сообщении или txt-файле.\n\n"
                "<b>Примечание:</b> каждый ID с новой строки", reply_markup=await back_to_task(task_name))
            account_mark = manager.tasks[task_name]['accounts'].copy()
            await state.update_data(task_name=task_name, account_mark=account_mark.pop())
            await state.set_state(AccountsMessage.message_articles)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Завершить работу', callback_data=f'task-db-stop-{task_name}')],
            [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
        ])
        await call.message.edit_text("Запущен процесс публикации сгенерированных статей из базы данных.", reply_markup=keyboard)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('select_account_task_posting_db:'), AdminFilter())
async def posting_from_db_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    account_index = int(call.data.split(":")[1])

    task_name = data['task_name']
    selected_account = data['accounts'][account_index]

    account_mark = f"{"vc" if "vc" in selected_account[1].lower() else "dtf"}-{selected_account[0]}"

    await call.message.edit_text("Отправьте список ID статей, которые нужно опубликовать на аккаунт, в сообщении или txt-файле.\n\n"
                         "<b>Примечание:</b> каждый ID с новой строки", reply_markup=await back_to_task(task_name))

    await state.update_data(task_name=task_name, account_mark=account_mark)
    await state.set_state(AccountsMessage.message_articles)

@router_tasks_panel.message(AccountsMessage.message_articles, AdminFilter())
async def posting_from_db_create_handler(message: Message, state: FSMContext):
    panel_data = await state.get_data()
    task_name = panel_data.get('task_name')
    account_mark = panel_data.get('account_mark')

    if message.document:

        if not message.document.file_name.endswith('.txt'):
            await message.answer("❌ Пожалуйста, отправьте файл с расширением .txt", reply_markup=await back_to_task(task_name))
            return

        file_path = f"bot/assets/txt/{uuid.uuid4()}.txt"
        bot = message.bot
        await bot.download(message.document.file_id, destination=file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            list_articles = f.read()
        os.remove(file_path)

    elif message.text:
        list_articles = message.text

    else:
        await message.answer("❌ Пожалуйста, отправьте сообщение или txt-файл.", reply_markup=await back_to_task(task_name))
        return

    await message.answer(f"Запуск процесса постинга статей из базы данных (<b>{task_name}</b>)")

    start_task = asyncio.create_task(manager.add_task(2,
                                                      additional_public_db,
                                                      f'PostingDB_{task_name}',
                                                      [account_mark],
                                                      task_name,
                                                      account_mark,
                                                      list_articles,
                                                      message.chat.id
                                                      ))
    tasks_db[task_name] = start_task

    await task_panel_view(task_name=task_name, message=message, type_answer='answer')
    await state.set_state(None)
    await state.clear()
    await start_task

@router_tasks_panel.callback_query(lambda call: call.data.startswith('posting-prompts-skips-'), AdminFilter())
async def posting_from_prompts_skips_callback_query(call: CallbackQuery, state: FSMContext):
    """Постинг генерации пропусков для изменённых аккаунтов задания"""

    task_name = call.data[22:]

    if task_name not in tasks_skips or tasks_skips[task_name].done():
        if task_name in manager.tasks and len(manager.tasks[task_name]['accounts']) > 1:
            accounts = get_accounts_from_db()
            keyboard = generate_pagination_keyboard(accounts=accounts, page=0,
                                                    type_selected='select_account_task_posting_db')
            await call.message.edit_text(f"Выберите аккаунт, на который нужно сгенерировать пропуски:", reply_markup=keyboard)
            await state.update_data(task_name=task_name,
                                    accounts=accounts,
                                    type_selected='select_account_task_prompts_skips',
                                    page=0)
        else:
            await call.message.edit_text(
                "Отправьте список ID промтов, которые нужно отработать на аккаунт, в сообщении или txt-файле.\n\n"
                         "<b>Примечание:</b> каждый ID с новой строки", reply_markup=await back_to_task(task_name))
            account_mark = manager.tasks[task_name]['accounts'].copy()
            await state.update_data(task_name=task_name, account_mark=account_mark.pop())
            await state.set_state(AccountsPromptsMessage.message_prompts)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Завершить работу', callback_data=f'task-prompts-skips-stop-{task_name}')],
            [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
        ])
        await call.message.edit_text("Запущен процесс генерации пропусков.", reply_markup=keyboard)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('select_account_task_prompts_skips:'), AdminFilter())
async def posting_from_prompts_skips_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    account_index = int(call.data.split(":")[1])

    task_name = data['task_name']
    selected_account = data['accounts'][account_index]

    account_mark = f"{"vc" if "vc" in selected_account[1].lower() else "dtf"}-{selected_account[0]}"

    await call.message.edit_text("Отправьте список ID промтов, которые нужно отработать на аккаунт, в сообщении или txt-файле.\n\n"
                         "<b>Примечание:</b> каждый ID с новой строки", reply_markup=await back_to_task(task_name))

    await state.update_data(task_name=task_name, account_mark=account_mark)
    await state.set_state(AccountsPromptsMessage.message_prompts)

@router_tasks_panel.message(AccountsPromptsMessage.message_prompts, AdminFilter())
async def posting_from_prompts_skips_create_handler(message: Message, state: FSMContext):
    panel_data = await state.get_data()
    task_name = panel_data.get('task_name')
    account_mark = panel_data.get('account_mark')

    if message.document:

        if not message.document.file_name.endswith('.txt'):
            await message.answer("❌ Пожалуйста, отправьте файл с расширением .txt", reply_markup=await back_to_task(task_name))
            return

        file_path = f"bot/assets/txt/{uuid.uuid4()}.txt"
        bot = message.bot
        await bot.download(message.document.file_id, destination=file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            list_skip_prompts = f.read()
        os.remove(file_path)

    elif message.text:
        list_skip_prompts = message.text

    else:
        await message.answer("❌ Пожалуйста, отправьте сообщение или txt-файл.", reply_markup=await back_to_task(task_name))
        return

    await message.answer(f"Запуск процесса генерации пропусков (<b>{task_name}</b>)")

    start_task = asyncio.create_task(manager.add_task(2,
                                                      additional_public_prompts_skip,
                                                      f'PostingPrompts_{task_name}',
                                                      [account_mark],
                                                      task_name,
                                                      list_skip_prompts,
                                                      account_mark,
                                                      message.chat.id
                                                      ))
    tasks_skips[task_name] = start_task

    await task_panel_view(task_name=task_name, message=message, type_answer='answer')
    await state.set_state(None)
    await state.clear()
    await start_task

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-db-stop-'), AdminFilter())
async def stop_posting_from_db_callback_query(call: CallbackQuery):
    """Остановка постинг из базы данных"""

    task_name = call.data[13:]

    if task_name in tasks_db and not tasks_db[task_name].done():
        tasks_db[task_name].cancel()
        del tasks_db[task_name]
        await call.message.edit_text(f"Работа постинга из базы данных завершена принудительно. (<b>{task_name}</b>)")
    else:
        await call.message.edit_text("Нет активной задачи для остановки.")

    await task_panel_view(task_name=task_name, message=call.message, type_answer='answer')

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-prompts-skips-stop-'), AdminFilter())
async def stop_posting_from_prompts_skips_callback_query(call: CallbackQuery):
    """Остановка постинг пропусков"""

    task_name = call.data[24:]

    if task_name in tasks_skips and not tasks_skips[task_name].done():
        tasks_skips[task_name].cancel()
        del tasks_skips[task_name]
        await call.message.edit_text(f"Работа генерации пропусков завершена принудительно. (<b>{task_name}</b>)")
    else:
        await call.message.edit_text("Нет активной задачи для остановки.")

    await task_panel_view(task_name=task_name, message=call.message, type_answer='answer')

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-models-'), AdminFilter())
async def get_api_models_callback_query(call: CallbackQuery):
    """Модели задания OpenAI"""

    task_name = call.data[12:]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Модель текста', callback_data=f'task-text-model-{task_name}'),
         InlineKeyboardButton(text='Модель изображения', callback_data=f'task-imag-model-{task_name}')],
        [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
    ])

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT model_text, model_image FROM ModelAI WHERE id = 1")
    model_text, model_image = cursor.fetchone()
    connection.close()

    await call.message.edit_text("Текущие модели:\n"
                                 f"Текст - {model_text if model_text != '-' else 'модель по умолчанию'}\n"
                                 f"Изображение - {model_image if model_image != '-' else 'модель по умолчанию'}\n\n"
                                 "Выберите модель для редактирования:",
                                 reply_markup=keyboard)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-text-model-'), AdminFilter())
@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-imag-model-'), AdminFilter())
async def task_get_api_text_model_callback_query(call: CallbackQuery, state: FSMContext):
    """Ожидание модели текста и изображения для задания OpenAI"""

    task_name = call.data[16:]
    await call.message.edit_text("Отправьте название модели OpenAI в сообщении.", reply_markup=await back_to_task(task_name))
    await state.update_data(model_type=call.data, task_name=task_name)
    await state.set_state(ModelTask.message)

@router_tasks_panel.message(ModelTask.message, AdminFilter())
async def task_upload_model_handler(message: Message, state: FSMContext):
    model_data = await state.get_data()
    model_type = model_data['model_type']
    task_name = model_data['task_name']

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()

    if model_type.startswith('task-text-model-'):
        cursor.execute(
            "UPDATE ModelAI SET model_text = ? WHERE id = 1",
            (message.text, )
        )

        await message.answer(f"✅ Модель текста успешно изменена. (<b>{task_name}</b>)")

    else:
        cursor.execute(
            "UPDATE ModelAI SET model_image = ? WHERE id = 1",
            (message.text, )
        )

        await message.answer(f"✅ Модель изображения по умолчанию успешно изменена. (<b>{task_name}</b>)")

    connection.commit()
    connection.close()

    await task_panel_view(task_name=task_name, message=message, type_answer='answer')
    await state.set_state(None)
    await state.clear()

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-timeout-cycle-'), AdminFilter())
async def task_get_timeout_cycle_callback_query(call: CallbackQuery, state: FSMContext):
    """Изменение задержки цикла"""

    task_name = call.data[19:]

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT timeout_task_cycle FROM TasksSettings WHERE id = 1")
    timeout = cursor.fetchone()[0]
    connection.close()

    if timeout == '-':
        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT timeout_task_cycle FROM TasksSettings WHERE id = 1")
            timeout = cursor.fetchone()[0]

    await call.message.edit_text(f"Текущая задержка цикла (<b>{task_name}</b>):\n"
                                 f"{int(int(timeout) / 60)} мин.\n\n"
                                 "Отправьте новую задержку (кол-во минут, минимум 1) в сообщении.", reply_markup=await back_to_task(task_name))

    await state.update_data(task_name=task_name)
    await state.set_state(TaskTimeoutCycle.message)

@router_tasks_panel.message(TaskTimeoutCycle.message, AdminFilter())
async def task_upload_timeout_cycle_handler(message: Message, state: FSMContext):
    panel_data = await state.get_data()
    task_name = panel_data['task_name']

    new_timeout = message.text.strip()

    if not re.fullmatch(r'\d+', message.text.strip()):
        await message.answer("❌ Введите корректную задержку цикла.", reply_markup=await back_to_task(task_name))
        return

    if int(new_timeout) < 1:
        await message.answer("❌ Задержка цикла не может быть меньше одной минуты. Попробуйте снова", reply_markup=await back_to_task(task_name))
        return

    timeout_in_seconds = int(new_timeout) * 60

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("UPDATE TasksSettings SET timeout_task_cycle = ? WHERE id = 1", (str(timeout_in_seconds),))
    connection.commit()
    connection.close()

    await message.answer(f"✅ Задержка цикла успешно обновлена на {new_timeout} мин. (<b>{task_name}</b>)")
    await task_panel_view(task_name=task_name, message=message, type_answer='answer')
    await state.set_state(None)
    await state.clear()

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-timeout-publishing-'), AdminFilter())
async def task_get_timeout_publishing_callback_query(call: CallbackQuery, state: FSMContext):
    """Изменение задержки постинга"""

    task_name = call.data[24:]

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT timeout_posting_articles FROM TasksSettings WHERE id = 1")
    timeout = cursor.fetchone()[0]
    connection.close()

    if timeout == '-':
        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT timeout_posting_articles FROM TasksSettings WHERE id = 1")
            timeout = cursor.fetchone()[0]

    await call.message.edit_text(f"Текущая задержка публикации (<b>{task_name}</b>):\n"
                                 f"{int(int(timeout) / 60)} мин.\n\n"
                                 "Отправьте новую задержку (в минутах) в сообщении.")

    await state.update_data(task_name=task_name)
    await state.set_state(TaskTimeoutPost.message)

@router_tasks_panel.message(TaskTimeoutPost.message, AdminFilter())
async def task_upload_timeout_publishing_handler(message: Message, state: FSMContext):
    panel_data = await state.get_data()
    task_name = panel_data['task_name']

    new_timeout = message.text.strip()

    if not re.fullmatch(r'\d+', message.text.strip()):
        await message.answer("❌ Введите корректную задержку постинга.", reply_markup=await back_to_task(task_name))
        return

    if int(new_timeout) < 1:
        await message.answer("❌ Задержка постинга не может быть меньше одной минуты. Попробуйте снова", reply_markup=await back_to_task(task_name))
        return

    timeout_in_seconds = int(new_timeout) * 60

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("UPDATE TasksSettings SET timeout_posting_articles = ? WHERE id = 1", (str(timeout_in_seconds),))
    connection.commit()
    connection.close()

    await message.answer(f"✅ Задержка постинга статей успешно обновлена на {new_timeout} мин. (<b>{task_name}</b>)")
    await task_panel_view(task_name=task_name, message=message, type_answer='answer')
    await state.set_state(None)
    await state.clear()

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-count-words-'), AdminFilter())
async def task_get_count_key_callback_query(call: CallbackQuery, state: FSMContext):
    """Изменение количество загрузки ключевых фраз"""

    task_name = call.data[17:]

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT count_key_words FROM TasksSettings WHERE id = 1")
    count = cursor.fetchone()[0]
    connection.close()

    if count == '-':
        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT count_key_words FROM TasksSettings WHERE id = 1")
            count = cursor.fetchone()[0]

    await call.message.edit_text(f"Текущее количество загрузки ключевых фраз (<b>{task_name}</b>):\n"
                                 f"{count} шт.\n\n"
                                 "Отправьте новое количество загрузки фраз (минимум 1) в сообщении.", reply_markup=await back_to_task(task_name))

    await state.update_data(task_name=task_name)
    await state.set_state(TaskKeyWord.message)

@router_tasks_panel.message(TaskKeyWord.message, AdminFilter())
async def task_upload_count_key_handler(message: Message, state: FSMContext):
    panel_data = await state.get_data()
    task_name = panel_data['task_name']

    new_count = message.text.strip()

    if not re.fullmatch(r'\d+', message.text.strip()):
        await message.answer("❌ Введите корректное количество.", reply_markup=await back_to_task(task_name))
        return

    if int(new_count) < 1:
        await message.answer("❌ Минимальное количество - 1. Попробуйте снова", reply_markup=await back_to_task(task_name))
        return

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("UPDATE TasksSettings SET count_key_words = ? WHERE id = 1", (str(new_count),))
    connection.commit()
    connection.close()

    await message.answer(f"✅ Количество загружаемых фраз успешно обновлено на {new_count} шт. (<b>{task_name}</b>)")
    await task_panel_view(task_name=task_name, message=message, type_answer='answer')
    await state.set_state(None)
    await state.clear()

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-options-posting-'), AdminFilter())
async def task_get_options_callback_query(call: CallbackQuery):
    """Изменение настройки постинга"""
    task_name = call.data[21:]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Для основного режима', callback_data=f'task-option-main-{task_name}'),
         InlineKeyboardButton(text='Для постинга из БД', callback_data=f'task-option-db-{task_name}')],
        [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
    ])

    await call.message.edit_text(f"Выберите режим настройки (<b>{task_name}</b>):", reply_markup=keyboard)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-option-db-'), AdminFilter())
async def task_get_options_db_callback_query(call: CallbackQuery, state: FSMContext):
    task_name = call.data[15:]

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

    await call.message.edit_text(f"(<b>{task_name}</b>) Текущая настройка публикации из базы данных (для генерации пропусков и публикации статей из бд):\n"
                                 f"{'Публиковать сразу' if flag == 'True' else 'Добавлять в черновики'}\n\n"
                                 "Отправьте новую настройку в сообщении (True - публиковать сразу, "
                                 "False - добавлять в черновики).", reply_markup=await back_to_task(task_name))

    await state.update_data(task_name=task_name, type='db')
    await state.set_state(TaskFlagPost.message)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-option-main-'), AdminFilter())
async def task_get_options_main_callback_query(call: CallbackQuery, state: FSMContext):
    task_name = call.data[17:]

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT flag_posting_for_main FROM TasksSettings WHERE id = 1")
    flag = cursor.fetchone()[0]
    connection.close()

    if flag == '-':
        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT flag_posting_for_main FROM TasksSettings WHERE id = 1")
            flag = cursor.fetchone()[0]

    await call.message.edit_text(f"Текущая настройка публикации (<b>{task_name}</b>):\n"
                                 f"{'Публиковать сразу' if flag == 'True' else 'Добавлять в черновики'}\n\n"
                                 "Отправьте новую настройку в сообщении (True - публиковать сразу, "
                                 "False - добавлять в черновики).", reply_markup=await back_to_task(task_name))

    await state.update_data(task_name=task_name, type='main')
    await state.set_state(TaskFlagPost.message)

@router_tasks_panel.message(TaskFlagPost.message, AdminFilter())
async def task_upload_options_db_handler(message: Message, state: FSMContext):
    panel_data = await state.get_data()
    task_name = panel_data['task_name']
    type_posting = panel_data['type']

    new_flag = message.text.strip()

    if new_flag != 'True' and new_flag != 'False':
        await message.answer("❌ Некорректный ввод. Попробуйте снова", reply_markup=await back_to_task(task_name))
        return

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()

    if type_posting == 'db':
        cursor.execute("UPDATE TasksSettings SET flag_posting_db = ? WHERE id = 1", (new_flag,))
    else:
        cursor.execute("UPDATE TasksSettings SET flag_posting_for_main = ? WHERE id = 1", (new_flag,))
    connection.commit()
    connection.close()

    await message.answer(
        f"✅ (<b>{task_name}</b>) Настройка постинга {'из базы данных' if type_posting == 'db' 
        else 'для Основного режима'} обновлена: <b>{'Публиковать сразу' if new_flag == 'True' 
        else 'Добавлять в черновики'}</b>")

    await task_panel_view(task_name=task_name, message=message, type_answer='answer')
    await state.set_state(None)
    await state.clear()

@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-indexing-'), AdminFilter())
async def get_action_indexing_callback_query(call: CallbackQuery, state: FSMContext):
    """Ожидание настройки индексации задания"""

    task_name = call.data[14:]

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

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'{'✅ Индексация вкл.' if indexing == 'True' else '❌ Индексация выкл.'}', callback_data=f'indexing-trigger-{task_name}'),
         InlineKeyboardButton(text='Параметры индексации', callback_data=f'task-param-indexing-{task_name}')],
        [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
    ])

    await call.message.edit_text("Выберите действие:", reply_markup=keyboard)

@router_tasks_panel.callback_query(lambda call: call.data.startswith('indexing-trigger-'), AdminFilter())
async def task_indexing_trigger_callback_query(call: CallbackQuery, state: FSMContext):
    task_name = call.data[17:]

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT indexing FROM TasksSettings WHERE id = 1")
    indexing_task = cursor.fetchone()[0]
    connection.close()

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT indexing FROM TasksSettings WHERE id = 1")
        indexing_main = cursor.fetchone()[0]

    if indexing_task == '-':
        if indexing_main == 'True':
            indexing = 'False'
        else:
            indexing = 'True'
    else:
        if indexing_task == 'True':
            indexing = 'False'
        else:
            indexing = 'True'

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE TasksSettings SET indexing = ? WHERE id = 1",
        (indexing, )
    )
    connection.close()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'{'✅ Индексация вкл.' if indexing == 'True' else '❌ Индексация выкл.'}',
                              callback_data=f'indexing-trigger-{task_name}'),
         InlineKeyboardButton(text='Параметры индексации', callback_data=f'task-param-indexing-{task_name}')],
        [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
    ])

    await call.message.edit_text("Выберите действие:", reply_markup=keyboard)


@router_tasks_panel.callback_query(lambda call: call.data.startswith('task-param-indexing-'), AdminFilter())
async def get_task_indexing_callback_query(call: CallbackQuery, state: FSMContext):
    """Ожидание настройки индексации задания"""

    task_name = call.data[20:]

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT api_key, searchengine, se_type FROM TasksSettings WHERE id = 1")
    api_key, searchengine, se_type = cursor.fetchone()
    connection.close()

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()

        if api_key == '-':
            cursor.execute("SELECT api_key FROM TasksSettings WHERE id = 1")
            api_key = cursor.fetchone()[0]

        if searchengine == '-':
            cursor.execute("SELECT searchengine FROM TasksSettings WHERE id = 1")
            searchengine = cursor.fetchone()[0]

        if se_type == '-':
            cursor.execute("SELECT se_type FROM TasksSettings WHERE id = 1")
            se_type = cursor.fetchone()[0]

    await call.message.edit_text(f"<b>Текущие параметры индексации (<b>{task_name}</b>)</b>:\n"
                                 f"API-ключ: {api_key}\n"
                                 f"Поисковик: {searchengine}\n"
                                 f"Способ индексации: {se_type}\n\n"
                                 "Отправьте настройки индексации.\n"
                                 "Поисковик - google/yandex/google+yandex\n"
                                 "Способ индексации - normal/hard\n\n"
                                 "<b>Формат отправки:</b>\n"
                                 "api-key\n"
                                 "поисковик\n"
                                 "способ индексации\n\n"
                                 "<b>Примечание:</b> каждый параметр с новой строки", reply_markup=await back_to_task(task_name))

    await state.update_data(task_name=task_name)
    await state.set_state(TaskIndexing.message)

@router_tasks_panel.message(TaskIndexing.message, AdminFilter())
async def upload_task_indexing_param_handler(message: Message, state: FSMContext):
    """Загрузка настроек индексации задания"""

    panel_data = await state.get_data()
    task_name = panel_data['task_name']

    try:
        api_key, searchengine, se_type = message.text.strip().split('\n')
    except:
        await message.answer("❌ Пожалуйста, введите параметры в корректном формате.", reply_markup=await back_to_task(task_name))
        return

    if searchengine != 'google' and searchengine != 'yandex' and searchengine != 'google+yandex':
        await message.answer("❌ Пожалуйста, введите корректный поисковик.", reply_markup=await back_to_task(task_name))
        return

    if se_type != 'hard' and se_type != 'normal':
        await message.answer("❌ Пожалуйста, введите корректный способ индексации.", reply_markup=await back_to_task(task_name))
        return

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE TasksSettings SET api_key = ?, searchengine = ?, se_type = ? WHERE id = 1",
            (api_key, searchengine, se_type)
        )
        connection.commit()

    await message.answer(f"✅ Настройки индексации успешно обновлены (<b>{task_name}</b>)")
    await task_panel_view(task_name=task_name, message=message, type_answer='answer')
    await state.set_state(None)
    await state.clear()