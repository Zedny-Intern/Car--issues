from django.core.management.base import BaseCommand

from apps.ml_models.tasks import dispatch_prime_rag_runtime, prime_rag_runtime_sync


class Command(BaseCommand):
    help = "Prime the RAG/chat runtime and sync static/manual/uploaded documents."

    def add_arguments(self, parser):
        parser.add_argument(
            '--async',
            action='store_true',
            dest='run_async',
            help='Queue the priming job in the background and return immediately.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force a full resync instead of skipping recently indexed documents.',
        )
        parser.add_argument(
            '--no-cleanup-missing',
            action='store_true',
            help='Do not remove index entries for files deleted from disk.',
        )

    def handle(self, *args, **options):
        cleanup_missing = not options['no_cleanup_missing']

        if options['run_async']:
            result = dispatch_prime_rag_runtime(
                force=options['force'],
                cleanup_missing=cleanup_missing,
            )
            self.stdout.write(self.style.SUCCESS(f"Queued runtime priming: {result}"))
            return

        result = prime_rag_runtime_sync(
            force=options['force'],
            cleanup_missing=cleanup_missing,
        )
        self.stdout.write(self.style.SUCCESS(f"Runtime primed: {result}"))
