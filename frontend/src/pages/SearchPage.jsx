import { useState } from 'react';
import Navbar from '../components/layout/Navbar';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import apiClient from '../services/api';

import ThemeToggle from '../components/ui/ThemeToggle';

export default function SearchPage() {
    const [licensePlate, setLicensePlate] = useState('');
    const [loading, setLoading] = useState(false);
    const [results, setResults] = useState(null);

    const handleSearch = async () => {
        if (!licensePlate.trim()) {
            alert('Please enter a license plate');
            return;
        }

        setLoading(true);
        const response = await apiClient.searchCarByPlate(licensePlate);

        if (response.success) {
            const historyResponse = await apiClient.getCarHistory(response.data.id);
            if (historyResponse.success) {
                setResults(historyResponse.data);
            }
        } else {
            setResults({ car: null, complaints: [] });
        }

        setLoading(false);
    };

    return (
        <div className="min-h-screen bg-page-bg text-text-main relative overflow-hidden">
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
                        Search Vehicle History
                    </h1>
                    <p className="text-xl text-muted">
                        Find all complaints and diagnoses for any vehicle
                    </p>
                </div>

                <Card>
                    <div className="flex gap-4 mb-8">
                        <Input
                            placeholder="Enter license plate number..."
                            value={licensePlate}
                            onChange={(e) => setLicensePlate(e.target.value.toUpperCase())}
                            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                        />
                        <Button onClick={handleSearch} disabled={loading} className="whitespace-nowrap">
                            {loading ? <Spinner size="sm" text="" /> : (
                                <>
                                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
                                    </svg>
                                    Search
                                </>
                            )}
                        </Button>
                    </div>

                    {results && (
                        results.car ? (
                            <div className="space-y-6">
                                {/* Car Info */}
                                <div className="p-6 rounded-xl bg-card-bg border border-border-color/10">
                                    <h3 className="text-2xl font-heading font-bold text-text-main mb-4">
                                        {results.car.display_name}
                                    </h3>
                                    <div className="grid md:grid-cols-2 gap-4">
                                        <div className="flex justify-between">
                                            <span className="text-muted">License Plate:</span>
                                            <span className="text-text-main font-semibold">{results.car.license_plate}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted">Customer:</span>
                                            <span className="text-text-main font-semibold">{results.car.customer?.name}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted">Total Complaints:</span>
                                            <span className="text-primary font-semibold">{results.complaints.length}</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Complaints List */}
                                <div className="space-y-4">
                                    <h4 className="text-xl font-heading font-bold text-text-main">
                                        Complaint History
                                    </h4>
                                    {results.complaints.length === 0 ? (
                                        <p className="text-center text-muted py-8">
                                            No complaints found for this vehicle
                                        </p>
                                    ) : (
                                        results.complaints.map((complaint) => (
                                            <div
                                                key={complaint.id}
                                                className="p-6 rounded-xl bg-white/5 border border-border-color/10 
                                 hover:border-primary/50 transition-all"
                                            >
                                                <div className="flex justify-between items-start mb-4">
                                                    <div>
                                                        <span className="px-3 py-1 rounded-full bg-primary/20 text-primary text-sm font-semibold">
                                                            {complaint.category_display || complaint.predicted_category}
                                                        </span>
                                                        {complaint.crash && (
                                                            <span className="ml-2 px-3 py-1 rounded-full bg-danger/20 text-danger text-sm font-semibold">
                                                                CRASH
                                                            </span>
                                                        )}
                                                        {complaint.fire && (
                                                            <span className="ml-2 px-3 py-1 rounded-full bg-orange-500/20 text-orange-500 text-sm font-semibold">
                                                                FIRE
                                                            </span>
                                                        )}
                                                    </div>
                                                    <span className="text-muted text-sm">
                                                        {new Date(complaint.created_at).toLocaleDateString()}
                                                    </span>
                                                </div>
                                                <p className="text-text-main leading-relaxed">
                                                    {complaint.complaint_text || 'No description available'}
                                                </p>
                                                <div className="mt-4 pt-4 border-t border-border-color/10">
                                                    <div className="flex items-center justify-between text-sm">
                                                        <span className="text-muted">Confidence:</span>
                                                        <span className="text-text-main font-semibold">
                                                            {(complaint.prediction_confidence * 100).toFixed(1)}%
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        ) : (
                            <div className="text-center py-12">
                                <div className="w-20 h-20 mx-auto rounded-full bg-danger/20 flex items-center justify-center mb-4">
                                    <svg className="w-12 h-12 text-danger" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                    </svg>
                                </div>
                                <h3 className="text-xl font-semibold text-text-main mb-2">
                                    No vehicle found
                                </h3>
                                <p className="text-muted">
                                    No vehicle with license plate "{licensePlate}" was found
                                </p>
                            </div>
                        )
                    )}
                </Card>
            </div>
        </div>
    );
}
