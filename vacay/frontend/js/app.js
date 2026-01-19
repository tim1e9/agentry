// Main application module - handles routing, views, and UI state
import { Auth } from './auth.js';
import { API, ApiError } from './api.js';

class VacationApp {
    constructor() {
        this.currentView = 'dashboard';
        this.employee = null;
        this.balance = null;
        this.vacations = [];
        this.holidaysYear = new Date().getFullYear();
        this.init();
    }

    init() {
        // Check authentication
        if (Auth.isAuthenticated()) {
            this.showMainApp();
            this.loadUserData();
        } else {
            this.showLogin();
        }

        this.setupEventListeners();
    }

    setupEventListeners() {
        // Login button
        document.getElementById('login-btn')?.addEventListener('click', () => {
            Auth.login();
        });

        // Logout button
        document.getElementById('logout-btn')?.addEventListener('click', () => {
            Auth.logout();
        });

        // Navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const view = e.target.dataset.view;
                this.switchView(view);
            });
        });

        // Corporate holidays controls
        const holidaysYearSelect = document.getElementById('holidays-year');
        const holidaysRefreshBtn = document.getElementById('holidays-refresh');

        if (holidaysYearSelect) {
            const currentYear = new Date().getFullYear();
            const years = [currentYear - 1, currentYear, currentYear + 1];
            holidaysYearSelect.innerHTML = years
                .map(y => `<option value="${y}" ${y === this.holidaysYear ? 'selected' : ''}>${y}</option>`)
                .join('');

            holidaysYearSelect.addEventListener('change', (e) => {
                this.holidaysYear = parseInt(e.target.value);
                this.loadHolidays();
            });
        }

        holidaysRefreshBtn?.addEventListener('click', () => this.loadHolidays());

        // Vacation form
        const form = document.getElementById('vacation-form');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitVacationRequest();
            });

            // Date change listeners for business days calculation
            const startDate = document.getElementById('start-date');
            const endDate = document.getElementById('end-date');
            
            startDate?.addEventListener('change', () => this.calculateBusinessDays());
            endDate?.addEventListener('change', () => this.calculateBusinessDays());

            // Cancel button
            document.getElementById('cancel-btn')?.addEventListener('click', () => {
                form.reset();
                document.getElementById('calculated-days').textContent = '-';
                document.getElementById('form-error').classList.add('hidden');
                this.switchView('dashboard');
            });
        }
    }

    showLogin() {
        document.getElementById('login-view').classList.remove('hidden');
        document.getElementById('main-app').classList.add('hidden');
    }

    showMainApp() {
        document.getElementById('login-view').classList.add('hidden');
        document.getElementById('main-app').classList.remove('hidden');
    }

    switchView(viewName) {
        // Update nav links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.view === viewName);
        });

        // Update content views
        document.querySelectorAll('.content-view').forEach(view => {
            view.classList.remove('active');
        });
        document.getElementById(`${viewName}-view`)?.classList.add('active');

        this.currentView = viewName;

        // Load data for view
        if (viewName === 'dashboard') {
            this.loadDashboard();
        } else if (viewName === 'vacations') {
            this.loadVacations();
        } else if (viewName === 'holidays') {
            this.loadHolidays();
        }
    }

    async loadUserData() {
        try {
            this.employee = await API.getProfile();
            Auth.setUser(this.employee);
            
            const name = this.employee.first_name 
                ? `${this.employee.first_name} ${this.employee.last_name || ''}`.trim()
                : this.employee.email;
            
            document.getElementById('user-name').textContent = name;

            // Load initial view
            this.loadDashboard();
        } catch (error) {
            this.showToast(error.message, 'error');
            if (error.status === 401) {
                Auth.logout();
            }
        }
    }

    async loadDashboard() {
        try {
            // Load balance
            this.balance = await API.getBalance();
            this.updateBalanceDisplay();

            // Load upcoming vacations (future only)
            const allVacations = await API.getVacations();
            const today = new Date().toISOString().split('T')[0];
            const upcoming = allVacations.filter(v => v.start_date >= today);
            
            this.renderUpcomingVacations(upcoming);
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    updateBalanceDisplay() {
        if (!this.balance) return;

        document.getElementById('vacation-available').textContent = this.balance.vacation_available;
        document.getElementById('vacation-accrued').textContent = this.balance.vacation_accrued;
        document.getElementById('vacation-used').textContent = this.balance.vacation_used;
        document.getElementById('vacation-carryover').textContent = this.balance.vacation_carryover;
        document.getElementById('holidays-available').textContent = this.balance.optional_holidays_available;
        document.getElementById('holidays-used').textContent = this.balance.optional_holidays_used;
    }

    renderUpcomingVacations(vacations) {
        const container = document.getElementById('upcoming-vacations');
        
        if (vacations.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📅</div>
                    <p>No upcoming time off scheduled</p>
                </div>
            `;
            return;
        }

        container.innerHTML = vacations
            .sort((a, b) => a.start_date.localeCompare(b.start_date))
            .slice(0, 5) // Show max 5 upcoming
            .map(v => this.createVacationCard(v))
            .join('');
    }

    async loadVacations() {
        const container = document.getElementById('all-vacations');
        container.innerHTML = '<div class="loading">Loading...</div>';

        try {
            this.vacations = await API.getVacations();
            
            if (this.vacations.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">🏖️</div>
                        <p>No vacation requests yet</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = this.vacations
                .sort((a, b) => b.start_date.localeCompare(a.start_date))
                .map(v => this.createVacationCard(v, true))
                .join('');

            // Add delete listeners
            this.setupDeleteListeners();
        } catch (error) {
            container.innerHTML = `<div class="error-message">${error.message}</div>`;
        }
    }

    async loadHolidays() {
        const container = document.getElementById('corporate-holidays');
        if (!container) return;

        container.innerHTML = '<div class="loading">Loading...</div>';

        try {
            const holidays = await API.getHolidays(this.holidaysYear);

            if (!holidays || holidays.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📅</div>
                        <p>No corporate holidays found for ${this.holidaysYear}</p>
                    </div>
                `;
                return;
            }

            // Backend returns items like: { name: string, date: "YYYY-MM-DD" }
            container.innerHTML = holidays
                .sort((a, b) => (a.date || '').localeCompare(b.date || ''))
                .map(h => `
                    <div class="holiday-card">
                        <div class="holiday-name">${this.escapeHtml(h.name || 'Holiday')}</div>
                        <div class="holiday-date">${this.formatHolidayDate(h.date)}</div>
                    </div>
                `)
                .join('');
        } catch (error) {
            container.innerHTML = `<div class="error-message">${error.message}</div>`;
        }
    }

    formatHolidayDate(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr + 'T00:00:00');
        if (Number.isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = String(value);
        return div.innerHTML;
    }

    createVacationCard(vacation, showActions = false) {
        const today = new Date().toISOString().split('T')[0];
        const isPast = vacation.start_date < today;
        const typeClass = vacation.vacation_type === 'optional_holiday' ? 'optional-holiday' : '';
        const pastClass = isPast ? 'past' : '';

        const badge = vacation.vacation_type === 'optional_holiday' 
            ? '<span class="vacation-type-badge optional-holiday">Optional Holiday</span>'
            : '<span class="vacation-type-badge">Vacation</span>';

        const actions = showActions && !isPast ? `
            <div class="vacation-actions">
                <button class="danger-btn delete-vacation-btn" data-id="${vacation.id}">Delete</button>
            </div>
        ` : '';

        const notes = vacation.notes ? `
            <div class="vacation-notes">"${vacation.notes}"</div>
        ` : '';

        return `
            <div class="vacation-card ${typeClass} ${pastClass}">
                <div class="vacation-header">
                    <div class="vacation-type">
                        ${this.formatDateRange(vacation.start_date, vacation.end_date)}
                        ${badge}
                    </div>
                </div>
                <div class="vacation-days">
                    ${vacation.business_days} business day${vacation.business_days !== 1 ? 's' : ''}
                </div>
                ${notes}
                ${actions}
            </div>
        `;
    }

    formatDateRange(start, end) {
        const startDate = new Date(start + 'T00:00:00');
        const endDate = new Date(end + 'T00:00:00');
        
        const options = { month: 'short', day: 'numeric', year: 'numeric' };
        
        if (start === end) {
            return startDate.toLocaleDateString('en-US', options);
        }
        
        return `${startDate.toLocaleDateString('en-US', options)} - ${endDate.toLocaleDateString('en-US', options)}`;
    }

    setupDeleteListeners() {
        document.querySelectorAll('.delete-vacation-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const id = parseInt(e.target.dataset.id);
                if (confirm('Are you sure you want to delete this vacation request?')) {
                    await this.deleteVacation(id);
                }
            });
        });
    }

    async deleteVacation(vacationId) {
        try {
            await API.deleteVacation(vacationId);
            this.showToast('Vacation request deleted', 'success');
            this.loadVacations();
            this.loadDashboard(); // Refresh balance
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    async calculateBusinessDays() {
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;

        if (!startDate || !endDate) {
            document.getElementById('calculated-days').textContent = '-';
            return;
        }

        try {
            const result = await API.calculateBusinessDays(startDate, endDate);
            document.getElementById('calculated-days').textContent = result.business_days;
        } catch (error) {
            document.getElementById('calculated-days').textContent = '?';
            console.error('Failed to calculate business days:', error);
        }
    }

    async submitVacationRequest() {
        const formError = document.getElementById('form-error');
        formError.classList.add('hidden');

        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';

        const vacationData = {
            vacation_type: document.getElementById('vacation-type').value,
            start_date: document.getElementById('start-date').value,
            end_date: document.getElementById('end-date').value,
            notes: document.getElementById('notes').value
        };

        try {
            await API.createVacation(vacationData);
            this.showToast('Vacation request submitted successfully!', 'success');
            document.getElementById('vacation-form').reset();
            document.getElementById('calculated-days').textContent = '-';
            this.switchView('dashboard');
        } catch (error) {
            formError.textContent = error.message;
            formError.classList.remove('hidden');
            this.showToast(error.message, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Request';
        }
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 5000);
    }
}

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new VacationApp());
} else {
    new VacationApp();
}
