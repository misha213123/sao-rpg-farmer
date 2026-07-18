from __future__ import annotations

import asyncio
import getpass

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = int(input("API_ID: ").strip())
    api_hash = getpass.getpass("API_HASH: ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()

    print("\nSTRING_SESSION (сохраните как секрет):\n")
    print(client.session.save())
    print("\nНе публикуйте эту строку и не добавляйте её в GitHub.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
