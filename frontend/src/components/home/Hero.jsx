import { Link } from 'react-router-dom';
import Button from '../ui/Button';
import bmwCleanInfo from '../../assets/bmw_clean.png';

export default function Hero() {
    return (
        <section className="relative pt-32 pb-20 px-4">
            <div className="max-w-7xl mx-auto">
                <div className="grid md:grid-cols-2 gap-12 items-center">
                    {/* Left Content */}
                    <div className="space-y-8">
                        <div className="space-y-4">
                            <h1 className="text-6xl md:text-7xl font-heading font-black text-transparent bg-clip-text bg-gradient-to-r from-primary to-blue-400 leading-tight drop-shadow-lg">
                                AI-Powered
                                <br />
                                Car Diagnosis
                            </h1>
                            <p className="text-xl text-muted leading-relaxed">
                                Submit your car complaint and get instant AI-powered diagnosis.
                                Chat with our virtual mechanic powered by advanced machine learning.
                            </p>
                        </div>

                        {/* CTA Buttons */}
                        <div className="flex flex-wrap gap-4">
                            <Link to="/complaint">
                                <Button size="lg" className="group">
                                    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M10 3.5a1.5 1.5 0 013 0V4a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-.5a1.5 1.5 0 000 3h.5a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-.5a1.5 1.5 0 00-3 0v.5a1 1 0 01-1 1H6a1 1 0 01-1-1v-3a1 1 0 00-1-1h-.5a1.5 1.5 0 010-3H4a1 1 0 001-1V6a1 1 0 011-1h3a1 1 0 001-1v-.5z" />
                                    </svg>
                                    Submit Complaint
                                </Button>
                            </Link>

                            <Link to="/search">
                                <Button variant="secondary" size="lg">
                                    Search History
                                </Button>
                            </Link>
                        </div>

                        {/* Stats */}
                        <div className="flex gap-8 pt-8">
                            <Stat value="10K+" label="Diagnoses" />
                            <Stat value="98%" label="Accuracy" />
                            <Stat value="24/7" label="Available" />
                        </div>
                    </div>

                    {/* Right Visual */}
                    <div className="relative perspective-1000 flex items-center justify-center">
                        <img
                            src={bmwCleanInfo}
                            alt="3D BMW M4"
                            className="relative z-10 w-full max-w-2xl drop-shadow-2xl animate-float-3d transform-gpu mix-blend-screen md:mix-blend-normal"
                            style={{
                                animation: 'float-3d 8s ease-in-out infinite',
                                filter: 'drop-shadow(0 0 40px rgba(59, 130, 246, 0.1))'
                            }}
                        />

                        <style jsx="true">{`
                            @keyframes float-3d {
                                0%, 100% { transform: translateY(0) scale(1) rotateX(2deg); }
                                50% { transform: translateY(-15px) scale(1.02) rotateX(5deg); }
                            }
                        `}</style>
                    </div>
                </div>
            </div>
        </section>
    );
}

function Stat({ value, label }) {
    return (
        <div className="text-center">
            <div className="text-3xl font-heading font-bold text-primary">{value}</div>
            <div className="text-sm text-muted">{label}</div>
        </div>
    );
}
