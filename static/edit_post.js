        const csrfToken = document.body.dataset.csrfToken;  // CSRFトークンをdata属性から取得

        document.addEventListener('DOMContentLoaded', () => {
            const contentTextArea = document.getElementById('content');
            if (contentTextArea) {
                contentTextArea.dataset.initialLoad = 'true';
                contentTextArea.value = contentTextArea.value.replace(/\\n/g, '\n');
                
                if (contentTextArea.dataset.initialLoad === 'true') {
                    contentTextArea.focus();
                    contentTextArea.selectionStart = 0;
                    contentTextArea.selectionEnd = 0;
                    contentTextArea.scrollTop = 0;
                    delete contentTextArea.dataset.initialLoad;
                }
            }

            autoSaveContent();

            document.addEventListener('keydown', function(event) {
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                    // ページ切り替えモーダルが開いている場合はスキップ
                    const switchPageOverlay = document.getElementById('switchPageOverlay');
                    if (switchPageOverlay && switchPageOverlay.style.display === 'flex') {
                        return;
                    }

                    event.preventDefault();
                    // フォームを送信（保存して遷移）
                    const form = document.querySelector('form');
                    if (form) {
                        form.submit();
                    }
                } else if ((event.ctrlKey || event.metaKey) && event.key === 's') {
                    event.preventDefault();
                    saveWithoutRedirect();
                } else if (event.altKey && (event.code === 'KeyY' || event.key === 'y' || event.key === 'Y')) {
                    event.preventDefault();
                    const currentDate = getCurrentDate();
                    insertTextAtCursor(document.getElementById('content'), currentDate);
                } else if (event.altKey && (event.code === 'KeyH' || event.key === 'h' || event.key === 'H')) {
                    event.preventDefault();
                    const currentTime = getCurrentTime();
                    insertTextAtCursor(document.getElementById('content'), currentTime);
                } else if (event.altKey && (event.code === 'Digit1' || event.key === '1')) {
                    event.preventDefault();
                    cycleHeaderLevel(document.getElementById('content'));
                } else if (event.altKey && (event.code === 'Digit2' || event.key === '2')) {
                    event.preventDefault();
                    cycleDashMark(document.getElementById('content'));
                } else if (event.altKey && (event.code === 'Digit3' || event.key === '3')) {
                    event.preventDefault();
                    cycleNumberMark(document.getElementById('content'));
                } else if (event.altKey && (event.code === 'Digit4' || event.key === '4')) {
                    event.preventDefault();
                    cycleQuoteMark(document.getElementById('content'));
                } else if (event.altKey && (event.code === 'Digit5' || event.key === '5')) {
                    // ALT+5: Bold（選択範囲がある場合のみ）
                    event.preventDefault();
                    const textarea = document.getElementById('content');
                    const start = textarea.selectionStart;
                    const end = textarea.selectionEnd;
                    if (start !== end) { // 選択範囲がある場合のみ実行
                        wrapSelectedTextWith(textarea, '**');
                    }
                } else if (event.altKey && (event.code === 'Digit6' || event.key === '6')) {
                    // ALT+6: 4スペーストグル
                    event.preventDefault();
                    cycleFourSpaces(document.getElementById('content'));
                } else if (event.altKey && event.key === 'ArrowUp') {
                    // ALT+Up: Move cursor to the beginning of the textarea
                    event.preventDefault();
                    const textarea = document.getElementById('content');
                    textarea.selectionStart = 0;
                    textarea.selectionEnd = 0;
                    textarea.focus();
                } else if (event.altKey && event.key === 'ArrowDown') {
                    // ALT+Down: Move cursor to the end of the textarea
                    event.preventDefault();
                    const textarea = document.getElementById('content');
                    textarea.selectionStart = textarea.value.length;
                    textarea.selectionEnd = textarea.value.length;
                    textarea.focus();
                } else if (event.altKey && (event.code === 'KeyA' || event.key === 'a' || event.key === 'A')) {
                    // ALT+A: AIアシスタントを開く
                    event.preventDefault();
                    document.getElementById('aiButton').click();
                }
            });

            // Saveボタン（ツールバー）
            const saveButton = document.getElementById('saveButton');
            if (saveButton) {
                saveButton.addEventListener('click', () => {
                    saveWithoutRedirect();
                });
            }

            // Claude Codeボタン
            const ccButton = document.getElementById('ccButton');
            if (ccButton) {
                ccButton.addEventListener('click', () => {
                    const filename = document.body.dataset.filename;
                    const baseUrl = document.body.dataset.claudeCodeUrl;
                    if (baseUrl) {
                        const url = `${baseUrl}?papernote=${encodeURIComponent(filename)}`;
                        window.open(url, '_blank');
                    } else {
                        alert('Claude Code URLが設定されていません');
                    }
                });
            }

            const pasteMermaidButton = document.getElementById('pasteMermaidButton');
            if (pasteMermaidButton) {
                pasteMermaidButton.addEventListener('click', () => {
                    insertTextAtCursor(contentTextArea, '\n```mermaid\n\n```');
                    const insertOverlay = document.getElementById('insertOverlay');
                    if (insertOverlay) {
                        insertOverlay.style.display = 'none';
                    }
                });
            }

            // 削除ボタン
            const deletePostButton = document.getElementById('deletePostButton');
            if (deletePostButton) {
                deletePostButton.addEventListener('click', () => {
                    const filename = document.body.dataset.filename;
                    if (confirm('本当にこの投稿を削除しますか？\n\nこの操作は元に戻せません。')) {
                        fetch('/delete_post', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded',
                                'X-CSRFToken': csrfToken
                            },
                            body: 'filename=' + encodeURIComponent(filename)
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                location.href = '/postlist';
                            } else {
                                alert('削除に失敗しました: ' + (data.error || '不明なエラー'));
                            }
                        })
                        .catch(error => {
                            alert('削除に失敗しました: ' + error.message);
                        });
                    }
                    // オプションメニューを閉じる
                    const insertOverlay = document.getElementById('insertOverlay');
                    if (insertOverlay) {
                        insertOverlay.style.display = 'none';
                    }
                });
            }

            // ファイル名をコピーボタン（ツールバー）
            const copyFilenameButton = document.getElementById('copyFilenameButton');
            if (copyFilenameButton) {
                copyFilenameButton.addEventListener('click', () => {
                    const filename = document.body.dataset.filename;
                    navigator.clipboard.writeText(filename).then(() => {
                        showTemporaryMessage('ファイル名をコピーしました！');
                    }).catch(err => {
                        console.error('コピーに失敗しました:', err);
                        showTemporaryMessage('コピーに失敗しました');
                    });
                });
            }

            // Markdown書式ボタン: トグル動作
            const insertHashButton = document.getElementById('insertHashButton');
            if (insertHashButton) {
                insertHashButton.addEventListener('click', () => {
                    cycleHeaderLevel(contentTextArea);
                });
            }

            const insertDashButton = document.getElementById('insertDashButton');
            if (insertDashButton) {
                insertDashButton.addEventListener('click', () => {
                    cycleDashMark(contentTextArea);
                });
            }

            const insert1Button = document.getElementById('insert1Button');
            if (insert1Button) {
                insert1Button.addEventListener('click', () => {
                    cycleNumberMark(contentTextArea);
                });
            }

            const insertQuoteButton = document.getElementById('insertQuoteButton');
            if (insertQuoteButton) {
                insertQuoteButton.addEventListener('click', () => {
                    cycleQuoteMark(contentTextArea);
                });
            }

            // その他のボタン: 従来通りの動作
            const insertSpaceButton = document.getElementById('insertSpaceButton');
            if (insertSpaceButton) {
                insertSpaceButton.addEventListener('click', () => {
                    cycleFourSpaces(contentTextArea);
                });
            }

            const insertBoldButton = document.getElementById('insertBoldButton');
            if (insertBoldButton) {
                insertBoldButton.addEventListener('click', () => {
                    wrapSelectedTextWith(contentTextArea, '**');
                });
            }

            contentTextArea.addEventListener('paste', handlePaste);

            // LINEボタンの機能追加
            const lineButton = document.getElementById('lineButton');
            const overlay = document.getElementById('overlay');
            const lineTextInput = document.getElementById('lineTextInput');
            const lineAttachButton = document.getElementById('lineAttachButton');

            lineButton.addEventListener('click', () => {
                // オプション画面を閉じる
                insertOverlay.style.display = 'none';
                // チャット入力画面を開く
                overlay.style.display = 'flex';
                lineTextInput.focus(); // オーバーレイが表示されたときにフォーカスを設定
            });

            let isComposing = false;

            lineTextInput.addEventListener('compositionstart', () => {
                isComposing = true;
            });

            lineTextInput.addEventListener('compositionend', () => {
                isComposing = false;
            });

            lineTextInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' && !isComposing) {
                    event.preventDefault();
                    const text = '\n- ' + lineTextInput.value;
                    insertTextAtCursor(contentTextArea, text);
                    lineTextInput.value = ''; // テキストボックスをクリア
                    lineTextInput.focus();
                }
            });

            lineAttachButton.addEventListener('click', () => {
                document.getElementById('uploadFileButton').click(); 
            });

            overlay.addEventListener('click', (event) => {
                if (event.target === overlay) {
                    overlay.style.display = 'none';
                }
            });

            // 挿入ボタンの機能追加
            const insertButton = document.getElementById('insertButton');
            const insertOverlay = document.getElementById('insertOverlay');
            const insertCancelButton = document.getElementById('insertCancelButton');
            const uploadFileButton = document.getElementById('uploadFileButton');

            if (insertButton && insertOverlay) {
                insertButton.addEventListener('click', () => {
                    insertOverlay.style.display = 'flex';
                });

                // 背景クリックでオーバーレイを閉じる
                insertOverlay.addEventListener('click', (event) => {
                    if (event.target === insertOverlay) {
                        insertOverlay.style.display = 'none';
                    }
                });

                // キャンセルボタン
                if (insertCancelButton) {
                    insertCancelButton.addEventListener('click', () => {
                        insertOverlay.style.display = 'none';
                    });
                }

                // ファイルアップロードボタンクリック時にオーバーレイを閉じる
                if (uploadFileButton) {
                    uploadFileButton.addEventListener('click', () => {
                        insertOverlay.style.display = 'none';
                    });
                }
            }

            // ESCキーが押されたときにオーバーレイを非表示にする
            document.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') {
                    overlay.style.display = 'none';
                    if (document.getElementById('aiOverlay')) {
                        document.getElementById('aiOverlay').style.display = 'none';
                    }
                    if (insertOverlay) {
                        insertOverlay.style.display = 'none';
                    }
                }
            });

            // YYボタンとHHボタンのイベントリスナーを追加
            const insertDateButton = document.getElementById('insertDateButton');
            const insertTimeButton = document.getElementById('insertTimeButton');

            if (insertDateButton) {
                insertDateButton.addEventListener('click', () => {
                    const currentDate = getCurrentDate();
                    insertTextAtCursor(contentTextArea, currentDate);
                    if (insertOverlay) {
                        insertOverlay.style.display = 'none';
                    }
                });
            }

            if (insertTimeButton) {
                insertTimeButton.addEventListener('click', () => {
                    const currentTime = getCurrentTime();
                    insertTextAtCursor(contentTextArea, currentTime);
                    if (insertOverlay) {
                        insertOverlay.style.display = 'none';
                    }
                });
            }

            // New Postボタン
            const newPostButton = document.getElementById('newPostButton');
            if (newPostButton) {
                newPostButton.addEventListener('click', () => {
                    // オプションメニューを閉じる
                    const insertOverlay = document.getElementById('insertOverlay');
                    if (insertOverlay) {
                        insertOverlay.style.display = 'none';
                    }

                    // フォームを動的に作成して送信
                    const form = document.createElement('form');
                    form.method = 'POST';
                    form.action = '/add_post';
                    form.target = '_blank';

                    // CSRFトークンを追加
                    const csrfToken = document.body.dataset.csrfToken;
                    const csrfInput = document.createElement('input');
                    csrfInput.type = 'hidden';
                    csrfInput.name = 'csrf_token';
                    csrfInput.value = csrfToken;
                    form.appendChild(csrfInput);

                    document.body.appendChild(form);
                    form.submit();
                });
            }

            // AI機能の実装（プリセット対応）
            const aiButton = document.getElementById('aiButton');
            const aiOverlay = document.getElementById('aiOverlay');
            const aiPromptInput = document.getElementById('aiPromptInput');
            const aiContextPreview = document.getElementById('aiContextPreview');
            const aiSendButton = document.getElementById('aiSendButton');
            const aiCancelButton = document.getElementById('aiCancelButton');
            const aiButtonText = document.getElementById('aiButtonText');
            const aiSpinner = document.getElementById('aiSpinner');
            const templateSelect = document.getElementById('templateSelect');
            const systemPromptSelect = document.getElementById('systemPromptSelect');

            let aiContextText = '';
            let aiCursorPosition = 0;
            let aiSelectionStart = 0; // 選択範囲の開始位置
            let aiSelectionEnd = 0; // 選択範囲の終了位置
            let aiPresets = null;
            let selectedTemplateId = null;
            let aiResultContent = ''; // AI結果を保存

            // AIプリセットを読み込む
            async function loadAIPresets() {
                try {
                    const response = await fetch('/ai_presets', {
                        headers: {
                            'X-CSRFToken': csrfToken
                        }
                    });
                    if (response.ok) {
                        aiPresets = await response.json();
                        renderTemplateSelect();
                        renderSystemPromptSelect();
                    } else {
                        console.error('Failed to load AI presets');
                    }
                } catch (error) {
                    console.error('Error loading AI presets:', error);
                }
            }

            // テンプレートドロップダウンを描画
            function renderTemplateSelect() {
                if (!aiPresets || !aiPresets.prompt_templates) return;

                templateSelect.innerHTML = '<option value="">-- テンプレートを選択 --</option>';

                Object.entries(aiPresets.prompt_templates).forEach(([id, template]) => {
                    const option = document.createElement('option');
                    option.value = id;
                    option.textContent = `${template.icon} ${template.name}`;
                    templateSelect.appendChild(option);
                });
            }

            // テンプレート選択時の処理
            templateSelect.addEventListener('change', () => {
                const selectedId = templateSelect.value;
                if (selectedId && aiPresets.prompt_templates[selectedId]) {
                    selectedTemplateId = selectedId;
                    aiPromptInput.value = aiPresets.prompt_templates[selectedId].prompt;
                } else {
                    selectedTemplateId = null;
                    aiPromptInput.value = '';
                }
            });

            // システムプロンプトセレクトを描画
            function renderSystemPromptSelect() {
                if (!aiPresets || !aiPresets.system_prompts) return;

                systemPromptSelect.innerHTML = '';
                const selectedPromptId = aiPresets.user_presets?.selected_system_prompt || 'default';

                Object.entries(aiPresets.system_prompts).forEach(([id, prompt]) => {
                    const option = document.createElement('option');
                    option.value = id;
                    option.textContent = prompt.name;
                    if (id === selectedPromptId) {
                        option.selected = true;
                    }
                    systemPromptSelect.appendChild(option);
                });
            }

            // システムプロンプトの選択変更を保存
            systemPromptSelect.addEventListener('change', async () => {
                const selectedId = systemPromptSelect.value;
                try {
                    await fetch('/ai_presets/system_prompt', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify({ preset_id: selectedId })
                    });
                } catch (error) {
                    console.error('Error saving system prompt:', error);
                }
            });

            // ページロード時にプリセットを読み込む
            loadAIPresets();

            // AIボタンクリック
            aiButton.addEventListener('click', () => {
                const start = contentTextArea.selectionStart;
                const end = contentTextArea.selectionEnd;
                const selectedText = contentTextArea.value.substring(start, end);

                if (selectedText) {
                    // テキスト選択時: コンテキストとして保存
                    aiContextText = selectedText;
                    aiSelectionStart = start;
                    aiSelectionEnd = end;
                    aiCursorPosition = end; // 選択範囲の終わりにカーソルを設定
                    aiContextPreview.textContent = selectedText;
                    aiContextPreview.style.display = 'block';
                } else {
                    // 未選択時: コンテキストなし
                    aiContextText = '';
                    aiSelectionStart = start;
                    aiSelectionEnd = start;
                    aiCursorPosition = start; // 現在のカーソル位置
                    aiContextPreview.style.display = 'none';
                }

                aiOverlay.style.display = 'flex';
                aiPromptInput.focus();
            });

            // AI送信ボタンクリック
            async function sendAIRequest() {
                let prompt = aiPromptInput.value.trim();

                // テンプレートが選択されていてプロンプト入力がない場合、テンプレートのプロンプトを使用
                if (selectedTemplateId && !prompt && aiPresets.prompt_templates[selectedTemplateId]) {
                    prompt = aiPresets.prompt_templates[selectedTemplateId].prompt;
                }

                if (!prompt) {
                    alert('テンプレートを選択するか、問い合わせ内容を入力してください');
                    return;
                }

                // ローディング状態に変更
                aiButtonText.style.display = 'none';
                aiSpinner.style.display = 'inline';
                aiSendButton.disabled = true;
                aiCancelButton.disabled = true;
                aiPromptInput.disabled = true;

                try {
                    const systemPromptId = systemPromptSelect.value;
                    const response = await fetch('/ai_assist', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify({
                            prompt: prompt,
                            context: aiContextText,
                            system_prompt_id: systemPromptId
                        })
                    });

                    const data = await response.json();

                    if (response.ok) {
                        // AI応答を保存して結果タブに表示
                        aiResultContent = data.response;
                        const aiResultText = document.getElementById('aiResultText');
                        if (aiResultText) {
                            aiResultText.value = aiResultContent;
                        }

                        // 結果タブに切り替え
                        const resultTab = document.getElementById('result-tab');
                        if (resultTab) {
                            resultTab.click();
                        }

                        // 置換ボタンの有効/無効を制御
                        updateReplaceButtonState();
                    } else {
                        alert('エラー: ' + (data.error || '不明なエラーが発生しました'));
                    }
                } catch (error) {
                    console.error('AI処理エラー:', error);
                    alert('AI処理に失敗しました: ' + error.message);
                } finally {
                    // ローディング状態を解除
                    aiButtonText.style.display = 'inline';
                    aiSpinner.style.display = 'none';
                    aiSendButton.disabled = false;
                    aiCancelButton.disabled = false;
                    aiPromptInput.disabled = false;
                }
            }

            aiSendButton.addEventListener('click', sendAIRequest);

            // AIキャンセルボタンクリック（入力タブ用）
            aiCancelButton.addEventListener('click', () => {
                aiOverlay.style.display = 'none';
                resetAIModal();
            });

            // AIオーバーレイクリック（背景クリック）
            aiOverlay.addEventListener('click', (event) => {
                if (event.target === aiOverlay) {
                    aiOverlay.style.display = 'none';
                    resetAIModal();
                }
            });

            // AIプロンプト入力でのIME制御
            let isAIComposing = false;
            aiPromptInput.addEventListener('compositionstart', () => {
                isAIComposing = true;
            });
            aiPromptInput.addEventListener('compositionend', () => {
                isAIComposing = false;
            });

            // AIプロンプト入力でのCtrl+Enter送信
            aiPromptInput.addEventListener('keydown', (event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !isAIComposing) {
                    event.preventDefault();
                    sendAIRequest();
                }
            });

            // 置換ボタンの有効/無効を制御
            function updateReplaceButtonState() {
                const aiReplaceButton = document.getElementById('aiReplaceButton');
                if (aiReplaceButton) {
                    // 選択範囲がある場合のみ有効
                    const hasSelection = aiContextText.length > 0;
                    aiReplaceButton.disabled = !hasSelection;
                    if (!hasSelection) {
                        aiReplaceButton.style.opacity = '0.5';
                        aiReplaceButton.title = 'テキストを選択してから実行してください';
                    } else {
                        aiReplaceButton.style.opacity = '1';
                        aiReplaceButton.title = '選択範囲をAI結果で置き換え';
                    }
                }
            }

            // 挿入ボタン（装飾付き）
            const aiInsertButton = document.getElementById('aiInsertButton');
            if (aiInsertButton) {
                aiInsertButton.addEventListener('click', () => {
                    if (!aiResultContent) return;

                    const insertText = '\n\n---\n**( ・∀・)つ〃∩＜どうも！**\n' + aiResultContent + '\n\n---\n';

                    // カーソル位置に挿入
                    const value = contentTextArea.value;
                    contentTextArea.value = value.slice(0, aiCursorPosition) + insertText + value.slice(aiCursorPosition);

                    // カーソルを挿入後の位置に移動
                    const newPosition = aiCursorPosition + insertText.length;
                    contentTextArea.selectionStart = contentTextArea.selectionEnd = newPosition;
                    contentTextArea.focus();

                    // プレビュー更新のために input イベントを発火
                    const event = new Event('input', { bubbles: true });
                    contentTextArea.dispatchEvent(event);

                    // モーダルを閉じる
                    aiOverlay.style.display = 'none';
                    resetAIModal();
                });
            }

            // 置換ボタン（装飾なし）
            const aiReplaceButton = document.getElementById('aiReplaceButton');
            if (aiReplaceButton) {
                aiReplaceButton.addEventListener('click', () => {
                    if (!aiResultContent || !aiContextText) return;

                    // 保存しておいた選択範囲をAI結果で置き換え（装飾なし）
                    const value = contentTextArea.value;

                    // 選択範囲を置換
                    contentTextArea.value = value.slice(0, aiSelectionStart) + aiResultContent + value.slice(aiSelectionEnd);

                    // カーソルを置換後の位置に移動
                    const newPosition = aiSelectionStart + aiResultContent.length;
                    contentTextArea.selectionStart = contentTextArea.selectionEnd = newPosition;
                    contentTextArea.focus();

                    // プレビュー更新のために input イベントを発火
                    const event = new Event('input', { bubbles: true });
                    contentTextArea.dispatchEvent(event);

                    // モーダルを閉じる
                    aiOverlay.style.display = 'none';
                    resetAIModal();
                });
            }

            // コピーボタン
            const aiCopyButton = document.getElementById('aiCopyButton');
            if (aiCopyButton) {
                aiCopyButton.addEventListener('click', () => {
                    if (!aiResultContent) return;

                    navigator.clipboard.writeText(aiResultContent).then(() => {
                        showTemporaryMessage('AI結果をコピーしました');
                    }).catch(() => {
                        showTemporaryMessage('コピーに失敗しました');
                    });
                });
            }

            // 結果タブのキャンセルボタン
            const aiResultCancelButton = document.getElementById('aiResultCancelButton');
            if (aiResultCancelButton) {
                aiResultCancelButton.addEventListener('click', () => {
                    aiOverlay.style.display = 'none';
                    resetAIModal();
                });
            }

            // AIモーダルをリセット
            function resetAIModal() {
                selectedTemplateId = null;
                aiPromptInput.value = '';
                templateSelect.value = '';
                aiResultContent = '';
                const aiResultText = document.getElementById('aiResultText');
                if (aiResultText) {
                    aiResultText.value = '';
                }
                // 入力タブに戻す
                const inputTab = document.getElementById('input-tab');
                if (inputTab) {
                    inputTab.click();
                }
            }

            // ========== プレビュー機能 ==========
            const previewToggleButton = document.getElementById('previewToggleButton');
            const previewPane = document.getElementById('previewPane');
            const resizer = document.getElementById('resizer');
            const editorContainer = document.querySelector('.editor-container');
            const editorPane = document.querySelector('.editor-pane');

            if (previewToggleButton && previewPane && resizer) {
                let previewVisible = false;

                // localStorageから前回の状態を復元
                const savedPreviewState = localStorage.getItem('previewVisible');
                if (savedPreviewState === 'true') {
                    previewVisible = true;
                }

                // Marked.js設定（post.htmlと同じ設定）
                const renderer = new marked.Renderer();

                renderer.code = function(code, language) {
                    const codeText = (typeof code === 'string' ? code : code.text).trim()
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;');
                    const lang = (language === undefined) ? code.lang : language;

                    if (lang === undefined) {
                        return `<pre>${codeText}</pre>`;
                    }

                    if (lang === 'mermaid') {
                        return `<div class="mermaid">${codeText}</div>`;
                    } else {
                        return `<pre><code>${codeText}</code></pre>`;
                    }
                };

                renderer.image = function(href, title, text) {
                    if (typeof href === 'object' && href !== null) {
                        href = href.href || 'default-image-path.jpg';
                    } else if (typeof href !== 'string') {
                        console.error('Invalid href:', href);
                        href = 'default-image-path.jpg';
                    }
                    text = text || 'image';
                    return `<img loading="lazy" src="${href}" alt="${text}">`;
                };

                marked.setOptions({
                    renderer: renderer,
                    sanitize: true
                });

                // テーブルのレンダリングをカスタマイズ
                const originalTable = renderer.table;
                renderer.table = function(header, body) {
                    const table = originalTable.call(this, header, body);
                    return '<div class="table-responsive">' + table + '</div>';
                };

                // Mermaid初期化
                mermaid.initialize({ startOnLoad: false });

                // プレビュー更新関数
                let updateTimeout;
                function updatePreview() {
                    clearTimeout(updateTimeout);
                    updateTimeout = setTimeout(() => {
                        const markdown = contentTextArea.value;

                        // タイトルとタグを除外（3行目以降をプレビュー）
                        const lines = markdown.split('\n');
                        const contentOnly = lines.slice(2).join('\n');

                        try {
                            const html = marked.parse(contentOnly);

                            // 画面表示の際、以下のタグをエスケープ（post.htmlと同じ処理）
                            const tagsToEscape = ['title', 'script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'link', 'meta'];
                            let escapedHtml = html;
                            tagsToEscape.forEach(tag => {
                                const regex = new RegExp(`<${tag}>`, 'g');
                                const closingRegex = new RegExp(`</${tag}>`, 'g');
                                escapedHtml = escapedHtml.replace(regex, `&lt;${tag}&gt;`).replace(closingRegex, `&lt;/${tag}&gt;`);
                            });

                            // preview-content div に挿入（styles.cssの#contentスタイルを適用するため）
                            const previewContent = document.getElementById('preview-content');
                            previewContent.innerHTML = escapedHtml;

                            // Mermaidダイアグラムを再レンダリング
                            const mermaidElements = previewContent.querySelectorAll('.mermaid');
                            mermaidElements.forEach((element, index) => {
                                const id = `mermaid-${Date.now()}-${index}`;
                                mermaid.render(id, element.textContent).then(result => {
                                    element.innerHTML = result.svg;
                                }).catch(error => {
                                    console.error('Mermaid rendering error:', error);
                                    element.innerHTML = `<pre>Mermaid Error: ${error.message}</pre>`;
                                });
                            });

                            // スライドショー機能を初期化
                            if (typeof initializeSlideshowImages === 'function') {
                                initializeSlideshowImages('#preview-content');
                            }
                        } catch (error) {
                            console.error('Markdown rendering error:', error);
                            const previewContent = document.getElementById('preview-content');
                            previewContent.innerHTML = '<p>Markdown rendering error</p>';
                        }
                    }, 300); // 300ms debounce
                }

                // プレビュートグル関数
                const togglePreview = () => {
                    previewVisible = !previewVisible;

                    // localStorageに状態を保存
                    localStorage.setItem('previewVisible', previewVisible);

                    if (previewVisible) {
                        previewPane.classList.remove('hidden');
                        editorContainer.classList.remove('preview-hidden');
                        editorPane.style.flex = '1';
                        previewPane.style.flex = '1';
                        updatePreview();
                    } else {
                        previewPane.classList.add('hidden');
                        editorContainer.classList.add('preview-hidden');
                    }
                };

                // プレビュートグルボタン（ツールバー）
                previewToggleButton.addEventListener('click', togglePreview);

                // リアルタイムプレビュー更新
                contentTextArea.addEventListener('input', () => {
                    if (previewVisible) {
                        updatePreview();
                    }
                });

                // localStorageの状態に基づいてプレビューを初期表示
                if (previewVisible) {
                    previewPane.classList.remove('hidden');
                    editorContainer.classList.remove('preview-hidden');
                    editorPane.style.flex = '1';
                    previewPane.style.flex = '1';
                    updatePreview();
                }

                // リサイザーのドラッグ機能
                let isResizing = false;
                let startX = 0;
                let startEditorWidth = 0;
                let startPreviewWidth = 0;

                resizer.addEventListener('mousedown', (e) => {
                    if (!previewVisible) return;

                    isResizing = true;
                    startX = e.clientX;
                    startEditorWidth = editorPane.offsetWidth;
                    startPreviewWidth = previewPane.offsetWidth;

                    document.body.style.cursor = 'col-resize';
                    document.body.style.userSelect = 'none';

                    e.preventDefault();
                });

                document.addEventListener('mousemove', (e) => {
                    if (!isResizing) return;

                    const deltaX = e.clientX - startX;
                    const containerWidth = editorContainer.offsetWidth;
                    const resizerWidth = resizer.offsetWidth;

                    const newEditorWidth = startEditorWidth + deltaX;
                    const newPreviewWidth = startPreviewWidth - deltaX;

                    // 最小幅チェック（200px）
                    if (newEditorWidth >= 200 && newPreviewWidth >= 200) {
                        const editorFlex = newEditorWidth / (containerWidth - resizerWidth);
                        const previewFlex = newPreviewWidth / (containerWidth - resizerWidth);

                        editorPane.style.flex = editorFlex;
                        previewPane.style.flex = previewFlex;
                    }
                });

                document.addEventListener('mouseup', () => {
                    if (isResizing) {
                        isResizing = false;
                        document.body.style.cursor = '';
                        document.body.style.userSelect = '';
                    }
                });
            }
        });

        function wrapSelectedTextWith(textArea, text) {
            if (!textArea) return;
            const start = textArea.selectionStart;
            const end = textArea.selectionEnd;
            const value = textArea.value;

            // 選択部分の前後にテキストを挿入
            if (text === '**') {
                //textArea.value = value.slice(0, start) + ' ' + text + value.slice(start, end) + text + ' ' + value.slice(end);
                textArea.value = value.slice(0, start) + text + value.slice(start, end) + text + value.slice(end);
                textArea.selectionStart = start + text.length; // 前後のスペースを考慮
                textArea.selectionEnd = end + text.length;
            } else {
                textArea.value = value.slice(0, start) + text + value.slice(start, end) + text + value.slice(end);
                textArea.selectionStart = start + text.length;
                textArea.selectionEnd = end + text.length;
            }
            textArea.focus();

            // プレビュー更新のために input イベントを発火
            const event = new Event('input', { bubbles: true });
            textArea.dispatchEvent(event);
        }

        function insertTextAtLineStart(textArea, text) {
            if (!textArea) return;
            const start = textArea.selectionStart;
            const end = textArea.selectionEnd;
            const value = textArea.value;

            const lineStart = value.lastIndexOf('\n', start - 1) + 1;
            const lineEnd = value.indexOf('\n', end);
            const before = value.slice(0, lineStart);
            const after = value.slice(lineEnd === -1 ? value.length : lineEnd);

            const selectedLines = value.slice(lineStart, lineEnd === -1 ? value.length : lineEnd);
            const newText = selectedLines.split('\n').map(line => text + line).join('\n');

            textArea.value = before + newText + after;
            textArea.selectionStart = lineStart;
            textArea.selectionEnd = lineStart + newText.length;

            textArea.focus();
            console.log('Inserted Text at Line Start:', text);
        }

        function insertTextAtCursor(textArea, text) {
            if (!textArea) return;
            const start = textArea.selectionStart;
            const end = textArea.selectionEnd;
            const value = textArea.value;
            textArea.value = value.slice(0, start) + text + value.slice(start);
            textArea.selectionStart = textArea.selectionEnd = start + text.length;
            textArea.focus();

            // プレビュー更新のために input イベントを手動で発火
            const event = new Event('input', { bubbles: true });
            textArea.dispatchEvent(event);
        }

        function getCurrentDate() {
            const now = new Date();
            const year = now.getFullYear();
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const day = String(now.getDate()).padStart(2, '0');
            return `${year}${month}${day}`;
        }

        function getCurrentTime() {
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            return `${hours}${minutes}${seconds}`;
        }

        async function handlePaste(event) {
            const items = (event.clipboardData || window.clipboardData).items;
            for (let item of items) {
                if (item.kind === 'file' && item.type.startsWith('image/')) {
                    const file = item.getAsFile();
                    if (file) {
                        const formData = new FormData();
                        formData.append('file', file);

                        try {
                            const response = await fetch('/attach_upload', {
                                method: 'POST',
                                body: formData,
                                headers: {
                                    'X-CSRFToken': csrfToken  // CSRFトークンをヘッダーに追加
                                }
                            });

                            if (response.ok) {
                                const result = await response.json();
                                const filename = result.filename;
                                const url = result.url;
                                const smallImageUrl = url.replace(/\/([^\/]+)$/, '/s_$1');

                                // 改善版：title属性付きMarkdown
                                const markdownLink = result.isImage
                                    ? `[![${filename}](${smallImageUrl} "${filename}")](${url} "${filename}")`
                                    : `[${filename}](${url} "${filename}")`;

                                console.log(markdownLink);
                                insertTextAtCursor(document.getElementById('content'), markdownLink);
                            } else {
                                alert('ファイルのアップロードに失敗しました。');
                            }
                        } catch (error) {
                            console.error('アップロード中にエラーが発生しました:', error);
                            alert('ファイルのアップロードに失敗しました。');
                        }
                    }
                    event.preventDefault();
                }
            }
        }

        async function saveWithoutRedirect() {
            const saveButton = document.getElementById('saveButton');
            const content = document.getElementById('content').value;
            const formData = new FormData();
            formData.append('content', content);

            // 保存中: ボタンを無効化 + スピナー表示
            saveButton.disabled = true;
            saveButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            try {
                const response = await fetch(window.location.href, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': csrfToken
                    }
                });

                if (response.ok) {
                    showTemporaryMessage('保存成功!');
                } else {
                    showTemporaryMessage('保存失敗!');
                }
            } catch (error) {
                console.error('保存中にエラーが発生しました:', error);
                showTemporaryMessage('保存失敗!');
            } finally {
                // 保存完了: ボタンを復元
                saveButton.disabled = false;
                saveButton.innerHTML = '<i class="fas fa-save"></i>';
            }
        }

        function cycleHeaderLevel(textArea) {
            if (!textArea) return;
            const start = textArea.selectionStart;
            const end = textArea.selectionEnd;
            const value = textArea.value;

            // 選択範囲を含む行の開始と終了を取得
            const lineStart = value.lastIndexOf('\n', start - 1) + 1;
            const lineEnd = value.indexOf('\n', end);
            const before = value.slice(0, lineStart);
            const after = value.slice(lineEnd === -1 ? value.length : lineEnd);

            // 選択範囲内の行を取得
            const selectedLines = value.slice(lineStart, lineEnd === -1 ? value.length : lineEnd);

            // 各行を独立してトグル
            const newText = selectedLines.split('\n').map(line => {
                // 現在の#の数を数える
                const match = line.match(/^#{1,3}\s/);
                let newPrefix = '';

                if (!match) {
                    newPrefix = '# '; // #なしから#へ
                } else {
                    const hashCount = match[0].trim().length;
                    if (hashCount < 3) {
                        newPrefix = '#'.repeat(hashCount + 1) + ' '; // 次のレベルへ
                    }
                    // hashCount === 3 の場合は newPrefix = '' のまま（#を削除）
                }

                // 既存の#を削除して新しい#を追加
                const lineWithoutHash = line.replace(/^#{1,3}\s/, '');
                return newPrefix + lineWithoutHash;
            }).join('\n');

            textArea.value = before + newText + after;
            textArea.selectionStart = lineStart;
            textArea.selectionEnd = lineStart + newText.length;
            textArea.focus();

            // プレビュー更新のために input イベントを発火
            const event = new Event('input', { bubbles: true });
            textArea.dispatchEvent(event);
        }

        function cycleDashMark(textArea) {
            if (!textArea) return;
            const start = textArea.selectionStart;
            const end = textArea.selectionEnd;
            const value = textArea.value;

            // 選択範囲を含む行の開始と終了を取得
            const lineStart = value.lastIndexOf('\n', start - 1) + 1;
            const lineEnd = value.indexOf('\n', end);
            const before = value.slice(0, lineStart);
            const after = value.slice(lineEnd === -1 ? value.length : lineEnd);

            // 選択範囲内の行を取得
            const selectedLines = value.slice(lineStart, lineEnd === -1 ? value.length : lineEnd);

            // 各行を独立して3段階ローテーション（無し → - → インデント付き- → 無し）
            const newText = selectedLines.split('\n').map(line => {
                const hasIndentedDash = line.match(/^    - /);  // 4スペース + "- "
                const hasDash = line.match(/^- /);

                if (hasIndentedDash) {
                    // 3段階目: インデント付き → 除外
                    return line.replace(/^    - /, '');
                } else if (hasDash) {
                    // 2段階目: 付与 → インデント付与
                    return line.replace(/^- /, '    - ');
                } else {
                    // 1段階目: 無し → 付与
                    return '- ' + line;
                }
            }).join('\n');

            textArea.value = before + newText + after;
            textArea.selectionStart = lineStart;
            textArea.selectionEnd = lineStart + newText.length;
            textArea.focus();

            // プレビュー更新のために input イベントを発火
            const event = new Event('input', { bubbles: true });
            textArea.dispatchEvent(event);
        }

        function cycleNumberMark(textArea) {
            if (!textArea) return;
            const start = textArea.selectionStart;
            const end = textArea.selectionEnd;
            const value = textArea.value;

            // 選択範囲を含む行の開始と終了を取得
            const lineStart = value.lastIndexOf('\n', start - 1) + 1;
            const lineEnd = value.indexOf('\n', end);
            const before = value.slice(0, lineStart);
            const after = value.slice(lineEnd === -1 ? value.length : lineEnd);

            // 選択範囲内の行を取得
            const selectedLines = value.slice(lineStart, lineEnd === -1 ? value.length : lineEnd);

            // 各行を独立して3段階ローテーション（無し → 1. → インデント付き1. → 無し）
            const newText = selectedLines.split('\n').map(line => {
                const hasIndentedNumber = line.match(/^    1\. /);  // 4スペース + "1. "
                const hasNumber = line.match(/^1\. /);

                if (hasIndentedNumber) {
                    // 3段階目: インデント付き → 除外
                    return line.replace(/^    1\. /, '');
                } else if (hasNumber) {
                    // 2段階目: 付与 → インデント付与
                    return line.replace(/^1\. /, '    1. ');
                } else {
                    // 1段階目: 無し → 付与
                    return '1. ' + line;
                }
            }).join('\n');

            textArea.value = before + newText + after;
            textArea.selectionStart = lineStart;
            textArea.selectionEnd = lineStart + newText.length;
            textArea.focus();

            // プレビュー更新のために input イベントを発火
            const event = new Event('input', { bubbles: true });
            textArea.dispatchEvent(event);
        }

        function cycleQuoteMark(textArea) {
            if (!textArea) return;
            const start = textArea.selectionStart;
            const end = textArea.selectionEnd;
            const value = textArea.value;

            // 選択範囲を含む行の開始と終了を取得
            const lineStart = value.lastIndexOf('\n', start - 1) + 1;
            const lineEnd = value.indexOf('\n', end);
            const before = value.slice(0, lineStart);
            const after = value.slice(lineEnd === -1 ? value.length : lineEnd);

            // 選択範囲内の行を取得
            const selectedLines = value.slice(lineStart, lineEnd === -1 ? value.length : lineEnd);

            // 各行を独立してトグル
            const newText = selectedLines.split('\n').map(line => {
                const hasQuote = line.match(/^> /);
                return hasQuote ? line.replace(/^> /, '') : '> ' + line;
            }).join('\n');

            textArea.value = before + newText + after;
            textArea.selectionStart = lineStart;
            textArea.selectionEnd = lineStart + newText.length;
            textArea.focus();

            // プレビュー更新のために input イベントを発火
            const event = new Event('input', { bubbles: true });
            textArea.dispatchEvent(event);
        }

        function cycleFourSpaces(textArea) {
            if (!textArea) return;
            const start = textArea.selectionStart;
            const end = textArea.selectionEnd;
            const value = textArea.value;

            // 選択範囲を含む行の開始と終了を取得
            const lineStart = value.lastIndexOf('\n', start - 1) + 1;
            const lineEnd = value.indexOf('\n', end);
            const before = value.slice(0, lineStart);
            const after = value.slice(lineEnd === -1 ? value.length : lineEnd);

            // 選択範囲内の行を取得
            const selectedLines = value.slice(lineStart, lineEnd === -1 ? value.length : lineEnd);

            // 各行を独立してトグル
            const newText = selectedLines.split('\n').map(line => {
                const hasFourSpaces = line.match(/^    /); // 4つのスペースで始まるか
                return hasFourSpaces ? line.replace(/^    /, '') : '    ' + line;
            }).join('\n');

            textArea.value = before + newText + after;
            textArea.selectionStart = lineStart;
            textArea.selectionEnd = lineStart + newText.length;
            textArea.focus();

            // プレビュー更新のために input イベントを発火
            const event = new Event('input', { bubbles: true });
            textArea.dispatchEvent(event);
        }


// ページ切り替え機能
(function() {
    const overlay = document.getElementById('switchPageOverlay');
    const pageList = document.getElementById('pageList');
    let pageItems = [];  // 動的に更新されるページアイテム配列
    let selectedIndex = 0;

    // Ctrl+K でオーバーレイを開く
    document.addEventListener('keydown', function(event) {
        // Ctrl+K または Cmd+K
        if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
            event.preventDefault();
            openSwitchPageOverlay();
        }
    });

    // HTMLエスケープ関数
    function escapeHtmlForPageList(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ページリストを描画
    function renderPageList(posts) {
        pageList.innerHTML = '';
        pageItems = [];

        if (posts.length === 0) {
            pageList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">他のページがありません</div>';
            return;
        }

        posts.forEach((post, index) => {
            const item = document.createElement('div');
            item.className = 'page-item';
            item.dataset.filename = post.filename;
            item.dataset.index = index;

            item.innerHTML = `
                <div class="page-info">
                    <div class="page-date">
                        <i class="fas fa-clock"></i> ${escapeHtmlForPageList(post.date)}
                    </div>
                    <div class="page-title">${escapeHtmlForPageList(post.title)}</div>
                    <div class="page-filename">${escapeHtmlForPageList(post.filename)}</div>
                </div>
                <div class="page-actions">
                    <button class="btn-page-view" title="閲覧">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-page-edit" title="編集">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            `;

            // ホバーイベント
            item.addEventListener('mouseenter', function() {
                selectedIndex = index;
                updateSelection();
            });

            // クリックイベント（Ctrl+クリック対応）
            item.addEventListener('click', function(event) {
                // page-actions内のボタンからのクリックは無視（ボタン側で処理）
                if (event.target.closest('.page-actions')) {
                    return;
                }
                const filename = item.dataset.filename;
                // Ctrl+クリック または Cmd+クリック: 新しいタブで開く（モーダルは残す）
                if (event.ctrlKey || event.metaKey) {
                    event.preventDefault();
                    navigateToPage(filename, true);
                } else {
                    // 通常クリック: 現在のタブで遷移（モーダルを閉じる）
                    navigateToPage(filename, false);
                }
            });

            // 閲覧ボタン
            const viewButton = item.querySelector('.btn-page-view');
            if (viewButton) {
                viewButton.addEventListener('click', function(event) {
                    event.stopPropagation();
                    navigateToPage(post.filename, 'view', event);
                });
            }

            // 編集ボタン
            const editButton = item.querySelector('.btn-page-edit');
            if (editButton) {
                editButton.addEventListener('click', function(event) {
                    event.stopPropagation();
                    navigateToPage(post.filename, 'edit', event);
                });
            }

            pageList.appendChild(item);
            pageItems.push(item);
        });
    }

    // オーバーレイを開く（非同期で最新データを取得）
    async function openSwitchPageOverlay() {
        // まずオーバーレイを表示（ローディング状態）
        overlay.style.display = 'flex';
        pageList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;"><i class="fas fa-spinner fa-spin"></i> 読み込み中...</div>';

        // サーバーから最新のページ一覧を取得
        const currentFilename = document.body.dataset.filename;
        try {
            const response = await fetch(`/api/ui/recent_posts?exclude=${encodeURIComponent(currentFilename)}`, {
                headers: { 'X-CSRFToken': csrfToken }
            });
            if (response.ok) {
                const posts = await response.json();
                renderPageList(posts);
            } else {
                pageList.innerHTML = '<div style="padding: 20px; text-align: center; color: #f00;">ページリストの取得に失敗しました</div>';
            }
        } catch (error) {
            console.error('ページリストの取得に失敗:', error);
            pageList.innerHTML = '<div style="padding: 20px; text-align: center; color: #f00;">エラーが発生しました</div>';
        }

        selectedIndex = 0;
        updateSelection();

        // オーバーレイ内のキーボードイベント
        document.addEventListener('keydown', handleOverlayKeydown);
    }

    // オーバーレイを閉じる
    function closeSwitchPageOverlay() {
        overlay.style.display = 'none';
        document.removeEventListener('keydown', handleOverlayKeydown);
    }

    // オーバーレイ内でのキーボード操作
    function handleOverlayKeydown(event) {
        if (overlay.style.display !== 'flex') return;

        switch(event.key) {
            case 'ArrowDown':
                event.preventDefault();
                selectedIndex = Math.min(selectedIndex + 1, pageItems.length - 1);
                updateSelection();
                break;

            case 'ArrowUp':
                event.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, 0);
                updateSelection();
                break;

            case 'Enter':
                event.preventDefault();
                event.stopPropagation(); // イベント伝播を停止（グローバルハンドラーを防ぐ）
                if (pageItems[selectedIndex]) {
                    const filename = pageItems[selectedIndex].dataset.filename;
                    // Ctrl+Enter: 新しいタブで開く（モーダルは残す）
                    if (event.ctrlKey || event.metaKey) {
                        navigateToPage(filename, true);
                    } else {
                        // 通常Enter: 現在のタブで遷移（モーダルを閉じる）
                        navigateToPage(filename, false);
                    }
                }
                break;

            case 'Escape':
                event.preventDefault();
                closeSwitchPageOverlay();
                break;
        }
    }

    // 選択状態を更新
    function updateSelection() {
        pageItems.forEach((item, index) => {
            if (index === selectedIndex) {
                item.classList.add('selected');
                // スクロールして表示
                item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } else {
                item.classList.remove('selected');
            }
        });
    }

    // ページに移動
    window.navigateToPage = function(filename, modeOrEvent, eventArg) {
        // 後方互換性: 第2引数がboolean（旧API）の場合の処理
        var mode = 'edit';  // デフォルトは編集
        var event = null;

        if (typeof modeOrEvent === 'boolean') {
            // 旧API: navigateToPage(filename, openInNewTab)
            var openInNewTab = modeOrEvent;
            if (openInNewTab) {
                window.open('/edit_post/' + filename, '_blank');
            } else {
                closeSwitchPageOverlay();
                location.href = '/edit_post/' + filename;
            }
            return;
        }

        // 新API: navigateToPage(filename, mode, event)
        mode = modeOrEvent || 'edit';
        event = eventArg;

        if (event) {
            event.stopPropagation();
        }

        var openInNewTab = event && event.ctrlKey;
        var url = mode === 'edit' ? '/edit_post/' + filename : '/post/' + filename;

        if (openInNewTab) {
            window.open(url, '_blank');
        } else {
            closeSwitchPageOverlay();
            location.href = url;
        }
    };

    // ページ切り替えボタン
    const switchPageButton = document.getElementById('switchPageButton');
    if (switchPageButton) {
        switchPageButton.addEventListener('click', function() {
            openSwitchPageOverlay();
        });
    }

    // キャンセルボタン
    const cancelButton = document.getElementById('switchPageCancelButton');
    if (cancelButton) {
        cancelButton.addEventListener('click', function() {
            closeSwitchPageOverlay();
        });
    }

    // オーバーレイの背景クリックで閉じる
    overlay.addEventListener('click', function(event) {
        if (event.target === overlay) {
            closeSwitchPageOverlay();
        }
    });
})();

// バックアップ確認機能
(function() {
    const currentFilename = document.body.dataset.filename;
    const backupButton = document.getElementById('backupButton');
    const insertOverlay = document.getElementById('insertOverlay');
    const backupListOverlay = document.getElementById('backupListOverlay');
    const backupContentOverlay = document.getElementById('backupContentOverlay');
    const backupList = document.getElementById('backupList');
    let backupItems = [];
    let selectedBackupIndex = 0;
    let currentBackupContent = '';
    let isDiffMode = false;

    // バックアップボタンクリック
    if (backupButton) {
        backupButton.addEventListener('click', async () => {
            insertOverlay.style.display = 'none';
            await loadBackupList();
            backupListOverlay.style.display = 'flex';
            selectedBackupIndex = 0;
            updateBackupSelection();
        });
    }

    // バックアップ一覧を取得
    async function loadBackupList() {
        try {
            const response = await fetch(`/api/backups/${currentFilename}`, {
                headers: { 'X-CSRFToken': csrfToken }
            });

            if (response.ok) {
                const data = await response.json();
                renderBackupList(data.backups);
            } else {
                alert('バックアップの取得に失敗しました');
            }
        } catch (error) {
            console.error('Error loading backups:', error);
            alert('エラーが発生しました');
        }
    }

    // バックアップ一覧を描画
    function renderBackupList(backups) {
        backupList.innerHTML = '';
        backupItems = [];

        if (backups.length === 0) {
            backupList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">バックアップがありません</div>';
            return;
        }

        backups.forEach((backup, index) => {
            const item = document.createElement('div');
            item.className = 'backup-item';
            item.dataset.filename = backup.filename;
            item.dataset.index = index;

            item.innerHTML = `
                <div class="backup-date">
                    <i class="fas fa-clock"></i> ${backup.date}
                    <span class="backup-relative-time">(${backup.relative_time})</span>
                </div>
                <div class="backup-filename">${backup.filename}</div>
            `;

            // クリックイベント
            item.addEventListener('click', () => {
                selectedBackupIndex = index;
                updateBackupSelection();
                openBackupContent(backup.filename);
            });

            // ホバーイベント
            item.addEventListener('mouseenter', () => {
                selectedBackupIndex = index;
                updateBackupSelection();
            });

            backupList.appendChild(item);
            backupItems.push(item);
        });
    }

    // 選択状態を更新
    function updateBackupSelection() {
        backupItems.forEach((item, index) => {
            if (index === selectedBackupIndex) {
                item.classList.add('selected');
                item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } else {
                item.classList.remove('selected');
            }
        });
    }

    // キーボード操作（バックアップ一覧）
    document.addEventListener('keydown', (event) => {
        if (backupListOverlay.style.display !== 'flex') return;

        switch(event.key) {
            case 'ArrowDown':
                event.preventDefault();
                selectedBackupIndex = Math.min(selectedBackupIndex + 1, backupItems.length - 1);
                updateBackupSelection();
                break;
            case 'ArrowUp':
                event.preventDefault();
                selectedBackupIndex = Math.max(selectedBackupIndex - 1, 0);
                updateBackupSelection();
                break;
            case 'Enter':
                event.preventDefault();
                if (backupItems[selectedBackupIndex]) {
                    const filename = backupItems[selectedBackupIndex].dataset.filename;
                    openBackupContent(filename);
                }
                break;
            case 'Escape':
                event.preventDefault();
                backupListOverlay.style.display = 'none';
                break;
        }
    });

    // バックアップ内容を表示
    async function openBackupContent(backupFilename) {
        try {
            const response = await fetch(`/api/backup_content/${encodeURIComponent(backupFilename)}`, {
                headers: { 'X-CSRFToken': csrfToken }
            });

            if (response.ok) {
                const data = await response.json();
                currentBackupContent = data.content;

                document.getElementById('backupContentTitle').textContent = `バックアップ内容: ${backupFilename}`;
                document.getElementById('backupContentText').value = data.content;

                // 初期状態は通常表示
                isDiffMode = false;
                document.getElementById('backupContentText').style.display = 'block';
                document.getElementById('backupContentDiff').style.display = 'none';
                document.getElementById('backupDiffButton').classList.remove('active');
                document.getElementById('backupDiffButton').innerHTML = '<i class="fas fa-code-compare"></i> 差分';

                backupContentOverlay.style.display = 'flex';
            } else {
                alert('バックアップ内容の取得に失敗しました');
            }
        } catch (error) {
            console.error('Error loading backup content:', error);
            alert('エラーが発生しました');
        }
    }

    // 差分ボタン
    const backupDiffButton = document.getElementById('backupDiffButton');
    if (backupDiffButton) {
        backupDiffButton.addEventListener('click', () => {
            toggleDiffMode();
        });
    }

    // 差分表示モードの切り替え
    function toggleDiffMode() {
        isDiffMode = !isDiffMode;

        const textArea = document.getElementById('backupContentText');
        const diffDiv = document.getElementById('backupContentDiff');
        const diffButton = document.getElementById('backupDiffButton');

        if (isDiffMode) {
            // 差分表示モードに切り替え
            textArea.style.display = 'none';
            diffDiv.style.display = 'block';
            diffButton.classList.add('active');
            diffButton.innerHTML = '<i class="fas fa-file-alt"></i> 通常';

            // 差分を計算して表示
            renderDiffHighlight();
        } else {
            // 通常表示モードに切り替え
            textArea.style.display = 'block';
            diffDiv.style.display = 'none';
            diffButton.classList.remove('active');
            diffButton.innerHTML = '<i class="fas fa-code-compare"></i> 差分';
        }
    }

    // 差分をハイライト表示
    function renderDiffHighlight() {
        const backupText = currentBackupContent;
        const currentText = document.getElementById('content').value;

        const dmp = new diff_match_patch();
        const diffs = dmp.diff_main(backupText, currentText);
        dmp.diff_cleanupSemantic(diffs);

        let html = '';
        let lineNumber = 1;

        diffs.forEach(([operation, text]) => {
            const lines = text.split('\n');

            lines.forEach((line, index) => {
                let lineClass = '';
                let prefix = '';

                if (operation === -1) {
                    // 削除された行（バックアップにあるが現在はない）
                    lineClass = 'diff-line-deleted';
                    prefix = '- ';
                } else if (operation === 1) {
                    // 追加された行（バックアップになく現在ある）
                    lineClass = 'diff-line-added';
                    prefix = '+ ';
                } else {
                    // 変更なし
                    lineClass = 'diff-line-normal';
                    prefix = '  ';
                }

                html += `<div class="diff-line ${lineClass}">` +
                       `<span class="diff-line-number">${lineNumber}</span>` +
                       escapeHtml(prefix + line) +
                       `</div>`;

                if (operation !== 1) {
                    lineNumber++;
                }
            });
        });

        document.getElementById('backupContentDiff').innerHTML = html;
    }

    // HTMLエスケープ
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // コピーボタン
    const backupCopyButton = document.getElementById('backupCopyButton');
    if (backupCopyButton) {
        backupCopyButton.addEventListener('click', () => {
            let content = '';

            if (isDiffMode) {
                // 差分モードの場合：削除行と通常行のみをコピー
                const diffDiv = document.getElementById('backupContentDiff');
                const lines = diffDiv.querySelectorAll('.diff-line');

                lines.forEach(line => {
                    if (!line.classList.contains('diff-line-added')) {
                        const text = line.textContent;
                        const lineContent = text.substring(text.indexOf(' ', 5) + 1);
                        content += lineContent + '\n';
                    }
                });
                content = content.trimEnd();
            } else {
                // 通常モードの場合：そのままコピー
                content = document.getElementById('backupContentText').value;
            }

            navigator.clipboard.writeText(content).then(() => {
                showTemporaryMessage('コピーしました！');
            });
        });
    }

    // 復元ボタン
    const backupRestoreButton = document.getElementById('backupRestoreButton');
    if (backupRestoreButton) {
        backupRestoreButton.addEventListener('click', () => {
            if (confirm('現在の編集内容をバックアップ内容で置き換えますか？\n（この操作は元に戻せません）')) {
                document.getElementById('content').value = currentBackupContent;
                backupContentOverlay.style.display = 'none';
                backupListOverlay.style.display = 'none';
                showTemporaryMessage('復元しました！');

                // プレビュー更新
                const event = new Event('input', { bubbles: true });
                document.getElementById('content').dispatchEvent(event);
            }
        });
    }

    // 閉じるボタン
    const backupContentCloseButton = document.getElementById('backupContentCloseButton');
    if (backupContentCloseButton) {
        backupContentCloseButton.addEventListener('click', () => {
            backupContentOverlay.style.display = 'none';
        });
    }

    const backupListCancelButton = document.getElementById('backupListCancelButton');
    if (backupListCancelButton) {
        backupListCancelButton.addEventListener('click', () => {
            backupListOverlay.style.display = 'none';
        });
    }

    // ESCキー（バックアップ内容表示）
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && backupContentOverlay.style.display === 'flex') {
            event.preventDefault();
            backupContentOverlay.style.display = 'none';
        }
    });

    // 背景クリック
    if (backupListOverlay) {
        backupListOverlay.addEventListener('click', (event) => {
            if (event.target === backupListOverlay) {
                backupListOverlay.style.display = 'none';
            }
        });
    }

    if (backupContentOverlay) {
        backupContentOverlay.addEventListener('click', (event) => {
            if (event.target === backupContentOverlay) {
                backupContentOverlay.style.display = 'none';
            }
        });
    }
})();
