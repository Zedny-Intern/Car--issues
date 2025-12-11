import { Link } from 'react-router-dom';


export default function Navbar() {
    return (
        <nav className="backdrop-blur-lg bg-page-bg border-b border-border-color/10 sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-20">
                    {/* Logo */}
                    <Link to="/" className="flex items-center gap-3 group">
                        <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-electric-cyan to-race-red p-[2px] 
                          group-hover:scale-110 transition-transform">
                            <div className="w-full h-full bg-carbon-fiber rounded-lg flex items-center justify-center">
                                <svg className="w-8 h-8 text-electric-cyan" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z" />
                                </svg>
                            </div>
                        </div>
                        <div>
                            <h1 className="text-2xl font-heading font-bold text-gradient-cyan text-shadow-glow">
                                Car Diagnosis
                            </h1>
                            <p className="text-xs text-chrome-silver">AI-Powered System</p>
                        </div>
                    </Link>

                    {/* Nav Links */}
                    <div className="hidden md:flex items-center gap-6">
                        <NavLink to="/">Home</NavLink>
                        <NavLink to="/complaint">Submit Complaint</NavLink>
                        <NavLink to="/chat">Chat</NavLink>
                        <NavLink to="/search">Search</NavLink>

                        {/* CTA Button */}
                        <Link
                            to="/complaint"
                            className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-race-red to-race-red/80 
                       text-pearl-white font-semibold
                       hover:shadow-lg hover:shadow-race-red/50 
                       transition-all duration-300
                       transform hover:scale-105"
                        >
                            Get Started
                        </Link>
                    </div>
                </div>
            </div>
        </nav>
    );
}

function NavLink({ to, children }) {
    return (
        <Link
            to={to}
            className="text-chrome-silver hover:text-electric-cyan 
                 transition-colors duration-300
                 relative group"
        >
            {children}
            <span className="absolute bottom-0 left-0 w-0 h-0.5 bg-electric-cyan 
                       group-hover:w-full transition-all duration-300"></span>
        </Link>
    );
}
