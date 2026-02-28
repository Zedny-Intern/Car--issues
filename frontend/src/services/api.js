// API Configuration
const API_BASE_URL = '/api/v1';

const formatApiErrorPayload = (payload) => {
    if (!payload) {
        return 'API request failed';
    }

    if (typeof payload === 'string') {
        return payload;
    }

    if (Array.isArray(payload)) {
        return payload.map((item) => formatApiErrorPayload(item)).filter(Boolean).join('\n');
    }

    if (typeof payload === 'object') {
        if (typeof payload.message === 'string' && payload.message.trim()) {
            return payload.message;
        }

        if (typeof payload.error === 'string' && payload.error.trim()) {
            return payload.error;
        }

        if (payload.errors) {
            return formatApiErrorPayload(payload.errors);
        }

        return Object.entries(payload)
            .map(([key, value]) => `${key}: ${formatApiErrorPayload(value)}`)
            .filter(Boolean)
            .join('\n');
    }

    return String(payload);
};

const sanitizeComplaintPayload = (formData) => {
    const payload = {
        customer_name: (formData.customer_name || '').trim(),
        customer_email: (formData.customer_email || '').trim(),
        customer_phone: (formData.customer_phone || '').trim(),
        license_plate: (formData.license_plate || '').trim(),
        car_make: (formData.car_make || '').trim(),
        car_model: (formData.car_model || '').trim(),
        complaint_text: (formData.complaint_text || '').trim(),
        crash: Boolean(formData.crash),
        fire: Boolean(formData.fire),
    };

    const yearValue = `${formData.car_year ?? ''}`.trim();
    const mileageValue = `${formData.car_mileage ?? ''}`.trim();

    if (yearValue !== '') {
        payload.car_year = Number(yearValue);
    }
    if (mileageValue !== '') {
        payload.car_mileage = Number(mileageValue);
    }

    return payload;
};

// API Client
const apiClient = {
    async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };

        const finalOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers,
            },
        };

        try {
            const response = await fetch(url, finalOptions);

            // Check if the response is ok before trying to parse JSON
            if (!response.ok) {
                // Try to parse JSON error, but fallback to text if HTML
                let errorMessage = 'API request failed';
                try {
                    const errorData = await response.json();
                    errorMessage = formatApiErrorPayload(errorData);
                } catch {
                    // If JSON parsing fails, it's likely an HTML error page
                    const textError = await response.text();
                    errorMessage = `Server error (${response.status}): ${response.statusText}`;
                    console.error('Server returned non-JSON error:', textError.substring(0, 200));
                }
                throw new Error(errorMessage);
            }

            // Parse successful response
            const data = await response.json();
            return { success: true, data };
        } catch (error) {
            console.error('API Error:', error);
            return { success: false, error: error.message };
        }
    },

    // Complaints
    async submitComplaint(formData) {
        return this.request(`${API_BASE_URL}/complaints/quick-submit/`, {
            method: 'POST',
            body: JSON.stringify(sanitizeComplaintPayload(formData)),
        });
    },

    async uploadComplaintDocument(complaintId, file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/complaints/${complaintId}/upload_document/`, {
            method: 'POST',
            body: formData,
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            return {
                success: false,
                message: payload?.error || payload?.message || `Upload failed (${response.status})`,
            };
        }
        return payload;
    },

    // Chat
    async createChatSession(complaintId) {
        return this.request(`${API_BASE_URL}/chat/sessions/`, {
            method: 'POST',
            body: JSON.stringify({ complaint_id: complaintId }),
        });
    },

    async getChatSession(sessionId) {
        return this.request(`${API_BASE_URL}/chat/sessions/${sessionId}/`);
    },

    async getChatSessions(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`${API_BASE_URL}/chat/sessions/?${queryString}`);
    },

    async closeChatSession(sessionId) {
        return this.request(`${API_BASE_URL}/chat/sessions/${sessionId}/close/`, {
            method: 'POST',
        });
    },

    async sendChatMessage(sessionId, message, images = []) {
        const url = `${API_BASE_URL}/chat/sessions/${sessionId}/send_message/`;

        const hasImages = Array.isArray(images) && images.length > 0;
        const requestOptions = hasImages
            ? (() => {
                const formData = new FormData();
                if (message) {
                    formData.append('message', message);
                }
                images.forEach((file) => formData.append('images', file));
                return {
                    method: 'POST',
                    body: formData,
                };
            })()
            : {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            };

        const response = await fetch(url, requestOptions);
        if (!response.ok) {
            const body = await response.text().catch(() => '');
            throw new Error(`Chat request failed (${response.status}): ${body.slice(0, 200)}`);
        }
        return response;
    },

    // Search
    async searchCarByPlate(licensePlate) {
        return this.request(
            `${API_BASE_URL}/cars/by_license_plate/?plate=${encodeURIComponent(licensePlate)}`
        );
    },

    async getCarHistory(carId) {
        return this.request(`${API_BASE_URL}/cars/${carId}/complaint_history/`);
    },
};

export default apiClient;
