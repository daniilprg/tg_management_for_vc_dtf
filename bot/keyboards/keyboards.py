import sqlite3

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import DB_TASK_DIRECTORY, TIMEOUT_DELAY, DB_DIRECTORY, DB_MAIN_ACCOUNTS_DIRECTORY, \
    DB_MULTI_ACCOUNTS_DIRECTORY, DB_PATTERNS_DIRECTORY, DB_LINKS_DIRECTORY, DB_IMAGES_DIRECTORY


async def get_count(db_path: str, table_name: str) -> int:
    """Подсчёт количества данных в таблице"""

    with sqlite3.connect(db_path, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]

async def create_keyboard(buttons) -> InlineKeyboardMarkup:
    """Создание многострочной клавиатуры"""
    inline_keyboard = []

    for row in buttons:
        inline_keyboard.append([InlineKeyboardButton(text=text, callback_data=data) for text, data in row])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

async def tasks_list() -> InlineKeyboardMarkup:
    """Список заданий"""

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT task_name FROM Tasks")
        tasks = cursor.fetchall()

    buttons = [[(task[0], f'self-task-{task[0]}')] for task in tasks]

    buttons += [
        [('📝 Создать задание', 'task-create')],
        [('📃 Шаблоны', 'patterns-list'), ('🔐 Аккаунты', 'accounts-type')],
        [('🔗 Ссылки', 'links-list'), ('🖼 Изображения', 'images-list')],
        [('📖 Постинг из БД', 'posting-articles-db'), ('🖥 Постинг с сервера', 'posting-articles-server')],
        [('♻️ Редактор статей', 'articles-editor'), ('❔ Тест промта', 'test-prompt')],
        [('Настройки по умолчанию:', 'none')],
        [('🗝 API-ключ', 'openai-key'), ('📺 Настройки подключения', 'options-connected-server')],
        [('🤖 Модели', 'openai-models'), ('🖼 Промт изображений', 'prompt-image')],
        [('⏳ Таймаут цикла', 'timeout-cycle'), ('⏳ Таймаут публикации', 'timeout-publishing')],
        [('⚙️ Настройка постинга', 'options-posting'), ('🧮 Количество фраз', 'count-words')],
        [('⛓️ URLs', 'xlsx-urls'), ('🔍 Индексация', 'options-links-indexing')],
        [('🔀 Автоперелинковка', 'options-auto-links')],
    ]

    return await create_keyboard(buttons)

async def patterns_list() -> InlineKeyboardMarkup:
    """Список шаблонов"""

    with sqlite3.connect(DB_PATTERNS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT id, pattern_name, pattern FROM Patterns")
        patterns = cursor.fetchall()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for pattern_id, pattern_name, pattern in patterns:
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=pattern_name, callback_data=f'self-pattern-{pattern_id}')])

        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text='📝 Добавить шаблон', callback_data=f'create-pattern')])
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text='📦 Массовая загрузка', callback_data='all-create-patterns')])

        if patterns:
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text='🗃 Выгрузка шаблонов', callback_data='download-patterns')])

        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="⬅️ Назад к заданиям", callback_data=f'back-to-tasks')])

    return keyboard

async def images_list() -> InlineKeyboardMarkup:
    """Список изображений"""

    with sqlite3.connect(DB_IMAGES_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT id, image_name, image_path FROM Images")
        images = cursor.fetchall()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for image_id, image_name, image_path in images:
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=image_name, callback_data=f'self-image-{image_id}')])

        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text='📝 Добавить изображения', callback_data=f'create-images')])

        if images:
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text='🗃 Выгрузка изображений', callback_data='download-images')])

        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="⬅️ Назад к заданиям", callback_data=f'back-to-tasks')])

    return keyboard

async def links_list() -> InlineKeyboardMarkup:
    """Список ссылок"""

    with sqlite3.connect(DB_LINKS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT link_name, id FROM Links")
        links = cursor.fetchall()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for link_name, link_id in links:
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=link_name, callback_data=f'self-links-{link_id}')]
            )

        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text='📝 Добавить ссылку', callback_data='create-link')])
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text='📦 Массовая загрузка', callback_data='all-create-links')])

        if links:
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text='🗃 Выгрузка ссылок', callback_data='download-links')])

        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="⬅️ Назад к заданиям", callback_data='back-to-tasks')])

    return keyboard

async def task_prompts(task_name: str) -> tuple:
    """Промты задания"""

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM Prompts")
    prompts_count = cursor.fetchone()[0]
    connection.close()

    with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT priority_prompts, theme_count FROM Tasks WHERE task_name = ?", (task_name,))
        priority_prompts, theme_count = cursor.fetchone()

    if prompts_count == 0:
        text = f"Промтов не обнаружено."
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Загрузка ключей", callback_data=f'upload-xlsx-{task_name}')],
            [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
        ])
    else:
        text = (f"<b>Распознано тем:</b> {theme_count}\n"
                f"<b>Сгенерировано промтов:</b> {prompts_count}\n"
                f"<b>Диапазон приоритетных промтов:</b> {priority_prompts}")

        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🆙 Установить приоритет", callback_data=f'priority-prompts-{task_name}')],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f'prompts-edit-{task_name}')],
            [InlineKeyboardButton(text="📦 Массовое редактирование", callback_data=f'all-prompts-edit-{task_name}')],
            [InlineKeyboardButton(text="🗃 Выгрузка промтов", callback_data=f'download-prompts-{task_name}')],
            [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
        ])
    return text, buttons

async def task_articles(task_name: str) -> tuple:
    """Готовые статьи задания"""

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM Articles")
    articles_count = cursor.fetchone()[0]
    connection.close()

    if articles_count == 0:
        text = f"Статей не обнаружено."
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
        ])
    else:
        text = f"<b>Количество готовых статей:</b> {articles_count}\n"

        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f'articles-edit-{task_name}')],
            [InlineKeyboardButton(text="🗃 Выгрузка статей", callback_data=f'download-articles-{task_name}')],
            [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data=f'self-task-{task_name}')]
        ])

    return text, buttons

async def task_panel_keyboard(task_name: str, task_type: str, action: InlineKeyboardButton) -> InlineKeyboardMarkup:
    """Клавиатура панели задания"""

    if task_type == 'Основной':
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✉️ Промты', callback_data=f'prompts-list-{task_name}'),
             InlineKeyboardButton(text='📔 Статьи', callback_data=f'articles-list-{task_name}')],
            [InlineKeyboardButton(text='🗄 Постинг', callback_data=f'posting-many-func-{task_name}'),
             InlineKeyboardButton(text='🗂 Выгрузка лога', callback_data=f'log-{task_name}')],
            [action, InlineKeyboardButton(text='🔄 Обновить статус', callback_data=f'update-status-{task_name}')],
            [InlineKeyboardButton(text='Настройки до запуска:', callback_data='none')],
            [InlineKeyboardButton(text='🤖 Модели задания', callback_data=f'task-models-{task_name}'),
             InlineKeyboardButton(text='🔍 Индексация', callback_data=f'task-indexing-{task_name}')],
            [InlineKeyboardButton(text='⏳ Таймаут цикла', callback_data=f'task-timeout-cycle-{task_name}'),
             InlineKeyboardButton(text='⏳ Таймаут публикации', callback_data=f'task-timeout-publishing-{task_name}')],
            [InlineKeyboardButton(text='⚙️ Настройка постинга', callback_data=f'task-options-posting-{task_name}'),
            InlineKeyboardButton(text='🧮 Количество фраз', callback_data=f'task-count-words-{task_name}')],
            [InlineKeyboardButton(text='⬅️ Назад к заданиям', callback_data=f'back-to-tasks'),
             InlineKeyboardButton(text='🗑', callback_data=f'task-delete-{task_name}')],
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✉️ Промты', callback_data=f'prompts-list-{task_name}'),
             InlineKeyboardButton(text='📔 Статьи', callback_data=f'articles-list-{task_name}')],
            [InlineKeyboardButton(text='🗂 Выгрузка лога', callback_data=f'log-{task_name}')],
            [action, InlineKeyboardButton(text='🔄 Обновить статус', callback_data=f'update-status-{task_name}')],
            [InlineKeyboardButton(text='Настройки до запуска:', callback_data='none')],
            [InlineKeyboardButton(text='🧮 Количество постов', callback_data=f'count-posts-{task_name}'),
             InlineKeyboardButton(text='⏳ Задержка', callback_data=f'delay-{task_name}')],
            [InlineKeyboardButton(text='🤖 Модели задания', callback_data=f'task-models-{task_name}')],
            [InlineKeyboardButton(text='🔍 Индексация', callback_data=f'task-indexing-{task_name}'),
             InlineKeyboardButton(text='🧮 Количество фраз', callback_data=f'task-count-words-{task_name}')],
            [InlineKeyboardButton(text='⬅️ Назад к заданиям', callback_data=f'back-to-tasks'),
             InlineKeyboardButton(text='🗑', callback_data=f'task-delete-{task_name}')],
        ])

    return keyboard

async def get_accounts(task_type: str) -> tuple:
    """Аккаунты определённого режима"""

    db_path = DB_MAIN_ACCOUNTS_DIRECTORY if task_type == 'Основной' else DB_MULTI_ACCOUNTS_DIRECTORY
    accounts_count = await get_count(db_path, "Accounts")

    if accounts_count == 0:
        return (
            "Аккаунтов не обнаружено.",
            await create_keyboard([
                [("📋 Добавить", f'add-accounts-{task_type}')],
                [("⬅️ Назад к заданиям", 'back-to-tasks')]
            ])
        )

    keyboard_buttons = [
        [("📋 Добавить", f'add-accounts-{task_type}'), ("🗑 Удалить", f'accounts-del-{task_type}')],
        [("🗃 Выгрузка аккаунтов", f'download-accounts-{task_type}')],
        [("⬅️ Назад к заданиям", 'back-to-tasks')]
    ]

    if task_type == 'Основной':
        keyboard_buttons.insert(2, [("✏️ Редактировать", f'edit-accounts-{task_type}')])

    return f"<b>Количество загруженных аккаунтов:</b> {accounts_count}", await create_keyboard(keyboard_buttons)

def get_accounts_from_db():
    """Получение списка основных аккаунтов"""

    with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT id, account_url, account_login FROM Accounts")

        return cursor.fetchall()

def generate_pagination_keyboard(accounts, page: int, type_selected: str):
    """Пагинация список основных аккаунтов"""

    ITEMS_PER_PAGE = 10

    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    buttons = [
        [InlineKeyboardButton(text=f"{"vc" if "vc" in platform.lower() else "dtf"}-{login}", callback_data=f"{type_selected}:{idx}")]
        for idx, (_, platform, login) in enumerate(accounts[start_idx:end_idx], start=start_idx)
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"page:{page - 1}"))
    if end_idx < len(accounts):
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"page:{page + 1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons)
