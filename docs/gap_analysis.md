# Gap Analysis — Legado vs PRD v1.1 (Sprint 1.0)

**Data:** 22/09/2026 · **Escopo:** §§7–8 do PRD (`docs/prd.md`)
**Baseline:** código em produção (EC2, empresa única, sem clientes reais)

## 1. Models (§7.2)

| PRD | Legado atual | Ação |
|---|---|---|
| `core.TimeStampedModel` / `TenantScopedModel` | ausente — models sem `created_at`/`updated_at`/`tenant` | **Criar** apps `core` (Sprint 1.1) |
| `tenants.Tenant` (+ `Plan`, `Subscription`) | `Company` em `service_order` (empresa única, `objects.first()`) | **Renomear/migrar** → `tenants.Tenant`; `Company` vira sinônimo de Tenant no MVP |
| `accounts.User` (email `USERNAME_FIELD`, `role`) | `django.contrib.auth.models.User` (username) | **Recriar** com `AbstractUser` custom (Sprint 1.1) |
| `clients.Client` + unique `(tenant, document)` | `service_order.Client` — unique só no form | **Manter campos**; adicionar tenant + constraint |
| `assets.Unit`, `assets.Scale` | `service_order.Unit`, `Scale` (`model`→`model_name`, `serie`→`serial_number`, capacity/division Char→Decimal) | **Renomear campos** + tipos; unique `(tenant, owner, serial)` |
| `stamps.Stamp` / `StampDelivery` | mesmo nome; **choices em pt-BR** | Normalizar choices → inglês (**Sprint 1.0**); service com lock (Sprint 1.3) |
| `service_orders.ServiceOrder` + `uuid` + `number` seq/tenant | `ServiceOrder` sem `uuid`/`number`; serviços `service1..8`; `user`≠`created_by`; sem `status` | **Manter core**; adicionar `uuid`, `number`, renomear `user`→`created_by`, `status` default `COMPLETED` |
| `ServicePart` / `ServiceTime` | `Part` / `TimeService` (`total_hours` Time→Decimal, car/truck Char→Decimal) | **Renomear** + ajustar tipos (Sprint 1.3) |
| Índices `(tenant, …)` | ausentes | Adicionar com multi-tenant |

## 2. Views / Endpoints (§8)

| PRD | Legado | Ação |
|---|---|---|
| `/auth/login/` por **email** | `/login/` por username (`AuthenticationForm`) | Adaptar `EmailBackend` + template (Sprint 1.1) |
| `/auth/logout/` POST | GET `/logout/` | Tornar POST |
| `/app/` `HomeView` | `/` `HomeView` | Mover prefixo (Sprint 1.1) |
| `/clientes/…` CRUD ADMIN/STAFF | `/search_client/`, `/new_client/`, … sem role | Renomear rotas + `RoleRequiredMixin` (Sprint 1.2) |
| `/balancas/…` | `/search_scale/`, … | Idem |
| `/os/nova/<client>/<scale>/` | `/service_order/<id_client>/<id_scale>/` | Renomear (Sprint 1.3) |
| `/os/` list com `q` + `date_from/date_to` | `/list_os/` com `search` + `date_filter` | Alinhar params (Sprint 1.4) |
| `/os/<pk>/imprimir/` | detalhe único com CSS print | Separar rota print (Sprint 1.4) |
| `/selos/…` views ADMIN | só Django Admin | Criar views (Sprint 1.3) |
| `/usuarios/…` gestão tenant | ausente | Criar (Sprint 1.1+) |
| `TenantMiddleware` → `request.tenant` | ausente | Criar (Sprint 1.1) |
| Matriz de permissões §8.9 | só `is_superuser` na list de O.S. | `RoleRequiredMixin` + testes (Sprint 1.4) |

## 3. Decisões imediatas (Sprint 1.0)

1. **Choices de selo** normalizadas para `AVAILABLE` / `DISTRIBUTED` / `USED` / `DAMAGED` (labels pt-BR) — feito nesta sprint.
2. **`ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`** via env, sem ngrok em produção — feito nesta sprint.
3. **CI** ruff + testes — feito nesta sprint.
4. **Migração de dados** real (backfill de um único Tenant) fica para Sprint 1.1, quando `tenants.Tenant` existir — hoje `Company.objects.first()` continua válido.

## 4. Riscos abertos

| Risco | Nota |
|---|---|
| `Company` vs `Tenant` duplicados | Evitar criar os dois; na Sprint 1.1 `Company` é absorvida por `Tenant` |
| `Scale.model` renomeio quebra templates | Renomear em sprint dedicada com migração de dados |
| Login username→email | Exigirá reset de senhas de usuários de teste no staging |
