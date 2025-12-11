import { useEffect, useState } from 'react';

const ThemeToggle = () => {
    const [theme, setTheme] = useState(() => {
        // Initialize from localStorage or default to light
        if (typeof window !== 'undefined') {
            return localStorage.getItem('theme') || 'light';
        }
        return 'light';
    });

    // Apply theme class to html element
    useEffect(() => {
        const root = document.documentElement;
        if (theme === 'dark') {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }
        localStorage.setItem('theme', theme);
    }, [theme]);

    const toggle = () => {
        setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
    };

    return (
        <button
            onClick={toggle}
            className="p-2 rounded-full bg-page-bg dark:bg-card-bg transition-colors duration-500 hover:scale-110"
            aria-label="Toggle dark mode"
        >
            {/* Sun/Moon icon with simple CSS animation */}
            <span className="block w-5 h-5 relative">
                <svg
                    className={`absolute inset-0 w-full h-full transition-transform duration-500 ${theme === 'dark' ? 'rotate-180' : ''}`}
                    viewBox="0 0 24 24"
                    fill="currentColor"
                >
                    {theme === 'dark' ? (
                        // Moon
                        <path d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79z" />
                    ) : (
                        // Sun
                        <path d="M12 4V2m0 20v-2m8.66-13.66l1.42-1.42M4.92 19.08l1.42-1.42M20 12h2M2 12h2m13.66 5.66l1.42 1.42M4.92 4.92l1.42 1.42M12 8a4 4 0 100 8 4 4 0 000-8z" />
                    )}
                </svg>
            </span>
        </button>
    );
};

export default ThemeToggle;
