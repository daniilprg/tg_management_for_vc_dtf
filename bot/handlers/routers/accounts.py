import os
import re
import sqlite3

import openpyxl
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, Message

from bot.config import TIMEOUT_DELAY, DB_MAIN_ACCOUNTS_DIRECTORY, DB_MULTI_ACCOUNTS_DIRECTORY
from bot.handlers.commands.admins_filter import AdminFilter
from bot.handlers.commands.commands_manager import CommandsManager
from bot.handlers.routers.control_panel import BACK_TO_TASKS
from bot.keyboards.keyboards import get_accounts

router_tasks_account = Router(name=__name__)

class AccountsMessage(StatesGroup):
    upload_accounts = State()

class AccountsDelete(StatesGroup):
    delete_accounts = State()

class AccountsEdit(StatesGroup):
    data_accounts = State()
    edit_accounts = State()

@router_tasks_account.callback_query(lambda call: call.data.startswith('accounts-type'), AdminFilter())
async def accounts_type_callback_query(call: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Основной', callback_data=f'accounts-list-Основной')],
        [InlineKeyboardButton(text='Мультиаккаунты', callback_data=f'accounts-list-Мультиаккаунты')],
        [InlineKeyboardButton(text='⬅️ Назад к заданиям', callback_data=f'back-to-tasks')]
    ])
    await call.message.edit_text("Выберите тип аккаунтов:", reply_markup=keyboard)

@router_tasks_account.callback_query(lambda call: call.data.startswith('accounts-list-'), AdminFilter())
async def task_accounts_callback_query(call: CallbackQuery):
    task_type = call.data[14:]
    text, keyboard = await get_accounts(task_type=task_type)
    await call.message.edit_text(text, reply_markup=keyboard)

@router_tasks_account.callback_query(lambda call: call.data.startswith('accounts-del-'), AdminFilter())
async def del_accounts_callback_query(call: CallbackQuery, state: FSMContext):
    task_type = call.data[13:]
    await call.message.edit_text('Отправьте ID аккаунтов через запятую или пробел.', reply_markup=BACK_TO_TASKS)
    await state.update_data(task_type=task_type)
    await state.set_state(AccountsDelete.delete_accounts)

@router_tasks_account.callback_query(lambda call: call.data.startswith('edit-accounts-'), AdminFilter())
async def edit_accounts_callback_query(call: CallbackQuery, state: FSMContext):
    task_type = call.data[14:]
    await call.message.edit_text('Отправьте ID аккаунта для редактирования данных.', reply_markup=BACK_TO_TASKS)
    await state.update_data(task_type=task_type)
    await state.set_state(AccountsEdit.data_accounts)

@router_tasks_account.message(AccountsEdit.data_accounts, AdminFilter())
async def data_accounts_handler(message: Message, state: FSMContext):
    accounts_data = await state.get_data()
    task_type = accounts_data.get('task_type')

    with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY if task_type == 'Основной'\
                         else DB_MULTI_ACCOUNTS_DIRECTORY) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT account_email, account_password, account_login, 
                   proxy_ip, proxy_port, proxy_login, 
                   proxy_password, account_url
            FROM Accounts
            WHERE id = ?
            """,
            (int(message.text),)
        )
        account_data = cursor.fetchone()

    if not account_data:
        await message.answer("❌ Аккаунт с указанным ID не найден. Попробуйте снова.", reply_markup=BACK_TO_TASKS)
        return

    if not message.text.isdigit():
        await message.answer("❌ ID должен быть числом. Попробуйте снова.", reply_markup=BACK_TO_TASKS)
        return

    await message.answer("Отправьте новые данные аккаунта в формате:\n"
                         "E-mail, Пароль, Логин, IP, Порт, Логин прокси, Пароль прокси, URL-площадки\n\n"
                         "Если поле не нужно изменять, поставьте прочерк (-).\n\n"
                         "Пример:\n"
                         "qwerty@bk.ru, qwerty123, qwerty, 94.123.43.56, 5555, -, -, -\n\n"
                         f"Текущие данные аккаунта:\n{", ".join(map(str, account_data))}", reply_markup=BACK_TO_TASKS)
    await state.update_data(task_type=task_type, account_id=int(message.text))
    await state.set_state(AccountsEdit.edit_accounts)

@router_tasks_account.message(AccountsEdit.edit_accounts, AdminFilter())
async def edit_accounts_handler(message: Message, state: FSMContext):
    accounts_data = await state.get_data()
    task_type = accounts_data.get('task_type')
    account_id = accounts_data.get('account_id')
    new_account_data = message.text.split(', ')

    if len(new_account_data) != 8:
        await message.answer("❌ Введено неправильное количество данных. Попробуйте снова.", reply_markup=BACK_TO_TASKS)
        return

    update_columns = ["account_email", "account_password", "account_login",
                      "proxy_ip", "proxy_port", "proxy_login",
                      "proxy_password", "account_url"]

    updated_data = []
    for field, new_value in zip(update_columns, new_account_data):
        if new_value != '-':
            updated_data.append((new_value, field))

    if updated_data:
        with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY if task_type == 'Основной'
                             else DB_MULTI_ACCOUNTS_DIRECTORY) as connection:
            cursor = connection.cursor()
            for new_value, field in updated_data:
                cursor.execute(
                    f"""
                    UPDATE Accounts
                    SET {field} = ?
                    WHERE id = ?
                    """,
                    (new_value, account_id)
                )
            cursor.execute(
                f"""
                UPDATE Accounts
                SET accessToken = ?
                WHERE id = ?
                """,
                ('-', account_id)
            )
            connection.commit()

        await message.answer("✅ Данные аккаунта успешно обновлены!")
    else:
        await message.answer("❌ Не было указано ни одного значения для обновления.")

    text, keyboard = await get_accounts(task_type=task_type)
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(None)
    await state.clear()

@router_tasks_account.message(AccountsDelete.delete_accounts, AdminFilter())
async def del_accounts_handler(message: Message, state: FSMContext):
    accounts_data = await state.get_data()
    task_type = accounts_data.get('task_type')
    raw_text = message.text
    ids = re.findall(r'\b\d+\b', raw_text)
    ids = list(map(int, ids))
    if not ids:
        await message.answer("❌ Пожалуйста, отправьте корректный список ID аккаунтов (только числа).", reply_markup=BACK_TO_TASKS)
        return
    success, result = await CommandsManager.delete_accounts_by_ids(ids, task_type)
    if success:
        await message.answer(f"✅ Успешно удалены аккаунты с ID: {', '.join(map(str, result))}.")
    else:
        missing_ids = ', '.join(map(str, result))
        await message.answer(f"❌ Не удалось найти аккаунты с ID: {missing_ids}.")

    text, keyboard = await get_accounts(task_type=task_type)
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(None)
    await state.clear()

@router_tasks_account.callback_query(lambda call: call.data.startswith('add-accounts-'), AdminFilter())
async def add_accounts_callback_query(call: CallbackQuery, state: FSMContext):
    task_type = call.data[13:]
    await call.message.edit_text('Отправьте xlsx-файл со списком аккаунтов, прокси и ссылками на площадки.', reply_markup=BACK_TO_TASKS)
    await state.update_data(task_type=task_type)
    await state.set_state(AccountsMessage.upload_accounts)

@router_tasks_account.message(AccountsMessage.upload_accounts, AdminFilter())
async def upload_xlsx_handler(message: Message, state: FSMContext):
    accounts_data = await state.get_data()
    task_type = accounts_data.get('task_type')
    document = message.document

    if not document.file_name.endswith('.xlsx'):
        await message.answer("❌ Пожалуйста, отправьте файл в формате xlsx.", reply_markup=BACK_TO_TASKS)
        return

    file_path = os.path.join('bot/assets/xlsx', f'accounts_{task_type}.xlsx')
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    bot = message.bot

    await bot.download(document.file_id, destination=file_path)
    await CommandsManager.save_accounts_to_db(file_path=file_path, task_type=task_type)
    await message.answer(f"✅ Аккаунты сохранены (<b>{task_type}</b>).")

    text, keyboard = await get_accounts(task_type=task_type)
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(None)
    await state.clear()

@router_tasks_account.callback_query(lambda call: call.data.startswith('download-accounts-'), AdminFilter())
async def download_accounts_callback_query(call: CallbackQuery):
    task_type = call.data[18:]
    if task_type == 'Основной':
        with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM Accounts")
            articles_data = cursor.fetchall()
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = f"Accounts_{task_type}"
            ws.append(["ID", "Email", "Password", "Login", "Proxy_Ip", "Proxy_Port", "Proxy_Login", "Proxy_Password", "accessToken", "Account_Url"])
            for row in articles_data:
                ws.append(row)
            file_path = f"bot/assets/xlsx/accounts_{task_type}.xlsx"
            wb.save(file_path)
    else:
        with sqlite3.connect(DB_MULTI_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM Accounts")
            articles_data = cursor.fetchall()
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = f"Accounts_{task_type}"
            ws.append(["ID", "Email", "Password", "Login", "Proxy_Ip", "Proxy_Port", "Proxy_Login", "Proxy_Password", "accessToken", "Account_Url", "Account_Status"])
            for row in articles_data:
                ws.append(row)
            file_path = f"bot/assets/xlsx/accounts_{task_type}.xlsx"
            wb.save(file_path)

    await call.message.answer_document(FSInputFile(file_path), caption="Конвертированная таблица базы данных в xlsx-файл.")
    os.remove(file_path)
    text, keyboard = await get_accounts(task_type=task_type)
    await call.message.answer(text, reply_markup=keyboard)