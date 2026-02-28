import { Link } from 'react-router-dom';
import Navbar from '../components/layout/Navbar';
import ThemeToggle from '../components/ui/ThemeToggle';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';

const capabilities = [
    {
        title: 'Precision Diagnosis',
        description: 'Classify complaints with ML-driven triage so critical issues are surfaced first.',
        route: '/complaint',
        badge: 'AI Core',
    },
    {
        title: 'Mechanic Chat',
        description: 'Open a guided troubleshooting conversation linked to the exact complaint context.',
        route: '/chat',
        badge: 'Context Aware',
    },
    {
        title: 'Vehicle Timeline',
        description: 'Search complaint history by plate and track repeated issues before they escalate.',
        route: '/search',
        badge: 'Operational View',
    },
];

const workflow = [
    { step: '01', title: 'Capture', text: 'Submit complaint details with optional incident flags.' },
    { step: '02', title: 'Analyze', text: 'Run classification and route to focused diagnostic flow.' },
    { step: '03', title: 'Resolve', text: 'Use chat guidance and history to cut repeat failures.' },
];

export default function HomePage() {
    return (
        <div className="relative min-h-screen overflow-hidden bg-page-bg text-text-main">
            <BackgroundLayers />

            <div className="relative z-10">
                <Navbar />
                <ThemeToggle />

                <main className="mx-auto flex w-full max-w-7xl flex-col gap-20 px-4 pb-20 pt-14 sm:px-6 lg:px-8">
                    <section className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
                        <div className="space-y-6">
                            <p className="inline-flex items-center rounded-full border border-primary/40 bg-primary/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-primary">
                                Production Workflow
                            </p>
                            <h1 className="max-w-3xl font-heading text-4xl font-black leading-tight sm:text-5xl lg:text-6xl">
                                From complaint intake to
                                <span className="block bg-gradient-to-r from-primary via-cyan-300 to-blue-300 bg-clip-text text-transparent">
                                    decisive repair direction.
                                </span>
                            </h1>
                            <p className="max-w-2xl text-base text-text-muted sm:text-lg">
                                Car Diagnosis System gives workshops and service teams an AI-assisted control room:
                                consistent complaint capture, faster root-cause guidance, and searchable technical history.
                            </p>

                            <div className="flex flex-wrap gap-3">
                                <Link to="/complaint" className="focus-visible:outline-none">
                                    <Button
                                        size="lg"
                                        className="min-w-[190px] focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-page-bg"
                                    >
                                        Start Diagnosis
                                    </Button>
                                </Link>
                                <Link to="/search" className="focus-visible:outline-none">
                                    <Button
                                        variant="secondary"
                                        size="lg"
                                        className="min-w-[190px] focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-page-bg"
                                    >
                                        Inspect History
                                    </Button>
                                </Link>
                            </div>
                        </div>

                        <Card className="border-primary/20 bg-card-bg/90 p-7">
                            <h2 className="font-heading text-xl font-bold sm:text-2xl">Live Operations Snapshot</h2>
                            <p className="mt-2 text-sm text-text-muted">
                                Tune decisions with a practical blend of model confidence, incident severity, and past outcomes.
                            </p>
                            <div className="mt-6 grid grid-cols-2 gap-3">
                                <Metric label="Avg triage time" value="< 2 min" />
                                <Metric label="Model confidence" value="Up to 98%" />
                                <Metric label="System availability" value="24/7" />
                                <Metric label="History coverage" value="Cross-case" />
                            </div>
                        </Card>
                    </section>

                    <section className="space-y-6">
                        <div className="flex items-end justify-between gap-6">
                            <h2 className="font-heading text-3xl font-bold sm:text-4xl">Core Capabilities</h2>
                            <p className="max-w-md text-sm text-text-muted">
                                Built for technicians who need fast signal, not noisy dashboards.
                            </p>
                        </div>

                        <div className="grid gap-5 md:grid-cols-3">
                            {capabilities.map((item) => (
                                <Link
                                    key={item.title}
                                    to={item.route}
                                    className="group focus-visible:outline-none"
                                >
                                    <Card className="h-full border-border-color/40 bg-card-bg/85 transition-all duration-300 group-hover:-translate-y-1 group-hover:border-primary/45 group-hover:shadow-2xl group-hover:shadow-primary/10">
                                        <div className="flex h-full flex-col gap-4">
                                            <span className="w-fit rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                                                {item.badge}
                                            </span>
                                            <h3 className="font-heading text-2xl font-bold leading-tight">{item.title}</h3>
                                            <p className="text-sm leading-relaxed text-text-muted">{item.description}</p>
                                            <span className="mt-auto inline-flex items-center gap-2 text-sm font-semibold text-primary transition-all duration-300 group-hover:gap-3">
                                                Open Module
                                                <ArrowIcon />
                                            </span>
                                        </div>
                                    </Card>
                                </Link>
                            ))}
                        </div>
                    </section>

                    <section className="grid gap-6 rounded-2xl border border-border-color/40 bg-card-bg/70 p-6 md:grid-cols-3">
                        {workflow.map((item) => (
                            <div key={item.step} className="space-y-3">
                                <p className="font-heading text-2xl font-bold text-primary">{item.step}</p>
                                <h3 className="font-heading text-xl font-semibold">{item.title}</h3>
                                <p className="text-sm text-text-muted">{item.text}</p>
                            </div>
                        ))}
                    </section>
                </main>
            </div>
        </div>
    );
}

function Metric({ label, value }) {
    return (
        <div className="rounded-xl border border-border-color/50 bg-page-bg/70 p-4">
            <p className="text-xs uppercase tracking-[0.14em] text-text-muted">{label}</p>
            <p className="mt-1 font-heading text-xl font-bold text-primary">{value}</p>
        </div>
    );
}

function BackgroundLayers() {
    return (
        <div className="absolute inset-0">
            <div className="grid-pattern absolute inset-0 animate-grid-move opacity-30" />
            <div className="absolute -left-24 top-20 h-72 w-72 rounded-full bg-cyan-500/20 blur-3xl" />
            <div className="absolute right-0 top-1/3 h-80 w-80 rounded-full bg-primary/20 blur-3xl" />
            <div className="absolute bottom-10 left-1/3 h-72 w-72 rounded-full bg-emerald-400/10 blur-3xl" />
        </div>
    );
}

function ArrowIcon() {
    return (
        <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path
                fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd"
            />
        </svg>
    );
}
