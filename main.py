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
    logging.info(f"Запрос данных с API: {api_url}")
    try:
        response = requests.get(api_url, verify=False, timeout=10)
        response.raise_for_status()
        logging.info("Данные успешно получены с API")
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Ошибка при запросе API: {e}")
        sys.exit(1)


def ensure_cidr(ip_list):
    """Добавляет маску /32 для IP-адресов без маски."""
    return [f"{ip}/32" if '/' not in ip else ip for ip in ip_list]


def generate_ipset_commands(table, data):
    """Генерирует команды для ipset на основе полученных данных."""
    logging.info(f"Генерация команд для ipset для таблицы {table}")
    lines = [f'create {table}_tmp hash:ip family inet hashsize 2048 maxelem 131072']
    data = ensure_cidr(data)  # Добавляем /32 для IP-адресов без маски
    lines.extend([f'add {table}_tmp {ip}' for ip in data])
    return "\n".join(lines)


def save_to_file(file_path, content):
    """Сохраняет содержимое в файл, если оно изменилось."""
    logging.info(f"Проверка изменений и сохранение файла: {file_path}")
    if os.path.isfile(file_path):
        with open(file_path, "r") as file:
            if file.read() == content:
                logging.info("Изменений нет, сохранение не требуется")
                return False

    with open(file_path, "w") as file:
        file.write(content)
        logging.info(f"Файл успешно сохранен: {file_path}")
    return True


def execute_ipset_commands(file_path, table):
    """Выполняет команды для обновления ipset."""
    logging.info(f"Начало выполнения команд для обновления ipset таблицы {table}")
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

    logging.info("Завершено обновление для всех таблиц")
    logging.info("====================")
    sys.exit(0)


if __name__ == "__main__":
    main()
