import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/layout/Navbar';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import apiClient from '../services/api';

import ThemeToggle from '../components/ui/ThemeToggle';

export default function ComplaintPage() {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({
        customer_name: '',
        customer_email: '',
        customer_phone: '',
        license_plate: '',
        car_make: '',
        car_model: '',
        car_year: '',
        car_mileage: '',
        complaint_text: '',
        crash: false,
        fire: false,
    });

    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);

        const response = await apiClient.submitComplaint(formData);

        setLoading(false);

        if (response.success) {
            setResult(response.data.data);
        } else {
            alert('Error: ' + response.error);
        }
    };

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    return (
        <div className="min-h-screen bg-page-bg text-text-main relative overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0">
                <div className="grid-pattern absolute inset-0 animate-grid-move"></div>
                <div className="absolute top-20 left-10 w-96 h-96 bg-primary/20 rounded-full blur-3xl animate-pulse"></div>
                <div className="absolute bottom-20 right-10 w-96 h-96 bg-secondary/20 rounded-full blur-3xl animate-pulse"
                    style={{ animationDelay: '1s' }}></div>
            </div>

            <Navbar />
            <ThemeToggle />

            <div className="relative z-10 max-w-5xl mx-auto px-4 py-12">
                <div className="text-center mb-12">
                    <h1 className="text-5xl font-heading font-bold text-text-main text-shadow-glow mb-4">
                        Submit Complaint
                    </h1>
                    <p className="text-xl text-muted">
                        AI-powered diagnosis for your vehicle issue
                    </p>
                </div>

                {!result ? (
                    <Card>
                        <form onSubmit={handleSubmit} className="space-y-8">
                            {/* Customer Info */}
                            <div>
                                <h2 className="text-2xl font-heading font-bold text-text-main mb-4 flex items-center gap-2">
                                    <span className="text-primary">👤</span>
                                    Customer Information
                                </h2>
                                <div className="grid md:grid-cols-2 gap-6">
                                    <Input
                                        label="Full Name"
                                        name="customer_name"
                                        value={formData.customer_name}
                                        onChange={handleChange}
                                        required
                                    />
                                    <Input
                                        label="Email"
                                        name="customer_email"
                                        type="email"
                                        value={formData.customer_email}
                                        onChange={handleChange}
                                    />
                                    <Input
                                        label="Phone"
                                        name="customer_phone"
                                        type="tel"
                                        value={formData.customer_phone}
                                        onChange={handleChange}
                                    />
                                </div>
                            </div>

                            {/* Vehicle Info */}
                            <div>
                                <h2 className="text-2xl font-heading font-bold text-text-main mb-4 flex items-center gap-2">
                                    <span className="text-primary">🚗</span>
                                    Vehicle Information
                                </h2>
                                <div className="grid md:grid-cols-2 gap-6">
                                    <Input
                                        label="License Plate"
                                        name="license_plate"
                                        value={formData.license_plate}
                                        onChange={handleChange}
                                        required
                                    />
                                    <Input
                                        label="Make"
                                        name="car_make"
                                        placeholder="e.g., BMW"
                                        value={formData.car_make}
                                        onChange={handleChange}
                                    />
                                    <Input
                                        label="Model"
                                        name="car_model"
                                        placeholder="e.g., 320i"
                                        value={formData.car_model}
                                        onChange={handleChange}
                                    />
                                    <Input
                                        label="Year"
                                        name="car_year"
                                        type="number"
                                        value={formData.car_year}
                                        onChange={handleChange}
                                    />
                                    <Input
                                        label="Mileage (km)"
                                        name="car_mileage"
                                        type="number"
                                        value={formData.car_mileage}
                                        onChange={handleChange}
                                    />
                                </div>
                            </div>

                            {/* Complaint */}
                            <div>
                                <h2 className="text-2xl font-heading font-bold text-text-main mb-4 flex items-center gap-2">
                                    <span className="text-primary">⚠️</span>
                                    Complaint Details
                                </h2>
                                <textarea
                                    name="complaint_text"
                                    value={formData.complaint_text}
                                    onChange={handleChange}
                                    required
                                    rows={6}
                                    placeholder="Describe the problem in detail..."
                                    className="w-full px-4 py-3 rounded-lg
                           bg-input-bg border-2 border-border-color/20
                           text-text-main placeholder-muted/50
                           focus:border-primary focus:ring-2 focus:ring-primary/20
                           focus:outline-none transition-all duration-300 backdrop-blur-sm"
                                />

                                <div className="flex gap-6 mt-4">
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            name="crash"
                                            checked={formData.crash}
                                            onChange={handleChange}
                                            className="w-5 h-5"
                                        />
                                        <span className="text-text-main">Involves Crash</span>
                                    </label>
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            name="fire"
                                            checked={formData.fire}
                                            onChange={handleChange}
                                            className="w-5 h-5"
                                        />
                                        <span className="text-text-main">Involves Fire</span>
                                    </label>
                                </div>
                            </div>

                            <Button type="submit" size="lg" className="w-full" disabled={loading}>
                                {loading ? <Spinner size="sm" text="" /> : (
                                    <>
                                        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                                            <path d="M10 3.5a1.5 1.5 0 013 0V4a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-.5a1.5 1.5 0 000 3h.5a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-.5a1.5 1.5 0 00-3 0v.5a1 1 0 01-1 1H6a1 1 0 01-1-1v-3a1 1 0 00-1-1h-.5a1.5 1.5 0 010-3H4a1 1 0 001-1V6a1 1 0 011-1h3a1 1 0 001-1v-.5z" />
                                        </svg>
                                        Submit Complaint
                                    </>
                                )}
                            </Button>
                        </form>
                    </Card>
                ) : (
                    <Card>
                        <div className="text-center space-y-6">
                            <div className="w-20 h-20 mx-auto rounded-full bg-primary/20 flex items-center justify-center">
                                <svg className="w-12 h-12 text-primary" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                </svg>
                            </div>

                            <h2 className="text-3xl font-heading font-bold text-text-main">
                                Complaint Submitted!
                            </h2>

                            <div className="space-y-4 text-left">
                                <div className="flex justify-between border-b border-border-color/20 pb-2">
                                    <span className="text-muted">Complaint ID:</span>
                                    <span className="text-text-main font-semibold">{result.complaint.id}</span>
                                </div>
                                <div className="flex justify-between border-b border-border-color/20 pb-2">
                                    <span className="text-muted">Category:</span>
                                    <span className="px-3 py-1 rounded-full bg-primary/20 text-primary font-semibold">
                                        {result.complaint.category_display}
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-muted">Confidence:</span>
                                    <span className="text-text-main font-semibold">
                                        {(result.complaint.prediction_confidence * 100).toFixed(1)}%
                                    </span>
                                </div>
                            </div>

                            <Button
                                size="lg"
                                className="w-full"
                                onClick={() => navigate(`/chat?complaint_id=${result.complaint.id}`)}
                            >
                                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clipRule="evenodd" />
                                </svg>
                                Chat with AI Mechanic
                            </Button>
                        </div>
                    </Card>
                )}
            </div>
        </div>
    );
}
