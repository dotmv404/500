import asyncio
import random
import json
import uuid
import time
from loguru import logger
import aiohttp
import aiohttp_proxy
from websockets import connect
from websockets.exceptions import ConnectionClosedError
from keep_alive import keep_alive
keep_alive()
WEBSOCKET_URL = "wss://nw.nodepay.ai:4576/websocket"
RETRY_INTERVAL = 60  # seconds
PING_INTERVAL = 10  # seconds
retries = 0

CONNECTION_STATES = {
    'CONNECTING': 0,  # Socket has been created. The connection is not yet open.
    'OPEN': 1,  # The connection is open and ready to communicate.
    'CLOSING': 2,  # The connection is in the process of closing.
    'CLOSED': 3,  # The connection is closed or couldn't be opened.
}

def uuidv4():
    return str(uuid.uuid4())

device_id = uuidv4()
browser_id = uuidv4()
socket = None
logger.info(f"Device ID: {browser_id}")

local_storage = {}
sync_storage = {}

def to_json(response):
    if response.ok:
        return response.json()
    return response.raise_for_status()

def valid_resp(resp):
    if 'code' in resp and resp['code'] < 0:
        raise ValueError(resp)
    return resp

async def call_api_info(token, proxy_url):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    async with aiohttp.ClientSession() as session:
        async with session.post("https://sandbox-api.nodepay.ai/api/auth/session", headers=headers, proxy=proxy_url) as response:
            return valid_resp(await to_json(response))

async def send_ping(socket, guid, options={}):
    payload = {
        'id': guid,
        'action': 'PING',
        **options,
    }
    try:
        if socket.state == CONNECTION_STATES['OPEN']:
            await socket.send(json.dumps(payload))
            logger.info(f"Sent PING with ID: {guid} and options: {options}")
    except Exception as e:
        logger.error(f"Error sending PING: {e}")

async def send_pong(socket, guid):
    payload = {
        'id': guid,
        'origin_action': 'PONG',
    }
    try:
        if socket.state == CONNECTION_STATES['OPEN']:
            await socket.send(json.dumps(payload))
            logger.info(f"Sent PONG with ID: {guid}")
    except Exception as e:
        logger.error(f"Error sending PONG: {e}")

async def connect_socket(token, proxy_url):
    global socket, retries, browser_id
    browser_id = uuidv4()

    if not browser_id:
        logger.warning("[INITIALIZE] Browser ID is blank. Cancelling connection...")
        browser_id = device_id
        sync_storage['browser_id'] = browser_id
        await connect_socket(token, proxy_url)
        return

    if socket and socket.state in [CONNECTION_STATES['OPEN'], CONNECTION_STATES['CONNECTING']]:
        logger.info("Socket already active or connecting")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://sandbox-api.nodepay.ai/api/auth/session", proxy=proxy_url) as response:
                logger.info(f"HTTP response status: {response.status}")
                async with connect(WEBSOCKET_URL, extra_headers={"Proxy-Authorization": proxy_url}) as websocket:
                    socket = websocket
                    local_storage['status_ws'] = CONNECTION_STATES['OPEN']
                    logger.info("WebSocket connection established")

                    while True:
                        try:
                            message = await socket.recv()
                            data = json.loads(message)
                            logger.info(f"Received message: {data}")

                            if data.get('action') == 'PONG':
                                await send_pong(socket, data['id'])
                                await asyncio.sleep(PING_INTERVAL)
                                await send_ping(socket, data['id'])
                            elif data.get('action') == 'AUTH':
                                res = await call_api_info(token, proxy_url)
                                if res['code'] == 0 and res['data']['uid']:
                                    local_storage['accountInfo'] = res['data']
                                    data_info = {
                                        'user_id': '1245399962284457984',
                                        'browser_id': browser_id,
                                        'user_agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                                        'timestamp': int(time.time()),
                                        'device_type': 'extension',
                                        'version': '1.0',
                                        'token': token,
                                        'origin_action': 'AUTH',
                                    }
                                    await send_ping(socket, data['id'], data_info)
                                    logger.info(f"Sent AUTH PING with data: {data_info}")

                        except ConnectionClosedError:
                            local_storage['status_ws'] = CONNECTION_STATES['CLOSED']
                            logger.warning("[close] Connection died")
                            await asyncio.sleep(RETRY_INTERVAL)
                            await connect_socket(token, proxy_url)
                            retries += 1
                            break

    except Exception as e:
        local_storage['status_ws'] = CONNECTION_STATES['CLOSED']    
        logger.error(f"Connection error: {e}")

async def check_permission(proxy_url):
    token = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjQ1Mzk5OTYyMjg0NDU3OTg0IiwiaWF0IjoxNzE3MDEzNTM1LCJleHAiOjE3MTgyMjMxMzV9.m6RY0SpXpiaWJRHoq1d0G8yYAE0IGhaqxh3AU9hlMQmJHFYMrCQWm2YXJczq6-gA0YVw-ThKJFrM8Klicv2cQw"
    if token:
        await connect_socket(token, proxy_url)
    else:
        logger.info("Redirecting to login...")

if __name__ == "__main__":
    logger.info("Starting script")
    # Update the proxy URL format to include the protocol scheme properly
    proxy_url = "http://customer-itzmiru-sessid-0094298613-sesstime-30:Miru9899091miru@pr.oxylabs.io:7777"
    asyncio.run(check_permission(proxy_url))
