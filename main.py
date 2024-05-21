import asyncio
import random
import ssl
import json
import time
import uuid
from loguru import logger
from keep_alive import keep_alive
from websockets_proxy import Proxy, proxy_connect
keep_alive()

async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(f"Device ID: {device_id}")
    custom_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    uri = "wss://proxy.wynd.network:4650/"
    server_hostname = "proxy.wynd.network"
    proxy = Proxy.from_url(socks5_proxy)

    while True:
        try:
            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                async def send_ping():
                    while True:
                        try:
                            send_message = json.dumps(
                                {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                            logger.debug(f"Sending PING: {send_message}")
                            await websocket.send(send_message)
                            await asyncio.sleep(20)
                        except Exception as e:
                            logger.error(f"Error in send_ping: {e}")
                            break

                # Start the ping task after connection is established
                asyncio.create_task(send_ping())

                async for response in websocket:
                    message = json.loads(response)
                    logger.info(f"Received message: {message}")
                    if message.get("action") == "AUTH":
                        auth_response = {
                            "id": message["id"],
                            "origin_action": "AUTH",
                            "result": {
                                "browser_id": device_id,
                                "user_id": user_id,
                                "user_agent": custom_headers['User-Agent'],
                                "timestamp": int(time.time()),
                                "device_type": "extension",
                                "version": "2.5.0"
                            }
                        }
                        logger.debug(f"Sending AUTH response: {auth_response}")
                        await websocket.send(json.dumps(auth_response))

                    elif message.get("action") == "PONG":
                        pong_response = {"id": message["id"], "origin_action": "PONG"}
                        logger.debug(f"Sending PONG response: {pong_response}")
                        await websocket.send(json.dumps(pong_response))
        except Exception as e:
            logger.error(f"Error: {e}")
            logger.error(f"Proxy: {socks5_proxy}")
            # Add a delay before retrying the connection
            await asyncio.sleep(5)

async def main():
    _user_id = '2fItNI22plTwaGamzYFVKou5OzC'
    with open('proxy.txt', 'r') as file:
        socks5_proxy_list = [line.strip() for line in file if line.strip()]
    await asyncio.gather(*(connect_to_wss(proxy, _user_id) for proxy in socks5_proxy_list))

if __name__ == '__main__':
    asyncio.run(main())