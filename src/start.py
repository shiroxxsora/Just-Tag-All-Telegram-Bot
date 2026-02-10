import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from tagallbot.app import start

if __name__ == "__main__":
    asyncio.run(start())