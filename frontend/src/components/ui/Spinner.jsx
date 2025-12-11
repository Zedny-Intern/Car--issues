export default function Spinner({ size = 'md', text = 'Loading...' }) {
    const sizes = {
        sm: 'w-8 h-8 border-2',
        md: 'w-16 h-16 border-4',
        lg: 'w-24 h-24 border-4',
    };

    return (
        <div className="flex flex-col items-center justify-center gap-4">
            <div className={`${sizes[size]} rounded-full border-chrome-silver/20 border-t-electric-cyan animate-spin`}></div>
            {text && (
                <p className="text-chrome-silver animate-pulse">{text}</p>
            )}
        </div>
    );
}
