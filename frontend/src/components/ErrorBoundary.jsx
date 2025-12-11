import { Component } from 'react';
import Card from './ui/Card';
import Button from './ui/Button';

class ErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error('Error caught by boundary:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-racing-black flex items-center justify-center px-4">
                    <Card className="max-w-lg">
                        <div className="text-center space-y-6">
                            <div className="w-20 h-20 mx-auto rounded-full bg-race-red/20 flex items-center justify-center">
                                <svg className="w-12 h-12 text-race-red" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                </svg>
                            </div>
                            <div>
                                <h2 className="text-2xl font-heading font-bold text-pearl-white mb-2">
                                    Something went wrong
                                </h2>
                                <p className="text-chrome-silver mb-4">
                                    We're sorry for the inconvenience. Please try refreshing the page.
                                </p>
                                {process.env.NODE_ENV === 'development' && this.state.error && (
                                    <pre className="text-left text-xs text-race-red bg-steel-gray/30 p-4 rounded overflow-auto max-h-48">
                                        {this.state.error.toString()}
                                    </pre>
                                )}
                            </div>
                            <Button onClick={() => window.location.reload()}>
                                Refresh Page
                            </Button>
                        </div>
                    </Card>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
