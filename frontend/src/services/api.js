// API Configuration
const API_BASE_URL = '/api/v1';

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
                    errorMessage = errorData.message || errorData.errors || JSON.stringify(errorData);
                } catch (parseError) {
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
            body: JSON.stringify(formData),
        });
    },

    async uploadComplaintDocument(complaintId, file) {
        const formData = new FormData();
        formData.append('file', file);

        return fetch(`${API_BASE_URL}/complaints/${complaintId}/upload_document/`, {
            method: 'POST',
            body: formData,
        }).then(res => res.json());
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

    async sendChatMessage(sessionId, message) {
        const url = `${API_BASE_URL}/chat/sessions/${sessionId}/send_message/`;

        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });
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
