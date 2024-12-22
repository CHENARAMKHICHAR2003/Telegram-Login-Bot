import asyncio
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram import Update
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError

# Telegram API credentials
api_id = "24894984"
api_hash = "4956e23833905463efb588eb806f9804"
phone = "+91....."

client = TelegramClient('session_name', api_id, api_hash)

# Ensure asyncio loop is created
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# /start command
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "Hey User! 👋\n"
        "Welcome to the Telegram Info Bot.\n\n"
        "Commands you can use:\n"
        "/login - Login to your Telegram account\n"
        "/help - Get more info about this bot"
    )

# /help command
def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "ℹ️ This bot allows you to access some of your Telegram information.\n\n"
        "⚙️ Available Commands:\n"
        "/start - Start the bot\n"
        "/login - Login to your Telegram account\n"
        "/help - Show this message"
    )

# Async login function
async def async_login(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    await client.start()
    
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        update.message.reply_text("🛡️ A login code has been sent to your Telegram. Please enter it below:")

        try:
            code = input("Enter the code (OTP): ")
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("🔐 Enter your 2FA password: ")
            await client.sign_in(password=password)
    
    me = await client.get_me()
    update.message.reply_text(f"✅ Login successful! Welcome {me.first_name} ({me.username})")

# /login command (dispatcher to call async function)
def login(update: Update, context: CallbackContext) -> None:
    loop.run_until_complete(async_login(update, context))

# Main function to run the bot
def main():
    TOKEN = "YOUR_BOT_TOKEN"
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    
    # Command Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("login", login))
    
    # Start Bot Polling
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
