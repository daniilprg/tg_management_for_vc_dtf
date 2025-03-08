import asyncio
import os

from bot.config import DB_DIRECTORY
from bot.handlers.commands.logging import log
from bot.handlers.commands.posting_modes.main_posting import task_pause_events


class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.current_tasks = {}
        self.lock = asyncio.Lock()
        self.condition = asyncio.Condition(self.lock)

    async def add_task(self, priority, func, name, accounts, *args):
        accounts = set(accounts)
        paused_tasks = []  # Список имён задач, которые нужно приостановить

        async with self.condition:
            # Если для какого-либо аккаунта уже запущена задача с более высоким приоритетом,
            # новый процесс должен подождать, пока этот аккаунт не освободится.
            while any(
                acc in self.current_tasks and self.tasks[self.current_tasks[acc]]['priority'] > priority
                for acc in accounts
            ):
                log.debug(f"Процесс '{name}' ожидает освобождения аккаунтов с более высоким приоритетом")
                await self.condition.wait()

            # Если для какого-либо аккаунта уже запущена задача с более низким приоритетом,
            # добавляем её в список на паузу.
            for acc in accounts:
                if acc in self.current_tasks:
                    existing_task_name = self.current_tasks[acc]
                    existing_task = self.tasks.get(existing_task_name)
                    if existing_task and existing_task['priority'] < priority:
                        paused_tasks.append(existing_task_name)

            # Приостанавливаем найденные задачи
            for task_name in set(paused_tasks):
                if task_name in self.tasks:
                    log.debug(
                        f"Процесс '{task_name}' приостановлен, так как процесс '{name}' имеет более высокий приоритет"
                    )
                    self.tasks[task_name]['event'].clear()
                    if task_name in task_pause_events and task_pause_events[task_name].is_set():
                        task_pause_events[task_name].clear()

            # Регистрируем новый процесс. Поскольку условие выполнено — этот процесс может стартовать сразу.
            event = asyncio.Event()
            event.set()
            self.tasks[name] = {
                'priority': priority,
                'event': event,
                'func': func,
                'accounts': accounts,
                'args': args
            }
            for acc in accounts:
                self.current_tasks[acc] = name

        # Запускаем функцию задачи
        try:
            await func(event, *args)
            log.debug(f"Процесс '{name}' завершился")
        finally:
            async with self.condition:
                # Удаляем задачу из реестра
                if name in self.tasks:
                    task_accounts = self.tasks[name]['accounts']
                    del self.tasks[name]
                    for acc in task_accounts:
                        self.current_tasks.pop(acc, None)

                # Возобновляем приостановленные задачи, т.к. условия могли измениться
                for task_name in paused_tasks:
                    if task_name in self.tasks:
                        log.debug(
                            f"Процесс '{task_name}' возобновлен, так как процесс '{name}' завершен"
                        )
                        self.tasks[task_name]['event'].set()
                        if task_name in task_pause_events and not task_pause_events[task_name].is_set():
                            task_pause_events[task_name].set()

                # Уведомляем все ожидающие задачи о том, что что-то изменилось
                self.condition.notify_all()

manager = TaskManager()
