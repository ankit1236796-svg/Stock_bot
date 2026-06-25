import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
CHECK_INTERVAL = 300
PRODUCTS_FILE = "products.json"

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

def check_amazon(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        title = soup.find("span", {"id": "productTitle"})
        name = title.get_text(strip=True)[:60] if title else "Product"
        avail = soup.find("div", {"id": "availability"})
        if avail:
            text = avail.get_text(strip=True).lower()
            in_stock = "in stock" in text or "available" in text
        else:
            btn = soup.find("input", {"id": "add-to-cart-button"})
            in_stock = btn is not None
        return name, in_stock
    except Exception as e:
        logging.error(f"Error: {e}")
        return "Product", False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Stock Alert Bot\n\n"
        "/add <url> — Product add karo\n"
        "/remove <url> — Remove karo\n"
        "/list — Sab products dekho\n"
        "/check — Abhi check karo"
    )

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ URL do! /add https://amazon.in/dp/...")
        return
    url = context.args[0]
    products = load_products()
    if url in products:
        await update.message.reply_text("⚠️ Pehle se add hai!")
        return
    await update.message.reply_text("🔍 Check kar raha hoon...")
    name, in_stock = check_amazon(url)
    products[url] = {"name": name, "last_status": in_stock}
    save_products(products)
    status = "✅ In Stock" if in_stock else "❌ Out of Stock"
    await update.message.reply_text(f"✅ Add ho gaya!\n📦 {name}\n📊 {status}")

async def remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ URL do!")
        return
    url = context.args[0]
    products = load_products()
    if url not in products:
        await update.message.reply_text("⚠️ List mein nahi hai!")
        return
    name = products[url]["name"]
    del products[url]
    save_products(products)
    await update.message.reply_text(f"🗑️ Removed: {name}")

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_products()
    if not products:
        await update.message.reply_text("📋 Koi product nahi hai!\n/add se add karo")
        return
    msg = "📋 Tracked Products:\n\n"
    for i, (url, data) in enumerate(products.items(), 1):
        s = "✅" if data["last_status"] else "❌"
        msg += f"{i}. {s} {data['name']}\n"
    await update.message.reply_text(msg)

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_products()
    if not products:
        await update.message.reply_text("📋 Koi product nahi hai!")
        return
    await update.message.reply_text("🔍 Check kar raha hoon...")
    msg = "📊 Stock Status:\n\n"
    for url, data in products.items():
        name, in_stock = check_amazon(url)
        s = "✅ In Stock" if in_stock else "❌ Out of Stock"
        msg += f"📦 {data['name']}\n{s}\n\n"
    await update.message.reply_text(msg)

async def auto_check(context: ContextTypes.DEFAULT_TYPE):
    products = load_products()
    for url, data in products.items():
        name, in_stock = check_amazon(url)
        if in_stock and not data["last_status"]:
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=f"🚨 STOCK ALERT!\n\n✅ {name} IN STOCK hai!\n\n🛒 {url}"
            )
        elif not in_stock and data["last_status"]:
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=f"📴 Out of Stock\n\n❌ {name} out of stock ho gaya."
            )
        products[url]["last_status"] = in_stock
    save_products(products)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_product))
    app.add_handler(CommandHandler("remove", remove_product))
    app.add_handler(CommandHandler("list", list_products))
    app.add_handler(CommandHandler("check", check_now))
    app.job_queue.run_repeating(auto_check, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot chal raha hai!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
