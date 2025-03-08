import os
import re
import sqlite3
import uuid

import openpyxl
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.config import TIMEOUT_DELAY, DB_TASK_DIRECTORY, DB_DIRECTORY
from bot.handlers.commands.admins_filter import AdminFilter
from bot.handlers.routers.control_panel import BACK_TO_TASKS
from bot.keyboards.keyboards import task_articles

router_tasks_articles = Router(name=__name__)

class ArticlesEdit(StatesGroup):
    message = State()
    txt = State()

@router_tasks_articles.callback_query(lambda call: call.data.startswith('articles-list-'), AdminFilter())
async def task_articles_callback_query(call: CallbackQuery):
    task_name = call.data[14:]
    text, keyboard = await task_articles(task_name)
    await call.message.edit_text(text, reply_markup=keyboard)

@router_tasks_articles.callback_query(lambda call: call.data.startswith('download-articles-'), AdminFilter())
async def download_articles_callback_query(call: CallbackQuery):
    task_name = call.data[18:]

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT task_type FROM Tasks WHERE task_name = ?", (task_name,))
        task_type = cursor.fetchone()[0]

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    if task_type == 'Основной':
        cursor.execute("SELECT id, article_text, article_image, marks, status FROM Articles")
    else:
        cursor.execute("SELECT id, article_text, article_image, account_login, marks, status, article_url FROM Articles")
    articles_data = cursor.fetchall()
    connection.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Articles_{task_name}"

    if task_type == 'Основной':
        ws.append(["ID", "Text", "Image", "Marks", "Status"])
    else:
        ws.append(["ID", "Text", "Image", "Login", "Marks", "Status", "Url"])

    for row in articles_data:
        ws.append(row)
    file_path = f"bot/assets/xlsx/articles_{task_name}.xlsx"
    wb.save(file_path)
    await call.message.answer_document(FSInputFile(file_path), caption="Конвертированная таблица базы данных в xlsx-файл.")
    os.remove(file_path)
    text, keyboard = await task_articles(task_name)
    await call.message.answer(text, reply_markup=keyboard)


@router_tasks_articles.callback_query(lambda call: call.data.startswith('articles-edit-'), AdminFilter())
async def edit_articles_callback_query(call: CallbackQuery, state: FSMContext):
    task_name = call.data[14:]
    await call.message.edit_text("Отправьте существующий ID статьи в сообщении.", reply_markup=BACK_TO_TASKS)
    await state.update_data(task_name=task_name)
    await state.set_state(ArticlesEdit.message)

@router_tasks_articles.message(ArticlesEdit.message, AdminFilter())
async def get_id_edit_articles_handler(message: Message, state: FSMContext):
    articles_data = await state.get_data()
    task_name = articles_data['task_name']

    if not re.fullmatch(r'\d+', message.text.strip()):
        await message.answer("❌ Укажите корректный ID, состоящий только из цифр.", reply_markup=BACK_TO_TASKS)
        return

    article_id = int(message.text.strip())

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM Articles WHERE id = ?", (article_id,))
    result = cursor.fetchone()
    connection.close()

    if not result:
        await message.answer("❌ Статья с указанным ID не найдена. Убедитесь, что ID указан верно.", reply_markup=BACK_TO_TASKS)
        return

    await message.answer("Отправьте txt-файл с изменённым текстом статьи.")
    await state.update_data(task_name=task_name, article_id=article_id)
    await state.set_state(ArticlesEdit.txt)

@router_tasks_articles.message(ArticlesEdit.txt, AdminFilter())
async def edit_articles_handler(message: Message, state: FSMContext):

    if not message.document or not message.document.file_name.endswith('.txt'):
        await message.answer("❌ Пожалуйста, отправьте txt-файл.", reply_markup=BACK_TO_TASKS)
        return

    articles_data = await state.get_data()
    task_name = articles_data['task_name']
    article_id = articles_data['article_id']

    file_path = f"bot/assets/txt/{uuid.uuid4()}.txt"
    bot = message.bot
    await bot.download(message.document.file_id, destination=file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        new_article_text = f.read()
    os.remove(file_path)

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE Articles SET article_text = ? WHERE id = ?",
        (new_article_text, article_id)
    )
    connection.commit()
    connection.close()

    await message.answer("✅ Текст статьи успешно обновлён!")

    text, keyboard = await task_articles(task_name)
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(None)
    await state.clear()
