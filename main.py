from bot.handlers.commands.logging import log
from bot.databases.database_manager import DatabaseManager
from bot.app import dp, bot

import asyncio

from bot.handlers.routers.accounts import router_tasks_account
from bot.handlers.routers.articles import router_tasks_articles
from bot.handlers.routers.images import router_tasks_images
from bot.handlers.routers.control_panel import router_tasks_list
from bot.handlers.routers.taskbar import router_tasks_panel
from bot.handlers.routers.patterns import router_tasks_patterns
from bot.handlers.routers.prompts import router_tasks_prompts
from bot.handlers.routers.links import router_tasks_links


async def notification():
    """Уведомление об успешном запуске бота"""
    log.debug('Запуск бота')

async def on_startup():
    """Оповещение о запущенном боте"""
    asyncio.create_task(notification())

async def main() -> None:
    """Объявление роутеров. Запуск режима поллинга"""
    db = DatabaseManager()

    db.create_task_db()
    db.create_patterns_db()
    db.create_db_articles()
    db.create_db_images()
    db.create_links_db()
    db.create_main_accounts_db()
    db.create_multi_accounts_db()
    db.create_api_key_db()
    db.create_db_xlsx()

    dp.include_routers(
        router_tasks_list,
        router_tasks_panel,
        router_tasks_prompts,
        router_tasks_patterns,
        router_tasks_articles,
        router_tasks_account,
        router_tasks_links,
        router_tasks_images
    )

    dp.startup.register(on_startup)

    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    log.debug('Бот запущен')
    asyncio.run(main())
