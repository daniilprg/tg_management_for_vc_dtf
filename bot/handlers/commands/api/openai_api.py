import asyncio
import os
import sqlite3
from uuid import uuid4

import requests
from openai import AsyncOpenAI

from bot.config import TIMEOUT_DELAY, DB_OPENAI_API_KEY_DIRECTORY, DB_DIRECTORY
from bot.handlers.commands.logging import get_task_logger


async def send_prompt_to_chatgpt_text(prompt, task_name):
    """Отправка промта в ChatGPT-o1 для получения текста"""
    task_log = get_task_logger(task_name)

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT model_text FROM ModelAI WHERE id = 1")
    model_text = cursor.fetchone()[0]
    connection.close()

    with sqlite3.connect(DB_OPENAI_API_KEY_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT api_key FROM ApiKey WHERE id = 1")
        api_key = cursor.fetchone()[0]

        if model_text == '-':
            cursor.execute("SELECT model_text FROM ModelAI WHERE id = 1")
            model_text = cursor.fetchone()[0]

    client = AsyncOpenAI(api_key=api_key)
    try:
        chat_completion = await client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=model_text,
        )
        chat_response = chat_completion.choices[0].message.content

        if len(chat_response) <= 100:
            return False, 'content_policy_violation'

        return chat_response, '-'
    except Exception as e:
        if 'content_policy_violation' in str(e):
            task_log.debug(f'Ошибка: {str(e)}! Промт нарушает политику об отношении контента OpenAI.')
            return False, 'content_policy_violation'
        elif 'quota' in str(e):
            task_log.debug(f'Ошибка: {str(e)}! Закончился баланс API-ключа OpenAI.')
            return False, 'quota'
        else:
            task_log.debug(f'Ошибка: {str(e)}! Не удалось получить текст от ChatGPT-o1.')
            return False, str(e)

async def send_prompt_to_chatgpt_image(prompt, task_name) -> tuple:
    """Отправка промта в ChatGPT-4o для получения изображения"""
    task_log = get_task_logger(task_name)

    connection = sqlite3.connect(DB_DIRECTORY + task_name + '.db', timeout=TIMEOUT_DELAY)
    cursor = connection.cursor()
    cursor.execute("SELECT model_image FROM ModelAI WHERE id = 1")
    model_image = cursor.fetchone()[0]
    connection.close()

    with sqlite3.connect(DB_OPENAI_API_KEY_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT api_key FROM ApiKey WHERE id = 1")
        api_key = cursor.fetchone()[0]

        if model_image == '-':
            cursor.execute("SELECT model_image FROM ModelAI WHERE id = 1")
            model_image = cursor.fetchone()[0]

        cursor.execute("SELECT prompt_text FROM PromptImage WHERE id = 1")
        prompt_text = cursor.fetchone()[0]

    client = AsyncOpenAI(api_key=api_key)
    try:
        chat_completion = await client.images.generate(
                model=model_image,
                prompt=prompt_text.replace('%NAME%', prompt),
                size="1792x1024",
                quality="standard",
                n=1,
        )
        image_url = chat_completion.data[0].url
        image_path = os.path.join('bot/assets/images/', f"{uuid4()}.webp")
        try:
            with requests.get(image_url, stream=True) as r:
                try:
                    with open(image_path, 'wb') as f:
                        f.write(r.content)
                    task_log.debug(f'Изображение успешно скачано: {image_url}')
                    return image_url, image_path
                except Exception as e:
                    task_log.debug(f'Ошибка: {str(e)}! Не удалось скачать изображение. Вторая попытка.')
                    await asyncio.sleep(5)
                    try:
                        with open(image_path, 'wb') as f:
                            f.write(r.content)
                        task_log.debug(f'Изображение успешно скачано: {image_url}')
                        return image_url, image_path
                    except Exception as e:
                        task_log.debug(f'Ошибка: {str(e)}! Не удалось скачать изображение.')
                        return False, str(e)
        except Exception as e:
            task_log.debug(f'Ошибка: {str(e)}! Не удалось скачать изображение: {image_url}')
            return False, str(e)
    except Exception as e:
        if 'content_policy_violation' in str(e):
            task_log.debug(f'Ошибка: {str(e)}! Тема промта нарушает политику об отношении контента OpenAI.')
            return False, 'content_policy_violation_image'
        task_log.debug(f'Ошибка: {str(e)}! Не удалось получить изображение от DALL-E-3.')
        return False, str(e)