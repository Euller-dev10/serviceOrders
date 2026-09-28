# Runbook — Snapshot e Rollback (Sprint 1.0)

**Contexto:** produção EC2 (empresa única, sem clientes reais). Staging é ambiente separado para a Fase 1.

## 1. Snapshot do banco (antes de qualquer migração)

```bash
# Em produção (EC2) — PostgreSQL
pg_dump -Fc -h localhost -U postgres -d serviceorders \
  -f /var/backups/serviceorders_$(date +%Y%m%d_%H%M%S).dump

# Verificar
pg_restore --list /var/backups/serviceorders_YYYYMMDD_HHMMSS.dump | head
```

Retenção: manter ≥ 3 snapshots; `db.sqlite3` local (dev) — copiar arquivo.

## 2. Snapshot do código

```bash
git tag -a prod-baseline-$(date +%Y%m%d) -m "Baseline antes da Fase 1"
git push origin prod-baseline-$(date +%Y%m%d)
```

## 3. Staging

1. Branch: `git checkout -b staging/fase1` a partir de `main` (código atual de produção).
2. Banco separado: `serviceorders_staging` (mesmo PostgreSQL ou instância própria).
3. `.env` do staging com hosts/CSRF próprios (nunca herdar ngrok de produção).
4. Deploy: mesma uWSGI/Nginx, porta/domínio de staging.

## 4. Rollback

```bash
# 1. Voltar código
git checkout main && git reset --hard prod-baseline-YYYYMMDD

# 2. Restaurar banco (irreversível — só se migração corrompeu dados)
pg_restore -h localhost -U postgres -d serviceorders \
  --clean --if-exists /var/backups/serviceorders_YYYYMMDD_HHMMSS.dump

# 3. Reiniciar
sudo systemctl restart uwsgi   # ou o serviço do staging
```

**Critério de rollback:** teste de smoke (`/login/`, listagem de O.S., detalhe A4) falhando ou dados de selo inconsistentes.

## 5. Smoke test pós-deploy

- [ ] `GET /login/` → 200
- [ ] Login com usuário de teste → redirect `/` ou `/app/`
- [ ] Listar clientes e O.S. → 200
- [ ] Abrir detalhe de O.S. com empresa cadastrada → logo + IPEM/PR
- [ ] Django Admin acessível apenas para superuser

## 6. Backup diário e teste de restauração

Em produção, configurar cron no EC2 (usuário com permissão para gravar em
`/var/backups`) para executar diariamente:

```bash
0 2 * * * pg_dump -Fc -h localhost -U postgres -d serviceorders \
  -f /var/backups/serviceorders_$(date +\%Y\%m\%d_\%H\%M\%S).dump
```

Manter pelo menos três arquivos e remover dumps antigos somente após confirmar
que o backup mais recente pode ser listado e restaurado em banco temporário:

```bash
pg_restore --list /var/backups/serviceorders_YYYYMMDD_HHMMSS.dump >/dev/null
createdb serviceorders_restore_check
pg_restore -h localhost -U postgres -d serviceorders_restore_check \
  --clean --if-exists /var/backups/serviceorders_YYYYMMDD_HHMMSS.dump
```

Executar `python manage.py purge_audit_logs` diariamente após o período de
retenção configurado em `AUDIT_LOG_RETENTION_DAYS` (padrão: 1825 dias).

Para o teste de carga leve das listagens, usar `tests/k6/listings.js`:

```bash
k6 run -e BASE_URL=https://staging.seu-dominio.com tests/k6/listings.js
```
