#!/usr/bin/env python3
"""
Paper Translate - 論文PDFをページ単位で画像化・テキスト抽出・和訳するスキル

使用方法:
    python paper_translate.py {pdf_id} [--start N] [--end M] [--no-translate] [--dry-run] [--style kansai|standard]

v2.1 変更点:
    - 翻訳スタイルオプション追加（kansai: 関西弁でわかりやすく / standard: 標準語）
    - デフォルトは kansai（調子のよい関西人が素人向けに解説するスタイル）

v2.0 変更点:
    - 長文処理をClaude Codeに委譲（チャンク分割・統合ロジックを廃止）
    - 一時ファイル管理をコンテキストマネージャで確実にクリーンアップ
    - summary/とsummary2/のフォーマットを厳格化
"""

import argparse
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from contextlib import contextmanager

# PyMuPDF (fitz) - PDFの画像変換とページ数取得に使用
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# pdf2image (フォールバック用)
try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

from PIL import Image
from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

# ClaudeCLI のインポート
sys.path.insert(0, os.path.expanduser("~/.claude/skills/claudecli"))
try:
    from claudecli import ClaudeCLI
except ImportError:
    ClaudeCLI = None
    print("[WARN] ClaudeCLI not found. Translation will be skipped.")

# 定数
# 優先順位: 環境変数 PAPER_DIR → カレントディレクトリ
PAPER_DIR = Path(os.environ.get('PAPER_DIR', os.getcwd()))
PDFS_DIR = PAPER_DIR / "pdfs"
MEMO_DIR = PAPER_DIR / "memo"
ATTACH_DIR = PAPER_DIR / "attach"
SUMMARY_DIR = PAPER_DIR / "summary"
SUMMARY2_DIR = PAPER_DIR / "summary2"

# 画像設定
IMAGE_DPI = 150  # 画像品質
IMAGE_MAX_WIDTH = 1200  # 元画像の最大幅（ピクセル）
THUMBNAIL_WIDTH = 400  # サムネイルの幅（ピクセル）

# 長文判定の閾値（この文字数以下ならClaudeCLIで直接処理）
MAX_DIRECT_LENGTH = 80000

# 一時ファイル用ディレクトリ（/tmpではなくプロジェクト内に作成）
# ※ Claude Codeは/tmpへのアクセスがセキュリティ上制限されているため
TEMP_DIR = PAPER_DIR / ".tmp"

# ============================================================
# 翻訳スタイル定義
# ============================================================

TRANSLATION_STYLES = {
    'kansai': """【翻訳スタイル】
- 調子のよい関西人が友達に説明するような口調で翻訳してください
- 専門用語は噛み砕いてわかりやすく説明
- 「〜やねん」「〜やで」「〜やな」「めっちゃ」「ほんまに」「なんでかっていうと」などの関西弁を自然に使用
- 素人でも理解できる表現を心がける
- ただし学術的な正確さは維持し、重要な情報は省略しない
- 堅苦しくなく、読んでいて楽しい文章に""",

    'standard': """【翻訳スタイル】
- 標準的な日本語で翻訳してください
- 学術論文のため、専門用語は適切に訳す
- 正確で読みやすい文章に"""
}

DEFAULT_TRANSLATION_STYLE = 'kansai'


# ============================================================
# 一時ファイル管理
# ============================================================

@contextmanager
def temp_text_file(content: str, prefix: str = "paper_", suffix: str = ".txt"):
    """
    一時ファイルを作成し、処理後に確実に削除するコンテキストマネージャ

    使用例:
        with temp_text_file(full_text, prefix="input_") as temp_path:
            # temp_path を使った処理
        # withブロックを抜けると自動削除

    注意: Claude Codeは/tmpへのアクセスが制限されているため、
    PAPER_DIR/.tmp/ に一時ファイルを作成する
    """
    temp_path = None
    try:
        # 一時ファイル用ディレクトリを作成（存在しない場合）
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        # 一時ファイル作成（PAPER_DIR/.tmp/ 配下に作成）
        fd, temp_name = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=str(TEMP_DIR))
        temp_path = Path(temp_name)

        # 内容を書き込み
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)

        yield temp_path

    finally:
        # 確実に削除（エラー時も含む）
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
                print(f"    [CLEANUP] 一時ファイル削除: {temp_path.name}")
            except Exception as e:
                print(f"    [WARN] 一時ファイル削除失敗: {e}")


def _call_claude_code(prompt: str, timeout_sec: int = 900) -> tuple:
    """
    Claude Codeを非対話モードで呼び出す

    Returns:
        (success: bool, output: str)
    """
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=timeout_sec
        )

        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, f"returncode={result.returncode}\nstderr: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, f"タイムアウト（{timeout_sec}秒）"
    except FileNotFoundError:
        return False, "claude コマンドが見つかりません"
    except Exception as e:
        return False, str(e)


# ============================================================
# PDF処理関数
# ============================================================

def get_pdf_page_count(pdf_path: Path) -> int:
    """PDFのページ数を取得"""
    if HAS_PYMUPDF:
        doc = fitz.open(str(pdf_path))
        count = len(doc)
        doc.close()
        return count
    else:
        with open(pdf_path, 'rb') as f:
            return len(list(PDFPage.get_pages(f)))


def extract_text_from_page(pdf_path: Path, page_num: int) -> str:
    """指定ページからテキストを抽出"""
    try:
        text = extract_text(str(pdf_path), page_numbers=[page_num - 1])
        # テキストのクリーニング
        text = text.strip()
        # ハイフネーションの除去
        text = text.replace('-\n', '')
        return text
    except Exception as e:
        print(f"  [ERROR] テキスト抽出失敗: {e}")
        return ""


def convert_page_to_image(pdf_path: Path, page_num: int, output_path: Path, thumbnail_path: Path) -> bool:
    """指定ページを画像に変換（元画像＋サムネイル）"""
    try:
        if HAS_PYMUPDF:
            # PyMuPDF を使用
            doc = fitz.open(str(pdf_path))
            page = doc[page_num - 1]  # 0-indexed

            # DPIに応じたズーム率を計算（72dpiが基準）
            zoom = IMAGE_DPI / 72
            mat = fitz.Matrix(zoom, zoom)

            # ページを画像に変換
            pix = page.get_pixmap(matrix=mat)

            # PILイメージに変換
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            doc.close()
        elif HAS_PDF2IMAGE:
            # pdf2image を使用（フォールバック）
            images = convert_from_path(
                str(pdf_path),
                first_page=page_num,
                last_page=page_num,
                dpi=IMAGE_DPI
            )

            if not images:
                print(f"  [ERROR] 画像変換失敗: ページ {page_num}")
                return False

            image = images[0]
        else:
            print(f"  [ERROR] 画像変換ライブラリがインストールされていません")
            return False

        # 元画像: リサイズ（幅がIMAGE_MAX_WIDTHを超える場合）
        full_image = image.copy()
        if full_image.width > IMAGE_MAX_WIDTH:
            ratio = IMAGE_MAX_WIDTH / full_image.width
            new_height = int(full_image.height * ratio)
            full_image = full_image.resize((IMAGE_MAX_WIDTH, new_height), Image.Resampling.LANCZOS)

        # 元画像を保存
        full_image.save(str(output_path), 'PNG', optimize=True)

        # サムネイル: THUMBNAIL_WIDTH幅にリサイズ
        thumb_ratio = THUMBNAIL_WIDTH / image.width
        thumb_height = int(image.height * thumb_ratio)
        thumbnail = image.resize((THUMBNAIL_WIDTH, thumb_height), Image.Resampling.LANCZOS)

        # サムネイルを保存
        thumbnail.save(str(thumbnail_path), 'PNG', optimize=True)

        return True

    except Exception as e:
        print(f"  [ERROR] 画像変換エラー: {e}")
        return False


def translate_text(text: str, page_num: int, style: str = None) -> str:
    """
    ClaudeCLIを使ってテキストを和訳

    Args:
        text: 翻訳対象のテキスト
        page_num: ページ番号
        style: 翻訳スタイル ('kansai' or 'standard')。Noneの場合はデフォルト(kansai)
    """
    if not ClaudeCLI:
        return "[翻訳スキップ: ClaudeCLI未インストール]"

    if not text.strip():
        return "[テキストなし]"

    # スタイルの決定
    if style is None:
        style = DEFAULT_TRANSLATION_STYLE
    if style not in TRANSLATION_STYLES:
        print(f"  [WARN] 不明なスタイル '{style}'。デフォルト({DEFAULT_TRANSLATION_STYLE})を使用")
        style = DEFAULT_TRANSLATION_STYLE

    style_instruction = TRANSLATION_STYLES[style]

    # テキストが長すぎる場合は切り詰め
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[...テキスト省略...]"

    prompt = f"""以下の英文を日本語に翻訳してください。

{style_instruction}

余計な説明は不要です。翻訳文のみを出力してください。

---
{text}
---"""

    try:
        cli = ClaudeCLI()
        result = cli.execute(prompt, use_print=False)

        if result and result.get('success'):
            return result.get('output', '[翻訳結果なし]').strip()
        else:
            error_msg = result.get('error', '不明なエラー') if result else '実行失敗'
            return f"[翻訳エラー: {error_msg}]"

    except Exception as e:
        return f"[翻訳エラー: {e}]"


# ============================================================
# summary/ 章ごと要約生成（フォーマット厳守）
# ============================================================

# summary/の出力フォーマット定義
SUMMARY_FORMAT = """# 章タイトル（例: 1. Introduction）
- 要点1
- 要点2
- 要点3

# 章タイトル（例: 2. Methods）
- 要点1
- 要点2
- 要点3"""


def generate_chapter_summary(full_text: str, pdf_id: str, output_path: Path) -> str:
    """
    章ごとの項目要約を生成

    - 短文: ClaudeCLIで直接処理
    - 長文: Claude Codeに委譲
    """
    if not full_text.strip():
        return "[テキストなし]"

    text_length = len(full_text)
    print(f"    テキスト長: {text_length:,}文字")

    if text_length <= MAX_DIRECT_LENGTH:
        # === 短〜中程度: ClaudeCLIで直接処理 ===
        print(f"    [MODE] ClaudeCLI直接処理")
        return _generate_summary_direct(full_text)
    else:
        # === 長文: Claude Codeに委譲 ===
        print(f"    [MODE] Claude Code委譲（長文）")
        return _generate_summary_via_claude_code(full_text, pdf_id, output_path)


def _generate_summary_direct(full_text: str) -> str:
    """ClaudeCLIで直接要約（短〜中程度の論文向け）"""
    if not ClaudeCLI:
        return "[要約スキップ: ClaudeCLI未インストール]"

    prompt = f"""以下の論文全文を、章・セクションごとに要約してください。

【出力フォーマット（厳守）】
{SUMMARY_FORMAT}

【重要なルール】
- 各章は「# 章タイトル」で始める（##ではなく#）
- 各要点は「- 」で始める箇条書き
- 章タイトルには番号を含める（例: 1. Introduction, 2.1 Data Collection）
- 余計な説明や前置きは一切不要
- 要約のみを出力

---
{full_text}
---"""

    try:
        cli = ClaudeCLI()
        result = cli.execute(prompt, use_print=False)

        if result and result.get('success'):
            output = result.get('output', '[要約結果なし]').strip()
            return _validate_and_fix_summary_format(output)
        else:
            error_msg = result.get('error', '不明なエラー') if result else '実行失敗'
            return f"[要約エラー: {error_msg}]"
    except Exception as e:
        return f"[要約エラー: {e}]"


def _generate_summary_via_claude_code(full_text: str, pdf_id: str, output_path: Path) -> str:
    """Claude Codeに委譲して要約（超長文向け）"""

    # 出力ディレクトリを確保
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 一時ファイルに全文を保存し、処理後に確実に削除
    with temp_text_file(full_text, prefix=f"{pdf_id}_summary_input_") as input_path:

        prompt = f"""あなたはpaper-translateスキルから呼び出されています。

## タスク
論文テキストを読み込み、章・セクションごとの要約を生成してください。

## 入力ファイル
{input_path}

## 出力ファイル
{output_path}

## 出力フォーマット（厳守）
以下の形式で出力してください。これ以外の形式は許可されません。

```
# 1. Introduction
- 要点1
- 要点2
- 要点3

# 2. Related Work
- 要点1
- 要点2

# 3. Methods
- 要点1
- 要点2
- 要点3

# 4. Results
- 要点1
- 要点2

# 5. Discussion
- 要点1
- 要点2

# 6. Conclusion
- 要点1
- 要点2
```

## 厳守ルール
1. 各章は「# 章番号. 章タイトル」で始める（##ではなく#を使用）
2. 各要点は「- 」で始める箇条書き
3. 章の間は空行1行で区切る
4. 前置きや説明文は一切不要。要約のみを出力
5. 入力ファイルをReadツールで読み込むこと
6. 必ずWriteツールで {output_path} に結果を保存すること
7. テキストが非常に長い場合は、Taskツールで分割処理してから統合すること"""

        print(f"    Claude Code 実行中...")
        sys.stdout.flush()
        success, output = _call_claude_code(prompt, timeout_sec=900)

        if not success:
            print(f"    [ERROR] Claude Code 実行失敗: {output}")
            return f"[要約エラー: Claude Code実行失敗 - {output}]"

        # 出力ファイルを確認
        if output_path.exists():
            result = output_path.read_text(encoding='utf-8')
            result = _validate_and_fix_summary_format(result)
            print(f"    [OK] 要約生成完了（{len(result):,}文字）")
            return result
        else:
            print(f"    [ERROR] 出力ファイルが生成されませんでした")
            return f"[要約エラー: 出力ファイル未生成]\nClaude Code出力: {output[:500]}"


def _validate_and_fix_summary_format(text: str) -> str:
    """summary/のフォーマットを検証・修正"""
    lines = text.strip().split('\n')
    fixed_lines = []

    for line in lines:
        stripped = line.strip()

        # ##で始まる見出しを#に修正
        if stripped.startswith('## '):
            stripped = '#' + stripped[2:]

        # 見出しでも箇条書きでもない行で、空行でもない場合
        # （前置き文など）はスキップ
        if stripped and not stripped.startswith('#') and not stripped.startswith('-') and not stripped.startswith('*'):
            # 数字で始まる場合は見出しとして扱う
            if stripped[0].isdigit():
                stripped = '# ' + stripped
            else:
                # 前置き文はスキップ
                continue

        # *を-に統一
        if stripped.startswith('* '):
            stripped = '- ' + stripped[2:]

        fixed_lines.append(stripped)

    return '\n'.join(fixed_lines)


# ============================================================
# summary2/ 新規性分析生成（フォーマット厳守）
# ============================================================

# summary2/の出力フォーマット定義
NOVELTY_FORMAT = """# 新規性
- この論文の新しい貢献点1
- この論文の新しい貢献点2

# 言及されている全ての関連研究との相違点
- 先行研究Aとの違い
- 先行研究Bとの違い

# 有効性
- 提案手法の有効性1
- 実験結果から得られた成果

# 信頼性
- データの規模・質
- 再現性について"""


def generate_novelty_analysis(full_text: str, pdf_id: str, output_path: Path) -> str:
    """
    新規性・有効性・信頼性の分析を生成

    - 短文: ClaudeCLIで直接処理
    - 長文: Claude Codeに委譲
    """
    if not full_text.strip():
        return "[テキストなし]"

    text_length = len(full_text)
    print(f"    テキスト長: {text_length:,}文字")

    if text_length <= MAX_DIRECT_LENGTH:
        print(f"    [MODE] ClaudeCLI直接処理")
        return _generate_novelty_direct(full_text)
    else:
        print(f"    [MODE] Claude Code委譲（長文）")
        return _generate_novelty_via_claude_code(full_text, pdf_id, output_path)


def _generate_novelty_direct(full_text: str) -> str:
    """ClaudeCLIで直接分析（短〜中程度の論文向け）"""
    if not ClaudeCLI:
        return "[分析スキップ: ClaudeCLI未インストール]"

    prompt = f"""以下の論文全文を分析し、4つの観点でまとめてください。

【出力フォーマット（厳守）】
{NOVELTY_FORMAT}

【重要なルール】
- 必ず上記4つのセクション（新規性、言及されている全ての関連研究との相違点、有効性、信頼性）を含める
- 各セクションは「# セクション名」で始める（##ではなく#）
- 各要点は「- 」で始める箇条書き
- 余計な説明や前置きは一切不要
- 分析結果のみを出力

---
{full_text}
---"""

    try:
        cli = ClaudeCLI()
        result = cli.execute(prompt, use_print=False)

        if result and result.get('success'):
            output = result.get('output', '[分析結果なし]').strip()
            return _validate_and_fix_novelty_format(output)
        else:
            error_msg = result.get('error', '不明なエラー') if result else '実行失敗'
            return f"[分析エラー: {error_msg}]"
    except Exception as e:
        return f"[分析エラー: {e}]"


def _generate_novelty_via_claude_code(full_text: str, pdf_id: str, output_path: Path) -> str:
    """Claude Codeに委譲して新規性分析（超長文向け）"""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with temp_text_file(full_text, prefix=f"{pdf_id}_novelty_input_") as input_path:

        prompt = f"""あなたはpaper-translateスキルから呼び出されています。

## タスク
論文テキストを読み込み、新規性・有効性・信頼性の分析を生成してください。

## 入力ファイル
{input_path}

## 出力ファイル
{output_path}

## 出力フォーマット（厳守）
以下の形式で出力してください。これ以外の形式は許可されません。

```
# 新規性
- この論文の新しい貢献点1
- この論文の新しい貢献点2
- この論文の新しい貢献点3

# 言及されている全ての関連研究との相違点
- 先行研究Aとの違い: 〇〇
- 先行研究Bとの違い: 〇〇
- 先行研究Cとの違い: 〇〇

# 有効性
- 提案手法の有効性1
- 実験結果から得られた成果1
- 提案手法の有効性2

# 信頼性
- データの規模・質について
- 再現性について
- 統計的妥当性について
```

## 厳守ルール
1. 必ず4つのセクション（新規性、言及されている全ての関連研究との相違点、有効性、信頼性）を含める
2. 各セクションは「# セクション名」で始める（##ではなく#を使用）
3. 各要点は「- 」で始める箇条書き
4. セクションの間は空行1行で区切る
5. 前置きや説明文は一切不要。分析結果のみを出力
6. 入力ファイルをReadツールで読み込むこと
7. 必ずWriteツールで {output_path} に結果を保存すること
8. テキストが非常に長い場合は、Taskツールで分割処理してから統合すること
9. 「言及されている全ての関連研究との相違点」では、論文内で言及された全ての先行研究を列挙すること"""

        print(f"    Claude Code 実行中...")
        sys.stdout.flush()
        success, output = _call_claude_code(prompt, timeout_sec=900)

        if not success:
            print(f"    [ERROR] Claude Code 実行失敗: {output}")
            return f"[分析エラー: Claude Code実行失敗 - {output}]"

        if output_path.exists():
            result = output_path.read_text(encoding='utf-8')
            result = _validate_and_fix_novelty_format(result)
            print(f"    [OK] 分析生成完了（{len(result):,}文字）")
            return result
        else:
            print(f"    [ERROR] 出力ファイルが生成されませんでした")
            return f"[分析エラー: 出力ファイル未生成]\nClaude Code出力: {output[:500]}"


def _validate_and_fix_novelty_format(text: str) -> str:
    """summary2/のフォーマットを検証・修正"""
    lines = text.strip().split('\n')
    fixed_lines = []

    # 必須セクション
    required_sections = ['新規性', '言及されている全ての関連研究との相違点', '有効性', '信頼性']
    found_sections = set()

    for line in lines:
        stripped = line.strip()

        # ##で始まる見出しを#に修正
        if stripped.startswith('## '):
            stripped = '#' + stripped[2:]

        # セクション見出しの検出
        if stripped.startswith('# '):
            section_name = stripped[2:].strip()
            for req in required_sections:
                if req in section_name:
                    found_sections.add(req)
                    stripped = f'# {req}'
                    break

        # 見出しでも箇条書きでもない行で、空行でもない場合
        if stripped and not stripped.startswith('#') and not stripped.startswith('-') and not stripped.startswith('*'):
            # 前置き文はスキップ
            continue

        # *を-に統一
        if stripped.startswith('* '):
            stripped = '- ' + stripped[2:]

        fixed_lines.append(stripped)

    result = '\n'.join(fixed_lines)

    # 欠けているセクションを追加
    for req in required_sections:
        if req not in found_sections:
            result += f"\n\n# {req}\n- （情報なし）"

    return result


# ============================================================
# メイン処理
# ============================================================

def process_pdf(pdf_id: str, start_page: int = 1, end_page: int = None,
                no_translate: bool = False, dry_run: bool = False,
                style: str = None) -> bool:
    """
    PDFを処理してメモファイルを更新

    Args:
        pdf_id: PDFファイルのID
        start_page: 開始ページ
        end_page: 終了ページ
        no_translate: Trueの場合、翻訳をスキップ
        dry_run: Trueの場合、実際の処理を行わない
        style: 翻訳スタイル ('kansai' or 'standard')
    """

    pdf_path = PDFS_DIR / f"{pdf_id}.pdf"
    memo_path = MEMO_DIR / f"{pdf_id}.txt"

    # ファイル存在確認
    if not pdf_path.exists():
        print(f"[ERROR] PDFファイルが見つかりません: {pdf_path}")
        return False

    # ページ数取得
    total_pages = get_pdf_page_count(pdf_path)
    print(f"[INFO] PDF: {pdf_id} ({total_pages}ページ)")

    # ページ範囲の調整
    if end_page is None or end_page > total_pages:
        end_page = total_pages

    if start_page < 1:
        start_page = 1

    if start_page > end_page:
        print(f"[ERROR] 無効なページ範囲: {start_page}-{end_page}")
        return False

    print(f"[INFO] 処理範囲: ページ {start_page} - {end_page}")

    if dry_run:
        print("[DRY-RUN] 実際の処理は行いません")
        return True

    # 既存メモの読み込み（1-2行目を保持）
    memo_header = ""
    if memo_path.exists():
        with open(memo_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) >= 2:
                memo_header = ''.join(lines[:2])
            elif len(lines) == 1:
                memo_header = lines[0] + "\n"

    if not memo_header:
        memo_header = f"# {pdf_id}\n## \n"

    # 出力用のMarkdown構築
    markdown_content = memo_header + "\n---\n"

    # 各ページを処理
    pages_to_process = end_page - start_page + 1
    all_page_texts = []  # 全ページのテキストを収集（要約・分析用）

    for i, page_num in enumerate(range(start_page, end_page + 1), 1):
        print(f"[{i}/{pages_to_process}] Page {page_num} 処理中...")
        sys.stdout.flush()

        # 画像ファイル名（元画像 + サムネイル）
        image_filename = f"{pdf_id}_p{page_num:03d}.png"
        thumbnail_filename = f"s_{pdf_id}_p{page_num:03d}.png"
        image_path = ATTACH_DIR / image_filename
        thumbnail_path = ATTACH_DIR / thumbnail_filename

        # 1. 画像生成（元画像 + サムネイル）
        print(f"  画像生成中...")
        sys.stdout.flush()
        image_success = convert_page_to_image(pdf_path, page_num, image_path, thumbnail_path)

        if image_success:
            print(f"  [OK] 画像保存: {image_filename}, {thumbnail_filename}")
        else:
            print(f"  [WARN] 画像生成失敗")

        # 2. テキスト抽出
        print(f"  テキスト抽出中...")
        sys.stdout.flush()
        original_text = extract_text_from_page(pdf_path, page_num)

        if original_text:
            print(f"  [OK] テキスト抽出完了 ({len(original_text)}文字)")
            all_page_texts.append(original_text)  # 要約・分析用に収集
        else:
            print(f"  [WARN] テキストなし")

        # 3. 和訳
        translation = ""
        if not no_translate and original_text:
            style_label = style if style else DEFAULT_TRANSLATION_STYLE
            print(f"  和訳中... (スタイル: {style_label})")
            sys.stdout.flush()
            translation = translate_text(original_text, page_num, style=style)
            print(f"  [OK] 和訳完了")
        elif no_translate:
            translation = "[翻訳スキップ]"
        else:
            translation = "[テキストなし]"

        # 4. Markdown生成
        markdown_content += f"\n## Page {page_num}\n\n"

        if image_success:
            # サムネイルをクリックすると元画像を表示（スライドショー対応）
            markdown_content += f"[![Page {page_num}](/attach/{thumbnail_filename})](/attach/{image_filename})\n\n"

        markdown_content += "### 和訳\n\n"
        markdown_content += f"{translation}\n\n"

        markdown_content += "---\n"

        print(f"  [DONE] Page {page_num} 完了")
        sys.stdout.flush()

    # メモファイルに書き込み
    print(f"\n[INFO] メモファイル更新中: {memo_path}")
    with open(memo_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    # === 要約・分析の生成 ===
    full_text = "\n\n".join(all_page_texts)

    if full_text.strip() and not no_translate:
        # 5. 章ごとの項目要約を生成
        print(f"\n[INFO] 章ごとの要約を生成中...")
        sys.stdout.flush()

        # ディレクトリが存在しない場合は作成
        SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
        summary_path = SUMMARY_DIR / f"{pdf_id}.txt"

        chapter_summary = generate_chapter_summary(full_text, pdf_id, summary_path)

        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(chapter_summary)
        print(f"[OK] 章ごと要約を保存: {summary_path}")

        # 6. 新規性分析を生成
        print(f"\n[INFO] 新規性分析を生成中...")
        sys.stdout.flush()

        # ディレクトリが存在しない場合は作成
        SUMMARY2_DIR.mkdir(parents=True, exist_ok=True)
        summary2_path = SUMMARY2_DIR / f"{pdf_id}.txt"

        novelty_analysis = generate_novelty_analysis(full_text, pdf_id, summary2_path)

        with open(summary2_path, 'w', encoding='utf-8') as f:
            f.write(novelty_analysis)
        print(f"[OK] 新規性分析を保存: {summary2_path}")
    else:
        print(f"\n[INFO] テキストなしまたは翻訳スキップのため、要約・分析をスキップ")

    print(f"\n[OK] 処理完了: {pdf_id}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='論文PDFをページ単位で画像化・テキスト抽出・和訳'
    )
    parser.add_argument(
        'pdf_ids',
        nargs='*',
        help='処理対象のPDF ID（複数指定可）'
    )
    parser.add_argument(
        '--start',
        type=int,
        default=1,
        help='開始ページ（デフォルト: 1）'
    )
    parser.add_argument(
        '--end',
        type=int,
        default=None,
        help='終了ページ（デフォルト: 最終ページ）'
    )
    parser.add_argument(
        '--no-translate',
        action='store_true',
        help='翻訳をスキップ（画像とテキスト抽出のみ）'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='実際の処理を行わず内容を表示'
    )
    parser.add_argument(
        '--style',
        type=str,
        choices=['kansai', 'standard'],
        default=None,
        help=f'翻訳スタイル: kansai=関西弁でわかりやすく, standard=標準語（デフォルト: {DEFAULT_TRANSLATION_STYLE}）'
    )

    args = parser.parse_args()

    # PDF IDが指定されていない場合
    if not args.pdf_ids:
        print("[ERROR] PDF IDを指定してください")
        print("使用方法: python paper_translate.py {pdf_id} [--start N] [--end M]")
        print("\n利用可能なPDF:")

        # PDFリストを表示（最新10件）
        pdf_files = sorted(PDFS_DIR.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]
        for pdf_file in pdf_files:
            pdf_id = pdf_file.stem
            memo_path = MEMO_DIR / f"{pdf_id}.txt"
            title = "(タイトル不明)"
            if memo_path.exists():
                with open(memo_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    # #で始まる場合は除去、そうでなければそのまま使用
                    title = first_line.lstrip('#').strip() if first_line else "(タイトル不明)"
            print(f"  {pdf_id[:16]}...: {title[:50]}")

        sys.exit(1)

    # 各PDF IDを処理
    success_count = 0
    fail_count = 0

    for pdf_id in args.pdf_ids:
        # .pdf 拡張子を除去
        pdf_id = pdf_id.replace('.pdf', '')

        print(f"\n{'='*60}")
        print(f"処理開始: {pdf_id}")
        print(f"{'='*60}")

        success = process_pdf(
            pdf_id=pdf_id,
            start_page=args.start,
            end_page=args.end,
            no_translate=args.no_translate,
            dry_run=args.dry_run,
            style=args.style
        )

        if success:
            success_count += 1
        else:
            fail_count += 1

    # サマリー
    print(f"\n{'='*60}")
    print(f"処理完了: 成功 {success_count}, 失敗 {fail_count}")
    print(f"{'='*60}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == '__main__':
    main()
