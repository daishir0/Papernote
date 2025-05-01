# Papernote

![Top Page](./static/top_page.png)

日本語のREADMEは、英語のREADMEの後に記載されています。

## Overview
Papernote is a web application that manages PDF files and their associated notes and summaries. It includes features like file upload, text extraction, file search, user authentication, rate limiting, CSRF protection, PDF management, text extraction, email notifications, file attachments, memo and summary management, YouTube integration, and movie upload. You can read papers and freely write notes in Markdown/Mermaid, which can be accumulated. The application can be accessed from anywhere, not just on a PC but also on a smartphone.

![Detail Page](./static/detail_page.png)

## Installation
1. Ensure `ffmpeg` is installed on your system.
2. Clone the repository:
   ```bash
   git clone https://github.com/daishir0/Papernote
   ```
3. Change to the project directory:
   ```bash
   cd Papernote
   ```
4. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
5. Rename `config.yaml.org` to `config.yaml` and configure the application by editing the `config.yaml` file. Below are the descriptions of each field:
   - `allowed_extensions`: A list of allowed file extensions for uploads.
     - Supported extensions: `jpg`, `jpeg`, `png`, `gif`, `txt`, `pdf`, `docx`, `doc`, `xlsx`, `xls`, `pptx`, `ppt`, `zip`.
   - `exclude_string`: A string that, if found in a memo line, excludes that line from being shown.
   - `twitter`: Contains Twitter metadata for the site and creator.
     - `site`: The Twitter handle of the site.
     - `creator`: The Twitter handle of the content creator.
   - `server`: Contains port.
     - `port`: Server port.
   - `openai_api_key`: Your OpenAI API key for integration.
   - `gmail`: Contains Gmail configuration for sending emails.
     - `sender_email`: The email address used to send emails.
     - `recipient_email`: The email address to receive emails.
     - `app_password`: The application-specific password for Gmail.
   - `secret_key`: A secret key for session management and CSRF protection.
   - `users`: Contains user information for login.
     - `username`: The username for login.
     - `password`: The password for login.

## Usage
1. Start the application:
   ```bash
   python app.py
   ```
2. Access the web interface at `http://localhost:5555`.

## Features
- **User Authentication**: Secure login and logout functionality using Flask-Login.
- **Rate Limiting**: Protect routes from abuse with Flask-Limiter.
- **CSRF Protection**: Secure forms with Flask-WTF CSRF protection.
- **PDF Management**: Upload, search, and manage PDF files.
- **Text Extraction**: Extract and clean text from PDF files.
- **Email Notifications**: Send email notifications for login attempts and other events.
- **File Attachments**: Upload and manage file attachments.
- **Memo and Summary Management**: Create and edit memos and summaries for PDF files.
- **YouTube Integration**: Generate markdown from YouTube videos.
- **Movie Upload**: Upload and process movie files.

## Tools
### PDF to PaperNote Processor
A command-line tool that processes academic paper PDFs and generates files for the PaperNote system:
- Copies and renames PDF files using hash values
- Detects and copies attachment files (al-prefix files)
- Generates Twitter Card images (from the first page of PDFs)
- Extracts and formats clean text from PDFs
- Creates memo files containing paper titles (AI-extracted)
- Generates chapter-by-chapter summaries (AI-generated)
- Creates paper evaluations (peer review reports, AI-generated)

Usage:
```bash
python pdf_to_papernote.py [options] <PDF_file> [<PDF_file> ...]
```

Options:
- `-output`: Outputs files in a directory structure based on paper metadata
- `-openai`: Uses OpenAI's o3-mini model instead of Claude for summaries and evaluations

Example commands:
```bash
# Process a single PDF file
python pdf_to_papernote.py example.pdf

# Process multiple PDF files
python pdf_to_papernote.py a.pdf b.pdf

# Process all PDF files using wildcard
python pdf_to_papernote.py *.pdf

# Process with metadata-based directory output
python pdf_to_papernote.py -output example.pdf

# Use OpenAI model
python pdf_to_papernote.py -openai example.pdf

# Combine multiple options
python pdf_to_papernote.py -output -openai example.pdf
```

## Notes
- Ensure that the `config.yaml` file is properly configured.
- The application requires a running instance of Flask and other dependencies specified in `requirements.txt`.

## License
This project is licensed under the MIT License - see the LICENSE file for details.


---

# Papernote

## 概要
PapernoteはPDFファイルとそれに関連するメモや要約を管理するウェブアプリケーションです。ファイルアップロード、テキスト抽出、ファイル検索、ユーザー認証、レート制限、CSRF保護、PDF管理、テキスト抽出、メール通知、ファイル添付、メモと要約の管理、YouTube統合、ムービーアップロードなどの機能を含んでいます。論文を読んで、Markdown/Mermaidで自由にメモが書けて蓄積できること、PCだけでなくスマホでどこからでもアクセスできるメリットがあります。


## インストール方法
1. `ffmpeg`がシステムにインストールされていることを確認します。
2. リポジトリをクローンします：
   ```bash
   git clone https://github.com/daishir0/Papernote
   ```
3. プロジェクトディレクトリに移動します：
   ```bash
   cd Papernote
   ```
4. 必要なパッケージをインストールします：
   ```bash
   pip install -r requirements.txt
   ```
5. `config.yaml.org`を`config.yaml`にリネームし、アプリケーションを設定します。各フィールドの説明は以下の通りです：
   - `allowed_extensions`: アップロードが許可されているファイル拡張子のリスト。
     - サポートされている拡張子: `jpg`, `jpeg`, `png`, `gif`, `txt`, `pdf`, `docx`, `doc`, `xlsx`, `xls`, `pptx`, `ppt`, `zip`。
   - `exclude_string`: メモ行に含まれている場合、その行を表示から除外する文字列。
   - `twitter`: サイトとクリエイターのためのTwitterメタデータを含みます。
     - `site`: サイトのTwitterハンドル。
     - `creator`: コンテンツクリエイターのTwitterハンドル。
   - `server`: ポート番号を含みます。
     - `port`: サーバーのポート番号。
   - `openai_api_key`: OpenAI APIキー。
   - `gmail`: メール送信のためのGmail設定を含みます。
     - `sender_email`: メール送信に使用するメールアドレス。
     - `recipient_email`: メールを受信するメールアドレス。
     - `app_password`: Gmailのアプリケーション固有のパスワード。
   - `secret_key`: セッション管理とCSRF保護のためのシークレットキー。
   - `users`: ログイン用のユーザー情報を含みます。
     - `username`: ログイン用のユーザー名。
     - `password`: ログイン用のパスワード。

## 使い方
1. アプリケーションを開始します：
   ```bash
   python app.py
   ```
2. `http://localhost:5555`でウェブインターフェースにアクセスします。

## 機能
- **ユーザー認証**: Flask-Loginを使用した安全なログインとログアウト機能。
- **レート制限**: Flask-Limiterでルートを保護し、濫用を防止。
- **CSRF保護**: Flask-WTF CSRF保護でフォームを安全に。
- **PDF管理**: PDFファイルのアップロード、検索、管理。
- **テキスト抽出**: PDFファイルからテキストを抽出し、クリーンアップ。
- **メール通知**: ログイン試行やその他のイベントに対するメール通知を送信。
- **ファイル添付**: ファイル添付のアップロードと管理。
- **メモと要約の管理**: PDFファイルのメモと要約を作成および編集。
- **YouTube統合**: YouTube動画からMarkdownを生成。
- **ムービーアップロード**: ムービーファイルのアップロードと処理。

## ツール
### PDF論文処理ツール
学術論文のPDFファイルを処理し、PaperNoteシステム用のファイルを生成するコマンドラインツールです：
- PDFファイルのコピーとハッシュ値によるリネーム
- 添付ファイル（al-プレフィックスファイル）の検出とコピー
- Twitter Card用の画像生成（PDFの1ページ目から）
- PDFからのテキスト抽出と整形
- 論文のタイトルを含むメモファイルの作成（AI抽出）
- 論文の章ごとの要約生成（AI生成）
- 論文の評価レポート作成（査読レポート、AI生成）

使用方法：
```bash
python pdf_to_papernote.py [オプション] <PDFファイル> [<PDFファイル> ...]
```

オプション：
- `-output`: 論文メタデータに基づいたディレクトリ構造でファイルを出力
- `-openai`: 要約や評価の生成にClaudeの代わりにOpenAIのo3-miniモデルを使用

使用例：
```bash
# 単一のPDFファイルを処理
python pdf_to_papernote.py example.pdf

# 複数のPDFファイルを処理
python pdf_to_papernote.py a.pdf b.pdf

# ワイルドカードを使用して全てのPDFファイルを処理
python pdf_to_papernote.py *.pdf

# メタデータベースのディレクトリ出力を有効にして処理
python pdf_to_papernote.py -output example.pdf

# OpenAIのモデルを使用して処理
python pdf_to_papernote.py -openai example.pdf

# 複数のオプションを組み合わせて処理
python pdf_to_papernote.py -output -openai example.pdf
```

## 注意点
- `config.yaml`ファイルが正しく設定されていることを確認してください。
- アプリケーションにはFlaskと`requirements.txt`に記載された他の依存関係が必要です。

## ライセンス
このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。

