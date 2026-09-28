# Guia de Publicação — GitHub Privado para EC2

Este documento descreve como publicar o código desenvolvido no ambiente local
em um repositório privado do GitHub e, depois, instalar essa versão na EC2 que
já executa o Aferix com Nginx + uWSGI.

## 1. O que será publicado

O fluxo recomendado é:

```text
Computador local
    -> git commit / git push
GitHub privado
    -> git clone / git pull
EC2
    -> migrate / collectstatic / restart
Produção
```

O GitHub não é tecnicamente obrigatório, mas é recomendado porque mantém
histórico, permite rollback e evita depender de uma cópia única do projeto.

## 2. O que nunca deve ir para o GitHub

Antes do primeiro commit, confirme que estes itens estão ignorados:

- `.env` e qualquer arquivo com senha ou chave de API;
- `venv/` e ambientes virtuais;
- `media/` e uploads dos usuários;
- `staticfiles/` gerado pelo `collectstatic`;
- bancos locais, dumps e arquivos temporários;
- chaves SSH, certificados TLS e arquivos privados da EC2.

O arquivo `.env.example` pode ser publicado, desde que contenha apenas nomes
de variáveis e valores fictícios.

## 3. Preparar o repositório local

No PowerShell, dentro da pasta do projeto:

```powershell
git status
git branch --show-current
git remote -v
```

Revise as alterações antes de adicionar os arquivos:

```powershell
git diff --stat
git diff --check
```

Confirme que não aparecem `.env`, `media/`, `venv/` ou segredos:

```powershell
git status --short
```

Depois execute as verificações locais:

```powershell
python manage.py check --settings=app.test_settings
python manage.py test --settings=app.test_settings
ruff check .
```

## 4. Criar o repositório privado no GitHub

Crie um repositório vazio e privado no GitHub, por exemplo:

```text
aferix
```

Não marque a opção de criar README, `.gitignore` ou licença se o projeto local
já possui esses arquivos.

Se ainda não houver um remoto configurado:

```powershell
git remote add origin git@github.com:SEU_USUARIO/aferix.git
```

Confira:

```powershell
git remote -v
```

## 5. Criar o primeiro commit

Adicione somente arquivos intencionais:

```powershell
git add .
git status
```

Se o status estiver correto:

```powershell
git commit -m "Implementa plataforma multi-tenant e operacao"
```

Veja o branch atual:

```powershell
git branch --show-current
```

Se for `main`, publique:

```powershell
git push -u origin main
```

Se o branch tiver outro nome, substitua `main` pelo nome exibido.

## 6. Acesso da EC2 ao GitHub

A EC2 deve usar uma chave SSH própria. Não copie a chave pessoal do
computador para o servidor.

Na EC2:

```bash
ssh-keygen -t ed25519 -C "aferix-ec2-deploy" -f ~/.ssh/aferix_ec2
cat ~/.ssh/aferix_ec2.pub
```

Adicione a chave pública no GitHub em:

```text
Repository Settings -> Deploy keys -> Add deploy key
```

Para publicação somente leitura, não habilite `Allow write access`.

Configure o SSH na EC2:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-aferix
    HostName github.com
    User git
    IdentityFile ~/.ssh/aferix_ec2
    IdentitiesOnly yes
EOF

chmod 600 ~/.ssh/config ~/.ssh/aferix_ec2
ssh -T git@github-aferix
```

Use a URL correspondente ao alias:

```bash
```

## 7. Instalação limpa na EC2

Como não há clientes nem dados importantes em produção, é possível recriar o
banco. Ainda assim, mantenha um snapshot até confirmar o deploy.

Pare a aplicação:

```bash
sudo systemctl stop uwsgi
```

Faça um backup temporário:

```bash
sudo mkdir -p /var/backups
pg_dump -Fc -h localhost -U postgres -d serviceorders \
  -f /var/backups/serviceorders_before_aferix_$(date +%Y%m%d_%H%M%S).dump
```

Recrie o banco somente se tiver certeza de que os dados antigos não serão
necessários:

```bash
sudo -u postgres dropdb --if-exists serviceorders
sudo -u postgres createdb serviceorders
```

Clone o projeto:

```bash
sudo mkdir -p /var/www
sudo chown -R "$USER":"$USER" /var/www
git clone git@github-aferix:SEU_USUARIO/aferix.git /var/www/aferix
cd /var/www/aferix
```

## 8. Configurar o ambiente da EC2

Crie `/var/www/aferix/.env` diretamente na EC2. Não copie o `.env` local:

```env
DJANGO_SETTINGS_MODULE=app.settings
DJANGO_SECRET_KEY=uma-chave-aleatoria-grande
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=seu-dominio.com.br,www.seu-dominio.com.br
CSRF_TRUSTED_ORIGINS=https://seu-dominio.com.br,https://www.seu-dominio.com.br

POSTGRES_DB=serviceorders
POSTGRES_USER=postgres
POSTGRES_PASSWORD=senha-real
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
ENABLE_CSP=True

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=servidor.smtp
EMAIL_PORT=587
EMAIL_HOST_USER=usuario-smtp
EMAIL_HOST_PASSWORD=senha-smtp
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@seu-dominio.com.br
```

Confirme que o `app/settings.py` da release usa os mesmos nomes de variáveis
de banco configurados no ambiente de produção. Se a instalação atual usa
credenciais PostgreSQL fixas no código, substitua-as por variáveis de ambiente
antes de ativar a release.

## 9. Dependências, migrations e arquivos estáticos

```bash
cd /var/www/aferix
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install uwsgi==2.0.30

python manage.py check --deploy
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py seed_plans
python manage.py createsuperuser
```

As migrations dos sprints serão aplicadas automaticamente, incluindo o
`AuditLog` e o campo `status` da O.S.

## 10. Criar o primeiro tenant e usuário administrador

O superusuário do Django serve para suporte interno. Para usar o fluxo SaaS,
crie um `Tenant` e associe um usuário ADMIN pelo Django Admin ou pelo shell:

```bash
python manage.py shell
```

```python
from accounts.models import User
from tenants.models import Tenant

tenant = Tenant.objects.create(
    name='Minha Empresa',
    document='00000000000100',
    status='ACTIVE',
)
user = User.objects.create_user(
    email='admin@minhaempresa.com.br',
    password='troque-esta-senha',
    tenant=tenant,
    role='ADMIN',
)
```

## 11. Reiniciar e validar

```bash
sudo systemctl start uwsgi
sudo systemctl reload nginx

curl -I https://seu-dominio.com.br/login/
curl -I https://seu-dominio.com.br/list_os/
```

Validar manualmente:

- login por e-mail;
- criação de cliente e balança;
- criação e impressão de O.S.;
- assinatura obrigatória conforme plano;
- dashboard e exportação CSV;
- convite de usuário;
- exportação e anonimização LGPD;
- Django Admin somente para superusuário;
- envio de e-mail SMTP;
- headers HTTPS e CSP.

## 12. Rollback

Se a aplicação falhar, pare o serviço e restaure a release anterior. Se o
banco também tiver sido alterado, restaure o dump correspondente:

```bash
sudo systemctl stop uwsgi
pg_restore -h localhost -U postgres -d serviceorders \
  --clean --if-exists /var/backups/serviceorders_before_aferix_TIMESTAMP.dump
sudo systemctl start uwsgi
```

Para evitar perda de código, mantenha cada release em uma pasta separada, por
exemplo `/var/www/aferix/releases/20260923`, em vez de apagar a única cópia
ativa imediatamente.

## 13. Atualizações futuras

Depois da primeira instalação, o fluxo será:

```bash
cd /var/www/aferix
source venv/bin/activate
pip install -r requirements.txt
pip install uwsgi==2.0.30
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart uwsgi
```

O `.env`, o banco PostgreSQL e a pasta `media/` permanecem na EC2 e não devem
ser substituídos por arquivos vindos do GitHub.
