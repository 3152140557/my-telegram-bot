import os
import sys
import logging
import asyncio
import threading
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, InlineQueryHandler, ContextTypes
from telegram.helpers import create_deep_linked_url

# ==================== 🛠️ 智能环境自适应区 ====================
IS_LOCAL = sys.platform == 'win32'

if IS_LOCAL:
    import urllib.request

    proxies = urllib.request.getproxies()
    if 'https' in proxies:
        os.environ["http_proxy"] = proxies['https']
        os.environ["https_proxy"] = proxies['https']
        print(f"⚙️ 本地调试：成功自动捕获系统代理地址: {proxies['https']}")
else:
    print("🌐 云端运行：正在启动 Linux 守护进程环境...")
# ========================================================

BOT_TOKEN = "8729999872:AAFF_-vzc4fpXoe1MpCPDRtEctEkmcjtkDE"
BOT_USERNAME = "Lottery_robot8_bot"
DB_FILE = "lottery.db"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


# ==================== 💾 SQLite 数据库核心控制区 ====================
def init_db():
    """初始化数据库，创建用户表"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # users表：用户ID，剩余能量，点击次数
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            energy INTEGER DEFAULT 20,
            click_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()


def get_or_create_user(user_id):
    """获取或创建用户，默认赠送 20 能量"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT energy, click_count FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, energy, click_count) VALUES (?, 20, 0)", (user_id,))
        conn.commit()
        energy, click_count = 20, 0
    else:
        energy, click_count = row[0], row[1]
    conn.close()
    return energy, click_count


def update_user_click(user_id, new_count, new_energy):
    """更新用户的点击次数和能量值"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET click_count = ?, energy = ? WHERE user_id = ?", (new_count, new_energy, user_id))
    conn.commit()
    conn.close()


def add_user_energy(user_id, amount):
    """为指定用户增加能量值"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 先确保用户存在
    cursor.execute("SELECT energy FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        cursor.execute("UPDATE users SET energy = energy + ? WHERE user_id = ?", (amount, user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, energy, click_count) VALUES (?, ?, 0)", (user_id, 20 + amount))
    conn.commit()
    conn.close()


# ====================================================================

# 输入 /start 启动（核心裂变识别点）
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    # 获取当前用户的数据库状态
    energy, _ = get_or_create_user(user_id)

    # 💡 核心裂变监控：检查是不是通过别人的邀请链接（/start referrer_id）进来的
    if context.args:
        try:
            referrer_id = int(context.args[0])
            # 防止自己给自己助力
            if referrer_id != user_id:
                # 1. 数据库执行核心加能量操作：为邀请人 +10 能量
                add_user_energy(referrer_id, 10)
                logging.info(f"🔥【裂变成功】新用户 {user_id}({user_name}) 为邀请人 {referrer_id} 成功助力！")

                # 2. 实时发送私信通知给邀请人，仪式感拉满！
                try:
                    notify_text = (
                        "🔔 【裂变助力报喜】\n"
                        "──────────────────\n"
                        f"✨ 您的好友【{user_name}】已通过您分享的卡片成功加入！\n\n"
                        "🎁 恭喜获得：+10 抽奖能量！\n"
                        "📈 提现进度已从 99.99% 解锁更新为：【99.995%】！\n\n"
                        "⚡ 提现通道已重新为您开启，快点击下方按钮继续破关！"
                    )
                    keyboard = [[InlineKeyboardButton("🎰 回到控制台继续提现", callback_data="draw_lottery")]]
                    await context.bot.send_message(chat_id=referrer_id, text=notify_text,
                                                   reply_markup=InlineKeyboardMarkup(keyboard))
                except Exception as e:
                    logging.error(f"向邀请人发送通知失败（可能由于邀请人删除了Bot）: {e}")
        except ValueError:
            pass  # 规避非数字参数带来的异常

    keyboard = [[InlineKeyboardButton("🎰 点击开始免费抽奖 🎰", callback_data="draw_lottery")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "🔥 【官方粉丝特惠回馈中心】\n"
        "──────────────────\n"
        f"👑 欢迎您，{user_name}！\n"
        f"⚡ 当前可用抽奖能量：{energy} 点\n"
        "🎁 奖池包含：iPhone 16 Pro Max、万元现金等大奖！\n\n"
        "⏰ 账户资金提现通道已开通，点击下方按钮开始！"
    )
    await update.message.reply_text(text=welcome_text, reply_markup=reply_markup)


# 按钮点击逻辑
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    # 每次点击，从数据库读取最新最真实的数据
    energy, count = get_or_create_user(user_id)

    # 拼多多经典的“卡点消耗”套路：每次点击次数自增，同时消耗 10 点能量
    count += 1

    if count == 1:
        energy = max(0, energy - 10)  # 消耗 10 能量
        update_user_click(user_id, count, energy)

        await query.answer(text="🎉 🎉 🎉 恭喜你中奖啦！！！ 🎉 🎉 🎉")
        await query.message.reply_text("🎊 🎊 🎊 🎊 🎊 🎊 🎊 🎊\n🎉 🎉 🎉 🎉 🎉 🎉 🎉 🎉")

        text = (
            "💎 【中奖通知：特等奖】\n"
            "──────────────────\n"
            "恭喜抽中：【iPhone 16 Pro Max 256G 兑换券】一份！\n\n"
            "💰 当前提现进度：已完成 99.9%\n"
            "⚠️ 系统提示：由于微信/支付宝限额，只需再凑齐 0.1 元即可立提到账！"
        )
        button_text = f"⚡ 消耗10能量，免费抽取最后 0.1 元（当前能量:{energy}）"
        keyboard = [[InlineKeyboardButton(button_text, callback_data="draw_lottery")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.message.reply_text(text=text, reply_markup=reply_markup)
            await query.delete_message()
        except BadRequest:
            pass

    elif count == 2:
        if energy < 10:
            # 如果能量中途不够了，直接拦截提前进入裂变阶段
            count = 3
        else:
            energy = max(0, energy - 10)  # 再次消耗 10 能量，此时能量刚好归零
            update_user_click(user_id, count, energy)

            await query.answer(text="⚡ 正在为您疯狂暴击中...")
            text = (
                "🔥 【运气爆棚！提现暴击！】\n"
                "──────────────────\n"
                "刚才一击为您成功抽中：0.09 元！\n\n"
                "📈 当前总进度已达：【99.99%】\n"
                f"🔋 剩余可用能量：{energy} 点\n\n"
                "还差最后的【0.01 元】即可打破锁定，资金立刻全额汇入钱包！"
            )
            button_text = f"🚀 消耗 10 能量，抽取最后 0.01 元 🚀"
            keyboard = [[InlineKeyboardButton(button_text, callback_data="draw_lottery")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.edit_message_text(text=text, reply_markup=reply_markup)
            except BadRequest:
                pass
            return

    if count >= 3:
        # 能量不足，强行卡关拦截，展示裂变转发
        update_user_click(user_id, count, energy)
        await query.answer(text="❌ 今日抽奖能量耗尽！由于进度高达99.99%，提现已被暂时锁定！", show_alert=True)

        share_url = create_deep_linked_url(BOT_USERNAME, str(user_id))
        share_text = f"🎁 我正在参加抽 iPhone 16 活动，已经拿到 99.99% 了！快帮我点一下助力，你也能拿一台！"

        keyboard = [[InlineKeyboardButton("📢 一键转发给 TG 好友/群聊助力", switch_inline_query=f"\n{share_text}\n{share_url}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "❌ 【您的今日抽奖能量已耗尽】\n"
            "──────────────────\n"
            "🔒 提现通道当前锁定在：【99.99%】\n"
            f"🔋 当前可用能量：{energy} 点（抽奖每次需消耗 10 点）\n\n"
            "👇 点击下方按钮转发到任意 TG 好友或群聊，只要有 1 个好友点击链接进入，您即可瞬间获得 +10 能量打破锁定，直接提现！\n\n"
            "您的专属助力链接：\n"
            f"{share_url}"
        )
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
        except BadRequest:
            pass


# 处理内联卡片一键转发
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.inline_query.from_user.id
    share_url = create_deep_linked_url(BOT_USERNAME, str(user_id))
    message_content = (
        f"🔥 帮我点一下！还差 0.01 就能提现 iPhone 16 Pro Max 了！\n\n"
        f"🎁 点击下方链接帮我助力，你也可以免费获得 1 次 100% 中奖机会！\n👇 👇 👇\n{share_url}"
    )
    results = [
        InlineQueryResultArticle(
            id="pdd_share",
            title="🎁 点击发送拼多多抽奖助力卡片",
            input_message_content=InputTextMessageContent(message_content),
            description="点击即可将你的专属抽奖助力链接发送给当前好友或群聊"
        )
    ]
    await update.inline_query.answer(results, cache_time=1)


# 云端保活服务器
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is fully alive with database!")

    def log_message(self, format, *args):
        return


def run_health_server(port):
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


def main():
    # 启动时初始化本地数据库
    init_db()

    from telegram.request import HTTPXRequest
    custom_request = HTTPXRequest(read_timeout=60.0, write_timeout=60.0, connect_timeout=60.0)
    app = Application.builder().token(BOT_TOKEN).request(custom_request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click, pattern="^draw_lottery$"))
    app.add_handler(InlineQueryHandler(inline_query_handler))

    if IS_LOCAL:
        print("🚀 本地数据库版安全轮询模式启动成功...")
        app.run_polling()
    else:
        PORT = int(os.environ.get("PORT", 8443))
