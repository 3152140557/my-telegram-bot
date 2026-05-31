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
            energy, click_count = row[0], row[1]
        conn.close()
        return energy, click_count
    except Exception as e:
        logging.error(f"数据库读取失败: {e}")
        return 20, 0  # 降级容错方案


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

        energy, _ = get_or_create_user(user_id)

        # 裂变检测
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
                            f"✨ 您的好友【{user_name}】已为您助力成功！\n\n"
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
            f"🔋 当前可用幸运能量：{energy} 点\n\n"
            "🎁 头等大奖：iPhone 16 Pro Max 现金券（100%必中）\n"
            "👇 赶快点击下方按钮，摇动你的超级老虎机吧！"
        )
        await update.message.reply_text(text=welcome_text, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Start指令内运行发生未知错误: {e}")


# 核心小游戏与点击判定逻辑（强力容错版）
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    try:
        energy, count = get_or_create_user(user_id)
        count += 1

        # 🕹️ 第一次摇老虎机
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

        # 🕹️ 第二次摇老虎机
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
                                               text="🎉 🎉 🎉 🎉 🎉 🎉 🎉 🎉\n🎰 恭喜！老虎机大奖已爆出！ 🎰")

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

        # 🕹️ 第三次点击及以上
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
        logging.error(f"按钮处理分支抛出异常(已捕获守护): {button_err}")
        try:
            await query.answer(text="⚠️ 网络繁忙，请重新点击测试！")
        except Exception:
            pass


# 内联卡片一键转发
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
