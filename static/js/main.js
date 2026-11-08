/* ============================================================
   EASYTECH THATTA — main.js (Phase 2)
   Lightweight UI glue code. No external dependencies.
   ============================================================ */

(function () {
    'use strict';

    /* ============================================================
       1. SIDEBAR TOGGLE + COLLAPSE
       - Mobile (<992px): slide-in with backdrop
       - Desktop (>=992px): collapse to icon-only, persisted in localStorage
       ============================================================ */
    const Sidebar = {
        el: null,
        toggle: null,
        backdrop: null,
        STORAGE_KEY: 'easystech.sidebar.collapsed',

        init() {
            this.el = document.getElementById('appSidebar');
            this.toggle = document.getElementById('sidebarToggle');
            this.backdrop = document.getElementById('sidebarBackdrop');

            if (!this.el || !this.toggle) return;

            // Restore desktop collapse state
            if (window.innerWidth >= 992) {
                const collapsed = localStorage.getItem(this.STORAGE_KEY) === '1';
                if (collapsed) {
                    document.body.classList.add('sidebar-collapsed');
                }
            }

            this.toggle.addEventListener('click', () => this.handleToggle());

            if (this.backdrop) {
                this.backdrop.addEventListener('click', () => this.closeMobile());
            }

            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.el.classList.contains('show')) {
                    this.closeMobile();
                }
            });

            let resizeTimer;
            window.addEventListener('resize', () => {
                clearTimeout(resizeTimer);
                resizeTimer = setTimeout(() => {
                    if (window.innerWidth >= 992) {
                        this.closeMobile();
                    }
                }, 150);
            });
        },

        handleToggle() {
            if (window.innerWidth < 992) {
                if (this.el.classList.contains('show')) {
                    this.closeMobile();
                } else {
                    this.openMobile();
                }
            } else {
                document.body.classList.toggle('sidebar-collapsed');
                const isCollapsed = document.body.classList.contains('sidebar-collapsed');
                localStorage.setItem(this.STORAGE_KEY, isCollapsed ? '1' : '0');
            }
        },

        openMobile() {
            this.el.classList.add('show');
            if (this.backdrop) this.backdrop.classList.add('show');
            document.body.style.overflow = 'hidden';
        },

        closeMobile() {
            this.el.classList.remove('show');
            if (this.backdrop) this.backdrop.classList.remove('show');
            document.body.style.overflow = '';
        }
    };

    /* ============================================================
       2. TOAST SYSTEM
       Exposes window.Toast.{success,error,warning,info}
       ============================================================ */
    const Toast = {
        containerId: 'toastContainer',

        show(message, variant, duration = 4000) {
            const container = document.getElementById(this.containerId);
            if (!container || typeof bootstrap === 'undefined') {
                console.warn('[Toast] Container or Bootstrap not available');
                return;
            }

            const map = {
                success: { cls: 'text-bg-success', icon: 'check-circle-fill' },
                error:   { cls: 'text-bg-danger',  icon: 'exclamation-octagon-fill' },
                warning: { cls: 'text-bg-warning', icon: 'exclamation-triangle-fill' },
                info:    { cls: 'text-bg-info',    icon: 'info-circle-fill' }
            };
            const cfg = map[variant] || map.info;

            const toastEl = document.createElement('div');
            toastEl.className = 'toast ' + cfg.cls;
            toastEl.setAttribute('role', 'alert');
            toastEl.setAttribute('aria-live', 'assertive');
            toastEl.setAttribute('aria-atomic', 'true');
            toastEl.innerHTML = `
                <div class="toast-body">
                    <i class="bi bi-${cfg.icon}"></i>
                    <span class="flex-grow-1">${this._escape(message)}</span>
                    <button type="button" class="btn-close btn-close-white ms-2"
                            data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            `;

            container.appendChild(toastEl);

            const instance = new bootstrap.Toast(toastEl, { delay: duration });
            instance.show();

            toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
        },

        success(msg, duration) { this.show(msg, 'success', duration); },
        error(msg, duration)   { this.show(msg, 'error', duration); },
        warning(msg, duration) { this.show(msg, 'warning', duration); },
        info(msg, duration)    { this.show(msg, 'info', duration); },

        _escape(text) {
            const div = document.createElement('div');
            div.textContent = String(text);
            return div.innerHTML;
        }
    };

    /* ============================================================
       3. CONFIRM MODAL (Promise-based)
       Exposes window.Confirm.show({title, message, confirmText,
                                   cancelText, variant})
       Returns Promise<boolean>
       ============================================================ */
    const Confirm = {
        show(options = {}) {
            return new Promise((resolve) => {
                const modalEl = document.getElementById('globalConfirmModal');
                if (!modalEl || typeof bootstrap === 'undefined') {
                    // Fallback to native confirm if modal missing
                    resolve(window.confirm(options.message || 'Are you sure?'));
                    return;
                }

                const titleEl = modalEl.querySelector('#globalConfirmTitle');
                const msgEl   = modalEl.querySelector('#globalConfirmMessage');
                const okBtn   = modalEl.querySelector('#globalConfirmOk');
                const cancelBtn = modalEl.querySelector('#globalConfirmCancel');

                titleEl.textContent = options.title || 'Confirm';
                msgEl.textContent = options.message || 'Are you sure?';
                okBtn.textContent = options.confirmText || 'Confirm';
                cancelBtn.textContent = options.cancelText || 'Cancel';

                // Reset variant classes
                okBtn.classList.remove('btn-danger', 'btn-primary', 'btn-warning', 'btn-success');
                const variantClass = 'btn-' + (options.variant || 'primary');
                okBtn.classList.add(variantClass);

                const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });

                let resolved = false;

                const handleOk = () => {
                    if (resolved) return;
                    resolved = true;
                    cleanup();
                    modal.hide();
                    resolve(true);
                };

                const handleCancel = () => {
                    if (resolved) return;
                    resolved = true;
                    cleanup();
                    modal.hide();
                    resolve(false);
                };

                const cleanup = () => {
                    okBtn.removeEventListener('click', handleOk);
                    cancelBtn.removeEventListener('click', handleCancel);
                    modalEl.removeEventListener('hidden.bs.modal', handleCancel);
                };

                okBtn.addEventListener('click', handleOk);
                cancelBtn.addEventListener('click', handleCancel);
                modalEl.addEventListener('hidden.bs.modal', handleCancel, { once: true });

                modal.show();
            });
        }
    };

    /* ============================================================
       4. AUTO-DISMISS DJANGO MESSAGES (Phase 1 preserved)
       ============================================================ */
    function initAlerts() {
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach((alertEl) => {
            const timer = setTimeout(() => {
                if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
                    const instance = bootstrap.Alert.getOrCreateInstance(alertEl);
                    instance.close();
                } else {
                    alertEl.remove();
                }
            }, 5000);

            alertEl.addEventListener('closed.bs.alert', () => clearTimeout(timer));
        });

        // Clean empty wrapper
        document.querySelectorAll('.messages-wrapper').forEach((wrapper) => {
            wrapper.addEventListener('closed.bs.alert', () => {
                if (wrapper.querySelectorAll('.alert').length === 0) {
                    wrapper.remove();
                }
            });
        });
    }

    /* ============================================================
       5. TABLE ROW CLICK
       Rows with data-row-url navigate on click (not on link/button click)
       ============================================================ */
    function initTableRowClick() {
        document.querySelectorAll('tr[data-row-url]').forEach((row) => {
            row.style.cursor = 'pointer';
            row.addEventListener('click', (e) => {
                // Ignore if user clicked an interactive element
                if (e.target.closest('a, button, input, select, textarea, .dropdown-menu')) {
                    return;
                }
                window.location.href = row.getAttribute('data-row-url');
            });
        });
    }

    /* ============================================================
       6. BOOTSTRAP TOOLTIPS (auto-init)
       ============================================================ */
    function initTooltips() {
        if (typeof bootstrap === 'undefined' || !bootstrap.Tooltip) return;
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
            bootstrap.Tooltip.getOrCreateInstance(el);
        });
    }

    /* ============================================================
       7. DATETIME-LOCAL DEFAULT
       Auto-fill "now" for inputs[type="datetime-local"][data-now]
       ============================================================ */
    function initDateTimeNow() {
        document.querySelectorAll('input[type="datetime-local"][data-now]').forEach((input) => {
            if (!input.value) {
                const now = new Date();
                const tzOffset = now.getTimezoneOffset() * 60000;
                input.value = new Date(now - tzOffset).toISOString().slice(0, 16);
            }
        });
    }

    /* ============================================================
       INIT ON DOM READY
       ============================================================ */
    document.addEventListener('DOMContentLoaded', () => {
        Sidebar.init();
        initAlerts();
        initTableRowClick();
        initTooltips();
        initDateTimeNow();
    });

    /* ============================================================
       GLOBAL EXPORTS
       ============================================================ */
    window.Toast = Toast;
    window.Confirm = Confirm;

})();