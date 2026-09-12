Warning: truncated output (original token count: 73478)
Total output lines: 5260

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
    const scrapeResultsContainer = document.getElementById('scrape-results-card') || document.getElementById('scrape-results-container');
    const scrapeTableBody = document.getElementById('scrape-table-body');
    const downloadCsvBtn = document.getElementById('download-csv-btn');
    const commentSection = document.getElementById('comment-section');
    const commentTargets = document.getElementById('comment-targets');
    const commentContent = document.getElementById('comment-content');
    const commentLikePost = document.getElementById('comment-like-post');
    const aiCommentSpinBtn = document.getElementById('ai-comment-spin-btn');
    const autoSpinCommentOpt = document.getElementById('auto-spin-comment-opt');
    const aiInteractSpinBtn = document.getElementById('ai-interact-spin-btn');
    const interactRotateOpt = document.getElementById('interact-rotate-opt');
    const interactAutoSpinOpt = document.getElementById('interact-auto-spin-opt');
    const threadSection = document.getElementById('thread-section');
    const threadTargetInput = document.getElementById('thread-target-input');
    const threadContentInput = document.getElementById('thread-content-input');
    const folderPhotoBar = document.getElementById('folder-photo-bar');
    const delaySettingsBar = document.getElementById('delay-settings-bar');
    const accountsCard = document.querySelector('.accounts-card');
    const composerBodyCard = document.querySelector('.composer-body-card');
    const workflowGuide = document.querySelector('.workflow-guide');
    const profileActivitySection = document.getElementById('profile-activity-section');
    const settingsSection = document.getElementById('settings-section');
    const addToPostBar = document.getElementById('add-to-post-bar');
    const composerDividerBar = document.getElementById('composer-divider-bar');

    // Auto Join Group & Create Page elements
    const autoJoinGroupsOpt = document.getElementById('auto-join-groups-opt');
    const autoJoinKwContainer = document.getElementById('auto-join-kw-container');
    const autoJoinKeywords = document.getElementById('auto-join-keywords');
    const createPageSection = document.getElementById('create-page-section');
    const createPageProfileSelect = document.getElementById('create-page-profile-select');
    const createPageName = document.getElementById('create-page-name');
    const createPageCategory = document.getElementById('create-page-category');
    const createPageBio = document.getElementById('create-page-bio');
    const createPageAvatar = document.getElementById('create-page-avatar');
    const createPageCover = document.getElementById('create-page-cover');
    const submitCreatePageBtn = document.getElementById('submit-create-page-btn');
    const createPagePanelRight = document.getElementById('create-page-panel-right');
    const createdPagesQuotaBadge = document.getElementById('created-pages-quota-badge');
    const createdPagesTableBody = document.getElementById('created-pages-table-body');
    const refreshCreatedPagesBtn = document.getElementById('refresh-created-pages-btn');

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
    const gpmStatusBadge = document.getElementById('gpm-status-badge');
    const refreshGpmBtn = document.getElementById('refresh-gpm-btn');
    const syncGpmTableBtn = document.getElementById('sync-gpm-table-btn');
    const openSelectedProfileBtn = document.getElementById('open-selected-profile-btn');
    const openGpmImportModalBtn = document.getElementById('open-gpm-import-modal-btn');
    const gpmImportModal = document.getElementById('gpm-import-modal');
    const closeGpmModalBtn = document.getElementById('close-gpm-modal-btn');
    const modalCancelBtn = document.getElementById('modal-cancel-btn');
    const modalGpmSearch = document.getElementById('modal-gpm-search');
    const modalGpmSelectAll = document.getElementById('modal-gpm-select-all');
    const modalGpmDeselectAll = document.getElementById('modal-gpm-deselect-all');
    const modalSelectAllHeader = document.getElementById('modal-select-all-header');
    const modalGpmTableBody = document.getElementById('modal-gpm-table-body');
    const modalSelectedCounter = document.getElementById('modal-selected-counter');
    const modalConfirmImportBtn = document.getElementById('modal-confirm-import-btn');
    const tabSavedAccounts = document.getElementById('tab-saved-accounts');
    const tabAllGpmAccounts = document.getElementById('tab-all-gpm-accounts');
    const savedAccountsCount = document.getElementById('saved-accounts-count');
    const gpmAccountsCount = document.getElementById('gpm-accounts-count');
    const gpmQuickFilterContainer = document.getElementById('gpm-quick-filter-container');
    const gpmQuickFilterInput = document.getElementById('gpm-quick-filter-input');
    const manageAccountsBtn = document.getElementById('manage-accounts-btn');
    const accountsContent = document.getElementById('accounts-content');
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
    const approvalQueueCard = document.getElementById('approval-queue-card');
    const approvalQueueList = document.getElementById('approval-queue-list');
    const refreshQueueBtn = document.getElementById('refresh-queue-btn');
    const profilesPanelRight = document.getElementById('profiles-panel-right');
    const settingsPanelRight = document.getElementById('settings-panel-right');
    const composerActionBar = document.getElementById('composer-action-bar');
    const queueSection = document.getElementById('queue-section');
    let historySection = document.getElementById('history-section');
    if (!historySection && queueSection) {
        historySection = document.createElement('section');
        historySection.id = 'history-section';
        historySection.className = 'hidden execution-manager-section';
        queueSection.insertAdjacentElement('afterend', historySection);
    }
    const queueTab = document.getElementById('tab-queue');
    if (queueTab && !document.getElementById('tab-history')) {
        const historyTab = document.createElement('button');
        historyTab.className = 'composer-tab nav-item';
        historyTab.dataset.target = 'history'; historyTab.id = 'tab-history';
        historyTab.innerHTML = '<span style="font-size:17px">🔗</span><span>Lịch Sử & Đối Soát Bài Đăng</span>';
        queueTab.insertAdjacentElement('afterend', historyTab);
    }
    const workspaceGrid = document.querySelector('.workspace-grid');
    if (queueSection && approvalQueueCard && approvalQueueCard.parentElement !== queueSection) queueSection.insertBefore(approvalQueueCard, queueSection.firstChild);
    if (historySection && postedLinksCard && postedLinksCard.parentElement !== historySection) historySection.appendChild(postedLinksCard);
    const logCard = document.querySelector('.card.log-card') || document.querySelector('.log-card');
    const logCardHome = logCard ? logCard.parentElement : null;
    const workflowTaskBody = document.getElementById('workflow-task-body');
    const workflowSummary = document.getElementById('workflow-summary');
    const workflowFilter = document.getElementById('workflow-filter');
    const refreshWorkflowsBtn = document.getElementById('refresh-workflows-btn');
    const workflowEventPanel = document.getElementById('workflow-event-panel');
    const workflowEventList = document.getElementById('workflow-event-list');
    const interactSubmitBtn = document.getElementById('interact-submit-btn');
    const scrapeSubmitBtn = document.getElementById('scrape-submit-btn');
    const commentSubmitBtn = document.getElementById('comment-submit-btn');
    const threadSubmitBtn = document.getElementById('thread-submit-btn');
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

    // Join Group Section Elements
    const joinGroupSection = document.getElementById('join-group-section');
    const joinGroupPanelRight = document.getElementById('join-group-panel-right');
    const joinGroupProfileSelect = document.getElementById('join-group-profile-select');
    const joinModeKw = document.getElementById('join-mode-kw');
    const joinModeUrls = document.getElementById('join-mode-urls');
    const joinKwGroup = document.getElementById('join-kw-group');
    const joinUrlsGroup = document.getElementById('join-urls-group');
    const joinGroupKeywords = document.getElementById('join-group-keywords');
    const joinGroupUrls = document.getElementById('join-group-urls');
    const joinGroupLimit = document.getElementById('join-group-limit');
    const joinGroupMaxProfiles = document.getElementById('join-group-max-profiles');
    const joinProfileDelayMin = document.getElementById('join-profile-delay-min');
    const joinProfileDelayMax = document.getElementById('join-profile-delay-max');
    const joinGroupReadyHint = document.getElementById('join-group-ready-hint');
    const joinGroupAutoRules = document.getElementById('join-group-auto-rules');
    const joinGroupInteractFeed = document.getElementById('join-group-interact-feed');
    const submitJoinGroupBtn = document.getElementById('submit-join-group-btn');
    const refreshJoinedGroupsBtn = document.getElementById('refresh-joined-groups-btn');
    const clearJoinedGroupsBtn = document.getElementById('clear-joined-groups-btn');
    const joinedGroupsTableBody = document.getElementById('joined-groups-table-body');

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
    let defaultJoinProfileIds = [];
    let isCsvMode = false;
    let isRunning = false;
    let currentJobId = null;
    let logHasContent = false;
    let rawLogLines = [];
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
            const verText = data.version ? `v${data.version}` : 'v6.1.1';
            const buildText = data.built_at ? `Build: ${data.built_at}` : 'Build: 2026-09-08';
            
            const sidebarVer = document.getElementById('sidebar-version-badge');
            const sidebarBuild = document.getElementById('sidebar-build-time');
            const headerVer = document.getElementById('header-version-text');
            const headerBuild = document.getElementById('header-build-time-text');
            const buildInfoEl = document.getElementById('build-info');
            
            if (sidebarVer) sidebarVer.textContent = verText;
            if (sidebarBuild) sidebarBuild.textContent = buildText;
            if (headerVer) headerVer.textContent = `Phiên bản: ${verText}`;
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
            approvalQueueList.innerHTML = `
                <div style="background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 8px; padding: 14px; text-align: center; color: #64748B;">
                    <p style="font-weight: 700; font-size: 13px; margin-bottom: 6px; color: #1E293B;">Chưa có bài nào trong hàng đợi</p>
                    <p style="font-size: 12px; margin: 0; line-height: 1.5;">
                        👉 Soạn bài và nhập link ở bên trái, sau đó bấm <strong>"📋 Đưa vào Hàng đợi duyệt"</strong>.<br>
                        Bài viết sẽ xuất hiện tại đây kèm nút <strong>"✅ Duyệt bài này"</strong> để bạn kiểm duyệt trước khi đăng!
                    </p>
                </div>`;
            return;
        }
        items.forEach(item => {
            const row = document.createElement('div');
            row.className = 'queue-item-card';
            row.style.cssText = 'background:#fff;border:1px solid #E2E8F0;border-radius:7px;padding:8px 10px;margin-bottom:6px;display:flex;flex-direction:column;gap:5px;';

            const title = document.createElement('div');
            title.style.cssText = 'font-weight: 600; font-size: 13px; color: #1877f2; word-break: break-all;';
            const queueStatus = {
                approved: ['✅','Đã duyệt','#DCFCE7','#166534'], draft: ['📝','Nháp','#FEF3C7','#92400E'],
                processing: ['⚙️','Đang đăng','#DBEAFE','#1D4ED8'], reconciling: ['🔎','Đang đối soát','#E0E7FF','#3730A3'],
                pending: ['⏳','Chờ duyệt FB','#FEF3C7','#92400E'],
                unverified: ['⚠️','Chưa xác minh','#FFEDD5','#9A3412'], manual_review: ['🧭','Cần đối soát thủ công','#FFEDD5','#9A3412'], failed: ['❌','Lỗi trước submit','#FEE2E2','#991B1B'], published: ['✅','Đã xuất bản','#DCFCE7','#166534'], cancelled: ['⏹','Đã hủy','#F1F5F9','#475569']
            };
            const qs = queueStatus[item.state] || ['•', item.state || 'Không rõ','#F1F5F9','#475569'];
            const statusBadge = `<span style="background:${qs[2]};color:${qs[3]};padding:2px 7px;border-radius:10px;font-size:10px;margin-right:4px;">${qs[0]} ${qs[1]}</span>`;
            title.innerHTML = `${statusBadge} <strong>${escapeHtml(item.target)}</strong>`;

            const preview = document.createElement('div');
            preview.style.cssText = 'font-size:11px;color:#64748B;line-height:1.35;max-height:32px;overflow:hidden;background:#F8FAFC;padding:4px 6px;border-radius:5px;';
            preview.textContent = item.content;

            const meta = document.createElement('div');
            meta.className = 'queue-item-meta';
            meta.style.cssText = 'font-size:10px;color:#64748B;display:flex;gap:10px;flex-wrap:wrap;align-items:center;';
            const rawQueueTime = item.created_at || item.updated_at || '';
            const queueTimeKind = item.created_at ? 'Tạo' : (item.updated_at ? 'Cập nhật' : 'Thời gian');
            const parsedQueueTime = rawQueueTime ? new Date(rawQueueTime) : null;
            const queueTimeLabel = parsedQueueTime && !Number.isNaN(parsedQueueTime.getTime())
                ? parsedQueueTime.toLocaleString('vi-VN', { hour12: false })
                : (rawQueueTime || 'Không rõ');
            const sessionLabel = item.campaign_id || item.session_id || item.id || 'Không rõ';
            meta.innerHTML = `<span>🕒 ${queueTimeKind}: <strong>${escapeHtml(queueTimeLabel)}</strong></span><span>🧾 Phiên/Mã: <strong>${escapeHtml(sessionLabel)}</strong></span>`;

            const actions = document.createElement('div');
            actions.style.cssText = 'display: flex; gap: 8px; align-items: center; margin-top: 4px;';

            if (item.state === 'draft') {
                const approve = document.createElement('button');
                approve.className = 'btn btn-primary btn-sm';
                approve.style.cssText = 'flex: 1; padding: 8px 14px; font-size: 13px; font-weight: 700; background: #10B981; color: #ffffff; border: none; border-radius: 6px; cursor: pointer; box-shadow: 0 1px 3px rgba(16,185,129,0.3); display: flex; align-items: center; justify-content: center; gap: 6px;';
                approve.innerHTML = '✅ <strong>Duyệt bài này</strong>';
                approve.addEventListener('click', () => updateQueueItem(item.id, 'approve'));
                actions.appendChild(approve);
            }

            if (item.state === 'unverified') {
                const reconcileBtn = document.createElement('button');
                reconcileBtn.className = 'btn btn-secondary btn-sm';
                reconcileBtn.textContent = '🔎 Đối soát link';
                reconcileBtn.addEventListener('click', () => {
                    const accId = item.account_id || (accountSelector ? accountSelector.value : '');
                    runCommand('reconcile-post', { accountId: accId, tasks: [{ target: item.target, content: item.content, queueItemId: item.id }] });
                });
                actions.appendChild(reconcileBtn);
            }

            if (item.state === 'approved') {
                const postItemBtn = document.createElement('button');
                postItemBtn.className = 'btn btn-primary btn-sm';
                postItemBtn.style.cssText = 'flex: 1; padding: 8px 14px; font-size: 13px; font-weight: 700; background: #1877f2; color: #ffffff; border: none; border-radius: 6px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px;';
                postItemBtn.innerHTML = '🚀 <strong>ĐĂNG BÀI NÀY NGAY</strong>';
                postItemBtn.addEventListener('click', () => {
                    const accId = accountSelector ? accountSelector.value : '';
                    const isGroup = item.target.includes('/groups/');
                    const mode = isGroup ? 'group' : 'page';
                    showToast(`Bắt đầu đăng bài: ${item.target}`);
                    runCommand(mode, {
                        accountId: accId,
                        tasks: [{ target: item.target, content: item.content, image: null, queueItemId: item.id }]
                    });
                });
                actions.appendChild(postItemBtn);
            }

            if (item.state === 'failed') {
                const retry = document.createElement('button');
                retry.className = 'btn btn-primary btn-sm';
                retry.textContent = '↻ Duyệt thử lại';
                retry.addEventListener('click', () => updateQueueItem(item.id, 'retry'));
                actions.appendChild(retry);
            }
            if (['draft','approved','pending','unverified'].includes(item.state)) {
                const cancel = document.createElement('button');
                cancel.className = 'btn btn-ghost btn-sm';
                cancel.style.cssText = 'padding: 6px 10px; font-size: 12px; color: #64748B; border: none; background: transparent; cursor: pointer;';
                cancel.textContent = '⏹ Hủy & lưu trữ';
                cancel.addEventListener('click', () => updateQueueItem(item.id, 'cancel'));
                actions.appendChild(cancel);
            }

            row.append(title, preview, meta, actions);
            approvalQueueList.appendChild(row);
        });

        // Xử lý nút Đăng tất cả bài đã duyệt trên Header
        const postAllApprovedBtn = document.getElementById('post-all-approved-btn');
        if (postAllApprovedBtn) {
            postAllApprovedBtn.onclick = async () => {
                const approvedItems = items.filter(i => i.state === 'approved');
                if (!approvedItems.length) {
                    showToast('Không có bài nào ở trạng thái "Đã duyệt" để đăng!', 'error');
                    return;
                }
                const accId = accountSelector ? accountSelector.value : '';
                const groupTasks = approvedItems.filter(i => i.target.includes('/groups/')).map(i => ({ target: i.target, content: i.content, image: null, queueItemId: i.id }));
                const pageTasks = approvedItems.filter(i => !i.target.includes('/groups/')).map(i => ({ target: i.target, content: i.content, image: null, queueItemId: i.id }));

                if (groupTasks.length > 0) {
                    showToast(`Đang chạy đăng ${groupTasks.length} bài Nhóm đã duyệt...`);
                    const groupResult = await runCommand('group', { accountId: accId, tasks: groupTasks });
                    if (groupResult === 'cancelled') return;
                }
                if (pageTasks.length > 0) {
                    showToast(`Đang chạy đăng ${pageTasks.length} bài Trang đã duyệt...`);
                    await runCommand('page', { accountId: accId, tasks: pageTasks });
                }
            };
        }
    }

    async function loadWorkflowEvents(taskId) {
        if (!workflowEventPanel || !workflowEventList || !taskId) return;
        try {
            const res = await fetch(`/api/workflows/tasks/${encodeURIComponent(taskId)}/events`);
            const data = await res.json();
            const events = Array.isArray(data.events) ? data.events : [];
            workflowEventList.innerHTML = events.length ? events.map(e => `<div class="workflow-event-row"><span class="workflow-event-seq">#${escapeHtml(e.seq)}</span><strong>${escapeHtml(e.event_type)}</strong><span>${escapeHtml(e.phase || '')}</span><span>${escapeHtml(e.message || '')}</span><time>${escapeHtml(e.created_at || '')}</time></div>`).join('') : '<div class="empty">Ch\u01b0a c\u00f3 evidence event.</div>';
            workflowEventPanel.classList.remove('hidden');
        } catch (err) {
            workflowEventList.innerHTML = `<div class="empty">Kh\u00f4ng t\u1ea3i \u0111\u01b0\u1ee3c timeline: ${escapeHtml(err.message || err)}</div>`;
            workflowEventPanel.classList.remove('hidden');
        }
    }

    async function loadWorkflowTasks() {
        if (!workflowTaskBody) return;
        const filter = workflowFilter?.value || 'active';
        const stateMap = {active:'queued,running,unverified,pending', all:'', published:'published', pending:'pending', unverified:'unverified', failed:'failed', cancelled:'cancelled'};
        const states = stateMap[filter] ?? '';
        const query = states ? `?states=${encodeURIComponent(states)}` : '';
        try {
            const res = await fetch('/api/workflows/tasks' + query);
            const data = await res.json();
            const tasks = Array.isArray(data.tasks) ? data.tasks : [];
            if (workflowSummary) workflowSummary.textContent = `${tasks.length} task`;
            workflowTaskBody.innerHTML = tasks.length ? tasks.map(t => {
                const target = String(t.target_url || '');
                const result = t.result_url ? 'M\u1edf k\u1ebft qu\u1ea3' : (t.error_code || t.error_message || '?');
                return `<tr class="workflow-task-row" data-task-id="${escapeHtml(t.id)}"><td>${escapeHtml(t.profile_id || '?')}</td><td title="${escapeHtml(target)}">${escapeHtml(target.slice(0,55) || '?')}</td><td>${escapeHtml(t.action || '')}</td><td>${escapeHtml(t.phase || '')}</td><td><span class="workflow-state workflow-state-${escapeHtml(t.state || 'unknown')}">${escapeHtml(t.state || 'unknown')}</span></td><td>${escapeHtml(t.verification_status || '')}</td><td>${Number(t.progress || 0)}%</td><td>${t.result_url ? `<a href="${escapeHtml(t.result_url)}" target="_blank" rel="noopener">${result}</a>` : escapeHtml(result)}</td></tr>`;
            }).join('') : '<tr><td colspan="8" class="empty">Ch\u01b0a c\u00f3 workflow task theo b\u1ed9 l\u1ecdc n\u00e0y.</td></tr>';
        } catch (err) {
            workflowTaskBody.innerHTML = `<tr><td colspan="8" class="empty">Kh\u00f4ng t\u1ea3i \u0111\u01b0\u1ee3c ti\u1ebfn tr\u00ecnh: ${escapeHtml(err.message || err)}</td></tr>`;
        }
    }

    async function loadQueue() {
        try {
            const filter = document.getElementById('queue-filter')?.value || 'active';
            const query = filter === 'active' ? '?active=1&limit=500' : (filter === 'all' ? '?limit=500' : `?state=${encodeURIComponent(filter)}&limit=500`);
            const [response, summaryRes] = await Promise.all([fetch('/api/queue' + query), fetch('/api/queue-summary')]);
            const visibleItems = await response.json();
            renderQueue(visibleItems);
            if (summaryRes.ok) {
                const q = await summaryRes.json();
                const el = document.getElementById('queue-summary-text');
                if (el) { const archived=(q.published||0)+(q.failed||0)+(q.cancelled||0); el.textContent = `(${q.active||0} hoạt động · ${q.needs_reconcile||0} cần đối soát · ${q.pending||0} chờ duyệt FB · ${archived} lưu trữ · đang hiển thị ${visibleItems.length})`; }
            }
        } catch (_) { approvalQueueList.textContent = 'Không thể tải hàng đợi.'; }
    }
    document.getElementById('queue-filter')?.addEventListener('change', loadQueue);

    async function updateQueueItem(id, action) {
        const response = await fetch(`/api/queue/${id}/${action}`, { method: 'POST' });
        const data = await response.json();
        if (!response.ok) showToast(data.error || 'Không thể cập nhật hàng đợi.', 'error');
        else { const msg=action==='approve'?'Đã duyệt bài đăng.':action==='retry'?'Đã đưa bài lỗi về trạng thái Đã duyệt để thử lại thủ công.':'Đã hủy và chuyển vào lưu trữ.'; showToast(msg); loadQueue(); }
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
        const queueTab = document.getElementById('tab-queue');
        if (queueTab) queueTab.click();
        loadQueue();
    });

    refreshQueueBtn.addEventListener('click', loadQueue);
    if (refreshWorkflowsBtn) refreshWorkflowsBtn.addEventListener('click', loadWorkflowTasks);
    if (workflowFilter) workflowFilter.addEventListener('change', loadWorkflowTasks);
    if (workflowTaskBody) workflowTaskBody.addEventListener('click', (event) => {
        const row = event.target.closest('tr[data-task-id]');
        if (row) loadWorkflowEvents(row.dataset.taskId);
    });

    // ---- Add to Queue (Đưa vào Hàng đợi duyệt) from Composer ----
    const addToQueueBtn = document.getElementById('add-to-queue-btn');
    if (addToQueueBtn) {
        addToQueueBtn.addEventListener('click', async () => {
            const rawTargets = targetInput.value.trim();
            const content = postContent.value.trim();

            if (!rawTargets || !content) {
                showToast('Vui lòng điền link mục tiêu và nội dung bài viết trước!', 'error');
                return;
            }

            const targets = rawTargets.split('\n').map(t => t.trim()).filter(t => t);
            if (!targets.length) {
                showToast('Chưa có link mục tiêu nào!', 'error');
                return;
            }

            addToQueueBtn.disabled = true;
            const originalText = addToQueueBtn.innerHTML;
            addToQueueBtn.innerHTML = '⏳ Đang thêm...';

            let addedCount = 0;
            for (const target of targets) {
                try {
                    const res = await fetch('/api/queue', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            target,
                            content,
                            image_url: ''
                        })
                    });
                    if (res.ok) addedCount++;
                } catch (e) {
                    console.error(e);
                }
            }

            addToQueueBtn.disabled = false;
            addToQueueBtn.innerHTML = originalText;

            if (addedCount > 0) {
                showToast(`Đã đưa ${addedCount} bài vào Hàng đợi! Vui lòng bấm '✅ Duyệt' để tiến hành đăng.`);
                const queueFilter = document.getElementById('queue-filter');
                if (queueFilter) queueFilter.value = 'active';
                const queueTab = document.getElementById('tab-queue');
                if (queueTab) queueTab.click();
                await loadQueue();
            } else {
                showToast('Không thể thêm bài vào hàng đợi.', 'error');
            }
        });
    }

    // ---- Approve All Queue Drafts (Duyệt tất cả bài nháp) ----
    const approveAllQueueBtn = document.getElementById('approve-all-queue-btn');
    if (approveAllQueueBtn) {
        approveAllQueueBtn.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/queue?state=draft&limit=500');
                const drafts = await res.json();
                if (!drafts.length) {
                    showToast('Không có bài nháp nào cần duyệt trong hàng đợi!', 'info');
                    return;
                }
                for (const d of drafts) {
                    await fetch(`/api/queue/${d.id}/approve`, { method: 'POST' });
                }
                showToast(`✅ Đã duyệt thành công ${drafts.length} bài đăng! Bây giờ bạn có thể bấm '🚀 Đăng bài đã duyệt'.`);
                loadQueue();
            } catch (e) {
                showToast('Lỗi khi duyệt bài', 'error');
            }
        });
    }

    async function loadPostedLinks() {
        try {
            const filter = document.getElementById('posted-links-filter')?.value || 'all';
            const query = filter === 'all' ? '?limit=30' : `?limit=30&state=${encodeURIComponent(filter)}`;
            const res = await fetch('/api/posted-links' + query);
            if (res.ok) {
                const links = await res.json();
                if (Array.isArray(links)) {
                    savedPostLinks = links;
                    renderPostedLinks(links);
                    const countEl = document.getElementById('posted-links-count');
                    if (countEl) countEl.textContent = `(${links.length} mục)`;
                    return;
                }
            }
        } catch (e) {
            console.warn('Không thể tải danh sách bài đã đăng từ server:', e);
        }

        // Fallback localStorage
        const stored = localStorage.getItem('fb_posted_links');
        if (stored) {
            try {
                savedPostLinks = JSON.parse(stored);
                renderPostedLinks(savedPostLinks);
            } catch (_) {}
        }
    }

    function saveLink(url) {
        if (!url) return;
        const exists = savedPostLinks.some(item => {
            const u = typeof item === 'string' ? item : (item.url || item.target || '');
            return u === url;
        });
        if (!exists) {
            savedPostLinks.unshift({
                url: url,
                target: url,
                status: 'Đã xuất bản',
                posted_at: new Date().toLocaleTimeString('vi-VN')
            });
            localStorage.setItem('fb_posted_links', JSON.stringify(savedPostLinks));
            renderPostedLinks(savedPostLinks);
        }
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }

    function renderPostedLinks(links) {
        if (!postedLinksList) return;
        postedLinksList.innerHTML = '';
        if (!links || links.length === 0) {
            postedLinksList.innerHTML = '<span class="empty" style="display:block; padding:16px; text-align:center; color:#64748B;">Chưa có link bài đăng nào được ghi nhận.</span>';
            return;
        }

        links.forEach(item => {
            const row = document.createElement('div');
            row.className = 'posted-link-item';
            row.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:6px 8px;border-bottom:1px solid #E2E8F0;gap:7px;font-size:12px;';

            const targetUrl = item.url || item.target || (typeof item === 'string' ? item : '');
            const status = item.status || 'Đã xuất bản';
            const postedAt = item.posted_at || '';
            const state = item.publish_state || 'unknown';
            const stateUi = state === 'published' ? ['✅','#DCFCE7','#166534'] : state === 'pending' ? ['⏳','#FEF3C7','#92400E'] : state === 'submitted_unverified' ? ['⚠️','#FFF7ED','#C2410C'] : ['•','#F1F5F9','#475569'];
            const statusBadge = `<span style="background:${stateUi[1]};color:${stateUi[2]};font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;">${stateUi[0]} ${escapeHtml(status)}</span>`;

            const infoCol = document.createElement('div');
            infoCol.style.cssText = 'display:flex; flex-direction:column; gap:3px; overflow:hidden; flex:1;';
            infoCol.innerHTML = `
                <div style="display:flex; align-items:center; gap:6px;">
                    ${statusBadge}
                    ${postedAt ? `<span style="font-size:11px; color:#64748B;">${escapeHtml(postedAt)}</span>` : ''}
                </div>
                <div style="font-weight:600; color:#1E293B; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(targetUrl)}">
                    ${escapeHtml(targetUrl)}
                </div>
            `;

            const btnCol = document.createElement('div');
            btnCol.style.cssText = 'flex-shrink:0;';
            if (targetUrl && (targetUrl.startsWith('http://') || targetUrl.startsWith('https://'))) {
                const a = document.createElement('a');
                a.href = targetUrl;
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                a.className = 'btn btn-secondary btn-xs';
                a.style.cssText = 'padding:4px 8px; font-size:12px; text-decoration:none; display:inline-flex; align-items:center; gap:4px;';
                a.innerHTML = '🔗 Mở';
                btnCol.appendChild(a);
            }
            if (state === 'submitted_unverified' && item.target && item.content) {
                const reconcileHistoryBtn = document.createElement('button');
                reconcileHistoryBtn.className = 'btn btn-secondary btn-xs';
                reconcileHistoryBtn.style.marginLeft = '4px';
                reconcileHistoryBtn.textContent = '🔎 Đối soát';
                reconcileHistoryBtn.addEventListener('click', async () => {
                    const accId = item.account_id || (accountSelector ? accountSelector.value : '');
                    await runCommand('reconcile-post', { accountId: accId, tasks: [{ target: item.target, content: item.content }] });
                    loadPostedLinks();
                });
                btnCol.appendChild(reconcileHistoryBtn);
            }

            row.append(infoCol, btnCol);
            postedLinksList.appendChild(row);
        });

        if (postedLinksCard) postedLinksCard.classList.remove('hidden');
    }

    document.getElementById('posted-links-filter')?.addEventListener('change', loadPostedLinks);

    // Nút Xóa toàn bộ lịch sử link bài đăng
    if (clearLinksBtn) {
        clearLinksBtn.addEventListener('click', async () => {
            try {
                await fetch('/api/posted-links', { method: 'DELETE' });
            } catch (_) {}
            localStorage.removeItem('fb_posted_links');
            savedPostLinks = [];
            renderPostedLinks([]);
            showToast('Đã xóa toàn bộ lịch sử link bài đăng!');
        });
    }

    // Nút Làm mới lịch sử link bài đăng
    const refreshLinksBtn = document.getElementById('refresh-links-btn');
    if (refreshLinksBtn) {
        refreshLinksBtn.addEventListener('click', () => {
            loadPostedLinks();
            showToast('Đã làm mới danh sách link bài đăng.');
        });
    }

    // Nút Đưa danh sách link sang tab Comment
    const sendToCommentBtn = document.getElementById('send-to-comment-btn');
    if (sendToCommentBtn) {
        sendToCommentBtn.addEventListener('click', () => {
            if (!savedPostLinks || savedPostLinks.length === 0) {
                showToast('Chưa có link bài đăng nào để đưa sang Comment!', 'error');
                return;
            }
            const publishedLinks = savedPostLinks.filter(item => {
                if (typeof item === 'string') {
                    return /(?:\/posts\/|\/permalink\/|permalink\.php|story\.php|\/videos\/|\/share\/[pv]\/|\/reel\/)/i.test(item);
                }
                const url = item.url || '';
                const isPostUrl = /(?:\/posts\/|\/permalink\/|permalink\.php|story\.php|\/videos\/|\/share\/[pv]\/|\/reel\/)/i.test(url);
                const urlType = item.url_type || (isPostUrl ? 'post' : 'unknown');
                const pubState = item.publish_state || ((item.status && item.status.toLowerCase().includes('đã xuất bản')) ? 'published' : 'unknown');
                return (urlType === 'post' || isPostUrl) && pubState === 'published';
            });
            const urls = publishedLinks.map(item => typeof item === 'string' ? item : (item.url || '')).filter(u => u && u.startsWith('http'));
            if (urls.length === 0) {
                showToast('Chưa có link bài viết đã xuất bản hợp lệ để bình luận!', 'warning');
                return;
            }
            const commentTargetInput = document.getElementById('comment-targets');
            if (commentTargetInput) {
                commentTargetInput.value = urls.join('\n');
            }
            // Switch to comment tab
            const tabComment = document.getElementById('tab-comment');
            if (tabComment) tabComment.click();
            showToast(`Đã chuyển ${urls.length} link bài viết sang tab Comment!`);
        });
    }

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

    // ---- Account Management State ----
    let currentAccountsTab = 'saved';
    let cachedGpmProfiles = [];
    let selectedGpmImportIds = new Set();

    // ---- Load and Render Accounts ----
    async function loadAccounts() {
        try {
            const gpmUrl = gpmApiInput ? gpmApiInput.value.trim() : 'http://127.0.0.1:19995';

            // 1. Lấy danh sách tài khoản đã lưu (accounts.json)
            const res = await fetch('/api/accounts');
            accountsList = await res.json();

            // 2. Lấy danh sách profiles trực tiếp từ GPMLogin v3 API
            let gpmData = { connected: false, profiles: [], total: 0 };
            try {
                const gpmRes = await fetch(`/api/gpm/profiles?gpm_api_url=${encodeURIComponent(gpmUrl)}&page=1&page_size=300`);
                if (gpmRes.ok) {
                    gpmData = await gpmRes.json();
                }
            } catch (gpmErr) {
                console.warn("GPM API fetch error:", gpmErr);
            }

            cachedGpmProfiles = (gpmData.connected && Array.isArray(gpmData.profiles)) ? gpmData.profiles : [];

            // Cập nhật thẻ trạng thái GPM
            if (gpmStatusBadge) {
                if (gpmData.connected) {
                    gpmStatusBadge.textContent = `🟢 GPM: Online (${gpmData.total} Profiles)`;
                    gpmStatusBadge.style.background = '#DCFCE7';
                    gpmStatusBadge.style.color = '#15803D';
                } else {
                    gpmStatusBadge.textContent = '⚪ GPM: Offline';
                    gpmStatusBadge.style.background = '#FEE2E2';
                    gpmStatusBadge.style.color = '#991B1B';
                }
            }

            // Cập nhật số lượng trên các thẻ Tab
            if (savedAccountsCount) savedAccountsCount.textContent = accountsList.length;
            if (gpmAccountsCount) gpmAccountsCount.textContent = cachedGpmProfiles.length;

            // Đổ dữ liệu vào Dropdown chọn Profile (#account-selector)
            const selectedVal = accountSelector.value;
            accountSelector.innerHTML = '';

            // Tùy chọn xoay tua luân phiên: CHỈ XOAY TUA TRÊN CÁC NICK FACEBOOK ĐÃ LƯU
            if (accountsList.length > 1) {
                const rotateOpt = document.createElement('option');
                rotateOpt.value = '__rotate__';
                rotateOpt.textContent = `🔄 Luân phiên ${accountsList.length} tài khoản Facebook đã lưu (Xoay vòng chống spam)`;
                accountSelector.appendChild(rotateOpt);
            }

            // Nhóm 1: Các nick Facebook đã lưu chính thức (được dùng để đăng bài/xoay tua)
            if (accountsList.length > 0) {
                const grpSaved = document.createElement('optgroup');
                grpSaved.label = `📂 Tài khoản Facebook đã lưu (${accountsList.length})`;
                accountsList.forEach(acc => {
                    const opt = document.createElement('option');
                    opt.value = acc.id;
                    const proxyText = acc.proxy ? ` - ${acc.proxy.split(':')[0]}` : '';
                    opt.textContent = `👤 ${acc.name} (${acc.type === 'gpm' ? 'GPM' : 'Local'}${proxyText})`;
                    grpSaved.appendChild(opt);
                });
                accountSelector.appendChild(grpSaved);
            }

            // Nhóm 2: Các profile GPM khác chưa lưu (để người dùng có thể chọn chạy đơn lẻ nếu muốn)
            const otherGpmProfiles = cachedGpmProfiles.filter(p => !accountsList.some(a => a.id === p.id || a.profile_path_or_id === p.id));
            if (otherGpmProfiles.length > 0) {
                const grpOther = document.createElement('optgroup');
                grpOther.label = `🌐 Profile GPM khác (${otherGpmProfiles.length} - chọn chạy đơn lẻ)`;
                otherGpmProfiles.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    const proxyText = p.proxy_hint ? ` - ${p.proxy_hint}` : '';
                    opt.textContent = `📱 ${p.name} (${p.browser_type || 'Chrome'}${proxyText})`;
                    grpOther.appendChild(opt);
                });
                accountSelector.appendChild(grpOther);
            }

            const fallbackOpt = document.createElement('option');
            fallbackOpt.value = '';
            fallbackOpt.textContent = '-- Mặc định (state.json) --';
            accountSelector.appendChild(fallbackOpt);

            // Giữ lựa chọn cũ nếu còn tồn tại, nếu không chọn tài khoản đã lưu đầu tiên
            if (selectedVal && [...accountSelector.querySelectorAll('option')].some(o => o.value === selectedVal)) {
                accountSelector.value = selectedVal;
            } else if (accountsList.length > 0) {
                accountSelector.value = accountsList[0].id;
            } else if (otherGpmProfiles.length > 0) {
                accountSelector.value = otherGpmProfiles[0].id;
            }

            // Render bảng tài khoản
            renderAccountsTable();

        } catch (e) {
            console.error("Lỗi khi tải tài khoản:", e);
        }
    }

    // ---- Render Bảng Accounts (Tab Đã lưu vs Tab GPM) ----
    function renderAccountsTable() {
        if (!accountsTableBody) return;
        accountsTableBody.innerHTML = '';

        if (currentAccountsTab === 'saved') {
            if (accountsList.length === 0) {
                accountsTableBody.innerHTML = `
                    <tr>
                        <td colspan="6" style="text-align: center; padding: 24px; color: var(--fb-text-secondary);">
                            <div style="font-size: 15px; margin-bottom: 6px;">📂 Chưa có tài khoản Facebook nào trong danh sách đã lưu.</div>
                            <div style="font-size: 13px; color: #64748B;">Nhấn nút <strong>"📥 Nhập Nick FB từ GPM"</strong> bên trên để chọn các nick Facebook mong muốn và đưa vào xoay tua!</div>
                        </td>
                    </tr>`;
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
                const typeCell = makeCell(acc.type === 'gpm' ? 'GPM Facebook' : 'Cục bộ (Local)');
                typeCell.firstChild.className = `badge badge-${acc.type}`;
                const profileCell = makeCell(acc.profile_path_or_id, 'code');
                const proxyCell = makeCell(acc.proxy || 'Trực tiếp');

                const statusCell = document.createElement('td');
                statusCell.innerHTML = `
                    <span class="badge badge-success" style="font-size:11px; padding:2px 8px; border-radius:10px; background:#DCFCE7; color:#15803D; font-weight:600;">Sẵn sàng (Đã lưu)</span>
                    ${acc.created_at ? `<div style="font-size:11px; color:#94A3B8; margin-top:2px;">🕒 ${acc.created_at}</div>` : ''}
                `;

                const actions = document.createElement('td');
                actions.className = 'acc-action-btns';

                if (acc.type === 'gpm') {
                    const openGpmBtn = document.createElement('button');
                    openGpmBtn.className = 'btn btn-prima…43478 tokens truncated…cùng khu, có nghỉ trưa, không bịa thời gian di chuyển", purpose:"meo", target:"khach" },
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
      
      const facts = JSON.stringify(OFFLINE_KNOWLEDGE[currentHubBrand] || OFFLINE_KNOWLEDGE.hue);
      
      return `Bạn là người viết content tự nhiên cho ${b.name} tại Huế.
      Ý CHÍNH NGƯỜI DÙNG: ${f.idea}.
      MỤC ĐÍCH: ${f.purpose}.
      ĐỐI TƯỢNG: ${targetTxt}.
      TÔNG GIỌNG: ${toneTxt}.
      ĐỘ DÀI: ${lenTxt}.
      CONTENT HUB — SỰ THẬT ĐÃ XÁC MINH: ${facts}.
      QUY TẮC CỨNG: Chỉ được dùng dữ kiện có trong SỰ THẬT ĐÃ XÁC MINH hoặc trường người dùng vừa nhập. Không tự bịa giá, số phòng trống, ưu đãi, voucher, khoảng cách/thời gian di chuyển, tiện nghi, giờ mở cửa, lịch sự kiện, thời tiết hay claim tốt nhất/rẻ nhất. Nếu thiếu dữ liệu thì bỏ claim đó, không đoán. Nếu weatherUnavailable=true thì tuyệt đối không nói thời tiết hôm nay.
      Mọi URL, số điện thoại, địa chỉ và tên thương hiệu phải giữ đúng dữ liệu Content Hub.
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
                f.weatherLine = "";
                f.weatherUnavailable = true;
                showToast('Không lấy được thời tiết thật; Content Hub sẽ không tự bịa thời tiết hôm nay.', 'error');
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
    loadAccounts().then(loadDefaultProductionSetup);
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
    // ====== PRESET GIÃN CÁCH AN TOÀN ======
    const delayPresetSelect = document.getElementById('delay-preset-select');
    const customDelayInputs = document.getElementById('custom-delay-inputs');
    const delayPreviewBadge = document.getElementById('delay-preview-badge');
    
    if (delayPresetSelect) {
        delayPresetSelect.addEventListener('change', () => {
            const val = delayPresetSelect.value;
            if (val === 'custom') {
                customDelayInputs.classList.remove('hidden');
                customDelayInputs.style.display = 'flex';
                delayPreviewBadge.textContent = 'Tùy chỉnh phút';
            } else {
                customDelayInputs.classList.add('hidden');
                customDelayInputs.style.display = 'none';
                if (val === 'safe') {
                    delayPreviewBadge.textContent = '5 - 10 phút (An toàn)';
                    delayPreviewBadge.style.background = '#DBEAFE';
                    delayPreviewBadge.style.color = '#1E40AF';
                } else if (val === 'moderate') {
                    delayPreviewBadge.textContent = '2 - 5 phút (Vừa phải)';
                    delayPreviewBadge.style.background = '#FEF3C7';
                    delayPreviewBadge.style.color = '#92400E';
                } else if (val === 'fast') {
                    delayPreviewBadge.textContent = '30 - 60s (Thử nghiệm)';
                    delayPreviewBadge.style.background = '#FEE2E2';
                    delayPreviewBadge.style.color = '#B91C1C';
                } else if (val === 'test') {
                    delayPreviewBadge.textContent = '10 - 20s (Test nhanh)';
                    delayPreviewBadge.style.background = '#DCFCE7';
                    delayPreviewBadge.style.color = '#15803D';
                }
            }
        });
    }

    // Tải danh sách link đã đăng ban đầu
    loadPostedLinks();

    // ---- Google Sheet Group Sync & Deduplication ----
    function setupGoogleSheetSync() {
        const syncSheetGroupsBtn = document.getElementById('sync-sheet-groups-btn');
        const toggleSheetModalBtn = document.getElementById('toggle-sheet-modal-btn');
        const sheetConfigContainer = document.getElementById('sheet-config-container');
        const customSheetUrlInput = document.getElementById('custom-sheet-url-input');
        const sheetActiveOnlyCheckbox = document.getElementById('sheet-active-only-checkbox');
        const sheetSyncStatusMsg = document.getElementById('sheet-sync-status-msg');
        const joinSyncSheetBtn = document.getElementById('join-sync-sheet-btn');
        const groupManagerSyncSheetBtn = document.getElementById('group-manager-sync-sheet-btn');

        if (toggleSheetModalBtn && sheetConfigContainer) {
            toggleSheetModalBtn.addEventListener('click', () => {
                sheetConfigContainer.classList.toggle('hidden');
            });
        }

        async function triggerSheetSync(targetTextarea, btnElement) {
            const customUrl = customSheetUrlInput ? customSheetUrlInput.value.trim() : '';
            const filterActive = sheetActiveOnlyCheckbox ? sheetActiveOnlyCheckbox.checked : false;

            const originalBtnText = btnElement ? btnElement.innerHTML : '';
            if (btnElement) {
                btnElement.disabled = true;
                btnElement.innerHTML = '⏳ Đang đồng bộ...';
            }

            appendLog('📥 [Google Sheets] Đang kết nối tải và đồng bộ danh sách nhóm từ Google Sheets...');

            try {
                const res = await fetch('/api/groups/sync-sheet', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sheet_url: customUrl,
                        filter_active_only: filterActive,
                        save_registry: true
                    })
                });
                const data = await res.json();

                if (data.success && data.groups) {
                    const urls = data.groups.map(g => g.url || g.raw_url).filter(Boolean);
                    if (targetTextarea) {
                        targetTextarea.value = urls.join('\n');
                    }

                    const uniqueCount = data.unique_count || data.selected_count || urls.length;
                    const dupCount = data.duplicates_count || 0;
                    const totalRows = data.total_rows || (uniqueCount + dupCount);

                    const successMsg = `Đã nạp ${urls.length} nhóm độc nhất từ Google Sheets! (Lọc bỏ ${dupCount} link trùng lặp)`;
                    showToast(successMsg, 'success');
                    appendLog(`✅ [Google Sheets Sync] ${successMsg}`);
                    appendLog(`📊 Chi tiết dữ liệu Sheet: ${totalRows} dòng tổng cộng, ${urls.length} nhóm hợp lệ.`);

                    if (data.duplicates_details && data.duplicates_details.length > 0) {
                        const dupSummary = data.duplicates_details.slice(0, 5).map(d => `Dòng ${d.duplicate_row} trùng Dòng ${d.first_row} (${d.name || d.duplicate_url})`).join('; ');
                        appendLog(`⚠️ Phát hiện ${data.duplicates_details.length} vị trí trùng trong Sheet: ${dupSummary}${data.duplicates_details.length > 5 ? '...' : ''}`);
                    }

                    if (sheetSyncStatusMsg) {
                        sheetSyncStatusMsg.style.display = 'block';
                        sheetSyncStatusMsg.textContent = `Đã nạp lúc ${new Date().toLocaleTimeString('vi-VN')}: ${urls.length} nhóm (lọc ${dupCount} trùng).`;
                    }
                } else {
                    const errMsg = data.error || 'Không thể đồng bộ nhóm từ Google Sheets.';
                    showToast(errMsg, 'error');
                    appendLog(`❌ [Google Sheets Sync Lỗi] ${errMsg}`);
                }
            } catch (err) {
                const errMsg = `Lỗi kết nối đồng bộ: ${err.message}`;
                showToast(errMsg, 'error');
                appendLog(`❌ [Google Sheets Sync Lỗi] ${errMsg}`);
            } finally {
                if (btnElement) {
                    btnElement.disabled = false;
                    btnElement.innerHTML = originalBtnText;
                }
            }
        }

        if (syncSheetGroupsBtn) {
            syncSheetGroupsBtn.addEventListener('click', () => {
                triggerSheetSync(targetInput, syncSheetGroupsBtn);
            });
        }

        if (joinSyncSheetBtn) {
            const joinGroupUrls = document.getElementById('join-group-urls');
            joinSyncSheetBtn.addEventListener('click', () => {
                triggerSheetSync(joinGroupUrls, joinSyncSheetBtn);
            });
        }

        if (groupManagerSyncSheetBtn) {
            groupManagerSyncSheetBtn.addEventListener('click', async () => {
                const origText = groupManagerSyncSheetBtn.innerHTML;
                groupManagerSyncSheetBtn.disabled = true;
                groupManagerSyncSheetBtn.innerHTML = '⏳ Đang nạp...';
                try {
                    const res = await fetch('/api/groups/sync-sheet', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ save_registry: true })
                    });
                    const data = await res.json();
                    if (data.success) {
                        showToast(`Đã đồng bộ ${data.unique_count} nhóm vào kho quản lý!`, 'success');
                        appendLog(`✅ [Group Manager] Đã nạp ${data.unique_count} nhóm từ Google Sheets vào kho dữ liệu.`);
                        const refreshBtn = document.getElementById('group-manager-refresh-btn');
                        if (refreshBtn) refreshBtn.click();
                    } else {
                        showToast(data.error || 'Lỗi đồng bộ', 'error');
                    }
                } catch (e) {
                    showToast(`Lỗi: ${e.message}`, 'error');
                } finally {
                    groupManagerSyncSheetBtn.disabled = false;
                    groupManagerSyncSheetBtn.innerHTML = origText;
                }
            });
        }
    }
    setupGoogleSheetSync();

    // Khởi tạo trạng thái cách ly panel theo tab mặc định & nạp cấu hình hệ thống
    applyTabIsolation(currentMode);
    loadSettings();

    syncActiveJobState();
    window.setInterval(() => syncActiveJobState(), 3000);
    window.setInterval(() => { if (currentMode === 'queue') loadWorkflowTasks(); }, 3000);

    // In phiên bản hệ thống vào nhật ký hoạt động
    setTimeout(async () => {
        let ver = 'v6.1.1';
        let build = '2026-09-09';
        try {
            const res = await fetch('/api/app-info');
            const data = await res.json();
            if (data.version) ver = `v${data.version}`;
            if (data.built_at) build = data.built_at;
        } catch (e) {}
        appendLog(`🚀 FB AUTOMATION SYSTEM — PHIÊN BẢN ${ver} [Build: ${build}]`);
        appendLog('💡 Hệ thống tự động hóa Facebook: Sẵn sàng tác vụ Đăng bài, Nuôi nick & Gia nhập nhóm.');
        appendLog('🛡️ Chế độ chống spam: Giãn cách an toàn & Hỗ trợ xoay tua Profile tự động.');
        appendLog('📋 Quy trình duyệt: Hỗ trợ Đưa vào hàng đợi & bấm Duyệt bài trước khi đăng.');
    }, 500);
});
