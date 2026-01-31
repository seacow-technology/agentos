/**
 * FloatingPet - 悬浮Assistant组件
 *
 * 功能特性:
 * - 可拖拽悬浮按钮 (FAB)
 * - 自动吸边停靠
 * - 位置持久化 (localStorage)
 * - 宠物动画面板
 * - 快捷入口: Chat / 创建任务 / RAG
 * - 完整的响应式设计
 * - FAB 和面板中同步Show Lottie 动画
 * - 面板中支持鼠标跟随 3D 旋转效果
 *
 * v0.3.2.6 - WebUI FloatingPet Component
 */

class FloatingPet {
    constructor(options = {}) {
        // Configuration选项
        this.options = {
            petType: options.petType || 'default',           // 宠物Type
            enableShortcuts: options.enableShortcuts !== false, // 快捷入口开关
            initialPosition: options.initialPosition || 'bottom-right', // 初始位置
            dragThreshold: options.dragThreshold || 5,       // 拖拽阈值 (px)
            snapToEdge: options.snapToEdge !== false,        // 是否吸边
            snapOffset: options.snapOffset || 20,            // 吸边偏移 (px)
            lottiePath: options.lottiePath || '/static/assets/lottie/pet-cute.json', // Lottie 动画路径
            ...options,
        };

        // Status管理
        this.state = {
            isPanelOpen: false,        // 面板是否Open
            isTaskModalOpen: false,    // 任务创建 Modal 是否Open
            fabPosition: { x: 0, y: 0 }, // FAB 位置
            currentEdge: 'right',      // 当前吸边方向
        };

        // 拖拽Status (独立管理，符合User要求)
        this._drag = {
            active: false,             // 是否正在拖拽
            pointerId: null,           // 跟踪的指针 ID
            startX: 0,                 // 拖拽起始 X
            startY: 0,                 // 拖拽起始 Y
            originLeft: 0,             // FAB 原始 left
            originTop: 0,              // FAB 原始 top
            moved: false,              // 是否超过阈值移动
            movedPx: 0,                // 移动距离 (px)
        };

        // 拖拽阈值
        this._DRAG_THRESHOLD = 6;

        // Lottie 动画实例
        this._lottie = null;           // 面板中的 Lottie
        this._lottieEl = null;
        this._lottieReady = false;
        this._fabLottie = null;        // FAB 中的 Lottie
        this._fabLottieEl = null;
        this._fabLottieReady = false;

        // DOM 引用
        this.elements = {
            fabButton: null,
            backdrop: null,
            panel: null,
            taskModal: null,
        };

        // 初始化
        this.init();
    }

    /**
     * 初始化组件
     */
    init() {
        console.log('FloatingPet: Initializing...');

        // 渲染 DOM（先渲染，确保元素存在）
        this.render();

        // 加载Save的位置（渲染后加载，确保能正确Settings位置）
        this.loadPosition();

        // Settings初始位置（确保位置正确应用）
        this.setFABPosition(this.state.fabPosition.x, this.state.fabPosition.y);

        // 绑定事件
        this.attachEventListeners();

        // 初始化 Lottie 动画
        this._initLottie();

        console.log('FloatingPet: Initialized successfully');
    }

    /**
     * 渲染 DOM 结构
     */
    render() {
        // 1. 创建 FAB 按钮
        this.renderFAB();

        // 2. 创建背景遮罩
        this.renderBackdrop();

        // 3. 创建面板
        this.renderPanel();

        // 4. 创建任务创建 Modal
        this.renderTaskModal();

        // 注意：位置Settings移到 init() 中，确保在 loadPosition() 之后执行
    }

    /**
     * 渲染 FAB 按钮
     */
    renderFAB() {
        const fab = document.createElement('button');
        fab.className = 'floating-pet-fab';
        fab.innerHTML = `
            <div class="floating-pet-fab-icon">
                <div id="fp-fab-lottie" class="fp-fab-lottie"></div>
            </div>
        `;
        fab.title = 'AgentOS Assistant';
        fab.setAttribute('aria-label', 'Open AgentOS assistant');

        document.body.appendChild(fab);
        this.elements.fabButton = fab;
    }

    /**
     * 渲染背景遮罩
     */
    renderBackdrop() {
        const backdrop = document.createElement('div');
        backdrop.className = 'floating-pet-backdrop';
        backdrop.style.display = 'none';

        document.body.appendChild(backdrop);
        this.elements.backdrop = backdrop;
    }

    /**
     * 渲染面板
     */
    renderPanel() {
        const panel = document.createElement('div');
        panel.className = 'floating-pet-panel';
        panel.style.display = 'none';

        panel.innerHTML = `
            <div class="floating-pet-panel-left">
                <div class="pet-animation-container">
                    <div class="fp-pet">
                        <div id="fp-lottie" class="fp-lottie" aria-label="Floating Pet"></div>
                    </div>
                    <div class="pet-greeting">
                        <div class="pet-greeting-title">AgentOS</div>
                        <div class="pet-greeting-subtitle">Your AI-powered assistant</div>
                    </div>
                </div>
            </div>
            <div class="floating-pet-panel-right">
                <div class="pet-shortcuts">
                    <button class="pet-shortcut-btn" data-action="chat">
                        <div class="pet-shortcut-icon">
                            <span class="material-icons md-24">add_comment</span>
                        </div>
                        <div class="pet-shortcut-content">
                            <div class="pet-shortcut-title">Chat</div>
                            <div class="pet-shortcut-desc">Start conversation</div>
                        </div>
                    </button>
                    <button class="pet-shortcut-btn" data-action="task">
                        <div class="pet-shortcut-icon">
                            <span class="material-icons md-24">check_circle</span>
                        </div>
                        <div class="pet-shortcut-content">
                            <div class="pet-shortcut-title">New Task</div>
                            <div class="pet-shortcut-desc">Create a task</div>
                        </div>
                    </button>
                    <button class="pet-shortcut-btn" data-action="rag">
                        <div class="pet-shortcut-icon">
                            <span class="material-icons md-24">search</span>
                        </div>
                        <div class="pet-shortcut-content">
                            <div class="pet-shortcut-title">Knowledge</div>
                            <div class="pet-shortcut-desc">Query playground</div>
                        </div>
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(panel);
        this.elements.panel = panel;
    }

    /**
     * 渲染任务创建 Modal
     */
    renderTaskModal() {
        const modal = document.createElement('div');
        modal.className = 'pet-task-modal';
        modal.style.display = 'none';

        modal.innerHTML = `
            <div class="pet-task-modal-content">
                <div class="pet-task-modal-header">
                    <h3>Create New Task</h3>
                    <button class="pet-task-modal-close" aria-label="Close modal">×</button>
                </div>
                <div class="pet-task-modal-body">
                    <textarea
                        class="pet-task-input"
                        placeholder="Describe your task..."
                        rows="4"
                    ></textarea>
                </div>
                <div class="pet-task-modal-footer">
                    <button class="pet-task-btn pet-task-btn-cancel">Cancel</button>
                    <button class="pet-task-btn pet-task-btn-submit">Create Task</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        this.elements.taskModal = modal;
    }

    /**
     * 绑定事件监听器
     */
    attachEventListeners() {
        // FAB 拖拽事件 (使用 Pointer Events 以支持触摸)
        // 按照User要求: pointerdown 只绑在 FAB 上
        this.elements.fabButton.addEventListener('pointerdown', this._onFabPointerDown.bind(this));

        // move/up/cancel 绑在 document 上，但必须检查 active 和 pointerId
        this._boundPointerMove = this._onDocPointerMove.bind(this);
        this._boundPointerUp = this._onDocPointerUp.bind(this);
        this._boundPointerCancel = this._onDocPointerCancel.bind(this);

        document.addEventListener('pointermove', this._boundPointerMove);
        document.addEventListener('pointerup', this._boundPointerUp);
        document.addEventListener('pointercancel', this._boundPointerCancel);

        // 捕获阶段拦截 click，防止拖拽后触发
        this.elements.fabButton.addEventListener('click', this._onFabClick.bind(this), true);

        // 背景遮罩点击Close
        this.elements.backdrop.addEventListener('click', () => {
            this.closePanel();
        });

        // 面板快捷按钮
        const shortcuts = this.elements.panel.querySelectorAll('.pet-shortcut-btn');
        shortcuts.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.currentTarget.dataset.action;
                this.handleShortcutAction(action);
            });
        });

        // 任务 Modal 事件
        const closeBtn = this.elements.taskModal.querySelector('.pet-task-modal-close');
        const cancelBtn = this.elements.taskModal.querySelector('.pet-task-btn-cancel');
        const submitBtn = this.elements.taskModal.querySelector('.pet-task-btn-submit');

        closeBtn.addEventListener('click', () => this.closeTaskModal());
        cancelBtn.addEventListener('click', () => this.closeTaskModal());
        submitBtn.addEventListener('click', () => this.submitTask());

        // Modal 背景点击Close
        this.elements.taskModal.addEventListener('click', (e) => {
            if (e.target === this.elements.taskModal) {
                this.closeTaskModal();
            }
        });

        // 键盘事件
        document.addEventListener('keydown', (e) => {
            // Esc 键Close面板或 Modal
            if (e.key === 'Escape') {
                if (this.state.isTaskModalOpen) {
                    this.closeTaskModal();
                } else if (this.state.isPanelOpen) {
                    this.closePanel();
                }
            }
            // Alt + P Open面板
            if (e.altKey && e.key === 'p') {
                e.preventDefault();
                this.togglePanel();
            }
        });

        // 窗口 resize 事件 (防抖)
        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                this.handleResize();
            }, 300);
        });
    }

    /**
     * FAB Pointer Down - 只在 FAB 上触发
     * 按照User要求: 只有 FAB 自己能Start拖拽
     */
    _onFabPointerDown(e) {
        // 只处理主按钮 (鼠标左键或触摸)
        if (e.button != null && e.button !== 0) return;

        e.preventDefault();
        e.stopPropagation();

        // 初始化拖拽Status
        this._drag.active = true;
        this._drag.pointerId = e.pointerId;
        this._drag.startX = e.clientX;
        this._drag.startY = e.clientY;
        this._drag.moved = false;
        this._drag.movedPx = 0;

        // 记录 FAB 初始位置
        const rect = this.elements.fabButton.getBoundingClientRect();
        this._drag.originLeft = rect.left;
        this._drag.originTop = rect.top;

        // 按照User要求: 立即 capture 指针
        try {
            this.elements.fabButton.setPointerCapture(e.pointerId);
        } catch (err) {
            console.warn('FloatingPet: setPointerCapture failed', err);
        }

        // 如果面板Open，立即Close
        if (this._isPanelOpen()) {
            this.closePanel();
        }
    }

    /**
     * Document Pointer Move - 检查 active 和 pointerId
     * 按照User要求: 必须检查 this._drag.active 和 pointerId
     */
    _onDocPointerMove(e) {
        if (!this._drag.active) return;
        if (e.pointerId !== this._drag.pointerId) return;

        e.preventDefault();

        const dx = e.clientX - this._drag.startX;
        const dy = e.clientY - this._drag.startY;
        const dist = Math.hypot(dx, dy);

        this._drag.movedPx = dist;

        // 按照User要求: 拖拽阈值 6px
        if (!this._drag.moved && dist < this._DRAG_THRESHOLD) {
            return; // 未超过阈值，不移动
        }

        // 标记为已移动
        if (!this._drag.moved) {
            this._drag.moved = true;
            this.elements.fabButton.classList.add('is-dragging');
        }

        // 计算新位置
        const newX = this._drag.originLeft + dx;
        const newY = this._drag.originTop + dy;

        // 边界约束
        const clampedPos = this.clampToBounds(newX, newY);
        this.setFABPosition(clampedPos.x, clampedPos.y, false);
    }

    /**
     * Document Pointer Up - 检查 active 和 pointerId
     * 按照User要求: 必须检查并 cleanup
     */
    _onDocPointerUp(e) {
        if (!this._drag.active) return;
        if (e.pointerId !== this._drag.pointerId) return;

        e.preventDefault();

        const wasMoved = this._drag.moved;

        // 清理拖拽Status
        this._drag.active = false;
        this.elements.fabButton.classList.remove('is-dragging');

        // 释放 pointer capture
        try {
            this.elements.fabButton.releasePointerCapture(e.pointerId);
        } catch (err) {
            // 忽略Error (可能已经释放)
        }

        if (wasMoved) {
            // 拖拽结束: 执行吸边动画
            this._snapToEdge();
            this._savePosition();
        } else {
            // 点击: Open/Close面板
            this.togglePanel();
        }
    }

    /**
     * Document Pointer Cancel - 清理Status
     * 按照User要求: 必须处理 pointercancel
     */
    _onDocPointerCancel(e) {
        if (!this._drag.active) return;
        if (e.pointerId !== this._drag.pointerId) return;

        // 清理拖拽Status
        this._drag.active = false;
        this.elements.fabButton.classList.remove('is-dragging');

        try {
            this.elements.fabButton.releasePointerCapture(e.pointerId);
        } catch (err) {
            // 忽略Error
        }
    }

    /**
     * FAB Click - 捕获阶段拦截
     * 按照User要求: 在捕获阶段拦截 click，防止拖拽后触发
     */
    _onFabClick(e) {
        if (this._drag.moved) {
            // 如果刚才拖拽过，阻止 click
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
        }
    }

    /**
     * 检查面板是否Open
     */
    _isPanelOpen() {
        return this.state.isPanelOpen;
    }

    /**
     * 吸边动画
     */
    _snapToEdge() {
        if (!this.options.snapToEdge) return;

        const snapPos = this.calculateSnapPosition();
        this.animateToPosition(snapPos.x, snapPos.y);
        this.state.currentEdge = snapPos.edge;
    }

    /**
     * Save位置 (包装方法)
     */
    _savePosition() {
        this.savePosition();
    }

    /**
     * 边界约束 - 确保 FAB 不会超出视口
     */
    clampToBounds(x, y) {
        const fabRect = this.elements.fabButton.getBoundingClientRect();
        const fabWidth = fabRect.width;
        const fabHeight = fabRect.height;

        const minX = 0;
        const minY = 0;
        const maxX = window.innerWidth - fabWidth;
        const maxY = window.innerHeight - fabHeight;

        return {
            x: Math.max(minX, Math.min(maxX, x)),
            y: Math.max(minY, Math.min(maxY, y)),
        };
    }

    /**
     * 计算吸边位置
     */
    calculateSnapPosition() {
        const fabRect = this.elements.fabButton.getBoundingClientRect();
        const fabCenterX = fabRect.left + fabRect.width / 2;
        const viewportWidth = window.innerWidth;

        // 根据中心点判断吸向左边还是右边
        const snapToLeft = fabCenterX < viewportWidth / 2;

        let targetX, targetY;
        const edge = snapToLeft ? 'left' : 'right';

        if (snapToLeft) {
            targetX = this.options.snapOffset;
        } else {
            targetX = viewportWidth - fabRect.width - this.options.snapOffset;
        }

        // Y 轴保持不变
        targetY = fabRect.top;

        // 再次应用边界约束
        const clampedPos = this.clampToBounds(targetX, targetY);

        return {
            x: clampedPos.x,
            y: clampedPos.y,
            edge: edge,
        };
    }

    /**
     * 缓动动画移动到指定位置
     */
    animateToPosition(targetX, targetY) {
        const startX = parseFloat(this.elements.fabButton.style.left) || 0;
        const startY = parseFloat(this.elements.fabButton.style.top) || 0;
        const duration = 300; // ms
        const startTime = Date.now();

        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // ease-out 缓动函数
            const easeOut = 1 - Math.pow(1 - progress, 3);

            const currentX = startX + (targetX - startX) * easeOut;
            const currentY = startY + (targetY - startY) * easeOut;

            this.setFABPosition(currentX, currentY, false);

            if (progress < 1) {
                requestAnimationFrame(animate);
            } else {
                // 动画Complete,Save最终位置
                this.state.fabPosition = { x: targetX, y: targetY };
            }
        };

        requestAnimationFrame(animate);
    }

    /**
     * Settings FAB 位置
     */
    setFABPosition(x, y, updateState = true) {
        this.elements.fabButton.style.left = `${x}px`;
        this.elements.fabButton.style.top = `${y}px`;

        if (updateState) {
            this.state.fabPosition = { x, y };
        }
    }

    /**
     * Open面板
     */
    openPanel() {
        if (this.state.isPanelOpen) return;

        this.state.isPanelOpen = true;

        // Show背景遮罩
        this.elements.backdrop.style.display = 'block';
        requestAnimationFrame(() => {
            this.elements.backdrop.classList.add('is-visible');
        });

        // Show面板
        this.elements.panel.style.display = 'flex';

        // 根据 FAB 位置调整面板位置
        this.updatePanelPosition();

        // 触发动画
        requestAnimationFrame(() => {
            this.elements.panel.classList.add('is-visible');
        });

        // FAB 添加激活Status
        this.elements.fabButton.classList.add('is-active');

        // 播放 Lottie 动画
        if (this._lottie && this._lottieReady) {
            this._lottie.play();
        }
    }

    /**
     * Close面板
     */
    closePanel() {
        if (!this.state.isPanelOpen) return;

        this.state.isPanelOpen = false;

        // Hide背景遮罩
        this.elements.backdrop.classList.remove('is-visible');
        setTimeout(() => {
            this.elements.backdrop.style.display = 'none';
        }, 300);

        // Hide面板
        this.elements.panel.classList.remove('is-visible');
        setTimeout(() => {
            this.elements.panel.style.display = 'none';
        }, 300);

        // FAB 移除激活Status
        this.elements.fabButton.classList.remove('is-active');

        // Pause Lottie 动画
        if (this._lottie && this._lottieReady) {
            this._lottie.pause();
        }
    }

    /**
     * 切换面板Status
     */
    togglePanel() {
        if (this.state.isPanelOpen) {
            this.closePanel();
        } else {
            this.openPanel();
        }
    }

    /**
     * 更新面板位置 (根据 FAB 位置)
     */
    updatePanelPosition() {
        const fabRect = this.elements.fabButton.getBoundingClientRect();
        const panelRect = this.elements.panel.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const panelGap = 24; // 增加面板与 FAB 的距离

        // 根据当前吸边方向决定面板位置
        if (this.state.currentEdge === 'right') {
            // FAB 在右侧,面板Show在左侧
            const panelLeft = fabRect.left - panelRect.width - panelGap;
            this.elements.panel.style.left = `${panelLeft}px`;
        } else {
            // FAB 在左侧,面板Show在右侧
            const panelLeft = fabRect.right + panelGap;
            this.elements.panel.style.left = `${panelLeft}px`;
        }

        // 垂直居中对齐 FAB
        const panelTop = fabRect.top + fabRect.height / 2 - panelRect.height / 2;
        const clampedTop = Math.max(20, Math.min(viewportHeight - panelRect.height - 20, panelTop));
        this.elements.panel.style.top = `${clampedTop}px`;
    }

    /**
     * 处理快捷入口点击
     */
    handleShortcutAction(action) {
        this.closePanel();

        switch (action) {
            case 'chat':
                this.handleChatAction();
                break;
            case 'task':
                this.handleTaskAction();
                break;
            case 'rag':
                this.handleRagAction();
                break;
            default:
                console.warn(`FloatingPet: Unknown action: ${action}`);
        }
    }

    /**
     * Chat 快捷入口
     */
    handleChatAction() {
        if (typeof window.navigateToView === 'function') {
            window.navigateToView('chat');
            window.showToast('Opening Chat...', 'info', 1000);
        } else {
            console.error('FloatingPet: window.navigateToView not found');
            window.showToast('Navigation failed', 'error');
        }
    }

    /**
     * Task 快捷入口
     */
    handleTaskAction() {
        this.openTaskModal();
    }

    /**
     * RAG 快捷入口
     */
    handleRagAction() {
        if (typeof window.navigateToView === 'function') {
            window.navigateToView('knowledge-playground');
            window.showToast('Opening Knowledge Playground...', 'info', 1000);
        } else {
            console.error('FloatingPet: window.navigateToView not found');
            window.showToast('Navigation failed', 'error');
        }
    }

    /**
     * Open任务创建 Modal
     */
    openTaskModal() {
        this.state.isTaskModalOpen = true;
        this.elements.taskModal.style.display = 'flex';

        // 触发动画
        requestAnimationFrame(() => {
            this.elements.taskModal.classList.add('is-visible');
        });

        // 聚焦输入框
        const input = this.elements.taskModal.querySelector('.pet-task-input');
        setTimeout(() => input.focus(), 100);
    }

    /**
     * Close任务创建 Modal
     */
    closeTaskModal() {
        this.state.isTaskModalOpen = false;
        this.elements.taskModal.classList.remove('is-visible');

        setTimeout(() => {
            this.elements.taskModal.style.display = 'none';
            // Clear输入
            const input = this.elements.taskModal.querySelector('.pet-task-input');
            input.value = '';
        }, 300);
    }

    /**
     * 提交任务
     */
    async submitTask() {
        const input = this.elements.taskModal.querySelector('.pet-task-input');
        const description = input.value.trim();

        if (!description) {
            window.showToast('Please enter task description', 'warning');
            return;
        }

        // Disable按钮,Show加载Status
        const submitBtn = this.elements.taskModal.querySelector('.pet-task-btn-submit');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';

        try {
            // 调用 API 创建任务
            const result = await window.apiClient.post('/api/tasks', {
                description: description,
                status: 'pending',
                created_via: 'floating_pet',
            });

            if (result.ok) {
                window.showToast('Task created successfully!', 'success');
                this.closeTaskModal();

                // 跳转到 Tasks 面
                setTimeout(() => {
                    if (typeof window.navigateToView === 'function') {
                        window.navigateToView('tasks', { task_id: result.data.id });
                    }
                }, 500);
            } else {
                window.showToast(`Failed to create task: ${result.error}`, 'error');
            }
        } catch (error) {
            console.error('FloatingPet: Task creation error:', error);
            window.showToast('Failed to create task', 'error');
        } finally {
            // 恢复按钮
            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Task';
        }
    }

    /**
     * 初始化 Lottie 动画
     */
    _initLottie() {
        // 检查 lottie-web 是否加载
        if (!window.lottie) {
            console.warn('FloatingPet: lottie-web not loaded, using fallback');
            this._fallbackPet();
            this._fallbackFabPet();
            return;
        }

        // 初始化面板中的 Lottie
        this._initPanelLottie();

        // 初始化 FAB 中的 Lottie
        this._initFabLottie();
    }

    /**
     * 初始化面板中的 Lottie 动画
     */
    _initPanelLottie() {
        this._lottieEl = document.getElementById('fp-lottie');
        if (!this._lottieEl) {
            console.warn('FloatingPet: Panel Lottie container not found');
            return;
        }

        try {
            this._lottie = window.lottie.loadAnimation({
                container: this._lottieEl,
                renderer: 'svg',
                loop: true,
                autoplay: false, // 手动控制：Open面板才播放
                path: this.options.lottiePath,
                rendererSettings: {
                    progressiveLoad: true,
                    preserveAspectRatio: 'xMidYMid meet',
                },
            });

            // 动画加载Complete
            this._lottie.addEventListener('DOMLoaded', () => {
                this._lottieReady = true;
                console.log('FloatingPet: Panel Lottie animation loaded');

                // 如果面板当前是OpenStatus，直接播放
                if (this.state.isPanelOpen) {
                    this._lottie.play();
                }

                // 绑定 hover 旋转效果
                this._bindPetHover();
            });

            // 加载Failed降级
            this._lottie.addEventListener('data_failed', () => {
                console.warn('FloatingPet: Panel Lottie animation failed to load');
                this._fallbackPet();
            });
        } catch (e) {
            console.error('FloatingPet: Error initializing panel Lottie:', e);
            this._fallbackPet();
        }
    }

    /**
     * 初始化 FAB 中的 Lottie 动画
     */
    _initFabLottie() {
        this._fabLottieEl = document.getElementById('fp-fab-lottie');
        if (!this._fabLottieEl) {
            console.warn('FloatingPet: FAB Lottie container not found');
            return;
        }

        try {
            this._fabLottie = window.lottie.loadAnimation({
                container: this._fabLottieEl,
                renderer: 'svg',
                loop: true,
                autoplay: true, // FAB 中的动画一直播放
                path: this.options.lottiePath,
                rendererSettings: {
                    progressiveLoad: true,
                    preserveAspectRatio: 'xMidYMid meet',
                },
            });

            // 动画加载Complete
            this._fabLottie.addEventListener('DOMLoaded', () => {
                this._fabLottieReady = true;
                console.log('FloatingPet: FAB Lottie animation loaded');
            });

            // 加载Failed降级
            this._fabLottie.addEventListener('data_failed', () => {
                console.warn('FloatingPet: FAB Lottie animation failed to load');
                this._fallbackFabPet();
            });
        } catch (e) {
            console.error('FloatingPet: Error initializing FAB Lottie:', e);
            this._fallbackFabPet();
        }
    }

    /**
     * 降级方案：Show静态占位符（面板）
     */
    _fallbackPet() {
        if (this._lottieEl) {
            this._lottieEl.innerHTML = `
                <div style="font-size:48px; line-height:96px; text-align:center; color:#667EEA;">
                    <span class="material-icons md-18">pets</span>
                </div>
            `;
        }
    }

    /**
     * 降级方案：Show静态占位符（FAB）
     */
    _fallbackFabPet() {
        if (this._fabLottieEl) {
            this._fabLottieEl.innerHTML = `
                <span class="material-icons md-18">pets</span>
            `;
        }
    }

    /**
     * 绑定 3D 旋转效果
     */
    _bindPetHover() {
        const wrap = this._lottieEl?.parentElement;
        if (!wrap || !this._lottie) return;

        // 鼠标移动时 3D 旋转
        wrap.addEventListener('mousemove', (e) => {
            if (!this._lottie || !this._lottieReady) return;

            // 获取容器边界
            const rect = this._lottieEl.getBoundingClientRect();

            // 计算鼠标相对于容器的位置（-1 到 1）
            const x = (e.clientX - rect.left) / rect.width;  // 0 到 1
            const y = (e.clientY - rect.top) / rect.height;  // 0 到 1

            // 转换为 -1 到 1 的范围，中心点为 0
            const centerX = (x - 0.5) * 2;  // -1 到 1
            const centerY = (y - 0.5) * 2;  // -1 到 1

            // 计算 3D 旋转角度（最大 15 度）
            const maxRotation = 15;
            const rotateY = centerX * maxRotation;  // 左右旋转
            const rotateX = -centerY * maxRotation; // 上下旋转（负号使倾斜方向自然）

            // 应用 3D 变换
            this._lottieEl.style.transform =
                `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;

            // 加速动画
            this._lottie.setSpeed(1.5);
        });

        // 鼠标离开时恢复
        wrap.addEventListener('mouseleave', () => {
            if (this._lottie && this._lottieReady) {
                this._lottieEl.style.transform =
                    'perspective(1000px) rotateX(0deg) rotateY(0deg)';
                this._lottie.setSpeed(1.0);
            }
        });
    }

    /**
     * 获取宠物图标 (FAB)
     */
    getPetIcon() {
        const icons = {
            default: 'smart_toy',       // 机器人图标
            cat: 'pets',                // 宠物图标
            fox: 'cruelty_free',        // 狐狸图标
            robot: 'smart_toy',         // 机器人图标
            assistant: 'psychology',    // AI Assistant图标
            support: 'support_agent',   // 客服图标
        };
        return icons[this.options.petType] || icons.default;
    }

    /**
     * 获取宠物头像 (面板)
     */
    getPetAvatar() {
        return this.getPetIcon();
    }

    /**
     * 窗口 Resize 处理
     */
    handleResize() {
        // 重新验证 FAB 位置
        const fabRect = this.elements.fabButton.getBoundingClientRect();
        const clampedPos = this.clampToBounds(fabRect.left, fabRect.top);

        if (clampedPos.x !== fabRect.left || clampedPos.y !== fabRect.top) {
            this.setFABPosition(clampedPos.x, clampedPos.y);
            this.savePosition();
        }

        // 如果面板Open,更新面板位置
        if (this.state.isPanelOpen) {
            this.updatePanelPosition();
        }
    }

    /**
     * Save位置到 localStorage
     */
    savePosition() {
        const data = {
            x: this.state.fabPosition.x,
            y: this.state.fabPosition.y,
            edge: this.state.currentEdge,
            timestamp: Date.now(),
        };

        try {
            localStorage.setItem('agentos_floating_pet_position', JSON.stringify(data));
        } catch (error) {
            console.warn('FloatingPet: Failed to save position:', error);
        }
    }

    /**
     * 从 localStorage 加载位置
     */
    loadPosition() {
        try {
            const saved = localStorage.getItem('agentos_floating_pet_position');
            if (saved) {
                const data = JSON.parse(saved);

                // 验证数据有效性
                if (data.x !== undefined && data.y !== undefined) {
                    // 验证位置是否在当前视口内（保留一定边距）
                    const viewportWidth = window.innerWidth;
                    const viewportHeight = window.innerHeight;
                    const fabSize = 64;
                    const minMargin = 10; // 最小边距

                    // 确保位置合理（不在左上角，至少有一定边距）
                    if (data.x >= minMargin &&
                        data.x <= viewportWidth - fabSize - minMargin &&
                        data.y >= minMargin &&
                        data.y <= viewportHeight - fabSize - minMargin) {
                        this.state.fabPosition = { x: data.x, y: data.y };
                        this.state.currentEdge = data.edge || 'right';
                        console.log('FloatingPet: Loaded saved position:', data);
                        return;
                    } else {
                        console.log('FloatingPet: Saved position invalid, using default');
                    }
                }
            }
        } catch (error) {
            console.warn('FloatingPet: Failed to load position:', error);
        }

        // 使用默认位置
        this.setDefaultPosition();
    }

    /**
     * Settings默认位置
     */
    setDefaultPosition() {
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const fabSize = 64; // 默认 FAB 大小

        let x, y;

        switch (this.options.initialPosition) {
            case 'bottom-left':
                x = this.options.snapOffset;
                y = viewportHeight - fabSize - this.options.snapOffset;
                this.state.currentEdge = 'left';
                break;
            case 'top-right':
                x = viewportWidth - fabSize - this.options.snapOffset;
                y = this.options.snapOffset;
                this.state.currentEdge = 'right';
                break;
            case 'top-left':
                x = this.options.snapOffset;
                y = this.options.snapOffset;
                this.state.currentEdge = 'left';
                break;
            case 'bottom-right':
            default:
                x = viewportWidth - fabSize - this.options.snapOffset;
                y = viewportHeight - fabSize - this.options.snapOffset;
                this.state.currentEdge = 'right';
                break;
        }

        this.state.fabPosition = { x, y };
        console.log('FloatingPet: Using default position:', this.options.initialPosition);
    }

    /**
     * 销毁组件
     */
    destroy() {
        // 移除 document 级事件监听器
        if (this._boundPointerMove) {
            document.removeEventListener('pointermove', this._boundPointerMove);
        }
        if (this._boundPointerUp) {
            document.removeEventListener('pointerup', this._boundPointerUp);
        }
        if (this._boundPointerCancel) {
            document.removeEventListener('pointercancel', this._boundPointerCancel);
        }

        // 销毁 Lottie 动画
        if (this._lottie) {
            this._lottie.destroy();
            this._lottie = null;
        }

        // 移除 DOM
        if (this.elements.fabButton) this.elements.fabButton.remove();
        if (this.elements.backdrop) this.elements.backdrop.remove();
        if (this.elements.panel) this.elements.panel.remove();
        if (this.elements.taskModal) this.elements.taskModal.remove();

        console.log('FloatingPet: Destroyed');
    }
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FloatingPet;
}
