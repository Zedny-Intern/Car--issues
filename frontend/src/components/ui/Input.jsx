export default function Input({
    label,
    type = 'text',
    placeholder,
    value,
    onChange,
    required = false,
    error,
    icon: Icon,
    ...props
}) {
    return (
        <div className="space-y-2">
            {label && (
                <label className="block text-sm font-semibold text-text-main">
                    {label}
                    {required && <span className="text-danger ml-1">*</span>}
                </label>
            )}

            <div className="relative">
                {Icon && (
                    <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted">
                        <Icon className="w-5 h-5" />
                    </div>
                )}

                <input
                    type={type}
                    value={value}
                    onChange={onChange}
                    placeholder={placeholder}
                    required={required}
                    className={`w-full px-4 py-3 rounded-lg
                     bg-input-bg border-2 border-border-color/20
                     text-text-main placeholder-muted/50
                     focus:border-primary focus:ring-2 focus:ring-primary/20
                     focus:outline-none
                     transition-all duration-300
                     backdrop-blur-sm
                     ${Icon ? 'pl-11' : ''}
                     ${error ? 'border-danger' : ''}`}
                    {...props}
                />

                {/* Glow on Focus */}
                <div className="absolute -inset-1 rounded-lg 
                        bg-gradient-to-r from-primary/0 via-primary/20 to-primary/0
                        opacity-0 focus-within:opacity-100 transition-opacity -z-10 blur"></div>
            </div>

            {error && (
                <p className="text-sm text-danger flex items-center gap-1">
                    <span>⚠️</span>
                    {error}
                </p>
            )}
        </div>
    );
}
