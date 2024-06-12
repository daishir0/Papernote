document.addEventListener('DOMContentLoaded', () => {
    const uploadFileButton = document.getElementById('uploadFileButton');
    const fileInput = document.getElementById('fileInput');
    const contentTextArea = document.getElementById('content');

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
                body: formData
            });

            if (response.ok) {
                const result = await response.json();
                const smallImageUrl = result.url.replace(/\/([^\/]+)$/, '/s_$1');
                const markdownLink = result.isImage 
                    ? `[![${result.filename}](${smallImageUrl})](${result.url})` 
                    : `[${result.filename}](${result.url})`;
                insertTextAtCursor(contentTextArea, markdownLink);
            } else {
                alert('ファイルのアップロードに失敗しました。');
            }
        }
        fileInput.value = null;
    });
});

function insertTextAtCursor(textArea, text) {
    if (!textArea) return;
    const start = textArea.selectionStart;
    const end = textArea.selectionEnd;
    const value = textArea.value;

    textArea.value = value.slice(0, start) + text + value.slice(start);
    textArea.selectionStart = textArea.selectionEnd = start + text.length;
    textArea.focus();
}
