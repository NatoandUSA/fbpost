document.addEventListener('DOMContentLoaded', () => {
    // ---- DOM References ----
    const statusBadge = document.getElementById('auth-status');
    const statusText = statusBadge.querySelector('.status-text');
    const authCard = document.getElementById('auth-card');
    const authBtn = document.getElementById('auth-btn');
    const postBtn = document.getElementById('post-btn');
    const targetLabel = document.getElementById('target-label');
    const targetInput = document.getElementById('target-input');
    const postContent = document.getElementById('post-content');
    const logOutput = document.getElementById('log-output');
    const logDot = document.getElementById('log-dot');
    const clearLogBtn = document.getElementById('clear-log');
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const toastContainer = document.getElementById('toast-container');

    // Input mode elements
    const manualSection = document.getElementById('manual-section');
    const csvSection = document.getElementById('csv-section');
    const csvUrlInput = document.getElementById('csv-url');
    const modeManualBtn = document.getElementById('mode-manual');
    const modeCsvBtn = document.getElementById('mode-csv');

    let currentMode = 'group';
    let isCsvMode = false;
    let isRunning = false;
    let logHasContent = false;

    // ---- Toast Notifications ----
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `<span>${type === 'success' ? '✅' : '❌'}</span><span>${message}</span>`;
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(16px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ---- Auth Status ----
    async function checkStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            if (data.authenticated) {
                statusText.textContent = 'Đã xác thực';
                statusBadge.className = 'status-badge authenticated';
                authCard.classList.add('hidden');
                postBtn.disabled = false;
            } else {
                statusText.textContent = 'Chưa xác thực';
                statusBadge.className = 'status-badge unauthenticated';
                authCard.classList.remove('hidden');
                postBtn.disabled = true;
            }
        } catch (e) {
            statusText.textContent = 'Server Offline';
            statusBadge.className = 'status-badge unauthenticated';
        }
    }

    // ---- Input Mode Toggle ----
    modeManualBtn.addEventListener('click', () => {
        isCsvMode = false;
        modeManualBtn.classList.add('active');
        modeCsvBtn.classList.remove('active');
        manualSection.classList.remove('hidden');
        csvSection.classList.add('hidden');
    });

    modeCsvBtn.addEventListener('click', () => {
        isCsvMode = true;
        modeCsvBtn.classList.add('active');
        modeManualBtn.classList.remove('active');
        csvSection.classList.remove('hidden');
        manualSection.classList.add('hidden');
    });

    // ---- Tabs ----
    const tabConfig = {
        group: {
            label: '🔗 Đường dẫn Group (mỗi link 1 dòng)',
            placeholder: 'https://facebook.com/groups/...'
        },
        page: {
            label: '🔗 Đường dẫn Page (mỗi link 1 dòng)',
            placeholder: 'https://facebook.com/your-page'
        },
        thread: {
            label: '🔗 Thread ID / Username (mỗi dòng 1 ID)',
            placeholder: 'markzuckerberg\njohndoe'
        }
    };

    document.querySelectorAll('.composer-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.composer-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentMode = tab.dataset.target;
            const config = tabConfig[currentMode];
            targetLabel.textContent = config.label;
            targetInput.placeholder = config.placeholder;
        });
    });

    // ---- Logging ----
    function clearLogEmpty() {
        if (!logHasContent) {
            logOutput.innerHTML = '';
            logHasContent = true;
        }
    }

    function appendLog(text) {
        clearLogEmpty();
        const line = document.createElement('div');
        line.className = 'log-line';

        // Color-code log lines
        const t = text.toLowerCase();
        if (t.includes('error') || t.includes('❌') || t.includes('fail')) {
            line.classList.add('error');
        } else if (t.includes('success') || t.includes('✅') || t.includes('completed') || t.includes('[batch')) {
            line.classList.add('success');
        } else if (t.includes('warning') || t.includes('anti-spam') || t.includes('waiting')) {
            line.classList.add('warning');
        } else if (t.includes('target') || t.includes('==========')) {
            line.classList.add('target');
        }

        line.textContent = text;
        logOutput.appendChild(line);
        logOutput.scrollTop = logOutput.scrollHeight;
    }

    clearLogBtn.addEventListener('click', () => {
        logOutput.innerHTML = `<div class="log-empty"><svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-7 12h-2v-2h2v2zm0-4h-2V6h2v4z"/></svg><span>Chưa có hoạt động nào</span></div>`;
        logHasContent = false;
        progressContainer.classList.add('hidden');
    });

    // ---- Set Running State ----
    function setRunning(running) {
        isRunning = running;
        postBtn.disabled = running;
        authBtn.disabled = running;
        logDot.className = running ? 'log-dot running' : 'log-dot idle';
        postBtn.textContent = running ? '⏳ Đang xử lý...' : 'Đăng bài ngay';
    }

    // ---- Run Command ----
    async function runCommand(command, payload = {}) {
        setRunning(true);
        appendLog(`▶ Bắt đầu lệnh: ${command}...`);

        try {
            const response = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command, ...payload })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                for (const l of lines) {
                    if (l.trim()) appendLog(l);
                }
            }

            appendLog('[✅ Hoàn tất]');
            showToast('Tác vụ hoàn tất thành công!');
        } catch (error) {
            appendLog(`❌ Lỗi: ${error.message}`);
            showToast('Đã xảy ra lỗi!', 'error');
        } finally {
            setRunning(false);
            checkStatus();
        }
    }

    // ---- Auth Button ----
    authBtn.addEventListener('click', () => {
        runCommand('auth');
    });

    // ---- Post Button ----
    postBtn.addEventListener('click', async () => {
        let tasks = [];

        if (isCsvMode) {
            const csvUrl = csvUrlInput.value.trim();
            if (!csvUrl) {
                showToast('Vui lòng nhập URL Google Sheets CSV!', 'error');
                return;
            }
            appendLog('📊 Đang tải dữ liệu từ Google Sheets...');
            try {
                const res = await fetch(csvUrl);
                const text = await res.text();
                const lines = text.split('\n');
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i].trim();
                    if (!line) continue;
                    const row = line.match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g);
                    if (!row || row.length < 2) continue;

                    let target = row[0].replace(/^"|"$/g, '').trim();
                    let content = row[1].replace(/^"|"$/g, '').trim();
                    let image = row.length > 2 ? row[2].replace(/^"|"$/g, '').trim() : null;

                    if (target && content) {
                        tasks.push({ target, content, image });
                    }
                }

                if (tasks.length === 0) {
                    appendLog('❌ Không tìm thấy dữ liệu hợp lệ trong CSV.');
                    showToast('Không tìm thấy dữ liệu hợp lệ!', 'error');
                    return;
                }
                appendLog(`📋 Đã tải ${tasks.length} mục tiêu từ CSV.`);
            } catch (err) {
                appendLog(`❌ Lỗi tải CSV: ${err.message}`);
                showToast('Không thể tải CSV!', 'error');
                return;
            }
        } else {
            const rawTargets = targetInput.value.trim();
            const content = postContent.value.trim();

            if (!rawTargets || !content) {
                showToast('Vui lòng điền đầy đủ mục tiêu và nội dung!', 'error');
                return;
            }

            const targets = rawTargets.split('\n').map(t => t.trim()).filter(t => t);
            tasks = targets.map(t => ({ target: t, content: content, image: null }));
        }

        // Show progress
        progressContainer.classList.remove('hidden');
        progressFill.style.width = '0%';

        runCommand(currentMode, { tasks });
    });

    // ---- Image button (placeholder behavior) ----
    const addImageBtn = document.getElementById('add-image-btn');
    if (addImageBtn) {
        addImageBtn.addEventListener('click', () => {
            showToast('Tính năng đính kèm ảnh - nhập đường dẫn ảnh trong nội dung CSV', 'success');
        });
    }

    // ---- Auto-resize textarea ----
    const composerTextarea = document.querySelector('.composer-textarea');
    if (composerTextarea) {
        composerTextarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    }

    // ---- Initial Check ----
    checkStatus();
});
