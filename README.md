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

Установим зависимости, необходимые для сборки некоторых используемых модулей:

`sudo apt update && sudo apt install -y zlib1g libjpeg-dev python3-distutils`

Установим все необходимые зависимости и активируем виртуальное окружение:

`poetry install && poetry shell`

Поменяем конфигурацию Hub, файлы которой находятся в `config/hub_config.yaml` и `config/workbench_config.yaml`

### Установить Go-IPFS

Для того чтобы бекенд мог работать с сетью IPFS необходимо установить клиент ["Go-IPFS"](https://docs.ipfs.io/reference/go/api/) и 
настроить его на автозапуск.

Hub использует библиотеку ["ipfshttpclient"](https://pypi.org/project/ipfshttpclient/), которая на момент написания стабильно работает 
только с Go-IPFS 0.7, поэтому необходимо установить эту версию.

#### Установка

1. Скачать исполняемые файлы со [страницы версий Go-IPFS](https://dist.ipfs.io/go-ipfs):
   
`wget https://dist.ipfs.io/go-ipfs/v0.7.0/go-ipfs_v0.7.0_linux-amd64.tar.gz`

2. Распаковать архив: `tar -xvf go-ipfs_v0.7.0_linux-amd64.tar.gz`

3. Перейти в папку и запустить установочный скрипт: `cd go-ipfs && sudo bash install.sh`

4. Изменить порт шлюза в конфигурации, т.к. он конфликтует с демоном Spoke: `vim /root/.ipfs/config`
Необходимо заменить строку 
   
   `"Gateway": "/ip4/127.0.0.1/tcp/8080"`
   на 
   `"Gateway": "/ip4/127.0.0.1/tcp/8081"`

5. Инициализировать пустой репозиторий IPFS: 
   `sudo ipfs init`

6. Скачать сервис для запуска демона IPFS: 
   
   ```
   cd /etc/systemd/system/
   sudo wget https://raw.githubusercontent.com/NETMVAS/feecc-qa-main/master/services/ipfs.service
   ```

6. Добавить демон IPFS в автозапуск: 
   ```
   sudo systemctl enable ipfs.service
   sudo systemctl start ipfs.service
   ```

Теперь Hub готов к работе, запустим его:

`python app.py`

<h2 align="center">Тестирование приложения</h2>

Для запуска тестов выполните:

`pytest .`
