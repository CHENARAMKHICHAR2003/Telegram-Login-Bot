import asyncio
import logging
import os
import random
import string
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from pyrogram import Client, filters
from pyrogram.errors import ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired, SessionPasswordNeededError
from devgagan.core.mongo import db
from config import API_ID, API_HASH, BOT_TOKEN  # Import credentials from config.py

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define conversation states
PHONE = 1

# Generate random session name
def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Delete session files from disk
async def delete_session_files(user_id):
    session_file = f"session_{user_id}.session"
    memory_file = f"session_{user_id}.session-journal"
    
    # Delete files if they exist
    if os.path.exists(session_file):
        os.remove(session_file)
    if os.path.exists(memory_file):
        os.remove(memory_file)

    # Remove from database if files were deleted
    if os.path.exists(session_file) or os.path.exists(memory_file):
        await db.delete_session(user_id)
        return True
    return False

# Clear session data and files when user logs out
@app.on_message(filters.command("logout"))
async def clear_db(client, message):
    user_id = message.chat.id
    files_deleted = await delete_session_files(user_id)

    if files_deleted:
        await message.reply("✅ Your session data and files have been cleared from memory and disk.")
    else:
        await message.reply("⚠️ You are not logged in, no session data found.")

# Handle login command
@app.on_message(filters.command("login"))
async def login(client, message):
    user_id = message.chat.id
    
    # Request phone number from user
    number = await client.ask(user_id, 'Please enter your phone number with country code (e.g., +19876543210)', filters=filters.text)   
    phone_number = number.text.strip()
    
    try:
        await message.reply("📲 Sending OTP...")
        client_session = Client(f"session_{user_id}", API_ID, API_HASH)
        
        await client_session.connect()
    except Exception as e:
        await message.reply(f"❌ Failed to send OTP: {e}. Please wait and try again later.")
        return

    try:
        code = await client_session.send_code(phone_number)
    except ApiIdInvalid:
        await message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
        return
    except PhoneNumberInvalid:
        await message.reply('❌ Invalid phone number format. Please restart the session.')
        return

    # Ask user for OTP and validate
    try:
        otp_code = await client.ask(user_id, "Please check for an OTP in your official Telegram account. Enter it as: 12345", filters=filters.text, timeout=600)
        phone_code = otp_code.text.replace(" ", "")
        await client_session.sign_in(phone_number, code.phone_code_hash, phone_code)
    except PhoneCodeInvalid:
        await message.reply('❌ Invalid OTP. Please restart the session.')
        return
    except PhoneCodeExpired:
        await message.reply('❌ OTP expired. Please restart the session.')
        return

    # Handle two-step verification if enabled
    try:
        if await client_session.is_password_needed():
            password = await client.ask(user_id, 'Your account has two-step verification enabled. Please enter your password.', filters=filters.text, timeout=300)
            await client_session.check_password(password.text)
    except SessionPasswordNeededError:
        await message.reply('❌ Invalid password. Please restart the session.')
        return

    # Export session string to database and disconnect
    string_session = await client_session.export_session_string()
    await db.set_session(user_id, string_session)
    await client_session.disconnect()
    await otp_code.reply("✅ Login successful!")

# Start command: Provide welcome message and instructions
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "Hey User! 👋\n"
        "Welcome to the Telegram Info Bot.\n\n"
        "Commands you can use:\n"
        "/login - Login to your Telegram account\n"
        "/help - Get more info about bot features 🎉\n\n"
        "Note: After logging in, you can fetch your Telegram ID, username, and more!"
    )

# Help command: Display bot instructions
def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "ℹ️ This bot allows you to access some of your Telegram information.\n\n"
        "⚙️ Available Commands:\n"
        "/start - Start the bot\n"
        "/login - Login to your Telegram account\n"
        "/help - Show this message"
    )

# Request phone number from user during login
def phone_number(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Please enter your phone number in the following format:\n+91XXXXXXXXXX")
    return PHONE

# Handle login
async def async_login(update: Update, context: CallbackContext, phone_number: str) -> None:
    global user_logged_in

    phone = phone_number.strip()
    
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

# Conversation handler for login
def conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler('login', login)],
        states={
            PHONE: [MessageHandler(Filters.text & ~Filters.command, phone_number)],
        },
        fallbacks=[]
    )

# Unauthorized message handler
def handle_unauthorized_messages(update: Update, context: CallbackContext) -> None:
    if not user_logged_in:
        update.message.reply_text(
            "🚫 Please log in first! 🔑\n\n"
            "Use the /login command to connect with your Telegram account."
        )
    else:
        update.message.reply_text(
            "❓ I couldn't understand your message. Please use the correct command.\n\n"
            "Available Commands:\n"
            "/start - Start the bot\n"
            "/help - Get help\n"
            "/login - Login to your Telegram account"
        )

# Main function to run the bot
def main():
    updater = Updater(BOT_TOKEN)  # Use the bot token from config.py
    dp = updater.dispatcher

    # Command Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(conversation_handler())  # Handle login conversation
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_unauthorized_messages))  # Unauthorized messages

    # Start polling and keep the bot running
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
