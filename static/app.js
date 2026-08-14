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
    const modeToggleContainer = document.getElementById('mode-toggle-container');
    const manualSection = document.getElementById('manual-section');
    const csvSection = document.getElementById('csv-section');
    const csvUrlInput = document.getElementById('csv-url');
    const modeManualBtn = document.getElementById('mode-manual');
    const modeCsvBtn = document.getElementById('mode-csv');

    // New feature sections
    const interactSection = document.getElementById('interact-section');
    const interactLimit = document.getElementById('interact-limit');
    const interactComments = document.getElementById('interact-comments');
    
    const scrapeSection = document.getElementById('scrape-section');
    const scrapeTarget = document.getElementById('scrape-target');
    const scrapeLimit = document.getElementById('scrape-limit');
    const scrapeResultsContainer = document.getElementById('scrape-results-container');
    const scrapeTableBody = document.getElementById('scrape-table-body');
    const downloadCsvBtn = document.getElementById('download-csv-btn');
    const addToPostBar = document.getElementById('add-to-post-bar');
    const composerDividerBar = document.getElementById('composer-divider-bar');

    // 2FA elements
    const tfaToggleBtn = document.getElementById('tfa-toggle-btn');
    const tfaPopover = document.getElementById('tfa-popover');
    const tfaSecretInput = document.getElementById('tfa-secret-input');
    const tfaGenerateBtn = document.getElementById('tfa-generate-btn');
    const tfaResult = document.getElementById('tfa-result');
    const tfaCode = document.getElementById('tfa-code');
    const tfaCopyBtn = document.getElementById('tfa-copy-btn');

    // Multi-Account elements
    const gpmApiInput = document.getElementById('gpm-api-input');
    const accountSelector = document.getElementById('account-selector');
    const addAccountToggleBtn = document.getElementById('add-account-toggle-btn');
    const addAccountForm = document.getElementById('add-account-form');
    const cancelAccountBtn = document.getElementById('cancel-account-btn');
    const saveAccountBtn = document.getElementById('save-account-btn');
    
    const accName = document.getElementById('acc-name');
    const accType = document.getElementById('acc-type');
    const accProfileId = document.getElementById('acc-profile-id');
    const accProxy = document.getElementById('acc-proxy');
    const accountsTableBody = document.getElementById('accounts-table-body');

    let currentMode = 'group'; // group, page, thread, interact, scrape
    let isCsvMode = false;
    let isRunning = false;
    let logHasContent = false;
    let currentScrapedData = [];
    let accountsList = [];

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

    // ---- Load and Render Accounts ----
    async function loadAccounts() {
        try {
            const res = await fetch('/api/accounts');
            accountsList = await res.json();
            
            // Populate account selector
            const selectedVal = accountSelector.value;
            accountSelector.innerHTML = '<option value="">-- Mặc định (Sử dụng state.json toàn cục) --</option>';
            accountsList.forEach(acc => {
                const opt = document.createElement('option');
                opt.value = acc.id;
                opt.textContent = `${acc.name} (${acc.type === 'gpm' ? 'GPM' : 'Local'})`;
                accountSelector.appendChild(opt);
            });
            // Restore selection if existed
            if (selectedVal) accountSelector.value = selectedVal;
            
            // Render accounts table
            accountsTableBody.innerHTML = '';
            if (accountsList.length === 0) {
                accountsTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--fb-text-secondary);">Chưa cấu hình tài khoản nào. Hãy nhấp nút "Thêm Profile" bên trên.</td></tr>';
                return;
            }
            
            accountsList.forEach(acc => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${acc.name}</strong></td>
                    <td><span class="badge badge-${acc.type}">${acc.type === 'gpm' ? 'GPM Login' : 'Cục bộ (Local)'}</span></td>
                    <td><code>${acc.profile_path_or_id}</code></td>
                    <td><span style="color: var(--fb-text-secondary);">${acc.proxy || 'Trực tiếp (Không dán)'}</span></td>
                    <td class="acc-action-btns">
                        <button class="btn btn-secondary btn-sm btn-auth-acc" data-id="${acc.id}">🔑 Xác thực</button>
                        <button class="btn btn-danger btn-sm btn-delete-acc" data-id="${acc.id}">❌ Xóa</button>
                    </td>
                `;
                accountsTableBody.appendChild(tr);
            });

            // Bind actions
            document.querySelectorAll('.btn-auth-acc').forEach(btn => {
                btn.addEventListener('click', () => {
                    const id = btn.dataset.id;
                    runCommand('auth', { accountId: id });
                });
            });

            document.querySelectorAll('.btn-delete-acc').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = btn.dataset.id;
                    if (confirm('Bạn chắc chắn muốn xóa tài khoản này khỏi danh sách?')) {
                        try {
                            const response = await fetch(`/api/accounts/${id}`, { method: 'DELETE' });
                            const result = await response.json();
                            if (result.success) {
                                showToast('Đã xóa tài khoản thành công!');
                                loadAccounts();
                            } else {
                                showToast(result.error || 'Lỗi khi xóa', 'error');
                            }
                        } catch (err) {
                            showToast('Lỗi kết nối', 'error');
                        }
                    }
                });
            });

        } catch (e) {
            console.error("Lỗi khi tải tài khoản:", e);
        }
    }

    // Toggle add form
    addAccountToggleBtn.addEventListener('click', () => {
        addAccountForm.classList.toggle('hidden');
    });

    cancelAccountBtn.addEventListener('click', () => {
        addAccountForm.classList.add('hidden');
        clearAddForm();
    });

    function clearAddForm() {
        accName.value = '';
        accProfileId.value = '';
        accProxy.value = '';
        accType.value = 'local';
    }

    // Save account
    saveAccountBtn.addEventListener('click', async () => {
        const name = accName.value.trim();
        const type = accType.value;
        const profileId = accProfileId.value.trim();
        const proxy = accProxy.value.trim();

        if (!name) {
            showToast('Vui lòng điền tên tài khoản gợi nhớ!', 'error');
            return;
        }

        try {
            const res = await fetch('/api/accounts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, type, profile_path_or_id: profileId, proxy })
            });
            const data = await res.json();
            if (data.error) {
                showToast(data.error, 'error');
            } else {
                showToast('Đã thêm tài khoản thành công!');
                addAccountForm.classList.add('hidden');
                clearAddForm();
                loadAccounts();
            }
        } catch (err) {
            showToast('Lỗi máy chủ', 'error');
        }
    });

    // ---- 2FA Code Generator ----
    tfaToggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        tfaPopover.classList.toggle('hidden');
    });

    document.addEventListener('click', (e) => {
        if (!tfaPopover.contains(e.target) && e.target !== tfaToggleBtn) {
            tfaPopover.classList.add('hidden');
        }
    });

    tfaGenerateBtn.addEventListener('click', async () => {
        const secret = tfaSecretInput.value.trim();
        if (!secret) {
            showToast('Vui lòng nhập Secret Key!', 'error');
            return;
        }
        tfaGenerateBtn.disabled = true;
        tfaGenerateBtn.textContent = 'Đang tạo...';
        try {
            const res = await fetch('/api/2fa', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ secret })
            });
            const data = await res.json();
            if (data.token) {
                tfaCode.textContent = data.token;
                tfaResult.classList.remove('hidden');
                showToast('Đã tạo mã OTP thành công!');
            } else {
                showToast(data.error || 'Lỗi không xác định', 'error');
            }
        } catch (err) {
            showToast('Không thể kết nối đến máy chủ', 'error');
        } finally {
            tfaGenerateBtn.disabled = false;
            tfaGenerateBtn.textContent = 'Tạo mã';
        }
    });

    tfaCopyBtn.addEventListener('click', () => {
        const code = tfaCode.textContent;
        if (code && code !== '------') {
            navigator.clipboard.writeText(code);
            showToast('Đã sao chép mã 2FA!');
        }
    });

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

    // ---- Tabs Switcher ----
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
            
            // Hide all specialized sections first
            manualSection.classList.add('hidden');
            csvSection.classList.add('hidden');
            interactSection.classList.add('hidden');
            scrapeSection.classList.add('hidden');
            modeToggleContainer.classList.add('hidden');
            addToPostBar.classList.add('hidden');
            composerDividerBar.classList.add('hidden');

            if (currentMode === 'interact') {
                interactSection.classList.remove('hidden');
                postBtn.textContent = 'Bắt đầu tương tác';
            } else if (currentMode === 'scrape') {
                scrapeSection.classList.remove('hidden');
                postBtn.textContent = 'Bắt đầu quét';
            } else {
                // Standard modes (Group, Page, Thread)
                modeToggleContainer.classList.remove('hidden');
                addToPostBar.classList.remove('hidden');
                composerDividerBar.classList.remove('hidden');
                postBtn.textContent = 'Đăng bài ngay';
                
                if (isCsvMode) {
                    csvSection.classList.remove('hidden');
                } else {
                    manualSection.classList.remove('hidden');
                }

                const config = tabConfig[currentMode];
                targetLabel.textContent = config.label;
                targetInput.placeholder = config.placeholder;
            }
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
        } else if (t.includes('success') || t.includes('✅') || t.includes('completed') || t.includes('[batch') || t.includes('hoàn tất')) {
            line.classList.add('success');
        } else if (t.includes('warning') || t.includes('anti-spam') || t.includes('waiting') || t.includes('chờ')) {
            line.classList.add('warning');
        } else if (t.includes('target') || t.includes('==========') || t.includes('bắt đầu')) {
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
        
        if (running) {
            postBtn.textContent = '⏳ Đang xử lý...';
        } else {
            if (currentMode === 'interact') {
                postBtn.textContent = 'Bắt đầu tương tác';
            } else if (currentMode === 'scrape') {
                postBtn.textContent = 'Bắt đầu quét';
            } else {
                postBtn.textContent = 'Đăng bài ngay';
            }
        }
    }

    // ---- Scrape Table Render ----
    function renderScrapedTable(data) {
        currentScrapedData = data;
        scrapeTableBody.innerHTML = '';
        if (data.length === 0) {
            scrapeTableBody.innerHTML = '<tr><td colspan="4" style="text-align: center;">Không có dữ liệu nào được tìm thấy</td></tr>';
            return;
        }
        
        data.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${item.name}</strong></td>
                <td><a href="${item.profile}" target="_blank">${item.profile}</a></td>
                <td>${item.comment}</td>
                <td style="color: ${item.phone !== 'Không có' ? '#1877F2' : 'inherit'}; font-weight: ${item.phone !== 'Không có' ? 'bold' : 'normal'};">${item.phone}</td>
            `;
            scrapeTableBody.appendChild(row);
        });
        scrapeResultsContainer.classList.remove('hidden');
    }

    // Download CSV
    downloadCsvBtn.addEventListener('click', () => {
        if (currentScrapedData.length === 0) return;
        
        let csvContent = "data:text/csv;charset=utf-8,\uFEFF"; // Add BOM for Excel UTF-8 support
        csvContent += "Họ tên,Profile URL,Nội dung bình luận,Số điện thoại\n";
        
        currentScrapedData.forEach(row => {
            const name = `"${row.name.replace(/"/g, '""')}"`;
            const profile = `"${row.profile.replace(/"/g, '""')}"`;
            const comment = `"${row.comment.replace(/"/g, '""')}"`;
            const phone = `"${row.phone.replace(/"/g, '""')}"`;
            csvContent += `${name},${profile},${comment},${phone}\n`;
        });
        
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `FB_Scraped_Comments_${new Date().toISOString().slice(0,10)}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });

    // ---- Run Command ----
    async function runCommand(command, payload = {}) {
        setRunning(true);
        progressContainer.classList.remove('hidden');
        progressFill.style.width = '20%';
        appendLog(`▶ Bắt đầu lệnh: ${command}...`);

        // Add account attributes to payload if selected
        const accId = accountSelector.value;
        const gpmApi = gpmApiInput.value.trim();
        
        if (accId) {
            payload.accountId = accId;
            payload.gpmApiUrl = gpmApi;
        }

        try {
            const response = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command, ...payload })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            progressFill.style.width = '60%';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                for (const l of lines) {
                    const cleanLine = l.trim();
                    if (cleanLine.startsWith('JSON_DATA:')) {
                        const jsonStr = cleanLine.substring('JSON_DATA:'.length);
                        try {
                            const data = JSON.parse(jsonStr);
                            renderScrapedTable(data);
                        } catch (err) {
                            appendLog(`Lỗi xử lý bảng dữ liệu: ${err.message}`);
                        }
                    } else if (cleanLine) {
                        appendLog(cleanLine);
                    }
                }
            }

            progressFill.style.width = '100%';
            appendLog('[✅ Hoàn tất]');
            showToast('Tác vụ hoàn tất thành công!');
        } catch (error) {
            appendLog(`❌ Lỗi: ${error.message}`);
            showToast('Đã xảy ra lỗi!', 'error');
        } finally {
            setRunning(false);
            checkStatus();
            setTimeout(() => {
                progressContainer.classList.add('hidden');
            }, 1000);
        }
    }

    // ---- Auth Button ----
    authBtn.addEventListener('click', () => {
        runCommand('auth');
    });

    // ---- Post Button ----
    postBtn.addEventListener('click', async () => {
        if (currentMode === 'interact') {
            const limit = parseInt(interactLimit.value) || 5;
            const comments = interactComments.value.trim();
            runCommand('interact', { limit, comments });
        } else if (currentMode === 'scrape') {
            const target = scrapeTarget.value.trim();
            const limit = parseInt(scrapeLimit.value) || 50;
            if (!target) {
                showToast('Vui lòng nhập đường dẫn bài viết cần quét!', 'error');
                return;
            }
            scrapeResultsContainer.classList.add('hidden');
            runCommand('scrape', { target, limit });
        } else {
            // Standard posting modes
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
                targets.forEach(t => {
                    tasks.push({ target: t, content: content, image: null });
                });
            }

            runCommand(currentMode, { tasks });
        }
    });

    // ---- Image button (placeholder behavior) ----
    const addImageBtn = document.getElementById('add-image-btn');
    if (addImageBtn) {
        addImageBtn.addEventListener('click', () => {
            showToast('Đã kích hoạt chế độ đăng ảnh! Hãy chỉ định đường dẫn hình ảnh trong CSV.', 'success');
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
    loadAccounts();
});
