"""
Prints telegram session string key
"""
try:
    from config import API_HASH, API_ID, build_proxy_config
    proxy_config = build_proxy_config()
except Exception:
    print("Failed load API_HASH and API_ID from .env")
    API_HASH = input("Input telegram API_HASH: ")
    API_ID = input("Input telegram API_ID: ")
    proxy_config = None

from telethon import TelegramClient
from telethon.sessions import StringSession

with TelegramClient(
    session=StringSession(), api_id=API_ID, api_hash=API_HASH, proxy=proxy_config
) as client:
    print("Session string: ", client.session.save())
