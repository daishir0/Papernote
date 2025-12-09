#!/usr/bin/env python3
"""
Paper Translate - 論文PDFをページ単位で画像化・テキスト抽出・和訳するスキル

使用方法:
    python paper_translate.py {pdf_id} [--start N] [--end M] [--no-translate] [--dry-run]
"""

import argparse
import os
import sys
from pathlib import Path

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


def translate_text(text: str, page_num: int) -> str:
    """ClaudeCLIを使ってテキストを和訳"""
    if not ClaudeCLI:
        return "[翻訳スキップ: ClaudeCLI未インストール]"

    if not text.strip():
        return "[テキストなし]"

    # テキストが長すぎる場合は切り詰め
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[...テキスト省略...]"

    prompt = f"""以下の英文を日本語に翻訳してください。学術論文のため、専門用語は適切に訳してください。
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


def split_text_into_chunks(text: str, chunk_size: int = 30000) -> list:
    """テキストを指定サイズのチャンクに分割"""
    chunks = []
    current_pos = 0
    text_len = len(text)

    while current_pos < text_len:
        end_pos = min(current_pos + chunk_size, text_len)

        # チャンクの終わりを段落区切りで調整（可能な場合）
        if end_pos < text_len:
            # 段落区切り（\n\n）を探す
            newline_pos = text.rfind('\n\n', current_pos, end_pos)
            if newline_pos > current_pos + chunk_size // 2:
                end_pos = newline_pos + 2

        chunks.append(text[current_pos:end_pos])
        current_pos = end_pos

    return chunks


def generate_chapter_summary(full_text: str, pdf_id: str) -> str:
    """章ごとの項目要約を生成（長文は分割処理して統合）"""
    if not ClaudeCLI:
        return "[要約スキップ: ClaudeCLI未インストール]"

    if not full_text.strip():
        return "[テキストなし]"

    chunk_size = 30000
    chunks = split_text_into_chunks(full_text, chunk_size)
    total_chunks = len(chunks)

    print(f"    テキスト長: {len(full_text)}文字 → {total_chunks}チャンクに分割")

    partial_summaries = []

    for i, chunk in enumerate(chunks, 1):
        print(f"    チャンク {i}/{total_chunks} を要約中...")
        sys.stdout.flush()

        prompt = f"""以下の論文テキスト（パート {i}/{total_chunks}）を、章・セクションごとに要約してください。

形式:
# 章タイトル
- 要点1
- 要点2
- 要点3

重要なポイントを箇条書きで簡潔にまとめてください。
余計な説明は不要です。要約のみを出力してください。

---
{chunk}
---"""

        try:
            cli = ClaudeCLI()
            result = cli.execute(prompt, use_print=False)

            if result and result.get('success'):
                partial_summaries.append(result.get('output', '').strip())
            else:
                error_msg = result.get('error', '不明なエラー') if result else '実行失敗'
                partial_summaries.append(f"[チャンク{i}要約エラー: {error_msg}]")

        except Exception as e:
            partial_summaries.append(f"[チャンク{i}要約エラー: {e}]")

    # 複数チャンクの場合は統合
    if total_chunks > 1:
        print(f"    {total_chunks}チャンクの要約を統合中...")
        sys.stdout.flush()

        combined_summaries = "\n\n".join(partial_summaries)

        merge_prompt = f"""以下は論文の各パートの章ごと要約です。これらを1つの統合された章ごと要約にまとめてください。
重複する章は統合し、章の順序を整理してください。

形式:
# 章タイトル
- 要点1
- 要点2
- 要点3

余計な説明は不要です。統合された要約のみを出力してください。

---
{combined_summaries}
---"""

        try:
            cli = ClaudeCLI()
            result = cli.execute(merge_prompt, use_print=False)

            if result and result.get('success'):
                return result.get('output', '[統合結果なし]').strip()
            else:
                # 統合に失敗した場合は連結して返す
                return combined_summaries

        except Exception as e:
            return combined_summaries
    else:
        return partial_summaries[0] if partial_summaries else "[要約結果なし]"


def generate_novelty_analysis(full_text: str, pdf_id: str) -> str:
    """新規性・有効性・信頼性の分析を生成（長文は分割処理して統合）"""
    if not ClaudeCLI:
        return "[分析スキップ: ClaudeCLI未インストール]"

    if not full_text.strip():
        return "[テキストなし]"

    chunk_size = 30000
    chunks = split_text_into_chunks(full_text, chunk_size)
    total_chunks = len(chunks)

    print(f"    テキスト長: {len(full_text)}文字 → {total_chunks}チャンクに分割")

    partial_analyses = []

    for i, chunk in enumerate(chunks, 1):
        print(f"    チャンク {i}/{total_chunks} を分析中...")
        sys.stdout.flush()

        prompt = f"""以下の論文テキスト（パート {i}/{total_chunks}）を分析し、以下の4つの観点で情報を抽出してください。
余計な説明は不要です。分析結果のみを出力してください。
このパートに該当する情報がない観点は「該当情報なし」と記載してください。

# 新規性
（この論文の新しい貢献は何か、箇条書きで）

# 言及されている全ての関連研究との相違点
（先行研究と比べて何が違うか、箇条書きで）

# 有効性
（提案手法・分析は有効か、どのような成果があるか、箇条書きで）

# 信頼性
（結果は信頼できるか、データの質・規模・再現性はどうか、箇条書きで）

---
{chunk}
---"""

        try:
            cli = ClaudeCLI()
            result = cli.execute(prompt, use_print=False)

            if result and result.get('success'):
                partial_analyses.append(result.get('output', '').strip())
            else:
                error_msg = result.get('error', '不明なエラー') if result else '実行失敗'
                partial_analyses.append(f"[チャンク{i}分析エラー: {error_msg}]")

        except Exception as e:
            partial_analyses.append(f"[チャンク{i}分析エラー: {e}]")

    # 複数チャンクの場合は統合
    if total_chunks > 1:
        print(f"    {total_chunks}チャンクの分析を統合中...")
        sys.stdout.flush()

        combined_analyses = "\n\n---\n\n".join(partial_analyses)

        merge_prompt = f"""以下は論文の各パートから抽出した分析結果です。これらを1つの統合された分析にまとめてください。
重複する内容は統合し、各観点ごとに整理してください。

形式:
# 新規性
- 要点1
- 要点2

# 言及されている全ての関連研究との相違点
- 要点1
- 要点2

# 有効性
- 要点1
- 要点2

# 信頼性
- 要点1
- 要点2

余計な説明は不要です。統合された分析結果のみを出力してください。

---
{combined_analyses}
---"""

        try:
            cli = ClaudeCLI()
            result = cli.execute(merge_prompt, use_print=False)

            if result and result.get('success'):
                return result.get('output', '[統合結果なし]').strip()
            else:
                # 統合に失敗した場合は連結して返す
                return combined_analyses

        except Exception as e:
            return combined_analyses
    else:
        return partial_analyses[0] if partial_analyses else "[分析結果なし]"


def process_pdf(pdf_id: str, start_page: int = 1, end_page: int = None,
                no_translate: bool = False, dry_run: bool = False) -> bool:
    """PDFを処理してメモファイルを更新"""

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
            print(f"  和訳中...")
            sys.stdout.flush()
            translation = translate_text(original_text, page_num)
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

        # Original Textセクションは一時的にコメントアウト（必要に応じて復活可能）
        # markdown_content += "### Original Text\n\n"
        # markdown_content += f"{original_text}\n\n" if original_text else "[テキストなし]\n\n"

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
        chapter_summary = generate_chapter_summary(full_text, pdf_id)

        # ディレクトリが存在しない場合は作成
        SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
        summary_path = SUMMARY_DIR / f"{pdf_id}.txt"

        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(chapter_summary)
        print(f"[OK] 章ごと要約を保存: {summary_path}")

        # 6. 新規性分析を生成
        print(f"\n[INFO] 新規性分析を生成中...")
        sys.stdout.flush()
        novelty_analysis = generate_novelty_analysis(full_text, pdf_id)

        # ディレクトリが存在しない場合は作成
        SUMMARY2_DIR.mkdir(parents=True, exist_ok=True)
        summary2_path = SUMMARY2_DIR / f"{pdf_id}.txt"

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
            dry_run=args.dry_run
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
