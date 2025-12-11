/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                'page-bg': '#020617', // Slate 950
                'card-bg': '#0f172a', // Slate 900
                'input-bg': '#1e293b', // Slate 800
                'primary': '#3b82f6', // Blue 500
                'primary-hover': '#2563eb', // Blue 600
                'secondary': '#475569', // Slate 600
                'danger': '#ef4444', // Red 500
                'success': '#22c55e', // Green 500
                'text-main': '#f8fafc', // Slate 50
                'text-muted': '#94a3b8', // Slate 400
                'border-color': '#1e293b', // Slate 800
            },
            backgroundImage: {
                'carbon': 'linear-gradient(27deg, #0A0E27 5%, #1A1D2E 25%, #16213E 50%, #1A1D2E 75%, #0A0E27 95%)',
                'racing-stripe': 'linear-gradient(135deg, #E94560 0%, #00FFFF 100%)',
                'metallic': 'linear-gradient(to right, #0F3460, #16213E, #0F3460)',
            },
            animation: {
                'carbon-shift': 'carbonShift 15s ease infinite',
                'metallic-shine': 'metallicShine 3s linear infinite',
                'grid-move': 'gridMove 20s linear infinite',
            },
            keyframes: {
                carbonShift: {
                    '0%, 100%': { backgroundPosition: '0% 50%' },
                    '50%': { backgroundPosition: '100% 50%' },
                },
                metallicShine: {
                    '0%': { backgroundPosition: '0% 50%' },
                    '100%': { backgroundPosition: '200% 50%' },
                },
                gridMove: {
                    '0%': { transform: 'translateY(0)' },
                    '100%': { transform: 'translateY(50px)' },
                },
            },
            fontFamily: {
                'heading': ['Orbitron', 'Rajdhani', 'sans-serif'],
                'body': ['Inter', 'Cairo', 'sans-serif'],
            },
        },
    },
    plugins: [],
}
