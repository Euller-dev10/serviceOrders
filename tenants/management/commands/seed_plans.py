from django.core.management.base import BaseCommand

from tenants.services import seed_plans


class Command(BaseCommand):
    help = 'Cria/atualiza os planos baseline (trial, basic, pro, enterprise).'

    def handle(self, *args, **options):
        plans = seed_plans()
        for plan in plans:
            self.stdout.write(
                self.style.SUCCESS(
                    f'  {plan.code}: {plan.name} — '
                    f'seat={plan.max_technicians} os={plan.max_service_orders_per_month} '
                    f'ia={plan.max_ai_credits_per_month}'
                )
            )
        self.stdout.write(self.style.SUCCESS(f'{len(plans)} planos ok.'))
