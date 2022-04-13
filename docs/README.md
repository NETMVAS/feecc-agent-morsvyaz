<h2 align="center">Feecc Workbench Daemon</h2>

<p align="center">
    <img alt="Workflow status" src="https://img.shields.io/github/workflow/status/NETMVAS/feecc-agent-morsvyaz/Python%20CI?label=CI%20checks">
    <img alt="GitHub License" src="https://img.shields.io/github/license/NETMVAS/feecc-agent-morsvyaz">
    <img alt="Maintenance" src="https://img.shields.io/maintenance/yes/2022">
    <img alt="Black" src="https://img.shields.io/badge/code%20style-black-000000.svg">
</p>

> "Feecc Workbench Daemon - это сердце системы контроля качества Feecc. Он устанавливается на клиентские устройства,
> расположенные на рабочих местах сотрудников, предоставляя пользователям
> доступ ко всем возможностям Feecc и гибкую систему конфигурации для быстрого начала работы."

<h2 align="center">Установка и запуск</h2>

> Предполагаем, что вы уже установили Ubuntu (или другой дистрибутив Linux), Docker и Docker-compose.

### Развертывание Feecc Workbench Daemon

Клонируйте данный репозиторий с GitHub с помощью команды `git clone`.

Перейдите в папку репозитория и поменяйте файл `docker-compose.yml` в соответствии со своими нуждами. Конфигурация
определяется рядом переменных окружения:

- **DB_MONGO_CONNECTION_URL** (Required): Your MongoDB connection URI
- **ROBONOMICS_ENABLE_DATALOG** (Optional): Whether to enable datalog posting or not
- **ROBONOMICS_ACCOUNT_SEED** (Optional): Your Robonomics network account seed phrase
- **ROBONOMICS_SUBSTRATE_NODE_URL** (Optional): Robonomics network node URI
- **YOURLS_SERVER** (Required): Your Yourls server URL
- **YOURLS_USERNAME** (Required): Your Yourls server username
- **YOURLS_PASSWORD** (Required): Your Yourls server password
- **IPFS_GATEWAY_ENABLE** (Optional): Whether to enable IPFS posting or not
- **IPFS_GATEWAY_IPFS_SERVER_URI** (Optional): Your IPFS gateway deployment URI
- **PRINTER_ENABLE** (Optional): Whether to enable printing or not
- **PRINTER_PRINT_SERVER_URI** (Optional): Your Print-server deployment URI
- **PRINTER_PRINT_BARCODE** (Optional): Whether to print barcodes or not
- **PRINTER_PRINT_QR** (Optional): Whether to print QR codes or not
- **PRINTER_PRINT_QR_ONLY_FOR_COMPOSITE** (Optional): Whether to enable QR code printing for non-composite units or note
  or not
- **PRINTER_QR_ADD_LOGOS** (Optional): Whether to add logos to the QR code or not
- **PRINTER_PRINT_SECURITY_TAG** (Optional): Whether to enable printing security tags or not
- **PRINTER_SECURITY_TAG_ADD_TIMESTAMP** (Optional): Whether to enable timestamps on security tags or not
- **CAMERA_ENABLE** (Optional): Whether to enable Cameraman or not
- **CAMERA_CAMERAMAN_URI** (Optional): Your Cameraman deployment URI
- **CAMERA_CAMERA_NO** (Optional): Camera number
- **WORKBENCH_NUMBER** (Required): Workbench number
- **HID_DEVICES_RFID_READER** (Optional): RFID reader device name
- **HID_DEVICES_BARCODE_READER** (Optional): Barcode reader device name

Разверните Feecc Workbench Daemon при помощи Docker-compose: находясь в корне репозитория введите команду
`sudo docker-compose up -d --build`.

> Обратите внимание: опция `--build` говорит системе собрать образ контейнера перед запуском. В зависимости от
> скорости соединения и конфигурации машины этот процесс может быть достаточно долгим, однако нет необходимости
> повторять этот шаг перед каждым запуском. При последующем запуске эту опцию можно будет убрать, однако после
> каждого обновления или изменения конфигурации образ требуется собрать заново. Повторная сборка обычно происходит
> гораздо быстрее, т.к. использует кеш предыдущей сборки, если он не устарел.

После этого шага сервер должен быть доступен по адресу `127.0.0.1:5000`. Проверьте, запустились ли ваши контейнеры с
помощью менеджера процессов Docker: введите команду `sudo docker ps` и удостоверьтесь в том, что видите в списке
процессов контейнер `feecc_workbench_daemon`. Если это не так, вероятно возникли ошибки на этапе сборки и запуска.
Проверьте лог сборки, устраните их и повторите предыдущий шаг.

Если контейнер присутствует в таблице, попробуйте перейти в браузер и открыть страницу `http://127.0.0.1:5000/docs`, в
ней должна быть отражена документация по REST API серверу системы. Если страница по этому адресу недоступна, то сервер
не запустился должным образом. Следует проверить логи внутри контейнера на предмет ошибок, исправить их и повторить
сборку и запуск.
