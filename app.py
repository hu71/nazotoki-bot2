import os
from flask import Flask, request, render_template, redirect
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, StickerMessage
from linebot.exceptions import InvalidSignatureError

app = Flask(__name__)
line_bot_api = LineBotApi('00KCkQLhlaDFzo5+UTu+/C4A49iLmHu7bbpsfW8iamonjEJ1s88/wdm7Yrou+FazbxY7719UNGh96EUMa8QbsG Bf9K5rDWhJpq8XTxakXRuTM6HiJDSmERbIWfyfRMfscXJPcRyTL6YyGNZxqkYSAQdB04t89/1O/w1cDnyilFU=')  # ← あなたのトークンに置き換えてください
handler = WebhookHandler('6c12aedc292307f95ccd67e959973761')        # ← あなたのシークレットに置き換えてください

user_states = {}
pending_users = []

questions = [
    "第1問: 鍵は赤い箱の中。その答えを写真で送ってね！",
    "第2問: 机の裏を探してみよう。写真で送ってね！",
    "第3問: 黒板に書かれた数字に注目。写真で送ってね！",
    "第4問: 窓の外にヒントがあるよ。写真で送ってね！",
    "第5問: 最後の謎はあなたの直感！写真で送ってね！"
]

hints = [
    "赤い箱の中に何があるか見てみよう！",
    "机の裏のメモをよく読んで！",
    "数字の順番がヒント！",
    "外の風景に答えが隠れてるかも！",
    "今までの謎を思い出してみよう！"
]

@app.route("/")
def hello():
    return "LINE Bot is running."

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature.', 400

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
        if any(u["name"] == text for u in user_states.values() if u["name"]):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="その名前はすでに使われています。別の名前を入力してください。"))
            return
        state["name"] = text
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{text}さん、参加ありがとう！\n{questions[0]}"))
        return

    if text.startswith("Reset"):
        try:
            n = int(text[5:])
            if 0 <= n <= state["stage"]:
                state["stage"] = n
                state["completed"] = False
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"第{n+1}問にリセットしました！\n{questions[n]}"))
            return
        except:
            return

    if text == "ヒント":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=hints[state["stage"]]))
        return

    if text == "Retire":
        if state["stage"] < len(questions) - 1:
            state["stage"] += 1
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"謎の解説を送ったよ！次はこちら！\n{questions[state['stage']]}"))
        else:
            state["completed"] = True
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="謎解きお疲れ様でした！"))
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
    if user_id not in user_states:
        return

    state = user_states[user_id]
    if state["completed"]:
        return

    os.makedirs("static/images", exist_ok=True)
    try:
        content = line_bot_api.get_message_content(event.message.id)
        path = f"static/images/{user_id}.jpg"
        with open(path, "wb") as f:
            for chunk in content.iter_content():
                f.write(chunk)
    except Exception as e:
        print("Error saving image:", e)
        return

    if user_id not in pending_users:
        pending_users.append(user_id)

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="画像を受け取りました！判定をお待ちください。"))

@app.route("/form")
def form():
    users = []
    for user_id in pending_users:
        state = user_states[user_id]
        users.append({
            "user_id": user_id,
            "name": state["name"],
            "stage": state["stage"] + 1,
            "image": f"/static/images/{user_id}.jpg"
        })
    return render_template("judge.html", users=users)

@app.route("/judge", methods=["POST"])
def judge():
    user_id = request.form["user_id"]
    result = request.form["result"]
    state = user_states[user_id]

    if result == "correct1":
        if state["stage"] == 4:
            line_bot_api.push_message(user_id, TextSendMessage(text="おめでとう！よく気づいたね。君のひらめきは最高だった！"))
            state["completed"] = True
        else:
            state["stage"] += 1
            line_bot_api.push_message(user_id, TextSendMessage(text="大正解！次の問題に進もう！\n" + questions[state["stage"]]))

    elif result == "correct2":
        if state["stage"] == 4:
            line_bot_api.push_message(user_id, TextSendMessage(text="すばらしい！落ち着いて考えた君の勝利だ！"))
            state["completed"] = True

    elif result == "incorrect":
        line_bot_api.push_message(user_id, TextSendMessage(text="残念、不正解。もう一度考えてみよう。「ヒント」と送ってみてね！"))

    if user_id in pending_users:
        pending_users.remove(user_id)

    return redirect("/form")

@app.route("/admin")
def admin():
    all_users = [
        {"user_id": uid, "name": state["name"], "stage": state["stage"] + 1}
        for uid, state in user_states.items()
    ]
    return render_template("admin_send.html", users=all_users)

@app.route("/admin_send", methods=["POST"])
def admin_send():
    user_id = request.form["user_id"]
    message = request.form["message"]
    image = request.files.get("image")

    if message:
        line_bot_api.push_message(user_id, TextSendMessage(text=message))

    if image:
        path = f"static/images/admin_{user_id}.jpg"
        image.save(path)
        line_bot_api.push_message(user_id, TextSendMessage(text="画像を送信しました（仮: Renderでは画像Pushは未実装）"))

    return redirect("/admin")
