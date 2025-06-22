import os
from flask import Flask, request, render_template, redirect
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage,
    ImageSendMessage, StickerMessage
)
from linebot.exceptions import InvalidSignatureError

app = Flask(__name__)

line_bot_api = LineBotApi('00KCkQLhlaDFzo5+UTu+/C4A49iLmHu7bbpsfW8iamonjEJ1s88/wdm7Yrou+FazbxY7719UNGh96EUMa8QbsG Bf9K5rDWhJpq8XTxakXRuTM6HiJDSmERbIWfyfRMfscXJPcRyTL6YyGNZxqkYSAQdB04t89/1O/w1cDnyilFU=')  # ← 自分のトークンに書き換え
handler = WebhookHandler('6c12aedc292307f95ccd67e959973761')         # ← 自分のシークレットに書き換え

user_states = {}
pending_users = []
completed_users = set()

questions = [
    "第1問: 鍵は赤い箱の中。写真で答えてね！",
    "第2問: 机の裏を探してみよう。写真で答えてね！",
    "第3問: 黒板に書かれた数字に注目。写真で答えてね！",
    "第4問: 窓の外にヒントがあるよ。写真で答えてね！",
    "第5問: 最後の謎はあなたの直感！写真で答えてね！"
]

hints = [
    "赤い箱の中に何があるか見てみよう！",
    "机の裏のメモをよく読んで！",
    "数字の順番がヒント！",
    "外の風景に答えが隠れてるかも！",
    "今までの謎を思い出してみよう！"
]

@app.route("/")
def index():
    return "Bot is running"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature', 400
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_states:
        user_states[user_id] = {"name": None, "stage": 0, "completed": False}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="参加してくれてありがとう！名前を登録してね。"))
        return

    state = user_states[user_id]
    if state["completed"]:
        return

    if state["name"] is None:
        name = text
        for u in user_states.values():
            if u["name"] == name:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="この名前はすでに使われています。別の名前を入力してください。"))
                return
        state["name"] = name
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}さん、参加してくれてありがとう！\n{questions[0]}"))
        return

    if text.lower() == "retire":
        advance_stage(user_id, event.reply_token, force=True)
        return

    if text.lower().startswith("reset"):
        suffix = text[5:]
        if suffix.isdigit():
            target_stage = int(suffix)
            if target_stage <= state["stage"]:
                state["stage"] = target_stage
                state["completed"] = False
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{state['name']}さん、第{target_stage+1}問から再スタートします。\n{questions[target_stage]}"))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="進んでいない問題にはリセットできません。"))
        return

    if text == "ヒント":
        stage = state["stage"]
        if stage < len(hints):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=hints[stage]))
        return

    if text == "1=∞":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="そんなわけないだろ亀ども"))
        return

    if text.endswith("？"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="good question!"))
        return

@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker(event):
    pass  # 無反応

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    if user_id not in user_states or user_states[user_id]["completed"]:
        return

    os.makedirs("static/images", exist_ok=True)
    message_content = line_bot_api.get_message_content(event.message.id)
    image_path = f"static/images/{user_id}.jpg"
    with open(image_path, 'wb') as f:
        for chunk in message_content.iter_content():
            f.write(chunk)

    if user_id not in pending_users:
        pending_users.append(user_id)

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="画像を受け取りました！判定をお待ちください。"))

@app.route("/form")
def form():
    users = []
    for uid in pending_users:
        state = user_states[uid]
        users.append({
            "user_id": uid,
            "name": state["name"],
            "stage": state["stage"] + 1,
            "image": f"/static/images/{uid}.jpg"
        })
    return render_template("judge.html", users=users)

@app.route("/judge", methods=["POST"])
def judge():
    user_id = request.form["user_id"]
    result = request.form["result"]
    state = user_states[user_id]

    if state["completed"]:
        return redirect("/form")

    if state["stage"] == len(questions) - 1:
        if result == "correct1":
            line_bot_api.push_message(user_id, TextSendMessage(text="本当に素晴らしい発見力でした！あなたはこの謎解きの達人です。"))
        elif result == "correct2":
            line_bot_api.push_message(user_id, TextSendMessage(text="最後までよくがんばりました！柔軟な発想が光っていました。"))
        else:
            line_bot_api.push_message(user_id, TextSendMessage(text="残念、不正解でした！"))
        state["completed"] = True
    elif result == "correct":
        state["stage"] += 1
        line_bot_api.push_message(user_id, TextSendMessage(text=questions[state["stage"]]))
    else:
        line_bot_api.push_message(user_id, TextSendMessage(text="残念、不正解。もう一度考えてみて！"))

    if user_id in pending_users:
        pending_users.remove(user_id)

    return redirect("/form")

@app.route("/admin_send", methods=["GET", "POST"])
def admin_send():
    if request.method == "POST":
        user_id = request.form["user_id"]
        message = request.form["message"]
        image_url = request.form.get("image_url")

        messages = [TextSendMessage(text=message)]
        if image_url:
            messages.append(ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            ))

        line_bot_api.push_message(user_id, messages)
        return redirect("/admin_send")

    return render_template("admin_send.html")
