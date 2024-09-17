import asyncio
import aiohttp
import sys
import logging
import base64
import json
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiohttp import ClientSession, ClientTimeout
from aiohttp_retry import RetryClient, ExponentialRetry
from tqdm.asyncio import tqdm_asyncio
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    filename='missedblocks_async.log',
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s:%(message)s'
)

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logging.error("TELEGRAM_BOT_TOKEN not found in environment variables.")
    sys.exit("TELEGRAM_BOT_TOKEN not set. Please check your .env file.")

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Define your node's REST API base URLs and the base64 encoded validator address
BASE_URLS = [
    "https://REPLACE_WITH_YOUR_REST_API",  # Primary node's REST API endpoint
    "https://REPLACE_WITH_YOUR_REST_API"  # Secondary node's REST API endpoint
]
VALIDATOR_ADDRESS_BASE64 = "REPLACE_WITH_YOUR_BASE64_ADDRESS"

# Configuration
TIMEOUT = 10  # seconds
MAX_CONCURRENT_REQUESTS_DEFAULT = 100  # Default number of concurrent requests
RETRIES = 3  # Number of retries for failed requests
BACKOFF_FACTOR = 0.5  # Exponential backoff factor
BLOCK_RANGE_OPTIONS = {
    '100': 100,
    '500': 500,
    '1000': 1000,
    '2000': 2000,
    '5000': 5000,
    '10000': 10000,
    '25000': 25000,
    '50000': 50000,
    '100000': 100000
}
MISSED_BLOCKS_LIMIT = 100  # Maximum number of missed blocks to record
ALERTS_FILE = '/root/nodescan/alert_chat_ids.json'  # File to store alert chat IDs
ALERT_CHAT_IDS = set()  # To store multiple chat IDs for alerts

AUTHORIZED_USERS = set()  # Populate with authorized Telegram user IDs if restricting access

# Load alert chat IDs from file
def load_alert_chat_ids():
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f:
                data = json.load(f)
                return set(data)
        except Exception as e:
            logging.error(f"Error loading alert chat IDs: {e}")
    return set()

# Save alert chat IDs to file
def save_alert_chat_ids():
    try:
        with open(ALERTS_FILE, 'w') as f:
            json.dump(list(ALERT_CHAT_IDS), f)
    except Exception as e:
        logging.error(f"Error saving alert chat IDs: {e}")

ALERT_CHAT_IDS = load_alert_chat_ids()

# Function to check if a user is authorized (optional)
def is_authorized(user_id):
    return not AUTHORIZED_USERS or user_id in AUTHORIZED_USERS

async def create_retry_session():
    """Create an aiohttp session with retry strategy."""
    retry_options = ExponentialRetry(
        attempts=RETRIES,
        start_timeout=BACKOFF_FACTOR,
        statuses={500, 502, 503, 504},
        exceptions={aiohttp.ClientError},
        factor=2,
        max_timeout=TIMEOUT
    )
    session_timeout = ClientTimeout(total=TIMEOUT)
    retry_client = RetryClient(
        raise_for_status=False,
        retry_options=retry_options,
        client_session=ClientSession(timeout=session_timeout)
    )
    return retry_client

async def get_latest_block_height(sessions):
    """Fetch the latest block height from the blockchain using the available base URLs."""
    for base_url, session in sessions.items():
        try:
            url = f"{base_url}/cosmos/base/tendermint/v1beta1/blocks/latest"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return int(data["block"]["header"]["height"])
                else:
                    logging.error(f"Error fetching the latest block height from {base_url}: Status Code {response.status}")
        except Exception as e:
            logging.error(f"Exception fetching latest block height from {base_url}: {e}")
    return None

async def check_validator_signed_block(session, base_url, block_height):
    """Check if the validator signed a specific block using the provided session and base URL."""
    try:
        url = f"{base_url}/cosmos/base/tendermint/v1beta1/blocks/{block_height}"
        async with session.get(url) as response:
            if response.status == 200:
                block_info = await response.json()
                signatures = block_info.get('block', {}).get('last_commit', {}).get('signatures', [])

                # Check if the validator's base64 address is in the signatures
                for signature in signatures:
                    if signature.get('validator_address') == VALIDATOR_ADDRESS_BASE64:
                        return True
                return False
            else:
                logging.error(f"Error fetching block {block_height} from {base_url}: Status Code {response.status}")
                return None
    except Exception as e:
        logging.error(f"Exception fetching block {block_height} from {base_url}: {e}")
        return None

async def process_block(block_height, sessions):
    """Process a single block by checking if the validator signed it."""
    for base_url, session in sessions.items():
        result = await check_validator_signed_block(session, base_url, block_height)
        if result is not None:
            return result
    return None  # All URLs failed for this block

async def fetch_blocks(count):
    """Fetch the last `count` blocks and return their statuses."""
    sessions = {}
    for url in BASE_URLS:
        sessions[url] = await create_retry_session()

    latest_block_height = await get_latest_block_height(sessions)

    if latest_block_height is None:
        logging.error("Failed to get the latest block height from all provided URLs.")
        await asyncio.gather(*[s.close() for s in sessions.values()])
        return None

    start_block = max(1, latest_block_height - count + 1)
    end_block = latest_block_height

    block_heights = range(start_block, end_block + 1)

    # Adjust concurrency based on the number of blocks
    if count <= 1000:
        max_concurrent = 1000
    elif count <= 5000:
        max_concurrent = 500
    elif count <= 10000:
        max_concurrent = 300
    elif count <= 25000:
        max_concurrent = 200
    elif count <= 50000:
        max_concurrent = 100
    else:
        max_concurrent = 50  # For 100k blocks

    semaphore = asyncio.Semaphore(max_concurrent)

    signed_count = 0
    missed_count = 0
    missed_blocks = []

    async def semaphore_wrapped_process(block_height):
        async with semaphore:
            return await process_block(block_height, sessions), block_height

    tasks = [semaphore_wrapped_process(bh) for bh in block_heights]

    # Decide whether to show progress bar based on count
    show_progress = count <= 10000  # Show progress for up to 10k blocks

    if show_progress:
        for future in tqdm_asyncio.as_completed(tasks, total=len(tasks), desc=f"Processing Last {count} Blocks"):
            result, bh = await future
            if result is True:
                signed_count += 1
            elif result is False:
                if len(missed_blocks) < MISSED_BLOCKS_LIMIT:
                    missed_count += 1
                    missed_blocks.append(f"Block {bh}")
                else:
                    missed_count += 1  # Still count the missed block but don't record its detail
            # Ignore None results (failed to fetch block)
    else:
        # Process without progress bar for large block ranges
        for future in asyncio.as_completed(tasks):
            result, bh = await future
            if result is True:
                signed_count += 1
            elif result is False:
                if len(missed_blocks) < MISSED_BLOCKS_LIMIT:
                    missed_count += 1
                    missed_blocks.append(f"Block {bh}")
                else:
                    missed_count += 1  # Still count the missed block but don't record its detail
            # Optionally, you can implement periodic logging or notifications here

    await asyncio.gather(*[s.close() for s in sessions.values()])

    return {
        "latest_block": latest_block_height,
        "start_block": start_block,
        "end_block": end_block,
        "signed": signed_count,
        "missed": missed_count,
        "missed_blocks": missed_blocks
    }

@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    """Send a welcome message with available commands."""
    welcome_text = (
        "👋 Hello! I'm your Validator Node Monitor Bot.\n\n"
        "📋 **Available Commands:**\n"
        "/last100 - Fetch the last 100 blocks\n"
        "/last500 - Fetch the last 500 blocks\n"
        "/last1000 - Fetch the last 1,000 blocks\n"
        "/last2000 - Fetch the last 2,000 blocks\n"
        "/last5000 - Fetch the last 5,000 blocks\n"
        "/last10000 - Fetch the last 10,000 blocks\n"
        "/last25000 - Fetch the last 25,000 blocks\n"
        "/last50000 - Fetch the last 50,000 blocks\n"
        "/last100000 - Fetch the last 100,000 blocks\n"
        "/status - Check the current status of your validator node\n"
        "/set_alert - Register this chat to receive missed block alerts\n"
        "/unset_alert - Unregister this chat from receiving alerts\n"
    )
    await message.reply(welcome_text, parse_mode='Markdown')

@dp.message_handler(commands=['last100', 'last500', 'last1000', 'last2000', 'last5000', 'last10000', 'last25000', 'last50000', 'last100000'])
async def fetch_last_blocks(message: types.Message):
    """Fetch the last X blocks based on the command."""
    cmd = message.get_command().lstrip('/')
    count_key = cmd.replace('last', '')
    count = BLOCK_RANGE_OPTIONS.get(count_key, 100)
    await message.reply(f"🔍 Fetching the last {count} blocks. Please wait...")

    block_data = await fetch_blocks(count)
    if block_data:
        response = (
            f"📊 **Last {count} Blocks Status:**\n"
            f"🆙 Latest Block: {block_data['latest_block']}\n"
            f"🟢 Signed Blocks: {block_data['signed']}\n"
            f"🔴 Missed Blocks: {block_data['missed']}\n"
        )
        if block_data['missed_blocks']:
            missed_blocks_str = "\n".join(block_data['missed_blocks'])
            response += f"\n**Missed Blocks (Showing up to {MISSED_BLOCKS_LIMIT}):**\n{missed_blocks_str}"
        await message.reply(response, parse_mode='Markdown')
    else:
        await message.reply("❌ Failed to fetch block data. Please try again later.")

@dp.message_handler(commands=['status'])
async def check_status(message: types.Message):
    """Check the current status of the validator node."""
    await message.reply("🔄 Checking the current status. Please wait...")

    block_data = await fetch_blocks(1)
    if block_data:
        latest_block = block_data['latest_block']
        # Optionally, add more detailed status information here
        await message.reply(f"✅ Validator node is active. Latest block: {latest_block}")
    else:
        await message.reply("❌ Failed to retrieve the status of the validator node.")

@dp.message_handler(commands=['set_alert'])
async def set_alert(message: types.Message):
    """Set the chat ID for receiving alerts."""
    if AUTHORIZED_USERS and message.from_user.id not in AUTHORIZED_USERS:
        await message.reply("❌ You are not authorized to use this command.")
        return
    ALERT_CHAT_IDS.add(message.chat.id)
    save_alert_chat_ids()
    await message.reply("✅ This chat will now receive alerts for missed blocks.")

@dp.message_handler(commands=['unset_alert'])
async def unset_alert(message: types.Message):
    """Unset the chat ID for receiving alerts."""
    if AUTHORIZED_USERS and message.from_user.id not in AUTHORIZED_USERS:
        await message.reply("❌ You are not authorized to use this command.")
        return
    if message.chat.id in ALERT_CHAT_IDS:
        ALERT_CHAT_IDS.remove(message.chat.id)
        save_alert_chat_ids()
        await message.reply("❌ This chat will no longer receive alerts.")
    else:
        await message.reply("ℹ️ This chat was not registered for alerts.")

async def monitor_blocks():
    """Background task to monitor blocks and send alerts on missed blocks."""
    global last_checked_block
    alert_interval = 30  # seconds between checks

    sessions = {}
    for url in BASE_URLS:
        sessions[url] = await create_retry_session()

    while True:
        try:
            latest_block_height = await get_latest_block_height(sessions)
            if latest_block_height is None:
                logging.error("Failed to get the latest block height.")
                await asyncio.sleep(alert_interval)
                continue

            if last_checked_block is None:
                last_checked_block = latest_block_height
                await asyncio.sleep(alert_interval)
                continue

            # Check for new blocks since last check
            if latest_block_height > last_checked_block:
                new_blocks = range(last_checked_block + 1, latest_block_height + 1)
                semaphore = asyncio.Semaphore(100)  # Limit concurrency for monitoring

                async def semaphore_wrapped_monitor(block_height):
                    async with semaphore:
                        return await process_block(block_height, sessions), block_height

                monitor_tasks = [semaphore_wrapped_monitor(bh) for bh in new_blocks]

                # Process new blocks without progress bar
                for future in asyncio.as_completed(monitor_tasks):
                    result, bh = await future
                    if result is False:
                        # Missed block detected
                        alert_message = f"⚠️ **Missed Block Detected!**\nBlock Height: {bh}"
                        for chat_id in ALERT_CHAT_IDS:
                            try:
                                await bot.send_message(chat_id, alert_message, parse_mode='Markdown')
                            except Exception as e:
                                logging.error(f"Failed to send alert to chat {chat_id}: {e}")
                        logging.info(f"Missed block detected at height {bh}")
                last_checked_block = latest_block_height

            await asyncio.sleep(alert_interval)
        except Exception as e:
            logging.error(f"Exception in monitor_blocks: {e}")
            await asyncio.sleep(alert_interval)

    # Close all sessions on exit
    await asyncio.gather(*[s.close() for s in sessions.values()])

async def on_startup(dp):
    """Actions to perform on bot startup."""
    asyncio.create_task(monitor_blocks())
    logging.info("Bot started and monitoring blocks.")

if __name__ == "__main__":
    try:
        executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually.")
