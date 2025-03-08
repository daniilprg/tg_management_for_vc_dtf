import os
import sqlite3
import uuid
import zipfile
import shutil
from html import escape

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from bot.config import TIMEOUT_DELAY, DB_IMAGES_DIRECTORY
from bot.handlers.commands.admins_filter import AdminFilter
from bot.handlers.routers.control_panel import BACK_TO_TASKS
from bot.keyboards.keyboards import images_list

router_tasks_images = Router(name=__name__)

class ImageMessage(StatesGroup):
    message = State()
    create = State()

class ImageNameEdit(StatesGroup):
    message = State()

class ImageSourceEdit(StatesGroup):
    message = State()

IMAGES_BASE_PATH = 'bot/assets/images/'

@router_tasks_images.callback_query(lambda call: call.data.startswith('images-list'), AdminFilter())
async def task_images_callback_query(call: CallbackQuery):
    keyboard = await images_list()
    await call.message.edit_text(escape('Текущий текст для переменной %IMAGES%:\n\n'
                                 'В соответствующем названию подзаголовке добавь <div type="image">Name</div>, '
                                 'где Name соответствует названию продукта. Названия картинок:\n'
                                 '...\n\n'
                                 'Выберите папку изображений или добавьте новую:'), reply_markup=keyboard)

@router_tasks_images.callback_query(lambda call: call.data.startswith('self-image-'), AdminFilter())
async def self_image_callback_query(call: CallbackQuery):
    image_id = call.data[11:]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✏️ Редактировать название', callback_data=f'imag-name-edit-{image_id}')],
        [InlineKeyboardButton(text='✏️ Редактировать содержимое', callback_data=f'imag-source-edit-{image_id}')],
        [InlineKeyboardButton(text='🗑 Удалить изображения', callback_data=f'image-delete-{image_id}')],
        [InlineKeyboardButton(text='🗃 Выгрузка изображений', callback_data=f'image-download-{image_id}')],
        [InlineKeyboardButton(text='⬅️ Назад к изображениям', callback_data=f'images-list')]
    ])

    with sqlite3.connect(DB_IMAGES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT image_name FROM Images WHERE id = ?", (image_id,))
        image_name = cursor.fetchone()[0]

    await call.message.edit_text(f"📃 Папка изображений (<b>{image_name}</b>):", reply_markup=keyboard)

@router_tasks_images.callback_query(lambda call: call.data.startswith('image-download-'), AdminFilter())
async def image_download_callback_query(call: CallbackQuery):
    image_id = call.data[15:]

    ZIP_PATH = f'bot/assets/{uuid.uuid4()}.zip'

    with sqlite3.connect(DB_IMAGES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT image_path FROM Images WHERE id = ?", (image_id,))
        image_files = []

        for row in cursor.fetchall():
            image_files.extend(row[0].split("\n"))

    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in image_files:
            if os.path.exists(file_path):
                arcname = os.path.basename(file_path)
                zipf.write(file_path, arcname)

    await call.message.answer_document(FSInputFile(ZIP_PATH))
    os.remove(ZIP_PATH)

    keyboard = await images_list()
    await call.message.answer("Выберите папку изображений или добавьте новую:", reply_markup=keyboard)

@router_tasks_images.callback_query(lambda call: call.data.startswith('image-delete-'), AdminFilter())
async def image_delete_callback_query(call: CallbackQuery):
    image_id = call.data[13:]

    with sqlite3.connect(DB_IMAGES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT image_path FROM Images WHERE id = ?", (image_id,))
        folder_path = cursor.fetchone()[0]

    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path)

    cursor.execute("DELETE FROM Images WHERE id = ?", (image_id,))
    connection.commit()

    keyboard = await images_list()
    await call.message.edit_text("Выберите папку изображений или добавьте новую:", reply_markup=keyboard)


@router_tasks_images.callback_query(lambda call: call.data.startswith('create-images'), AdminFilter())
async def create_image_name_callback_query(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("💬 Отправьте название папки изображений в сообщении.", reply_markup=BACK_TO_TASKS)
    await state.set_state(ImageMessage.message)

@router_tasks_images.message(ImageMessage.message, AdminFilter())
async def create_image_name_handler(message: Message, state: FSMContext):
    image_name = message.text
    await message.answer('💬 Отправьте архив в формате .zip с изображениями.\n\n'
                                'Правильный формат структуры архива (Без дополнительных вложений по типу папок):\n\n'
                                '<pre>────Архив.zip\n'
                                '    ├───Изображение1.png\n'
                                '    ├───Изображение2.jpg\n'
                                '    └───Изображение3.jpeg</pre>', reply_markup=BACK_TO_TASKS
                        )
    await state.update_data(image_name=image_name)
    await state.set_state(ImageMessage.create)

@router_tasks_images.message(ImageMessage.create, AdminFilter())
async def create_image_handler(message: Message, state: FSMContext):
    image_data = await state.get_data()
    image_name = image_data.get('image_name')

    document = message.document
    zip_path = os.path.join(IMAGES_BASE_PATH, f"{uuid.uuid4()}.zip")
    await message.bot.download(document, zip_path)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(IMAGES_BASE_PATH)
            extracted_files = [os.path.join(IMAGES_BASE_PATH, file) for file in zip_ref.namelist()]
        os.remove(zip_path)

    except zipfile.BadZipFile:
        await message.answer("❌ Ошибка! Файл поврежден или не является ZIP-архивом. Попробуйте снова.", reply_markup=BACK_TO_TASKS)
        os.remove(zip_path)
        return

    image_paths_str = '\n'.join(extracted_files)

    with sqlite3.connect(DB_IMAGES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO Images (image_name, image_path) VALUES (?, ?)", (image_name, image_paths_str))
        connection.commit()

    await message.answer("✅ Архив изображений успешно загружен!")

    keyboard = await images_list()
    await message.answer("Выберите папку изображений или добавьте новую:", reply_markup=keyboard)
    await state.set_state(None)
    await state.clear()


@router_tasks_images.callback_query(lambda call: call.data.startswith('imag-name-edit-'), AdminFilter())
async def edit_image_name_callback_query(call: CallbackQuery, state: FSMContext):
    image_id = call.data[15:]
    await call.message.edit_text("💬 Отправьте новое название папки изображений в сообщении", reply_markup=BACK_TO_TASKS)
    await state.update_data(image_id=image_id)
    await state.set_state(ImageNameEdit.message)

@router_tasks_images.message(ImageNameEdit.message, AdminFilter())
async def edit_image_name_handler(message: Message, state: FSMContext):
    image_data = await state.get_data()
    image_id = image_data.get('image_id')

    with sqlite3.connect(DB_IMAGES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE Images SET image_name = ? WHERE id = ?", (message.text, image_id)
        )
        connection.commit()

    keyboard = await images_list()
    await message.answer('✅ Название папки изображений успешно изменено!')
    await message.answer("Выберите папку изображений или добавьте новую:", reply_markup=keyboard)
    await state.set_state(None)
    await state.clear()

@router_tasks_images.callback_query(lambda call: call.data.startswith('imag-source-edit-'), AdminFilter())
async def edit_image_source_callback_query(call: CallbackQuery, state: FSMContext):
    image_id = call.data[17:]
    await call.message.edit_text("💬 Отправьте новый zip-архив с изображениями.", reply_markup=BACK_TO_TASKS)
    await state.update_data(image_id=image_id)
    await state.set_state(ImageSourceEdit.message)

@router_tasks_images.message(ImageSourceEdit.message, AdminFilter())
async def edit_image_source_handler(message: Message, state: FSMContext):
    image_data = await state.get_data()
    image_id = image_data.get('image_id')

    document = message.document

    with sqlite3.connect(DB_IMAGES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT image_path FROM Images WHERE id = ?", (image_id,))
        old_files = cursor.fetchone()[0].split("\n")

    for file_path in old_files:
        if os.path.exists(file_path):
            os.remove(file_path)

    zip_path = os.path.join(IMAGES_BASE_PATH, f"{uuid.uuid4()}.zip")
    await message.bot.download(document, zip_path)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(IMAGES_BASE_PATH)
            new_files = [os.path.join(IMAGES_BASE_PATH, f) for f in zip_ref.namelist()]
        os.remove(zip_path)

    except zipfile.BadZipFile:
        await message.answer("❌ Ошибка! Файл поврежден или не является ZIP-архивом. Попробуйте снова.", reply_markup=BACK_TO_TASKS)
        os.remove(zip_path)
        return

    new_image_paths = '\n'.join(new_files)

    with sqlite3.connect(DB_IMAGES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("UPDATE Images SET image_path = ? WHERE id = ?", (new_image_paths, image_id))
        connection.commit()

    keyboard = await images_list()
    await message.answer('✅ Содержимое папки изображений успешно изменено!')
    await message.answer("Выберите папку изображений или добавьте новую:", reply_markup=keyboard)
    await state.set_state(None)
    await state.clear()

@router_tasks_images.callback_query(lambda call: call.data.startswith('download-images'), AdminFilter())
async def images_download_callback_query(call: CallbackQuery):
    ZIP_PATH = f'bot/assets/{uuid.uuid4()}.zip'

    with sqlite3.connect(DB_IMAGES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT image_path FROM Images")
        image_files = []

        for row in cursor.fetchall():
            image_files.extend(row[0].split("\n"))

    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in image_files:
            if os.path.exists(file_path):
                arcname = os.path.basename(file_path)
                zipf.write(file_path, arcname)

    await call.message.answer_document(FSInputFile(ZIP_PATH))
    os.remove(ZIP_PATH)

    keyboard = await images_list()
    await call.message.answer("Выберите папку изображений или добавьте новую:", reply_markup=keyboard)