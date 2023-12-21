#!/opt/scripts/env/bin/python3

import os
import requests
import subprocess
import logging
import socket
import urllib3
import sys

from dotenv import load_dotenv
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

# Отключаем предупреждения о проверке SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Определение корневого каталога проекта
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

ENV_PATH = Path(os.path.join(ROOT_DIR, '.env'))

load_dotenv(dotenv_path=ENV_PATH)

# Настройка логгера
log_file_path = os.path.join(ROOT_DIR, 'logs.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=5)
    ]
)

# Получаем текущий hostname машины
NAS_NAME = os.getenv('NAS_NAME', default=socket.gethostname())

# Константы для таблиц
TABLE = os.getenv('TABLE', default='allow_smtp')
TMP_TABLE = f'{TABLE}_tmp'

# Формируем URL API с использованием текущего hostname
API_EP = f"{os.getenv('API_URL')}?nas_name={NAS_NAME}"

logging.info("Запуск")

# Получаем данные с API с включенной проверкой SSL-сертификата
try:
    response = requests.get(API_EP, verify=False, timeout=10)
    response.raise_for_status()
except requests.RequestException as e:
    logging.error(f"Ошибка при запросе API: {e}")
    sys.exit()

# Преобразуем JSON-ответ в Python-структуру данных
data = response.json()

# Генерируем текст из списка
generated_lines = [
    f'create {TMP_TABLE} hash:ip family inet hashsize 1024 maxelem 65536'
]
for ip in data:
    generated_lines.append(f'add {TMP_TABLE} {ip}')

# Определение пути к файлу относительно корня проекта
file_path = os.path.join(ROOT_DIR, f"{TABLE}.tmp")

changed = False

# Проверяем существование файла перед открытием
if os.path.exists(file_path):
    with open(file_path, "r") as file:
        content = file.read()

    # Сравниваем существующий текст с генерируемым текстом
    if content != "\n".join(generated_lines):
        changed = True
    else:
        logging.info("Изменений нет")
else:
    changed = True

if changed:
    # Сохраняем текст в файл
    with open(file_path, "w") as file:
        file.write("\n".join(generated_lines))
        logging.info(f"Файл успешно создан: {file_path}")

    # Проверяем существование таблицы allow_smtp перед swap и destroy
    commands = [
        f"/sbin/ipset restore -! < {file_path}",
        f"/sbin/ipset swap {TMP_TABLE} {TABLE}",
        f"/sbin/ipset destroy {TMP_TABLE}",
    ]

    for command in commands:
        try:
            logging.info(f"Выполнение команды:{command}")
            subprocess.run(command, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Ошибка при выполнении команды: {e}")

logging.info("Завершено")
logging.info("====================")
sys.exit()
