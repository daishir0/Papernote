import argparse
import os
import re
import requests
import numpy as np
import yaml
import time
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, make_response, send_file
from subprocess import Popen, PIPE
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text
from urllib.parse import urlparse
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image, ExifTags
import string
import hashlib
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
from flask_wtf.csrf import CSRFProtect
from datetime import timedelta
import tldextract
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pytube import YouTube
import yt_dlp
from bs4 import BeautifulSoup
from markdownify import markdownify as md

processing = False

# Load configuration from YAML file
with open('config.yaml', 'r') as config_file:
    config = yaml.safe_load(config_file)

app = Flask(__name__)

# secret_keyの設定
app.secret_key = config['secret_key']

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

# セッションの保持時間を設定（例: 1日）
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=1)

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
                    login_user(user_obj)
                    # send_email("Authentication Success", f"User {username} logged in successfully.\n\n{get_client_info()}")
                    with open('./access_log.txt', 'a') as log_file:
                        log_file.write(f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - User {username} logged in successfully - {get_client_info()}\n")
                    # Create response object
                    response = make_response(redirect(url_for('post_index')))
                    
                    # Set domain-specific cookie
                    host = request.host
                    extracted = tldextract.extract(host)
                    
                    if extracted.subdomain:
                        # If there's a subdomain, set the cookie for the main domain and all its subdomains
                        cookie_domain = f".{extracted.domain}.{extracted.suffix}"
                    else:
                        # If there's no subdomain, set the cookie for the current domain only
                        cookie_domain = f"{extracted.domain}.{extracted.suffix}"

                    response.set_cookie('session', user_obj.get_id(), 
                                        domain=cookie_domain,
                                        httponly=True, secure=True, samesite='Strict',
                                        max_age=3600)  # Set cookie expiration to 1 hour
                    
                    return response
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

        is_image = file_ext in {'jpg', 'jpeg', 'png', 'gif'}
        file_url = f"/attach/{new_filename}"

        if is_image:
            # Save a smaller size image with 's_' prefix if it's an image file
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
            return redirect(request.url)
        
        file = request.files['file']

        # アップロードされた際の元ファイル名を取得
        original_filename = file.filename

        if original_filename == '':
            return redirect(request.url)
        
        if file and allowed_file(original_filename):
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
            
            return redirect(url_for('file_upload'))

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
    if current_user.is_authenticated:
        return send_from_directory('./pdfs', secure_filename(filename))
    else:
        abort(403)  # Forbiddenアクセス拒否


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
def delete_file():
    filename = request.form['filename']

    # 削除するファイルのパスを構築
    paths = {
        'PDF File': os.path.join('./pdfs', secure_filename(filename)),
        'Clean Text File': os.path.join('./clean_text', secure_filename(filename.replace('.pdf', '.txt'))),
        'Memo File': os.path.join('./memo', secure_filename(filename.replace('.pdf', '.txt'))),
        'Summary File': os.path.join('./summary', secure_filename(filename.replace('.pdf', '.txt'))),
        'Secondary Summary File': os.path.join('./summary2', secure_filename(filename.replace('.pdf', '.txt'))),
        'Twitter Card Image': os.path.join('./tw', secure_filename(filename.replace('.pdf', '.png')))
    }

    # 各ファイルの存在を確認し、存在する場合は削除
    for file_type, path in paths.items():
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"{file_type} at {path} was successfully deleted.")
            else:
                print(f"{file_type} at {path} does not exist.")
        except Exception as e:
            print(f"Failed to delete {file_type} at {path}: {e}")

    return jsonify({'message': f'{filename} が削除されました。'})

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

def get_sorted_post_files_info():
    # ブログディレクトリの全ファイルを取得
    post_dir = './post'
    post_files = [f for f in os.listdir(post_dir) if os.path.isfile(os.path.join(post_dir, f)) and not f.endswith('.gitkeep')]
    search_query = request.args.get('search')

    authenticated = current_user.is_authenticated
    post_files_info = {}

    for filename in post_files:
        file_path = os.path.join(post_dir, filename)
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            lines = file.readlines()
            title = lines[0].strip() if lines else ""
            tags = lines[1].strip() if len(lines) > 1 else ""
            if search_query:
                content = ''.join(lines).lower()  # ファイル全体の内容を取得
            else:
                content = ""
                
            # 限定公開と非公開の場合はインデックスに掲載しない
            if not authenticated and title.startswith('#'):
                continue

            # トピックを抽出
            topic_match = re.match(r'\[(.*?)\]', filename)
            topic = topic_match.group(1) if topic_match else '_トピック未設定'

            if topic not in post_files_info:
                post_files_info[topic] = []

            post_files_info[topic].append({
                'filename': filename,
                'title': title,
                'tags': tags,
                'content': content,  # ファイル全体の内容を追加
                'timestamp': os.path.getmtime(file_path)  # 最終更新日時を追加
            })

    if search_query:
        search_terms = search_query.lower().split()
        for topic in post_files_info:
            filtered_files = []
            for file in post_files_info[topic]:
                if any(term in file['content'] for term in search_terms):

                    filtered_files.append(file)
            post_files_info[topic] = filtered_files
    else:
        # 検索クエリがない場合、すべてのファイルを表示
        for topic in post_files_info:
            post_files_info[topic] = [file for file in post_files_info[topic]]
            
    for topic, files in post_files_info.items():
        print(f"トピック: {topic}, ファイル情報: {files}")

    # 各トピック内でファイル名昇順にソート
    for topic in post_files_info:
        post_files_info[topic].sort(key=lambda x: x['filename'])

    # トピック名でソート
    sorted_post_files_info = dict(sorted(post_files_info.items()))
    
    print(sorted_post_files_info)

    return sorted_post_files_info

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

    return render_template('post.html', content=content, authenticated=authenticated)

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
        
        # 現在日付を3で割った余りの数を取得
        remainder = datetime.datetime.now().day % 3
        backup_filename = f"{filename}_{remainder}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # バックアップディレクトリ保存
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # .txtを空文字列に置換して削除
        filename_without_txt = filename.replace('.txt', '')
        return redirect(f'/post/{filename}')

    if os.path.exists(post_path):
        with open(post_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            content = content.replace('\n', '\\n')  # 改行をエスケープ文字に置換
            content = html.escape(content)  # HTMLエスケープ処理
    else:
        content = ""

    return render_template('edit_post.html', filename=filename, content=content, form=form)

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
    
    return redirect(url_for('post_index'))

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
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # JavaScriptタグを削除
                for script in soup(["script", "style"]):
                    script.decompose()
                
                markdown_text = md(str(soup).replace('\n', ''))
                
                # HTMLからタイトルを取得し、ファイル名に変換
                title = soup.title.string if soup.title else 'untitled'
                file_name = f"[web]{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
                file_path = os.path.join('./post', file_name)
                
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(web_url.strip() + '\n' + markdown_text)
                
                success_count += 1
            except requests.exceptions.RequestException as e:
                error_count += 1
                print(f"Error processing URL {web_url.strip()}: {e}")
            
            time.sleep(1)  # 1秒のタイムアウトを入れる
        
        message = f"{success_count}件のファイルが変換され、{error_count}件のファイルがエラーになりました。"
        return render_template('webtomd.html', form=form, message=message)
    
    return render_template('webtomd.html', form=form, message=message)

if __name__ == "__main__":
    # ユーザー情報のハッシュ化
    for user_id, user in config['users'].items():
        print(f"Hashing password for user: {user['username']}")
        user['password'] = generate_password_hash(user['password'])
        print(f"Hashed password: {user['password']}")
    port = config['server']['port']
    app.run(host='0.0.0.0', port=port, debug=True)
