#!/usr/bin/env python3
"""
# PaperNote PDF処理ツール (PDF to PaperNote Processor)

## プログラム概要 (Program Overview)
このプログラムは学術論文のPDFファイルを処理し、PaperNoteシステム用の以下のファイルを生成します：

- PDFファイルのコピー（ハッシュ値でリネーム）
- 添付ファイル（al-プレフィックスファイル）の検出とコピー
- Twitter Card用の画像（PDFの1ページ目から生成）
- 論文のクリーンテキスト（PDFからテキストを抽出して整形）
- 論文のタイトルを含むメモファイル（AI抽出）
- 論文の章ごとの要約（AI生成）
- 論文の評価（査読レポート、AI生成）

このプログラムはAnthropicのClaude APIまたはOpenAIのAPIを使用して、論文のタイトル抽出、要約生成、
および評価レポートの作成を行います。APIキーは設定ファイル（/home/ec2-user/paper/config.yaml）から読み込まれます。

## 使用方法 (Usage Instructions)
基本的な使用方法：
```
python pdf_to_papernote.py [オプション] <PDFファイル> [<PDFファイル> ...]
```

### オプション
- `-output`: 論文メタデータに基づいたディレクトリ構造でファイルを別途出力します
  ファイルは以下の形式でコピーされます：
  - tmp/{発行年月}_{論文タイトル}/paper.pdf        - 元のPDFファイル
  - tmp/{発行年月}_{論文タイトル}/al-paper.pdf     - 添付PDFファイル（存在する場合）
  - tmp/{発行年月}_{論文タイトル}/summary.txt      - 論文の要約
  - tmp/{発行年月}_{論文タイトル}/summary2.txt     - 論文の評価（査読）

- `-openai`: 要約や評価の生成にClaudeの代わりにOpenAIのo3-miniモデルを使用します
  このオプションが指定されない場合は、従来通りClaudeを使用します

### 出力ディレクトリ構造
プログラムは以下のディレクトリ構造を作成し、ファイルを保存します：
- ./pdfs/            - ハッシュ値でリネームされたPDFファイル
- ./memo/            - 論文タイトルを含むメモファイル
- ./clean_text/      - PDFから抽出されたクリーンテキスト
- ./static/tw/       - Twitter Card用の画像
- ./pdfs-attach/     - 添付ファイル（al-プレフィックスファイル）
- ./summary/         - 論文の章ごとの要約
- ./summary2/        - 論文の評価（査読）
- ./tmp/             - メタデータベースのディレクトリ（-outputオプション使用時）

## サンプルコマンド (Sample Commands)
1. 単一のPDFファイルを処理する:
   ```
   python pdf_to_papernote.py example.pdf
   ```

2. 複数のPDFファイルを個別に指定して処理する:
   ```
   python pdf_to_papernote.py a.pdf b.pdf foo.pdf hoge.pdf
   ```

3. ワイルドカードを使用して全てのPDFファイルを処理する:
   ```
   python pdf_to_papernote.py *.pdf
   ```

4. メタデータベースのディレクトリ出力を有効にして処理する:
   ```
   python pdf_to_papernote.py -output example.pdf
   python pdf_to_papernote.py -output *.pdf
   ```

5. OpenAIのモデルを使用して処理する:
   ```
   python pdf_to_papernote.py -openai example.pdf
   ```

6. 複数のオプションを組み合わせる:
   ```
   python pdf_to_papernote.py -output -openai example.pdf
   ```

7. オプションなしで実行するとヘルプ情報が表示されます:
   ```
   python pdf_to_papernote.py
   ```
"""
import argparse
import os
import hashlib
import threading
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
from pdfminer.high_level import extract_text
import re
import sys
import anthropic  # Anthropic APIを使用するためのライブラリ
import openai     # OpenAI APIを使用するためのライブラリ
import yaml       # YAML設定ファイルを読み込むためのライブラリ

def calculate_sha256(file_path):
    """ファイルのSHA256ハッシュを計算"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def ensure_directories():
    """必要なディレクトリを作成"""
    directories = [
        './pdfs',
        './memo',
        './clean_text',
        './static/tw',
        './pdfs-attach',  # 添付ファイル用ディレクトリ
        './summary',      # 要約用ディレクトリ
        './summary2',     # 2つ目の要約用ディレクトリ
        './tmp'           # 整理されたファイル用の親ディレクトリ
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def crop_and_resize_image(image, target_width, target_height):
    """画像をクロップしてリサイズ"""
    original_width, original_height = image.size
    target_aspect_ratio = target_width / target_height
    original_aspect_ratio = original_width / original_height
    
    if target_aspect_ratio <= original_aspect_ratio:
        new_height = original_height
        new_width = int(target_aspect_ratio * new_height)
    else:
        new_width = original_width
        new_height = int(new_width / target_aspect_ratio)
    
    left = (original_width - new_width) // 2
    top = 0
    right = left + new_width
    bottom = top + new_height
    
    cropped_image = image.crop((left, top, right, bottom))
    resized_image = cropped_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    return resized_image

def pdf_to_twitter_card(pdf_path, output_dir):
    """PDFの1ページ目からTwitterカード用の画像を生成"""
    try:
        output_file_path = output_dir / (pdf_path.stem + '.png')
        
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

def extract_text_from_pdf(file_path):
    """PDFからテキストを抽出"""
    try:
        text = extract_text(file_path)
        return text
    except Exception as e:
        print(f"Error extracting text from {file_path}: {str(e)}")
        return ""
def clean_extracted_text(text):
    """抽出したテキストをクリーニング"""
    text = text.replace('-\n', '')
    text = re.sub(r'\s+', ' ', text)
    return text

def load_anthropic_api_key():
    """
    Anthropic APIキーを設定ファイルから読み込む
    
    Returns:
        str: APIキー、読み込みに失敗した場合はNone
    """
    config_path = '/home/ec2-user/paper/config.yaml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        api_key = config.get('anthropic_api_key')
        if not api_key:
            print("Anthropic APIキーが設定ファイルに見つかりません")
            return None
            
        return api_key
    except Exception as e:
        print(f"設定ファイルの読み込みエラー: {e}")
        return None

def load_openai_api_key():
    """
    OpenAI APIキーを設定ファイルから読み込む
    
    Returns:
        str: APIキー、読み込みに失敗した場合はNone
    """
    config_path = '/home/ec2-user/paper/config.yaml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        api_key = config.get('openai_api_key')
        if not api_key:
            print("OpenAI APIキーが設定ファイルに見つかりません")
            return None
            
        return api_key
    except Exception as e:
        print(f"設定ファイルの読み込みエラー: {e}")
        return None

def extract_paper_metadata(text, api_key):
    """
    論文テキスト全体からClaudeを使って論文のメタデータ（タイトル、掲載雑誌名、発行年月）を抽出
    
    Args:
        text (str): 論文の全テキスト
        api_key (str): AnthropicのAPIキー
    
    Returns:
        dict: 抽出されたメタデータ（タイトル、掲載雑誌名、発行年月）、エラー時はデフォルト値を含む辞書
    """
    # テキストが長すぎる場合は、重要な部分を抽出（冒頭、中間、末尾）
    text_length = len(text)
    if text_length > 15000:
        # 冒頭5000文字、末尾3000文字、中間から2000文字を抽出
        text_start = text[:5000]
        text_end = text[-3000:]
        middle_start = text_length // 2 - 1000
        text_middle = text[middle_start:middle_start + 2000]
        processed_text = f"{text_start}\n\n[...中略...]\n\n{text_middle}\n\n[...中略...]\n\n{text_end}"
    else:
        processed_text = text
    
    # Claudeへのプロンプト
    prompt = """
論文テキストから以下の情報を抽出してください：
1. 論文のタイトル
2. 掲載雑誌名
3. 発行年月（YYYYMM形式、例：202503）

以下の形式で返してください：
タイトル: [論文タイトル]
雑誌名: [掲載雑誌名]
発行年月: [YYYYMM]

情報が見つからない場合は「不明」と記入してください。
余計な説明は不要です。

論文テキスト:
"""
    
    try:
        # Anthropic APIクライアントを初期化
        client = anthropic.Anthropic(api_key=api_key)
        
        # Claudeに問い合わせ
        message = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": f"{prompt}\n\n{processed_text}"}
            ]
        )
        
        # レスポンスからメタデータを抽出
        response_text = message.content[0].text.strip()
        
        # 正規表現でメタデータを抽出
        title_match = re.search(r'タイトル:\s*(.+)', response_text)
        journal_match = re.search(r'雑誌名:\s*(.+)', response_text)
        date_match = re.search(r'発行年月:\s*(.+)', response_text)
        
        # 抽出結果を辞書に格納
        metadata = {
            "title": title_match.group(1).strip() if title_match else "不明",
            "journal": journal_match.group(1).strip() if journal_match else "不明",
            "date": date_match.group(1).strip() if date_match else "不明"
        }
        
        # 日付形式の正規化（YYYYMM形式に）
        if metadata["date"] != "不明":
            # 数字だけを抽出
            date_digits = re.sub(r'\D', '', metadata["date"])
            
            # YYYYMM形式になっているか確認
            if len(date_digits) >= 6:
                metadata["date"] = date_digits[:6]  # 先頭6桁を使用
            else:
                metadata["date"] = "不明"
        
        return metadata
    
    except Exception as e:
        print(f"Claude APIの呼び出しエラー: {e}")
        return {"title": "不明", "journal": "不明", "date": "不明"}

def extract_paper_title(text, api_key):
    """
    テキストの冒頭部分からClaudeを使って論文タイトルを抽出（後方互換性のため維持）
    
    Args:
        text (str): 論文のテキスト
        api_key (str): AnthropicのAPIキー
    
    Returns:
        str: 抽出された論文タイトル、エラー時はNone
    """
    # メタデータ抽出関数を使用
    metadata = extract_paper_metadata(text, api_key)
    return metadata["title"] if metadata["title"] != "不明" else None

def extract_paper_metadata_openai(text, api_key):
    """
    論文テキスト全体からOpenAIのモデルを使って論文のメタデータ（タイトル、掲載雑誌名、発行年月）を抽出
    
    Args:
        text (str): 論文の全テキスト
        api_key (str): OpenAIのAPIキー
    
    Returns:
        dict: 抽出されたメタデータ（タイトル、掲載雑誌名、発行年月）、エラー時はデフォルト値を含む辞書
    """
    # テキストが長すぎる場合は、重要な部分を抽出（冒頭、中間、末尾）
    text_length = len(text)
    if text_length > 15000:
        # 冒頭5000文字、末尾3000文字、中間から2000文字を抽出
        text_start = text[:5000]
        text_end = text[-3000:]
        middle_start = text_length // 2 - 1000
        text_middle = text[middle_start:middle_start + 2000]
        processed_text = f"{text_start}\n\n[...中略...]\n\n{text_middle}\n\n[...中略...]\n\n{text_end}"
    else:
        processed_text = text
    
    # OpenAIへのプロンプト
    system_prompt = """あなたは学術論文のメタデータを抽出する専門家です。
与えられた論文テキストから以下の情報を抽出してください：
1. 論文のタイトル
2. 掲載雑誌名
3. 発行年月（YYYYMM形式、例：202503）

情報が見つからない場合は「不明」と記入してください。
余計な説明は不要です。"""

    user_prompt = f"""以下の論文テキストからメタデータを抽出し、以下の形式で返してください：

タイトル: [論文タイトル]
雑誌名: [掲載雑誌名]
発行年月: [YYYYMM]

論文テキスト:
{processed_text}"""
    
    try:
        # OpenAI APIクライアントを初期化
        client = openai.OpenAI(api_key=api_key)
        
        # OpenAIに問い合わせ
        response = client.chat.completions.create(
            model="o3-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # レスポンスからメタデータを抽出
        response_text = response.choices[0].message.content.strip()
        
        # 正規表現でメタデータを抽出
        title_match = re.search(r'タイトル:\s*(.+)', response_text)
        journal_match = re.search(r'雑誌名:\s*(.+)', response_text)
        date_match = re.search(r'発行年月:\s*(.+)', response_text)
        
        # 抽出結果を辞書に格納
        metadata = {
            "title": title_match.group(1).strip() if title_match else "不明",
            "journal": journal_match.group(1).strip() if journal_match else "不明",
            "date": date_match.group(1).strip() if date_match else "不明"
        }
        
        # 日付形式の正規化（YYYYMM形式に）
        if metadata["date"] != "不明":
            # 数字だけを抽出
            date_digits = re.sub(r'\D', '', metadata["date"])
            
            # YYYYMM形式になっているか確認
            if len(date_digits) >= 6:
                metadata["date"] = date_digits[:6]  # 先頭6桁を使用
            else:
                metadata["date"] = "不明"
        
        return metadata
    
    except Exception as e:
        print(f"OpenAI APIの呼び出しエラー: {e}")
        return {"title": "不明", "journal": "不明", "date": "不明"}

def extract_paper_title_openai(text, api_key):
    """
    テキストからOpenAIのモデルを使って論文タイトルを抽出（後方互換性のため維持）
    
    Args:
        text (str): 論文のテキスト
        api_key (str): OpenAIのAPIキー
    
    Returns:
        str: 抽出された論文タイトル、エラー時はNone
    """
    # メタデータ抽出関数を使用
    metadata = extract_paper_metadata_openai(text, api_key)
    return metadata["title"] if metadata["title"] != "不明" else None
def generate_paper_summary(text, api_key, metadata=None):
    """
    論文テキストをClaudeに送信して章ごとの要約を生成
    
    Args:
        text (str): 論文の全テキスト
        api_key (str): AnthropicのAPIキー
        metadata (dict, optional): 論文のメタデータ（タイトル、掲載雑誌名、発行年月）
    
    Returns:
        str: Markdown形式の要約、エラー時はNone
    """
    # メタデータヘッダーを作成
    metadata_header = ""
    if metadata:
        metadata_header = f"""論文タイトル：{metadata.get('title', '（取得できませんでした）')}
論文掲載雑誌名：{metadata.get('journal', '（取得できませんでした）')}
論文発行年月：{metadata.get('date', '（取得できませんでした）')}

"""
    
    # プロンプトを定義
    prompt = """
# 以下の論文について、章ごとに、多くの要約項目で日本語を使って要約してください。
# 以下のテンプレートに従ってMarkdown形式で出力してください

{テンプレート}=
# 章1
- 要約項目1
- 要約項目2
# 章2
- 要約項目1

{論文テキスト}=
"""
    
    try:
        # Anthropic APIクライアントを初期化
        client = anthropic.Anthropic(api_key=api_key)
        
        # Claudeに問い合わせ - 新しいAPIバージョン用の呼び出し方法
        message = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=8000,  # 出力の最大長を指定
            messages=[
                {"role": "user", "content": f"{prompt}\n\n{text}"}
            ]
        )
        
        # レスポンスから要約を抽出
        summary = message.content[0].text.strip()
        
        # メタデータヘッダーを追加
        if metadata_header:
            summary = metadata_header + summary
            
        return summary
    
    except Exception as e:
        print(f"Claude APIの呼び出しエラー: {e}")
        return None

def generate_paper_summary_openai(text, api_key, metadata=None):
    """
    論文テキストをOpenAIのモデルに送信して章ごとの要約を生成
    
    Args:
        text (str): 論文の全テキスト
        api_key (str): OpenAIのAPIキー
        metadata (dict, optional): 論文のメタデータ（タイトル、掲載雑誌名、発行年月）
    
    Returns:
        str: Markdown形式の要約、エラー時はNone
    """
    # メタデータヘッダーを作成
    metadata_header = ""
    if metadata:
        metadata_header = f"""論文タイトル：{metadata.get('title', '（取得できませんでした）')}
論文掲載雑誌名：{metadata.get('journal', '（取得できませんでした）')}
論文発行年月：{metadata.get('date', '（取得できませんでした）')}

"""
    
    # システムプロンプトとユーザープロンプトを定義
    system_prompt = """あなたは学術論文の要約を作成する専門家です。
論文の内容を章ごとに要約し、各章の重要なポイントを箇条書きで示してください。
日本語で出力し、Markdown形式で整形してください。"""
    
    user_prompt = f"""以下の論文を章ごとに要約してください。
以下のテンプレートに従ってMarkdown形式で出力してください：

# 章1
- 要約項目1
- 要約項目2
# 章2
- 要約項目1

論文テキスト:
{text}"""
    
    try:
        # OpenAI APIクライアントを初期化
        client = openai.OpenAI(api_key=api_key)
        
        # OpenAIに問い合わせ
        response = client.chat.completions.create(
            model="o3-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # レスポンスから要約を抽出
        summary = response.choices[0].message.content.strip()
        
        # メタデータヘッダーを追加
        if metadata_header:
            summary = metadata_header + summary
            
        return summary
    
    except Exception as e:
        print(f"OpenAI APIの呼び出しエラー: {e}")
        return None

def generate_paper_review(text, api_key, metadata=None):
    """
    論文テキストをClaudeに送信して論文の評価を生成
    
    Args:
        text (str): 論文の全テキスト
        api_key (str): AnthropicのAPIキー
        metadata (dict, optional): 論文のメタデータ（タイトル、掲載雑誌名、発行年月）
    
    Returns:
        str: Markdown形式の論文評価、エラー時はNone
    """
    # メタデータヘッダーを作成
    metadata_header = ""
    if metadata:
        metadata_header = f"""論文タイトル：{metadata.get('title', '（取得できませんでした）')}
論文掲載雑誌名：{metadata.get('journal', '（取得できませんでした）')}
論文発行年月：{metadata.get('date', '（取得できませんでした）')}

"""
    
    # プロンプトを定義
    prompt = """
# あなたはトップジャーナルの論文査読者です。以下の論文について、新規性、言及されている全ての関連研究との相違点、有効性、信頼性を、日本語を使って、まとめてください。
# 以下のテンプレートに従ってMarkdown形式で出力してください

{テンプレート}=
# 新規性
- 内容
# 言及されている全ての関連研究との相違点
- 内容
# 有効性
- 内容
# 信頼性
- 内容

{論文テキスト}=
"""
    
    try:
        # Anthropic APIクライアントを初期化
        client = anthropic.Anthropic(api_key=api_key)
        
        # Claudeに問い合わせ - 最大トークン数を設定
        message = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=8000,  # 出力の最大長を指定
            messages=[
                {"role": "user", "content": f"{prompt}\n\n{text}"}
            ]
        )
        
        # レスポンスから評価を抽出
        review = message.content[0].text.strip()
        
        # メタデータヘッダーを追加
        if metadata_header:
            review = metadata_header + review
            
        return review
    
    except Exception as e:
        print(f"Claude APIの呼び出しエラー: {e}")
        return None

def generate_paper_review_openai(text, api_key, metadata=None):
    """
    論文テキストをOpenAIのモデルに送信して論文の評価を生成
    
    Args:
        text (str): 論文の全テキスト
        api_key (str): OpenAIのAPIキー
        metadata (dict, optional): 論文のメタデータ（タイトル、掲載雑誌名、発行年月）
    
    Returns:
        str: Markdown形式の論文評価、エラー時はNone
    """
    # メタデータヘッダーを作成
    metadata_header = ""
    if metadata:
        metadata_header = f"""論文タイトル：{metadata.get('title', '（取得できませんでした）')}
論文掲載雑誌名：{metadata.get('journal', '（取得できませんでした）')}
論文発行年月：{metadata.get('date', '（取得できませんでした）')}

"""
    
    # システムプロンプトとユーザープロンプトを定義
    system_prompt = """あなたはトップジャーナルの論文査読者です。
学術論文を評価して、新規性、関連研究との相違点、有効性、信頼性について詳細な査読レポートを作成してください。
日本語で出力し、Markdown形式で整形してください。"""
    
    user_prompt = f"""以下の論文を査読し、評価してください。
以下のテンプレートに従ってMarkdown形式で出力してください：

# 新規性
- 内容
# 言及されている全ての関連研究との相違点
- 内容
# 有効性
- 内容
# 信頼性
- 内容

論文テキスト:
{text}"""
    
    try:
        # OpenAI APIクライアントを初期化
        client = openai.OpenAI(api_key=api_key)
        
        # OpenAIに問い合わせ
        response = client.chat.completions.create(
            model="o3-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # レスポンスから評価を抽出
        review = response.choices[0].message.content.strip()
        
        # メタデータヘッダーを追加
        if metadata_header:
            review = metadata_header + review
            
        return review
    
    except Exception as e:
        print(f"OpenAI APIの呼び出しエラー: {e}")
        return None

def pdf_to_cleantext(pdf_path, clean_text_dir):
    """PDFからテキストを抽出してクリーニング"""
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

def sanitize_directory_name(title):
    """
    ディレクトリ名として安全に使用できるように論文タイトルを整形する
    
    Args:
        title (str): 論文のタイトル
    
    Returns:
        str: 安全なディレクトリ名
    """
    if not title:
        return "untitled"
    
    # 1. 禁止文字（WindowsとLinuxの両方で問題になりうる文字）を置換
    # Windows: \ / : * ? " < > |
    # Linux: / と NULL文字が主な制約
    safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
    
    # 2. 先頭と末尾のスペース、ドット、特殊文字を削除
    safe_title = safe_title.strip('. \t\n\r')
    
    # 3. 連続する特殊文字やスペースを単一のアンダースコアに置換
    safe_title = re.sub(r'[\s\-_]+', '_', safe_title)
    
    # 4. 使用できない名前（WindowsのCON, PRN, AUX, NUL等）を避ける
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                     'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                     'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
    
    if safe_title.upper() in reserved_names:
        safe_title = f"paper_{safe_title}"
    
    # 5. 長すぎるタイトルは切り詰める（大体200文字程度で）
    if len(safe_title) > 200:
        safe_title = safe_title[:197] + '...'
    
    # 6. 空文字列になってしまった場合はデフォルト名を使用
    if not safe_title:
        safe_title = "untitled_paper"
    
    return safe_title

def copy_files_with_title_structure(pdf_path, file_hash, metadata, output_enabled=False):
    """
    論文メタデータに基づいたディレクトリ構造でファイルをコピーする
    
    Args:
        pdf_path (str): 元のPDFファイルパス
        file_hash (str): ファイルのハッシュ値
        metadata (dict): 論文のメタデータ（タイトル、掲載雑誌名、発行年月）
        output_enabled (bool): outputオプションが有効かどうか
    
    Returns:
        list: コピーされたファイルのパスのリスト
    """
    if not output_enabled or not metadata:
        return []
    
    title = metadata.get('title', '')
    date = metadata.get('date', 'unknown')
    
    if not title:
        return []
    
    # 論文タイトルをディレクトリ名として安全に使用できるように整形
    safe_title = sanitize_directory_name(title)
    print(f"ディレクトリ名に変換されたタイトル: {safe_title}")
    
    # 発行年月とタイトルに基づいたディレクトリパスを生成
    dir_name = f"{date}_{safe_title}"
    title_dir = os.path.join('./tmp', dir_name)
    
    # ディレクトリが存在しない場合は作成
    os.makedirs(title_dir, exist_ok=True)
    
    copied_files = []
    
    # 1. 元のPDFファイルをコピー (paper.pdf)
    paper_dest = os.path.join(title_dir, 'paper.pdf')
    try:
        with open(pdf_path, 'rb') as src, open(paper_dest, 'wb') as dst:
            dst.write(src.read())
        copied_files.append(paper_dest)
        print(f"元のPDFファイルをコピーしました: {paper_dest}")
    except Exception as e:
        print(f"PDFファイルのコピー中にエラーが発生しました: {e}")
    
    # 2. al-プレフィックスファイルをコピー (al-paper.pdf)
    attach_file = os.path.join('./pdfs-attach', f"{file_hash}_01.pdf")
    if os.path.exists(attach_file):
        al_paper_dest = os.path.join(title_dir, 'al-paper.pdf')
        try:
            with open(attach_file, 'rb') as src, open(al_paper_dest, 'wb') as dst:
                dst.write(src.read())
            copied_files.append(al_paper_dest)
            print(f"添付PDFファイルをコピーしました: {al_paper_dest}")
        except Exception as e:
            print(f"添付PDFファイルのコピー中にエラーが発生しました: {e}")
    
    # 3. 要約ファイルをコピー (summary.txt)
    summary_path = os.path.join('./summary', f"{file_hash}.txt")
    if os.path.exists(summary_path):
        summary_dest = os.path.join(title_dir, 'summary.txt')
        try:
            with open(summary_path, 'r', encoding='utf-8') as src, open(summary_dest, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            copied_files.append(summary_dest)
            print(f"要約ファイルをコピーしました: {summary_dest}")
        except Exception as e:
            print(f"要約ファイルのコピー中にエラーが発生しました: {e}")
    
    # 4. 論文評価ファイルをコピー (summary2.txt)
    summary2_path = os.path.join('./summary2', f"{file_hash}.txt")
    if os.path.exists(summary2_path):
        summary2_dest = os.path.join(title_dir, 'summary2.txt')
        try:
            with open(summary2_path, 'r', encoding='utf-8') as src, open(summary2_dest, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            copied_files.append(summary2_dest)
            print(f"論文評価ファイルをコピーしました: {summary2_dest}")
        except Exception as e:
            print(f"論文評価ファイルのコピー中にエラーが発生しました: {e}")
    
    return copied_files

def process_pdf(pdf_path, output_enabled=False, openai_enabled=False):
    """
    PDFファイルの処理メイン関数
    
    Args:
        pdf_path (str): 処理対象のPDFファイルパス
        output_enabled (bool): タイトルに基づいたディレクトリ構造でファイルを別途出力するかどうか
        openai_enabled (bool): OpenAIのモデルを使用するかどうか（Falseの場合はClaudeを使用）
    """
    try:
        # ディレクトリの準備
        ensure_directories()
        
        # ファイルの存在確認
        if not os.path.exists(pdf_path):
            print(f"エラー: ファイル {pdf_path} が見つかりません。")
            return False
            
        # ハッシュ値の計算
        file_hash = calculate_sha256(pdf_path)
        print(f"ファイルハッシュ: {file_hash}")
        
        # PDFファイルのコピー
        pdf_filename = f"{file_hash}.pdf"
        pdf_destination = os.path.join('./pdfs', pdf_filename)
        if not os.path.exists(pdf_destination):
            with open(pdf_path, 'rb') as src, open(pdf_destination, 'wb') as dst:
                dst.write(src.read())
            print(f"PDFファイルをコピーしました: {pdf_destination}")
        
        # al-プレフィックスファイルの確認と処理
        pdf_dir = os.path.dirname(pdf_path)
        pdf_basename = os.path.basename(pdf_path)
        
        # 添付ファイルを探すための複数のパターンを試行
        al_pdf_path = None
        
        # パターン1: 単純に al- を付ける (例: al-2205.01202v2.pdf)
        candidate_path = os.path.join(pdf_dir, f"al-{pdf_basename}")
        if os.path.exists(candidate_path):
            al_pdf_path = candidate_path
            print(f"添付ファイルを見つけました (パターン1): {al_pdf_path}")
        
        # パターン2: ドットを削除したバージョン (例: al-220501202v2.pdf)
        if al_pdf_path is None:
            no_dot_basename = pdf_basename.replace('.', '')
            candidate_path = os.path.join(pdf_dir, f"al-{no_dot_basename}")
            if os.path.exists(candidate_path):
                al_pdf_path = candidate_path
                print(f"添付ファイルを見つけました (パターン2): {al_pdf_path}")
        
        # パターン3: スペース、ハイフン、ドットを削除したバージョン
        if al_pdf_path is None:
            # 拡張子を除いたファイル名を取得
            pdf_name_without_ext = os.path.splitext(pdf_basename)[0]
            # スペース、ハイフン、ドットを削除したバージョンを作成
            no_space_hyphen_dot_name = re.sub(r'[\s\-\.]+', '', pdf_name_without_ext)
            candidate_path = os.path.join(pdf_dir, f"al-{no_space_hyphen_dot_name}.pdf")
            if os.path.exists(candidate_path):
                al_pdf_path = candidate_path
                print(f"添付ファイルを見つけました (パターン3): {al_pdf_path}")
        
        # パターン4: ディレクトリ内のすべての al- ファイルから部分一致で検索
        if al_pdf_path is None:
            pdf_name_without_ext = os.path.splitext(pdf_basename)[0]  # 拡張子を除いたファイル名
            # ドットを削除したバージョンも用意
            no_dot_name = pdf_name_without_ext.replace('.', '')
            # スペース、ハイフン、ドットを削除したバージョンも用意
            no_space_hyphen_dot_name = re.sub(r'[\s\-\.]+', '', pdf_name_without_ext)
            
            # ディレクトリ内のファイルを検索
            for filename in os.listdir(pdf_dir):
                if filename.startswith('al-') and filename.endswith('.pdf'):
                    # 拡張子とプレフィックスを除いたファイル名
                    al_name = os.path.splitext(filename[3:])[0]
                    
                    # 元のファイル名またはドットなしバージョンまたはスペース/ハイフン/ドットなしバージョンとの部分一致を確認
                    if (pdf_name_without_ext in al_name) or (no_dot_name in al_name) or (no_space_hyphen_dot_name in al_name):
                        al_pdf_path = os.path.join(pdf_dir, filename)
                        print(f"添付ファイルを見つけました (パターン4): {al_pdf_path}")
                        break
        
        # 添付ファイルが見つかった場合は処理
        if al_pdf_path:
            # 添付ファイルのコピー先パス
            attach_destination = os.path.join('./pdfs-attach', f"{file_hash}_01.pdf")
            
            # ファイルをコピー
            if not os.path.exists(attach_destination):
                with open(al_pdf_path, 'rb') as src, open(attach_destination, 'wb') as dst:
                    dst.write(src.read())
                print(f"添付ファイルをコピーしました: {attach_destination}")
            else:
                print(f"添付ファイルは既に存在します: {attach_destination}")
        else:
            print(f"添付ファイル (al-プレフィックス) は見つかりませんでした: {pdf_basename}")
        
        # Twitter Card画像の生成
        pdf_to_twitter_card(Path(pdf_destination), Path('./static/tw'))
        
        # テキスト抽出とクリーニング
        success = pdf_to_cleantext(pdf_destination, './clean_text')
        if not success:
            print("テキスト抽出に失敗しました。")
            return False
        
        # 生成したファイルのリスト
        generated_files = []
        
        # PDFファイルとクリーンテキスト
        pdf_file = os.path.join('./pdfs', f"{file_hash}.pdf")
        clean_text_path = os.path.join('./clean_text', f"{file_hash}.txt")
        generated_files.append(pdf_file)
        generated_files.append(clean_text_path)
        
        # al-プレフィックスファイルの処理結果
        attach_file = os.path.join('./pdfs-attach', f"{file_hash}_01.pdf")
        if os.path.exists(attach_file):
            generated_files.append(attach_file)
        
        # Twitter Card画像
        twitter_card = os.path.join('./static/tw', f"{file_hash}.png")
        if os.path.exists(twitter_card):
            generated_files.append(twitter_card)
            
        # メモファイルの作成（メタデータ抽出機能を追加）
        memo_path = os.path.join('./memo', f"{file_hash}.txt")
        
        # メタデータを格納する変数
        paper_metadata = None
        
        # クリーンテキストからメタデータを抽出
        if os.path.exists(clean_text_path):
            try:
                # テキストファイルの内容を読み込む
                with open(clean_text_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                # OpenAI/Anthropic APIキーを読み込む
                if openai_enabled:
                    api_key = load_openai_api_key()
                    if api_key:
                        # メタデータを抽出（OpenAI）
                        print("論文メタデータをOpenAIで抽出中...")
                        paper_metadata = extract_paper_metadata_openai(text, api_key)
                    else:
                        # OpenAI APIキーが取得できない場合はAnthropicにフォールバック
                        print("OpenAI APIキーが取得できなかったため、Claudeを使用します。")
                        api_key = load_anthropic_api_key()
                        if api_key:
                            print("論文メタデータをClaudeで抽出中...")
                            paper_metadata = extract_paper_metadata(text, api_key)
                        else:
                            paper_metadata = {"title": "不明", "journal": "不明", "date": "不明"}
                else:
                    # 従来通りAnthropicを使用
                    api_key = load_anthropic_api_key()
                    if api_key:
                        # メタデータを抽出（Claude）
                        print("論文メタデータをClaudeで抽出中...")
                        paper_metadata = extract_paper_metadata(text, api_key)
                    else:
                        paper_metadata = {"title": "不明", "journal": "不明", "date": "不明"}
                
                # タイトルを取得
                title = paper_metadata.get('title', '不明')
                
                if title != '不明':
                    # タイトルを1行目に書き込む（元のファイル名は書き込まない）
                    with open(memo_path, 'w', encoding='utf-8') as memo_file:
                        memo_file.write(f"{title}\n")
                    print(f"論文タイトルを抽出しました: {title}")
                    print(f"論文掲載雑誌名: {paper_metadata.get('journal', '不明')}")
                    print(f"論文発行年月: {paper_metadata.get('date', '不明')}")
                    generated_files.append(memo_path)
                else:
                    # タイトル抽出に失敗した場合
                    with open(memo_path, 'w', encoding='utf-8') as memo_file:
                        memo_file.write(os.path.basename(pdf_path) + '\n')
                    print("タイトル抽出に失敗しました。元のファイル名をメモに保存しました。")
                    generated_files.append(memo_path)
                    paper_metadata = {"title": os.path.basename(pdf_path), "journal": "不明", "date": "不明"}
            except Exception as e:
                # エラーが発生した場合
                print(f"メタデータ抽出中にエラーが発生しました: {e}")
                with open(memo_path, 'w', encoding='utf-8') as memo_file:
                    memo_file.write(os.path.basename(pdf_path) + '\n')
                generated_files.append(memo_path)
                paper_metadata = {"title": os.path.basename(pdf_path), "journal": "不明", "date": "不明"}
        else:
            # クリーンテキストファイルが見つからない場合
            with open(memo_path, 'w', encoding='utf-8') as memo_file:
                memo_file.write(os.path.basename(pdf_path) + '\n')
            print("クリーンテキストファイルが見つからないため、元のファイル名をメモに保存しました。")
            generated_files.append(memo_path)
            paper_metadata = {"title": os.path.basename(pdf_path), "journal": "不明", "date": "不明"}
        
        # 要約の生成と保存
        summary_path = os.path.join('./summary', f"{file_hash}.txt")
        
        # クリーンテキストから要約を生成
        if os.path.exists(clean_text_path):
            try:
                # テキストファイルの内容を読み込む
                with open(clean_text_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                # OpenAI/Anthropic APIキーを読み込む
                if openai_enabled:
                    api_key = load_openai_api_key()
                    if api_key:
                        # 要約を生成（OpenAI）
                        print("論文の要約をOpenAIで生成中...")
                        summary = generate_paper_summary_openai(text, api_key, paper_metadata)
                    else:
                        # OpenAI APIキーが取得できない場合はAnthropicにフォールバック
                        print("OpenAI APIキーが取得できなかったため、Claudeを使用します。")
                        api_key = load_anthropic_api_key()
                        if api_key:
                            print("論文の要約をClaudeで生成中...")
                            summary = generate_paper_summary(text, api_key, paper_metadata)
                        else:
                            summary = None
                else:
                    # 従来通りAnthropicを使用
                    api_key = load_anthropic_api_key()
                    if api_key:
                        # 要約を生成（Claude）
                        print("論文の要約をClaudeで生成中...")
                        summary = generate_paper_summary(text, api_key, paper_metadata)
                    else:
                        summary = None
                
                if summary:
                    # 要約をファイルに保存
                    with open(summary_path, 'w', encoding='utf-8') as summary_file:
                        summary_file.write(summary)
                    print(f"論文の要約を保存しました: {summary_path}")
                    generated_files.append(summary_path)
                else:
                    print("要約の生成に失敗しました。")
            except Exception as e:
                print(f"要約生成中にエラーが発生しました: {e}")
        else:
            print(f"クリーンテキストファイル {clean_text_path} が見つからないため、要約生成をスキップします。")
        
        # 論文評価（査読）の生成と保存
        summary2_path = os.path.join('./summary2', f"{file_hash}.txt")
        
        # クリーンテキストから論文評価を生成
        if os.path.exists(clean_text_path):
            try:
                # テキストファイルの内容を読み込む
                with open(clean_text_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                # OpenAI/Anthropic APIキーを読み込む
                if openai_enabled:
                    api_key = load_openai_api_key()
                    if api_key:
                        # 論文評価を生成（OpenAI）
                        print("論文評価（査読）をOpenAIで生成中...")
                        review = generate_paper_review_openai(text, api_key, paper_metadata)
                    else:
                        # OpenAI APIキーが取得できない場合はAnthropicにフォールバック
                        print("OpenAI APIキーが取得できなかったため、Claudeを使用します。")
                        api_key = load_anthropic_api_key()
                        if api_key:
                            print("論文評価（査読）をClaudeで生成中...")
                            review = generate_paper_review(text, api_key, paper_metadata)
                        else:
                            review = None
                else:
                    # 従来通りAnthropicを使用
                    api_key = load_anthropic_api_key()
                    if api_key:
                        # 論文評価を生成（Claude）
                        print("論文評価（査読）をClaudeで生成中...")
                        review = generate_paper_review(text, api_key, paper_metadata)
                    else:
                        review = None
                
                if review:
                    # 評価をファイルに保存
                    with open(summary2_path, 'w', encoding='utf-8') as summary2_file:
                        summary2_file.write(review)
                    print(f"論文評価を保存しました: {summary2_path}")
                    generated_files.append(summary2_path)
                else:
                    print("論文評価の生成に失敗しました。")
            except Exception as e:
                print(f"論文評価生成中にエラーが発生しました: {e}")
        else:
            print(f"クリーンテキストファイル {clean_text_path} が見つからないため、論文評価生成をスキップします。")
        
        # -outputオプションが有効な場合、論文メタデータに基づいたディレクトリ構造でファイルをコピー
        if output_enabled and paper_metadata and paper_metadata.get('title') != '不明':
            print("\n=== 論文メタデータに基づいたディレクトリにファイルをコピーします ===")
            copied_files = copy_files_with_title_structure(pdf_path, file_hash, paper_metadata, output_enabled)
            if copied_files:
                generated_files.extend(copied_files)
                print(f"メタデータベースのディレクトリにファイルをコピーしました: {paper_metadata.get('date', 'unknown')}_{paper_metadata.get('title', '')}")
            else:
                print("メタデータベースのコピーに失敗しました。")
        
        # 処理完了とファイル一覧を表示
        print("\n=== 処理が完了しました ===")
        print("生成されたファイル一覧:")
        for file_path in generated_files:
            print(f"- {file_path}")
        return True
        
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        return False

def show_program_info():
    """プログラムの概要とコマンド例を表示"""
    print("""
===== PaperNote PDF処理ツール =====

このプログラムは学術論文のPDFファイルを処理し、PaperNoteシステム用の以下のファイルを生成します：

- PDFファイルのコピー（ハッシュ値でリネーム）
- 添付ファイル（al-プレフィックスファイル）のコピー
- Twitter Card用の画像
- 論文のクリーンテキスト
- 論文のタイトルを含むメモファイル
- 論文の章ごとの要約
- 論文の評価（査読）

オプション：
  -output    論文メタデータに基づいたディレクトリ構造でファイルを別途出力します。
             以下のような形式でファイルがコピーされます：
             ・tmp/{発行年月}_{論文タイトル}/paper.pdf        - 元のPDFファイル
             ・tmp/{発行年月}_{論文タイトル}/al-paper.pdf     - 添付PDFファイル（存在する場合）
             ・tmp/{発行年月}_{論文タイトル}/summary.txt      - 論文の要約
             ・tmp/{発行年月}_{論文タイトル}/summary2.txt     - 論文の評価（査読）
             
  -openai    要約や評価の生成にClaudeの代わりにOpenAIのo3-miniモデルを使用します。
             このオプションが指定されない場合は、従来通りClaudeを使用します。

使用例：
  1. 単一のPDFファイルを処理する:
     python pdf_to_papernote.py example.pdf
  
  2. 複数のPDFファイルを個別に指定して処理する:
     python pdf_to_papernote.py a.pdf b.pdf foo.pdf hoge.pdf
  
  3. ワイルドカードを使用して全てのPDFファイルを処理する:
     python pdf_to_papernote.py *.pdf
  
  4. メタデータベースのディレクトリ出力を有効にして処理する:
     python pdf_to_papernote.py -output example.pdf
     python pdf_to_papernote.py -output *.pdf
     
  5. OpenAIのモデルを使用して処理する:
     python pdf_to_papernote.py -openai example.pdf
     
  6. 複数のオプションを組み合わせる:
     python pdf_to_papernote.py -output -openai example.pdf
""")

def main():
    parser = argparse.ArgumentParser(description='PDFファイルを処理してPaperNoteシステム用のファイルを生成')
    parser.add_argument('pdf_files', nargs='*', help='処理対象のPDFファイル（複数指定可能）')
    parser.add_argument('-output', action='store_true', help='論文メタデータ（発行年月とタイトル）に基づいたディレクトリ構造でファイルを別途出力する')
    parser.add_argument('-openai', action='store_true', help='要約や評価の生成にClaudeの代わりにOpenAIのモデルを使用する')
    args = parser.parse_args()

    # 引数がない場合、プログラムの概要とコマンド例を表示して終了
    if not args.pdf_files:
        show_program_info()
        return

    # -outputオプションが指定されている場合のメッセージ
    if args.output:
        print("\n-outputオプションが有効です。論文メタデータに基づいたディレクトリにファイルをコピーします。")
        print("出力ディレクトリ: ./tmp/{発行年月}_{論文タイトル}/\n")
        
    # -openaiオプションが指定されている場合のメッセージ
    if args.openai:
        print("\n-openaiオプションが有効です。要約や評価の生成にOpenAIのo3-miniモデルを使用します。\n")

    # 処理したファイル数をカウント
    success_count = 0
    failure_count = 0
    
    # 各PDFファイルを処理
    for pdf_path in args.pdf_files:
        print(f"\n==== ファイル処理開始: {pdf_path} ====")
        
        # メインのPDFファイルを処理（al-プレフィックスファイルの処理も含む）
        if process_pdf(pdf_path, args.output, args.openai):
            success_count += 1
            print(f"ファイル {pdf_path} の処理が成功しました。")
        else:
            failure_count += 1
            print(f"ファイル {pdf_path} の処理に失敗しました。")
    
    # 処理結果の要約を表示
    print("\n=== 処理結果の要約 ===")
    print(f"処理成功: {success_count} ファイル")
    print(f"処理失敗: {failure_count} ファイル")
    print(f"合計: {success_count + failure_count} ファイル")
    
    # 失敗したファイルがある場合、非ゼロの終了コードを返す
    if failure_count > 0:
        sys.exit(1)
    else:
        print("\n=== 完了！ ===")

if __name__ == "__main__":
    main()