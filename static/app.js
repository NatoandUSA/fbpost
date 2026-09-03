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
    const commentSection = document.getElementById('comment-section');
    const commentTargets = document.getElementById('comment-targets');
    const commentContent = document.getElementById('comment-content');
    const commentLikePost = document.getElementById('comment-like-post');
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
    const accountSelectorContainer = document.getElementById('account-selector-container');
    const addAccountToggleBtn = document.getElementById('add-account-toggle-btn');
    const addAccountForm = document.getElementById('add-account-form');
    const cancelAccountBtn = document.getElementById('cancel-account-btn');
    const saveAccountBtn = document.getElementById('save-account-btn');
    
    const accName = document.getElementById('acc-name');
    const accType = document.getElementById('acc-type');
    const accProfileId = document.getElementById('acc-profile-id');
    const accProxy = document.getElementById('acc-proxy');
    const accountsTableBody = document.getElementById('accounts-table-body');

    // Diverse Posting Options & Saved Links Card
    const diversePostSettingsBar = document.getElementById('diverse-post-settings-bar');
    const postFeelingOpt = document.getElementById('post-feeling-opt');
    const postCheckinOpt = document.getElementById('post-checkin-opt');
    const postedLinksCard = document.getElementById('posted-links-card');
    const postedLinksList = document.getElementById('posted-links-list');
    const clearLinksBtn = document.getElementById('clear-links-btn');
    const preflightBtn = document.getElementById('preflight-btn');
    const queuePostBtn = document.getElementById('queue-post-btn');
    const preflightStatus = document.getElementById('preflight-status');
    const approvalQueueList = document.getElementById('approval-queue-list');
    const refreshQueueBtn = document.getElementById('refresh-queue-btn');
    const campaignName = document.getElementById('campaign-name');
    const campaignBrand = document.getElementById('campaign-brand');
    const campaignTarget = document.getElementById('campaign-target');
    const campaignSelector = document.getElementById('campaign-selector');
    const createCampaignBtn = document.getElementById('create-campaign-btn');
    const refreshCampaignsBtn = document.getElementById('refresh-campaigns-btn');
    const campaignReportList = document.getElementById('campaign-report-list');
    let campaignCache = [];

    // Image Upload Elements
    const addImageBtn = document.getElementById('add-image-btn');
    const postImageFile = document.getElementById('post-image-file');
    const imageUploadPreview = document.getElementById('image-upload-preview');
    const imagePreviewName = document.getElementById('image-preview-name');
    const removeImageBtn = document.getElementById('remove-image-btn');

    // Content Hub Section
    const contentHubSection = document.getElementById('content-hub-section');
    const schedSection = document.getElementById('page-scheduler-section');

    // Visual Progress Dashboard Elements
    const visualProgressDashboard = document.getElementById('visual-progress-dashboard');
    const activeTaskName = document.getElementById('active-task-name');
    const activeTargetIndex = document.getElementById('active-target-index');
    const activeTargetUrl = document.getElementById('active-target-url');
    const statusIndicatorDot = document.getElementById('status-indicator-dot');
    const statusDetailText = document.getElementById('status-detail-text');
    const cooldownTimerCard = document.getElementById('cooldown-timer-card');
    const cooldownTimeLeft = document.getElementById('cooldown-time-left');
    const cooldownProgressFill = document.getElementById('cooldown-progress-fill');
    const targetStepperList = document.getElementById('target-stepper-list');
    let cooldownInterval = null;

    let currentMode = 'group'; // group, page, thread, interact, scrape, content-hub
    let isCsvMode = false;
    let isRunning = false;
    let logHasContent = false;
    let currentScrapedData = [];
    let accountsList = [];
    let savedPostLinks = [];
    let selectedImagePath = null; // Stores uploaded absolute image path

    // ---- Toast Notifications ----
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icon = document.createElement('span');
        icon.textContent = type === 'success' ? '✅' : '❌';
        const text = document.createElement('span');
        text.textContent = message;
        toast.append(icon, text);
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(16px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ---- Build & Version Info ----
    async function loadBuildInfo() {
        try {
            const res = await fetch('/api/app-info');
            const data = await res.json();
            const verText = data.version ? `v${data.version}` : 'v5.5.0';
            const buildText = data.built_at ? `Build: ${data.built_at}` : 'Build: 2026-09-03 23:05';
            
            const sidebarVer = document.getElementById('sidebar-version-badge');
            const sidebarBuild = document.getElementById('sidebar-build-time');
            const headerVer = document.getElementById('header-version-text');
            const headerBuild = document.getElementById('header-build-time-text');
            const buildInfoEl = document.getElementById('build-info');
            
            if (sidebarVer) sidebarVer.textContent = verText;
            if (sidebarBuild) sidebarBuild.textContent = buildText;
            if (headerVer) headerVer.textContent = verText;
            if (headerBuild) headerBuild.textContent = buildText;
            if (buildInfoEl) buildInfoEl.textContent = `UI ${verText} · Server ${verText} (${buildText})`;
        } catch (e) {
            console.warn('Không thể đọc thông tin build:', e);
        }
    }

    // ---- Auth Status ----
    async function checkStatus() {
        loadBuildInfo();
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

    // ---- Saved Links Handling ----
    function loadSavedLinks() {
        try {
            const links = localStorage.getItem('fb_posted_links');
            savedPostLinks = links ? JSON.parse(links) : [];
            renderSavedLinks();
        } catch (e) {
            savedPostLinks = [];
        }
    }

    function currentDraft() {
        const selectedCampaign = campaignCache.find(campaign => campaign.id === campaignSelector.value);
        return {
            target: targetInput.value.split('\n').map(value => value.trim()).find(Boolean) || selectedCampaign?.target || '',
            content: postContent.value.trim(),
            campaign_id: campaignSelector.value,
        };
    }

    function renderCampaigns(campaigns) {
        campaignCache = campaigns;
        const selected = campaignSelector.value;
        campaignSelector.innerHTML = '<option value="">Không gắn chiến dịch</option>';
        campaignReportList.innerHTML = '';
        if (!campaigns.length) {
            campaignReportList.innerHTML = '<span class="empty">Chưa có chiến dịch.</span>';
            return;
        }
        campaigns.forEach(campaign => {
            const option = document.createElement('option');
            option.value = campaign.id;
            option.textContent = `${campaign.name}${campaign.state === 'paused' ? ' (tạm dừng)' : ''}`;
            campaignSelector.appendChild(option);

            const row = document.createElement('div');
            row.className = 'posted-link-item';
            const body = document.createElement('div');
            const title = document.createElement('strong');
            title.textContent = `${campaign.state === 'active' ? '🟢' : '⏸'} ${campaign.name}`;
            const meta = document.createElement('div');
            meta.className = 'text-small';
            const summary = campaign.summary || {};
            meta.textContent = `${campaign.brand || 'Chưa gắn thương hiệu'} · ${summary.total || 0} bài · Nháp ${summary.draft || 0} · Đã duyệt ${summary.approved || 0}`;
            body.append(title, meta);
            const toggle = document.createElement('button');
            toggle.className = 'btn btn-secondary btn-sm';
            toggle.textContent = campaign.state === 'active' ? 'Tạm dừng' : 'Kích hoạt';
            toggle.addEventListener('click', () => toggleCampaign(campaign.id));
            row.append(body, toggle);
            if (campaign.state === 'active' && (summary.draft || 0) > 0) {
                const approveAll = document.createElement('button');
                approveAll.className = 'btn btn-primary btn-sm';
                approveAll.textContent = `Duyệt ${summary.draft}`;
                approveAll.addEventListener('click', () => approveCampaignDrafts(campaign.id));
                row.appendChild(approveAll);
            }
            campaignReportList.appendChild(row);
        });
        campaignSelector.value = selected;
    }

    async function loadCampaigns() {
        try {
            const response = await fetch('/api/campaigns');
            renderCampaigns(await response.json());
        } catch (_) {
            campaignReportList.textContent = 'Không thể tải chiến dịch.';
        }
    }

    async function toggleCampaign(id) {
        const response = await fetch(`/api/campaigns/${id}/toggle`, { method: 'POST' });
        const data = await response.json();
        if (!response.ok) showToast(data.error || 'Không thể cập nhật chiến dịch.', 'error');
        else { showToast(data.state === 'active' ? 'Đã kích hoạt chiến dịch.' : 'Đã tạm dừng chiến dịch.'); loadCampaigns(); }
    }

    async function approveCampaignDrafts(id) {
        const response = await fetch(`/api/campaigns/${id}/approve-drafts`, { method: 'POST' });
        const data = await response.json();
        if (!response.ok) showToast(data.error || 'Không thể duyệt các bài nháp.', 'error');
        else { showToast(`Đã duyệt ${data.approved} bài trong chiến dịch.`); loadCampaigns(); loadQueue(); }
    }

    createCampaignBtn.addEventListener('click', async () => {
        const payload = { name: campaignName.value.trim(), brand: campaignBrand.value.trim(), target: campaignTarget.value.trim() };
        const response = await fetch('/api/campaigns', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
        const data = await response.json();
        if (!response.ok) return showToast(data.error || 'Không thể tạo chiến dịch.', 'error');
        campaignName.value = '';
        campaignBrand.value = '';
        campaignTarget.value = '';
        showToast('Đã tạo chiến dịch.');
        await loadCampaigns();
        campaignSelector.value = data.id;
    });

    refreshCampaignsBtn.addEventListener('click', loadCampaigns);

    function renderQueue(items) {
        approvalQueueList.innerHTML = '';
        if (!items.length) {
            approvalQueueList.innerHTML = '<span class="empty">Chưa có bài nào trong hàng đợi.</span>';
            return;
        }
        items.forEach(item => {
            const row = document.createElement('div');
            row.className = 'posted-link-item';
            const text = document.createElement('div');
            const title = document.createElement('strong');
            title.textContent = `${item.state === 'approved' ? '✅ Đã duyệt' : item.state === 'cancelled' ? '⏹ Đã hủy' : '📝 Nháp'} · ${item.target}`;
            const preview = document.createElement('div');
            preview.className = 'text-small';
            preview.textContent = item.content.slice(0, 100);
            text.append(title, preview);
            row.appendChild(text);
            if (item.state === 'draft') {
                const approve = document.createElement('button');
                approve.className = 'btn btn-primary btn-sm';
                approve.textContent = 'Duyệt';
                approve.addEventListener('click', () => updateQueueItem(item.id, 'approve'));
                row.appendChild(approve);
            }
            if (item.state !== 'approved') {
                const cancel = document.createElement('button');
                cancel.className = 'btn btn-ghost btn-sm';
                cancel.textContent = 'Hủy';
                cancel.addEventListener('click', () => updateQueueItem(item.id, 'cancel'));
                row.appendChild(cancel);
            }
            approvalQueueList.appendChild(row);
        });
    }

    async function loadQueue() {
        try {
            const response = await fetch('/api/queue');
            renderQueue(await response.json());
        } catch (_) {
            approvalQueueList.textContent = 'Không thể tải hàng đợi.';
        }
    }

    async function updateQueueItem(id, action) {
        const response = await fetch(`/api/queue/${id}/${action}`, { method: 'POST' });
        const data = await response.json();
        if (!response.ok) showToast(data.error || 'Không thể cập nhật hàng đợi.', 'error');
        else { showToast(action === 'approve' ? 'Đã duyệt bài đăng.' : 'Đã hủy bài đăng.'); loadQueue(); }
    }

    preflightBtn.addEventListener('click', async () => {
        const draft = currentDraft();
        const response = await fetch('/api/preflight', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(draft) });
        const data = await response.json();
        preflightStatus.textContent = data.ready ? '✅ Sẵn sàng duyệt' : `⚠️ ${data.issues[0] || 'Cần kiểm tra'}`;
        preflightStatus.className = `sched-badge ${data.ready ? 'badge-success' : 'badge-error'}`;
    });

    queuePostBtn.addEventListener('click', async () => {
        const response = await fetch('/api/queue', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(currentDraft()) });
        const data = await response.json();
        if (!response.ok) return showToast(data.error || 'Không thể tạo hàng đợi.', 'error');
        showToast('Đã thêm bài vào hàng đợi để duyệt.');
        loadQueue();
    });

    refreshQueueBtn.addEventListener('click', loadQueue);

    function saveLink(url) {
        if (!savedPostLinks.includes(url)) {
            savedPostLinks.unshift(url);
            localStorage.setItem('fb_posted_links', JSON.stringify(savedPostLinks));
            renderSavedLinks();
        }
    }

    function renderSavedLinks() {
        postedLinksList.innerHTML = '';
        if (savedPostLinks.length === 0) {
            postedLinksCard.classList.add('hidden');
            return;
        }
        
        savedPostLinks.forEach(link => {
            let url;
            try {
                url = new URL(link, window.location.origin);
            } catch (_) {
                return;
            }
            const item = document.createElement('div');
            item.className = 'posted-link-item';
            if (!['http:', 'https:'].includes(url.protocol)) return;
            const label = document.createElement('span');
            label.className = 'posted-link-url';
            label.title = link;
            label.textContent = link;
            const anchor = document.createElement('a');
            anchor.href = url.href;
            anchor.target = '_blank';
            anchor.rel = 'noopener noreferrer';
            anchor.className = 'btn btn-secondary btn-sm';
            anchor.textContent = '🔗 Mở link';
            item.append(label, anchor);
            postedLinksList.appendChild(item);
        });
        postedLinksCard.classList.remove('hidden');
    }

    clearLinksBtn.addEventListener('click', () => {
        savedPostLinks = [];
        localStorage.setItem('fb_posted_links', JSON.stringify(savedPostLinks));
        renderSavedLinks();
        showToast('Đã xóa danh sách liên kết!');
    });

    // ---- Image Upload Handling ----
    addImageBtn.addEventListener('click', () => {
        postImageFile.click();
    });

    postImageFile.addEventListener('change', async () => {
        const file = postImageFile.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('image', file);

        showToast('Đang tải ảnh lên...', 'info');
        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.filepath) {
                selectedImagePath = data.filepath;
                imagePreviewName.textContent = `📎 ${file.name}`;
                imageUploadPreview.classList.remove('hidden');
                showToast('Đã đính kèm ảnh thành công!');
            } else {
                showToast(data.error || 'Lỗi tải ảnh lên', 'error');
            }
        } catch (err) {
            showToast('Lỗi kết nối máy chủ', 'error');
        }
    });

    removeImageBtn.addEventListener('click', () => {
        selectedImagePath = null;
        postImageFile.value = '';
        imageUploadPreview.classList.add('hidden');
        showToast('Đã hủy đính kèm ảnh.');
    });

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
            if (selectedVal) accountSelector.value = selectedVal;
            
            // Render accounts table
            accountsTableBody.innerHTML = '';
            if (accountsList.length === 0) {
                accountsTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--fb-text-secondary);">Chưa cấu hình tài khoản nào. Hãy nhấp nút "Thêm Profile" bên trên.</td></tr>';
                return;
            }
            
            accountsList.forEach(acc => {
                const tr = document.createElement('tr');
                const makeCell = (text, tag = 'span') => {
                    const cell = document.createElement('td');
                    const value = document.createElement(tag);
                    value.textContent = text;
                    cell.appendChild(value);
                    return cell;
                };
                const nameCell = makeCell(acc.name, 'strong');
                const typeCell = makeCell(acc.type === 'gpm' ? 'GPM Login' : 'Cục bộ (Local)');
                typeCell.firstChild.className = `badge badge-${acc.type}`;
                const profileCell = makeCell(acc.profile_path_or_id, 'code');
                const proxyCell = makeCell(acc.proxy || 'Trực tiếp (Không dùng)');
                const actions = document.createElement('td');
                actions.className = 'acc-action-btns';
                for (const [label, className] of [['🔑 Xác thực', 'btn-auth-acc'], ['❌ Xóa', 'btn-delete-acc']]) {
                    const button = document.createElement('button');
                    button.className = `btn btn-${className === 'btn-delete-acc' ? 'danger' : 'secondary'} btn-sm ${className}`;
                    button.dataset.id = acc.id;
                    button.textContent = label;
                    actions.appendChild(button);
                }
                tr.append(nameCell, typeCell, profileCell, proxyCell, actions);
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

    // Workspace title map for each mode
    const workspaceTitleMap = {
        group: 'Đăng Bài Nhóm (Group)',
        page: 'Đăng Bài Trang (Page)',
        thread: 'Gửi Tin Nhắn Cá Nhân (Thread)',
        interact: 'Nuôi Nick — Tương tác Newsfeed',
        scrape: 'Quét & Lọc Bình Luận',
        'content-hub': 'Content Hub — Tạo Nội Dung AI',
        'page-scheduler': 'Page Scheduler — Lên Lịch Đăng Bài',
        comment: 'Bình luận bài viết theo Link (Group & Fanpage)'
    };

    const workspaceTitleEl = document.getElementById('active-workspace-title');

    document.querySelectorAll('.composer-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.composer-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentMode = tab.dataset.target;

            // Update workspace title
            if (workspaceTitleEl) {
                workspaceTitleEl.textContent = workspaceTitleMap[currentMode] || 'Tác vụ';
            }
            
            // Hide all specialized sections first
            manualSection.classList.add('hidden');
            csvSection.classList.add('hidden');
            interactSection.classList.add('hidden');
            scrapeSection.classList.add('hidden');
            contentHubSection.classList.add('hidden');
            schedSection.classList.add('hidden');
            commentSection.classList.add('hidden');
            modeToggleContainer.classList.add('hidden');
            addToPostBar.classList.add('hidden');
            composerDividerBar.classList.add('hidden');
            diversePostSettingsBar.classList.add('hidden');
            postBtn.classList.add('hidden');
            accountSelectorContainer.classList.remove('hidden');

            if (currentMode === 'interact') {
                interactSection.classList.remove('hidden');
                postBtn.classList.remove('hidden');
                postBtn.textContent = 'Bắt đầu tương tác Newsfeed';
            } else if (currentMode === 'scrape') {
                scrapeSection.classList.remove('hidden');
                postBtn.classList.remove('hidden');
                postBtn.textContent = 'Bắt đầu quét bình luận';
            } else if (currentMode === 'content-hub') {
                contentHubSection.classList.remove('hidden');
                accountSelectorContainer.classList.add('hidden');
            } else if (currentMode === 'page-scheduler') {
                schedSection.classList.remove('hidden');
                accountSelectorContainer.classList.add('hidden');
                loadSchedConfig();
                loadSchedStatus();
            } else if (currentMode === 'comment') {
                commentSection.classList.remove('hidden');
                postBtn.classList.remove('hidden');
                postBtn.textContent = 'Bắt đầu bình luận bài viết';
            } else {
                // Standard modes (Group, Page, Thread)
                modeToggleContainer.classList.remove('hidden');
                addToPostBar.classList.remove('hidden');
                composerDividerBar.classList.remove('hidden');
                postBtn.classList.remove('hidden');
                postBtn.textContent = 'Đăng bài ngay';
                
                // Show diverse settings for post methods only
                if (currentMode === 'group' || currentMode === 'page') {
                    diversePostSettingsBar.classList.remove('hidden');
                }
                
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
        } else if (t.includes('success') || t.includes('✅') || t.includes('completed') || t.includes('[batch') || t.includes('hoàn tất') || t.includes('posted_link:')) {
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
            const nameCell = document.createElement('td');
            const name = document.createElement('strong');
            name.textContent = item.name || '';
            nameCell.appendChild(name);
            const profileCell = document.createElement('td');
            try {
                const profileUrl = new URL(item.profile);
                if (['http:', 'https:'].includes(profileUrl.protocol)) {
                    const link = document.createElement('a');
                    link.href = profileUrl.href;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    link.textContent = item.profile;
                    profileCell.appendChild(link);
                } else {
                    profileCell.textContent = item.profile || '';
                }
            } catch (_) {
                profileCell.textContent = item.profile || '';
            }
            const commentCell = document.createElement('td');
            commentCell.textContent = item.comment || '';
            const phoneCell = document.createElement('td');
            phoneCell.textContent = item.phone || '';
            if (item.phone !== 'Không có') {
                phoneCell.style.color = '#1877F2';
                phoneCell.style.fontWeight = 'bold';
            }
            row.append(nameCell, profileCell, commentCell, phoneCell);
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

    // ---- Visual Progress Helper ----
    function initProgressDashboard(taskName, targets) {
        activeTaskName.textContent = taskName;
        activeTargetIndex.textContent = `0/${targets.length}`;
        activeTargetUrl.textContent = 'Đang khởi chạy...';
        statusIndicatorDot.className = 'status-indicator-dot active';
        statusDetailText.textContent = 'Đang thiết lập phiên làm việc...';
        cooldownTimerCard.classList.add('hidden');
        
        if (cooldownInterval) {
            clearInterval(cooldownInterval);
            cooldownInterval = null;
        }
        
        targetStepperList.innerHTML = '';
        targets.forEach((t, idx) => {
            const item = document.createElement('div');
            item.className = 'stepper-item pending';
            item.id = `stepper-item-${idx}`;
            
            let displayTarget = t;
            if (t.startsWith('http')) {
                displayTarget = t.split('/').pop() || t;
                if (!displayTarget && t.includes('groups/')) {
                    displayTarget = t.split('groups/')[1].split('/')[0];
                }
            }
            if (displayTarget.length > 20) displayTarget = displayTarget.slice(0, 17) + '...';
            
            item.innerHTML = `<span class="stepper-icon"></span><span>${displayTarget}</span>`;
            targetStepperList.appendChild(item);
        });
        
        visualProgressDashboard.classList.remove('hidden');
    }

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

        // Add Feeling and Check-in parameters if checking Group or Page commands
        if (command === 'group' || command === 'page') {
            payload.feeling = postFeelingOpt.checked;
            payload.checkin = postCheckinOpt.checked;
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
                    } else if (cleanLine.startsWith('POSTED_LINK:')) {
                        const postUrl = cleanLine.substring('POSTED_LINK:'.length).trim();
                        if (postUrl && postUrl.startsWith('http')) {
                            saveLink(postUrl);
                            appendLog(`🔗 Đã lấy được link bài đăng: ${postUrl}`);
                        }
                    } else {
                        if (cleanLine) {
                            appendLog(cleanLine);
                            
                            // Visual Dashboard Real-time Parsing
                            const targetMatch = cleanLine.match(/========== \[Target (\d+)\/(\d+)\] ==========/);
                            if (targetMatch) {
                                const index = parseInt(targetMatch[1]);
                                const total = parseInt(targetMatch[2]);
                                activeTargetIndex.textContent = `${index}/${total}`;
                                
                                for (let idx = 0; idx < total; idx++) {
                                    const item = document.getElementById(`stepper-item-${idx}`);
                                    if (item) {
                                        if (idx < index - 1) {
                                            item.className = 'stepper-item success';
                                        } else if (idx === index - 1) {
                                            item.className = 'stepper-item active';
                                            item.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
                                        } else {
                                            item.className = 'stepper-item pending';
                                        }
                                    }
                                }
                            }

                            const postingMatch = cleanLine.match(/Posting to:\s*(.*)/);
                            if (postingMatch) {
                                const target = postingMatch[1].trim();
                                activeTargetUrl.textContent = target;
                                statusIndicatorDot.className = 'status-indicator-dot active';
                                statusDetailText.textContent = 'Đang truy cập trang mục tiêu...';
                            }

                            // Stepper detail feedback
                            if (cleanLine.includes('Looking for')) {
                                statusDetailText.textContent = 'Đang tìm kiếm ô nhập bài viết...';
                            } else if (cleanLine.includes('Attaching image')) {
                                statusDetailText.textContent = '🖼️ Đang tải ảnh lên bài viết...';
                            } else if (cleanLine.includes('Typing content') || cleanLine.includes('Typing...')) {
                                statusDetailText.textContent = '✍️ Đang gõ nội dung bài đăng...';
                            } else if (cleanLine.includes("Clicking 'Post'")) {
                                statusDetailText.textContent = '🚀 Đang nhấn nút đăng bài viết...';
                            } else if (cleanLine.includes('Successfully posted') || cleanLine.includes('posted successfully')) {
                                statusDetailText.textContent = '✅ Đăng bài lên Facebook thành công!';
                                const activeItem = document.querySelector('.stepper-item.active');
                                if (activeItem) activeItem.className = 'stepper-item success';
                            } else if (cleanLine.toLowerCase().includes('error') || cleanLine.toLowerCase().includes('fail')) {
                                statusDetailText.textContent = '❌ Lỗi: ' + cleanLine;
                                const activeItem = document.querySelector('.stepper-item.active');
                                if (activeItem) activeItem.className = 'stepper-item error';
                            }

                            // Anti-Spam Cooldown timer
                            const delayMatch = cleanLine.match(/\[Anti-Spam\] Waiting (\d+) seconds/);
                            if (delayMatch) {
                                let timeLeft = parseInt(delayMatch[1]);
                                const totalDelay = timeLeft;
                                statusIndicatorDot.className = 'status-indicator-dot wait';
                                statusDetailText.textContent = '⏳ Giãn cách nghỉ tránh spam để bảo vệ tài khoản...';
                                
                                cooldownTimeLeft.textContent = `${timeLeft}s`;
                                cooldownTimerCard.classList.remove('hidden');
                                cooldownProgressFill.style.transition = 'none';
                                cooldownProgressFill.style.width = '100%';
                                setTimeout(() => {
                                    cooldownProgressFill.style.transition = `width ${totalDelay}s linear`;
                                    cooldownProgressFill.style.width = '0%';
                                }, 100);

                                if (cooldownInterval) clearInterval(cooldownInterval);
                                cooldownInterval = setInterval(() => {
                                    timeLeft -= 1;
                                    if (timeLeft <= 0) {
                                        clearInterval(cooldownInterval);
                                        cooldownTimerCard.classList.add('hidden');
                                    } else {
                                        cooldownTimeLeft.textContent = `${timeLeft}s`;
                                    }
                                }, 1000);
                            }

                            const remainMatch = cleanLine.match(/\.\.\.\s*(\d+)s remaining/);
                            if (remainMatch) {
                                const secondsLeft = parseInt(remainMatch[1]);
                                cooldownTimeLeft.textContent = `${secondsLeft}s`;
                            }

                            // Interact Newsfeed parsing
                            if (cleanLine.includes('Bắt đầu tương tác Newsfeed')) {
                                statusDetailText.textContent = 'Khởi chạy tương tác Newsfeed nuôi nick...';
                            } else if (cleanLine.includes('Đang lướt Newsfeed')) {
                                statusDetailText.textContent = '📱 Đang cuộn lướt xem Bảng tin (Newsfeed)...';
                                statusIndicatorDot.className = 'status-indicator-dot active';
                            } else if (cleanLine.includes('Thả biểu cảm')) {
                                statusDetailText.textContent = '💖 Đang thả cảm xúc biểu đạt bài viết...';
                            } else if (cleanLine.includes('Viết bình luận')) {
                                statusDetailText.textContent = '💬 Đang tiến hành bình luận bài viết...';
                            } else if (cleanLine.includes('Hoàn thành tương tác Newsfeed')) {
                                statusDetailText.textContent = '✅ Đã hoàn thành tương tác nuôi nick!';
                                statusIndicatorDot.className = 'status-indicator-dot';
                            }

                            // Scrape articles parsing
                            if (cleanLine.includes('Quét tìm bình luận')) {
                                statusDetailText.textContent = '🔍 Đang quét thu thập bình luận...';
                            } else if (cleanLine.includes('Lọc số điện thoại')) {
                                statusDetailText.textContent = '📱 Đang phân tích lọc số điện thoại khách hàng...';
                            }
                        }
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
            const dummyTargets = Array.from({ length: limit }, (_, i) => `Bài viết Newsfeed #${i+1}`);
            initProgressDashboard('Nuôi Nick (Tương tác)', dummyTargets);
            runCommand('interact', { limit, comments });
        } else if (currentMode === 'scrape') {
            const target = scrapeTarget.value.trim();
            const limit = parseInt(scrapeLimit.value) || 50;
            if (!target) {
                showToast('Vui lòng nhập đường dẫn bài viết cần quét!', 'error');
                return;
            }
            scrapeResultsContainer.classList.add('hidden');
            initProgressDashboard('Quét bình luận bài viết', [target]);
            runCommand('scrape', { target, limit });
        } else if (currentMode === 'comment') {
            const rawTargets = commentTargets.value.trim();
            const content = commentContent.value.trim();
            if (!rawTargets || !content) {
                showToast('Vui lòng nhập danh sách link bài viết và nội dung bình luận!', 'error');
                return;
            }
            const targets = rawTargets.split('\n').map(t => t.trim()).filter(t => t);
            const tasks = targets.map(t => ({ target: t, content: content }));
            initProgressDashboard('Bình luận bài viết theo link', targets);
            runCommand('comment', {
                tasks,
                likePost: commentLikePost ? commentLikePost.checked : true,
                accountId: accountSelector.value
            });
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
                    // Assign selectedImagePath if it was uploaded successfully
                    tasks.push({ target: t, content: content, image: selectedImagePath });
                });
            }

            // Khởi tạo bảng tiến trình trực quan
            const taskNameMap = {
                group: 'Tác vụ đăng bài Nhóm (Group)',
                page: 'Tác vụ đăng bài Trang (Page)',
                thread: 'Tác vụ gửi tin nhắn (Thread)'
            };
            initProgressDashboard(taskNameMap[currentMode] || 'Tác vụ đăng bài', tasks.map(t => t.target));

            runCommand(currentMode, { tasks });
        }
    });

    // ---- Auto-resize textarea ----
    const composerTextarea = document.querySelector('.composer-textarea');
    if (composerTextarea) {
        composerTextarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    }

    // =========================================================================
    // CONTENT HUB LOGIC INTEGRATION
    // =========================================================================

    const BRANDS = {
      lacasa: {
        title: "🌿 Lacasa Content Hub",
        theme: { p:"#5a7d3c", pd:"#45602e", bg:"#f6f7f2", border:"#e3e6da", text:"#2c3327", muted:"#7a8270", accent:"#eef2e6" },
        name: "Lacasa Homestay", reelBrand: "Lacasa", reelName: "Lacasa Homestay Huế",
        addr: "🏡 Số 3 kiệt 17 Trần Phú, TP. Huế", addrShort: "Số 3 kiệt 17 Trần Phú, Huế",
        phone: "0905 555 317", heart: "💛", icon: "🌿",
        links: { fb:"https://www.facebook.com/lacasahomestayinvietnam", tiktok:"@lacasahomestayhue", web:"https://www.lacasahomestay.com", map:"https://maps.app.goo.gl/yatorSbnQBytZCEk9" },
        tagMain: "#LacasaHomestayHue #LacasaHomestay #HomestayHue #DuLichHue #HueTravel",
        tagGrp: "#LacasaHomestay #HomestayHue #DuLichHue",
        tagReel: "#LacasaHomestayHue #HomestayHue #DuLichHue #HueTravel #VisitHue",
        priceLine: "",
        priceDorm: "",
        rooms: [
          { label:"101 · Deluxe Double", sale:"phòng Deluxe Double (101)", attrs:"phòng riêng queen, 2 người" },
          { label:"102 · Deluxe", sale:"phòng Deluxe (102)", attrs:"phòng riêng queen" },
          { label:"103 · Deluxe", sale:"phòng Deluxe (103)", attrs:"phòng riêng queen" },
          { label:"104 · Dorm 8 giường", sale:"dorm 8 giường (104)", attrs:"dorm 8 giường, rèm riêng tư" },
          { label:"105 · Dorm 4 giường", sale:"dorm 4 giường (105)", attrs:"dorm 4 giường, rèm riêng tư" }
        ],
        chips: [
          "còn phòng hôm nay",
          "còn phòng cuối tuần",
          "dorm 8 giường, rèm riêng tư, tủ khoá lớn",
          "dorm 4 giường cho nhóm nhỏ",
          "phòng riêng giường queen, sạch thoáng, yên tĩnh",
          "couple, 2 người, riêng tư",
          "sân vườn BBQ miễn phí, bếp chung",
          "ở khu vực trung tâm Huế, kiểm tra bản đồ theo điểm muốn đi",
          "khách solo backpacker, giá dễ chịu",
          "gia đình nhỏ, phòng thoáng",
          "trốn nắng mùa hè, máy lạnh mát",
          "mưa chill, khu sinh hoạt chung ấm cúng",
          "check-in sớm, gửi hành lý miễn phí",
          "ưu đãi cuối tuần, giá tốt"
        ],
        targets: [
          ["auto","Tự chọn theo ý chính"], ["couple","Couple / cặp đôi"], ["sinhvien","Sinh viên"],
          ["nhom","Hội nhóm bạn"], ["giadinh","Gia đình nhỏ"], ["solo","Khách solo / backpacker"]
        ],
        targetText: {
          couple:"couple, các cặp đôi", sinhvien:"sinh viên, các bạn trẻ", nhom:"hội nhóm bạn đi đông",
          giadinh:"gia đình nhỏ", solo:"khách solo, backpacker đi tự túc",
          autoDefault:"couple, nhóm bạn và khách đi tự túc"
        },
        punch: [
          "💛 Người ta đi Huế để check-in, còn về Lacasa là để… không muốn đi đâu nữa.",
          "💛 Lacasa không hứa cho bạn giàu hơn, nhưng hứa cho bạn về là muốn nằm liền.",
          "💛 Ở Lacasa không có gì nhiều, chỉ có vườn xanh, gió mát và giấc ngủ ngon thôi à.",
          "💛 Sáng cà phê sân vườn, tối ngủ ngon khỏi bàn — ở Lacasa chỉ việc thả lỏng.",
          "💛 Trung tâm ngoài kia nhộn nhịp, còn trong Lacasa thì bình yên lạ."
        ],
        punchGroup: [
          "🎉 Đi đông mới vui — tối cả đám nướng BBQ ngoài vườn là hết sảy.",
          "💛 Đi chơi cả ngày, tối về cả nhóm quây quản — kỷ niệm đẹp là ở mấy đêm như vậy.",
          "🎉 Chỗ ở dễ chịu là nửa chuyến đi vui rồi — nửa còn lại là đồ ăn Huế 😋"
        ],
        features: [
          { kw:["dorm","giường tầng","8 giường","4 giường","6 giường","hostel","giường đơn","phòng tập thể"], line:"🛏️ Dorm 4 & 8 giường — mỗi giường có rèm riêng tư, đèn ngủ riêng, tủ lớn có khoá", short:"dorm có rèm riêng tư" },
          { kw:["3 wc","nhà vệ sinh","vệ sinh","wc","toilet"], line:"🚿 Khu dorm có 3 WC riêng — nhóm đông không phải chờ nhau", short:"3 WC riêng khu dorm" },
          { kw:["phòng riêng","queen","giường queen"], line:"🛏️ Phòng riêng sạch thoáng, giường Queen êm — riêng tư giữa lòng trung tâm", short:"phòng riêng giường Queen" },
          { kw:["2 người","couple","cặp đôi","cặp","người thương","lãng mạn"], line:"💛 Phòng riêng ấm cúng cho 2 người — sạch, thoáng, yên tĩnh", short:"phòng riêng cho 2 người" },
          { kw:["bbq","nướng","sân vườn","vườn","cây xanh","tiệc nướng","view vườn"], line:"🌳 Sân vườn xanh mát + khu BBQ chung miễn phí — tối quây quần nướng đồ cực vui", short:"sân vườn BBQ xanh mát" },
          { kw:["bếp","phòng khách","khu sinh hoạt","nấu"], line:"🍳 Bếp + phòng khách chung thoải mái — nấu nhẹ, tám chuyện như ở nhà", short:"bếp & khu sinh hoạt chung" },
          { kw:["cửa sổ","thoáng","gió"], line:"☀️ Phòng thoáng sáng, cửa sổ đón gió — sáng mở rèm ra là thấy đời nhẹ hẳn", short:"phòng thoáng sáng" },
          { kw:["tiện nghi","máy sấy","bàn ủi","lọc không khí","tủ lạnh","nước nóng","đầy đủ","điều hoà","điều hòa"], line:"🧺 Đủ tiện nghi: máy lạnh, nước nóng, tủ lạnh, bàn ủi, máy sấy tóc, máy lọc không khí", short:"đủ tiện nghi như ở nhà" },
          { kw:["check-in sớm","checkin sớm","đến sớm","nhận phòng sớm"], line:"⏰ Hỗ trợ check-in sớm tùy tình trạng phòng — nhắn trước để mình sắp xếp nha", short:"hỗ trợ check-in sớm tùy phòng" },
          { kw:["solo","backpacker","một mình","phượt","du lịch bụi","đi bụi","tây ba lô"], line:"🎒 Hợp khách solo/backpacker — giá dễ chịu, không gian thân thiện dễ làm quen bạn mới", short:"hợp khách solo backpacker" },
          { kw:["máy lạnh","điều hoà","điều hòa"], line:"❄️ Máy lạnh mát rượi — bước vào phòng là quên hết cái nóng ngoài trời", short:"máy lạnh mát rượi" },
          { kw:["gần ga","ga huế","đi tàu"], line:"🚉 Từ ga Huế đến Lacasa, nên kiểm tra tuyến đường thực tế trên bản đồ theo thời điểm di chuyển", short:"thuận tiện kiểm tra đường từ ga Huế" },
          { kw:["quán ngon","quán ăn","đồ ăn","ăn ngon"], line:"🍜 Khu vực trung tâm có nhiều lựa chọn món Huế; nên kiểm tra quán, giờ bán và quãng đường trước khi đi", short:"dễ tìm món Huế ở khu trung tâm" },
          { kw:["đại nội","trường tiền","sông hương","phố tây","an định","trung tâm","vị trí","gần đại nội","phố đi bộ","gần sông hương"], line:"📍 Lacasa ở khu vực trung tâm Huế; hãy kiểm tra bản đồ để ghép Đại Nội, cầu Trường Tiền, sông Hương, phố Tây hoặc cung An Định vào lịch trình", short:"vị trí khu trung tâm Huế" },
          { kw:["nắng","mùa hè","nóng","tránh nắng"], line:"☀️ Trốn nắng Huế cực hợp lý — ngoài trời oi bức, trong nhà mát rượi dễ chịu", short:"trốn nắng mùa hè" },
          { kw:["ưu đãi","giảm","khuyến mãi","deal","giá tốt","cuối tuần"], line:"🎁 Gửi ngày ở và số khách để mình kiểm tra giá hoặc ưu đãi đang áp dụng", short:"kiểm tra ưu đãi theo ngày ở" },
          { kw:["còn phòng","trống"], line:"📅 Còn phòng — đặt sớm để chọn được phòng ưng ý nhất", short:"còn phòng" },
          { kw:["chill","healing","thư giãn"], line:"😌 Không gian chill đúng nghĩa — về là thả lỏng, healing nhẹ nhàng", short:"không gian chill" },
          { kw:["yên tĩnh","tĩnh"], line:"🤫 Yên tĩnh dễ chịu — ngoài phố đông vui, trong nhà thì bình yên", short:"yên tĩnh dễ chịu" },
          { kw:["giá rẻ","bình dân","tiết kiệm","hợp lý","giá tốt sinh viên"], line:"💛 Giá hợp lý cho đa số khách du lịch — ở ngay trung tâm mà không lo cháy ví", short:"giá hợp lý ngay trung tâm" },
          { kw:["nhà mới","mới xây","sạch sẽ"], line:"🏡 Nhà mới, sạch sẽ, không gian thoáng — nghỉ ngơi cực dễ chịu sau ngày dài khám phá", short:"nhà mới sạch thoáng" }
        ],
        defaults: [
          { line:"🛏️ Phòng sạch, giường êm, chăn ga mới tinh — ngủ ngon khỏi bàn", skipIfDorm:false },
          { line:"🌳 Sân vườn xanh mát + khu BBQ chung miễn phí — tối quây quần nướng đồ cực vui", skipIfDorm:false },
          { line:"📍 Ở khu vực trung tâm Huế; nên kiểm tra bản đồ để chọn tuyến đi phù hợp", skipIfDorm:false },
          { line:"❄️ Máy lạnh mát rượi, nước nóng, đủ tiện nghi như ở nhà", skipIfDorm:false }
        ],
        dormExtra: [
          "🛏️ Mỗi giường dorm có rèm riêng tư, đèn ngủ riêng, tủ lớn có khoá",
          "🚿 Khu dorm có 3 WC riêng — nhóm đông không phải chờ nhau"
        ],
        grp1Extra: "Lacasa ở khu vực trung tâm Huế; thời gian đi từng điểm cần kiểm tra theo bản đồ và giao thông thực tế.",
        grp2Body: function(s){ return "Chiều dạo bờ sông Hương, ghé cầu Trường Tiền chụp vài tấm, tối về Lacasa Homestay — " + s + ", sạch sẽ dễ chịu, ngủ một giấc là khỏe re."; },
        priceGrp2: "Giá mềm.",
        grp4Move: "— Đi lại: ở khu vực trung tâm; kiểm tra bản đồ trước khi ghép các điểm",
        hashSets: {
          short: "#LacasaHomestayHue #LacasaHomestay #HomestayHue #DuLichHue #HueTravel #KhamPhaHue",
          full: "#LacasaHomestayHue #LacasaHomestay #HomestayHue #HueHomestay #DormHue #HostelHue #DuLichHue #KhamPhaHue #HueTravel #VisitHue #DaiNoiHue #SongHuong #CauTruongTien #PhoTayHue #CungAnDinh #LuuTruHue #PhongRiengHue #PhongDormHue #BackpackerHue #TravelVietnam #VietnamTravel",
          reel: "#LacasaHomestayHue #HomestayHue #DuLichHue #HueTravel #VisitHue #KhamPhaHue #SongHuong #DaiNoiHue",
          group: "#LacasaHomestay #HomestayHue #DuLichHue",
          location: "#DaiNoiHue #CauTruongTien #SongHuong #PhoTayHue #CungAnDinh #LuuTruHue"
        },
        templates: [
          { name:"🛏️ Còn dorm cho nhóm bạn", idea:"dorm 8 giường, rèm riêng tư, tủ khoá lớn, 3 WC riêng", purpose:"dorm", target:"nhom" },
          { name:"💛 Phòng riêng queen cho couple", idea:"phòng riêng giường queen, sạch thoáng, yên tĩnh", purpose:"couple", target:"couple" },
          { name:"🤫 Trung tâm nhưng yên tĩnh", idea:"ở khu vực trung tâm Huế, yên tĩnh, kiểm tra bản đồ theo điểm muốn đi", purpose:"conphong", target:"auto" },
          { name:"🌳 Sân vườn BBQ cho nhóm", idea:"sân vườn BBQ miễn phí, bếp chung, nhóm bạn quây quần", purpose:"dorm", target:"nhom" },
          { name:"🎒 Solo/backpacker giá tốt", idea:"khách solo backpacker, dorm từ 1xx/người, rèm riêng tư", purpose:"solo", target:"solo" },
          { name:"📝 Lịch trình Huế + Lacasa", idea:"gợi ý lịch trình Huế một ngày, tối về Lacasa nghỉ, sân vườn chill", purpose:"lichtrinh", target:"auto" }
        ],
        comments: {
          question: "😌 Mọi người đi Huế thích ở gần Đại Nội hay dạo phố Tây buổi tối hơn nè?",
          special: "🍜 Khu trung tâm có nhiều món Huế; nhớ kiểm tra quán, giờ bán và đường đi trước khi ghé.",
          zaloExtra: ""
        }
      },
      umee: {
        title: "🎬 UMEE Content Hub",
        theme: { p:"#8e4157", pd:"#6f2f43", bg:"#faf6f5", border:"#eadfe0", text:"#362a2e", muted:"#8a767c", accent:"#f6e9ed" },
        name: "UMEE Homestay", reelBrand: "UMEE", reelName: "UMEE Homestay Huế",
        addr: "🏡 SH44 – Manor Crown, 62 Tố Hữu, TP. Huế", addrShort: "SH44 – Manor Crown, 62 Tố Hữu, Huế",
        phone: "0905 555 317", heart: "💜", icon: "🎬",
        links: { fb:"https://www.facebook.com/umeehomestay", tiktok:"@umee.homestay", web:"https://www.umeehomestay.com", map:"https://maps.app.goo.gl/YvhzxAjYBoJ2QqUX6" },
        tagMain: "#UmeeHomestayHue #UmeeHomestay #HomestayHue #DuLichHue #HueTravel",
        tagGrp: "#UmeeHomestay #HomestayHue #DuLichHue",
        tagReel: "#UmeeHomestayHue #HomestayHue #PhongDepHue #DuLichHue #HueTravel",
        priceLine: "",
        priceDorm: "",
        rooms: [
          { label:"201 · Cố Đô", sale:"phòng Cố Đô (201)", attrs:"giường king, máy chiếu netflix" },
          { label:"202 · Midnight", sale:"phòng Midnight (202)", attrs:"tông đen cá tính, giường king, máy chiếu netflix" },
          { label:"301 · Ban công", sale:"phòng Ban công (301)", attrs:"ban công, bếp nhỏ, giường king" },
          { label:"302 · Family", sale:"phòng Family (302)", attrs:"gia đình, bếp và bàn ăn, 2 cửa sổ, giường king" },
          { label:"401 · Dorm", sale:"dorm rooftop (401)", attrs:"dorm, view toàn cảnh" }
        ],
        chips: [
          "còn phòng hôm nay",
          "phòng couple lãng mạn, máy chiếu Netflix 100 inch",
          "giường King, bồn tắm thư giãn",
          "phòng Midnight tông đen cá tính",
          "phòng ban công + bếp nhỏ, pha cà phê hóng gió",
          "phòng Family, bếp và bàn ăn, 2 cửa sổ",
          "đi ô tô tự lái, đỗ xe miễn phí trước cửa",
          "check-in tự động 24/7, tới khuya vẫn nhận phòng",
          "nghỉ theo giờ, day-use linh hoạt",
          "nhóm bạn đi đông, xem phim chung",
          "trốn nắng, phòng mát rượi",
          "mưa, nằm xem phim chill",
          "trang trí sinh nhật kỷ niệm",
          "ưu đãi cuối tuần, giá tốt"
        ],
        targets: [
          ["auto","Tự chọn theo ý chính"], ["couple","Couple / cặp đôi"], ["giadinh","Gia đình nhỏ"],
          ["nhom","Hội nhóm bạn"], ["oto","Khách đi ô tô tự lái"], ["solo","Khách solo tự túc"]
        ],
        targetText: {
          couple:"couple, các cặp đôi", giadinh:"gia đình nhỏ", nhom:"hội nhóm bạn đi đông",
          oto:"khách đi ô tô tự lái", solo:"khách solo, đi tự túc",
          autoDefault:"couple, gia đình nhỏ và hội nhóm bạn"
        },
        punch: [
          "💜 Đi Huế với người thương, về UMEE bật máy chiếu lên là hết muốn ra ngoài.",
          "💜 UMEE không hứa gì nhiều — chỉ hứa một buổi tối thật chill giữa lòng Huế.",
          "💜 Người ta đi Huế để ngắm Cố đô, còn tối về UMEE là để nghỉ ngơi đúng nghĩa.",
          "🛁 Đi chơi cả ngày mỏi chân, về UMEE nghỉ một đêm là khỏe re.",
          "🎬 Phòng đẹp, đèn ấm — tối ở UMEE dễ chịu khỏi chỉnh."
        ],
        punchGroup: [
          "🎉 Đi đông mới vui — tối cả nhóm quây quần bật máy chiếu xem phim là hết sảy.",
          "💜 Đi chơi cả ngày, tối về cả đám nằm tám chuyện — kỷ niệm đẹp là ở mấy đêm như vậy.",
          "🎉 Chỗ ở rộng rãi thoải mái là nửa chuyến đi vui rồi — nửa còn lại là đồ ăn Huế 😋"
        ],
        features: [
          { kw:["dorm","giường tầng","8 giường","4 giường","6 giường"], line:"🛏️ Phòng dorm rộng rãi — giường thoải mái, hợp hội nhóm đi đông vui", short:"phòng dorm rộng rãi" },
          { kw:["view toàn cảnh","toàn cảnh","view đẹp","tầng cao","view"], line:"🌆 View toàn cảnh từ trên cao — sáng ngắm bình minh, tối ngắm đèn thành phố Huế", short:"view toàn cảnh" },
          { kw:["nhà vệ sinh","vệ sinh","wc","toilet"], line:"🚿 Nhà vệ sinh rộng sạch — đi nhóm đông cũng không phải chờ nhau", short:"nhà vệ sinh rộng sạch" },
          { kw:["máy chiếu","netflix","chiếu phim","100 inch","xem phim","movie night","rạp phim mini"], line:"🎬 Máy chiếu Netflix 100 inch ngay trong phòng — tối nằm xem như rạp riêng", short:"máy chiếu Netflix 100 inch" },
          { kw:["giường king","king"], line:"🛏️ Giường King size êm ái — nằm xuống là lún vào giấc ngủ, sáng dậy không muốn rời", short:"giường King size" },
          { kw:["tông đen","màu đen","đen cá tính","midnight"], line:"🖤 Phòng tông đen cá tính — decor gu riêng, lên hình cực nghệ", short:"phòng tông đen cá tính" },
          { kw:["bàn ăn","dining"], line:"🍽️ Bếp + bàn ăn ngay trong phòng — cả nhà nấu nướng, ăn uống quây quần như ở nhà", short:"bếp + bàn ăn trong phòng" },
          { kw:["cửa sổ","2 cửa sổ"], line:"☀️ Phòng 2 cửa sổ thoáng sáng — đón nắng gió tự nhiên cả ngày", short:"phòng 2 cửa sổ thoáng sáng" },
          { kw:["bồn tắm","ngâm","bathtub","tắm bồn","thư giãn bồn"], line:"🛁 Có phòng với bồn tắm — ngâm mình thư giãn sau ngày dài dạo Cố đô", short:"bồn tắm thư giãn" },
          { kw:["ban công","balcony"], line:"🌤️ Có phòng ban công + bếp nhỏ — sáng pha cà phê hóng gió, chill hết nấc", short:"ban công + bếp nhỏ" },
          { kw:["bếp","nấu"], line:"🍳 Bếp nhỏ trong phòng (một số phòng) — pha cà phê, nấu nhẹ tiện lợi", short:"bếp nhỏ tiện lợi" },
          { kw:["ô tô","oto","đỗ xe","xe hơi","parking","tự lái","bãi xe","đậu xe"], line:"🚗 Bãi đỗ ô tô miễn phí ngay trước cửa — đi xe hơi tới Huế là tiện khỏi bàn", short:"đỗ ô tô miễn phí trước cửa" },
          { kw:["check-in","checkin","tự động","tới trễ","khuya","24/7"], line:"🔑 Check-in/out tự động 24/7 — tới khuya cỡ nào cũng nhận phòng được", short:"check-in tự động 24/7" },
          { kw:["theo giờ","nghỉ giờ","day-use","day use","linh hoạt"], line:"⏰ Nhận phòng theo giờ hoặc theo ngày — linh hoạt theo lịch trình của bạn", short:"nhận theo giờ & theo ngày" },
          { kw:["couple","cặp","2 người","người thương","lãng mạn","kỷ niệm","hẹn hò"], line:"💜 Không gian lãng mạn cho couple — đèn ấm, decor xinh, riêng tư tuyệt đối", short:"phòng couple lãng mạn" },
          { kw:["gia đình"], line:"👨‍👩‍👧 Phòng rộng thoải mái cho gia đình — an toàn, tiện nghi, ngay trung tâm", short:"phòng rộng cho gia đình" },
          { kw:["nhóm","hội","đi đông"], line:"🎉 Chỗ ở thoải mái cho hội bạn — đi đông càng vui", short:"chỗ ở cho nhóm đông" },
          { kw:["dọn phòng","vệ sinh hằng ngày"], line:"🧹 Dọn phòng hằng ngày — lúc nào cũng sạch sẽ tinh tươm", short:"dọn phòng hằng ngày" },
          { kw:["đưa đón","sân bay","thuê xe","xe máy","giặt"], line:"🛵 Hỗ trợ thuê xe máy, đưa đón ga/sân bay, giặt là — cần gì nhắn mình lo", short:"hỗ trợ xe máy & đưa đón" },
          { kw:["bể bơi","hồ bơi","bơi"], line:"🏊 Bể bơi 4 mùa trong nhà kính tầng 6 của tòa nhà, có phụ phí — mưa hay nắng đều bơi được", short:"bể bơi 4 mùa nhà kính (phụ phí)" },
          { kw:["trung tâm","vị trí"], line:"📍 Ngay trung tâm TP. Huế — đi Đại Nội, sông Hương, phố đi bộ đều nhanh", short:"ngay trung tâm Huế" },
          { kw:["nắng","mùa hè","nóng","tránh nắng"], line:"☀️ Trốn nắng Huế cực hợp lý — ngoài trời oi bước, trong phòng mát rượi", short:"trốn nắng mùa hè" },
          { kw:["ưu đãi","giảm","khuyến mãi","deal","giá tốt","cuối tuần"], line:"🎁 Gửi ngày ở và số khách để mình kiểm tra giá hoặc ưu đãi đang áp dụng", short:"kiểm tra ưu đãi theo ngày ở" },
          { kw:["còn phòng","trống"], line:"📅 Còn phòng — đặt sớm để chọn được phòng ưng ý nhất", short:"còn phòng" },
          { kw:["chill","healing","thư giãn"], line:"😌 Không gian chill đúng nghĩa — về là thả lỏng, healing nhẹ nhàng", short:"không gian chill" },
          { kw:["riêng tư","tự do","không ai làm phiền"], line:"🔒 Riêng tư tuyệt đối — tự check-in, tự do giờ giấc, không ai làm phiền", short:"riêng tư tự do" }
        ],
        defaults: [
          { line:"🎬 Phòng riêng đều có giường King size + máy chiếu Netflix 100 inch — combo nằm xem phim cực đã", skipIfDorm:true },
          { line:"🔑 Check-in/out tự động 24/7 — tới trễ vẫn nhận phòng ngon lành", skipIfDorm:false },
          { line:"🚗 Đỗ ô tô miễn phí ngay trước cửa", skipIfDorm:false },
          { line:"📍 Ngay trung tâm TP. Huế — đi Đại Nội, sông Hương, phố đi bộ đều nhanh", skipIfDorm:false }
        ],
        dormExtra: [],
        grp1Extra: "Vị trí ngay trung tâm (62 Tố Hữu), đi Đại Nội, phố đi bộ đều nhanh, có chỗ đỗ ô tô miễn phí trước cửa.",
        grp2Body: function(s){ return "Chiều dạo bờ sông Hương, tối về UMEE Homestay — " + s + ", check-in tự động 24/7 nên về trễ cũng không sao."; },
        priceGrp2: "Giá mềm, nhận theo giờ hoặc theo ngày.",
        grp4Move: "— Đi ô tô: có chỗ đỗ miễn phí ngay trước cửa",
        hashSets: {
          short: "#UmeeHomestayHue #UmeeHomestay #HomestayHue #DuLichHue #HueTravel #PhongDepHue",
          full: "#UmeeHomestayHue #UmeeHomestay #HomestayHue #HueHomestay #PhongDepHue #PhongChillHue #CoupleHue #DuLichHue #KhamPhaHue #HueTravel #VisitHue #SongHuong #DaiNoiHue #CauTruongTien #LuuTruHue #TravelVietnam #VietnamTravel",
          reel: "#UmeeHomestayHue #HomestayHue #PhongDepHue #PhongChillHue #DuLichHue #HueTravel #VisitHue",
          group: "#UmeeHomestay #HomestayHue #DuLichHue",
          location: "#SongHuong #DaiNoiHue #CauTruongTien #LuuTruHue #ToHuuHue"
        },
        templates: [
          { name:"🎬 Couple movie night máy chiếu", idea:"phòng couple lãng mạn, máy chiếu Netflix 100 inch, đèn ấm", purpose:"couple", target:"couple" },
          { name:"🛁 Phòng bồn tắm lãng mạn", idea:"phòng có bồn tắm, giường King, riêng tư", purpose:"couple", target:"couple" },
          { name:"🚗 Đỗ xe free + tự check-in", idea:"đi ô tô tự lái, đỗ xe miễn phí trước cửa, check-in tự động 24/7", purpose:"conphong", target:"oto" },
          { name:"👨‍👩‍👧 Phòng gia đình", idea:"phòng rộng cho gia đình, ngay trung tâm, tiện nghi", purpose:"giadinh", target:"giadinh" },
          { name:"🎉 Nhóm bạn đi đông", idea:"nhóm bạn đi đông, phòng rộng, máy chiếu xem phim chung", purpose:"dorm", target:"nhom" },
          { name:"⏰ Nghỉ theo giờ / day-use", idea:"nhận phòng theo giờ, day-use linh hoạt, check-in tự động", purpose:"conphong", target:"auto" }
        ],
        comments: {
          question: "😌 Tối ở UMEE mọi người thích nằm xem phim máy chiếu hay ngâm bồn tắm thư giãn hơn nè?",
          special: "🚗 Đi ô tô tới Huế thì quá tiện — bãi đỗ xe miễn phí ngay trước cửa UMEE luôn.",
          zaloExtra: " Nhận theo giờ hoặc theo ngày đều được."
        }
      },
      hue: {
        isPlace: true,
        title: "🌸 Về Huế — Content Hub",
        theme: { p:"#6b4f8a", pd:"#533c6d", bg:"#f8f6fb", border:"#e6e0ee", text:"#2f2a38", muted:"#837b91", accent:"#efe9f6" },
        name: "Huế Mộng Mơ", reelBrand: "Huế", reelName: "Huế Mộng Mơ",
        addr: "📍 Huế — Cố đô mộng mơ", addrShort: "Huế",
        phone: "0905 555 317", heart: "💜", icon: "🌸",
        tagMain: "#DuLichHue #HueTravel #KhamPhaHue #CheckInHue #HueMongMo",
        tagGrp: "#DuLichHue #HueTravel #KhamPhaHue",
        tagReel: "#DuLichHue #HueTravel #CheckInHue #HueMongMo #VisitHue",
        priceLine: "", priceDorm: "",
        rooms: [],
        chips: [
          "cuối tuần này Huế có sự kiện gì",
          "bún bò, cơm hến, chè Huế phải thử",
          "bánh khoái, bánh bèo, bánh nậm, bánh lọc",
          "cà phê muối, quán cà phê view sông Hương",
          "Đại Nội đi sớm, thuê áo dài chụp hình",
          "lăng Tự Đức, lăng Khải Định",
          "đồi Vọng Cảnh, hoàng hôn sông Hương",
          "phá Tam Giang, đầm Chuồn hoàng hôn",
          "làng hương Thuỷ Xuân sống ảo",
          "Huế mưa thì chơi gì",
          "thời tiết hôm nay, đi sớm về trưa",
          "cầu Trường Tiền lên đèn, phố đi bộ buổi tối",
          "lịch trình Huế 1 ngày",
          "đặc sản mang về: mè xửng, tôm chua"
        ],
        purposes: [
          ["auto","Tự chọn theo ý chính"],["sukien","Sự kiện Huế"],["amthuc","Ẩm thực Huế"],
          ["vanhoa","Văn hoá & di sản"],["thoitiet","Thời tiết hôm nay"],["checkin","Góc check-in đẹp"],["meo","Mẹo du lịch Huế"]
        ],
        targets: [
          ["auto","Tự chọn"],["khach","Khách du lịch"],["nhom","Nhóm bạn"],["giadinh","Gia đình"],["couple","Couple"]
        ],
        targetText: { khach:"khách du lịch tự túc", nhom:"hội nhóm bạn", giadinh:"gia đình", couple:"các cặp đôi", autoDefault:"ai sắp đi Huế" },
        punch: [
          "💜 Huế không vội — tới Huế là để sống chậm lại một chút.",
          "💜 Huế đẹp kiểu nhẹ nhàng — đi một lần là nhớ hoài.",
          "🌸 Ở Huế, bình yên không phải tìm — nó tự tới.",
          "💜 Huế mộng mơ thiệt, không phải nói quá đâu."
        ],
        punchGroup: [
          "🌸 Đi Huế với hội bạn thân — chậm rãi mà vui khó tả.",
          "💜 Huế là kiểu nơi cả nhóm đi xong ai cũng muốn quay lại."
        ],
        features: [
          { kw:["bún bò"], line:"🍜 Bún bò Huế — ăn một tô nóng buổi sáng là tỉnh cả người", short:"bún bò Huế" },
          { kw:["cơm hến"], line:"🍚 Cơm hến — món dân dã mà tới Huế không ăn là tiếc", short:"cơm hến" },
          { kw:["chè"], line:"🍧 Chè Huế mấy chục loại — ăn thử chè bột lọc heo quay cho biết", short:"chè Huế" },
          { kw:["cà phê muối","cafe muối"], line:"☕ Cà phê muối Huế — vị mặn ngọt lạ mà cuốn, uống là ghiền", short:"cà phê muối" },
          { kw:["cà phê","cafe","quán"], line:"☕ Huế nhiều quán cà phê view đẹp — ngồi nhìn sông Hương trôi là hết buổi", short:"cà phê view đẹp" },
          { kw:["đại nội","hoàng thành"], line:"🏯 Đại Nội thường dễ tham quan hơn khi đi sớm và thời tiết dịu; hãy kiểm tra giờ mở cửa chính thức", short:"Đại Nội buổi sớm" },
          { kw:["áo dài"], line:"👘 Thuê áo dài chụp ở Đại Nội hay bờ sông Hương — bộ hình để đời", short:"thuê áo dài chụp hình" },
          { kw:["lăng","khải định","minh mạng","tự đức"], line:"⛩️ Lăng Khải Định, Minh Mạng, Tự Đức — mỗi lăng một vẻ, đáng đi hết", short:"tham quan lăng tẩm" },
          { kw:["sông hương","thuyền"], line:"🌊 Chiều dạo bờ sông Hương, hóng gió ngắm hoàng hôn — bình yên khó tả", short:"dạo bờ sông Hương" },
          { kw:["trường tiền"], line:"🌉 Cầu Trường Tiền lên đèn buổi tối — góc check-in kinh điển của Huế", short:"cầu Trường Tiền lên đèn" },
          { kw:["phố đi bộ","phố tây","buổi tối","về đêm"], line:"🌃 Tối dạo phố đi bộ, phố Tây — ăn vặt, nghe nhạc, đông vui", short:"phố đi bộ buổi tối" },
          { kw:["chợ đông ba","đông ba"], line:"🛍️ Chợ Đông Ba — ăn vặt đã đời rồi mua đặc sản mang về", short:"chợ Đông Ba" },
          { kw:["thiên mụ"], line:"🛕 Chùa Thiên Mụ — chiều ghé vừa yên vừa đẹp, nhìn ra sông Hương", short:"chùa Thiên Mụ" },
          { kw:["mưa"], line:"🌧️ Huế mưa thì đừng buồn — kiếm quán cà phê nghe nhạc Trịnh là đúng bài", short:"Huế mưa chill" },
          { kw:["nắng","nóng","thời tiết"], line:"☀️ Huế đang nắng — đi sớm về trưa nghỉ, chiều mát hãy ra đường nha", short:"mẹo tránh nắng Huế" },
          { kw:["sự kiện","festival","lễ hội","event"], line:"🎪 Sự kiện Huế thay đổi theo ngày — kiểm tra nguồn chính thức rồi nhập đúng tên, ngày, giờ và địa điểm trước khi đăng", short:"kiểm tra lịch sự kiện Huế" },
          { kw:["check-in","checkin","sống ảo","chụp hình","góc chụp"], line:"📸 Huế góc nào cũng chụp được — nhớ sạc đầy pin điện thoại", short:"góc check-in Huế" },
          { kw:["lăng tự đức","tự đức"], line:"⛩️ Lăng Tự Đức — thơ mộng nhất trong các lăng, hồ nước và rừng thông đẹp như tranh", short:"lăng Tự Đức thơ mộng" },
          { kw:["lăng khải định","khải định"], line:"⛩️ Lăng Khải Định nổi bật với nghệ thuật khảm sành sứ và sự giao thoa trong kiến trúc", short:"lăng Khải Định" },
          { kw:["lăng minh mạng","minh mạng"], line:"⛩️ Lăng Minh Mạng — bề thế, đối xứng, đi vào là thấy sự uy nghiêm của triều Nguyễn", short:"lăng Minh Mạng" },
          { kw:["ngọ môn","cổng đại nội"], line:"🏯 Ngọ Môn — cổng chính Đại Nội, biểu tượng của Huế, chụp từ Kỳ Đài nhìn qua rất đẹp", short:"Ngọ Môn biểu tượng Huế" },
          { kw:["kỳ đài","cột cờ"], line:"🚩 Kỳ Đài trước Đại Nội — chiều ra hóng gió, chụp với cột cờ là có hình đẹp", short:"Kỳ Đài trước Đại Nội" },
          { kw:["cung an định","an định"], line:"🏰 Cung An Định có kiến trúc trang trí giao thoa Á–Âu, phù hợp chủ đề lịch sử và nhiếp ảnh", short:"kiến trúc Cung An Định" },
          { kw:["quốc học","trường quốc học"], line:"🏫 Trường Quốc Học — dãy nhà đỏ hơn 120 năm tuổi, góc check-in kinh điển của Huế", short:"Quốc Học tường đỏ" },
          { kw:["làng hương","thuỷ xuân","thủy xuân"], line:"🌈 Làng hương Thuỷ Xuân có những bó hương nhiều màu và không gian làng nghề phù hợp để tìm hiểu, chụp ảnh", short:"làng hương Thuỷ Xuân" },
          { kw:["đồi vọng cảnh","vọng cảnh"], line:"🌄 Đồi Vọng Cảnh cho góc nhìn cao về sông Hương và cảnh quan xung quanh; nên kiểm tra thời tiết trước khi đi", short:"hoàng hôn đồi Vọng Cảnh" },
          { kw:["đồi thiên an","thiên an"], line:"🌲 Đồi Thiên An có cảnh quan rừng thông; phù hợp đi bộ nhẹ và chụp ảnh khi thời tiết thuận lợi", short:"đồi Thiên An rừng thông" },
          { kw:["phá tam giang","tam giang","đầm phá"], line:"🌅 Phá Tam Giang — hợp đi buổi chiều để ngắm hoàng hôn; nhớ kiểm tra cung đường và thời tiết trước khi đi", short:"hoàng hôn phá Tam Giang" },
          { kw:["biển thuận an","thuận an","biển"], line:"🏖️ Biển Thuận An — gợi ý đổi gió ngoài khu trung tâm; kiểm tra thời tiết và tình trạng biển trước khi đi", short:"biển Thuận An" },
          { kw:["lăng cô"], line:"🏝️ Vịnh Lăng Cô — biển xanh cát trắng, tiện đường cho ai đi tiếp Đà Nẵng", short:"vịnh Lăng Cô" },
          { kw:["bạch mã"], line:"⛰️ Vườn quốc gia Bạch Mã — săn mây, thác nước, trekking mát lạnh giữa mùa hè", short:"Bạch Mã săn mây" },
          { kw:["suối","thác","trốn nóng"], line:"💦 Suối Mơ, thác Nhị Hồ — điểm trốn nóng gần Huế, nước trong vắt", short:"suối thác trốn nóng" },
          { kw:["cầu gỗ lim","gỗ lim","đường đi bộ ven sông"], line:"🌉 Cầu gỗ lim ven sông Hương — đi bộ hóng gió, chụp ảnh đẹp cả ngày lẫn đêm", short:"cầu gỗ lim ven sông" },
          { kw:["cầu ngói","thanh toàn"], line:"🌾 Cầu ngói Thanh Toàn — cây cầu cổ giữa làng quê, yên bình đúng chất Huế xưa", short:"cầu ngói Thanh Toàn" },
          { kw:["ca huế","thuyền rồng","nghe ca"], line:"🛶 Nghe ca Huế trên thuyền rồng sông Hương buổi tối — trải nghiệm rất Huế", short:"ca Huế trên thuyền rồng" },
          { kw:["nhã nhạc","cung đình"], line:"🎶 Nhã nhạc cung đình Huế — di sản phi vật thể UNESCO, nghe một lần cho biết", short:"nhã nhạc cung đình" },
          { kw:["lịch sử","triều nguyễn","kinh đô","di sản","unesco"], line:"📜 Huế — kinh đô triều Nguyễn gần 150 năm, quần thể di tích được UNESCO công nhận di sản thế giới", short:"kinh đô triều Nguyễn" },
          { kw:["xích lô"], line:"🛺 Dạo Thành Nội bằng xích lô — chậm rãi ngắm phố, đúng nhịp sống Huế", short:"dạo phố bằng xích lô" },
          { kw:["thuê xe máy","xe máy"], line:"🛵 Thuê xe máy giúp chủ động lịch trình; luôn kiểm tra quãng đường, thời tiết và chỗ gửi xe trước khi đi", short:"thuê xe máy dạo Huế" },
          { kw:["bản đồ","chỉ đường","map","lịch trình"], line:"🗺️ Mẹo: lưu sẵn Google Maps, gom các điểm cùng khu và kiểm tra giờ mở cửa trước khi xuất phát", short:"lưu bản đồ các điểm" },
          { kw:["đặc sản","quà","mang về","mè xửng","tôm chua"], line:"🎁 Đặc sản mang về: mè xửng, tôm chua, trà cung đình, nón lá — ghé chợ Đông Ba là đủ", short:"đặc sản Huế mang về" },
          { kw:["bánh khoái","bánh bèo","bánh nậm","bánh lọc","bánh huế"], line:"🥞 Bánh khoái, bánh bèo, bánh nậm, bánh lọc — bộ tứ bánh Huế ăn một lần là nhớ", short:"bộ tứ bánh Huế" },
          { kw:["bún thịt nướng","nem lụi"], line:"🍢 Nem lụi, bún thịt nướng Huế — cuốn rau chấm nước lèo đậu phộng là hết nước chấm", short:"nem lụi bún thịt nướng" },
          { kw:["bánh canh","nam phổ"], line:"🍜 Bánh canh Nam Phổ — món chiều của người Huế, sệt sệt cay cay cực cuốn", short:"bánh canh Nam Phổ" },
          { kw:["cơm chay","chùa","ăn chay"], line:"🥗 Huế là thủ phủ cơm chay — quán chay ngon rẻ khắp nơi, ăn thanh đạm đổi vị", short:"cơm chay Huế" },
          { kw:["mùa mưa","tháng 10","tháng 11","lụt"], line:"🌧️ Huế mùa mưa (tháng 10–12) có cái đẹp riêng — quán cà phê ấm, phố vắng, rất tình", short:"Huế mùa mưa rất tình" },
          { kw:["tết","lễ","30/4","festival"], line:"🎊 Dịp lễ Huế đông vui hơn hẳn — đặt phòng và lên lịch sớm để đi được trọn vẹn", short:"Huế dịp lễ hội" }
        ],
        defaults: [
          { line:"🌊 Chiều dạo bờ sông Hương, hóng gió ngắm hoàng hôn — bình yên khó tả", skipIfDorm:false },
          { line:"🍜 Bún bò Huế — ăn một tô nóng buổi sáng là tỉnh cả người", skipIfDorm:false },
          { line:"🏯 Đại Nội thường dễ tham quan hơn khi đi sớm và thời tiết dịu; hãy kiểm tra giờ mở cửa chính thức", skipIfDorm:false }
        ],
        dormExtra: [],
        grp1Extra: "Đi tự túc nên gom các điểm cùng khu và kiểm tra bản đồ trước khi xuất phát.",
        grp2Body: function(s){ return "Sáng Đại Nội, trưa bún bò, chiều dạo bờ sông Hương, tối lên cầu Trường Tiền — kèm " + s + " nữa là trọn một ngày Huế."; },
        priceGrp2: "",
        grp4Move: "— Chỗ ở: Lacasa (kiệt 17 Trần Phú) hoặc UMEE (62 Tố Hữu) — Zalo 0905 555 317",
        hashSets: {
          short: "#DuLichHue #HueTravel #KhamPhaHue #CheckInHue #HueMongMo #VisitHue",
          full: "#DuLichHue #HueTravel #KhamPhaHue #CheckInHue #HueMongMo #VisitHue #AmThucHue #BunBoHue #ComHen #CheHue #CaPheMuoi #DaiNoiHue #SongHuong #CauTruongTien #ChoDongBa #ThienMu #PhoTayHue #AoDaiHue #LangTuDuc #LangKhaiDinh #LangMinhMang #CungAnDinh #QuocHocHue #LangHuongThuyXuan #DoiVongCanh #PhaTamGiang #BienThuanAn #LangCo #BachMa #CauGoLim #NhaNhacCungDinh #CaHue #DiSanHue #HueXua #TravelVietnam #VietnamTravel",
          reel: "#DuLichHue #HueTravel #CheckInHue #HueMongMo #AmThucHue #VisitHue #KhamPhaHue",
          group: "#DuLichHue #HueTravel #KhamPhaHue",
          location: "#DaiNoiHue #SongHuong #CauTruongTien #ChoDongBa #ThienMu #PhoTayHue"
        },
        templates: [
          { name:"🎪 Sự kiện Huế cuối tuần", idea:"cuối tuần này Huế có sự kiện gì, phố đi bộ buổi tối", purpose:"sukien", target:"auto" },
          { name:"🍜 Món Huế phải thử", idea:"bún bò, cơm hến, chè Huế, cà phê muối", purpose:"amthuc", target:"auto" },
          { name:"🌧️ Huế mưa chơi gì", idea:"Huế mưa, cà phê nghe nhạc Trịnh, chill", purpose:"thoitiet", target:"auto" },
          { name:"🏯 Một ngày di sản", idea:"Đại Nội đi sớm, lăng Khải Định, chùa Thiên Mụ", purpose:"vanhoa", target:"auto" },
          { name:"📸 Góc sống ảo Huế", idea:"thuê áo dài chụp Đại Nội, cầu Trường Tiền lên đèn", purpose:"checkin", target:"couple" },
          { name:"☀️ Mẹo tránh nắng", idea:"Huế nắng, đi sớm về trưa, chiều dạo sông Hương", purpose:"meo", target:"giadinh" }
        ],
        comments: {
          question: "😋 Mọi người tới Huế mê món nào nhất — bún bò, cơm hến hay chè Huế nè?",
          special: "💜 Lưu bài lại để dành, tới Huế là mở ra xài liền nha.",
          zaloExtra: ""
        }
      }
    };

    const OFFLINE_KNOWLEDGE = {
      updated: "2026-07-30",
      hue: {
        stableFacts: [
          "Huế là kinh đô của Việt Nam thống nhất dưới triều Nguyễn từ năm 1802 đến 1945.",
          "Quần thể Di tích Cố đô Huế được UNESCO ghi danh Di sản Thế giới năm 1993.",
          "Đại Nội gồm khu Hoàng thành và Tử Cấm Thành; Ngọ Môn là cổng chính phía nam của Hoàng thành.",
          "Nhã nhạc là âm nhạc cung đình Việt Nam, gắn với nghi lễ triều đình và được UNESCO ghi danh di sản văn hóa phi vật thể.",
          "Các điểm di sản thường được quan tâm gồm Đại Nội, chùa Thiên Mụ và các lăng Tự Đức, Minh Mạng, Khải Định.",
          "Ẩm thực Huế có cả dòng cung đình và dân gian; chủ đề an toàn gồm bún bò Huế, cơm hến, bánh bèo, bánh nậm, bánh lọc, bánh khoái, nem lụi, chè Huế và món chay.",
          "Sông Hương, cầu Trường Tiền, chợ Đông Ba, cầu đi bộ gỗ lim, đồi Vọng Cảnh, làng hương Thủy Xuân và cầu ngói Thanh Toàn là các chủ đề trải nghiệm quen thuộc."
          ,"Rú Chá là rừng ngập mặn trên vùng đầm phá Tam Giang, phù hợp nội dung thiên nhiên, nhiếp ảnh và du lịch có trách nhiệm."
          ,"Lăng Gia Long, còn gọi Thiên Thọ Lăng, là lăng của vua Gia Long — vị vua sáng lập triều Nguyễn."
          ,"Chèo SUP trên sông Hương là một trải nghiệm vận động ngoài trời; chỉ gợi ý khi điều kiện thời tiết, dòng nước và đơn vị tổ chức phù hợp."
          ,"Bún giấm nuốc là một gợi ý ẩm thực địa phương theo mùa; nuốc không nên được mô tả như sứa nếu chưa giải thích rõ."
          ,"Cà phê cóc là trải nghiệm đời sống địa phương: ghế thấp, không gian bình dân, ngồi quan sát nhịp phố; không tự gắn một quán cụ thể nếu chưa xác minh."
        ],
        planning: [
          "Lịch trình 1 ngày nên gom theo khu: buổi sáng di sản; giữa trưa nghỉ/ăn; chiều sông Hương hoặc điểm cảnh quan; tối cầu Trường Tiền/phố đi bộ nếu phù hợp.",
          "Lịch trình gia đình: giảm số điểm, ưu tiên nghỉ trưa, nước uống và phương án trong nhà.",
          "Lịch trình couple: áo dài/Đại Nội buổi sáng, cà phê hoặc nghỉ trưa, hoàng hôn sông Hương/đồi Vọng Cảnh.",
          "Lịch trình nhóm: điểm check-in, món địa phương, hoạt động tối; tránh hứa thời gian di chuyển khi chưa kiểm tra bản đồ.",
          "Ngày mưa: ưu tiên ẩm thực, cà phê, bảo tàng/không gian có mái che; kiểm tra thông báo mở cửa và ngập trước khi đi.",
          "Ngày nắng nóng: đi sớm, nghỉ giữa trưa, mang nước/nón/kem chống nắng, tiếp tục vào cuối chiều."
        ],
        dynamicRules: [
          "Không tự viết giá vé, giờ mở cửa, lịch biểu diễn, lịch sự kiện hoặc khuyến mãi.",
          "Không tự viết khoảng cách hay thời gian di chuyển từ homestay đến điểm tham quan.",
          "If người dùng chưa nhập tên + ngày + giờ + địa điểm sự kiện, chỉ tạo bài nhắc kiểm tra lịch, không khẳng định có sự kiện.",
          "Thời tiết chỉ dùng khi công cụ đã lấy được dữ liệu thật; nếu không có dữ liệu thì viết mẹo theo điều kiện, không nói 'hôm nay'.",
          "Không gọi một nơi là đẹp nhất, hot nhất, rẻ nhất hoặc gần nhất.",
          "Với điểm bán vé/di sản, nhắc khách kiểm tra trang chính thức trước khi đi."
        ],
        features: [
          { kw:["đại nội là gì","hoàng thành","tử cấm thành"], line:"🏯 Đại Nội gồm Hoàng thành và Tử Cấm Thành — không gian trung tâm của kinh đô triều Nguyễn", short:"Đại Nội và Hoàng thành" },
          { kw:["unesco","di sản thế giới","1993"], line:"📜 Quần thể Di tích Cố đô Huế được UNESCO ghi danh Di sản Thế giới năm 1993", short:"di sản UNESCO tại Huế" },
          { kw:["triều nguyễn","1802","1945","kinh đô"], line:"📜 Huế là kinh đô dưới triều Nguyễn từ năm 1802 đến 1945 — một nền rất hay cho bài kể chuyện di sản", short:"kinh đô triều Nguyễn" },
          { kw:["nhã nhạc","âm nhạc cung đình"], line:"🎶 Nhã nhạc là âm nhạc cung đình Việt Nam gắn với nghi lễ triều đình và là di sản văn hóa phi vật thể UNESCO", short:"Nhã nhạc cung đình Huế" },
          { kw:["gia đình","trẻ em","người lớn tuổi"], line:"👨‍👩‍👧 Đi Huế cùng gia đình nên giảm số điểm, nghỉ giữa trưa và luôn có phương án trong nhà khi nắng hoặc mưa", short:"lịch trình Huế cho gia đình" },
          { kw:["1 ngày","một ngày","24 giờ"], line:"🗺️ Lịch trình một ngày nên gom điểm cùng khu: sáng di sản, trưa nghỉ và ăn món Huế, chiều sông Hương, tối dạo trung tâm", short:"lịch trình Huế một ngày" },
          { kw:["2 ngày","hai ngày","48 giờ"], line:"🗺️ Hai ngày ở Huế có thể tách một ngày trung tâm–Đại Nội và một ngày lăng tẩm–cảnh quan để đỡ chạy nhiều", short:"lịch trình Huế hai ngày" },
          { kw:["mưa lớn","ngập","bão"], line:"🌧️ Khi mưa lớn, cần kiểm tra cảnh báo địa phương, tình trạng đường và thông báo mở cửa; an toàn quan trọng hơn lịch check-in", short:"an toàn khi Huế mưa lớn" },
          { kw:["giờ mở cửa","giá vé","vé đại nội","vé lăng"], line:"🎟️ Giá vé và giờ tham quan có thể thay đổi — kiểm tra trang chính thức của Trung tâm Bảo tồn Di tích Cố đô Huế trước khi đăng", short:"kiểm tra vé và giờ tham quan" }
          ,{ kw:["sup","chèo sup","ván chèo"], line:"🏄 Chèo SUP trên sông Hương cho một góc nhìn rất khác về Huế; cần kiểm tra thời tiết, an toàn mặt nước và đơn vị tổ chức trước khi đi", short:"chèo SUP sông Hương" }
          ,{ kw:["rú chá","ru cha","rừng ngập mặn"], line:"🌿 Rú Chá là không gian rừng ngập mặn bên vùng đầm phá Tam Giang — hợp đi chậm, chụp ảnh và giữ gìn hệ sinh thái", short:"rừng ngập mặn Rú Chá" }
          ,{ kw:["gia long","lăng gia long","thiên thọ lăng"], line:"⛩️ Lăng Gia Long (Thiên Thọ Lăng) là lăng của vị vua sáng lập triều Nguyễn — không gian rộng, gắn kiến trúc với cảnh quan", short:"Lăng Gia Long" }
          ,{ kw:["bún giấm nuốc","giấm nuốc","nuốc"], line:"🍜 Bún giấm nuốc là món địa phương theo mùa, hấp dẫn ở vị chua thanh và độ giòn mát — nên kiểm tra quán còn bán trước khi giới thiệu", short:"bún giấm nuốc Huế" }
          ,{ kw:["cafe cóc","cà phê cóc","cafe vỉa hè","cà phê vỉa hè"], line:"☕ Cà phê cóc là cách chạm vào nhịp sống Huế rất đời thường: ngồi ghế thấp, nhìn phố chậm trôi và nghe chuyện người địa phương", short:"cà phê cóc Huế" }
        ],
        chips: [
          "Huế 1 ngày: sáng di sản, trưa nghỉ, chiều sông Hương",
          "Huế 2 ngày: tách Đại Nội và tuyến lăng tẩm",
          "đi Huế cùng gia đình, lịch nhẹ và có nghỉ trưa",
          "Đại Nội gồm Hoàng thành và Tử Cấm Thành",
          "Huế mưa: kiểm tra cảnh báo, ưu tiên điểm trong nhà",
          "giá vé và giờ mở cửa: luôn kiểm tra nguồn chính thức"
          ,"chèo SUP sông Hương, kiểm tra thời tiết và an toàn"
          ,"Rú Chá, rừng ngập mặn và du lịch có trách nhiệm"
          ,"Lăng Gia Long, vị vua sáng lập triều Nguyễn"
          ,"bún giấm nuốc Huế, món địa phương theo mùa"
          ,"cà phê cóc, ngồi nhìn nhịp phố Huế"
        ],
        templates: [
          { name:"🗺️ Huế 2 ngày dễ đi", idea:"lịch trình Huế 2 ngày, gom điểm cùng khu, có nghỉ trưa, không bịa thời gian di chuyển", purpose:"meo", target:"khach" },
          { name:"👨‍👩‍👧 Huế cho gia đình", idea:"đi Huế cùng gia đình, lịch nhẹ, nghỉ giữa trưa, có phương án khi mưa", purpose:"meo", target:"giadinh" },
          { name:"📜 Kể chuyện Cố đô", idea:"Huế là kinh đô triều Nguyễn 1802–1945, Quần thể Di tích Cố đô Huế UNESCO 1993", purpose:"vanhoa", target:"khach" },
          { name:"🎶 Nhã nhạc cung đình", idea:"Nhã nhạc cung đình Huế, nghi lễ triều đình, di sản văn hóa phi vật thể UNESCO", purpose:"vanhoa", target:"khach" }
          ,{ name:"🏄 Huế nhìn từ mặt nước", idea:"chèo SUP sông Hương, bình minh hoặc chiều mát, kiểm tra thời tiết và an toàn", purpose:"meo", target:"nhom" }
          ,{ name:"🌿 Một chiều Rú Chá", idea:"Rú Chá, rừng ngập mặn, đi chậm, chụp ảnh, giữ vệ sinh và bảo vệ hệ sinh thái", purpose:"checkin", target:"couple" }
          ,{ name:"⛩️ Lăng Gia Long sâu hơn", idea:"Lăng Gia Long hay Thiên Thọ Lăng, vua sáng lập triều Nguyễn, kiến trúc hòa vào cảnh quan", purpose:"vanhoa", target:"khach" }
          ,{ name:"🍜 Món Huế người địa phương", idea:"bún giấm nuốc theo mùa, cà phê cóc, trải nghiệm đời sống địa phương, không bịa địa chỉ quán", purpose:"amthuc", target:"khach" }
        ]
      },
      lacasa: {
        facts: [
          "Địa chỉ: Số 3 kiệt 17 Trần Phú, TP. Huế.",
          "Phòng riêng có giường Queen; dorm 4 và 8 giường.",
          "Mỗi giường dorm có rèm riêng tư, đèn ngủ riêng và tủ lớn có khóa; khu dorm có 3 WC.",
          "Có sân vườn, khu BBQ chung miễn phí, bếp và phòng khách/khu sinh hoạt chung.",
          "Tiện nghi được xác nhận: máy lạnh, nước nóng, tủ lạnh, bàn ủi, máy sấy tóc và máy lọc không khí.",
          "Hỗ trợ check-in sớm tùy tình trạng phòng; không được hứa chắc.",
          "Phù hợp khách solo/backpacker, nhóm bạn, couple và gia đình nhỏ."
        ],
        rules: [
          "Không tự gán tiện nghi dorm cho phòng riêng hoặc ngược lại.",
          "Không nói đi bộ/vài phút/gần một điểm cụ thể nếu chưa kiểm tra bản đồ.",
          "Không tự bịa số giường trống, giá hoặc tình trạng còn phòng."
        ]
      },
      umee: {
        facts: [
          "Địa chỉ: SH44 – Manor Crown, 62 Tố Hữu, TP. Huế.",
          "Phòng riêng có giường King và máy chiếu Netflix 100 inch.",
          "Một số phòng có bồn tắm; một số phòng có ban công và bếp nhỏ.",
          "Có bãi đỗ ô tô miễn phí trước cửa và self check-in/out 24/7.",
          "Dịch vụ được xác nhận: thuê xe máy, đón/trả khách, giặt là và dọn phòng hằng ngày.",
          "Bể bơi 4 mùa trong nhà ở tầng 6 của tòa nhà và có phụ phí.",
          "Phù hợp couple, gia đình và nhóm; có hình thức nghỉ theo giờ và theo ngày."
        ],
        rules: [
          "Chỉ nói bồn tắm, ban công hoặc bếp nhỏ khi đúng loại phòng/mục người dùng đã chọn.",
          "Bài dorm/nhóm không tự gắn giường King, bồn tắm hoặc tiện nghi phòng riêng.",
          "Không tự bịa số phòng trống, giá hoặc tình trạng còn phòng."
        ]
      }
    };

    const EMOTIONAL_SELLING = {
      sleep: {
        lacasa:"Không chỉ là một chiếc giường — là cảm giác khép cửa lại, nghe mọi thứ dịu xuống và ngủ một giấc thật sâu.",
        umee:"Điều UMEE muốn giữ cho bạn không chỉ là căn phòng đẹp, mà là một đêm nằm thật rộng, xem bộ phim mình thích rồi ngủ quên lúc nào không hay.",
        hue:"Đi Huế chậm một nhịp, để tối về ngủ sâu và sáng dậy còn đủ năng lượng khám phá tiếp."
      },
      morning: {
        lacasa:"Buổi sáng ở Lacasa bắt đầu chậm: chút ánh sáng, khoảng vườn xanh và cảm giác chưa cần vội đi đâu.",
        umee:"Một buổi sáng không báo thức gấp gáp — kéo rèm, nằm thêm vài phút trên giường King rồi mới nghĩ xem hôm nay đi đâu.",
        hue:"Huế đẹp nhất đôi khi chỉ là một buổi sáng thức dậy sớm, phố còn nhẹ và mình chưa cần chạy theo lịch trình."
      },
      healing: {
        lacasa:"Lacasa bán một khoảng nghỉ: cây xanh, sự yên tĩnh và cảm giác được thở chậm lại sau những ngày quá nhiều tiếng ồn.",
        umee:"UMEE là khoảng riêng để tắt bớt thông báo, bật một bộ phim và cho bản thân một buổi tối không phải cố gắng gì.",
        hue:"Chữa lành ở Huế không cần điều gì lớn — chỉ cần đi chậm bên sông, ăn một món quen và cho mình một buổi chiều không lịch."
      },
      together: {
        lacasa:"Điều đáng nhớ không chỉ là căn phòng, mà là buổi tối cả nhóm ngồi với nhau ngoài vườn và kể những câu chuyện lâu rồi chưa kể.",
        umee:"Một bộ phim, một chiếc giường rộng và người mình thương ở bên — đôi khi chuyến đi đáng nhớ chỉ cần vậy.",
        hue:"Huế là cái nền dịu dàng để những người đi cùng nhau có thêm một kỷ niệm thật lâu."
      },
      freedom: {
        lacasa:"Đi chơi mệt thì về nghỉ, đói thì vào bếp, muốn ngồi yên thì ra vườn — một nơi ở khiến lịch trình nhẹ đầu hơn.",
        umee:"Tới muộn vẫn tự check-in, muốn xem phim thì bật máy chiếu, muốn ngủ thì kéo rèm — chuyến đi được trả lại cho nhịp riêng của bạn.",
        hue:"Không cần chạy đủ điểm; Huế hợp với một lịch trình vừa đủ và quyền đổi ý giữa đường."
      }
    };

    const SHARED_NOTES = `<h3>✅ Chuẩn chính sách Facebook (cả Lacasa & UMEE)</h3><ul>
      <li><span class="ok">Nên:</span> CTA về inbox/Zalo. SĐT duy nhất: <b>0905 555 317</b>.</li>
      <li><span class="bad">Tránh:</span> "tag 3 người bạn", "comment số 1", "share nhận quà" — đây là kiểu engagement bait nên tránh.</li>
      <li><span class="bad">Tránh:</span> "rẻ nhất", "số 1", "best", "nhất Huế", cam kết quá đà, review giả, giục giả ("chỉ còn 1 phòng" khi không đúng).</li>
      <li><span class="ok">Nên:</span> mỗi group 1 bản khác nhau — hub tạo sẵn 4 bản/lần. Giãn vài group/ngày.</li>
      <li><span class="bad">Tránh:</span> nhắc Booking, Agoda, Airbnb, Traveloka — mọi bài chỉ dẫn về inbox/Zalo.</li></ul>
      <h3>🔎 Chuẩn SEO Facebook (cả 2)</h3><ul>
      <li>Dòng đầu luôn có <b>"Homestay Huế"</b> hoặc "đi Huế" — hub tự làm.</li>
      <li>Gắn <b>Location = Hue, Vietnam</b> cho mọi post & reel; reel thêm topics Travel/Hue.</li>
      <li>Hashtag: bài chính 5–8 · group 3–5 · reel 5–12 (tab Hashtag có sẵn từng bộ).</li>
      <li>Tên – địa chỉ – SĐT y hệt mọi nơi: Lacasa (Số 3 kiệt 17 Trần Phú) · UMEE (SH44 – Manor Crown, 62 Tố Hữu).</li>
      <li>Comment đầu nên bổ sung thông tin thật hoặc trả lời câu hỏi thường gặp; không dùng engagement bait.</li></ul>
      <h3>🌿 Quy tắc riêng Lacasa</h3><ul>
      <li>Check-in sớm luôn viết: <b>"hỗ trợ check-in sớm tùy tình trạng phòng"</b> — không hứa chắc.</li>
      <li>Dorm: nhớ khoe rèm riêng tư, đèn đọc sách, tủ khoá, 3 WC riêng. Giá dorm chỉ ghi <b>"từ 1xx/người"</b>.</li>
      <li>Điểm đến nên nhắc: Đại Nội, cầu Trường Tiền, sông Hương, phố Tây, cung An Định. Không tự nhấn "gần ga" trừ khi mình chủ động nhập.</li></ul>
      <h3>🚫 Quy tắc riêng UMEE</h3><ul>
      <li>Bể bơi luôn ghi: <b>"bể bơi 4 mùa tầng 6 của tòa nhà, có phụ phí"</b>.</li>
      <li>Bài dorm/nhóm không gắn nhầm giường King/bồn tắm của phòng riêng.</li></ul>
      <h3>🔗 Kênh chính thức (để gắn/tham chiếu)</h3><ul>
      <li><b>Lacasa:</b> fb.com/lacasahomestayinvietnam · TikTok @lacasahomestayhue · lacasahomestay.com · Maps: maps.app.goo.gl/yatorSbnQBytZCEk9</li>
      <li><b>UMEE:</b> fb.com/umeehomestay · TikTok @umee.homestay · umeehomestay.com · Maps: maps.app.goo.gl/YvhzxAjYBoJ2QqUX6</li>
      <li>Chỉ dùng link chính thức khi thật sự giúp khách xem đường, ảnh hoặc thông tin phòng.</li></ul>
      <h3>📌 Cách dùng an toàn</h3><ul>
      <li>Ưu tiên ảnh/reel thật, rõ nét và đúng loại phòng đang giới thiệu.</li>
      <li>Thử các khung giờ khác nhau rồi dùng số liệu tài khoản của chính mình để chọn lịch đăng.</li>
      <li>Trả lời comment/inbox sớm khi có thể để khách nhận được thông tin chính xác.</li></ul>`;

    let currentHubBrand = "lacasa";
    let selectedHubRooms = [];
    let hubBrandDrafts = { lacasa: null, umee: null, hue: null };
    let savedHubContent = { lacasa: null, umee: null, hue: null };

    // DOM selectors for Hub
    const hubIdea = document.getElementById('idea');
    const hubPurpose = document.getElementById('purpose');
    const hubDate = document.getElementById('fDate');
    const hubRoom = document.getElementById('fRoom');
    const hubCount = document.getElementById('fCount');
    const hubPrice = document.getElementById('fPrice');
    const hubGuest = document.getElementById('fGuest');
    const hubNote = document.getElementById('fNote');
    const hubPlatform = document.getElementById('platform');
    const hubEmotion = document.getElementById('emotion');
    const hubTarget = document.getElementById('target');
    const hubTone = document.getElementById('tone');
    const hubLength = document.getElementById('length');
    const hubCta = document.getElementById('cta');
    const hubRoomCard = document.getElementById('roomCard');
    const hubRoomChips = document.getElementById('roomChips');
    const hubIdeaChips = document.getElementById('chips');

    const hubGenBtn = document.getElementById('genBtn');
    const hubGenOffBtn = document.getElementById('genOffBtn');
    const hubStatus = document.getElementById('status');

    function getHubBrand() {
        return BRANDS[currentHubBrand];
      }

    function ideaParts() {
        return (hubIdea ? hubIdea.value : "").split(/[,;\n]+/).map(s => s.trim()).filter(Boolean);
    }
    
    function chipKey(s) {
        return String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/đ/g,"d").replace(/Đ/g,"D").toLowerCase().replace(/\s+/g," ").trim();
    }
    
    function syncIdeaChips() {
        const keys = ideaParts().map(chipKey);
        document.querySelectorAll('#chips .chip').forEach(d => {
          const on = keys.indexOf(chipKey(d.dataset.value)) !== -1;
          d.classList.toggle('on', on);
        });
    }
    
    function toggleIdeaChip(value) {
        let parts = ideaParts();
        const key = chipKey(value);
        const found = parts.some(p => chipKey(p) === key);
        parts = parts.filter(p => chipKey(p) !== key);
        if (!found) parts.push(value);
        hubIdea.value = parts.join(", ");
        syncIdeaChips();
    }

    function renderRoomChips() {
        const b = getHubBrand();
        if (!hubRoomChips) return;
        hubRoomChips.innerHTML = "";
        (b.rooms || []).forEach(rm => {
          const d = document.createElement("div");
          const isSelected = selectedHubRooms.indexOf(rm) !== -1;
          d.className = "chip" + (isSelected ? " on" : "");
          d.textContent = rm.label;
          d.onclick = () => {
            const i = selectedHubRooms.indexOf(rm);
            if (i === -1) selectedHubRooms.push(rm); else selectedHubRooms.splice(i,1);
            renderRoomChips();
          };
          hubRoomChips.appendChild(d);
        });
    }

    function renderTemplates() {
        const b = getHubBrand();
        const box = document.getElementById('tplList'); 
        box.innerHTML = "";
        b.templates.forEach(t => {
          const row = document.createElement('div'); 
          row.className = 'titleopt';
          row.innerHTML = `<span>${t.name}</span><button class="btn btn-secondary btn-sm">Dùng mẫu</button>`;
          row.querySelector('button').onclick = () => {
            hubIdea.value = t.idea;
            hubPurpose.value = t.purpose;
            hubTarget.value = t.target;
            syncIdeaChips();
            document.querySelector('#hub-tabbar button[data-tab="0"]').click();
            hubStatus.textContent = "✅ Đã điền mẫu — hãy bấm Tạo nội dung nha.";
          };
          box.appendChild(row);
        });
    }

    function renderHashtags() {
        const b = getHubBrand();
        const s = document.getElementById('hashtagSection');
        const sets = [
          ["A. Bộ ngắn cho bài Page (5–8 tag)", b.hashSets.short],
          ["B. Bộ đầy đủ khám phá (20–35 tag)", b.hashSets.full],
          ["C. Bộ cho Reel (5–12 tag)", b.hashSets.reel],
          ["D. Bộ cho bài Group (3–5 tag)", b.hashSets.group],
          ["E. Bộ địa danh Huế", b.hashSets.location]
        ];
        let html = `<div class="card"><div class="label">Hashtag Center — ${b.reelBrand}</div>
          <p class="hint">Page 5–8 · Group 3–5 · Reel 5–12.</p></div>`;
        sets.forEach((st, i) => {
          html += `<div class="card"><div class="label">${st[0]}</div>
            <div class="post" id="hs${i}">${st[1]}</div>
            <button class="copy btn btn-secondary btn-sm" onclick="copyTextToClipboard('${st[1]}', this)">📋 Copy bộ này</button></div>`;
        });
        s.innerHTML = html;
    }

    window.copyTextToClipboard = function(text, btn) {
        navigator.clipboard.writeText(text).then(() => {
            const oldText = btn.innerHTML;
            btn.innerHTML = '✅ Đã Copy';
            setTimeout(() => { btn.innerHTML = oldText; }, 1500);
        });
    }

    window.copyEl = function(id, btn) {
        const text = document.getElementById(id).innerText;
        if (!text || text.includes("Chưa có nội dung")) return;
        window.copyTextToClipboard(text, btn);
    }

    function renderPurposes() {
        const b = getHubBrand();
        hubPurpose.innerHTML = "";
        const SALE_PURPOSES = [
          ["auto","Tự chọn theo ý chính"],["conphong","Còn phòng hôm nay"],["cuoituan","Còn phòng cuối tuần"],
          ["uudai","Ưu đãi / giá tốt"],["dorm","Dorm cho nhóm bạn"],["couple","Phòng riêng cho couple"],
          ["solo","Khách solo / backpacker"],["giadinh","Gia đình nhỏ"],["review","Review khách cũ"],
          ["lichtrinh","Gợi ý lịch trình Huế"],["reel","Reel ngắn"],["story","Story ngắn"],["inbox","Đẩy inbox / khách trực tiếp"]
        ];
        (b.purposes || SALE_PURPOSES).forEach(p => {
          const o = document.createElement("option"); 
          o.value = p[0]; 
          o.textContent = p[1];
          hubPurpose.appendChild(o);
        });
    }

    function switchHubBrand(brand) {
        currentHubBrand = brand;
        const b = getHubBrand();
        
        // Apply CSS Theme variables
        document.documentElement.style.setProperty('--p', b.theme.p);
        document.documentElement.style.setProperty('--pd', b.theme.pd);
        document.documentElement.style.setProperty('--bg', b.theme.bg);
        document.documentElement.style.setProperty('--border', b.theme.border);
        document.documentElement.style.setProperty('--text', b.theme.text);
        document.documentElement.style.setProperty('--muted', b.theme.muted);
        document.documentElement.style.setProperty('--accent', b.theme.accent);

        document.getElementById('brandLacasa').classList.toggle('active', brand === 'lacasa');
        document.getElementById('brandUmee').classList.toggle('active', brand === 'umee');
        document.getElementById('brandHue').classList.toggle('active', brand === 'hue');

        hubRoomCard.style.display = b.isPlace ? 'none' : 'block';
        renderPurposes();

        // Render Idea Chips
        hubIdeaChips.innerHTML = "";
        b.chips.forEach(c => {
          const d = document.createElement('button'); 
          d.type = 'button'; 
          d.className = 'chip'; 
          d.textContent = c;
          d.dataset.value = c; 
          d.onclick = (e) => { e.preventDefault(); toggleIdeaChip(c); };
          hubIdeaChips.appendChild(d);
        });
        syncIdeaChips();

        // Target settings
        hubTarget.innerHTML = "";
        b.targets.forEach(t => {
          const o = document.createElement('option'); 
          o.value = t[0]; 
          o.textContent = t[1];
          hubTarget.appendChild(o);
        });

        selectedHubRooms = [];
        renderRoomChips();
        renderTemplates();
        renderHashtags();
        renderHistory();
        document.getElementById('notes').innerHTML = SHARED_NOTES;

        if (savedHubContent[brand]) {
            applyHubContent(savedHubContent[brand]);
            renderScore(savedHubContent[brand]);
        } else {
            clearHubContent();
            renderScoreEmpty();
        }
        hubStatus.textContent = "";
    }

    // Brand clicks binding
    document.getElementById('brandLacasa').onclick = () => switchHubBrand('lacasa');
    document.getElementById('brandUmee').onclick = () => switchHubBrand('umee');
    document.getElementById('brandHue').onclick = () => switchHubBrand('hue');

    // Sub-tabbar clicks binding
    document.querySelectorAll('#hub-tabbar .tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('#hub-tabbar .tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Hide all sub sections
            document.querySelectorAll('.hub-section').forEach(sec => sec.classList.remove('active'));
            document.getElementById(`hub-sec-${tab.dataset.tab}`).classList.add('active');
        });
    });

    function clearHubContent() {
        document.getElementById('main').innerHTML = '<span class="empty">Chưa có nội dung. Qua tab ✨ Tạo bài trước nha.</span>';
        ['grp1','grp2','grp3','grp4'].forEach(id => {
          document.getElementById(id).innerHTML = '<span class="empty">Chưa có nội dung.</span>';
        });
        document.getElementById('reeldesc').innerHTML = '<span class="empty">Chưa có nội dung.</span>';
        document.getElementById('story').innerHTML = '<span class="empty">Chưa có nội dung.</span>';
        const reelCount = document.getElementById('reelcount');
        const storyCount = document.getElementById('storycount');
        if (reelCount) reelCount.textContent = "";
        if (storyCount) storyCount.textContent = "";
        document.getElementById('titles').innerHTML = '<span class="empty">Chưa có nội dung.</span>';
    }

    function applyHubContent(a) {
        document.getElementById('main').innerText = a.main || "";
        document.getElementById('grp1').innerText = a.grp1 || "";
        document.getElementById('grp2').innerText = a.grp2 || "";
        document.getElementById('grp3').innerText = a.grp3 || "";
        document.getElementById('grp4').innerText = a.grp4 || "";
        
        const desc = a.reeldesc || "";
        document.getElementById('reeldesc').innerText = desc;
        const reelCount = document.getElementById('reelcount');
        if (reelCount) reelCount.innerText = `${desc.length}/255 ký tự`;
        
        const st = a.story || "";
        document.getElementById('story').innerText = st;
        const storyCount = document.getElementById('storycount');
        if (storyCount) storyCount.innerText = `${st.length}/120 ký tự`;
        
        const t = document.getElementById('titles'); 
        t.innerHTML = "";
        (a.titles || []).forEach(title => {
          const row = document.createElement('div'); 
          row.className = 'titleopt';
          row.innerHTML = `<span>${title}</span><button class="btn btn-secondary btn-sm">Copy</button>`;
          row.querySelector('button').onclick = (e) => { window.copyTextToClipboard(title, e.target); };
          t.appendChild(row);
        });

        // First comment rendering
        renderComments(a);
    }

    function renderComments(content) {
        const b = getHubBrand();
        const cm = document.getElementById('comments'); 
        cm.innerHTML = "";
        const meta = content && content.meta ? content.meta : {};
        const mainText = content && content.main ? content.main : "";
        const top1 = meta.top1 || (b.isPlace ? "một trải nghiệm địa phương" : "không gian nghỉ");
        const short2 = meta.short2 || "";
        const target = meta.target || b.targetText.autoDefault;
        
        // Extract emotional Selling lines
        let emotional = "";
        const emoKey = meta.emotion || "auto";
        if (EMOTIONAL_SELLING[emoKey] && EMOTIONAL_SELLING[emoKey][currentHubBrand]) {
            emotional = EMOTIONAL_SELLING[emoKey][currentHubBrand];
        }

        let list = [];
        if (b.isPlace) {
          list = [
            `Nếu chỉ có một buổi ở Huế, bạn sẽ chọn ${top1} hay dành thời gian đi chậm quanh sông Hương?`,
            `${top1.charAt(0).toUpperCase() + top1.slice(1)} hợp với người thích nhìn Huế ở một góc bớt quen hơn. Trước khi đi, nhớ kiểm tra thời tiết.`,
            short2 ? `Có thể ghép ${top1} với ${short2} trong cùng chủ đề.` : "Ở Huế, lịch trình vừa đủ thường dễ nhớ hơn một ngày chạy thật nhiều điểm.",
            emotional,
            "Mẹo nhỏ: gom các điểm cùng khu, nghỉ giữa trưa và để trống một khoảng cho những nơi tình cờ bắt gặp.",
            "Thông tin sự kiện, giá vé và giờ mở cửa có thể thay đổi. Mình luôn khuyên kiểm tra nguồn chính thức trước khi xuất phát.",
            "Cần một chỗ nghỉ khi tới Huế, bạn có thể nhắn Zalo 0905 555 317.",
            b.hashSets.group + " #HueLocal"
          ];
        } else {
          const truthfulDetail = short2 ? `${top1} và ${short2}` : top1;
          list = [
            `Chi tiết trong bài mình muốn nhấn mạnh nhất là ${truthfulDetail}. Đây là thông tin thật của loại phòng đang nói tới.`,
            emotional,
            "Nếu bạn gửi ngày ở, số người và nhu cầu chính, mình sẽ kiểm tra đúng phòng thay vì gửi một bảng giá chung.",
            `Phòng này phù hợp với ${target}.`,
            `Muốn xem ảnh thật của ${top1}, nhắn Zalo ${b.phone}.`,
            currentHubBrand === "lacasa"
              ? "Lacasa hỗ trợ check-in sớm tùy tình trạng phòng. Bạn báo giờ đến dự kiến để mình kiểm tra trước."
              : "UMEE có self check-in/out 24/7. Tiện nghi tùy từng phòng.",
            `Địa chỉ: ${b.addr.replace("🏡 ","")}.`
          ];
        }

        list.forEach(c => {
          const row = document.createElement('div'); 
          row.className = 'titleopt';
          row.innerHTML = `<span>${c}</span><button class="btn btn-secondary btn-sm">Copy</button>`;
          row.querySelector('button').onclick = (e) => { window.copyTextToClipboard(c, e.target); };
          cm.appendChild(row);
        });
    }

    // Local Generation (Fallback offline generator)
    function generateLocal(f) {
        const b = getHubBrand();
        const roomText = (f.roomNames && f.roomNames.length) ? f.roomNames.join(" + ") : f.room;
        const ideaAll = [f.idea, roomText, f.roomAttrs, f.note].filter(Boolean).join(", ") || "sân vườn chill, phòng sạch mát";
        
        let lines = [];
        let shorts = [];
        const used = {};

        // Auto match points
        const splitPhrases = (str) => str.split(/[,;\n]+/).map(s => s.trim()).filter(Boolean);
        const vn = (s) => String(s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d");

        splitPhrases([f.idea, f.roomAttrs].filter(Boolean).join(", ")).forEach(p => {
          let matchedAny = false;
          b.features.forEach(ft => {
            for (let i = 0; i < ft.kw.length; i++){
              if (vn(p).includes(vn(ft.kw[i]))) {
                matchedAny = true;
                if (!used[ft.short]) { used[ft.short] = 1; lines.push(ft.line); shorts.push(ft.short); }
                break;
              }
            }
          });
          if (!matchedAny && p.length > 1) { lines.push(`✨ ${p.charAt(0).toUpperCase() + p.slice(1)}`); shorts.push(p.toLowerCase()); }
        });

        if (!lines.length) {
            lines.push(b.features[0].line);
            shorts.push(b.features[0].short);
        }

        if (f.weatherLine) lines.unshift(`🌤️ ${f.weatherLine}`);
        
        let saleBits = [];
        if (f.date) saleBits.push(f.date);
        if (roomText) saleBits.push(`còn ${f.count ? f.count + " " : ""}${roomText}`);
        if (saleBits.length) lines.unshift(`📅 ${saleBits.join(" — ")}`);

        if (f.price) lines.push(`💰 Giá: ${f.price}`);
        
        const maxLines = f.length === "ngan" ? 3 : (f.length === "dai" ? 7 : 4);
        lines = lines.slice(0, maxLines);

        const target = f.target === "auto" ? b.targetText.autoDefault : b.targetText[f.target];
        const emotional = EMOTIONAL_SELLING[f.emotion === 'auto' ? 'healing' : f.emotion]?.[currentHubBrand] || "";

        const hook = `${b.isPlace ? 'Gợi ý du lịch Huế' : b.name} - ${shorts[0]}`;
        const main = `${hook}\n\n${emotional}\n\n${lines.join('\n')}\n\n${b.addr}\nZalo: ${b.phone}\n\n${b.tagMain}`;

        const grp1 = `📌 Bài Group 1:\n\n${b.name} - ${shorts[0]}\n\n${lines.join('\n')}\n\nZalo: ${b.phone}\n\n${b.tagGrp}`;
        const grp2 = `📌 Bài Group 2:\n\n${b.name} - ${shorts[0]}\n\n${lines.join('\n')}\n\nZalo: ${b.phone}\n\n${b.tagGrp}`;
        const grp3 = `📌 Bài Group 3:\n\n${b.name} - ${shorts[0]}\n\n${lines.join('\n')}\n\nZalo: ${b.phone}\n\n${b.tagGrp}`;
        const grp4 = `📌 Bài Group 4:\n\n${b.name} - ${shorts[0]}\n\n${lines.join('\n')}\n\nZalo: ${b.phone}\n\n${b.tagGrp}`;

        const titles = [`${b.name} - ${shorts[0]}`, `${b.name} - ${shorts[0]} #2`];
        const reeldesc = `${b.name} - ${shorts[0]}\n\nZalo: ${b.phone}\n${b.tagReel}`;
        const story = `${b.name} - ${shorts[0]}`;

        return { main, grp1, grp2, grp3, grp4, titles, reeldesc, story, meta: { top1: shorts[0], target, emotion: f.emotion } };
    }

    // AI Generation Call
    async function generateAI(f) {
        // Construct the prompt for Claude
        const prompt = buildAIPrompt(f);
        
        const response = await fetch('/api/content/generate', {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt })
        });
        
        const data = await response.json();
        if (!response.ok || data.type === 'error') throw new Error(data.error?.message || data.error || 'AI API Error');
        
        let text = (data.content || []).map(bk => bk.text || "").join("").trim();
        text = text.replace(/```json/gi, "").replace(/```/g, "").trim();
        
        const s = text.indexOf("{"), e = text.lastIndexOf("}");
        if (s === -1 || e === -1) throw new Error("AI output missing JSON structure");
        
        const obj = JSON.parse(text.slice(s, e + 1));
        obj.meta = { top1: f.idea.split(',')[0], target: f.target, emotion: f.emotion };
        return obj;
    }

    function buildAIPrompt(f) {
      const b = getHubBrand();
      const targetTxt = f.target === "auto" ? "tự chọn hợp lý theo ý chính" : (b.targetText[f.target] || "tự chọn");
      const toneTxt = f.tone;
      const lenTxt = f.length;
      
      const facts = b.isPlace ? "Bài viết VỀ HUẾ: sự kiện, ẩm thực, lăng tẩm, sông Hương." : JSON.stringify(OFFLINE_KNOWLEDGE[currentHubBrand]);
      
      return `Bạn là người viết content tự nhiên cho homestay ${b.name} tại Huế.
      Ý CHÍNH: ${f.idea}.
      MỤC ĐÍCH: ${f.purpose}.
      ĐỐI TƯỢNG: ${targetTxt}.
      TÔNG GIỌNG: ${toneTxt}.
      ĐỘ DÀI: ${lenTxt}.
      SỰ THẬT ĐÃ XÁC MINH: ${facts}.
      Trả về duy nhất 1 JSON không markdown: {"main":"bài chính","grp1":"group 1","grp2":"group 2","grp3":"group 3","grp4":"group 4","titles":["tiêu đề 1","tiêu đề 2","tiêu đề 3"],"reeldesc":"mô tả reel","story":"story ngắn"}`;
    }

    // Trigger generate
    async function runGeneration(mode) {
        const f = {
            idea: hubIdea.value.trim(),
            purpose: hubPurpose.value,
            date: hubDate.value.trim(),
            room: hubRoom.value.trim(),
            roomNames: selectedHubRooms.map(r => r.sale),
            roomAttrs: selectedHubRooms.map(r => r.attrs).join(', '),
            count: hubCount.value.trim(),
            price: hubPrice.value.trim(),
            guest: hubGuest.value.trim(),
            note: hubNote.value.trim(),
            platform: hubPlatform.value,
            emotion: hubEmotion.value,
            target: hubTarget.value,
            tone: hubTone.value,
            length: hubLength.value,
            cta: hubCta.value
        };

        if (!f.idea && f.purpose === 'auto') {
            showToast('Vui lòng điền ý chính hoặc chọn mục đích!', 'error');
            return;
        }

        hubStatus.textContent = "⏳ Đang xử lý tạo bài viết...";
        hubGenBtn.disabled = true;
        hubGenOffBtn.disabled = true;

        // Fetch weather if selected
        if (f.idea.toLowerCase().includes('thời tiết') || f.purpose === 'thoitiet') {
            try {
                const wRes = await fetch("https://api.open-meteo.com/v1/forecast?latitude=16.4637&longitude=107.5909&current=temperature_2m&timezone=Asia%2FHo_Chi_Minh");
                const wData = await wRes.json();
                f.weatherLine = `Thời tiết Huế hôm nay: ${wData.current.temperature_2m}°C`;
            } catch (err) {
                f.weatherLine = "Thời tiết Huế hôm nay rất mát mẻ";
            }
        }

        try {
            if (mode === 'offline') {
                const res = generateLocal(f);
                finishHubGen(res, 'offline');
            } else {
                const res = await generateAI(f);
                finishHubGen(res, 'ai');
            }
        } catch (err) {
            console.error(err);
            // Fallback offline
            showToast('Lỗi AI, tự động chuyển chế độ Offline!', 'error');
            const res = generateLocal(f);
            finishHubGen(res, 'offline');
        } finally {
            hubGenBtn.disabled = false;
            hubGenOffBtn.disabled = false;
        }
    }

    function finishHubGen(res, mode) {
        savedHubContent[currentHubBrand] = res;
        applyHubContent(res);
        renderScore(res);
        addHistory(res, getFormValues());
        hubStatus.textContent = `✅ Đã tạo thành công (${mode === 'ai' ? 'AI Sonnet 5' : 'Offline'}). Hãy chuyển các tab bên trên để xem.`;
        showToast('Tạo nội dung bài đăng thành công!');
    }

    function getFormValues() {
        return {
            purpose: hubPurpose.value,
            idea: hubIdea.value.trim()
        };
    }

    hubGenBtn.onclick = () => runGeneration('ai');
    hubGenOffBtn.onclick = () => runGeneration('offline');

    // Score and audit logic
    function scoreContent(c) {
        let score = 100;
        let checks = [];
        
        const main = c.main || "";
        const low = main.toLowerCase();

        // Clean checks
        if (!low.includes('huế')) {
            score -= 15;
            checks.push({ ok: false, msg: "Thiếu từ khóa 'Huế' ở dòng đầu tiên (Cần cho SEO)" });
        } else {
            checks.push({ ok: true, msg: "Đã có từ khóa 'Huế' ở đầu bài" });
        }

        const otaHit = ["booking", "agoda", "airbnb", "traveloka"].filter(w => low.includes(w));
        if (otaHit.length > 0) {
            score -= 20;
            checks.push({ ok: false, msg: `Chứa từ khóa đặt phòng OTA cấm: ${otaHit.join(', ')}` });
        } else {
            checks.push({ ok: true, msg: "Không chứa liên kết đặt phòng OTA" });
        }

        const bannedHits = ["số 1", "nhất huế", "rẻ nhất"].filter(w => low.includes(w));
        if (bannedHits.length > 0) {
            score -= 15;
            checks.push({ ok: false, msg: `Chứa từ ngữ phóng đại cấm: ${bannedHits.join(', ')}` });
        } else {
            checks.push({ ok: true, msg: "Không chứa các tuyên bố phóng đại" });
        }

        if (score < 0) score = 0;
        return { score, checks };
    }

    function renderScore(c) {
        const r = scoreContent(c);
        c.scoreVal = r.score;
        const scoreBody = document.getElementById('scoreBody');
        
        const badge = r.score >= 90 ? '<span class="badge g">✅ Sẵn sàng đăng</span>'
          : r.score >= 70 ? '<span class="badge w">⚠️ Nên xem lại</span>'
          : '<span class="badge b">❌ Cần sửa lỗi</span>';

        let html = `<div class="scorehead"><div class="scorenum">${r.score}<span style="font-size:14px;color:var(--fb-text-secondary);">/100</span></div>${badge}</div>`;
        
        r.checks.forEach(ch => {
            html += `<div class="issue">${ch.ok ? '✅' : '❌'} <span>${ch.msg}</span></div>`;
        });

        if (r.score < 100) {
            html += `<div style="margin-top:12px;"><button class="btn btn-secondary btn-sm" id="btn-hub-autofix">🛠️ Tự động sửa lỗi chuẩn SEO</button></div>`;
        }

        scoreBody.innerHTML = html;

        const autofixBtn = document.getElementById('btn-hub-autofix');
        if (autofixBtn) {
            autofixBtn.onclick = () => {
                autoFix(c);
            };
        }
    }

    function renderScoreEmpty() {
        document.getElementById('scoreBody').innerHTML = '<span class="empty">Chưa có nội dung chấm điểm.</span>';
    }

    function autoFix(c) {
        // Simple replacements to clean the text
        let main = c.main || "";
        main = main.replace(/booking|agoda|airbnb|traveloka/gi, "inbox/Zalo");
        main = main.replace(/số 1|nhất huế|rẻ nhất/gi, "được đánh giá cao");
        if (!main.toLowerCase().includes('huế')) {
            main = "Homestay Huế thân thương 🌸\n" + main;
        }
        c.main = main;
        applyHubContent(c);
        renderScore(c);
        showToast('Đã sửa lỗi bài viết chuẩn SEO!');
    }

    // History and templates
    const HIST_KEY = "hub_history_v1";
    function loadHist() {
        try {
            return JSON.parse(localStorage.getItem(HIST_KEY) || "[]");
        } catch (e) {
            return [];
        }
    }

    function saveHist(h) {
        localStorage.setItem(HIST_KEY, JSON.stringify(h.slice(0, 30)));
    }

    function addHistory(c, f) {
        const h = loadHist();
        h.unshift({
            t: Date.now(),
            brand: currentHubBrand,
            idea: f.idea || "Tạo nhanh",
            purpose: f.purpose,
            content: c,
            score: c.scoreVal || 100
        });
        saveHist(h);
        renderHistory();
    }

    function renderHistory() {
        const h = loadHist();
        const box = document.getElementById('histList');
        if (h.length === 0) {
            box.innerHTML = '<span class="empty">Chưa có lịch sử tạo bài.</span>';
            return;
        }
        box.innerHTML = "";
        h.forEach((it, idx) => {
            const date = new Date(it.t).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
            const item = document.createElement('div');
            item.className = 'hist';
            item.innerHTML = `
                <div class="top"><span>📅 ${date} · <strong>${it.brand.toUpperCase()}</strong></span><span class="tag">Điểm: ${it.score}</span></div>
                <div class="idea">Ý tưởng: ${it.idea}</div>
                <div class="acts">
                    <button class="btn-copy-hist">📋 Copy</button>
                    <button class="btn-push-hist">📥 Đưa lên bảng đăng</button>
                </div>
            `;
            item.querySelector('.btn-copy-hist').onclick = (e) => {
                window.copyTextToClipboard(it.content.main, e.target);
            };
            item.querySelector('.btn-push-hist').onclick = () => {
                pushToComposerText(it.content.main);
            };
            box.appendChild(item);
        });
    }

    // Copy package
    const copyPkgBtn = document.getElementById('btn-copy-package');
    if (copyPkgBtn) {
        copyPkgBtn.onclick = (e) => {
            const c = savedHubContent[currentHubBrand];
            if (!c) return;
            const pkg = `=== BÀI CHÍNH ===\n${c.main}\n\n=== GROUP 1 ===\n${c.grp1}\n\n=== GROUP 2 ===\n${c.grp2}\n\n=== REEL ===\n${c.reeldesc}\n\n=== STORY ===\n${c.story}`;
            window.copyTextToClipboard(pkg, e.target);
        };
    }

    // ---- PUSH TO COMPOSER INTEGRATION ----
    document.querySelectorAll('.push-to-comp-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const sourceId = btn.dataset.source;
            const text = document.getElementById(sourceId).innerText;
            if (!text || text.includes("Chưa có nội dung")) {
                showToast('Chưa có nội dung để đưa vào Bảng đăng bài!', 'error');
                return;
            }
            pushToComposerText(text);
        });
    });

    function pushToComposerText(text) {
        // Set the text directly into the main composer content textbox
        postContent.value = text;
        
        // Auto grow the textarea
        postContent.style.height = 'auto';
        postContent.style.height = postContent.scrollHeight + 'px';
        
        // Find which tab is active or switch to standard posting tab
        // If it's a group post, we switch to group tab, otherwise we go to Page tab
        const b = getHubBrand();
        let targetTabId = 'tab-group';
        if (text.includes('=== BÀI CHÍNH ===') || currentMode === 'page') {
            targetTabId = 'tab-page';
        }
        
        // Trigger tab click to switch view
        document.getElementById(targetTabId).click();
        
        showToast('Đã đưa bài viết vào Bảng đăng bài thành công!');
        
        // Scroll smoothly to composer card
        document.querySelector('.composer-card').scrollIntoView({ behavior: 'smooth' });
    }

    // Initial load
    switchHubBrand('lacasa');

    // ---- Initial Check & Loads ----
    checkStatus();
    loadAccounts();
    loadSavedLinks();
    loadQueue();
    loadCampaigns();

    // ====== PAGE SCHEDULER JS ======
    // Show/hide scheduler section when tab is clicked
    document.getElementById('tab-page-scheduler')?.addEventListener('click', () => {
        schedSection?.classList.remove('hidden');
        // hide the bottom post bar & divider when in scheduler mode
        document.getElementById('composer-divider-bar')?.classList.add('hidden');
        document.getElementById('add-to-post-bar')?.classList.add('hidden');
        document.getElementById('post-btn')?.classList.add('hidden');
        document.getElementById('diverse-post-settings-bar')?.classList.add('hidden');
        loadSchedConfig();
        loadSchedStatus();
    });

    async function loadSchedConfig() {
        try {
            const res = await fetch('/api/page/config');
            const data = await res.json();
            const tokenBadge = document.getElementById('sched-token-badge');
            const pageInfo = document.getElementById('sched-page-info');

            if (data.has_token) {
                tokenBadge.textContent = `✅ ${data.page_name || 'Token hợp lệ'}`;
                tokenBadge.className = 'sched-badge badge-success';
                document.getElementById('sched-page-name').textContent = `📄 ${data.page_name}`;
                document.getElementById('sched-page-id-badge').textContent = `ID: ${data.page_id}`;
                pageInfo.classList.remove('hidden');
            } else {
                tokenBadge.textContent = 'Chưa cấu hình';
                tokenBadge.className = 'sched-badge badge-error';
                pageInfo.classList.add('hidden');
            }

            if (data.sheets_csv_url) {
                document.getElementById('sched-sheets-url').value = data.sheets_csv_url;
            }
            const intervalSel = document.getElementById('sched-interval');
            if (data.scheduler_interval_minutes) {
                intervalSel.value = String(data.scheduler_interval_minutes);
            }
        } catch (e) { console.error('loadSchedConfig error', e); }
    }

    async function loadSchedStatus() {
        try {
            const res = await fetch('/api/scheduler/status');
            const data = await res.json();
            const badge = document.getElementById('sched-status-badge');
            if (data.running) {
                badge.textContent = '🟢 Đang chạy';
                badge.className = 'sched-badge badge-success';
            } else {
                badge.textContent = '🔴 Đang dừng';
                badge.className = 'sched-badge badge-error';
            }
        } catch (e) {}
    }

    // Save Token
    document.getElementById('sched-save-token-btn')?.addEventListener('click', async () => {
        const token = document.getElementById('sched-token-input').value.trim();
        if (!token) return alert('Vui lòng nhập Page Access Token!');
        const btn = document.getElementById('sched-save-token-btn');
        btn.textContent = '⏳ Đang xác thực...';
        btn.disabled = true;
        try {
            const res = await fetch('/api/page/token', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token})
            });
            const data = await res.json();
            if (data.error) {
                alert(`❌ ${data.error}`);
            } else {
                alert(`✅ Xác thực thành công! Page: ${data.page_name} (ID: ${data.page_id})`);
                document.getElementById('sched-token-input').value = '';
                loadSchedConfig();
            }
        } catch (e) { alert(`Lỗi kết nối: ${e.message}`); }
        finally { btn.textContent = '✅ Xác thực & Lưu'; btn.disabled = false; }
    });

    // Save Sheets URL
    document.getElementById('sched-save-sheets-btn')?.addEventListener('click', async () => {
        const url = document.getElementById('sched-sheets-url').value.trim();
        const interval = document.getElementById('sched-interval').value;
        if (!url) return alert('Vui lòng nhập Google Sheets CSV URL!');
        const res = await fetch('/api/page/sheets', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url, interval: parseInt(interval)})
        });
        const data = await res.json();
        if (data.success) alert('✅ Đã lưu Sheets URL!');
        else alert(`❌ ${data.error}`);
    });

    // Preview Sheets
    document.getElementById('sched-preview-btn')?.addEventListener('click', async () => {
        const url = document.getElementById('sched-sheets-url').value.trim();
        const btn = document.getElementById('sched-preview-btn');
        btn.textContent = '⏳ Đang tải...';
        btn.disabled = true;
        try {
            const res = await fetch('/api/page/preview', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url})
            });
            const data = await res.json();
            if (data.error) { alert(data.error); return; }
            const rows = data.rows || [];
            const tbody = document.getElementById('sched-preview-body');
            tbody.innerHTML = '';
            if (rows.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;opacity:0.5">Không có dữ liệu hoặc URL sai.</td></tr>';
            } else {
                rows.forEach((row, i) => {
                    const statusClass = row.status === 'posted' ? 'sched-status-posted' :
                                       row.status === 'skip' ? 'sched-status-skip' : 'sched-status-pending';
                    const tr = document.createElement('tr');
                    const values = [i + 1, row.page_id, `${row.content.substring(0, 50)}${row.content.length > 50 ? '...' : ''}`, row.image_url ? '🖼 Có ảnh' : '-', row.scheduled_time, row.status];
                    values.forEach((value, index) => {
                        const td = document.createElement('td');
                        td.textContent = value;
                        if (index === 2) td.title = row.content;
                        if (index === 5) td.className = statusClass;
                        tr.appendChild(td);
                    });
                    tbody.appendChild(tr);
                });
            }
            document.getElementById('sched-preview-container').classList.remove('hidden');
        } catch (e) { alert(`Lỗi: ${e.message}`); }
        finally { btn.textContent = '👁 Xem trước dữ liệu Sheet'; btn.disabled = false; }
    });

    // Start Scheduler
    document.getElementById('sched-start-btn')?.addEventListener('click', async () => {
        const res = await fetch('/api/scheduler/start', {method:'POST'});
        const data = await res.json();
        if (data.success) { alert('🚀 Scheduler đã khởi động!'); loadSchedStatus(); }
        else alert('❌ Lỗi khởi động scheduler!');
    });

    // Stop Scheduler
    document.getElementById('sched-stop-btn')?.addEventListener('click', async () => {
        const res = await fetch('/api/scheduler/stop', {method:'POST'});
        const data = await res.json();
        alert(data.success ? '⏹ Scheduler đã dừng.' : 'Scheduler chưa chạy.');
        loadSchedStatus();
    });

    // Run Now
    document.getElementById('sched-run-now-btn')?.addEventListener('click', async () => {
        const btn = document.getElementById('sched-run-now-btn');
        btn.textContent = '⏳ Đang chạy...';
        btn.disabled = true;
        try {
            const res = await fetch('/api/scheduler/run-now', {method:'POST'});
            const data = await res.json();
            alert(data.success ? '✅ Đã chạy xong! Kiểm tra log bên dưới.' : `❌ ${data.error}`);
            loadSchedLogs();
        } catch (e) { alert(`Lỗi: ${e.message}`); }
        finally { btn.textContent = '⚡ Chạy ngay 1 lần'; btn.disabled = false; }
    });

    // Refresh Logs
    document.getElementById('sched-refresh-log-btn')?.addEventListener('click', loadSchedLogs);

    async function loadSchedLogs() {
        try {
            const res = await fetch('/api/scheduler/logs?lines=80');
            const data = await res.json();
            const logDiv = document.getElementById('sched-log-output');
            if (!data.logs || data.logs.length === 0) {
                logDiv.innerHTML = '<span style="opacity:0.5">Chưa có log.</span>';
                return;
            }
            logDiv.innerHTML = '';
            data.logs.forEach(line => {
                let cls = '';
                if (line.includes('✅') || line.includes('thành công')) cls = 'log-ok';
                else if (line.includes('❌') || line.includes('ERROR') || line.includes('thất bại')) cls = 'log-err';
                else if (line.includes('INFO') || line.includes('🔍') || line.includes('📢')) cls = 'log-info';
                const entry = document.createElement('span');
                entry.className = cls;
                entry.textContent = line;
                logDiv.append(entry, document.createTextNode('\n'));
            });
            logDiv.scrollTop = logDiv.scrollHeight;
        } catch (e) {}
    }
    // ====== END PAGE SCHEDULER JS ======
});

