document.addEventListener('DOMContentLoaded', () => {
    const uploadFileButton = document.getElementById('uploadFileButton');
    const fileInput = document.getElementById('fileInput');
    const contentTextArea = document.getElementById('content');

    // ========== 既存の単一ファイルアップロード機能（改善版） ==========
    uploadFileButton.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', async () => {
        const file = fileInput.files[0];
        if (file) {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/attach_upload', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrfToken
                }
            });

            if (response.ok) {
                const result = await response.json();
                const markdownLink = generateMarkdownLink(result);
                insertTextAtCursor(contentTextArea, markdownLink);
            } else {
                alert('ファイルのアップロードに失敗しました。');
            }
        }
        fileInput.value = null;
    });

    // ========== 新規：複数ファイルドラッグ&ドロップ機能 ==========

    // ドラッグオーバー時の視覚的フィードバック
    contentTextArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        contentTextArea.style.backgroundColor = '#e3f2fd';
        contentTextArea.style.border = '2px dashed #0d6efd';
    });

    contentTextArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        contentTextArea.style.backgroundColor = '';
        contentTextArea.style.border = '';
    });

    contentTextArea.addEventListener('drop', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        contentTextArea.style.backgroundColor = '';
        contentTextArea.style.border = '';

        const files = Array.from(e.dataTransfer.files);
        if (files.length === 0) return;

        // スピナー表示
        const spinner = document.getElementById('uploadSpinner');
        const progress = document.getElementById('uploadProgress');
        const currentFileName = document.getElementById('currentFileName');

        spinner.style.display = 'flex';
        progress.textContent = `0/${files.length}`;

        const cursorPos = contentTextArea.selectionStart;
        let insertedText = '';
        let successCount = 0;

        // 1ファイルずつ直列処理
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            currentFileName.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;

            try {
                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/attach_upload', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': csrfToken
                    }
                });

                if (response.ok) {
                    const result = await response.json();
                    const markdownLink = generateMarkdownLink(result);
                    insertedText += markdownLink;
                    successCount++;
                    progress.textContent = `${successCount}/${files.length}`;
                } else {
                    console.error(`Failed to upload ${file.name}`);
                }
            } catch (error) {
                console.error(`Error uploading ${file.name}:`, error);
            }
        }

        // カーソル位置に一括挿入
        if (insertedText) {
            const value = contentTextArea.value;
            contentTextArea.value = value.slice(0, cursorPos) + '\n' + insertedText + value.slice(cursorPos);
            contentTextArea.selectionStart = contentTextArea.selectionEnd = cursorPos + insertedText.length + 1;
            contentTextArea.focus();

            // プレビュー更新のために input イベントを手動で発火
            const event = new Event('input', { bubbles: true });
            contentTextArea.dispatchEvent(event);
        }

        // スピナー非表示
        spinner.style.display = 'none';

        // 完了メッセージ
        showTemporaryMessage(`${successCount}/${files.length} ファイルをアップロードしました`);
    });

    // ========== 共通関数：Markdownリンク生成（ファイル名表示対応） ==========
    function generateMarkdownLink(result) {
        const filename = result.filename;
        const url = result.url;

        if (result.isImage) {
            // 画像の場合：サムネイル表示 + クリックで原寸
            // [![ファイル名](サムネイルURL "ファイル名")](オリジナルURL "ファイル名")
            const smallImageUrl = url.replace(/\/([^\/]+)$/, '/s_$1');
            return `\n[![${filename}](${smallImageUrl} "${filename}")](${url} "${filename}")\n`;
        } else {
            // 非画像の場合：テキストリンク
            // [ファイル名](URL "ファイル名")
            return `\n[${filename}](${url} "${filename}")\n`;
        }
    }
});
