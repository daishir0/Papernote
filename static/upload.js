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
                    ? `\n[![${result.filename}](${smallImageUrl})](${result.url})\n` 
                    : `\n[${result.filename}](${result.url})\n`;
                insertTextAtCursor(contentTextArea, markdownLink);
            } else {
                alert('ファイルのアップロードに失敗しました。');
            }
        }
        fileInput.value = null;
    });
});
