import os
import sys
import logging
import sqlite3
import asyncio
import threading
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
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                energy INTEGER DEFAULT 20,
                click_count INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"数据库初始化失败: {e}")


def get_or_create_user(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT energy, click_count FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO users (user_id, energy, click_count) VALUES (?, 20, 0)", (user_id,))
            conn.commit()
            energy, click_count = 20, 0
        else:
            energy, click_count = row, row
        conn.close()
        return energy, click_count
    except Exception as e:
        logging.error(f"数据库读取失败: {e}")
        return 20, 0


def update_user_click(user_id, new_count, new_energy):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET click_count = ?, energy = ? WHERE user_id = ?",
                       (new_count, new_energy, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"数据库更新失败: {e}")


def add_user_energy(user_id, amount):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT energy FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE users SET energy = energy + ? WHERE user_id = ?", (amount, user_id))
        else:
            cursor.execute("INSERT INTO users (user_id, energy, click_count) VALUES (?, ?, 0)", (user_id, 20 + amount))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"数据库加能量失败: {e}")


# ====================================================================

# 输入 /start 启动
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name

        update_user_click(user_id, 0, 20)

        if context.args:
            try:
                referrer_id = int(context.args)
                if referrer_id != user_id:
                    add_user_energy(referrer_id, 10)
                    logging.info(f"🔥【裂变成功】新用户 {user_id} 为邀请人 {referrer_id} 成功助力！")

                    try:
                        notify_text = (
                            "🔔 【裂变助力报喜】\n"
                            "──────────────────\n"
                            f"✨ 您的好友【{user_name}】已通过您分享的卡片成功加入！\n\n"
                            "🎁 恭喜获得：+10 抽奖能量！\n"
                            "📈 提现进度已更新为：【99.995%】！\n\n"
                            "⚡ 能量已到账，快点击下方按钮继续开盘！"
                        )
                        keyboard = [[InlineKeyboardButton("🎰 进入娱乐城继续提现", callback_data="draw_lottery")]]
                        await context.bot.send_message(chat_id=referrer_id, text=notify_text,
                                                       reply_markup=InlineKeyboardMarkup(keyboard))
                    except Exception as notify_err:
                        logging.error(f"发送私信通知失败: {notify_err}")
            except ValueError:
                pass

        keyboard = [[InlineKeyboardButton("🎰 启动免费老虎机 🎰", callback_data="draw_lottery")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = (
            f"🔥 【官方至尊娱乐城 · 福利回馈】\n"
            "──────────────────\n"
            f"👑 欢迎入场！尊贵的会员【{user_name}】\n"
            f"🔋 当前可用幸运能量：20 点\n\n"
            "🎁 头等大奖：iPhone 16 Pro Max 现金券（100%必中）\n"
            "👇 赶快点击下方按钮，摇动你的超级老虎机吧！"
        )
        await update.message.reply_text(text=welcome_text, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Start运行错误: {e}")


# 老虎机点击与判定
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    try:
        energy, count = get_or_create_user(user_id)
        count += 1

        if count == 1:
            await query.answer(text="🎰 老虎机正在疯狂旋转中...")
            try:
                await query.message.delete()
            except Exception:
                pass

            await context.bot.send_dice(chat_id=query.message.chat_id, emoji="slot_machine")
            await asyncio.sleep(2.5)

            energy = max(0, energy - 10)
            update_user_click(user_id, count, energy)

            text = (
                "❌ 【哎呀，差一点点！】\n"
                "──────────────────\n"
                "刚刚摇出了普通组合，未能直接清空奖池。\n\n"
                "🎁 触发保底机制：恭喜获得【特等奖概率翻倍卡】x1！\n"
                f"🔋 剩余能量：{energy} 点（下次抽奖将100%爆出大奖！）"
            )
            keyboard = [[InlineKeyboardButton("⚡ 消耗最后10能量·必定中奖 ⚡", callback_data="draw_lottery")]]
            await context.bot.send_message(chat_id=query.message.chat_id, text=text,
                                           reply_markup=InlineKeyboardMarkup(keyboard))
            return

        elif count == 2:
            if energy < 10:
                count = 3
            else:
                await query.answer(text="🎰 翻倍卡已激活！正在为您锁定中奖图案...")
                try:
                    await query.message.delete()
                except Exception:
                    pass

                await context.bot.send_dice(chat_id=query.message.chat_id, emoji="slot_machine")
                await asyncio.sleep(2.5)

                energy = max(0, energy - 10)
                update_user_click(user_id, count, energy)

                await context.bot.send_message(chat_id=query.message.chat_id,
                                               text="🎉 🎉 🎉 🎉 🎉 🎉 🎉 🎉\n🎰 恭喜！老虎机特等奖已爆出！ 🎰")

                text = (
                    "🎉 🎉【恭喜斩获至尊特等奖】🎉 🎉\n"
                    "──────────────────\n"
                    "🎰 您的老虎机成功摇出【7 7 7】至尊满贯图案！\n"
                    "🎁 获得奖品：【iPhone 16 Pro Max 256G】现金全额券！\n\n"
                    "💰 当前资金提现进度：已达成 99.99%\n"
                    "⚠️ 系统风控提示：由于金额过大，只需凑齐最后【0.01元】即可立即提现到账！"
                )
                button_text = "🚀 消耗 10 能量，抽取最后 0.01 元 🚀"
                keyboard = [[InlineKeyboardButton(button_text, callback_data="draw_lottery")]]
                await context.bot.send_message(chat_id=query.message.chat_id, text=text,
                                               reply_markup=InlineKeyboardMarkup(keyboard))
                return

        if count >= 3:
            update_user_click(user_id, count, energy)
            await query.answer(text="❌ 槽位能量耗尽！提现已被锁定在 99.99%！", show_alert=True)

            share_url = create_deep_linked_url(BOT_USERNAME, str(user_id))
            share_text = f"🎁 我在至尊娱乐城摇老虎机中了 iPhone 16 Pro Max！已经拿到 99.99% 了！快帮我点一下助力，你也能白嫖一台！"

            keyboard = [
                [InlineKeyboardButton("📢 一键转发给 TG 好友/群聊助力", switch_inline_query=f"\n{share_text}\n{share_url}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            text = (
                "❌ 【您的幸运抽奖能量已耗尽】\n"
                "──────────────────\n"
                "🔒 提现通道当前锁定在：【99.99%】\n"
                f"🔋 当前可用能量：{energy} 点（每次充能启动需 10 点）\n\n"
                "👇 点击下方按钮转发到任意 TG 好友或群聊，只要有 1 个好友点击链接进入，您即可瞬间获得 +10 能量直接开盘提现！\n\n"
                "您的专属助力链接：\n"
                f"{share_url}"
            )
            try:
                await query.edit_message_text(text=text, reply_markup=reply_markup)
            except Exception:
                await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_markup)
    except Exception as button_err:
        logging.error(f"按钮异常: {button_err}")


# 内联分享
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user_id = update.inline_query.from_user.id
        share_url = create_deep_linked_url(BOT_USERNAME, str(user_id))
        message_content = (
            f"🔥 帮我点一下！还差 0.01 就能提现老虎机中的 iPhone 16 Pro Max 了！\n\n"
            f"🎁 点击下方链接帮我助力，你也可以免费获得 1 次 100% 中奖机会！\n👇 👇 👇\n{share_url}"
        )
        results = [
            InlineQueryResultArticle(
                id="pdd_share",
                title="🎁 点击发送至尊老虎机中奖助力卡片",
                input_message_content=InputTextMessageContent(message_content),
                description="点击即可将你的专属老虎机中奖助力卡片发送给当前好友或群聊"
            )
        ]
        await update.inline_query.answer(results, cache_time=1)
    except Exception as e:
        logging.error(f"转发异常: {e}")


# ==================== 🌐 云端保活及服务器核心启动区 ====================

class HealthCheckHandler(BaseHTTPRequestHandler):
    """自定义轻量级网页网关，专门用来回应云平台（Render）的健康检查"""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Slot machine system is up!")

    def log_message(self, format, *args):
        return  # 强行屏蔽心跳请求的日志，让你的 PyCharm 和云端控制台保持干净


def run_health_server(port):
    """启动子线程保活网页服务器"""
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        print(f"🔒 端口守卫启动成功，已成功锁定云端内部转发端口: {port}")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ 守护网页服务器发生异常: {e}")


def main():
    # 1. 初始化 SQLite 数据库（存盘用户的抽奖能量与点击数）
    init_db()

    # 2. 配置高抗网络波动的 HTTP 客户端
    from telegram.request import HTTPXRequest
    custom_request = HTTPXRequest(read_timeout=60.0, write_timeout=60.0, connect_timeout=60.0)

    # 3. 构建机器人核心驱动示例
    app = Application.builder().token(BOT_TOKEN).request(custom_request).build()

    # 4. 注册三大核心功能监听器
    app.add_handler(CommandHandler("start", start))  # 启动/重置
    app.add_handler(CallbackQueryHandler(button_click, pattern="^draw_lottery$"))  # 老虎机摇奖
    app.add_handler(InlineQueryHandler(inline_query_handler))  # 裂变转发卡片

    # 5. 启动自适应自愈分流引擎
    if IS_LOCAL:
        # 本地电脑环境：继续执行 Polling 主动轮询，方便开发者通过代理进行逻辑测试
        print("🚀 本地老虎机娱乐城 Polling 调试模式启动成功...")
        app.run_polling()
    else:
        # 云端（Render）Linux 环境：
        # 1. 动态抓取云服务器为这个应用分配的公网响应端口
        PORT = int(os.environ.get("PORT", 8443))

        # 2. 在独立的守护线程（Daemon Thread）中强行拉起网页服务器，满足云平台的 0 错误通过率
        threading.Thread(target=run_health_server, args=(PORT,), daemon=True).start()

        # 3. 主线程显式激活全新的异步网络循环事件，死死钉住长连接，100% 根除云端闪退！
        print("🚀 云端生产自适应守护 Polling 模式成功上线！")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app.run_polling(close_loop=False)


# ⚠️ 必须带双下划线，作为 Python 程序的标准执行生命线入口
if __name__ == '__main__':
    main()

