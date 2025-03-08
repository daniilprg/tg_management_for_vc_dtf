import requests

from bot.handlers.commands.logging import get_task_logger, log

class LinkIndexing:

    def __init__(self,
                 api_key: str, # API-ключ
                 user_id: str, # ID пользователя
                 se_type: str, # Способ индексации
                 task: str, # Задание, если есть
                 ) -> None:
        self.api_key = api_key
        self.user_id = user_id
        self.se_type = se_type
        self.task: str = task
        self.task_log = get_task_logger(task) if task != '-' else log

    def link_indexing(self, link, searchengine):

        data = {
            "api_key": self.api_key,
            "user_id": self.user_id,
            "links": link,
            "searchengine": searchengine,
            "se_type": self.se_type,
        }

        response = requests.post(
            url='https://link-indexing-bot.ru/api/tasks/new',
            data=data,
        )

        self.task_log.debug(f'Ответ индексации ссылки: {response.text}')

        if response.status_code == 200 or response.status_code == 201:
            self.task_log.debug(f'Ссылка успешно отправлена на индексацию')
            return True, '-'

        self.task_log.debug(f'Ссылка не отправлена на индексацию')
        return False, response.text