from aiogram.utils.executor import start_polling
from bot import dp, schedule_jobs, setup_bot_commands
import asyncio

if __name__ == '__main__':
    schedule_jobs()
    asyncio.get_event_loop().run_until_complete(setup_bot_commands())
    start_polling(dp, skip_updates=True)
