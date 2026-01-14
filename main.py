import json
import argparse
import os
import re
import requests
import numpy as np
import yaml
import time
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, make_response, send_file
from subprocess import Popen, PIPE
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text
from urllib.parse import urlparse
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image, ExifTags
from pillow_heif import register_heif_opener
import string
import hashlib

# HEIFフォーマット（HEIC）のサポートを有効化
register_heif_opener()
import threading
import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask import abort
from pdfminer.pdfparser import PDFSyntaxError
import mimetypes
import random
import datetime as dt
import html
import uuid
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, HiddenField
from wtforms.validators import DataRequired
from flask_wtf.csrf import CSRFProtect, validate_csrf
from datetime import timedelta
import tldextract
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from pytube import YouTube
import yt_dlp
from bs4 import BeautifulSoup
from markdownify import markdownify as md

processing = False

# Load configuration from YAML file
with open('config.yaml', 'r') as config_file:
    config = yaml.safe_load(config_file)

app = Flask(__name__)

# CORS設定（API用）
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Authorization", "Content-Type"]
    }
})

# secret_keyの設定
app.secret_key = config['secret_key']

# CSRFトークンの有効期限を8時間に設定
app.config['WTF_CSRF_TIME_LIMIT'] = 28800  # 8時間（秒）

# Flask-Limiterの設定
limiter = Limiter(
    get_remote_address,
    app=app
)

# CSRF保護の設定
csrf = CSRFProtect(app)

# Flask-Loginの設定
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# セッションの保持時間を設定（7日間）
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)
# Remember Me Cookieのセキュリティ設定
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Strict'

# ユーザークラスの定義
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

# ユーザー情報のロード
@login_manager.user_loader
def load_user(user_id):
    user = config['users'].get(user_id)
    if user:
        return User(user_id, user['username'], user['password'])
    return None

# セキュアなURL検証関数
def is_safe_url(target):
    """
    nextパラメータが安全なURLかどうかを検証
    Open Redirect脆弱性を防ぐため、以下をチェック：
    - プロトコル相対URL (//evil.com) を拒否
    - 絶対URL (http://evil.com) を拒否
    - JavaScriptスキーム (javascript:) を拒否
    - バックスラッシュを含むURLを拒否
    """
    if not target:
        return False

    # スキームがある場合は拒否（http:, javascript: など）
    if ':' in target:
        return False

    # プロトコル相対URL（//evil.com）を拒否
    if target.startswith('//'):
        return False

    # バックスラッシュを含む場合は拒否（IEの挙動対策）
    if '\\' in target:
        return False

    # 相対パス以外を拒否
    if not target.startswith('/'):
        return False

    # urlparseでネットワークロケーション（ドメイン部分）が存在しないことを確認
    parsed = urlparse(target)
    if parsed.netloc:
        return False

    return True

# ログインフォームの定義
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# ログインルートの追加
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # 1分間に5回の試行を許可
def login():
    print(f"current_user.is_authenticated: {current_user.is_authenticated}")
    if request.method == 'GET' and current_user.is_authenticated:
        # 既にログイン済みの場合、nextパラメータがあればそこへ、なければpost_indexへ
        next_page = request.args.get('next')
        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for('post_index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        print("Form validated successfully.")
        username = form.username.data
        password = form.password.data
        print(f"Attempting login for user: {username}")
        for user_id, user in config['users'].items():
            print(f"Checking user: {user['username']}")
            if user['username'] == username:
                print(f"User found. Checking password...")
                if check_password_hash(user['password'], password):
                    print(f"Password match. Logging in user: {username}")
                    user_obj = User(user_id, user['username'], user['password'])

                    # サブドメイン対応のREMEMBER_COOKIE_DOMAIN設定
                    host = request.host
                    extracted = tldextract.extract(host)

                    if extracted.subdomain:
                        # サブドメインがある場合、メインドメイン全体に設定
                        cookie_domain = f".{extracted.domain}.{extracted.suffix}"
                    else:
                        # サブドメインがない場合、現在のドメインのみ
                        cookie_domain = f"{extracted.domain}.{extracted.suffix}"

                    app.config['REMEMBER_COOKIE_DOMAIN'] = cookie_domain

                    # Remember Me機能を有効にしてログイン（7日間保持）
                    login_user(user_obj, remember=True)

                    # send_email("Authentication Success", f"User {username} logged in successfully.\n\n{get_client_info()}")
                    with open('./access_log.txt', 'a') as log_file:
                        log_file.write(f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - User {username} logged in successfully - {get_client_info()}\n")

                    # ログイン時にキャッシュを削除（全件キャッシュ＋旧キャッシュ）
                    cache_file_old = './post/.cache/post_files_info.json'
                    cache_file_all = './post/.cache/post_files_info_all.json'
                    filelist_cache = './post/.cache/filelist.json'
                    for cf in [cache_file_old, cache_file_all, filelist_cache]:
                        if os.path.exists(cf):
                            os.remove(cf)
                            print(f"Removed cache file: {cf}")

                    # ログイン前にアクセスしようとしていたURLを取得
                    # GETパラメータとPOSTパラメータの両方をチェック
                    next_page = request.args.get('next') or request.form.get('next')
                    # nextパラメータが存在し、かつ安全なURLであることを確認（Open Redirect対策）
                    if next_page and is_safe_url(next_page):
                        redirect_url = next_page
                    else:
                        redirect_url = url_for('post_latest')

                    return redirect(redirect_url)
                else:
                    print(f"Password does not match for user: {username}")
        print("Login failed. Invalid credentials.")
        send_email("Authentication Failed", f"Failed login attempt for user {username}.\n\n{get_client_info()}")
        with open('./access_log.txt', 'a') as log_file:
            log_file.write(f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - User {username} Authentication Failed - {get_client_info()}\n")

        return render_template('login.html', form=form, error="Invalid credentials")
    else:
        print("Form validation failed.")
        for field, errors in form.errors.items():
            for error in errors:
                print(f"Error in {field}: {error}")
    return render_template('login.html', form=form)

# ログアウトルートの追加
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ルートの保護
# @app.route('/admin')
# @login_required
# def admin():
#     client_info = get_client_info()
#     send_email("Authentication Success", f"Admin page accessed successfully.\n\n{client_info}")
#     return redirect(url_for('post_index'))

@app.route('/protected')
@login_required
def protected():
    return "You are seeing this because you are authenticated."

# 401エラーハンドラの変更
@app.errorhandler(401)
def custom_401(error):
    client_info = get_client_info()
    send_email("Authentication Failed", f"Unauthorized access attempt detected.\n\n{client_info}")
    response = make_response(render_template('401.html', client_info=client_info), 401)
    return response


UPLOAD_FOLDER = './attach'
ALLOWED_EXTENSIONS = set(config['allowed_extensions'])

# Excluded string
EXCLUDE_STRING = config['exclude_string']

def send_email(subject, body):
    sender_email = config['gmail']['sender_email']
    recipient_email = config['gmail']['recipient_email']
    app_password = config['gmail']['app_password']

    # 初期値の場合はメール送信をスキップ
    if sender_email == "sender@gmail.com" or recipient_email == "recipient@example.com":
        print("Skipping email sending due to default configuration values.")
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")

def get_client_info():
    client_ip_waf = request.headers.get('X-Forwarded-For', None)
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    # return f"Client IP (WAF): {client_ip_waf}\nClient IP: {client_ip}\nUser Agent: {user_agent}\n"
    return f"{client_ip_waf} {client_ip} {user_agent}"

@app.route('/', methods=['GET'])
def index():
    authenticated = current_user.is_authenticated
    search_query = request.args.get('search')
    pdf_files = [f for f in os.listdir('./pdfs') if os.path.isfile(os.path.join('./pdfs', f)) and f.endswith('.pdf') and f != '.gitkeep']
    if not authenticated:
        # 認証されていない場合、特定の条件を満たすPDFのみをリストする
        pdf_files = [f for f in pdf_files if os.path.exists(os.path.join('./memo', f.replace('.pdf', '.txt')))]
        pdf_files = [f for f in pdf_files if len(open(os.path.join('./memo', f.replace('.pdf', '.txt'))).readlines()) >= 2]

    if search_query:
        search_terms = re.split(r'\s+', search_query)  # 半角・全角スペースで分割
        pdf_files = [f for f in pdf_files if is_text_matched(f, search_terms)]

    pdf_files_info = []
    for file in pdf_files:
        path = os.path.join('./pdfs', file)
        timestamp = os.path.getmtime(path)
        date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d (%a)')  # 人間が読める形式の日付
        summary_exists = os.path.exists(os.path.join('./summary', file.replace('.pdf', '.txt')))
        summary_url = file.replace('.pdf', '.txt')
        pdf_id = file.replace('.pdf', '')

        memo_exists = os.path.exists(os.path.join('./memo', file.replace('.pdf', '.txt')))
        memo1_title = ""
        memo2_content = ""
        if memo_exists:
            with open(os.path.join('./memo', file.replace('.pdf', '.txt')), 'r') as memo_file:
                memo_lines = memo_file.readlines()
                memo1_title = memo_lines[0].strip()  # 1行目をタイトルとして取得
                memo2_content = memo_lines[1:]  # 2行目以降を取得

        pdf_files_info.append({
            'filename': file, # xxx.pdf
            'url': os.path.join('/pdfs', file),
            'date': date_str,  # 人間が読める形式の日付を保持
            'timestamp': timestamp,  # ソート用のタイムスタンプを追加
            'summary_exists': summary_exists, #
            'summary_url': summary_url, # xxx.txt
            'memo_exists': memo_exists, # true/false
            'memo1_title': memo1_title, # メモ1行目、タイトル
            'memo2_content': memo2_content, # メモ2行目以降、メモ
            'pdf_id': pdf_id # xxx
            })

        # ファイルを日付で降順に並び替え
        pdf_files_info.sort(key=lambda x: x['timestamp'], reverse=True)

    return render_template('index.html', pdf_files=pdf_files_info, authenticated=authenticated)

@app.route('/<filename>')
def permalink(filename):
    pdf_filename = secure_filename(filename + '.pdf')
    path = os.path.join('./pdfs', pdf_filename)
    if not os.path.exists(path):
        abort(404)  # ファイルが存在しない場合は404エラーを返す

    timestamp = os.path.getmtime(path)
    date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d (%a)')
    summary_exists = os.path.exists(os.path.join('./summary', filename + '.txt'))
    summary_url = filename + '.txt'
    twittercard_url = filename + '.png'
    pdf_id = filename

    memo_exists = os.path.exists(os.path.join('./memo', filename + '.txt'))
    memo1_title = ""
    memo2_content = ""
    if memo_exists:
        with open(os.path.join('./memo', filename + '.txt'), 'r', encoding='utf-8') as memo_file:
            memo1_title = memo_file.readline().strip()
            lines = memo_file.readlines()
            authenticated = current_user.is_authenticated
            memo2_content = [line.strip() for line in lines if EXCLUDE_STRING not in line]


    pdf_info = {
        'url': os.path.join('/pdfs', pdf_filename),
        'date': date_str,
        'timestamp': timestamp,
        'summary_exists': summary_exists,
        'summary_url': summary_url,
        'memo_exists': memo_exists,
        'memo1_title': memo1_title,
        'memo2_content': memo2_content,
        'twittercard_url': twittercard_url,
        'pdf_id': pdf_id
    }

    authenticated = current_user.is_authenticated

    # 添付ファイル名を取得してテンプレートに返答
    attach_files = [f for f in os.listdir('./pdfs-attach') if filename in f]
    
    return render_template('permalink.html', pdf=pdf_info, attach_files=attach_files, authenticated=authenticated, config=config)


@login_required
@app.route('/pdfsattach/<filename>')
def pdfsattach(filename):
    if current_user.is_authenticated:
        file_path = os.path.join('./pdfs-attach', secure_filename(filename))
        if os.path.exists(file_path):
            return send_from_directory('./pdfs-attach', secure_filename(filename))
        else:
            abort(404)  # ファイルが存在しない場合は404エラーを返す
    else:
        abort(401)  # 認証が必要なエラーを返す
        

def is_text_matched(pdf_filename, search_terms):
    # PDFファイル名からテキストファイル名を生成
    txt_filename = pdf_filename.replace('.pdf', '.txt')
    
    # clean_textディレクトリ内のテキストファイルのパス
    clean_txt_path = os.path.join('./clean_text', txt_filename)
    # memoディレクト内のテキストファイルのパス
    memo_txt_path = os.path.join('./memo', txt_filename)
    
    # 検索対象のテキストファイルのパスリスト
    paths = [clean_txt_path, memo_txt_path]
    
    # 検索キーワードを小文字に変換
    search_terms = [term.lower() for term in search_terms]
    
    for path in paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read().lower()  # テキスト内容を小文字に変換
                # すべての検索キーワードがテキスト内容に含まれているかチェック
                if all(term in content for term in search_terms):
                    return True
    return False


def calculate_sha256(file_stream):
    sha256_hash = hashlib.sha256()
    for byte_block in iter(lambda: file_stream.read(4096), b""):
        sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def allowed_file(filename):
    # return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_required
@app.route('/attach_upload', methods=['POST'])
def attach_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        original_filename = file.filename
        file_ext = original_filename.rsplit('.', 1)[1].lower()
        file_content = file.read()
        file_hash = hashlib.sha256(file_content).hexdigest()
        new_filename = f"{file_hash}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, new_filename)

        with open(file_path, 'wb') as f:
            f.write(file_content)

        is_image = file_ext in {'jpg', 'jpeg', 'png', 'gif', 'svg', 'heic', 'heif'}
        file_url = f"/attach/{new_filename}"

        # HEIC/HEIF形式の場合はJPEGに変換
        if file_ext in {'heic', 'heif'}:
            try:
                # HEICファイルをPILで開く
                heic_image = Image.open(file_path)

                # JPEG用の新しいファイル名を生成
                jpeg_filename = f"{file_hash}.jpg"
                jpeg_path = os.path.join(UPLOAD_FOLDER, jpeg_filename)

                # RGBモードに変換（HEIC→JPEG変換時に必要な場合がある）
                if heic_image.mode in ('RGBA', 'LA', 'P'):
                    heic_image = heic_image.convert('RGB')

                # JPEG形式で保存（品質90%）
                heic_image.save(jpeg_path, 'JPEG', quality=90, optimize=True)

                # 元のHEICファイルを削除
                os.remove(file_path)

                # 以降の処理はJPEGファイルを使用
                file_path = jpeg_path
                new_filename = jpeg_filename
                file_url = f"/attach/{jpeg_filename}"

                print(f"HEIC→JPEG変換成功: {original_filename} -> {jpeg_filename}")
            except Exception as e:
                print(f"HEIC変換エラー: {str(e)}")
                # エラー時は元のファイルを削除してエラーを返す
                if os.path.exists(file_path):
                    os.remove(file_path)
                return jsonify({'error': f'HEIC変換に失敗しました: {str(e)}'}), 500

        if is_image and file_ext != 'svg':
            # Save a smaller size image with 's_' prefix if it's an image file (except SVG)
            image = Image.open(file_path)

            # EXIFデータを考慮して画像を回転
            try:
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == 'Orientation':
                        break
                exif = image._getexif()
                if exif is not None:
                    orientation = exif.get(orientation, None)
                    if orientation == 3:
                        image = image.rotate(180, expand=True)
                    elif orientation == 6:
                        image = image.rotate(270, expand=True)
                    elif orientation == 8:
                        image = image.rotate(90, expand=True)
            except (AttributeError, KeyError, IndexError):
                # EXIFデータがない場合は何もしない
                pass

            small_image = image.copy()
            small_image.thumbnail((500, 500), Image.Resampling.LANCZOS)
            small_filename = f"s_{new_filename}"
            small_file_path = os.path.join(UPLOAD_FOLDER, small_filename)
            small_image.save(small_file_path)
        elif is_image and file_ext == 'svg':
            # SVG files don't need thumbnail generation, just copy the original
            import shutil
            small_filename = f"s_{new_filename}"
            small_file_path = os.path.join(UPLOAD_FOLDER, small_filename)
            shutil.copy(file_path, small_file_path)

        return jsonify({'filename': original_filename, 'url': file_url, 'isImage': is_image})

    return jsonify({'error': 'File type not allowed'}), 400


@app.route('/attach/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, secure_filename(filename))


@login_required
@app.route('/upload', methods=['GET', 'POST'])
def file_upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'ファイルがありません'}), 400
        
        file = request.files['file']

        # アップロードされた際の元ファイル名を取得
        original_filename = file.filename

        if original_filename == '':
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        if file and allowed_file(original_filename):
            try:
                file.stream.seek(0)  # ファイルストリームをリセット
                file_hash = calculate_sha256(file.stream)
                file.stream.seek(0)  # ハッシュ計算後、ファイルストリームを再リセット
                filename = secure_filename(f"{file_hash}.pdf")
                save_path = os.path.join('./pdfs', filename)
                
                # 既に同名のファイルが存在するかを確認
                if os.path.exists(save_path):
                    # 存在する場合は何もしない（上書きしない＝タイムスタンプを更新しない)
                    print("already file exist.")
                else:
                    # 存在しない場合は保存
                    file.save(save_path)
                
                # Twitter CardのPNGを出力するディレクトリを指定
                output_dir = Path('./static/tw')
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # アップロードされたPDFファイルに対して処理を実行
                pdf_to_twitter_card(Path(save_path), output_dir)

                # /memoディレクトリにメモファイルを作成（ファイルがまだ存在しない場合のみ）
                memo_path = os.path.join('./memo', f"{file_hash}.txt")
                if not os.path.exists(memo_path):
                    with open(memo_path, 'w') as memo_file:
                        memo_file.write(original_filename + '\n')  # 1行目に元のファイル名を記載
                
                return jsonify({'message': 'ファイルがアップロードされました'}), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        else:
            return jsonify({'error': '許可されていないファイル形式です'}), 400
    
    elif request.method == 'GET':
        return render_template('upload.html')


def crop_and_resize_image(image, target_width, target_height):
    # 元の画像サイズ
    original_width, original_height = image.size
    
    # 目的のサイズに合わせてクロップするサイズを計算
    target_aspect_ratio = target_width / target_height
    original_aspect_ratio = original_width / original_height
    
    if target_aspect_ratio <= original_aspect_ratio:
        # 横長の画像の場合、縦を基準にして横をクロップ
        new_height = original_height
        new_width = int(target_aspect_ratio * new_height)
    else:
        # 縦長の画像の場合（通常は発生しないが念のため）
        new_width = original_width
        new_height = int(new_width / target_aspect_ratio)
    
    # 上部を基準にクロップ
    left = (original_width - new_width) // 2
    top = 0
    right = left + new_width
    bottom = top + new_height
    
    cropped_image = image.crop((left, top, right, bottom))
    
    # 目的のサイズにリサイズ
    resized_image = cropped_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    return resized_image

def pdf_to_twitter_card(pdf_path, output_dir):
    try:
        output_file_path = output_dir / (pdf_path.stem + '.png')
        
        # 出力ファイルがすでに存在する場合はスキップ
        if output_file_path.exists():
            print(f"スキップ: {output_file_path} は既に存在します。")
            return
        
        images = convert_from_path(pdf_path, first_page=1, last_page=1)
        
        if images:
            image = images[0]
            twitter_card_image = crop_and_resize_image(image, 600, 314)
            twitter_card_image.save(output_file_path, 'PNG')
            print(f"Twitter Cardが生成されました: {output_file_path}")
        else:
            print(f"PDFから画像を変換できませんでした: {pdf_path}")
    except Exception as e:
        print(f"エラーが発生しました。ファイル: {pdf_path}, エラー: {e}")

@app.route('/cleantextize', methods=['GET'])
def cleantextize():
    pdf_files = [f for f in os.listdir('./pdfs') if os.path.isfile(os.path.join('./pdfs', f)) and f.endswith('.pdf') and f != '.gitkeep']
    thread = threading.Thread(target=cleantextize_pdfs_async, args=(pdf_files,))
    thread.start()

    return jsonify({'message': 'Summarization started for the PDF files.'})

def extract_text_from_pdf(file_path):
    try:
        text = extract_text(file_path)
        return text
    except Exception as e:
        print(f"Error extracting text from {file_path}: {str(e)}")
        return ""

def clean_extracted_text(text):
    text = text.replace('-\n', '')
    text = re.sub(r'\s+', ' ', text)
    return text

def pdf_to_cleantext(pdf_path, clean_text_dir):
    try:
        extracted_text = extract_text_from_pdf(pdf_path)
        if not extracted_text:
            print(f"Failed to extract text from {pdf_path}")
            return False
        
        clean_text = clean_extracted_text(extracted_text)
        
        if not os.path.exists(clean_text_dir):
            os.makedirs(clean_text_dir)
        
        clean_text_filename = os.path.basename(pdf_path).replace('.pdf', '.txt')
        clean_text_path = os.path.join(clean_text_dir, clean_text_filename)
        
        with open(clean_text_path, 'w', encoding='utf-8') as file:
            file.write(clean_text)
        print(f"Created clean text file for: {os.path.basename(pdf_path)}")
        return True
    except Exception as e:
        print(f"Error processing {pdf_path}: {str(e)}")
        return False
    

def cleantextize_pdfs_async(pdf_files):
    untextize_files = [f for f in pdf_files if not os.path.exists(os.path.join('./clean_text', f.replace('.pdf', '.txt')))]
    
    processed_files = []
    for pdf_file in untextize_files:
        pdf_path = os.path.join('./pdfs', pdf_file)
        clean_text_dir = './clean_text'
        success = pdf_to_cleantext(pdf_path, clean_text_dir)
        if success:
            processed_files.append(pdf_file)
    
    unprocessed_files = set(untextize_files) - set(processed_files)
    if unprocessed_files:
        print("Retrying processing for unprocessed files:")
        cleantextize_pdfs_async(list(unprocessed_files))
    

# 静的ファイルへのルートを定義
@app.route('/pdfs/<filename>')
def pdf_file(filename):
    # if current_user.is_authenticated:
    #     return send_from_directory('./pdfs', secure_filename(filename))
    # else:
    #     abort(403)  # Forbiddenアクセス拒否

    return send_from_directory('./pdfs', secure_filename(filename))

@app.route('/tw/<path:filename>')
def tw(filename):
    directory = './static/tw'
    response = send_from_directory(directory, secure_filename(filename))
    
    # ファイル名からMIMEタイプを決定
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        response.headers.set('Content-Type', mime_type)
    
    # Content-Dispositionヘッダーを設定
    response.headers.set('Content-Disposition', f'inline; filename="{secure_filename(filename)}"')
    
    # その他必要なヘッダーをここで追加
    response.headers.set('Cache-Control', 'no-cache')
    response.headers.set('Keep-Alive', 'timeout=5, max=100')
    
    return response

class EditMemoForm(FlaskForm):
    content = TextAreaField('Content', validators=[DataRequired()])
    csrf_token = HiddenField()  # CSRFトークン用のフィールド

@app.route('/edit_memo/<filename>', methods=['GET', 'POST'])
def edit_memo(filename):
    form = EditMemoForm()
    txt_filename = secure_filename(filename.replace('.pdf', '.txt'))
    txt_path = os.path.join('./memo', txt_filename)
    
    if request.method == 'POST':
        content = request.form['content']
        with open(txt_path, 'w') as f:
            f.write(content)
        # return redirect(url_for('index'))
        return redirect(url_for('permalink', filename=filename.replace('.pdf', '')))

    if os.path.exists(txt_path):
        with open(txt_path, 'r') as f:
            content = f.read()
    else:
        content = ""

    return render_template('edit_memo.html', filename=txt_filename, content=content, form=form)

@app.route('/memo/<filename>')
def memo(filename):
    txt_path = os.path.join('./memo', secure_filename(filename))
    
    if not os.path.exists(txt_path):
        abort(404)  # ファイルが存在しない場合は404エラーを返す

    with open(txt_path, 'r', encoding='utf-8') as memo_file:
        lines = memo_file.readlines()
        content = ''.join(line for line in lines[2:] if EXCLUDE_STRING not in line)  # 3行目以降を取得し、特定の文字列を含む行を除外

    return content

@app.route('/delete', methods=['POST'])
@login_required
@csrf.exempt  # CSRFトークンの検証を免除
def delete_file():
    try:
        filename = request.form['filename']
        csrf_token = request.form['csrf_token']

        try:
            validate_csrf(csrf_token)
        except ValidationError:
            return jsonify({'error': 'Invalid CSRF token'}), 400

        # 削除するファイルのパスを構築
        paths = {
            'PDF File': os.path.join('./pdfs', secure_filename(filename)),
            'Attached Files': [os.path.join('./pdfs-attach', f) for f in os.listdir('./pdfs-attach') if f.startswith(secure_filename(filename.replace('.pdf', '')))],
            'Clean Text File': os.path.join('./clean_text', secure_filename(filename.replace('.pdf', '.txt'))),
            'Memo File': os.path.join('./memo', secure_filename(filename.replace('.pdf', '.txt'))),
            'Summary File': os.path.join('./summary', secure_filename(filename.replace('.pdf', '.txt'))),
            'Secondary Summary File': os.path.join('./summary2', secure_filename(filename.replace('.pdf', '.txt'))),
            'Twitter Card Image': os.path.join('./static/tw', secure_filename(filename.replace('.pdf', '.png')))
        }

        # 各ファイルの存在を確認し、存在する場合は削除
        deleted_files = []
        for file_type, path in paths.items():
            if isinstance(path, list):  # 添付ファイルの場合
                for file_path in path:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_files.append(f"{file_type}: {os.path.basename(file_path)}")
                        print(f"{file_type} at {file_path} was successfully deleted.")
                    else:
                        print(f"{file_type} at {file_path} does not exist.")
            elif os.path.exists(path):
                os.remove(path)
                deleted_files.append(file_type)
                print(f"{file_type} at {path} was successfully deleted.")
            else:
                print(f"{file_type} at {path} does not exist.")

        if deleted_files:
            return jsonify({'message': f'{filename} の以下のファイルが削除されました: {", ".join(deleted_files)}'}), 200
        else:
            return jsonify({'message': f'{filename} に関連するファイルが見つかりませんでした。'}), 404

    except Exception as e:
        print(f"Error in delete_file: {str(e)}")
        return jsonify({'error': f'ファイルの削除中にエラーが発生しました: {str(e)}'}), 500

@app.route('/clean_text/<filename>')
def clean_text_file(filename):
    txt_filename = secure_filename(filename.replace('.pdf', '.txt'))
    print(txt_filename)
    return send_from_directory('./clean_text', txt_filename)
    
@app.route('/move_to_top/<filename>', methods=['GET'])
def move_to_top(filename):
    pdf_path = os.path.join('./pdfs', secure_filename(filename + '.pdf'))
    if os.path.exists(pdf_path):
        # os.utime()を使用してファイルのタイムスタンプを更新
        current_time = time.time()
        os.utime(pdf_path, (current_time, current_time))
        return redirect(url_for('index'))
    else:
        return jsonify({'message': 'エラー'})

@app.route('/post')
def post_index():
    form = LoginForm()  # フォームオブジェクトを作成
    authenticated = current_user.is_authenticated
    sorted_post_files_info = get_sorted_post_files_info()  # あなたのロジックに従ってデータを取得

    return render_template('post_index.html', post_files=sorted_post_files_info, authenticated=authenticated, form=form)

def get_file_metadata(file_path):
    print(f"Reading metadata from: {file_path}")
    """ファイルから必要な情報のみを取得"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            first_line = file.readline().strip()  # タイトル
            second_line = file.readline().strip() # タグ
            return {
                'title': first_line,
                'tags': second_line,
                'timestamp': os.path.getmtime(file_path)
            }
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return {
            'title': '',
            'tags': '',
            'timestamp': 0
        }

def get_sorted_post_files_info():
    """投稿ファイルの情報を取得（常に全件をキャッシュし、返却時に認証でフィルタ）"""
    CACHE_FILE = './post/.cache/post_files_info_all.json'
    FILELIST_CACHE = './post/.cache/filelist.json'
    search_query = request.args.get('search')
    authenticated = current_user.is_authenticated
    
    # 検索なしのときはキャッシュ（全件）を利用
    if not search_query:
        if os.path.exists(CACHE_FILE) and os.path.exists(FILELIST_CACHE):
            try:
                current_files = set(
                    f for f in os.listdir('./post')
                    if os.path.isfile(os.path.join('./post', f)) and not f.endswith('.gitkeep')
                )
                with open(FILELIST_CACHE, 'r') as f:
                    cached_files = set(json.load(f))
                if current_files == cached_files:
                    with open(CACHE_FILE, 'r') as f:
                        all_cached = json.load(f)  # 全件
                    if not authenticated:
                        filtered = {}
                        for topic, files in all_cached.items():
                            visible = [it for it in files if not it.get('title', '').startswith('#')]
                            if visible:
                                filtered[topic] = visible
                        return filtered
                    return all_cached
            except Exception as e:
                print(f"Error reading cache: {e}")

    print("Generating new cache")
    topic_files = {}
    post_dir = './post'
    post_files = [
        f for f in os.listdir(post_dir)
        if os.path.isfile(os.path.join(post_dir, f)) and not f.endswith('.gitkeep')
    ]

    for filename in post_files:
        file_path = os.path.join(post_dir, filename)
        
        if search_query:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read().lower()
                first_line = content.split('\n')[0].strip()
                second_line = content.split('\n')[1].strip() if len(content.split('\n')) > 1 else ""
            except Exception as e:
                print(f"Error reading file for search {file_path}: {e}")
                continue
        else:
            metadata = get_file_metadata(file_path)
            first_line = metadata['title']
            second_line = metadata['tags']
            content = ""

        # トピックを抽出
        topic_match = re.match(r'\[(.*?)\]', filename)
        topic = topic_match.group(1) if topic_match else '_トピック未設定'

        if topic not in topic_files:
            topic_files[topic] = []

        file_info = {
            'filename': filename,
            'title': first_line,
            'tags': second_line,
            'timestamp': os.path.getmtime(file_path)
        }

        if search_query:
            file_info['content'] = content

        topic_files[topic].append(file_info)

    post_files_info = {topic: files for topic, files in topic_files.items() if files}

    if search_query:
        search_terms = search_query.lower().split()
        filtered_info = {}
        for topic, files in post_files_info.items():
            filtered_files = [file for file in files if any(term in file.get('content', '') for term in search_terms)]
            if filtered_files:
                filtered_info[topic] = filtered_files
        post_files_info = filtered_info

    for topic in post_files_info:
        post_files_info[topic].sort(key=lambda x: x['filename'])
    all_sorted = dict(sorted(post_files_info.items()))

    if not search_query:
        try:
            cache_dir = os.path.dirname(CACHE_FILE)
            os.makedirs(cache_dir, exist_ok=True)
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_sorted, f, ensure_ascii=False, indent=2)
            current_files = [
                f for f in os.listdir('./post')
                if os.path.isfile(os.path.join('./post', f)) and not f.endswith('.gitkeep')
            ]
            with open(FILELIST_CACHE, 'w', encoding='utf-8') as f:
                json.dump(current_files, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error writing cache: {e}")

    if not authenticated:
        filtered = {}
        for topic, files in all_sorted.items():
            visible = [it for it in files if not it.get('title', '').startswith('#')]
            if visible:
                filtered[topic] = visible
        return filtered
    return all_sorted

def is_valid_filename(filename):
    # ファイル名がディレクトリトラバーサルを含まないかチェック
    if '..' in filename or filename.startswith('/'):
        return False
    
    # ファイル名が有効な文字のみを含むかチェック
    if not re.match(r'^[^/\\:*?"<>|]+\.txt$', filename):
        return False
    
    return True

@app.route('/post/<filename>')
def post(filename):
    authenticated = current_user.is_authenticated
    
    # ファイル名の安全性を手動で確認
    if not is_valid_filename(filename):
        abort(400)  # 無効なファイル名の場合は400エラーを返す

    path = os.path.join('./post', filename)
    if not os.path.exists(path):
        auth = current_user.is_authenticated
        if auth:
            # 認証されている場合、編集画面へリダイレクト
            return redirect(url_for('edit_post', filename=filename))
        else:
            # 認証されていない場合、404エラーを返す
            abort(404)

    with open(path, 'r', encoding='utf-8', errors='ignore') as memo_file:
        lines = memo_file.readlines()
        title = html.escape(lines[0].strip()) if lines else ""
        tags = html.escape(lines[1].strip()) if len(lines) > 1 else ""
        markdown = html.escape(''.join(lines[2:]))  # 3行目以降を抽出

    # 1行目が##で始まる場合は認証されていない場合に返答しない
    if not authenticated and title.startswith('##'):
        abort(404)

    content = {
        'markdown': markdown,
        'filename': filename,
        'title': title,
        'tags': tags
    }

    # 認証済みの場合のみページ切り替え用の最新投稿リストを取得
    recent_posts = get_latest_posts(limit=20, exclude=filename) if authenticated else []

    return render_template('post.html', content=content, authenticated=authenticated, recent_posts=recent_posts)

@app.route('/postmd/<filename>')
def markdown_file(filename):
    authenticated = current_user.is_authenticated
    
    # ファイル名の安全性を手動で確認
    if not is_valid_filename(filename):
        abort(400)  # 無効なファイル名の場合は400エラーを返す

    path = os.path.join('./post', filename)
    if not os.path.exists(path):
        auth = current_user.is_authenticated
        if auth:
            # 認証されている場合、編集画面へリダイレクト
            return redirect(url_for('edit_post', filename=filename))
        else:
            # 認証されていない場合、404エラーを返す
            abort(404)

    with open(path, 'r', encoding='utf-8', errors='ignore') as memo_file:
        lines = memo_file.readlines()
        markdown = ''.join(lines)  # 全ての行を結合して返す

    # 1行目が##で始まる場合は認証されていない場合に返答しない
    title = lines[0].strip() if lines else ""
    if not authenticated and title.startswith('##'):
        abort(404)

    return markdown, 200, {'Content-Type': 'text/plain; charset=utf-8'}

class EditPostForm(FlaskForm):
    content = TextAreaField('Content', validators=[DataRequired()])
    csrf_token = HiddenField()  # CSRFトークン用のフィールド

@app.route('/edit_post/<filename>', methods=['GET', 'POST'])
@login_required
def edit_post(filename):
    form = EditPostForm()  # フォームオブジェクトを作成
    # ファイル名の安全性を手動で確認
    if not is_valid_filename(filename):
        abort(400)  # 無効なファイル名の場合は400エラーを返す

    post_path = os.path.join('./post', filename)
    backup_dir = './post/bk'
    os.makedirs(backup_dir, exist_ok=True)
    
    if request.method == 'POST' and form.validate_on_submit():
        content = form.content.data
        with open(post_path, 'w', encoding='utf-8', errors='replace') as f:
            f.write(content)
        
        # 日時（年月日-時）形式のタイムスタンプを取得
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H')
        backup_filename = f"{filename}_{timestamp}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # バックアップディレクトリ保存
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        # キャッシュファイルを削除して強制的に再生成を促す（全件キャッシュ＋旧キャッシュ）
        cache_file_old = './post/.cache/post_files_info.json'
        cache_file_all = './post/.cache/post_files_info_all.json'
        filelist_cache = './post/.cache/filelist.json'
        for cf in [cache_file_old, cache_file_all, filelist_cache]:
            if os.path.exists(cf):
                os.remove(cf)
                print(f"Removed cache file: {cf}")
        
        # .txtを空文字列に置換して削除
        filename_without_txt = filename.replace('.txt', '')
        return redirect(f'/post/{filename}')

    if os.path.exists(post_path):
        with open(post_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            # 1行目からタイトルを抽出（#を除去）
            first_line = content.split('\n')[0] if content else ""
            title = first_line.lstrip('#').strip()
            content = content.replace('\n', '\\n')  # 改行をエスケープ文字に置換
            content = html.escape(content)  # HTMLエスケープ処理
    else:
        content = ""
        title = "新規ファイル"

    # 最新20件を取得（現在編集中のファイルを除外）
    recent_posts = get_latest_posts(limit=20, exclude=filename)

    return render_template('edit_post.html', filename=filename, content=content, title=title, form=form, recent_posts=recent_posts, claude_code_url=config.get('claude_code_url', ''))

class UploadTextForm(FlaskForm):
    content = TextAreaField('Content', validators=[DataRequired()])

@app.route('/upload_text', methods=['GET', 'POST'])
@login_required
def upload_text():
    form = UploadTextForm()
    if request.method == 'POST':
        files = request.files.getlist('files[]')
        for file in files:
            if file:
                content = file.read().decode('utf-8')
                if content.strip():  # 空でないことを確認
                    first_line = content.split('\n', 1)[0]
                    if first_line:
                        timestamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
                        new_filename = f"{timestamp}-{files.index(file)}.txt"
                        new_filepath = os.path.join('./post', new_filename)
                        
                        with open(new_filepath, 'w', encoding='utf-8') as f:
                            f.write(f"##{file.filename}\n\n{content}")
                else:
                    print(f'ファイル {file.filename} は空です。スキップします。')
            else:
                print(f'ファイル {file.filename} は無効です。スキップします。')
        return jsonify({'message': 'ファイルがアップロードされました。'}), 200

    return render_template('upload_text.html', form=form)


@app.route('/postdata/<filename>')
def postdata(filename):
    # ファイル名の安全性を手動で確認
    if not is_valid_filename(filename):
        abort(400)  # 無効なファイル名の場合は400エラーを返す

    path = os.path.join('./post', filename)
    if not os.path.exists(path):
        abort(404)

    with open(path, 'r', encoding='utf-8', errors='ignore') as memo_file:
        lines = memo_file.readlines()
        title = lines[0].strip() if lines else ""
        markdown = ''.join(lines[2:])  # 3行目以降を抽出

    authenticated = current_user.is_authenticated

    # 非公開の場合は認証されていない場合に出力しない
    if not authenticated and title.startswith('##'):
        abort(404)

    # 画像リンクのMarkdownパターンを除外
    markdown = re.sub(r'!\[.*?\]\(/attach/.*?\)', '', markdown)
    # [](...)形式のリンクも除外
    markdown = re.sub(r'\[.*?\]\(/attach/.*?\)', '', markdown)

    return markdown


@app.route('/rename_post', methods=['POST'])
@login_required
def rename_post():
    old_filename = request.form['old_filename']
    new_filename = request.form['new_filename'] + '.txt'
    
    # ファイル名の安全性を手動で確認
    if not is_valid_filename(old_filename):
        return jsonify({'error': '無効な元のファイル名です。'}), 400
    if not is_valid_filename(new_filename):
        return jsonify({'error': '無効な新しいファイル名です。'}), 400


    old_path = os.path.join('./post', old_filename)
    new_path = os.path.join('./post', new_filename)
    
    if os.path.exists(old_path):
        if os.path.exists(new_path):
            return jsonify({'error': '新しいファイル名は既に存在します。'}), 400
        os.rename(old_path, new_path)
        return jsonify({'success': 'ファイル名が変更されました。'}), 200
    else:
        return jsonify({'error': '元のファイルが存在しません。'}), 404

@app.route('/add_post', methods=['POST'])
@login_required
def add_post():
    date_string = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f"[__]{date_string}.txt"
    file_path = os.path.join('./post', filename)
    
    with open(file_path, 'w') as new_file:
        new_file.write("##タイトル未設定\n\n")
    
    return redirect(url_for('edit_post', filename=filename))

@app.route('/delete_post', methods=['POST'])
@login_required
def delete_post():
    filename = request.form['filename']
    # ファイル名の安全性を手動で確認
    if not is_valid_filename(filename):
        return jsonify({'error': '無効なファイル名です。'}), 400

    file_path = os.path.join('./post', filename)
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return jsonify({'success': 'ファイルが削除されました。'}), 200
        except Exception as e:
            return jsonify({'error': f'ファイルの削除に失敗しました: {str(e)}'}), 500
    else:
        return jsonify({'error': f'ファイルが存在しません。{filename}'}), 404

@app.route('/archive_post', methods=['POST'])
@login_required
def archive_post():
    filename = request.form['filename']
    if not is_valid_filename(filename):
        return jsonify({'error': '無効なファイル名です。'}), 400

    file_path = os.path.join('./post', filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'ファイルが存在しません。'}), 404

    try:
        # ファイル名の先頭の[]内の文字列を_archivedに置換
        new_filename = re.sub(r'^\[(.*?)\]', '[_archived]', filename)
        new_path = os.path.join('./post', new_filename)
        
        os.rename(file_path, new_path)
        return jsonify({'success': 'ファイルがアーカイブされました。'}), 200
    except Exception as e:
        return jsonify({'error': f'アーカイブに失敗しました: {str(e)}'}), 500

@app.route('/duplicate_post', methods=['POST'])
@login_required
def duplicate_post():
    filename = request.form['filename']
    if not is_valid_filename(filename):
        return jsonify({'error': '無効なファイル名です。'}), 400

    original_path = os.path.join('./post', filename)
    new_filename = filename.replace('.txt', '(copy).txt')
    new_path = os.path.join('./post', new_filename)

    if os.path.exists(original_path):
        try:
            with open(original_path, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(new_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return jsonify({'success': 'ファイルが複製されました。'}), 200
        except Exception as e:
            return jsonify({'error': f'ファイルの複製に失敗しました: {str(e)}'}), 500
    else:
        return jsonify({'error': 'ファイルが存在しません。'}), 404

@app.route('/get_categories', methods=['GET'])
@login_required
def get_categories():
    """既存のカテゴリ一覧を取得"""
    try:
        post_dir = './post'
        post_files = [f for f in os.listdir(post_dir)
                      if os.path.isfile(os.path.join(post_dir, f))
                      and not f.endswith('.gitkeep')]

        categories = set()
        for filename in post_files:
            topic_match = re.match(r'\[(.*?)\]', filename)
            if topic_match:
                category = topic_match.group(1)
                # _archivedは除外
                if category != '_archived':
                    categories.add(category)

        # アルファベット順にソート
        sorted_categories = sorted(list(categories))
        return jsonify({'categories': sorted_categories}), 200
    except Exception as e:
        return jsonify({'error': f'カテゴリ取得に失敗しました: {str(e)}'}), 500

@app.route('/change_category', methods=['POST'])
@login_required
def change_category():
    """ファイルのカテゴリを変更"""
    filename = request.form['filename']
    new_category = request.form.get('new_category', '').strip()

    if not is_valid_filename(filename):
        return jsonify({'error': '無効なファイル名です。'}), 400

    if not new_category:
        return jsonify({'error': 'カテゴリ名を入力してください。'}), 400

    # カテゴリ名のバリデーション（特殊文字を禁止）
    if not re.match(r'^[a-zA-Z0-9_\-ぁ-んァ-ヶー一-龯]+$', new_category):
        return jsonify({'error': 'カテゴリ名に使用できない文字が含まれています。'}), 400

    file_path = os.path.join('./post', filename)

    if not os.path.exists(file_path):
        return jsonify({'error': 'ファイルが存在しません。'}), 404

    try:
        # 新しいファイル名を生成
        # 既存のカテゴリがある場合は置換、ない場合は先頭に追加
        if re.match(r'^\[.*?\]', filename):
            new_filename = re.sub(r'^\[(.*?)\]', f'[{new_category}]', filename)
        else:
            new_filename = f'[{new_category}]{filename}'

        new_path = os.path.join('./post', new_filename)

        # 元のファイル名と新しいファイル名が同じ場合は何もしない
        if filename == new_filename:
            return jsonify({'success': 'カテゴリは既に同じです。', 'new_filename': new_filename}), 200

        # 既に同名のファイルが存在する場合はエラー（元のファイルとは別のファイル）
        if os.path.exists(new_path):
            return jsonify({'error': '変更後のファイル名は既に存在します。'}), 400

        # ファイルをリネーム
        os.rename(file_path, new_path)

        # キャッシュをクリア
        cache_file_old = './post/.cache/post_files_info.json'
        cache_file_all = './post/.cache/post_files_info_all.json'
        filelist_cache = './post/.cache/filelist.json'
        for cf in [cache_file_old, cache_file_all, filelist_cache]:
            if os.path.exists(cf):
                os.remove(cf)

        return jsonify({'success': 'カテゴリが変更されました。', 'new_filename': new_filename}), 200
    except Exception as e:
        return jsonify({'error': f'カテゴリ変更に失敗しました: {str(e)}'}), 500

# Helper functions for AI presets
def load_json_file(filepath):
    """Load JSON file, return empty dict if not found"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}

def save_json_file(filepath, data):
    """Save data to JSON file"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False

@app.route('/ai_presets', methods=['GET'])
@login_required
def get_ai_presets():
    """AIプリセットとテンプレートを取得"""
    system_prompts = load_json_file('./ai_presets/system_prompts.json')
    prompt_templates = load_json_file('./ai_presets/prompt_templates.json')
    user_presets = load_json_file('./ai_presets/user_presets.json')

    return jsonify({
        'system_prompts': system_prompts,
        'prompt_templates': prompt_templates,
        'user_presets': user_presets
    })

@app.route('/ai_presets/system_prompt', methods=['POST'])
@login_required
def save_system_prompt():
    """システムプロンプトの選択を保存"""
    data = request.json
    preset_id = data.get('preset_id')

    if not preset_id:
        return jsonify({'error': 'preset_idが必要です'}), 400

    user_presets = load_json_file('./ai_presets/user_presets.json')
    user_presets['selected_system_prompt'] = preset_id

    if save_json_file('./ai_presets/user_presets.json', user_presets):
        return jsonify({'success': True})
    else:
        return jsonify({'error': '設定の保存に失敗しました'}), 500

@app.route('/ai_assist', methods=['POST'])
@login_required
def ai_assist():
    """AI編集アシスタント機能（システムプロンプト対応）"""
    data = request.json
    prompt = data.get('prompt', '')
    context = data.get('context', '')
    system_prompt_id = data.get('system_prompt_id', 'default')

    # config.yamlから設定を読み込み
    api_key = config.get('openai_api_key')
    model = config.get('ai_model', 'gpt-4o-mini')  # デフォルトはgpt-4o-mini

    if not api_key:
        return jsonify({'error': 'OpenAI APIキーが設定されていません'}), 500

    if not prompt:
        return jsonify({'error': 'プロンプトが空です'}), 400

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        # システムプロンプトの取得
        system_prompts = load_json_file('./ai_presets/system_prompts.json')
        system_prompt_content = "あなたは優秀な編集アシスタントです。簡潔で分かりやすい回答を心がけてください。"

        if system_prompt_id in system_prompts:
            system_prompt_content = system_prompts[system_prompt_id].get('content', system_prompt_content)

        # メッセージ構築
        if context:
            # テキスト選択時: コンテキスト付き
            messages = [
                {"role": "system", "content": system_prompt_content},
                {"role": "user", "content": f"以下のテキストに関して：\n\n{context}\n\n{prompt}"}
            ]
        else:
            # 未選択時: コンテキストなし
            messages = [
                {"role": "system", "content": system_prompt_content},
                {"role": "user", "content": prompt}
            ]

        # OpenAI APIを呼び出し
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )

        ai_response = response.choices[0].message.content
        return jsonify({'response': ai_response}), 200

    except Exception as e:
        return jsonify({'error': f'AI処理に失敗しました: {str(e)}'}), 500

@app.route('/add_comment', methods=['POST'])
@login_required
def add_comment():
    filename = request.form.get('filename')
    comment = request.form.get('comment', '').strip()
    position = request.form.get('position', 'top')

    # バリデーション
    if not is_valid_filename(filename):
        return jsonify({'error': '無効なファイル名です。'}), 400

    if not comment:
        return jsonify({'error': 'コメントが空です。'}), 400

    file_path = os.path.join('./post', filename)

    if not os.path.exists(file_path):
        return jsonify({'error': 'ファイルが存在しません。'}), 404

    try:
        # ファイル読み込み
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        # コメント行を作成
        new_comment = f"- {comment}\n"

        # 位置に応じて挿入
        if position == 'top':
            # 3行目に挿入（先頭）
            title = lines[0] if len(lines) > 0 else "\n"
            tags = lines[1] if len(lines) > 1 else "\n"
            body = lines[2:] if len(lines) > 2 else []

            new_content = [title, tags, new_comment] + body
        else:  # position == 'bottom'
            # 末尾に追加
            new_content = lines + [new_comment]

        # ファイル書き込み
        with open(file_path, 'w', encoding='utf-8', errors='replace') as f:
            f.writelines(new_content)

        # キャッシュ削除
        cache_file_old = './post/.cache/post_files_info.json'
        cache_file_all = './post/.cache/post_files_info_all.json'
        filelist_cache = './post/.cache/filelist.json'
        for cf in [cache_file_old, cache_file_all, filelist_cache]:
            if os.path.exists(cf):
                os.remove(cf)

        return jsonify({'success': 'コメントが追加されました。'}), 200
    except Exception as e:
        return jsonify({'error': f'コメント追加に失敗しました: {str(e)}'}), 500


@app.route('/summary/<filename>')
def summary(filename):
    path = os.path.join('./summary', secure_filename(filename))
    if not os.path.exists(path):
        auth = current_user.is_authenticated
        if auth:
            # 認証されている場合、編集画面へリダイレクト
            return redirect(url_for('edit_summary', filename=filename))
        else:
            # 認証されていない場合、404エラーを返す
            abort(404)

    with open(path, 'r') as memo_file:
        markdown = memo_file.read()

    content = {
        'markdown': markdown,
        'filename': filename
    }

    authenticated = current_user.is_authenticated
    
    return render_template('summary.html', content=content, authenticated=authenticated)

class EditSummaryForm(FlaskForm):
    content = TextAreaField('Content', validators=[DataRequired()])
    csrf_token = HiddenField()  # CSRFトークン用のフィールド

@app.route('/edit_summary/<filename>', methods=['GET', 'POST'])
@login_required  # Add this decorator
def edit_summary(filename):
    form = EditSummaryForm()
    txt_path = os.path.join('./summary', secure_filename(filename))
    
    if request.method == 'POST':
        content = request.form['content']
        with open(txt_path, 'w') as f:
            f.write(content)
        # .txtを空文字列に置換して削除
        filename_without_txt = filename.replace('.txt', '')
        return redirect(url_for('permalink', filename=filename_without_txt))

    if os.path.exists(txt_path):
        with open(txt_path, 'r') as f:
            content = f.read()
    else:
        content = ""

    return render_template('edit_summary.html', filename=filename, content=content, form=form)


@app.route('/summary2/<filename>')
def summary2(filename):
    path = os.path.join('./summary2', secure_filename(filename))
    if not os.path.exists(path):
        auth = current_user.is_authenticated
        if auth:
            # 認証されている場合、編集画面へリダイレクト
            return redirect(url_for('edit_summary2', filename=filename))
        else:
            # 認証されていない場合、404エラーを返す
            abort(404)

    with open(path, 'r') as memo_file:
        markdown = memo_file.read()

    content = {
        'markdown': markdown,
        'filename': filename
    }

    authenticated = current_user.is_authenticated
    
    return render_template('summary2.html', content=content, authenticated=authenticated)

@app.route('/edit_summary2/<filename>', methods=['GET', 'POST'])
@login_required  # Add this decorator
def edit_summary2(filename):
    form = EditSummaryForm()
    txt_path = os.path.join('./summary2', secure_filename(filename))
    
    if request.method == 'POST':
        content = request.form['content']
        with open(txt_path, 'w') as f:
            f.write(content)
        # .txtを空文字列に置換して削除
        filename_without_txt = filename.replace('.txt', '')
        return redirect(url_for('permalink', filename=filename_without_txt))

    if os.path.exists(txt_path):
        with open(txt_path, 'r') as f:
            content = f.read()
    else:
        content = ""

    return render_template('edit_summary2.html', filename=filename, content=content, form=form)

@app.route('/youtube', methods=['GET', 'POST'])
@login_required
def youtube():
    form = UploadTextForm()  # フォームオブジェクトを作成
    global processing
    if request.method == 'POST':
        if processing:
            return jsonify({"status": "processing"}), 202
        
        youtube_url = request.form['youtube_url']
        interval_sec = request.form.get('interval_sec', 10)
        
        processing = True
        process = Popen(['python', 'create_youtubemd.py', youtube_url, str(interval_sec)], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        processing = False
        if process.returncode != 0:
            print(f"Error: {stderr.decode('utf-8')}")
            return jsonify({"status": "error", "message": stderr.decode('utf-8')}), 500
        
        return redirect(url_for('youtube'))

    return render_template('youtube.html', form=form)


@app.route('/upload_movie', methods=['GET', 'POST'])
@login_required
def upload_movie():
    form = UploadTextForm()  # フォームオブジェクトを作成
    if request.method == 'POST':
        if 'movie_file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        movie_file = request.files['movie_file']
        if movie_file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        interval_sec = request.form.get('interval_sec', 10)
        interval_sec = int(interval_sec)

        if movie_file:
            # UUIDでファイル名を生成
            filename = f"{uuid.uuid4()}.mp4"
            file_path = os.path.join('./', filename)  # 同じディレクトリに保存
            movie_file.save(file_path)

            # create_youtubemd.pyをサブプロセスとして実行
            command = f"python create_youtubemd.py {file_path} {interval_sec}"
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                return jsonify({'error': stderr.decode('utf-8')}), 500

            # 正常処理後にファイルを削除
            os.remove(file_path)
            mp3_file_path = file_path.replace('.mp4', '.mp3')
            if os.path.exists(mp3_file_path):
                os.remove(mp3_file_path)

            return render_template('upload_movie.html', message='変換処理が完了しました。', form=form)

    return render_template('upload_movie.html', form=form)

def download_video_with_pytube(url):
    try:
        yt = YouTube(url)
        title = yt.title  # 動画のタイトルを取得
        stream = yt.streams.filter(file_extension='mp4').get_highest_resolution()
        filename = f"{uuid.uuid4()}.mp4"
        stream.download(filename=filename)
        print("Downloaded with pytube")
        return filename, title  # タイトルも返すように変更
    except Exception as e:
        print(f"pytube failed: {e}")
        return None, None

def download_video_with_ytdlp(url):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': '%(id)s.%(ext)s',
        'noplaylist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)
            title = info_dict.get('title', None)
            print("Downloaded with yt-dlp")
            return filename, title
    except Exception as e:
        print(f"yt-dlp failed: {e}")
        return None, None

class YouTubeDownloadForm(FlaskForm):
    url = StringField('YouTube URL', validators=[DataRequired()])
    submit = SubmitField('Download')

@app.route('/ytdl', methods=['GET', 'POST'])
@login_required
def ytdl():
    form = YouTubeDownloadForm()
    if form.validate_on_submit():
        url = form.url.data
        filename, title = download_video_with_pytube(url)
        if filename is None:
            print("Trying to download with yt-dlp...")
            filename, title = download_video_with_ytdlp(url)
        
        if filename is not None:
            # 安全なファイル名を作成
            safe_title = "".join([c if c.isalnum() else "_" for c in title]) + ".mp4"
            response = send_file(filename, as_attachment=True, download_name=safe_title)
            
            # ダウンロードが終わったらローカルファイルを削除
            os.remove(filename)
            return response
        else:
            return "Failed to download the video with both pytube and yt-dlp.", 500

    return render_template('ytdl.html', form=form)


class UploadTextForm(FlaskForm):
    web_url = TextAreaField('WebページURL', validators=[DataRequired()])  # TextAreaFieldに変更
    submit = SubmitField('送信')

@app.route('/webtomd', methods=['GET', 'POST'])
@login_required
def webtomd():
    form = UploadTextForm()
    message = ''
    if request.method == 'POST':
        web_urls = form.web_url.data.splitlines()  # 複数行のURLを取得
        success_count = 0
        error_count = 0
        for web_url in web_urls:
            if not web_url.strip():
                continue
            try:
                response = requests.get(web_url.strip(), allow_redirects=True)
                response.encoding = 'utf-8'  # エンコーディングをUTF-8に設定
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser', from_encoding='utf-8')
                
                # JavaScriptタグを削除
                for script in soup(["script", "style"]):
                    script.decompose()
                
                markdown_text = md(str(soup).replace('\n', ''))
                
                # HTMLからタイトルを取得し、ファイル名に変換
                title = soup.title.string if soup.title else 'untitled'
                file_name = f"[web]{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
                file_path = os.path.join('./post', file_name)
                
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write('##' + web_url.strip() + '\n' + markdown_text)
                
                success_count += 1
            except requests.exceptions.RequestException as e:
                error_count += 1
                print(f"Error processing URL {web_url.strip()}: {e}")
            
            time.sleep(1)  # 1秒のタイムアウトを入れる
        
        message = f"{success_count}件のファイルが変換され、{error_count}件のファイルがエラーになりました。"
        return render_template('webtomd.html', form=form, message=message)
    
    return render_template('webtomd.html', form=form, message=message)

@app.route('/post_latest')
@login_required
def post_latest():
    form = LoginForm()
    authenticated = current_user.is_authenticated
    sorted_posts = get_posts_by_date_periods()
    return render_template('post_latest.html', posts=sorted_posts, authenticated=authenticated, form=form)

@app.route('/postlist')
@login_required
def post_list():
    """コンパクトリスト形式の投稿一覧（日付順/カテゴリ別切り替え対応）"""
    form = LoginForm()
    authenticated = current_user.is_authenticated
    view_mode = request.args.get('view', 'date')  # 'date' or 'category'
    search_query = request.args.get('search')

    if view_mode == 'category':
        # カテゴリ別表示
        all_posts = get_posts_by_category_with_relative_time()
        group_counts = {cat: len(files) for cat, files in all_posts.items()}

        if search_query:
            # 検索時は全データ
            posts = all_posts
        else:
            # 初期表示: カテゴリ「_」のみ
            posts = {}
            for cat, files in all_posts.items():
                if cat == '_':
                    posts[cat] = files
                else:
                    posts[cat] = []  # 空（遅延取得）
    else:
        # 日付順表示（デフォルト）
        all_posts = get_posts_by_date_periods()
        group_counts = {period: len(files) for period, files in all_posts.items()}

        if search_query:
            # 検索時は全データ
            posts = all_posts
        else:
            # 初期表示: week のみ
            posts = {
                'week': all_posts.get('week', []),
                'month': [],      # 空（遅延取得）
                'half_year': [],  # 空（遅延取得）
                'older': []       # 空（遅延取得）
            }

    return render_template('post_list.html',
                           posts=posts,
                           group_counts=group_counts,
                           authenticated=authenticated,
                           form=form,
                           view_mode=view_mode)

def get_posts_by_category_with_relative_time():
    """カテゴリ別に投稿を取得（relative_time付き）"""
    post_files_info = get_sorted_post_files_info()
    search_query = request.args.get('search')

    # relative_timeとdateを追加
    for topic, files in post_files_info.items():
        for file_info in files:
            timestamp = file_info.get('timestamp', 0)
            file_info['relative_time'] = get_relative_time(timestamp)
            file_info['date'] = datetime.datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d %H:%M')

        # 各カテゴリ内で更新日時の降順にソート
        files.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

    return post_files_info

def get_posts_by_date_periods():
    """投稿を日付期間でグループ化して取得"""
    now = datetime.datetime.now()
    week_ago = now - datetime.timedelta(days=7)
    month_ago = now - datetime.timedelta(days=30)
    half_year_ago = now - datetime.timedelta(days=183)

    posts = {
        'week': [],      # 1週間以内
        'month': [],     # 1週間〜1ヶ月
        'half_year': [], # 1ヶ月〜半年
        'older': []      # それ以前
    }

    # 検索クエリの取得
    search_query = request.args.get('search')
    
    # 投稿ファイルの取得
    post_dir = './post'
    post_files = [f for f in os.listdir(post_dir)
                if os.path.isfile(os.path.join(post_dir, f))
                and not f.endswith('.gitkeep')]

    for filename in post_files:
        file_path = os.path.join(post_dir, filename)
        timestamp = os.path.getmtime(file_path)
        file_date = datetime.datetime.fromtimestamp(timestamp)
        
        # メタデータの取得
        metadata = get_file_metadata(file_path)
        
        # 検索時は全文を読み込む
        if search_query:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read().lower()
                    if not any(term.lower() in content for term in search_query.split()):
                        continue
            except Exception as e:
                print(f"Error reading file for search {file_path}: {e}")
                continue

        file_info = {
            'filename': filename,
            'title': metadata['title'],
            'date': file_date.strftime('%Y/%m/%d %H:%M'),
            'timestamp': timestamp,
            'relative_time': get_relative_time(timestamp)
        }

        # 期間に応じて振り分け
        if file_date >= week_ago:
            posts['week'].append(file_info)
        elif file_date >= month_ago:
            posts['month'].append(file_info)
        elif file_date >= half_year_ago:
            posts['half_year'].append(file_info)
        else:
            posts['older'].append(file_info)

    # 各期間内で更新日時の降順にソート
    for period in posts:
        posts[period].sort(key=lambda x: x['timestamp'], reverse=True)

    return posts

def get_latest_posts(limit=10, exclude=None):
    """最新N件の投稿を取得（指定ファイルを除外可能）"""
    post_dir = './post'
    post_files = [f for f in os.listdir(post_dir)
                  if os.path.isfile(os.path.join(post_dir, f))
                  and not f.endswith('.gitkeep')
                  and f != exclude]  # 現在編集中のファイルを除外

    files_with_time = []
    for filename in post_files:
        file_path = os.path.join(post_dir, filename)
        timestamp = os.path.getmtime(file_path)
        metadata = get_file_metadata(file_path)
        files_with_time.append({
            'filename': filename,
            'title': metadata['title'],
            'date': datetime.datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d %H:%M'),
            'timestamp': timestamp
        })

    files_with_time.sort(key=lambda x: x['timestamp'], reverse=True)
    return files_with_time[:limit]

def get_relative_time(timestamp):
    """相対的な時間表示を生成"""
    now = datetime.datetime.now()
    target = datetime.datetime.fromtimestamp(timestamp)
    diff = now - target

    # 今日かどうか
    if target.date() == now.date():
        if diff.seconds < 60:
            return "数秒前"
        elif diff.seconds < 3600:
            return f"{diff.seconds // 60}分前"
        else:
            return f"{diff.seconds // 3600}時間前"

    # 昨日
    yesterday = now.date() - datetime.timedelta(days=1)
    if target.date() == yesterday:
        return "昨日"

    # 一昨日
    day_before = now.date() - datetime.timedelta(days=2)
    if target.date() == day_before:
        return "一昨日"

    # 1週間以内
    if diff.days < 7:
        return f"{diff.days}日前"

    # 1ヶ月以内
    if diff.days < 30:
        weeks = diff.days // 7
        return f"{weeks}週間前"

    # 1年以内
    if diff.days < 365:
        months = diff.days // 30
        return f"{months}ヶ月前"

    # 1年以上
    years = diff.days // 365
    return f"{years}年前"

@app.route('/api/backups/<filename>', methods=['GET'])
@login_required
def get_backups(filename):
    """指定ファイルの最新10件のバックアップを返す"""
    backup_dir = './post/bk'

    # ファイル名バリデーション
    if not is_valid_filename(filename):
        return jsonify({'error': '無効なファイル名'}), 400

    # バックアップディレクトリが存在しない場合
    if not os.path.exists(backup_dir):
        return jsonify({'backups': []})

    # バックアップファイルを検索
    backup_files = [
        f for f in os.listdir(backup_dir)
        if f.startswith(filename + '_')
    ]

    # タイムスタンプでソート（新しい順）
    backup_info = []
    for bf in backup_files:
        path = os.path.join(backup_dir, bf)
        timestamp = os.path.getmtime(path)
        backup_info.append({
            'filename': bf,
            'timestamp': timestamp,
            'date': datetime.datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d %H:%M'),
            'relative_time': get_relative_time(timestamp)
        })

    backup_info.sort(key=lambda x: x['timestamp'], reverse=True)

    return jsonify({'backups': backup_info[:10]})

@app.route('/api/backup_content/<path:backup_filename>', methods=['GET'])
@login_required
def get_backup_content(backup_filename):
    """バックアップファイルの内容を返す"""

    # ファイル名バリデーション（ディレクトリトラバーサル対策）
    if '..' in backup_filename or backup_filename.startswith('/'):
        return jsonify({'error': '無効なファイル名'}), 400

    backup_path = os.path.join('./post/bk', backup_filename)

    if not os.path.exists(backup_path):
        return jsonify({'error': 'ファイルが存在しません'}), 404

    try:
        with open(backup_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================================
# Papernote編集API（MVP）
# ========================================

# API Key認証デコレータ
def require_api_key(f):
    """API Key認証を要求するデコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                "status": "error",
                "message": "Missing or invalid Authorization header"
            }), 401

        token = auth_header.split(' ')[1]
        valid_keys = [k['key'] for k in config.get('api_keys', []) if k.get('enabled', True)]

        if token not in valid_keys:
            app.logger.warning(f"Invalid API key attempt: {token[:20]}...")
            return jsonify({
                "status": "error",
                "message": "Invalid API key"
            }), 401

        return f(*args, **kwargs)
    return decorated_function

# ファイル名検証（API専用）
def is_valid_api_filename(filename):
    """
    APIアクセス可能なファイル名かを検証
    - ./post直下のみ
    - .txt拡張子のみ
    - パストラバーサル禁止
    - サブディレクトリ禁止
    """
    # パストラバーサルチェック
    if '..' in filename or '/' in filename or '\\' in filename:
        return False

    # .txt拡張子チェック
    if not filename.endswith('.txt'):
        return False

    # サブディレクトリ名の禁止（.cache, bk, tmpなど）
    if filename.startswith('.') or filename.startswith('bk') or filename.startswith('tmp'):
        return False

    return True

# API 1: 投稿内容取得
@app.route('/api/posts/<filename>', methods=['GET'])
@require_api_key
@limiter.limit("60 per minute")
@csrf.exempt
def api_get_post(filename):
    """指定されたファイルの内容を取得"""
    # ファイル名検証
    if not is_valid_api_filename(filename):
        return jsonify({
            "status": "error",
            "message": "Invalid filename or access denied"
        }), 400

    file_path = os.path.join('./post', filename)

    # ファイル存在チェック
    if not os.path.isfile(file_path):
        return jsonify({
            "status": "error",
            "message": "File not found"
        }), 404

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        file_stat = os.stat(file_path)

        return jsonify({
            "status": "success",
            "data": {
                "filename": filename,
                "content": content,
                "size": file_stat.st_size,
                "modified_at": dt.datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            }
        })
    except Exception as e:
        app.logger.error(f"Error reading file {filename}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# API 2: 新規投稿作成
@app.route('/api/posts', methods=['POST'])
@require_api_key
@limiter.limit("60 per minute")
@csrf.exempt
def api_create_post():
    """新規投稿を作成（ファイル名は自動生成）"""
    data = request.get_json()

    if not data or 'content' not in data:
        return jsonify({
            "status": "error",
            "message": "Missing 'content' field"
        }), 400

    content = data['content']

    # ファイル名自動生成: [_]YYYYmmdd-HHMMSS.txt
    now = dt.datetime.now()
    filename = f"[_]{now.strftime('%Y%m%d-%H%M%S')}.txt"
    file_path = os.path.join('./post', filename)

    # 万が一の重複チェック
    if os.path.exists(file_path):
        return jsonify({
            "status": "error",
            "message": "File already exists (please retry)"
        }), 409

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        app.logger.info(f"API: Created new post {filename}")

        return jsonify({
            "status": "success",
            "message": "Post created successfully",
            "data": {
                "filename": filename
            }
        }), 201
    except Exception as e:
        app.logger.error(f"Error creating file {filename}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# API 3: 投稿編集
@app.route('/api/posts/<filename>', methods=['PUT'])
@require_api_key
@limiter.limit("60 per minute")
@csrf.exempt
def api_update_post(filename):
    """既存の投稿を編集"""
    # ファイル名検証
    if not is_valid_api_filename(filename):
        return jsonify({
            "status": "error",
            "message": "Invalid filename or access denied"
        }), 400

    file_path = os.path.join('./post', filename)

    # ファイル存在チェック
    if not os.path.isfile(file_path):
        return jsonify({
            "status": "error",
            "message": "File not found"
        }), 404

    data = request.get_json()

    if not data or 'content' not in data:
        return jsonify({
            "status": "error",
            "message": "Missing 'content' field"
        }), 400

    content = data['content']

    try:
        # バックアップ作成
        backup_dir = './post/bk'
        os.makedirs(backup_dir, exist_ok=True)

        # バックアップファイル名を生成: 元のファイル名_YYYYmmdd-HH
        now = dt.datetime.now()
        backup_suffix = now.strftime('%Y%m%d-%H')
        backup_filename = f"{filename}_{backup_suffix}"

        # バックアップコピー
        import shutil
        shutil.copy2(file_path, os.path.join(backup_dir, backup_filename))

        # ファイル更新
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        app.logger.info(f"API: Updated post {filename} (backup: {backup_filename})")

        return jsonify({
            "status": "success",
            "message": "Post updated successfully",
            "data": {
                "filename": filename
            }
        })
    except Exception as e:
        app.logger.error(f"Error updating file {filename}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# API 3.5: 投稿削除
@app.route('/api/posts/<filename>', methods=['DELETE'])
@require_api_key
@limiter.limit("30 per minute")
@csrf.exempt
def api_delete_post(filename):
    """投稿を削除"""
    # ファイル名検証
    if not is_valid_api_filename(filename):
        return jsonify({
            "status": "error",
            "message": "Invalid filename or access denied"
        }), 400

    file_path = os.path.join('./post', filename)

    # ファイル存在チェック
    if not os.path.isfile(file_path):
        return jsonify({
            "status": "error",
            "message": "File not found"
        }), 404

    try:
        os.remove(file_path)
        app.logger.info(f"API: Deleted post {filename}")

        # キャッシュファイルを削除
        cache_file_old = './post/.cache/post_files_info.json'
        cache_file_all = './post/.cache/post_files_info_all.json'
        filelist_cache = './post/.cache/filelist.json'
        for cf in [cache_file_old, cache_file_all, filelist_cache]:
            if os.path.exists(cf):
                os.remove(cf)

        return jsonify({
            "status": "success",
            "message": "Post deleted successfully",
            "data": {
                "filename": filename
            }
        })
    except Exception as e:
        app.logger.error(f"Error deleting file {filename}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# API 4: 投稿一覧取得
@app.route('/api/posts', methods=['GET'])
@require_api_key
@limiter.limit("60 per minute")
@csrf.exempt
def api_list_posts():
    """全投稿の一覧を取得（カテゴリ・タイトル・更新日時付き）"""
    try:
        posts = []
        post_dir = './post'

        for filename in os.listdir(post_dir):
            # .txtファイルのみ、サブディレクトリは無視
            if not filename.endswith('.txt'):
                continue
            if filename.startswith('.') or filename.startswith('bk') or filename.startswith('tmp'):
                continue

            file_path = os.path.join(post_dir, filename)
            if not os.path.isfile(file_path):
                continue

            # カテゴリ解析: [category]filename.txt
            category = '_'  # デフォルト（未分類）
            if filename.startswith('[') and ']' in filename:
                category = filename[1:filename.index(']')]

            # タイトル取得（1行目）
            title = filename  # デフォルトはファイル名
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    # Markdownの見出し記号を除去
                    if first_line.startswith('#'):
                        title = first_line.lstrip('#').strip()
                    elif first_line:
                        title = first_line[:100]  # 最大100文字
            except:
                pass

            # ファイル情報
            file_stat = os.stat(file_path)

            posts.append({
                "filename": filename,
                "category": category,
                "title": title,
                "size": file_stat.st_size,
                "modified_at": dt.datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            })

        # 更新日時の降順でソート
        posts.sort(key=lambda x: x['modified_at'], reverse=True)

        return jsonify({
            "status": "success",
            "data": {
                "posts": posts,
                "total": len(posts)
            }
        })
    except Exception as e:
        app.logger.error(f"Error listing posts: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# API 5: 投稿検索
@app.route('/api/posts/search', methods=['GET'])
@require_api_key
@limiter.limit("30 per minute")
@csrf.exempt
def api_search_posts():
    """
    投稿を検索
    クエリパラメータ:
      - q: 検索キーワード（必須）
      - type: 検索対象 title|body|all（デフォルト: all）
    """
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all').lower()

    if not query:
        return jsonify({
            "status": "error",
            "message": "Missing 'q' parameter"
        }), 400

    if search_type not in ['title', 'body', 'all']:
        return jsonify({
            "status": "error",
            "message": "Invalid 'type' parameter. Use 'title', 'body', or 'all'"
        }), 400

    try:
        results = []
        post_dir = './post'
        query_lower = query.lower()

        for filename in os.listdir(post_dir):
            if not filename.endswith('.txt'):
                continue
            if filename.startswith('.') or filename.startswith('bk') or filename.startswith('tmp'):
                continue

            file_path = os.path.join(post_dir, filename)
            if not os.path.isfile(file_path):
                continue

            # カテゴリ解析
            category = '_'
            if filename.startswith('[') and ']' in filename:
                category = filename[1:filename.index(']')]

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except:
                continue

            # タイトル取得（1行目）
            lines = content.split('\n')
            first_line = lines[0].strip() if lines else ''
            if first_line.startswith('#'):
                title = first_line.lstrip('#').strip()
            elif first_line:
                title = first_line[:100]
            else:
                title = filename

            # 検索マッチング
            matched = False
            if search_type == 'title':
                matched = query_lower in title.lower()
            elif search_type == 'body':
                # タイトル行を除いた本文で検索
                body = '\n'.join(lines[1:]) if len(lines) > 1 else ''
                matched = query_lower in body.lower()
            else:  # all
                matched = query_lower in content.lower()

            if matched:
                file_stat = os.stat(file_path)
                results.append({
                    "filename": filename,
                    "category": category,
                    "title": title,
                    "size": file_stat.st_size,
                    "modified_at": dt.datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                })

        # 更新日時の降順でソート
        results.sort(key=lambda x: x['modified_at'], reverse=True)

        return jsonify({
            "status": "success",
            "data": {
                "posts": results,
                "total": len(results),
                "query": query,
                "type": search_type
            }
        })
    except Exception as e:
        app.logger.error(f"Error searching posts: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# API 6: カテゴリ一覧取得
@app.route('/api/categories', methods=['GET'])
@require_api_key
@limiter.limit("60 per minute")
@csrf.exempt
def api_list_categories():
    """全カテゴリの一覧を取得（投稿数付き）"""
    try:
        categories = {}
        post_dir = './post'

        for filename in os.listdir(post_dir):
            if not filename.endswith('.txt'):
                continue
            if filename.startswith('.') or filename.startswith('bk') or filename.startswith('tmp'):
                continue

            file_path = os.path.join(post_dir, filename)
            if not os.path.isfile(file_path):
                continue

            # カテゴリ解析
            category = '_'  # 未分類
            if filename.startswith('[') and ']' in filename:
                category = filename[1:filename.index(']')]

            if category not in categories:
                categories[category] = 0
            categories[category] += 1

        # カテゴリ名でソート（_は最後に）
        sorted_categories = []
        for cat, count in sorted(categories.items(), key=lambda x: (x[0] == '_', x[0])):
            sorted_categories.append({
                "name": cat,
                "count": count
            })

        return jsonify({
            "status": "success",
            "data": {
                "categories": sorted_categories,
                "total": len(sorted_categories)
            }
        })
    except Exception as e:
        app.logger.error(f"Error listing categories: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# ============================================
# UI用 内部API（ページネーション対応）
# ============================================

@app.route('/api/ui/postlist/group', methods=['GET'])
@login_required
@limiter.limit("120 per minute")
@csrf.exempt
def api_ui_postlist_group():
    """
    postlist用: 指定グループのデータを取得
    パラメータ:
      - view: 'date' or 'category'
      - group: グループキー（week, month, half_year, older またはカテゴリ名）
    """
    view_mode = request.args.get('view', 'date')
    group_key = request.args.get('group', '')

    if not group_key:
        return jsonify({"status": "error", "message": "group parameter required"}), 400

    try:
        if view_mode == 'category':
            all_posts = get_posts_by_category_with_relative_time()
        else:
            all_posts = get_posts_by_date_periods()

        items = all_posts.get(group_key, [])

        return jsonify({
            "status": "success",
            "group": group_key,
            "items": items
        })

    except Exception as e:
        print(f"Error in api_ui_postlist_group: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ui/postlist/remaining', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
@csrf.exempt
def api_ui_postlist_remaining():
    """
    postlist用: 未取得グループのデータを一括取得
    パラメータ:
      - view: 'date' or 'category'
      - loaded[]: 既に取得済みのグループキーの配列
    """
    view_mode = request.args.get('view', 'date')
    loaded_groups = request.args.getlist('loaded[]')

    try:
        if view_mode == 'category':
            all_posts = get_posts_by_category_with_relative_time()
        else:
            all_posts = get_posts_by_date_periods()

        # 未取得グループのみ返す
        remaining = {}
        for group_key, items in all_posts.items():
            if group_key not in loaded_groups and items:
                remaining[group_key] = items

        return jsonify({
            "status": "success",
            "data": remaining
        })

    except Exception as e:
        print(f"Error in api_ui_postlist_remaining: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ui/posts/paginate', methods=['GET'])
@limiter.limit("120 per minute")
@csrf.exempt
def api_ui_posts_paginate():
    """
    UI用ページネーションAPI（トピック別/日付別）
    クエリパラメータ:
      - page: ページ番号（1から開始、デフォルト: 1）
      - limit: 1ページあたりの件数（デフォルト: 30）
      - group: グループ化方式 topic|date（デフォルト: topic）
      - search: 検索キーワード（オプション）
    """
    try:
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 30))))
        group_by = request.args.get('group', 'topic').lower()
        search_query = request.args.get('search', '').strip()
        authenticated = current_user.is_authenticated

        CACHE_FILE = './post/.cache/post_files_info_all.json'
        FILELIST_CACHE = './post/.cache/filelist.json'
        DATE_CACHE_FILE = './post/.cache/posts_by_date.json'

        all_items = []

        if group_by == 'date':
            # 日付別グループ化（/post_latest用）
            all_items = _get_posts_flat_by_date(authenticated, search_query)
        else:
            # トピック別（/post用）- キャッシュ活用
            if not search_query and os.path.exists(CACHE_FILE) and os.path.exists(FILELIST_CACHE):
                try:
                    current_files = set(
                        f for f in os.listdir('./post')
                        if os.path.isfile(os.path.join('./post', f)) and not f.endswith('.gitkeep')
                    )
                    with open(FILELIST_CACHE, 'r') as f:
                        cached_files = set(json.load(f))
                    if current_files == cached_files:
                        with open(CACHE_FILE, 'r') as f:
                            all_cached = json.load(f)
                        # フラット化
                        for topic, files in all_cached.items():
                            for file_info in files:
                                if not authenticated and file_info.get('title', '').startswith('#'):
                                    continue
                                all_items.append({
                                    **file_info,
                                    'topic': topic
                                })
                except Exception as e:
                    app.logger.error(f"Cache read error: {e}")

            if not all_items:
                # キャッシュがない場合は生成
                all_items = _get_posts_flat_by_topic(authenticated, search_query)

        # 検索フィルタ
        if search_query:
            search_terms = search_query.lower().split()
            all_items = [
                item for item in all_items
                if any(term in item.get('title', '').lower() or term in item.get('filename', '').lower()
                       for term in search_terms)
            ]

        # ソート（更新日時の降順）
        all_items.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

        total = len(all_items)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_items = all_items[start_idx:end_idx]

        return jsonify({
            "status": "success",
            "data": {
                "items": paginated_items,
                "page": page,
                "limit": limit,
                "total": total,
                "has_more": end_idx < total
            }
        })
    except Exception as e:
        app.logger.error(f"Error in paginate API: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500


def _get_posts_flat_by_topic(authenticated, search_query=None):
    """トピック別に投稿を取得しフラット化"""
    post_dir = './post'
    items = []

    for filename in os.listdir(post_dir):
        if not os.path.isfile(os.path.join(post_dir, filename)):
            continue
        if filename.endswith('.gitkeep'):
            continue

        file_path = os.path.join(post_dir, filename)
        metadata = get_file_metadata(file_path)

        # 非認証時は#始まりのタイトルを除外
        if not authenticated and metadata['title'].startswith('#'):
            continue

        # トピック抽出
        topic_match = re.match(r'\[(.*?)\]', filename)
        topic = topic_match.group(1) if topic_match else '_トピック未設定'

        items.append({
            'filename': filename,
            'title': metadata['title'],
            'tags': metadata['tags'],
            'timestamp': os.path.getmtime(file_path),
            'topic': topic
        })

    return items


def _get_posts_flat_by_date(authenticated, search_query=None):
    """日付期間別に投稿を取得しフラット化"""
    post_dir = './post'
    now = datetime.datetime.now()
    week_ago = now - datetime.timedelta(days=7)
    month_ago = now - datetime.timedelta(days=30)
    half_year_ago = now - datetime.timedelta(days=183)

    items = []

    for filename in os.listdir(post_dir):
        if not os.path.isfile(os.path.join(post_dir, filename)):
            continue
        if filename.endswith('.gitkeep'):
            continue
        if filename.startswith('.') or filename.startswith('bk') or filename.startswith('tmp'):
            continue

        file_path = os.path.join(post_dir, filename)
        metadata = get_file_metadata(file_path)

        # 非認証時は#始まりのタイトルを除外
        if not authenticated and metadata['title'].startswith('#'):
            continue

        timestamp = os.path.getmtime(file_path)
        file_date = datetime.datetime.fromtimestamp(timestamp)

        # 期間分類
        if file_date >= week_ago:
            period = 'week'
        elif file_date >= month_ago:
            period = 'month'
        elif file_date >= half_year_ago:
            period = 'half_year'
        else:
            period = 'older'

        items.append({
            'filename': filename,
            'title': metadata['title'],
            'tags': metadata.get('tags', ''),
            'timestamp': timestamp,
            'date': file_date.strftime('%Y/%m/%d %H:%M'),
            'period': period
        })

    return items

# ============================================
# Paper APIs (論文管理API)
# ============================================

# API 7: 論文一覧取得
@app.route('/api/papers', methods=['GET'])
@require_api_key
@limiter.limit("60 per minute")
@csrf.exempt
def api_list_papers():
    """論文一覧を取得（タイトル、カテゴリ、日付付き）"""
    try:
        pdf_files = [f for f in os.listdir('./pdfs') if os.path.isfile(os.path.join('./pdfs', f)) and f.endswith('.pdf') and f != '.gitkeep']

        papers = []
        for file in pdf_files:
            pdf_id = file.replace('.pdf', '')
            path = os.path.join('./pdfs', file)
            timestamp = os.path.getmtime(path)

            # メモファイルからタイトルとカテゴリを取得
            memo_path = os.path.join('./memo', pdf_id + '.txt')
            title = pdf_id  # デフォルトはPDF ID
            category = ''
            has_memo = os.path.exists(memo_path)

            if has_memo:
                try:
                    with open(memo_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if len(lines) >= 1:
                            title = lines[0].strip()
                        if len(lines) >= 2:
                            category = lines[1].strip()
                except Exception:
                    pass

            # サマリーの存在チェック
            has_summary = os.path.exists(os.path.join('./summary', pdf_id + '.txt'))
            has_summary2 = os.path.exists(os.path.join('./summary2', pdf_id + '.txt'))

            papers.append({
                'pdf_id': pdf_id,
                'title': title,
                'category': category,
                'date': datetime.datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d'),
                'timestamp': timestamp,
                'has_memo': has_memo,
                'has_summary': has_summary,
                'has_summary2': has_summary2
            })

        # 日付で降順ソート
        papers.sort(key=lambda x: x['timestamp'], reverse=True)

        return jsonify({
            "status": "success",
            "data": {
                "papers": papers,
                "total": len(papers)
            }
        })
    except Exception as e:
        app.logger.error(f"Error listing papers: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# API 8: 論文詳細取得
@app.route('/api/papers/<pdf_id>', methods=['GET'])
@require_api_key
@limiter.limit("60 per minute")
@csrf.exempt
def api_get_paper(pdf_id):
    """論文の詳細情報を取得（memo, summary, summary2）"""
    try:
        # PDFの存在確認
        pdf_path = os.path.join('./pdfs', pdf_id + '.pdf')
        if not os.path.exists(pdf_path):
            return jsonify({
                "status": "error",
                "message": "Paper not found"
            }), 404

        timestamp = os.path.getmtime(pdf_path)

        # 各コンテンツを読み込み
        memo_content = ''
        title = pdf_id
        category = ''
        memo_path = os.path.join('./memo', pdf_id + '.txt')
        if os.path.exists(memo_path):
            with open(memo_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) >= 1:
                    title = lines[0].strip()
                if len(lines) >= 2:
                    category = lines[1].strip()
                if len(lines) >= 3:
                    memo_content = ''.join(lines[2:])  # 3行目以降がメモ本文

        summary_content = ''
        summary_path = os.path.join('./summary', pdf_id + '.txt')
        if os.path.exists(summary_path):
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary_content = f.read()

        summary2_content = ''
        summary2_path = os.path.join('./summary2', pdf_id + '.txt')
        if os.path.exists(summary2_path):
            with open(summary2_path, 'r', encoding='utf-8') as f:
                summary2_content = f.read()

        return jsonify({
            "status": "success",
            "data": {
                "pdf_id": pdf_id,
                "title": title,
                "category": category,
                "date": datetime.datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d'),
                "memo": memo_content,
                "summary": summary_content,
                "summary2": summary2_content,
                "pdf_url": f"/pdfs/{pdf_id}.pdf",
                "has_memo": bool(memo_content),
                "has_summary": bool(summary_content),
                "has_summary2": bool(summary2_content)
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting paper {pdf_id}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# API 9: 論文検索
@app.route('/api/papers/search', methods=['GET'])
@require_api_key
@limiter.limit("60 per minute")
@csrf.exempt
def api_search_papers():
    """論文を検索（タイトル、メモ、サマリーを対象）"""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({
                "status": "error",
                "message": "Missing search query parameter 'q'"
            }), 400

        search_terms = query.lower().split()
        pdf_files = [f for f in os.listdir('./pdfs') if os.path.isfile(os.path.join('./pdfs', f)) and f.endswith('.pdf') and f != '.gitkeep']

        results = []
        for file in pdf_files:
            pdf_id = file.replace('.pdf', '')
            path = os.path.join('./pdfs', file)
            timestamp = os.path.getmtime(path)

            # 検索対象テキストを収集
            searchable_text = ''
            title = pdf_id
            category = ''

            memo_path = os.path.join('./memo', pdf_id + '.txt')
            has_memo = os.path.exists(memo_path)
            if has_memo:
                try:
                    with open(memo_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        if len(lines) >= 1:
                            title = lines[0].strip()
                        if len(lines) >= 2:
                            category = lines[1].strip()
                        searchable_text += content.lower()
                except Exception:
                    pass

            summary_path = os.path.join('./summary', pdf_id + '.txt')
            has_summary = os.path.exists(summary_path)
            if has_summary:
                try:
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        searchable_text += f.read().lower()
                except Exception:
                    pass

            summary2_path = os.path.join('./summary2', pdf_id + '.txt')
            has_summary2 = os.path.exists(summary2_path)
            if has_summary2:
                try:
                    with open(summary2_path, 'r', encoding='utf-8') as f:
                        searchable_text += f.read().lower()
                except Exception:
                    pass

            # 全ての検索語がマッチするか確認
            if all(term in searchable_text for term in search_terms):
                results.append({
                    'pdf_id': pdf_id,
                    'title': title,
                    'category': category,
                    'date': datetime.datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d'),
                    'timestamp': timestamp,
                    'has_memo': has_memo,
                    'has_summary': has_summary,
                    'has_summary2': has_summary2
                })

        # 日付で降順ソート
        results.sort(key=lambda x: x['timestamp'], reverse=True)

        return jsonify({
            "status": "success",
            "data": {
                "papers": results,
                "total": len(results),
                "query": query
            }
        })
    except Exception as e:
        app.logger.error(f"Error searching papers: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500


if __name__ == "__main__":
    # ユーザー情報のハッシュ化
    for user_id, user in config['users'].items():
        print(f"Hashing password for user: {user['username']}")
        user['password'] = generate_password_hash(user['password'])
        print(f"Hashed password: {user['password']}")
    port = config['server']['port']

    # 環境変数 FLASK_DEBUG=1 の場合のみデバッグモード（開発用）
    # systemctl経由（本番）では環境変数なし → debug=False（安全）
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    print(f"Starting server with debug={debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
