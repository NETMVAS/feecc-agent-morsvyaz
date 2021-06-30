<h2 align="center">Feecc Hub</h2>

<p align="center">
    <img alt="Workflow status" src="https://img.shields.io/github/workflow/status/NETMVAS/feecc-agent-morsvyaz/Python%20CI?label=CI%20checks">
    <img alt="GitHub License" src="https://img.shields.io/github/license/NETMVAS/feecc-agent-morsvyaz">
    <img alt="Maintenance" src="https://img.shields.io/maintenance/yes/2021">
    <img alt="Black" src="https://img.shields.io/badge/code%20style-black-000000.svg">
</p>

> "Hub - это сердце системы контроля качества Feecc. Hub работает с IPFS, Pinata, FFMPEG, Robonomics Network и другими инструментами, предоставляя пользователю простой программный интерфейс и гибкую систему конфигурации для быстрого начала работы с Feecc."

<h2 align="center">Установка и запуск</h2>

> Для подробной инструкции обратитесь к документации Feecc.


> Предполагаем, что вы уже установили Ubuntu (или другой Debian-based дистрибутив Linux) и Python вместе с Poetry.

Установим все необходимые зависимости и активируем виртуальное окружение:

`poetry install && poetry shell`

Поменяем конфигурацию Hub, файлы которой находятся в `config/hub_config.yaml` и `config/workbench_config.yaml`

Теперь Hub готов к работе, запустим его:

`python app.py`

<h2 align="center">Тестирование приложения</h2>

Для запуска тестов выполните:

`pytest .`
