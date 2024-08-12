#!/opt/scripts/env/bin/python3

import os
import requests
import subprocess
import logging
import socket
import urllib3
import sys

from logging.handlers import TimedRotatingFileHandler

# Отключаем предупреждения о проверке SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Определение корневого каталога проекта
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Настройка логгера
log_file_path = os.path.join(ROOT_DIR, 'logs.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=5)
    ]
)

API_URL = 'https://ex.spi.uz/api/test'

# Получаем текущий hostname машины
NAS_NAME = os.getenv('NAS_NAME', default=socket.gethostname())


def fetch_data(api_url):
    """Получает данные с API."""
    try:
        response = requests.get(api_url, verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Ошибка при запросе API: {e}")
        sys.exit(1)


def generate_ipset_commands(table, data):
    """Генерирует команды для ipset на основе полученных данных."""
    lines = [f'create {table}_tmp hash:ip family inet hashsize 1024 maxelem 65536']
    lines.extend([f'add {table}_tmp {ip}' for ip in data])
    return "\n".join(lines)


def save_to_file(file_path, content):
    """Сохраняет содержимое в файл, если оно изменилось."""
    if os.path.isfile(file_path):
        with open(file_path, "r") as file:
            if file.read() == content:
                logging.info("Изменений нет")
                return False

    with open(file_path, "w") as file:
        file.write(content)
        logging.info(f"Файл успешно создан: {file_path}")
    return True


def execute_ipset_commands(file_path, table):
    """Выполняет команды для обновления ipset."""
    commands = [
        f"/sbin/ipset restore -! < {file_path}",
        f"/sbin/ipset swap {table}_tmp {table}",
        f"/sbin/ipset destroy {table}_tmp",
    ]

    for command in commands:
        try:
            logging.info(f"Выполнение команды: {command}")
            subprocess.run(command, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Ошибка при выполнении команды: {e}")


def main():
    logging.info("Запуск обновления для таблиц")

    # Ассоциативный массив с таблицами и соответствующими URL API
    api_endpoints = {
        'allow_smtp': f"{API_URL}/allow_smtp?nas_name={NAS_NAME}",
        'bypass': f"{API_URL}/zone?name=tasix"
    }

    for table, api_url in api_endpoints.items():
        logging.info(f"Обработка таблицы {table}")

        # Получаем данные с API
        data = fetch_data(api_url)

        # Генерируем команды для ipset
        commands = generate_ipset_commands(table, data)

        # Путь к файлу для сохранения данных
        file_path = os.path.join(ROOT_DIR, f"{table}.tmp")

        # Сохраняем данные в файл и выполняем команды, если данные изменились
        if save_to_file(file_path, commands):
            execute_ipset_commands(file_path, table)

    logging.info("Завершено")
    logging.info("====================")
    sys.exit(0)


if __name__ == "__main__":
    main()
