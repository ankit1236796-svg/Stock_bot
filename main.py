import os
import json
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue

# ============ SETTINGS ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
CHECK_INTERVAL = 300  # 5 minutes
PRODUCTS_FILE = "products.json"
# ==================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

def load_products():
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_products(products):
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=2)

def check_amazon_stock(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        title = soup.find("span", {"id": "productTitle"})
        name = title.get_text(strip=True)[:60] if title else "Product"

        availability = soup.find("div", {"id": "availability"})
        if availability:
            text = availability.get_text(strip=True).lower()
            in_stock = "in stock" in text or "available" in text
        else:
            add_to_cart = soup.find("input", {"id": "add-to-cart-button"})
            in_stock = add_to_cart is not None

        return {"name": name, "in_stock": in_stock}
    except Exception as e:
        return {"name": "Unknown", "in_stock": False, "error": str(e)}

def check_stock(url):
    if "amazon.in" in url or "amazon.com" in url:
        return check_amazon_stock(url)
    return {"name": url, "in_stock": False, "error": "Site not supported yet"}

# ============ TELEGRAM COMMANDS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """👋 *Stock Alert Bot*

Commands:
/add <url> — Product add karo
/remove <url> — Product remove karo
/list — Sab products dekho
/check — Abhi check karo

Example:
`/add https://www.amazon.in/dp/B0FQFYXCC4`"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ URL do!\nExample: /add https://www.amazon.in/dp/...")
        return

    url = context.args[0]
    products = load_products()

    if url in products:
        await update.message.reply_text("⚠️ Ye product pehle se add hai!")
        return

    await update.message.reply_text("🔍 Product check kar raha hoon...")
    result = check_stock(url)

    products[url] = {"name": result["name"], "last_status": result["in_stock"]}
    save_products(products)

    status = "✅ In Stock" if result["in_stock"] else "❌ Out of Stock"
    await update.message.reply_text(
        f"✅ *Product add ho gaya!*\n\n📦 {result['name']}\n📊 Status: {status}\n\nHar 5 minute mein check hoga!",
        parse_mode="Markdown"
    )

async def remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ URL do!\nExample: /remove https://www.amazon.in/dp/...")
        return

    url = context.args[0]
    products = load_products()

    if url not in products:
        await update.message.reply_text("⚠️ Ye product list mein nahi hai!")
        return

    name = products[url]["name"]
    del products[url]
    save_products(products)
    await update.message.reply_text(f"🗑️ *Removed:* {name}", parse_mode="Markdown")

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_products()

    if not products:
        await update.message.reply_text("📋 Koi product add nahi hai!\n\n/add <url> se add karo")
        return

    msg = "📋 *Tracked Products:*\n\n"
    for i, (url, data) in enumerate(products.items(), 1):
        status = "✅" if data["last_status"] else "❌"
        msg += f"{i}. {status} {data['name']}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_products()

    if not products:
        await update.message.reply_text("📋 Koi product add nahi hai!")
        return

    await update.message.reply_text("🔍 Sab check kar raha hoon...")

    msg = "📊 *Stock Status:*\n\n"
    for url, data in products.items():
        result = check_stock(url)
        status = "✅ In Stock" if result["in_stock"] else "❌ Out of Stock"
        msg += f"📦 {data['name']}\n{status}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ============ AUTO CHECK JOB ============

async def auto_check_job(context: ContextTypes.DEFAULT_TYPE):
    products = load_products()

    for url, data in products.items():
        result = check_stock(url)

        if result["in_stock"] and not data["last_status"]:
            msg = f"🚨 *STOCK ALERT!*\n\n✅ {result['name']} ab IN STOCK hai!\n\n🛒 {url}"
            await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

        elif not result["in_stock"] and data["last_status"]:
            msg = f"📴 *Out of Stock*\n\n❌ {result['name']} ab out of stock ho gaya."
            await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

        products[url]["last_status"] = result["in_stock"]

    save_products(products)

# ============ MAIN ============

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_product))
    app.add_handler(CommandHandler("remove", remove_product))
    app.add_handler(CommandHandler("list", list_products))
    app.add_handler(CommandHandler("check", check_now))

    app.job_queue.run_repeating(auto_check_job, interval=CHECK_INTERVAL, first=10)

    print("✅ Bot chal raha hai!")
    app.run_polling()

if __name__ == "__main__":
    main()
