# Papernote

日本語のREADMEは英語のREADMEの記載されています。

## Overview
Papernote is a web application that manages PDF files and their associated notes and summaries. It includes features like authentication, file upload, text extraction, and file search.

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/daishir0/Papernote
   ```
2. Change to the project directory:
   ```bash
   cd Papernote
   ```
3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Rename `config.yaml.org` to `config.yaml` and configure the application by editing the `config.yaml` file. Below are the descriptions of each field:
   - `basic_auth`: Contains the username and password for basic authentication.
     - `username`: The username for accessing protected routes.
     - `password`: The password for accessing protected routes. **Please set your own password.**
   - `allowed_extensions`: A list of allowed file extensions for uploads.
     - Supported extensions: `jpg`, `jpeg`, `png`, `gif`, `txt`, `pdf`, `docx`, `xlsx`, `xls`.
   - `exclude_string`: A string that, if found in a memo line, excludes that line from being shown.
   - `twitter`: Contains Twitter metadata for the site and creator.
     - `site`: The Twitter handle of the site.
     - `creator`: The Twitter handle of the content creator.

## Usage
1. Start the application:
   ```bash
   python app.py
   ```
2. Access the web interface at `http://localhost:5555`.

## Notes
- Ensure that the `config.yaml` file is properly configured.
- The application requires a running instance of Flask and other dependencies specified in `requirements.txt`.

## License
This project is licensed under the MIT License - see the LICENSE file for details.

---

# Papernote

## 概要
PapernoteはPDFファイルとそれに関連するメモや要約を管理するウェブアプリケーションです。認証、ファイルアップロード、テキスト抽出、ファイル検索などの機能を含んでいます。

## インストール方法
1. リポジトリをクローンします：
   ```bash
   git clone https://github.com/daishir0/Papernote
   ```
2. プロジェクトディレクトリに移動します：
   ```bash
   cd Papernote
   ```
3. 必要なパッケージをインストールします：
   ```bash
   pip install -r requirements.txt
   ```
4. `config.yaml.org`を`config.yaml`にリネームし、アプリケーションを設定します。各フィールドの説明は以下の通りです：
   - `basic_auth`: ベーシック認証のためのユーザー名とパスワードを含みます。
     - `username`: 保護されたルートにアクセスするためのユーザー名。
     - `password`: 保護されたルートにアクセスするためのパスワード。**ご自身のパスワードに設定してください。**
   - `allowed_extensions`: アップロードが許可されているファイル拡張子のリスト。
     - サポートされている拡張子: `jpg`, `jpeg`, `png`, `gif`, `txt`, `pdf`, `docx`, `xlsx`, `xls`。
   - `exclude_string`: メモ行に含まれている場合、その行を表示から除外する文字列。
   - `twitter`: サイトとクリエイターのためのTwitterメタデータを含みます。
     - `site`: サイトのTwitterハンドル。
     - `creator`: コンテンツクリエイターのTwitterハンドル。

## 使い方
1. アプリケーションを開始します：
   ```bash
   python app.py
   ```
2. `http://localhost:5555`でウェブインターフェースにアクセスします。

## 注意点
- `config.yaml`ファイルが正しく設定されていることを確認してください。
- アプリケーションにはFlaskと`requirements.txt`に記載された他の依存関係が必要です。

## ライセンス
このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。
