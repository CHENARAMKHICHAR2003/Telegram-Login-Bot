import random
import time
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext
import logging

# Enable logging to help track errors
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Temporary data storage for the session and OTP
user_sessions = {}  # Stores user session data
otp_storage = {}    # Stores generated OTPs
user_pins = {}      # Stores PINs for second verification

# List of authorized users by their Telegram user IDs (You can manually add IDs)
AUTHORIZED_USERS = {123456789, 987654321}  # Example user IDs

def start(update: Update, context: CallbackContext) -> None:
    """Handle /start command."""
    update.message.reply_text(
        "*Welcome to the Power Bot! 💥*\n\n"
        "With this bot, you can access powerful capabilities like:\n\n"
        "1. Retrieve user IDs of anyone who interacts with the bot. 🕵️‍♂️\n"
        "2. Retrieve phone numbers (if shared by users). 📞\n\n"
        "*But there's a catch...*\n"
        "_You need to log in first to unlock my full power._ 🔐\n\n"
        "Use `/login` to begin the secure login process. Once logged in, you'll have access to my full range of features!\n\n"
        "*Ready to experience the power?* 💪",
        parse_mode='Markdown'
    )

def help_command(update: Update, context: CallbackContext) -> None:
    """Handle /help command."""
    update.message.reply_text(
        "*Here are the available commands:* 😎\n\n"
        "1. `/start` - Start the bot and get a welcome message.\n"
        "2. `/login` - Begin the secure login process.\n"
        "3. `/logout` - Log out and end the session.\n\n"
        "_Use the commands above to navigate the bot!_ 🧭\n\n"
        "*Note:* You must log in to access most commands. 🔒",
        parse_mode='Markdown'
    )

def logout(update: Update, context: CallbackContext) -> None:
    """Handle /logout command."""
    user_id = update.effective_user.id

    if user_id in user_sessions:
        del user_sessions[user_id]
        update.message.reply_text(
            "*You have been logged out successfully!* 🚪👋\n\n"
            "To start a new session, use the `/login` command.",
            parse_mode='Markdown'
        )
    else:
        update.message.reply_text(
            "You're not logged in. Use `/login` to start the process.",
            parse_mode='Markdown'
        )

def login(update: Update, context: CallbackContext) -> None:
    """Handle /login command."""
    user_id = update.effective_user.id
    
    # Check if the user is authorized
    if user_id not in AUTHORIZED_USERS:
        update.message.reply_text(
            "*You are not authorized to use this bot.* 🚫\n"
            "Please contact the administrator to gain access.",
            parse_mode='Markdown'
        )
        return
    
    # Initiate the login process
    user_sessions[user_id] = {"step": 1}  # Step 1: Enter phone number
    update.message.reply_text(
        "*Step 1:* 📞 Please enter your phone number (e.g., +1234567890):",
        parse_mode='Markdown'
    )

def verify_phone_number(update: Update, context: CallbackContext) -> None:
    """Verify the phone number entered by the user."""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions or user_sessions[user_id]["step"] != 1:
        return  # Ignore if user is not in the login process

    # Validate phone number format
    phone_number = update.message.text.strip()

    if phone_number.startswith('+') and len(phone_number) > 10:  # Basic validation
        # Store phone number and generate OTP
        otp = random.randint(1000, 9999)
        otp_storage[user_id] = otp
        user_sessions[user_id]["phone"] = phone_number
        user_sessions[user_id]["step"] = 2  # Move to next step (OTP)

        # Send OTP to user
        update.message.reply_text(
            f"✅ OTP has been sent to your number: *{phone_number}*.\n\n"
            "*Step 2:* 🔒 Please enter the OTP to continue.",
            parse_mode='Markdown'
        )

    else:
        update.message.reply_text(
            "*Invalid phone number.* 🚫\n"
            "Please enter a valid phone number (e.g., +1234567890):",
            parse_mode='Markdown'
        )

def verify_otp(update: Update, context: CallbackContext) -> None:
    """Verify the OTP entered by the user."""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions or user_sessions[user_id]["step"] != 2:
        return  # Ignore if user is not in the OTP step

    entered_otp = update.message.text.strip()

    # Check if OTP matches
    if otp_storage.get(user_id) == int(entered_otp):
        user_sessions[user_id]["step"] = 3  # Move to next step (PIN)
        update.message.reply_text(
            "🔑 OTP verified successfully! Now, *enter your PIN* to complete the login process.",
            parse_mode='Markdown'
        )
    else:
        update.message.reply_text(
            "*Invalid OTP.* ❌\nPlease try again.",
            parse_mode='Markdown'
        )

def verify_pin(update: Update, context: CallbackContext) -> None:
    """Verify the PIN entered by the user."""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions or user_sessions[user_id]["step"] != 3:
        return  # Ignore if user is not in the PIN step

    pin = update.message.text.strip()
    
    # Check if PIN is correct (You can set a fixed PIN or generate it dynamically)
    correct_pin = "1234"  # This can be dynamic or set by the user

    if pin == correct_pin:
        user_sessions[user_id]["step"] = 4  # User is successfully logged in
        update.message.reply_text(
            f"🎉 *Login successful!* Welcome, {update.effective_user.first_name}. 🙌\n"
            "You're now logged in and can start using the bot.",
            parse_mode='Markdown'
        )
    else:
        update.message.reply_text(
            "*Invalid PIN.* ❌\nPlease try again.",
            parse_mode='Markdown'
        )

def cancel_login(update: Update, context: CallbackContext) -> None:
    """Cancel the login process and reset user session."""
    user_id = update.effective_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    update.message.reply_text(
        "*Login process cancelled.* 🚫\n"
        "To restart the process, use `/login`.",
        parse_mode='Markdown'
    )

def main():
    """Start the bot and set up handlers."""
    # Replace 'YOUR_BOT_TOKEN' with your actual Telegram bot token
    updater = Updater("YOUR_BOT_TOKEN", use_context=True)
    
    dp = updater.dispatcher

    # Commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("logout", logout))
    dp.add_handler(CommandHandler("login", login))
    dp.add_handler(CommandHandler("cancel", cancel_login))  # Cancel login command

    # Messages (Handle phone number, OTP, PIN)
    dp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, verify_phone_number))
    dp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, verify_otp))
    dp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, verify_pin))

    # Start polling
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
