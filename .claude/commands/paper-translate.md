---
description: 論文PDFをページ単位で画像化・テキスト抽出・和訳してメモに保存する
argument-hint: [pdf_id1] [pdf_id2] ...
---

論文PDFをページ単位で処理し、各ページの画像・テキスト・和訳をメモファイルに出力します。

## 引数の確認

**受け取った引数**: `$ARGUMENTS`

引数が空の場合は、ユーザーに処理対象のpdf_idを質問してください。その際、以下のコマンドで最新のPDF一覧を取得して選択肢として提示してください:

```bash
# カレントディレクトリがプロジェクトルートであることを前提
ls -lt pdfs/*.pdf | head -10 | while read line; do
  pdf_path=$(echo "$line" | awk '{print $NF}')
  pdf_id=$(basename "$pdf_path" .pdf)
  memo_path="memo/${pdf_id}.txt"
  if [ -f "$memo_path" ]; then
    title=$(head -1 "$memo_path" | sed 's/^#* *//')
  else
    title="(タイトル不明)"
  fi
  echo "${pdf_id}: ${title:0:50}"
done
```

## 実行手順

### ステップ1: 引数の解析

`$ARGUMENTS` に含まれるpdf_id（スペース区切りで複数可）を解析します。

### ステップ2: 各PDFの処理

引数で指定された各pdf_idに対して、以下のコマンドを実行します:

```bash
source ~/.claude/lib/load_env.sh
run_python ~/.claude/skills/paper-translate/paper_translate.py $ARGUMENTS
```

**オプション指定例**:
- ページ範囲指定: `--start 1 --end 5`
- 翻訳スキップ: `--no-translate`
- ドライラン: `--dry-run`

### ステップ3: 結果の報告

処理完了後、以下を報告してください:
- 処理したPDFの数
- 各PDFの処理結果（成功/失敗）
- 生成された画像ファイルの場所
- 更新されたメモファイルの場所

## 処理内容

各ページについて以下を実行:
1. **画像生成**: PDFの各ページをPNG画像に変換 → `attach/{pdf_id}_p{NNN}.png`
2. **テキスト抽出**: pdfminerで各ページのテキストを抽出
3. **和訳**: ClaudeCLIを使って英文を日本語に翻訳
4. **メモ更新**: 結果をMarkdown形式でメモファイルに保存 → `memo/{pdf_id}.txt`
5. **章ごと要約**: 論文全体の章ごと要約を生成 → `summary/{pdf_id}.txt`
6. **新規性分析**: 新規性・有効性・信頼性の分析 → `summary2/{pdf_id}.txt`

## 注意事項

- 処理時間: 1ページあたり約30-60秒（翻訳含む）
- 長い論文は `--start` `--end` オプションでページ範囲を指定可能
- 既存のメモ（1-2行目のタイトル・タグ）は保持される
- 翻訳が不要な場合は `--no-translate` オプションを使用

---

**処理対象PDF ID**: $ARGUMENTS
