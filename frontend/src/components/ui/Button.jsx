export default function Button({
    children,
    onClick,
    variant = 'primary',
    size = 'md',
    className = '',
    disabled = false,
    type = 'button'
}) {
    const baseClasses = "relative overflow-hidden font-semibold rounded-lg transition-all duration-300 transform disabled:opacity-50 disabled:cursor-not-allowed";

    const variants = {
        primary: `bg-primary hover:bg-primary-hover text-text-main 
               shadow-lg hover:shadow-primary/50`,
        secondary: `bg-steel-gray/50 text-pearl-white border-2 border-chrome-silver/20
               hover:border-electric-cyan hover:shadow-lg hover:shadow-electric-cyan/20
               backdrop-blur-sm`,
        outline: `bg-transparent text-electric-cyan border-2 border-electric-cyan
             hover:bg-electric-cyan hover:text-racing-black`,
    };

    const sizes = {
        sm: 'px-4 py-2 text-sm',
        md: 'px-6 py-3 text-base',
        lg: 'px-8 py-4 text-lg',
    };

    return (
        <button
            type={type}
            onClick={onClick}
            disabled={disabled}
            className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${className}`}
        >
            {/* Shine Effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent 
                      transform -translate-x-full hover:translate-x-full transition-transform duration-1000"></div>

            <span className="relative z-10 flex items-center justify-center gap-2">
                {children}
            </span>
        </button>
    );
}
