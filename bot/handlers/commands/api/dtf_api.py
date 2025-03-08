import asyncio
import os
import re
import sqlite3
import requests
import json

from bot.config import DB_MULTI_ACCOUNTS_DIRECTORY, TIMEOUT_DELAY
from bot.handlers.commands.logging import get_task_logger, log

from requests.exceptions import ProxyError, ConnectTimeout

from bs4 import BeautifulSoup


class DtfApi:

    def __init__(self,
                 email: str,
                 password: str,
                 task: str,
                 task_type: str,
                 proxy_login: str,
                 proxy_pass: str,
                 proxy_ip: str,
                 proxy_port: str,
                 posts_amount: int
                 ) -> None:
        self.email: str = email
        self.password: str = password
        self.task: str = task
        self.task_type: str = task_type
        self.task_log = get_task_logger(task) if task != '-' else log
        self.is_published: str = True
        self.accessToken: str = None
        self.refreshToken: str = None
        self.user_id: str = None
        self.image: dict = None
        self.posts_amount: int = posts_amount
        self.proxies = {'http': f'http://{proxy_login}:{proxy_pass}@{proxy_ip}:{proxy_port}'}
        self.headers: dict = {
            'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
        }

    def platform_authorization(self) -> tuple:
        """Авторизация на площадке"""
        data = {
            'email': self.email,
            'password': self.password,
        }

        try:
            response = requests.post(
                url='https://api.dtf.ru/v3.4/auth/email/login',
                headers=self.headers,
                data=data,
                proxies=self.proxies
            )
            self.task_log.debug(f'dtf.ru Ответ площадки на запрос авторизации: {response.text}')
            response = json.loads(response.text)

            try:
                result = response['message']

                if result == 'logined':
                    self.task_log.debug(f'dtf.ru Авторизация прошла успешно')
                    self.accessToken = response['data']['accessToken']
                    self.refreshToken = response['data']['refreshToken']
                    return True, '-', self.accessToken

                if self.task_type != 'Основной':
                    with sqlite3.connect(DB_MULTI_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                        cursor = connection.cursor()
                        cursor.execute(
                            """
                            UPDATE Accounts
                            SET account_status = ?
                            WHERE account_email = ? AND account_password = ?
                            """,
                            (str(result), self.email, self.password)
                        )
                        connection.commit()
                self.task_log.debug(f'dtf.ru Не удалось авторизоваться')
                return False, result, '-'
            except Exception as e:
                self.task_log.debug(f'dtf.ru Не удалось авторизоваться: {e}')
                return False, str(response), '-'
        except ProxyError:
            self.task_log.debug(f'dtf.ru Ошибка прокси-сервера')
            return False, 'Ошибка прокси', '-'
        except ConnectTimeout:
            self.task_log.debug("Время ожидания соединения с прокси истекло.")
            return False, 'Ошибка прокси', '-'
        except Exception as e:
            self.task_log.debug(f"Непредвиденная ошибка: {e}")
            return False, f'Неизвестная ошибка: {e}', '-'

    def platform_get_user_data(self) -> tuple:
        """Получение данных о пользователе"""
        token = {'JWTAuthorization': f'Bearer {self.accessToken}'}
        new_headers = self.headers.copy()
        new_headers.update(token)

        try:
            response = requests.get(
                url='https://api.dtf.ru/v2.1/subsite/me',
                headers=new_headers,
                proxies=self.proxies
            )

            self.task_log.debug(f'dtf.ru Ответ площадки на запрос получения данных о пользователе: {response.text}')
            response = json.loads(response.text)
            isBanned = response['result']['isBanned']

            if isBanned:
                if self.task_type != 'Основной':
                    with sqlite3.connect(DB_MULTI_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
                        cursor = connection.cursor()
                        cursor.execute(
                            """
                            UPDATE Accounts
                            SET account_status = ?
                            WHERE account_email = ? AND account_password = ?
                            """,
                            ('Заблокирован', self.email, self.password)
                        )
                        connection.commit()
                return False, 'Аккаунт заблокирован'
            else:
                try:
                    self.user_id = response['result']['id']
                    self.task_log.debug(f'dtf.ru Данные пользователя успешно получены')
                    return True, '-'
                except Exception as e:
                    self.task_log.debug(f'dtf.ru Не удалось получить данные пользователя по причине: {str(e)}')
                    return False, str(response)
        except ProxyError:
            self.task_log.debug(f'dtf.ru Ошибка прокси-сервера')
            return False, 'Ошибка прокси'
        except ConnectTimeout:
            self.task_log.debug("Время ожидания соединения с прокси истекло.")
            return False, 'Ошибка прокси'
        except Exception as e:
            self.task_log.debug(f"Непредвиденная ошибка: {e}")
            return False, f'Неизвестная ошибка: {e}'

    def platform_image_upload(self, image_path) -> tuple:
        """Загрузка изображения на площадку"""

        try:
            with open(image_path, 'rb') as file:
                response = requests.post(
                    url='https://upload.dtf.ru/v2.8/uploader/upload',
                    headers=self.headers,
                    files={"file": file},
                    proxies=self.proxies
                )

            self.task_log.debug(f'dtf.ru Ответ площадки на запрос загрузки изображения: {response.text}')
            response = json.loads(response.text)
            try:
                self.image = response['result'][0]
                self.task_log.debug(f'dtf.ru Изображение успешно загружено')
                return True, '-'
            except Exception as e:
                self.task_log.debug(f'dtf.ru Не удалось загрузить изображение: {e}')
                return False, str(response)
        except ProxyError:
            self.task_log.debug(f'dtf.ru Ошибка прокси-сервера')
            return False, 'Ошибка прокси'
        except ConnectTimeout:
            self.task_log.debug("Время ожидания соединения с прокси истекло.")
            return False, 'Ошибка прокси'
        except Exception as e:
            self.task_log.debug(f"Неизвестная ошибка: {e}")
            return False, f'Неизвестная ошибка: {e}'

    def platform_images_upload(self, image_path) -> tuple:
        """Загрузка изображений на площадку"""

        try:
            with open(image_path, 'rb') as file:
                response = requests.post(
                    url='https://upload.dtf.ru/v2.8/uploader/upload',
                    headers=self.headers,
                    files={"file": file},
                    proxies=self.proxies
                )

            self.task_log.debug(f'dtf.ru Ответ площадки на запрос загрузки изображения: {response.text}')
            response = json.loads(response.text)
            try:
                self.task_log.debug(f'dtf.ru Изображение успешно загружено')
                return True, response['result'][0]
            except Exception as e:
                self.task_log.debug(f'dtf.ru Не удалось загрузить изображение: {e}')
                return False, str(response)
        except ProxyError:
            self.task_log.debug(f'dtf.ru Ошибка прокси-сервера')
            return False, 'Ошибка прокси'
        except ConnectTimeout:
            self.task_log.debug("Время ожидания соединения с прокси истекло.")
            return False, 'Ошибка прокси'
        except Exception as e:
            self.task_log.debug(f"Неизвестная ошибка: {e}")
            return False, f'Неизвестная ошибка: {e}'

    async def platform_publishing(self, text) -> tuple:
        """Публикация статьи"""
        token = {'JWTAuthorization': f'Bearer {self.accessToken}'}
        new_headers = self.headers.copy()
        new_headers.update(token)

        try:
            self.image['data']['base64preview'] = self.image['data']['base64preview'].replace(r"\/", "/")

            soup = BeautifulSoup(text, "html.parser")

            parent = soup.html if soup.html else soup
            parent = parent.body if parent.body else parent

            ignored_tags = {"html", "head", "meta", "title", "script", "style", "link"}
            allowed_tags = {"ul", "ol", "h1", "h2", "h3"}
            fixed_tags = {"b", "a", "i"}

            tag_replacements = {
                "em": "i",
                "strong": "b",
                "u": "i",
                "h4": "h3",
                "h5": "h3",
                "h6": "h3",
                "span": "p"
            }

            # Замена синонимичные теги за один цикл
            for old_tag, new_tag in tag_replacements.items():
                for tag in parent.find_all(old_tag):
                    tag.name = new_tag

            elements = []

            # Получаем верхнеуровневые теги, исключая ненужные
            for tag in parent.find_all(recursive=False):
                if tag.name not in ignored_tags:
                    if tag.name in fixed_tags:
                        p_tag = soup.new_tag("p")
                        p_tag.append(tag)
                        elements.append(p_tag)
                    else:
                        elements.append(tag)

            # Разворачиваем <p>, если оно содержит разрешённые теги
            for index in range(len(elements)):
                for child in elements[index].contents:
                    if child.name in allowed_tags:
                        elements[index] = child

            result = []

            elements = [el for el in elements if el.text.strip() or (str(
                el) == '<div class="block-delimiter" data="[object Object]"></div>') or (str(el).startswith(
                '<div type="image">') or (str(el) == '<div type="links"></div>'))]

            if elements[0].name == 'h1':
                for el in elements:
                    if el.name == 'h1':
                        result.append(el.getText(strip=True))

                    elif el.name == 'h2' or el.name == 'h3':
                        content = el.getText()
                        anchor = el.get('anchor')
                        hidden = el.get('hidden')
                        el.attrs.pop("anchor", None)
                        el.attrs.pop("hidden", None)

                        result.append({
                            "type": "header",
                            "data": {
                                "text": content,
                                "style": el.name
                            },
                            "cover": False,
                            "hidden": hidden == "true",
                            "anchor": f"{anchor}" if anchor else ""
                        })

                    elif el.name == 'p':
                        anchor = el.get('anchor')
                        hidden = el.get('hidden')
                        el.attrs.pop("anchor", None)
                        el.attrs.pop("hidden", None)

                        result.append({
                            "type": "text",
                            "data": {
                                "text": str(el)
                            },
                            "cover": False,
                            "hidden": hidden == "true",
                            "anchor": f"{anchor}" if anchor else ""
                        })

                    elif str(el) == '<div class="block-delimiter" data="[object Object]"></div>':
                        result.append({
                            "type": "delimiter",
                            "data": {
                                "type": "default"
                            },
                            "cover": False,
                            "hidden": False,
                            "anchor": ""
                        })

                    elif el.name == 'div' and el.get('type') == 'links':
                        if self.task_type == 'Основной' and self.posts_amount is not None:
                            anchor = el.get('anchor')

                            self.task_log.debug(f"dtf.ru Получение ссылок на статьи в количестве: {self.posts_amount} шт.")

                            data = await self.fetch_user_posts(posts_amount=self.posts_amount)

                            if data:
                                self.task_log.debug(f"dtf.ru Ссылки получены: {data} шт.")
                                for link, theme in data:
                                    result.append({
                                        "type": "text",
                                        "data": {
                                            "text": f'<p>📌 <a href="{link}">{theme}</a></p>'
                                        },
                                        "cover": False,
                                        "hidden": False,
                                        "anchor": f"{anchor}" if anchor else ""
                                    })
                            else:
                                self.task_log.debug(f"dtf.ru Не удалось получить ссылки.")
                                if 'h3' in str(result[-1]).lower():
                                    result.pop(-1)
                        else:
                            if 'h3' in str(result[-1]).lower():
                                result.pop(-1)

                    elif el.name == 'div' and el.get('type') == 'image':
                        anchor = el.get('anchor')
                        hidden = el.get('hidden')
                        el.attrs.pop("anchor", None)
                        el.attrs.pop("hidden", None)

                        IMAGE_FOLDER = "bot/assets/images/"
                        div_text = el.getText(strip=True)

                        if div_text:
                            for file in os.listdir(IMAGE_FOLDER):
                                if file.startswith(div_text):
                                    image_path = os.path.join(IMAGE_FOLDER, file)
                                    flag, image = self.platform_images_upload(image_path)

                                    if flag:
                                        result.append({
                                            "type": "media",
                                            "cover": False,
                                            "hidden": hidden == "true",
                                            "anchor": f"{anchor}" if anchor else "",
                                            "data": {
                                                "items": [
                                                    {
                                                        "title": "",
                                                        "image": image,
                                                    }
                                                ]
                                            }
                                        })
                                        break

                    elif el.name == 'ul' or el.name == 'ol':
                        content = []
                        anchor = el.get('anchor')
                        hidden = el.get('hidden')

                        el.attrs.pop("anchor", None)
                        el.attrs.pop("hidden", None)

                        for child in el.contents:
                            if child.name == 'li':
                                item = ""
                                for obj in child.contents:
                                    item += str(obj)
                                content.append(item)

                        if content:
                            result.append({
                                "type": "list",
                                "data": {
                                    "items": content,
                                    "type": el.name.upper()
                                },
                                "cover": False,
                                "hidden": hidden == "true",
                                "anchor": f"{anchor}" if anchor else ""
                            })

                    elif el.name == 'div' and el.get('type') == 'quote':
                        anchor = el.get('anchor')
                        hidden = el.get('hidden')
                        text_content = None
                        subline = None

                        for child in el.contents:
                            if child.name == 'p' and child.get('style') == 'q-text':
                                child.attrs.pop("style", None)
                                text_content = str(child)

                            elif child.name == 'p' and child.get('style') == 'podp-do-80':
                                child.attrs.pop("style", None)

                                current_length = 0
                                trimmed_html = ""

                                for obj in child.contents:
                                    obj_text = BeautifulSoup(str(obj), "html.parser").get_text()
                                    if current_length + len(obj_text) <= 80:
                                        trimmed_html += str(obj)
                                        current_length += len(obj_text)
                                    else:
                                        trimmed_html += str(obj)[:80-current_length]
                                        break

                                subline = trimmed_html

                        if text_content:
                            result.append({
                                "type": "quote",
                                "data": {
                                    "text": text_content,
                                    "subline1": subline if subline else "",
                                    "subline2": "",
                                    "type": "",
                                    "text_size": "",
                                    "image": None
                                },
                                "cover": False,
                                "hidden": hidden == "true",
                                "anchor": f"{anchor}" if anchor else ""
                            })
            else:
                text = 'Текст статьи начинается с тега отличного от <h1>.'
                self.task_log.debug(f'dtf.ru Ошибка при распознавании текста статьи: {text}')
                return False, None, text

            article = {
                "user_id": self.user_id,
                "type": 1,
                "subsite_id": self.user_id,
                "title": result[0],
                "entry": {
                    "blocks": [
                        result[1],
                        {
                            "type": "media",
                            "cover": False,
                            "hidden": False,
                            "anchor": "",
                            "data": {
                                "items": [
                                    {
                                        "title": "",
                                        "image": self.image,
                                    }
                                ]
                            }
                        },
                        *result[2:]
                    ]
                },
                "is_published": self.is_published
            }

            json_data = json.dumps(article, ensure_ascii=False, separators=(',', ':'))

            try:
                response = requests.post(
                    url='https://api.dtf.ru/v2.1/editor',
                    headers=new_headers,
                    data={"entry": json_data},
                    proxies=self.proxies
                )
                self.task_log.debug(f'dtf.ru Ответ площадки на запрос публикации статьи: {response.text}')
                response = json.loads(response.text)

                try:
                    article_url = response['result']['entry']['url']
                    self.task_log.debug(f'dtf.ru Статья успешно опубликована: {article_url}')
                    return True, article_url, '-'
                except Exception as e:
                    self.task_log.debug(f'dtf.ru Не удалось опубликовать статью по причине: {str(e)}')
                    return False, None, str(response)
            except ProxyError:
                self.task_log.debug(f'dtf.ru Ошибка прокси-сервера')
                return False, '-', 'Ошибка прокси'
            except ConnectTimeout:
                self.task_log.debug("Время ожидания соединения с прокси истекло.")
                return False, '-', 'Ошибка прокси'
            except Exception as e:
                self.task_log.debug(f"Неизвестная ошибка при публикации статьи: {e}")
                return False, '-', f'Неизвестная ошибка при публикации статьи: {e}'
        except Exception as e:
            self.task_log.debug(f"Неизвестная ошибка при публикации статьи: {e}")
            return False, '-', f'Неизвестная ошибка при публикации статьи: {e}'

    async def platform_publishing_server(self, article_path, currents_replace, new_replace) -> tuple:
        """Публикация готовой json-статьи"""

        token = {'JWTAuthorization': f'Bearer {self.accessToken}'}
        new_headers = self.headers.copy()
        new_headers.update(token)

        with open(article_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if currents_replace != 'None' and new_replace != 'None':
            article_data_str = json.dumps(data, ensure_ascii=False)

            if any(word in article_data_str for word in currents_replace):
                pattern = re.compile("|".join(map(re.escape, currents_replace)))
                article_data_str = pattern.sub(new_replace, article_data_str)
                data = json.loads(article_data_str)

        title = data['title']
        blocks = data['blocks']

        recommend_pattern = re.compile(r'рекомендуем(ое)?\s+(к\s+прочтению|прочитать|ознакомиться)', re.IGNORECASE)

        filter_count = 7

        filtered_part = blocks[-filter_count:]

        remove_links = False
        filtered_blocks = []

        for block in filtered_part:
            block_str = str(block)

            if recommend_pattern.search(block_str):
                remove_links = True

            if remove_links and '<a href=' in block_str:
                continue

            filtered_blocks.append(block)

        result_blocks = blocks[:-filter_count] + filtered_blocks

        data = await self.fetch_user_posts(posts_amount=self.posts_amount)

        if data:
            for link, theme in data:
                result_blocks.append({
                    "type": "text",
                    "data": {
                        "text": f'<p>📌 <a href="{link}">{theme}</a></p>'
                    },
                    "cover": False,
                    "hidden": False,
                    "anchor": ""
                })
        else:
            if 'h3' in str(result_blocks[-1]).lower():
                result_blocks.pop(-1)

        article = {
            "user_id": self.user_id,
            "type": 1,
            "subsite_id": self.user_id,
            "title": title,
            "entry": {
                "blocks": [
                    *result_blocks
                ]
            },
            "is_published": self.is_published
        }

        json_data = json.dumps(article, ensure_ascii=False, separators=(',', ':'))

        try:
            response = requests.post(
                url='https://api.dtf.ru/v2.1/editor',
                headers=new_headers,
                data={"entry": json_data},
                proxies=self.proxies
            )
            self.task_log.debug(f'dtf.ru Ответ площадки на запрос публикации статьи: {response.text}')
            response = json.loads(response.text)

            try:
                article_url = response['result']['entry']['url']
                self.task_log.debug(f'dtf.ru Статья успешно опубликована: {article_url}')
                return True, article_url, '-'
            except Exception as e:
                self.task_log.debug(f'dtf.ru Не удалось опубликовать статью по причине: {str(e)}')
                return False, None, str(response)
        except ProxyError:
            self.task_log.debug(f'dtf.ru Ошибка прокси-сервера')
            return False, '-', 'Ошибка прокси'
        except ConnectTimeout:
            self.task_log.debug("Время ожидания соединения с прокси истекло.")
            return False, '-', 'Ошибка прокси'
        except Exception as e:
            self.task_log.debug(f"Неизвестная ошибка при публикации статьи: {e}")
            return False, '-', f'Неизвестная ошибка при публикации статьи: {e}'

    async def platform_authorization_v2(self) -> tuple:
        """Авторизация на площадке ver. 2"""

        data = {
            'email': self.email,
            'password': self.password,
        }

        try:
            response = requests.post(
                url=f'https://api.dtf.ru/v3.4/auth/email/login',
                headers=self.headers,
                data=data,
                proxies=self.proxies
            )

            if 'Too many calls' in response.text:
                log.debug('Превышение запросов авторизации. Задержка 10 мин.')
                await asyncio.sleep(600)
                return False, response.text, '-'

            response = json.loads(response.text)

            try:
                result = response['message']

                if result == 'logined':
                    print(f'dtf.ru Авторизация прошла успешно')
                    self.accessToken = response['data']['accessToken']
                    self.refreshToken = response['data']['refreshToken']
                    return True, '-', self.accessToken

                print(f'dtf.ru Ответ площадки на запрос авторизации: {response}')
                print(f'dtf.ru Не удалось авторизоваться')
                return False, result, '-'
            except Exception as e:
                print(f'dtf.ru Ответ площадки на запрос авторизации: {response}')
                print(f'dtf.ru Не удалось авторизоваться: {e}')
                return False, str(response), '-'
        except ProxyError:
            print(f'dtf.ru Ошибка прокси-сервера')
            return False, 'Ошибка прокси', '-'
        except ConnectTimeout:
            print("Время ожидания соединения с прокси истекло.")
            return False, 'Ошибка прокси', '-'
        except Exception as e:
            print(f"Непредвиденная ошибка: {e}")
            return False, f'Неизвестная ошибка: {e}', '-'


    def platform_get_exist_article(self, article_id) -> tuple:
        """Получение данных о пользователе"""
        token = {'JWTAuthorization': f'Bearer {self.accessToken}'}
        new_headers = self.headers.copy()
        new_headers.update(token)

        try:
            response = requests.get(
                url=f'https://api.dtf.ru/v2.1/editor/{article_id}',
                headers=new_headers,
                proxies=self.proxies
            )
            response = json.loads(response.text)

            try:
                article_data = response['result']['entry']
                return True, article_data, '-'
            except Exception as e:
                print(
                    f'dtf.ru Не удалось получить статью. Ответ площадки на запрос получения данных статьи: {response}')
                return False, None, str(response)
        except ProxyError:
            print(f'dtf.ru Ошибка прокси-сервера')
            return False, '-', 'Ошибка прокси'
        except ConnectTimeout:
            print("Время ожидания соединения с прокси истекло.")
            return False, '-', 'Ошибка прокси'
        except Exception as e:
            print(f"Неизвестная ошибка при публикации статьи: {e}")
            return False, '-', f'Неизвестная ошибка при публикации статьи: {e}'

    def platform_article_edit(self, article_data, currents_replace, new_replace) -> tuple:
        """Публикация статьи"""
        token = {'JWTAuthorization': f'Bearer {self.accessToken}'}
        new_headers = self.headers.copy()
        new_headers.update(token)

        article_data_str = json.dumps(article_data, ensure_ascii=False)

        if any(word in article_data_str for word in currents_replace):
            pattern = re.compile("|".join(map(re.escape, currents_replace)))
            article_data_str = pattern.sub(new_replace, article_data_str)

            article_data = json.loads(article_data_str)
        else:
            return True, '-', '-'

        json_data = json.dumps(article_data, ensure_ascii=False, separators=(',', ':'))

        try:
            response = requests.post(
                url=f'https://api.dtf.ru/v2.1/editor',
                headers=new_headers,
                data={"entry": json_data},
                proxies=self.proxies
            )
            response = json.loads(response.text)

            try:
                article_url = response['result']['entry']['url']
                print(f'dtf.ru Статья успешно опубликована: {article_url}')
                return True, article_url, '-'
            except Exception as e:
                print(
                    f'dtf.ru Не удалось опубликовать статью. Ответ площадки на запрос публикации статьи: {response}')
                return False, None, str(response)
        except ProxyError:
            print(f'dtf.ru Ошибка прокси-сервера')
            return False, '-', 'Ошибка прокси'
        except ConnectTimeout:
            print("Время ожидания соединения с прокси истекло.")
            return False, '-', 'Ошибка прокси'
        except Exception as e:
            print(f"Неизвестная ошибка при публикации статьи: {e}")
            return False, '-', f'Неизвестная ошибка при публикации статьи: {e}'

    async def fetch_user_posts(self, posts_amount: int):
        base_url = f'https://api.dtf.ru/v2.8/timeline'
        params = {'markdown': 'false', 'sorting': 'new', 'subsitesIds': self.user_id}

        posts = []

        try:
            while len(posts) < posts_amount:
                await asyncio.sleep(1)

                response = requests.get(base_url, params=params)
                response.raise_for_status()

                result = response.json().get('result', {})
                items = result.get('items', [])

                if not items:
                    break

                posts.extend([(item['data']['url'], item['data']['title']) for item in items])

                params['lastId'] = result.get('lastId')
                params['lastSortingValue'] = result.get('lastSortingValue')

            return posts[:posts_amount]
        except Exception as e:
            return False

