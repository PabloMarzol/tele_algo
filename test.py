from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram import Update

async def get_chat_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_type = chat.type
    chat_id = chat.id
    chat_title = chat.title
    chat_username = chat.username
    
    print(f"Chat Type: {chat_type}")
    print(f"Chat ID: {chat_id}")
    print(f"Chat Title: {chat_title}")
    
    if chat_username:
        print(f"Chat Username: @{chat_username}")
    else:
        print("Chat Username: None")
    
    print("-" * 30)

if __name__ == '__main__':
    # Replace with your bot token
    TOKEN = "7532055530:AAHC8xeMZBddUDNmhvlmmzgyGD8x59ft7wE"

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, get_chat_info))

    print("✅ Bot is running... Send a message in the group/channel where the bot is added.")
    app.run_polling()