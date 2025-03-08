from bot.config import DB_DIRECTORY, TIMEOUT_DELAY, DB_TASK_DIRECTORY, DB_PATTERNS_DIRECTORY, \
    DB_MAIN_ACCOUNTS_DIRECTORY, DB_MULTI_ACCOUNTS_DIRECTORY, DB_OPENAI_API_KEY_DIRECTORY, DB_LINKS_DIRECTORY, \
    DB_ARTICLES_DIRECTORY, DB_IMAGES_DIRECTORY, DB_XLSX_DIRECTORY

import sqlite3

class DatabaseManager:

    @staticmethod
    def create_db_main(task: str) -> None:
        """Создание базы данных для Основных аккаунтов"""

        connection = sqlite3.connect(DB_DIRECTORY + task + '.db', timeout=TIMEOUT_DELAY)
        cursor = connection.cursor()
        # Создание таблицы Prompts (Промты), если она ещё не создана
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS Prompts ("
            "id INTEGER PRIMARY KEY, "
            "prompt TEXT NOT NULL, "
            "prompt_theme TEXT NOT NULL, "
            "marks TEXT, "
            "xlsx_id TEXT) "
        )
        # Создание таблицы Articles (Статьи), если она ещё не создана
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS Articles ("
            "id INTEGER PRIMARY KEY, "
            "article_text TEXT NOT NULL, "
            "article_image TEXT NOT NULL, "
            "marks TEXT, "
            "status TEXT, "
            "xlsx_id TEXT) "
        )

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS ModelAI ("
            "id INTEGER PRIMARY KEY, "
            "model_text TEXT, "
            "model_image TEXT)"
        )

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS TasksSettings ("
            "id INTEGER PRIMARY KEY, "
            "indexing TEXT NOT NULL, "
            "user_id TEXT NOT NULL, "
            "api_key TEXT NOT NULL, "
            "searchengine TEXT NOT NULL, "
            "se_type TEXT NOT NULL, "
            "timeout_task_cycle TEXT NOT NULL, "
            "timeout_posting_articles TEXT NOT NULL, "
            "flag_posting_db TEXT NOT NULL, "
            "flag_posting_for_main TEXT NOT NULL, "
            "count_key_words TEXT NOT NULL)"
        )

        cursor.execute("SELECT COUNT(*) FROM TasksSettings")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute(
                """INSERT INTO TasksSettings (indexing, user_id, api_key, searchengine, se_type, timeout_task_cycle, 
                timeout_posting_articles, flag_posting_db, 
                count_key_words, flag_posting_for_main) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ('-', '-', '-', '-', '-', '-', '-', '-', '-', '-'))

        connection.commit()

        cursor.execute("SELECT COUNT(*) FROM ModelAI")
        model_count = cursor.fetchone()[0]
        if model_count == 0:
            cursor.execute("""INSERT INTO ModelAI (model_text, model_image) VALUES (?, ?)""",
                           ('-', '-'))

        connection.commit()
        connection.close()

    @staticmethod
    def create_db_multi(task: str) -> None:
        """Создание базы данных для Мультиаккаунтов"""

        connection = sqlite3.connect(DB_DIRECTORY + task + '.db', timeout=TIMEOUT_DELAY)
        cursor = connection.cursor()
        # Создание таблицы Prompts (Промты), если она ещё не создана
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS Prompts ("
            "id INTEGER PRIMARY KEY, "
            "prompt TEXT NOT NULL, "
            "prompt_theme TEXT NOT NULL, "
            "marks TEXT, "
            "xlsx_id TEXT) "
        )
        # Создание таблицы Articles (Статьи), если она ещё не создана
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS Articles ("
            "id INTEGER PRIMARY KEY, "
            "article_text TEXT NOT NULL, "
            "article_image TEXT NOT NULL, "
            "account_login TEXT,"
            "marks TEXT, "
            "status TEXT, "
            "article_url TEXT, "
            "xlsx_id TEXT) "
        )

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS ModelAI ("
            "id INTEGER PRIMARY KEY, "
            "model_text TEXT, "
            "model_image TEXT)"
        )

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS TasksSettings ("
            "id INTEGER PRIMARY KEY, "
            "indexing TEXT NOT NULL, "
            "user_id TEXT NOT NULL, "
            "api_key TEXT NOT NULL, "
            "searchengine TEXT NOT NULL, "
            "se_type TEXT NOT NULL, "
            "count_key_words TEXT NOT NULL)"
        )

        cursor.execute("SELECT COUNT(*) FROM TasksSettings")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute(
                """INSERT INTO TasksSettings (indexing, user_id, api_key, searchengine, se_type, count_key_words) VALUES (?, ?, ?, ?, ?, ?)""",
                ('-', '-', '-', '-', '-', '-', ))

        cursor.execute("SELECT COUNT(*) FROM ModelAI")
        model_count = cursor.fetchone()[0]
        if model_count == 0:
            cursor.execute("""INSERT INTO ModelAI (model_text, model_image) VALUES (?, ?)""",
                           ('-', '-'))

        connection.commit()
        connection.close()

    @staticmethod
    def create_task_db():
        """Создание базы данных заданий"""

        with sqlite3.connect(DB_TASK_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()

            # Создание таблицы Tasks (Задания), если она ещё не создана
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS Tasks ("
                "id INTEGER PRIMARY KEY, "
                "task_name TEXT NOT NULL, "
                "task_type TEXT NOT NULL, "
                "last_status TEXT NOT NULL DEFAULT '-', "
                "status TEXT NOT NULL, "
                "delay TEXT, "
                "posts_count TEXT, "
                "theme_count TEXT NOT NULL DEFAULT '0', "
                "priority_prompts TEXT NOT NULL DEFAULT '-')"
            )

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS TasksSettings ("
                "id INTEGER PRIMARY KEY, "
                "articles_links_count TEXT NOT NULL, "
                "currents_replace TEXT NOT NULL, "
                "new_replace TEXT NOT NULL, "
                "indexing TEXT NOT NULL, "
                "user_id TEXT NOT NULL, "
                "api_key TEXT NOT NULL, "
                "searchengine TEXT NOT NULL, "
                "se_type TEXT NOT NULL, "
                "host TEXT NOT NULL, "
                "port TEXT NOT NULL, "
                "username TEXT NOT NULL, "
                "password TEXT NOT NULL, "
                "timeout_task_cycle TEXT NOT NULL, "
                "timeout_posting_articles TEXT NOT NULL, "
                "flag_posting_db TEXT NOT NULL, "
                "flag_posting_for_main TEXT NOT NULL, "
                "count_key_words TEXT NOT NULL)"
            )

            cursor.execute("SELECT COUNT(*) FROM TasksSettings")
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute("""INSERT INTO TasksSettings (
                articles_links_count,
                currents_replace, new_replace,
                indexing, user_id,
                api_key, searchengine, se_type, 
                host, port, username, password, timeout_task_cycle, 
                timeout_posting_articles, flag_posting_db, 
                count_key_words, flag_posting_for_main) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                               ('4' ,'None', 'None', 'True', '-', '-', '-', '-', '-', '-', '-', '-', '3600', '180', 'True', '15', 'True'))

            connection.commit()

    @staticmethod
    def create_patterns_db():
        """Создание базы данных шаблонов"""

        with sqlite3.connect(DB_PATTERNS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()

            # Создание таблицы Patterns (Шаблоны), если она ещё не создана
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS Patterns ("
                "id INTEGER PRIMARY KEY, "
                "pattern_name TEXT NOT NULL, "
                "pattern TEXT NOT NULL)"
            )

            connection.commit()

    @staticmethod
    def create_links_db():
        """Создание базы данных ссылок"""

        with sqlite3.connect(DB_LINKS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()

            # Создание таблицы Links (Ссылки), если она ещё не создана
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS Links ("
                "id INTEGER PRIMARY KEY, "
                "link_name TEXT NOT NULL, "
                "link_source TEXT NOT NULL)"
            )

            connection.commit()

    @staticmethod
    def create_main_accounts_db():
        """Создание базы данных аккаунтов для Основного режима"""

        with sqlite3.connect(DB_MAIN_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()

            # Создание таблицы Accounts (Аккаунты), если она ещё не создана
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS Accounts ("
                "id INTEGER PRIMARY KEY, "
                "account_email TEXT NOT NULL, "
                "account_password TEXT NOT NULL, "
                "account_login TEXT NOT NULL, "
                "proxy_ip TEXT NOT NULL, "
                "proxy_port TEXT NOT NULL, "
                "proxy_login TEXT NOT NULL,"
                "proxy_password TEXT NOT NULL, "
                "accessToken TEXT DEFAULT '-', "
                "account_url TEXT NOT NULL)"
            )

            connection.commit()

    @staticmethod
    def create_multi_accounts_db():
        """Создание базы данных аккаунтов для Мульти режима"""

        with sqlite3.connect(DB_MULTI_ACCOUNTS_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()

            # Создание таблицы Accounts (Аккаунты), если она ещё не создана
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS Accounts ("
                "id INTEGER PRIMARY KEY, "
                "account_email TEXT NOT NULL, "
                "account_password TEXT NOT NULL, "
                "account_login TEXT NOT NULL, "
                "proxy_ip TEXT NOT NULL, "
                "proxy_port TEXT NOT NULL, "
                "proxy_login TEXT NOT NULL, "
                "proxy_password TEXT NOT NULL, "
                "accessToken TEXT DEFAULT '-', "
                "account_url TEXT NOT NULL, "
                "account_status TEXT DEFAULT '-')"
            )

            connection.commit()

    @staticmethod
    def create_api_key_db():
        """Создание базы данных API-ключ OpenAI"""

        with sqlite3.connect(DB_OPENAI_API_KEY_DIRECTORY, timeout=TIMEOUT_DELAY) as connection:
            cursor = connection.cursor()

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS ApiKey ("
                "id INTEGER PRIMARY KEY, "
                "api_key TEXT)"
            )

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS ModelAI ("
                "id INTEGER PRIMARY KEY, "
                "model_text TEXT, "
                "model_image TEXT)"
            )

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS PromptImage ("
                "id INTEGER PRIMARY KEY, "
                "prompt_text TEXT) "
            )

            cursor.execute("SELECT COUNT(*) FROM ApiKey")
            api_count = cursor.fetchone()[0]
            if api_count == 0:
                cursor.execute("""INSERT INTO ApiKey (api_key) VALUES (?)""",('-',))

            cursor.execute("SELECT COUNT(*) FROM ModelAI")
            model_count = cursor.fetchone()[0]
            if model_count == 0:
                cursor.execute("""INSERT INTO ModelAI (model_text, model_image) VALUES (?, ?)""",
                               ('gpt-4o', 'dall-e-3'))

            cursor.execute("SELECT COUNT(*) FROM PromptImage")
            prompt_count = cursor.fetchone()[0]
            if prompt_count == 0:
                cursor.execute("""INSERT INTO PromptImage (prompt_text) VALUES (?)""",
                               ('Сгенерируй яркую красивую картинку по теме %NAME%, '
                                'с минимальным количеством текста, широкоэкранное соотношение сторон',))

            connection.commit()

    @staticmethod
    def create_db_articles() -> None:
        """Создание базы данных для Статей"""

        connection = sqlite3.connect(DB_ARTICLES_DIRECTORY, timeout=TIMEOUT_DELAY)
        cursor = connection.cursor()

        # Создание таблицы Articles (Статьи), если она ещё не создана
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS Articles ("
            "id INTEGER PRIMARY KEY, "
            "article_text TEXT NOT NULL, "
            "article_image TEXT NOT NULL, "
            "marks TEXT)"
        )

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS ArticlesStatus ("
            "id INTEGER PRIMARY KEY, "
            "status TEXT)"
        )

        cursor.execute("SELECT COUNT(*) FROM ArticlesStatus")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute("""INSERT INTO ArticlesStatus (status) VALUES (?)""", ('-',))

        connection.commit()
        connection.close()

    @staticmethod
    def create_db_images() -> None:
        """Создание базы данных для Изображений"""

        connection = sqlite3.connect(DB_IMAGES_DIRECTORY, timeout=TIMEOUT_DELAY)
        cursor = connection.cursor()

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS Images ("
            "id INTEGER PRIMARY KEY, "
            "image_name TEXT NOT NULL, "
            "image_path TEXT NOT NULL) "
        )
        connection.commit()
        connection.close()

    @staticmethod
    def create_db_xlsx() -> None:
        """Создание базы данных для keys+urls+accounts"""

        connection = sqlite3.connect(DB_XLSX_DIRECTORY, timeout=TIMEOUT_DELAY)
        cursor = connection.cursor()

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS Xlsx ("
            "id INTEGER PRIMARY KEY, "
            "keys TEXT NOT NULL, "
            "urls_accounts TEXT) "
        )
        connection.commit()
        connection.close()