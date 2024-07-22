// メッセージを一時的に表示する関数
function showTemporaryMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.textContent = message;
    messageElement.style.position = 'fixed';
    messageElement.style.top = '50%'; // 上から50%の位置
    messageElement.style.left = '50%'; // 左から50%の位置
    messageElement.style.transform = 'translate(-50%, -50%)'; // 中央に配置
    messageElement.style.backgroundColor = 'rgba(0,0,0,0.7)';
    messageElement.style.color = 'white';
    messageElement.style.padding = '10px';
    messageElement.style.borderRadius = '5px';
    messageElement.style.zIndex = '1000';
    document.body.appendChild(messageElement);

    setTimeout(() => {
        document.body.removeChild(messageElement);
    }, 3000); // 3秒後にメッセージを消す
}

// ページのURLからIDを抽出し、そのIDを使用してテキストデータを非同期で取得する関数。
async function fetchText() {
    // 現在のページのURLから必要なIDを抽出
    const currentUrl = window.location.href;
    const idMatch = currentUrl.match(/([a-f0-9]+).txt/);

    if (idMatch) {
        // 抽出したIDを使用して新しいURLを生成
        const textUrl = `/clean_text/${idMatch[1]}.pdf`;

        try {
            const response = await fetch(textUrl);
            if (!response.ok) throw new Error('Network response was not ok');
            const text = await response.text(); // レスポンスをテキストとして取得
            return text; // テキストを返す
        } catch (error) {
            console.error('Fetching text failed:', error);
            return 'テキストデータの取得に失敗しました。'; // エラーメッセージを返す
        }
    }
    return ''; // IDが見つからない場合は空文字を返す
}

async function copyToClipboardWithFetch() {
    const promptText = document.getElementById('prompt').value; // textareaからプロンプトテキストを取得
    const paperContent = document.getElementById('paperContent').value; // textareaから論文テキストを取得
    const combinedText = `${promptText}${paperContent}`; // プロンプトと論文テキストを結合

    navigator.clipboard.writeText(combinedText)
        .then(() => {
            showTemporaryMessage('コピーされました');
        })
        .catch(err => {
            console.error('コピーに失敗:', err);
            alert('クリップボードへのコピーに失敗しました。');
        });
}

function autoSaveContent() {
    let lastContent = document.querySelector('textarea').value; // 最後に保存した内容を保持
    setInterval(() => { // 1分ごとに関数を実行
        let currentContent = document.querySelector('textarea').value;
        if (currentContent !== lastContent) { // 前回の内容と比較
            // 内容が異なる場合、ここに非同期保存の処理を書く
            fetch(window.location.href, { // 現在のページのURLを使用
                method: 'POST', // フォームの送信方法に合わせて 'POST'
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded', // CSRFトークンをヘッダーに追加
                    'X-CSRFToken': csrfToken
                    // コンテントタイプを適切に設定
                },
                body: `content=${encodeURIComponent(currentContent)}` // 送信するデータ。'content'はサーバーで期待されるフィールド名に合わせて変更してください
            }).then(response => {
                if (response.ok) {
                    showTemporaryMessage('保存成功!');
                    return response.text(); // レスポンスの内容に応じて変更が必要かもしれません
                } else {
                    throw new Error('保存に失敗しました');
                }
            }).catch(error => {
                showTemporaryMessage('保存中にエラーが発生しました:', error);
            });
            
            // showTemporaryMessage('変更を保存中...'); // 実際にはここでサーバーへの非同期通信を行う
            lastContent = currentContent; // 最後に保存した内容を更新
        } else {
            console.log('No changes detected, skipping server save.');
        }
    }, 60000); // 60000ミリ秒（1分）ごと
}