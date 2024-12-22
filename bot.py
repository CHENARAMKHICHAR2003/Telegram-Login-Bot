import asyncio
import json
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram import Update
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError

# Telegram API credentials
api_id = "24894984"
api_hash = "4956e23833905463efb588eb806f9804"
phone = "+91...."  # Apna phone number daalein

client = TelegramClient('session_name', api_id, api_hash)

# Ensure asyncio loop is created
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Track login status
user_logged_in = False
user_history = {}

# /start command
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "Hey User! 👋\n"
        "Welcome to the Telegram Info Bot.\n\n"
        "Commands you can use:\n"
        "/login - Login to your Telegram account\n"
        "/help - Get more info about bot features 🎉\n\n"
        "Note: \n"
        "I can help you fetch user IDs and mobile numbers after logging in. "
        "You can also check your own information after successful login."
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
    global user_logged_in
    
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
    update.message.reply_text(f"✅ Login successful! Welcome {me.first_name} ({me.username})\n\n"
                              f"Your ID: {me.id}\nYour Phone: {me.phone}")
    user_logged_in = True

    # Save the user's username to history
    user_history[update.effective_user.id] = me.username

# /login command (dispatcher to call async function)
def login(update: Update, context: CallbackContext) -> None:
    loop.run_until_complete(async_login(update, context))

# Handle forwarded messages and retrieve username history
def handle_forwarded_message(update: Update, context: CallbackContext) -> None:
    if not user_logged_in:
        update.message.reply_text(
            "🚫 Pehle login karein! 🔑\n\n"
            "Aapko /login command ka use karke apne Telegram account se connect karna hoga. "
            "Uske baad hi main aapki madad kar sakta hoon. 😊"
        )
        return

    # If message is forwarded, extract sender's info
    if update.message.forward_from:
        forwarded_user = update.message.forward_from
        sender_id = forwarded_user.id
        sender_username = forwarded_user.username if forwarded_user.username else "No username"

        # Check if the sender's history is available
        history = user_history.get(sender_id, None)

        if history:
            update.message.reply_text(f"User {sender_username} has previously logged in with the username: {history}")
        else:
            update.message.reply_text(f"User {sender_username} does not have a previous login history.")

# Unauthorized message handler (before login)
def handle_unauthorized_messages(update: Update, context: CallbackContext) -> None:
    if not user_logged_in:
        update.message.reply_text(
            "🚫 Pehle login karein! 🔑\n\n"
            "Aapko /login command ka use karke apne Telegram account se connect karna hoga. "
            "Uske baad hi main aapki madad kar sakta hoon. 😊"
        )
    else:
        update.message.reply_text(
            "❓ Main samajh nahi paya. Kripya sahi command ka istemal karein.\n\n"
            "Available Commands:\n"
            "/start - Bot ko start karein\n"
            "/help - Madad ke liye\n"
            "/login - Apne Telegram se connect karein"
        )

# Main function to run the bot
def main():
    TOKEN = "YOUR_BOT_TOKEN"
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    
    # Command Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("login", login))
    
    # Handle messages that are not commands
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_unauthorized_messages))
    
    # Handle forwarded messages to track username history
    dp.add_handler(MessageHandler(Filters.forwarded, handle_forwarded_message))
    
    # Start Bot Polling
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
