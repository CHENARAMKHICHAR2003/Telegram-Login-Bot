import asyncio
import logging
import os
import random
import string
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, ConversationHandler, Application
from telegram.ext import filters
from pyrogram import Client
from pyrogram.errors import ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired
from telethon.errors import SessionPasswordNeededError  # Correct import for session password error
from config import API_ID, API_HASH, BOT_TOKEN  # Import credentials from config.py

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

    # Return whether any files were deleted
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

# Define the /logout command to clear session data
async def clear_db(client, message):
    user_id = message.chat.id
    files_deleted = await delete_session_files(user_id)

    if files_deleted:
        await message.reply("✅ Your session data and files have been cleared from memory and disk.")
    else:
        await message.reply("⚠️ You are not logged in, no session data found.")

# Define the /login command (using pyrogram Client)
async def generate_session(update: Update, context: CallbackContext) -> int:
    user_id = update.message.chat.id
    context.user_data['user_id'] = user_id  # Store user_id in user_data to track login

    # Ask user for phone number
    await update.message.reply("Please enter your phone number along with the country code (e.g., +19876543210).")
    return 1  # Transition to the next state (state 1)

# Handle phone number input
async def phone_number(update: Update, context: CallbackContext) -> int:
    user_id = context.user_data['user_id']
    phone_number = update.message.text

    # Create pyrogram client for login
    client = Client(f"session_{user_id}", API_ID, API_HASH)
    
    try:
        await update.message.reply("📲 Sending OTP...")
        await client.connect()
        code = await client.send_code(phone_number)
    except (ApiIdInvalid, PhoneNumberInvalid) as e:
        await update.message.reply(f"❌ Error: {e}")
        return ConversationHandler.END

    # Ask user for OTP
    await update.message.reply("Please enter the OTP sent to your Telegram account.")
    context.user_data['phone_code_hash'] = code.phone_code_hash  # Store phone_code_hash for verification
    return 2  # Transition to the next state (state 2)

# Handle OTP input
async def otp_code(update: Update, context: CallbackContext) -> int:
    user_id = context.user_data['user_id']
    phone_code = update.message.text.replace(" ", "")
    phone_code_hash = context.user_data['phone_code_hash']

    client = Client(f"session_{user_id}", API_ID, API_HASH)
    
    try:
        await client.sign_in(update.message.text, phone_code_hash, phone_code)
    except (PhoneCodeInvalid, PhoneCodeExpired) as e:
        await update.message.reply(f"❌ OTP Error: {e}")
        return ConversationHandler.END
    except SessionPasswordNeededError:
        # Ask for password if 2FA is enabled
        await update.message.reply("Your account has two-step verification enabled. Please enter your password.")
        return 3  # Transition to password state

    # If login successful, save the session string
    string_session = await client.export_session_string()
    save_session_string(user_id, string_session)
    await client.disconnect()
    
    await update.message.reply("✅ Login successful!")
    return ConversationHandler.END  # End conversation

# Handle password input for two-step verification
async def password_input(update: Update, context: CallbackContext) -> int:
    user_id = context.user_data['user_id']
    password = update.message.text

    client = Client(f"session_{user_id}", API_ID, API_HASH)
    
    try:
        await client.check_password(password=password)
    except Exception as e:
        await update.message.reply(f"❌ Invalid password: {e}")
        return ConversationHandler.END
    
    # If password is correct, export the session string
    string_session = await client.export_session_string()
    save_session_string(user_id, string_session)
    await client.disconnect()
    
    await update.message.reply("✅ Login successful with two-step verification!")
    return ConversationHandler.END  # End conversation

# Define the start and help commands for the bot
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

def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "ℹ️ This bot allows you to access some of your Telegram information.\n\n"
        "⚙️ Available Commands:\n"
        "/start - Start the bot\n"
        "/login - Login to your Telegram account\n"
        "/help - Show this message"
    )

# Unauthorized message handler (before login)
def handle_unauthorized_messages(update: Update, context: CallbackContext) -> None:
    if 'user_id' not in context.user_data:
        update.message.reply_text(
            "🚫 Aapko pehle login karna hoga! 🔑\n\n"
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

# Conversation handler
def conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler('login', generate_session)],  # /login command triggers this conversation
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number)],  # Step 1: phone number
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, otp_code)],  # Step 2: OTP
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, password_input)],  # Step 3: Password (if 2FA)
        },
        fallbacks=[CommandHandler('help', help_command)],
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
    application.run_polling()

if __name__ == "__main__":
    main()  # Ensure this function call is properly indented
