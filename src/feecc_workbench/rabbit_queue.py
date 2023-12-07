import asyncio
import httpx
from aio_pika import Message, connect
from aio_pika import connect
from aio_pika.abc import AbstractIncomingMessage

n=0
file_path = ''
headers = ''
base_url = ''
files = ''

async def send_message_to_queue(message) -> None:
    # Perform connection
    connection = await connect("amqp://guest:guest@localhost/")

    async with connection:
        # Creating a channel
        channel = await connection.channel()

        # Declaring queue
        queue = await channel.declare_queue("ipfs_message")

        # Sending the message
        await channel.default_exchange.publish(
            Message(message.encode()),
            routing_key=queue.name,
        )

        #print(f" [x] Sent {message}")

async def send_message_to_client(file_path,headers,base_url,files):
    async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
        if file_path.exists():
            httpx.Response = await client.post(url="/upload-file", headers=headers, files=files)
        else:
            json = {"absolute_path": str(file_path)}
            await client.post(url="/by-path", headers=headers, json=json)
    
async def callback(message: AbstractIncomingMessage):
    global n, headers,files,base_url,file_path
        
    message_from_queue = message.body.decode("utf-8")
    match n:
        case 0: file_path = message_from_queue
        case 1: headers = message_from_queue
        case 2: base_url = message_from_queue
        case 3: files = message_from_queue
    n += 1
    if n > 3: 
        n = 0
        send_message_to_client(file_path,headers,base_url,files)

async def message_receiv_from_queue() -> None:
    # Perform connection
    connection = await connect("amqp://guest:guest@localhost/")
    async with connection:
        # Creating a channel
        channel = await connection.channel()

        # Declaring queue
        queue = await channel.declare_queue("ipfs_message")

        # Start listening the queue
        await queue.consume(callback, no_ack=True)

        #print(" [*] Waiting for messages. To exit press CTRL+C")
        await asyncio.Future()

async def rabbit_queue(message):
    #message = [_file_path,_headers,_base_url,_files]
    for mess in message:
        await asyncio.create_task(send_message_to_queue(mess))
    asyncio.create_task(message_receiv_from_queue())
