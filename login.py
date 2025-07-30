"""
Prints telegram session string key and shows all chats
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
from telethon.tl.types import Chat, Channel, User
import asyncio

async def main():
    # Create TelegramClient with or without proxy
    if proxy_config:
        client = TelegramClient(
            session=StringSession(), api_id=int(API_ID), api_hash=API_HASH, proxy=proxy_config
        )
    else:
        client = TelegramClient(
            session=StringSession(), api_id=int(API_ID), api_hash=API_HASH
        )
    
    async with client:
        # Get session string
        session_string = client.session.save()
        print("Session string: ", session_string)
        print("\n" + "="*50)
        print("LIST OF ALL CHATS:")
        print("="*50)
        
        # Get all dialogs
        dialogs = await client.get_dialogs()
        
        # Group chats by types
        private_chats = []
        groups = []
        channels = []
        
        for dialog in dialogs:
            entity = dialog.entity
            
            if isinstance(entity, User):
                if not entity.bot:
                    private_chats.append({
                        'id': entity.id,
                        'title': f"{entity.first_name or ''} {entity.last_name or ''}".strip(),
                        'username': entity.username
                    })
            elif isinstance(entity, Chat):
                groups.append({
                    'id': entity.id,
                    'title': entity.title,
                    'members_count': getattr(entity, 'participants_count', 'N/A')
                })
            elif isinstance(entity, Channel):
                if entity.broadcast:
                    channels.append({
                        'id': entity.id,
                        'title': entity.title,
                        'username': entity.username,
                        'subscribers': getattr(entity, 'participants_count', 'N/A')
                    })
                else:
                    groups.append({
                        'id': entity.id,
                        'title': entity.title,
                        'username': entity.username,
                        'members_count': getattr(entity, 'participants_count', 'N/A')
                    })
        
        # Display private chats
        if private_chats:
            print(f"\n📱 PRIVATE CHATS ({len(private_chats)}):")
            print("-" * 50)
            chat_names = []
            for chat in private_chats:
                username_info = f" (@{chat['username']})" if chat['username'] else ""
                chat_names.append(f"{chat['title']}{username_info} (ID: {chat['id']})")
            print(", ".join(chat_names))
        
        # Display groups
        if groups:
            print(f"\n👥 GROUPS ({len(groups)}):")
            print("-" * 50)
            group_names = []
            for group in groups:
                username_info = f" (@{group['username']})" if group.get('username') else ""
                group_names.append(f"{group['title']}{username_info} (ID: {group['id']}, Members: {group['members_count']})")
            print(", ".join(group_names))
        
        # Display channels
        if channels:
            print(f"\n📢 CHANNELS ({len(channels)}):")
            print("-" * 50)
            channel_names = []
            for channel in channels:
                username_info = f" (@{channel['username']})" if channel['username'] else ""
                channel_names.append(f"{channel['title']}{username_info} (ID: {channel['id']}, Subscribers: {channel['subscribers']})")
            print(", ".join(channel_names))
        
        print("\n" + "="*50)
        print(f"TOTAL CHATS: {len(dialogs)}")
        print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
