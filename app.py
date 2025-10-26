# app.py — 読み上げ対局時計（Render/Flask）
from datetime import datetime
import os, smtplib, ssl
from email.mime.text import MIMEText
from email.header import Header

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, flash, send_from_directory
)

# ---- .env 読み込み（環境変数で渡すなら不要）----
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# =========================
# Flask App（1回だけ生成！）
# =========================
app = Flask(__name__, template_folder="templates", static_folder="static")

# ====== 環境変数（SMTP/メール先/秘密鍵） ======
SMTP_HOST  = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT  = int(os.getenv("SMTP_PORT", "25"))  # 465=SSL / 587=STARTTLS
SMTP_USER  = os.getenv("SMTP_USER", "")
SMTP_PASS  = os.getenv("SMTP_PASS", "")
MAIL_FROM  = os.getenv("MAIL_FROM", "no-reply@example.com")  # 送信者
MAIL_TO    = os.getenv("MAIL_TO",   "owner@example.com")     # 受信先
APP_SECRET = os.getenv("APP_SECRET", "dev-secret")
app.secret_key = APP_SECRET

# =========================================
# Jinja: {{ now().year }} を有効にする
# =========================================
@app.context_processor
def inject_now():
    # {{ now().year }}, {{ now().strftime('%Y-%m-%d') }} などで利用可
    return {"now": lambda: datetime.now()}

# =========================================
# 直下で配信したい静的ファイル（SEO/検証用）
# =========================================
# Google Search Console 所有権確認ファイル
# ※ファイル名は Search Console が発行した名前のまま！
@app.route("/google5d7ab4edca390893.html")
def google_verification():
    return send_from_directory(app.static_folder, "google5d7ab4edca390893.html")

# robots.txt / sitemap.xml をルート直下で配信
@app.route("/robots.txt")
def robots_txt():
    return send_from_directory(app.static_folder, "robots.txt")

@app.route("/sitemap.xml")
def sitemap_xml():
    return send_from_directory(app.static_folder, "sitemap.xml")

# =========================================
# ページルート
# =========================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stopwatch")
def stopwatch():
    return render_template("stopwatch.html")

@app.route("/chessclock")
def chessclock():
    return render_template("chessclock.html")

@app.route("/fischer")
def fischer():
    return render_template("fischer.html")

@app.route("/consideration")
def consideration():
    return render_template("consideration.html")

@app.route("/sudden_death")
def sudden_death():
    return render_template("sudden_death.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/credit")
def credit():
    return render_template("credit.html")

# =========================================================
# お問い合わせフォーム（GET 表示／POST 送信）
# - contact.html は method="post" action="{{ url_for('contact') }}"
# - ハニーポット（name="website"）が埋まってたら弾く
# - 正常時：メール送信 → フラッシュ → 同ページへリダイレクト（PRG）
# =========================================================
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        # ハニーポット
        if (request.form.get("website") or "").strip():
            flash("送信に失敗しました。もう一度お試しください。", "error")
            return redirect(url_for("contact"))

        name        = (request.form.get("name") or "").strip()
        email       = (request.form.get("email") or "").strip()
        topic       = (request.form.get("topic") or "").strip()
        other_topic = (request.form.get("otherTopic") or "").strip()  # 自由件名
        msg         = (request.form.get("message") or "").strip()

        if not (name and email and len(msg) >= 10):
            flash("必須項目の入力に誤りがあります。", "error")
            return redirect(url_for("contact"))

        # 「その他」は自由入力を件名に反映
        if topic == "その他" and other_topic:
            topic_display = f"その他（{other_topic}）"
        else:
            topic_display = topic or "(未選択)"

        # 任意メタ
        ua   = request.form.get("client_ua", "")
        lang = request.form.get("client_lang", "")
        tz   = request.form.get("client_tz", "")

        # 管理者宛：件名にもカテゴリ（自由件名含む）を反映
        subject = f"【読み上げ対局時計】お問い合わせ - {topic_display}"
        body = (
            f"お名前: {name}\n"
            f"メール: {email}\n"
            f"カテゴリ: {topic_display}\n"
            f"--- 本文 ---\n{msg}\n\n"
            f"--- メタ情報 ---\nUA: {ua}\nLang: {lang}\nTZ: {tz}\n"
        )

        try:
            send_mail(MAIL_TO, subject, body)  # あなたの受信用

            # 自動返信（ユーザー宛）— 不要ならコメントアウトOK
            try:
                ack_subj = f"【読み上げ対局時計】お問い合わせを受け付けました - {topic_display}"
                ack_body = (
                    f"{name} 様\n\n"
                    f"お問い合わせありがとうございます。以下の内容で受け付けました。\n\n"
                    f"カテゴリ: {topic_display}\n\n{msg}\n\n"
                    "このメールは送信専用です。返信が必要な場合は、追って担当よりご連絡します。"
                )
                send_mail(email, ack_subj, ack_body)
            except Exception:
                pass

            flash("お問い合わせを受け付けました。メールが届かない場合はアドレスが間違っている可能性がありますので再度ご送信ください。", "success")
        except Exception as e:
            print("Mail send error:", e)
            flash("送信に失敗しました。しばらくしてからお試しください。", "error")

        return redirect(url_for("contact"))

    return render_template("contact.html")

# =========================================
# API（任意）：/api/contact でJSON受付
# =========================================
@app.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not (name and email and message):
        return jsonify({"ok": False, "error": "必須項目が未入力です。"}), 400

    subject = "【読み上げ対局時計】お問い合わせ(API)"
    body    = f"お名前: {name}\nメール: {email}\n--- 本文 ---\n{message}\n"
    try:
        send_mail(MAIL_TO, subject, body)
        return jsonify({"ok": True, "msg": "送信を受け付けました。ありがとうございます！"}), 200
    except Exception as e:
        print("Mail send error(API):", e)
        return jsonify({"ok": False, "error": "送信に失敗しました。"}), 500

# =========================================
# ヘルスチェック
# =========================================
@app.route("/healthz")
def healthz():
    return "ok", 200

# =========================================
# エラーハンドラ
# =========================================
@app.errorhandler(404)
def not_found(e):
    try:
        return render_template("404.html"), 404
    except Exception:
        return "404 Not Found", 404

@app.errorhandler(500)
def server_error(e):
    try:
        return render_template("500.html"), 500
    except Exception:
        return "500 Internal Server Error", 500

# =========================================
# メール送信ユーティリティ
# =========================================
def send_mail(to_addr: str, subject: str, body: str):
    """シンプルなSMTP送信（UTF-8, SSL/STARTTLS自動）"""
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"]    = MAIL_FROM
    msg["To"]      = to_addr

    if SMTP_PORT == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as s:
            if SMTP_USER and SMTP_PASS:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo()
            try:
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
            except smtplib.SMTPException:
                pass
            if SMTP_USER and SMTP_PASS:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)

# =========================================
# ローカル起動（本番はgunicorn等で起動）
# =========================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
