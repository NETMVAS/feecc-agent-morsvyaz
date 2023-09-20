# Feecc Workbench Daemon

[//]: # (<p>)

[//]: # (    <img alt="Workflow status" src="https://img.shields.io/github/workflow/status/NETMVAS/feecc-agent-morsvyaz/Python%20CI?label=CI%20checks">)

[//]: # (    <img alt="GitHub License" src="https://img.shields.io/github/license/NETMVAS/feecc-agent-morsvyaz">)

[//]: # (    <img alt="Maintenance" src="https://img.shields.io/maintenance/yes/2022">)

[//]: # (    <img alt="Black" src="https://img.shields.io/badge/code%20style-black-000000.svg">)

[//]: # (</p>)

The Feecc Workbench Daemon is the heart of the Feecc system. It is installed on client devices, located on employees' workbenches, providing users with access to all Feecc features and a flexible configuration system to get you up and running quickly.

## Installation and startup

> Assuming you have already installed Ubuntu (or another Linux distribution), Docker and Docker-compose.

Clone this repository from GitHub using the `git clone` command.

Go to the repository folder and change the `docker-compose.yml` file to suit your needs. The configuration is defined by a number of environment variables:

- **MONGODB_URI** (Required): Your MongoDB connection URI
- **MONGODB_DB_NAME** (Required): Your MongoDB DB name
- **ROBONOMICS_ENABLE_DATALOG** (Optional): Whether to enable datalog posting or not
- **ROBONOMICS_ACCOUNT_SEED** (Optional): Your Robonomics network account seed phrase
- **ROBONOMICS_SUBSTRATE_NODE_URI** (Optional): Robonomics network node URI
- **IPFS_GATEWAY_ENABLE** (Optional): Whether to enable IPFS posting or not
- **IPFS_GATEWAY_IPFS_SERVER_URI** (Optional): Your IPFS gateway deployment URI
- **PRINTER_ENABLE** (Optional): Whether to enable printing or not
- **PRINTER_PAPER_ASPECT_RATIO** (Optional): Printer labels aspect ratio (size in mm in form of width:height)
- **PRINTER_PRINT_BARCODE** (Optional): Whether to print barcodes or not
- **PRINTER_PRINT_QR** (Optional): Whether to print QR codes or not
- **PRINTER_PRINT_QR_ONLY_FOR_COMPOSITE** (Optional): Whether to enable QR code printing for non-composite units or note
  or not
- **PRINTER_PRINT_SECURITY_TAG** (Optional): Whether to enable printing security tags or not
- **PRINTER_SECURITY_TAG_ADD_TIMESTAMP** (Optional): Whether to enable timestamps on security tags or not
- **CAMERA_ENABLE** (Optional): Whether to enable Cameraman or not
- **CAMERA_FFMPEG_COMMAND** (Optional): ffmpeg record command
- **WORKBENCH_NUMBER** (Required): Workbench number
- **HID_DEVICES_RFID_READER** (Optional): RFID reader device name
- **HID_DEVICES_BARCODE_READER** (Optional): Barcode reader device name


Deploy the Feecc Workbench Daemon with Docker-compose: At the root of the repository, type:


```
sudo docker-compose up -d --build
```

> Note: the `--build` option tells the system to build an image of the container before running. Depending on the connection speed and machine configuration, this process can be quite long, but there is no need to repeat this step before each startup. This option can be removed at subsequent startups, but after each update or configuration change the image needs to be rebuilt. Rebuilds usually happen much faster as it uses the cache of the previous build, if it is not outdated.

After this step the server should be available at `127.0.0.1:5000`. Check if your containers are running with the Docker process manager: type `sudo docker ps` and make sure that you see the `feecc_workbench_daemon` on the container list. If not, there are probably errors in the build and run phases. Check the build log, fix them, and repeat the previous step.

If the container is present in the table, try going to the browser and opening the `http://127.0.0.1:5000/docs` page, which should contain documentation on the system's REST API interface. If the page at that address is not available, then the server is not started properly. You should check the logs inside the container for errors, fix them and repeat build and run steps.
