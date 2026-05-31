import os
import sys
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, InlineQueryHandler, ContextTypes
from telegram.utils.helpers import create_deep_linked_url

# ==================== 🛠️ 智能环境自适应区 ====================
# 自动检测是在本地 Windows 调试还是在 Linux 云端运行
IS_LOCAL = sys.platform == 'win32'

if IS_LOCAL:
    import urllib.request

    proxies = urllib.request.getproxies()
    if 'https' in proxies:
        os.environ["http_proxy"] = proxies['https']
        os.environ["https_proxy"] = proxies['https']
        print(f"⚙️ 本地调试：成功自动捕获系统代理地址: {proxies['https']}")
else:
    print("🌐 云端运行：正在启动 Linux 生产环境配置...")
# ========================================================

BOT_TOKEN = "8729999872:AAFF_-vzc4fpXoe1MpCPDRtEctEkmcjtkDE"
BOT_USERNAME = "Lottery_robot8_bot"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


# 输入 /start 启动
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    context.user_data['click_count'] = 0
    if context.args:
        referrer_id = context.args[0]
        logging.info(f"🔥【裂变报喜】新用户 {user_id} 是通过用户 {referrer_id} 的助力链接点进来的！")

    keyboard = [[InlineKeyboardButton("🎰 点击开始免费抽奖 🎰", callback_data="draw_lottery")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "🔥 【官方粉丝特惠回馈中心】\n"
        "──────────────────\n"
        "⚡ 恭喜你获得今日免费抽奖资格！\n"
        "🎁 奖池包含：iPhone 16 Pro Max、万元现金等大奖！\n\n"
        "⏰ 活动仅限今天，名额有限，赶紧点击下方按钮抽取！"
    )
    await update.message.reply_text(text=welcome_text, reply_markup=reply_markup)


# 按钮点击逻辑
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    if 'click_count' not in context.user_data:
        context.user_data['click_count'] = 1
    else:
        context.user_data['click_count'] += 1

    count = context.user_data['click_count']

    if count == 1:
        await query.answer(text="🎉 🎉 🎉 恭喜你中奖啦！！！ 🎉 🎉 🎉")
        await query.message.reply_text("🎊 🎊 🎊 🎊 🎊 🎊 🎊 🎊\n🎉 🎉 🎉 🎉 🎉 🎉 🎉 🎉")

        text = (
            "💎 【中奖通知：特等奖】\n"
            "──────────────────\n"
            "恭喜抽中：【iPhone 16 Pro Max 256G 兑换券】一份！\n\n"
            "💰 当前提现进度：已完成 99.9%\n"
            "⚠️ 系统提示：由于微信/支付宝限额，只需再凑齐 0.1 元即可立提到账！"
        )
        button_text = "⚡ 再次点击，免费抽取最后 0.1 元 ⚡"
        keyboard = [[InlineKeyboardButton(button_text, callback_data="draw_lottery")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.message.reply_text(text=text, reply_markup=reply_markup)
            await query.delete_message()
        except BadRequest:
            pass
    elif count == 2:
        await query.answer(text="⚡ 正在为您疯狂暴击中...")
        text = (
            "🔥 【运气爆棚！提现暴击！】\n"
            "──────────────────\n"
            "刚才一击为您成功抽中：0.09 元！\n\n"
            "📈 当前总进度已达：【99.99%】\n"
            "还差最后的【0.01 元】即可打破锁定，资金立刻全额汇入钱包！"
        )
        button_text = "🚀 消耗 1 能量，抽取最后 0.01 元 🚀"
        keyboard = [[InlineKeyboardButton(button_text, callback_data="draw_lottery")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
        except BadRequest:
            pass
    else:
        await query.answer(text="❌ 今日抽奖能量耗尽！由于进度高达99.99%，提现已被暂时锁定！", show_alert=True)
        share_url = create_deep_linked_url(BOT_USERNAME, str(user_id))
        share_text = f"🎁 我正在参加抽 iPhone 16 活动，已经拿到 99.99% 了！快帮我点一下助力，你也能拿一台！"

        keyboard = [[InlineKeyboardButton("📢 一键转发给 TG 好友/群聊助力", switch_inline_query=f"\n{share_text}\n{share_url}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "❌ 【您的今日抽奖能量已耗尽】\n"
            "──────────────────\n"
            "🔒 提现通道当前锁定在：【99.99%】\n\n"
            "👇 点击下方按钮转发到任意 TG 好友或微信群聊，只要有 1 个好友点击链接进入，您即可瞬间获得 100 能量打破锁定，直接提现！\n\n"
            "您的专属助力链接：\n"
            f"{share_url}"
        )
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
        except BadRequest:
            pass


# 内联卡片转发
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


def main():
    from telegram.request import HTTPXRequest
    custom_request = HTTPXRequest(read_timeout=60.0, write_timeout=60.0, connect_timeout=60.0)
    app = Application.builder().token(BOT_TOKEN).request(custom_request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click, pattern="^draw_lottery$"))
    app.add_handler(InlineQueryHandler(inline_query_handler))

    # 💡 核心自适应部署逻辑
    if IS_LOCAL:
        # 本地电脑继续采用 Polling 模式调试
        print("🚀 本地调试模式启动成功...")
        app.run_polling()
    else:
        # Render 云端自动转换为 Webhook 模式，绑定 Render 提供的端口和 URL
        PORT = int(os.environ.get("PORT", 8443))
        RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

        print(f"🚀 云端生产 Webhook 模式启动。目标 URL: {RENDER_EXTERNAL_URL}, 端口: {PORT}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            secret_token="pdd_bot_secure_token_123",  # 密钥
            url_path=BOT_TOKEN,
            webhook_url=f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}"
        )


if __name__ == '__main__':
    main()
