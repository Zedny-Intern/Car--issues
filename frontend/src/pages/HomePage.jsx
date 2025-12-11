import { Link } from 'react-router-dom';
import Navbar from '../components/layout/Navbar';
import Hero from '../components/home/Hero';
import Card from '../components/ui/Card';
import ThemeToggle from '../components/ui/ThemeToggle';

export default function HomePage() {
    return (
        <div className="relative min-h-screen overflow-hidden bg-page-bg text-text-main">
            {/* Animated Background */}
            <div className="absolute inset-0">
                {/* Grid Pattern */}
                <div className="grid-pattern absolute inset-0 animate-grid-move"></div>

                {/* Gradient Orbs */}
                <div className="absolute top-20 left-10 w-96 h-96 bg-primary/20 rounded-full blur-3xl animate-pulse"></div>
                <div className="absolute bottom-20 right-10 w-96 h-96 bg-secondary/20 rounded-full blur-3xl animate-pulse"
                    style={{ animationDelay: '1s' }}></div>
            </div>

            {/* Content */}
            <div className="relative z-10">
                <Navbar />
                <ThemeToggle />
                <Hero />

                {/* Features Section */}
                <section className="max-w-7xl mx-auto px-4 py-20">
                    <h2 className="text-4xl font-heading font-bold text-center text-text-main mb-12">
                        Our <span className="text-primary">Features</span>
                    </h2>

                    <div className="grid md:grid-cols-3 gap-8">
                        <FeatureCard
                            icon="🤖"
                            title="AI Diagnosis"
                            description="Advanced ML models analyze your complaint and provide accurate categorization with 98% confidence"
                            link="/complaint"
                        />
                        <FeatureCard
                            icon="💬"
                            title="Smart Chat"
                            description="Chat with our virtual mechanic powered by LLaVA and GROQ. Send images for visual analysis"
                            link="/chat"
                        />
                        <FeatureCard
                            icon="🔍"
                            title="History Search"
                            description="Search complete vehicle history by license plate. Track all past complaints and diagnoses"
                            link="/search"
                        />
                    </div>
                </section>
            </div>
        </div>
    );
}

function FeatureCard({ icon, title, description, link }) {
    return (
        <Link to={link}>
            <Card>
                <div className="text-center space-y-4">
                    <div className="text-6xl">{icon}</div>
                    <h3 className="text-2xl font-heading font-bold text-text-main">
                        {title}
                    </h3>
                    <p className="text-muted leading-relaxed">
                        {description}
                    </p>
                    <div className="flex items-center justify-center gap-2 text-primary 
                        group-hover:gap-4 transition-all">
                        <span className="font-semibold">Learn More</span>
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                        </svg>
                    </div>
                </div>
            </Card>
        </Link>
    );
}
