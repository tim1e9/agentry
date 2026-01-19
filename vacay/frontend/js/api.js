// API client module - handles all backend communication
import { Auth } from './auth.js';

const API_BASE = 'http://localhost:8001'; // TODO: Hard coded for now, adjust after full implementation

class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

async function handleResponse(response) {
    if (response.status === 401) {
        // Try to refresh token
        const refreshed = await Auth.refreshToken();
        if (!refreshed) {
            Auth.logout();
            throw new ApiError('Session expired. Please log in again.', 401);
        }
        throw new ApiError('Token refreshed, please retry', 401);
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Request failed' }));
        throw new ApiError(error.error || error.detail || 'Request failed', response.status);
    }

    return response.json();
}

async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
        ...options,
        headers: {
            ...Auth.getAuthHeaders(),
            ...options.headers
        }
    };

    try {
        const response = await fetch(url, config);
        return await handleResponse(response);
    } catch (error) {
        if (error instanceof ApiError) {
            throw error;
        }
        console.error('API request failed:', error);
        throw new ApiError('Network error. Please check your connection.', 0);
    }
}

export const API = {
    // Employee endpoints
    async getProfile() {
        return apiRequest('/employees/me');
    },

    async updateProfile(data) {
        return apiRequest('/employees/me', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    async getBalance() {
        return apiRequest('/employees/me/balance');
    },

    // Vacation endpoints
    async getVacations() {
        return apiRequest('/vacations');
    },

    async createVacation(vacationData) {
        return apiRequest('/vacations', {
            method: 'POST',
            body: JSON.stringify(vacationData)
        });
    },

    async deleteVacation(vacationId) {
        return apiRequest(`/vacations/${vacationId}`, {
            method: 'DELETE'
        });
    },

    async calculateBusinessDays(startDate, endDate) {
        return apiRequest('/vacations/calculate-days', {
            method: 'POST',
            body: JSON.stringify({
                start_date: startDate,
                end_date: endDate
            })
        });
    },

    // Holiday endpoints
    async getHolidays(year = new Date().getFullYear()) {
        return apiRequest(`/holidays?year=${year}`);
    }
};

export { ApiError };
