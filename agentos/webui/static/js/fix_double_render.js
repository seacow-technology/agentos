/**
 * 修复消息二次渲染问题
 * 此文件会自动在页面加载时应用修复
 */
(function() {
    // 等待DOM和loadMessages函数加载
    function applyFix() {
        if (typeof window.loadMessages === 'undefined') {
            setTimeout(applyFix, 100);
            return;
        }

        console.log('🔧 [Fix] 应用消息去重和并发保护');

        let isLoadingMessages = false;

        window.loadMessages = async function() {
            if (isLoadingMessages) {
                console.warn('[Fix] loadMessages并发调用被拒绝');
                return;
            }

            isLoadingMessages = true;

            try {
                const response = await fetch(`/api/sessions/${state.currentSession}/messages`);
                const messagesDiv = document.getElementById('messages');

                if (!response.ok) {
                    if (response.status === 404) {
                        messagesDiv.innerHTML = '<div class="text-center text-red-500 text-sm">Session not found.</div>';
                        return;
                    }
                    throw new Error(`HTTP ${response.status}`);
                }

                const messages = await response.json();

                // 消息去重
                const uniqueMessages = [];
                const seenIds = new Set();

                for (const msg of messages) {
                    const msgId = msg.id || `${msg.role}-${msg.content.substring(0, 50)}`;
                    if (!seenIds.has(msgId)) {
                        seenIds.add(msgId);
                        uniqueMessages.push(msg);
                    } else {
                        console.warn('[Fix] 跳过重复消息:', msgId);
                    }
                }

                if (uniqueMessages.length !== messages.length) {
                    console.warn(`[Fix] 检测到 ${messages.length - uniqueMessages.length} 条重复消息`);
                }

                messagesDiv.innerHTML = '';

                if (!Array.isArray(messages) || uniqueMessages.length === 0) {
                    messagesDiv.innerHTML = '<div class="text-center text-gray-500 text-sm">No messages yet.</div>';
                    return;
                }

                uniqueMessages.forEach(msg => {
                    const msgEl = createMessageElement(msg.role, msg.content, msg.metadata || {});
                    if (msg.id) msgEl.dataset.messageId = msg.id;
                    messagesDiv.appendChild(msgEl);

                    const isExtension = msg.metadata?.is_extension_output === true;
                    if (msg.role === 'assistant' && !isExtension && window.CodeBlockUtils) {
                        const contentDiv = msgEl.querySelector('.content');
                        if (contentDiv) {
                            contentDiv.innerHTML = window.CodeBlockUtils.renderAssistantMessage(msg.content);
                            if (typeof highlightCodeBlocks === 'function') {
                                highlightCodeBlocks(contentDiv);
                            }
                        }
                    }
                });

                messagesDiv.scrollTop = messagesDiv.scrollHeight;

            } catch (err) {
                console.error('[Fix] loadMessages错误:', err);
                const messagesDiv = document.getElementById('messages');
                if (messagesDiv) {
                    messagesDiv.innerHTML = '<div class="text-center text-red-500 text-sm">Failed to load messages</div>';
                }
            } finally {
                isLoadingMessages = false;
            }
        };

        console.log('✅ [Fix] 修复已应用');
    }

    // 页面加载后应用修复
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyFix);
    } else {
        applyFix();
    }
})();
