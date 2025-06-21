from flask import Flask, request, render_template, redirect
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, StickerMessage
from linebot.exceptions import InvalidSignatureError
import os

app = Flask(__name__)

line_bot_api = LineBotApi('00KCkQLhlaDFzo5+UTu+/C4A49iLmHu7bbpsfW8iamonjEJ1s88/wdm7Yrou+FazbxY7719UNGh96EUMa8QbsGBf9K5rDWhJpq8XTxakXRuTM6HiJDSmERbIWfyfRMfscXJPcRyTL6YyGNZxqkYSAQdB04t89/1O/w1cDnyilFU=')  # ← 自分のアクセストークンに置き換えて
handler = WebhookHandler('6c12aedc292307f95ccd67e959973761')         # ← 自分のシークレットに置き換えて

user_states = {}
pending_users = []
completed_users = set()

questions = [
    {"text": "第1問: 鍵は赤い箱の中。写真で答えてね！", "image": "static/question1.jpg"},
    {"text": "第2問: 机の裏を探してみよう。写真で答えてね！", "image": "static/question2.jpg"},
    {"text": "第3問: 黒板に書かれた数字に注目。写真で答えてね！", "image": "static/question3.jpg"},
    {"text": "第4問: 窓の外にヒントがあるよ。写真で答えてね！", "image": "static/question4.jpg"},
    {"text": "第5問: 最後の謎はあなたの直感！写真で答えてね！", "image": "static/question5.jpg"}
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
    signature = request.headers['X-Line-Signature']
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
        state["name"] = text
        send_question(user_id)
        return

    if text.lower() == "reset":
        user_states[user_id] = {"name": None, "stage": 0, "completed": False}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="名前を登録してね。"))
        return

    if text.lower() == "retire":
        advance_stage(user_id, event.reply_token, force=True)
        return

    if text.lower() == "ヒント":
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
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="何の意味があるの？"))

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
            line_bot_api.push_message(user_id, TextSendMessage(text="君の観察眼は確かだった。最後の答えがすべてを導いた！"))
        elif result == "correct2":
            line_bot_api.push_message(user_id, TextSendMessage(text="大胆な発想が突破口だった！最高のエンディングだ！"))
        else:
            line_bot_api.push_message(user_id, TextSendMessage(text="残念、不正解だったけど、よく頑張ったね！"))
        state["completed"] = True
    elif result == "correct":
        state["stage"] += 1
        send_question(user_id)
    else:
        line_bot_api.push_message(user_id, TextSendMessage(text="残念、不正解。もう一度考えてみて！"))

    if user_id in pending_users:
        pending_users.remove(user_id)

    return redirect("/form")

def send_question(user_id):
    stage = user_states[user_id]["stage"]
    q = questions[stage]
    if q["image"]:
        line_bot_api.push_message(user_id, [
            TextSendMessage(text=q["text"]),
            {
                "type": "image",
                "originalContentUrl": f"https://yourdomain.com/{q['image']}",
                "previewImageUrl": f"https://yourdomain.com/{q['image']}"
            }
        ])
    else:
        line_bot_api.push_message(user_id, TextSendMessage(text=q["text"]))

def advance_stage(user_id, token, force=False):
    state = user_states[user_id]
    state["stage"] += 1
    if state["stage"] >= len(questions):
        state["completed"] = True
        line_bot_api.reply_message(token, TextSendMessage(text="謎の解説を送るよ！お疲れ様！"))
    else:
        send_question(user_id)
        line_bot_api.reply_message(token, TextSendMessage(text="謎の解説を送ったよ。次はこちら！"))
