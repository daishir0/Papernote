# Papernote編集API ドキュメント

## 概要

Papernoteのテキスト投稿を外部システムから操作するためのRESTful APIです。

**Base URL:** `https://paper.path-finder.jp`

**認証方式:** API Key（Bearer Token）

**対応形式:** JSON

---

## 認証

全てのAPIリクエストには、以下のヘッダーが必要です：

```
Authorization: Bearer YOUR_API_KEY
```

### 認証エラー

認証に失敗した場合、以下のレスポンスが返されます：

```json
{
  "status": "error",
  "message": "Invalid API key"
}
```

**HTTPステータスコード:** `401 Unauthorized`

---

## エンドポイント一覧

### 1. 新規投稿作成

新しい投稿を作成します。ファイル名は自動生成されます。

**エンドポイント:** `POST /api/posts`

**リクエストヘッダー:**
```
Authorization: Bearer {API_KEY}
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "content": "投稿内容（Markdown形式）"
}
```

**レスポンス（成功）:**
```json
{
  "status": "success",
  "message": "Post created successfully",
  "data": {
    "filename": "[_]20251111-125217.txt"
  }
}
```

**HTTPステータスコード:** `201 Created`

**ファイル名形式:**
- 固定プレフィックス: `[_]`
- 日時フォーマット: `YYYYmmdd-HHMMSS`
- 拡張子: `.txt`
- 例: `[_]20250103-143025.txt`

**curlコマンド例:**
```bash
curl -X POST "https://paper.path-finder.jp/api/posts" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "## テスト投稿\n\nこれはテストです。"
  }'
```

**エラーレスポンス:**

| HTTPステータス | 説明 | レスポンス例 |
|---|---|---|
| 400 Bad Request | `content`フィールドが無い | `{"status": "error", "message": "Missing 'content' field"}` |
| 401 Unauthorized | API Key認証失敗 | `{"status": "error", "message": "Invalid API key"}` |
| 409 Conflict | ファイル重複（同一秒に作成） | `{"status": "error", "message": "File already exists (please retry)"}` |
| 429 Too Many Requests | レート制限超過 | Flask-Limiterのデフォルトレスポンス |
| 500 Internal Server Error | サーバーエラー | `{"status": "error", "message": "Internal server error"}` |

---

### 2. 投稿内容取得

指定したファイルの内容を取得します。

**エンドポイント:** `GET /api/posts/{filename}`

**URLパラメータ:**
- `filename`: 取得したいファイル名（URLエンコード必須）

**リクエストヘッダー:**
```
Authorization: Bearer {API_KEY}
```

**レスポンス（成功）:**
```json
{
  "status": "success",
  "data": {
    "filename": "[_]20251111-125217.txt",
    "content": "## テスト投稿\n\nこれはテストです。",
    "size": 103,
    "modified_at": "2025-11-11T12:52:55.266860"
  }
}
```

**HTTPステータスコード:** `200 OK`

**curlコマンド例:**
```bash
# ファイル名はURLエンコードが必要（[ → %5B, ] → %5D）
curl -X GET "https://paper.path-finder.jp/api/posts/%5B_%5D20251111-125217.txt" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**エラーレスポンス:**

| HTTPステータス | 説明 | レスポンス例 |
|---|---|---|
| 400 Bad Request | 不正なファイル名またはアクセス禁止 | `{"status": "error", "message": "Invalid filename or access denied"}` |
| 401 Unauthorized | API Key認証失敗 | `{"status": "error", "message": "Invalid API key"}` |
| 404 Not Found | ファイルが存在しない | `{"status": "error", "message": "File not found"}` |
| 429 Too Many Requests | レート制限超過 | Flask-Limiterのデフォルトレスポンス |
| 500 Internal Server Error | サーバーエラー | `{"status": "error", "message": "Internal server error"}` |

---

### 3. 投稿編集

既存の投稿内容を更新します。更新前の内容は自動的にバックアップされます。

**エンドポイント:** `PUT /api/posts/{filename}`

**URLパラメータ:**
- `filename`: 更新したいファイル名（URLエンコード必須）

**リクエストヘッダー:**
```
Authorization: Bearer {API_KEY}
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "content": "更新後の投稿内容"
}
```

**レスポンス（成功）:**
```json
{
  "status": "success",
  "message": "Post updated successfully",
  "data": {
    "filename": "[_]20251111-125217.txt"
  }
}
```

**HTTPステータスコード:** `200 OK`

**バックアップファイル:**
- 保存場所: `./post/bk/`
- 命名規則: `{元のファイル名}_YYYYmmdd-HH`
- 例: `[_]20251111-125217.txt_20251111-12`

**curlコマンド例:**
```bash
curl -X PUT "https://paper.path-finder.jp/api/posts/%5B_%5D20251111-125217.txt" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "## 更新されたタイトル\n\n更新内容"
  }'
```

**エラーレスポンス:**

| HTTPステータス | 説明 | レスポンス例 |
|---|---|---|
| 400 Bad Request | 不正なファイル名または`content`フィールドが無い | `{"status": "error", "message": "Invalid filename or access denied"}` または `{"status": "error", "message": "Missing 'content' field"}` |
| 401 Unauthorized | API Key認証失敗 | `{"status": "error", "message": "Invalid API key"}` |
| 404 Not Found | ファイルが存在しない | `{"status": "error", "message": "File not found"}` |
| 429 Too Many Requests | レート制限超過 | Flask-Limiterのデフォルトレスポンス |
| 500 Internal Server Error | サーバーエラー | `{"status": "error", "message": "Internal server error"}` |

---

## アクセス制限

### 許可されるファイル

- `./post/` **直下**の `.txt` ファイルのみアクセス可能

### 禁止されるファイル

以下のファイル・ディレクトリへのアクセスは**禁止**されています：

- サブディレクトリ: `.cache/`, `bk/`, `tmp/`
- パストラバーサル: `../`, `./bk/`, など
- `.txt`以外の拡張子
- `.`で始まるファイル名（隠しファイル）
- `bk`で始まるファイル名
- `tmp`で始まるファイル名

**禁止されたアクセスの例:**
```bash
# サブディレクトリ（404エラー）
GET /api/posts/.cache%2Flog.txt

# パストラバーサル（404エラー）
GET /api/posts/..%2Fconfig.yaml

# バックアップディレクトリ（404エラー）
GET /api/posts/bk%2Ftest.txt
```

---

## レート制限

全てのAPIエンドポイントには、以下のレート制限が適用されます：

**制限:** 60リクエスト/分（IPアドレス単位）

レート制限を超過した場合、HTTPステータスコード `429 Too Many Requests` が返されます。

---

## セキュリティ

### HTTPS必須

本番環境では、**HTTPS接続のみ**を使用してください。API Keyの漏洩を防ぐため、HTTP接続は推奨されません。

### API Key管理

- API Keyは機密情報として厳重に管理してください
- バージョン管理システム（Git等）にコミットしないでください
- 定期的にAPI Keyをローテーションすることを推奨します

### CSRF保護

APIエンドポイントはCSRF保護から除外されています（`@csrf.exempt`）。API Key認証で保護されているため、CSRFトークンは不要です。

---

## 使用例

### Python（requestsライブラリ）

```python
import requests

API_KEY = "YOUR_API_KEY"
BASE_URL = "https://paper.path-finder.jp"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 新規投稿作成
response = requests.post(
    f"{BASE_URL}/api/posts",
    headers=headers,
    json={"content": "## テスト投稿\n\nこれはテストです。"}
)
result = response.json()
print(f"作成されたファイル: {result['data']['filename']}")

# 投稿内容取得
filename = result['data']['filename']
response = requests.get(
    f"{BASE_URL}/api/posts/{filename}",
    headers=headers
)
post = response.json()
print(f"内容: {post['data']['content']}")

# 投稿編集
response = requests.put(
    f"{BASE_URL}/api/posts/{filename}",
    headers=headers,
    json={"content": "## 更新されたタイトル\n\n更新内容"}
)
result = response.json()
print(f"更新成功: {result['message']}")
```

### JavaScript（fetch API）

```javascript
const API_KEY = "YOUR_API_KEY";
const BASE_URL = "https://paper.path-finder.jp";

const headers = {
  "Authorization": `Bearer ${API_KEY}`,
  "Content-Type": "application/json"
};

// 新規投稿作成
const createPost = async () => {
  const response = await fetch(`${BASE_URL}/api/posts`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify({
      content: "## テスト投稿\n\nこれはテストです。"
    })
  });
  const result = await response.json();
  console.log("作成されたファイル:", result.data.filename);
  return result.data.filename;
};

// 投稿内容取得
const getPost = async (filename) => {
  const response = await fetch(
    `${BASE_URL}/api/posts/${encodeURIComponent(filename)}`,
    { headers: headers }
  );
  const post = await response.json();
  console.log("内容:", post.data.content);
};

// 投稿編集
const updatePost = async (filename) => {
  const response = await fetch(
    `${BASE_URL}/api/posts/${encodeURIComponent(filename)}`,
    {
      method: "PUT",
      headers: headers,
      body: JSON.stringify({
        content: "## 更新されたタイトル\n\n更新内容"
      })
    }
  );
  const result = await response.json();
  console.log("更新成功:", result.message);
};

// 実行例
(async () => {
  const filename = await createPost();
  await getPost(filename);
  await updatePost(filename);
})();
```

---

## トラブルシューティング

### Q: ファイル名に `[` や `]` が含まれるが、どうすればいい？

A: URLエンコードしてください。
- `[` → `%5B`
- `]` → `%5D`
- 例: `[_]20251111-125217.txt` → `%5B_%5D20251111-125217.txt`

### Q: 401エラーが返される

A: API Keyが正しいか確認してください。`Authorization: Bearer {API_KEY}` の形式で送信されているか確認してください。

### Q: 400エラー「Invalid filename or access denied」が返される

A: 以下を確認してください：
- ファイル名に `/` や `..` が含まれていないか
- `.txt` 拡張子が付いているか
- `.cache`, `bk`, `tmp` で始まるファイル名になっていないか

### Q: 409エラー「File already exists」が返される

A: 同一秒に複数の投稿を作成しようとした場合に発生します。1秒待ってから再試行してください。

### Q: 429エラー（レート制限）が返される

A: 1分間に60リクエストを超えています。リクエスト間隔を調整してください。

---

## 論文API

### 論文アップロード

PDFファイルをアップロードし、バックグラウンドで処理（テキスト抽出など）を開始します。

**エンドポイント:** `POST /api/papers`

**リクエストヘッダー:**
```
Authorization: Bearer {API_KEY}
Content-Type: multipart/form-data
```

**リクエストボディ:**
- `file`: PDFファイル（必須）

**レスポンス（成功）:**
```json
{
  "status": "accepted",
  "message": "Upload successful. Processing started.",
  "data": {
    "pdf_id": "abc123def456...",
    "original_filename": "論文タイトル.pdf",
    "is_new": true
  }
}
```

**HTTPステータスコード:** `202 Accepted`

**curlコマンド例:**
```bash
curl -X POST "https://paper.path-finder.jp/api/papers" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@./論文.pdf"
```

**Pythonコード例:**
```python
import requests

response = requests.post(
    "https://paper.path-finder.jp/api/papers",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    files={"file": open("論文.pdf", "rb")}
)
result = response.json()
print(f"PDF ID: {result['data']['pdf_id']}")
```

**エラーレスポンス:**

| HTTPステータス | 説明 | レスポンス例 |
|---|---|---|
| 400 Bad Request | ファイルなし、またはPDF以外 | `{"status": "error", "message": "Only PDF files are allowed"}` |
| 401 Unauthorized | API Key認証失敗 | `{"status": "error", "message": "Invalid API key"}` |
| 429 Too Many Requests | レート制限超過（30/分） | Flask-Limiterのデフォルトレスポンス |
| 500 Internal Server Error | サーバーエラー | `{"status": "error", "message": "Internal server error"}` |

**備考:**
- 同一ファイル（SHA256ハッシュが一致）は重複保存されません
- `is_new: false` の場合、ファイルは既に存在していたことを示します
- 処理完了の確認は `GET /api/papers/{pdf_id}` で行えます

---

## 変更履歴

### 2026-01-31
- 論文アップロードAPI（`POST /api/papers`）を追加
- Web UI改善: ドロップ即処理開始に変更

### 2025-11-11
- 初版リリース
- MVP機能（新規作成、取得、編集）を実装
- API Key認証を実装
- バックアップ機能を実装（`_YYYYmmdd-HH`形式）

---

## お問い合わせ

APIに関するご質問やバグ報告は、システム管理者までご連絡ください。
