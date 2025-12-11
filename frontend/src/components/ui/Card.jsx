export default function Card({ children, className = '', hover = true }) {
    return (
        <div className={`bg-card-bg border border-border-color/10 rounded-xl p-6 relative overflow-hidden backdrop-blur-sm ${hover ? 'group hover:scale-[1.02] transition-transform duration-300 hover:shadow-xl hover:border-primary/30' : ''} ${className}`}>
            {children}
        </div>
    );
}
