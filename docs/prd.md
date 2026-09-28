# PRD — Aferix OS Intelligence

**Product Requirement Document — Blueprint Técnico Definitivo**
**Versão:** 1.1 · **Status:** Aprovado para desenvolvimento · **Data:** 22/09/2026
**Sistema:** Aferix — SaaS Multi-Tenant de Gestão de Ordens de Serviço para Empresas de Manutenção, Calibração e Aferição de Balanças

> **Contexto de produção (v1.1):** o sistema legado (versão empresa única) já roda em **produção em EC2/AWS com domínio próprio**, mas **ainda não possui clientes pagantes ou operação real de campo** — apenas dados de teste. Isso elimina a necessidade de migração complexa de dados legados (R9 trivializado) e torna a adoção do modelo multi-tenant **a partir do schema atual, antes da aquisição dos primeiros clientes** (ver §1.6 e §13).

---

## Sumário

1. [Visão Geral do Produto](#1-visão-geral-do-produto)
2. [Objetivos e Métricas de Sucesso](#2-objetivos-e-métricas-de-sucesso)
3. [Personas e Casos de Uso](#3-personas-e-casos-de-uso)
4. [Escopo](#4-escopo)
5. [Arquitetura Técnica](#5-arquitetura-técnica)
6. [Estrutura de Apps Django](#6-estrutura-de-apps-django)
7. [Modelagem de Dados](#7-modelagem-de-dados)
8. [Especificação de Endpoints/Views](#8-especificação-de-endpointsviews)
9. [Integração com IA](#9-integração-com-ia)
10. [Design System](#10-design-system)
11. [Requisitos Não-Funcionais](#11-requisitos-não-funcionais)
12. [Planos e Monetização](#12-planos-e-monetização)
13. [Roadmap de Desenvolvimento em Fases](#13-roadmap-de-desenvolvimento-em-fases)
14. [Estrutura de Diretórios](#14-estrutura-de-diretórios)
15. [Variáveis de Ambiente](#15-variáveis-de-ambiente)
16. [Riscos e Mitigações](#16-riscos-e-mitigações)
17. [Glossário](#17-glossário)

---

## 1. Visão Geral do Produto

### 1.1 Problema

Empresas de manutenção, calibração e aferição de balanças operam sob **metrologia legal brasileira** (INMETRO / IPEM-PR). A rotina de campo é baseada em formulários de O.S. em papel, com riscos concretos:

- **Perda de rastreabilidade regulatória:** selos/lacres aplicados e retirados sem cadeia de custódia auditável (estoque → técnico → equipamento → O.S.).
- **Erros e retrabalho:** digitação manual, CNPJ/série duplicados, O.S. sem numeração sequencial consistente, peças e horas sem apontamento.
- **Demora administrativa:** fechamento do mês depende da digitação de papéis; gestão sem visão consolidada por técnico e por cliente.
- **Documento não padronizado:** O.S. sem cabeçalho fiscal, sem registro IPEM/PR, sem assinatura do cliente em bom formato.
- **Sem inteligência:** não há como consultar semanticamente histórico de O.S., resumir visitas, responder perguntas operacionais ("quantas preventivas em Curitiba no trimestre?") nem gerar rascunhos de laudos.

### 1.2 Solução

**Aferix** é um **SaaS multi-tenant** (Python 3.12+, Django 6.0, PostgreSQL) que:

1. Centraliza cadastro de **clientes**, patrimônio de **balanças** e emissão de **Ordens de Serviço** com os 8 tipos de serviço da área, selos, peças, tempos e **assinatura digital do cliente** em canvas.
2. Controla o **ciclo de vida dos selos** com máquina de estados automática e rastreabilidade completa.
3. Gera **documento A4 profissional** (logo, dados fiscais, nº IPEM/PR, numeração sequencial) com impressão/PDF nativo do navegador.
4. Isolamento por **tenant** (empresa contratante) e por **técnico** (visão restrita), com papéis claros.
5. Adiciona **camada de IA (LangChain + LangGraph + RAG)**: assistente conversacional que responde perguntas sobre O.S., clientes, balanças e selos, resume visitas, redige rascunhos de laudos e sugere preenchimento — com contexto multi-turno, cache de tokens, RAG sobre a base documental do próprio tenant e troca de modelo em runtime.

### 1.3 Público-alvo

| Segmento | Detalhe |
|---|---|
| Primário | Prestadoras de serviço de manutenção/calibração/aferição de balanças (dois a 50 técnicos), com forte aderência à metrologia legal (INMETRO, IPEM-PR). |
| Secundário | Empresas de outros serviços de campo com exigência de assinatura em ato (manutenção industrial, inspeção), validadas a posteriori. |
| Geográfico inicial | Brasil (pt-BR, fuso `America/Sao_Paulo`), com tração inicial no Paraná (IPEM/PR). |

### 1.4 Proposta de Valor

> **Do papel ao campo digital em minutos:** a empresa emite O.S. completa e assinada no tablet, com selo rastreado de ponta a ponta, documento A4 com registro IPEM/PR pronto para o cliente — e ainda pergunta à IA qualquer coisa sobre a própria operação.

**Diferenciais:**
- Encaixe fino com rotina regulatória de metrologia legal (selos, E(kg), inventário Inmetro, portaria).
- Assinatura do cliente no ato do serviço (canvas touch).
- Cadeia de custódia de selos automatizada (estoque → técnico → equipamento → O.S.).
- Isolamento por técnico sem módulo de permissões complexo.
- Assistente IA com RAG sobre os dados do próprio tenant (não genérico).
- Apontamento operacional integrado: peças, horas, carro/caminhão, hospedagem, refeição.

### 1.5 Estado Atual do Produto (baseline)

| Dimensão | Situação atual |
|---|---|
| Implantação | **Produção em EC2/AWS** + Nginx + uWSGI, **domínio próprio** |
| Modelo de dados | **Empresa única** (`Company.objects.first()`, sem coluna `tenant`) |
| Clientes reais | **Nenhum** — sem operação de campo nem pagantes; dados de teste |
| Funcionalidades em produção | Login, clientes, balanças, O.S. com 8 serviços, selos, assinatura canvas, impressão A4, listagem/busca, Django Admin |
| Ausente no legado | Multi-tenant, papéis (`TECHNICIAN`/`STAFF`/`ADMIN`), login por email, IA/RAG, planos/limites, PWA |
| Migração de dados | **Trivial** (sem clientes reais): backfill de um único tenant da própria empresa ou recriação limpa em staging |

**Decisão arquitetônica decorrente:** o **multi-tenant (Fase 1) deve ser implementado antes da aquisição dos primeiros clientes** — depois que houver O.S. real de terceiros, adicionar `tenant_id` em todas as tabelas e quebrar o modelo único custa ordens de grandeza mais caro.

### 1.6 Justificativa de Decisões Não-Triviais (Visão Geral)

| Decisão | Escolha | Justificativa |
|---|---|---|
| Modelo multi-tenant | Shared database / shared schema com coluna `tenant_id` | Regra crítica da arquitetura; menor custo operacional que schema-per-tenant (django-tenants), migrações únicas, complexidade de isolamento controlada por manager/middleware + RLS opcional. |
| Auth | Django nativo, login por **email** | Regra crítica; email é identificador estável e universal; `AbstractUser` customizado evita dívida de migração. |
| Vector store | **PostgreSQL + pgvector** | Mesmo banco operacional: sem novo serviço, transações ACID, backup único; escala suficiente para corpus de O.S./manuais de uma mid-size SaaS. |
| IA | LangChain (conectores) + **LangGraph** (orquestração) | LangGraph dá grafo explícito para fluxos com tool-calling (buscar O.S. → rag → resumir), checkpointing de sessão e memória durável. |
| Templates | Server-side Django (sem SPA) | Produto de campo com UX de formulário longo; manutenção mínima, SEO irrelevante, offline fora do MVP. |

---

## 2. Objetivos e Métricas de Sucesso

### 2.1 Objetivos de Produto

| # | Objetivo | Prazo |
|---|---|---|
| O1 | MVP multi-tenant funcional **em staging**, promovido a produção (EC2) no gate §13.5 — **antes do 1º cliente**. | Fase 1 (MVP) |
| O2 | Primeiro piloto real: empresa rodando 100% das O.S. no sistema (zero papel). | +60 dias pós-MVP |
| O3 | Assistente IA com RAG operacional em produção (resumo, busca semântica, rascunho de laudo). | Fase 2 (v1.1) |
| O4 | Modelos de monetização self-service (planos + limites + billing). | Fase 3 (v1.2) |

### 2.2 KPIs

**Fase comercial (até o 1º cliente):**

| KPI | Definição | Meta (primeiros 6 meses) |
|---|---|---|
| Pipeline | Empresas de balanças em negociação ativa | ≥ 10 leads qualificados |
| Primeiro tenant pagante | 1ª empresa convertida em plano pago | ≤ 6 meses pós-MVP |
| Piloto concluído | Empresa rodando ≥ 2 semanas só com O.S. do sistema (zero papel) | ≥ 1 piloto |
| Tempo até 1ª O.S. real | Do login do tenant ao primeiro documento assinado em campo | ≤ 1 dia |

**Fase operacional (após 1º cliente, meta 12 meses):**

| KPI | Definição | Meta (12 meses) |
|---|---|---|
| Ativação | % de tenants com ≥1 O.S. assinada nos primeiros 7 dias | ≥ 70% |
| Adoção de campo | O.S. criadas por semana / técnicos ativos | ≥ 3 |
| Tempo médio de emissão | Minutos entre abrir formulário e salvar O.S. | ≤ 6 min |
| Assinatura no ato | % de O.S. salvas com `signature` preenchida | ≥ 95% |
| Rastreio de selos | % de O.S. com selo vinculado (quando aplicável) | 100% |
| Retenção | Tenants com atividade no mês N e N+1 | ≥ 85% |
| Uso de IA | % de tenants ativos com ≥1 conversa IA/semana | ≥ 40% |
| Custo de IA | Tokens por O.S. gerada (cache hit ≥ 40%) | redução 30% vs. baseline |
| Disponibilidade | Uptime da aplicação (EC2) | ≥ 99,5% |
| Suporte | Tickets críticos / 100 O.S. | ≤ 1 |

---

## 3. Personas e Casos de Uso

### 3.1 Personas e Papéis (Roles)

| Role (`User.role`) | Persona | Responsabilidades | Fluxos principais | Escopo de visão |
|---|---|---|---|---|
| `TECHNICIAN` | **Carlos, técnico de campo** — 8 anos com balanças, tablet no carrinho | Executa visita, abre O.S., recebe selos, registra serviços/peças/horas, coleta assinatura do cliente | Login → busca cliente por CNPJ → balança → Gerar O.S. → preenche → assinatura → salva → imprime se preciso | Somente O.S. próprias (`created_by = self`) |
| `STAFF` | **Ana, coordenadora de campo** | Edita O.S. existentes, corrige lançamentos, apoia o técnico | Lista geral do tenant → detalhe → editar → reprimir | Todas O.S. do tenant; edição permitida |
| `ADMIN` | **Dono da prestadora (gestor)** | Visão consolidada, cadastros (empresa, clientes, balanças), distribuição de selos, gestão de usuários, planos | Admin + dashboards → distribuir selos → acompanhar O.S. → falar com IA sobre indicadores | Todo o tenant |
| `CLIENT_SIGNER` | **João, responsável do cliente** — não tem login | Assina digitalmente a O.S. no ato do serviço | Envia o tablet → assina no canvas → confirma | Só a O.S. apresentada no momento |

> **Regra de permissão canônica:** `TECHNICIAN` vê apenas suas O.S.; `STAFF`/`ADMIN` veem todas do tenant; edição de O.S. exigida a `role in {STAFF, ADMIN}`; Django Admin (superuser) é ferramenta de suporte interno, não fluxo de negócio do SaaS.

### 3.2 User Stories (MVP)

| ID | Como… | Quero… | Para que… | Critério de aceite (Given/When/Then resumido) |
|---|---|---|---|---|
| US-01 | ADMIN | Cadastrar a minha empresa (razão social, CNPJ, IE, endereço, logo, nº IPEM/PR) | O cabeçalho da O.S. impressa sair correto | Dados persistem; detalhe da O.S. exibe logo + nº IPEM/PR; sem empresa → aviso instrutivo. |
| US-02 | ADMIN | Cadastrar clientes validando CNPJ/CPF único no tenant | Evitar duplicidade | Duplicado → erro de campo; sucesso → lista com busca. |
| US-03 | ADMIN | Cadastrar balanças (série, capacidade, E(kg), TAG, inventário Inmetro, portaria) por cliente | Patrimônio rastreável | Série duplicada **no mesmo cliente** → erro; select2 de proprietário. |
| US-04 | ADMIN | Distribuir selos aos técnicos (nº, técnico, data) | Ter estoque em campo | Selo `AVAILABLE` → `DISTRIBUTED`; dropdown da O.S. só mostra selos do técnico `AVAILABLE`. |
| US-05 | TECHNICIAN | Gerar O.S. a partir do detalhe do cliente/balança | Registrar visita | Rota contextual `/os/nova/<client>/<scale>/`; cliente e balança somente leitura. |
| US-06 | TECHNICIAN | Marcar um dos 8 serviços, selo aplicado/retirado, informações complementares | Cumprir checklist regulatório | Checkboxes persistem; ao salvar, selo consumido → `USED` e FK gravada. |
| US-07 | TECHNICIAN | Adicionar peças (código, qtd, série, descrição, base de troca) e tempos (dia, início, parada, total, carro, caminhão) | Apontar custo | Formsets dinâmicos (add/remove linha) salvam em transação única. |
| US-08 | TECHNICIAN | Coletar a **assinatura do cliente** em canvas (touch) | Comprovar ato | `signature` (dataURL PNG) opcional no MVP com aviso; obrigatória em v1.2 por plano. |
| US-09 | TECHNICIAN | Ver "Suas Ordens" com busca (nº, cliente, cidade, CNPJ) e filtro de data | Consultar histórico | Queryset filtrado por `created_by` se não admin; ordenação `-created_at`. |
| US-10 | Qualquer autenticado | Visualizar O.S. em documento A4 e imprimir/PDF | Entregar ao cliente | `@media print` oculta UI; cabeçalho da empresa; nº `%05d`; assinaturas. |
| US-11 | STAFF | Editar O.S. existente | Corrigir erros | Rota protegida a `role in {STAFF, ADMIN}`; técnicos recebem 403. |
| US-12 | ADMIN | Gerir usuários do tenant (convidar técnico, mudar role) | Operar a equipe | CRUD de usuários restrito ao tenant; convite por email. |
| US-13 | ADMIN | Definir plano/limites e acompanhar consumo | Controlar custo | Tenant tem `plan`; bloqueio suave ao exceder limites. |

### 3.3 User Stories (IA — v1.1)

| ID | Como… | Quero… | Critério de aceite |
|---|---|---|---|
| US-20 | ADMIN/STAFF | Conversar com o **Assistente Aferix** no painel | Chat multi-turno com histórico por sessão; streaming de resposta. |
| US-21 | ADMIN/STAFF | Perguntar "quantas O.S. preventivas o cliente X teve em 2026?" | Agente usa tool `query_service_orders` com filtros (ferramenta tipada) e responde com números. |
| US-22 | ADMIN/STAFF | Resumir uma O.S. em 5 tópicos para reunião | Tool `get_service_order` + nó LLM de resumo; saída em pt-BR. |
| US-23 | TECHNICIAN | Redigir rascunho de laudo/observações a partir dos serviços marcados | Tool `draft_service_report`; técnico edita antes de salvar. |
| US-24 | ADMIN/STAFF | Perguntar sobre procedimentos (ex.: "como aplicar selo de conferência?") | RAG sobre corpus do tenant (manuais, normas carregadas) com citação de fonte. |
| US-25 | ADMIN | Trocar o modelo de IA em runtime (OpenAI ↔ Claude) | Setting por tenant/global; sem deploy; factory resolve em runtime. |
| US-26 | Qualquer autenticado | Respostas rápidas sem estourar token/custo | Cache semântico de prompts + histórico truncado por janela de tokens. |

### 3.4 Casos de Uso (diagrama conceitual)

```mermaid
flowchart LR
  subgraph Field[Técnico de campo]
    UC1[Buscar cliente por CNPJ]
    UC2[Selecionar balança]
    UC3[Emitir O.S.]
    UC4[Consumir selo]
    UC5[Assinatura canvas]
  end
  subgraph Office[Gestão]
    UC6[Cadastrar empresa/clientes/balanças]
    UC7[Distribuir selos]
    UC8[Listar/filtrar O.S.]
    UC9[Imprimir A4/PDF]
    UC10[Conversar com Assistente IA]
  end
  T((Técnico)) --> UC1 --> UC2 --> UC3 --> UC4 --> UC5
  A((Admin)) --> UC6
  A --> UC7
  A --> UC8 --> UC9
  A --> UC10
  S((Staff)) --> UC8
  S --> UC10
```

---

## 4. Escopo

### 4.1 Dentro do escopo — MVP (Fase 1)

- Multi-tenant shared schema com `Tenant` + middleware + managers.
- Auth nativa Django com login por email, registro por convite, papéis (`TECHNICIAN`, `STAFF`, `ADMIN`).
- Cadastro de Empresa (= Tenant com branding: logo, IPEM/PR), Clientes, Balanças, Unidades.
- Emissão de O.S.: 8 serviços, selos (aplicado/retirado), informações complementares, formsets de peças e tempos, assinatura canvas.
- Máquina de estados de selos: `AVAILABLE → DISTRIBUTED → USED / DAMAGED`.
- Listagem/detalhe/impressão A4 com numeração sequencial por tenant.
- Permissões por role + isolamento de O.S. por técnico.
- Busca (cliente por CNPJ, balança por série, O.S. por nº/cliente/cidade/CNPJ + filtro data) e filtros client-side.
- Django Admin para suporte (superuser) + telas de negócio próprias.
- Testes automatizados (suíte Django) e CI básica.
- Design system conforme `@design_system/design-system.html`.

### 4.2 Dentro do escopo — v1.1 (IA)

- App `ai`: chat multi-turno, sessões, streaming.
- Orquestração com **LangGraph** + ferramentas tipadas sobre o domínio (somente dados do tenant).
- **RAG com pgvector** sobre corpus do tenant (manuais, normas, templates de laudo).
- Gestão de contexto (janela de tokens, resumo de histórico), **cache semântico**, métricas de tokens.
- Abstração multi-provider (OpenAI, Anthropic, mock) com **troca em runtime**.

### 4.3 Dentro do escopo — v1.2 (Monetização e escala de operação)

- Planos, limites (técnicos, O.S./mês, créditos IA), trial, bloqueio suave/hard.
- Dashboard de indicadores (O.S. por status, por técnico, por período).
- Notificações por email (convite, O.S. assinada, limite atingido).
- Exportação CSV de O.S. e peças.
- Assinatura obrigatória por plano; reimpressão com hash de integridade (checksum do documento).

### 4.4 Fora do escopo (MVP e v1.x)

| Item | Motivo / quando |
|---|---|
| PDF nativo (WeasyPrint/ReportLab) | MVP usa `window.print()`; avaliar em v1.3 se volume exigir arquivamento binário. |
| Multiempresa dentro do mesmo login (multi-tenant aninhado) | Um usuário pertence a exatamente um tenant no MVP. |
| Offline/PWA | Requer service worker + sincronização conflitante; futuro v2.0. |
| Assinatura eletrônica ICP-Brasil/PAC-Brasil | Exige provedor de certificação e audit trail legal; roadmap v2.0. |
| App mobile nativo | Web responsiva cobre tablet de campo no MVP. |
| Marketplace de integrações (ERP, fiscal) | Somente após PMF; API REST pública entra em v1.3. |
| Faturamento/boleto próprio | MVP sem billing real (limites manuais); gateways em v1.2+. |
| Multi-idioma | Somente pt-BR. |
| Recuperação de senha por SMS | Usar email. |

### 4.5 Solicitações de mudança incorporadas a este PRD

#### 4.5.1 FEATURE 1 — Relatório técnico para balança rodoviária

O sistema deverá permitir o preenchimento e a impressão de um **Relatório Técnico**
baseado no formulário PDF fornecido pelo produto. O relatório é uma extensão da
O.S., não um documento independente: ele só poderá existir quando estiver
associado a uma `ServiceOrder` cuja balança seja classificada como
`RODOVIARIA`, `FERROVIARIA` ou `RODOFERROVIARIA`.

**Reaproveitamento obrigatório de dados existentes:**

- Cliente: razão social, CNPJ/CPF, inscrição estadual/RG, endereço, cidade, UF,
  CEP, contato e email.
- Balança: marca, modelo, série, capacidade máxima, divisão E(kg), TAG,
  inventário Inmetro e portaria/ano.
- O.S.: número, tenant, técnico responsável, data do serviço, serviços
  selecionados, selo aplicado/retirado, observações e assinatura do proprietário.
- Tenant: identidade visual, razão social, CNPJ, endereço e registro IPEM/PR.

**Dados adicionais específicos do relatório:**

- tipo da balança: `RODOVIARIA`, `FERROVIARIA` ou `RODOFERROVIARIA`;
- capacidade mínima e classe metrológica;
- código do proprietário;
- serviço executado: `REPARO`, `REFORMA` ou `INSTRUMENTO_NOVO`;
- ensaio de fidelidade com três posições;
- ensaio de excentricidade com seis posições;
- ensaio de pesagem com 22 posições;
- em cada posição: sequência, carga, indicação, erro e E.M.A., em kg;
- certificado e placa do peso padrão;
- número reparado/colocado e selo verificado/retirado;
- nome/documento do técnico, nome do responsável, cidade e data;
- assinatura do técnico, quando capturada no fluxo do relatório.

**Decisões de produto:**

- O relatório terá relação 1:1 com a O.S. para impedir dois documentos
  regulatórios concorrentes para a mesma visita.
- A assinatura do proprietário será reutilizada de `ServiceOrder.signature` e o
  nome será reutilizado de `ServiceOrder.client_signer_name`; o sistema não
  deverá solicitar esses dados novamente no relatório.
- As medições serão persistidas em registros estruturados, e não em um JSON ou
  imagem, para permitir auditoria, exportação e futura análise pela IA.
- Os registros das três tabelas de ensaio serão criados com as posições
  previstas pelo formulário, mesmo quando uma medição estiver vazia. Campos de
  medição serão opcionais enquanto o relatório estiver em rascunho e obrigatórios
  ao concluir o documento.
- O relatório não será criado automaticamente ao emitir a O.S.; o usuário o
  abrirá explicitamente pela ação “Relatório técnico”. Isso evita criar laudos
  vazios para O.S. que não exigem aferição rodoviária.
- Os campos `scale_type`, capacidade mínima e classe metrológica pertencem ao
  cadastro permanente de `Scale`, pois descrevem o equipamento. No momento da
  criação do relatório, seus valores também serão copiados para snapshots no
  relatório, juntamente com os valores regulatórios da balança e dos selos que
  aparecem no documento. A cópia é deliberada: um documento concluído não pode
  mudar porque o cadastro operacional foi corrigido depois.
- Balanças sem classificação e classificações fora das três opções suportadas
  não exibem o relatório técnico. Se uma balança com relatório concluído mudar
  de classificação para fora dessas opções, a alteração deverá ser bloqueada
  até que o relatório seja cancelado por `STAFF` ou `ADMIN`.

**Decisões da Sprint 5.1:**

- A validação com operação foi feita documentalmente contra o PDF fornecido,
  incluindo os campos manuscritos legíveis, as três tabelas e a observação legal.
  O aceite presencial/visual com técnico continua uma etapa de UAT da Sprint
  5.5 e não será tratado como concluído nesta sprint.
- Todas as massas e resultados usam kg. A entrada aceita sinal em `error` e
  `ema`, até três casas decimais; não haverá conversão automática de tonelada,
  ponto ou vírgula além da normalização explícita da UI. Valores negativos só
  serão aceitos para erro quando o técnico os informar.
- `FidelityTest` terá 3 posições, `EccentricityTest` terá 6 posições e
  `WeighingTest` terá 22 posições. `EccentricityTest` terá também
  `applied_load_kg` no cabeçalho do ensaio, pois o PDF não repete esse valor em
  cada linha.
- O relatório terá `DRAFT`, `COMPLETED` e `CANCELED`. Nasce como `DRAFT`, pode
  ser salvo incompleto, só passa a `COMPLETED` com os campos obrigatórios, e
  `CANCELED` é uma transição auditada que mantém o documento para consulta. Um
  `ADMIN` poderá reabrir um cancelado para `DRAFT`, sempre gerando auditoria;
  não haverá exclusão física de relatório concluído.
- A data, técnico, cidade, selos e placa do caminhão serão derivados da O.S. e
  dos seus tempos de serviço; não haverá campos duplicados no relatório.
- O número exibido no relatório será o número da O.S. com a mesma formatação
  `%05d`; não haverá uma segunda sequência regulatória. O `TechnicalReport`
  continuará 1:1 com a O.S.
- A assinatura do proprietário reutiliza `ServiceOrder.signature`. Se o plano
  exigir assinatura, a ausência dela impede concluir o relatório. O responsável
  técnico será o usuário da O.S.; o documento impresso exibirá seu nome, sem
  uma segunda assinatura ou RG no relatório.
- O erro de cada ensaio será calculado automaticamente como `indicação - carga`
  e ficará somente para leitura no formulário.
- Excentricidade significa aplicar a carga em diferentes pontos da plataforma
  para verificar se a balança mantém a mesma indicação; o fluxo manterá as seis
  posições do formulário com essa explicação visível.
- O MVP usará impressão do navegador (`window.print`) com CSS A4. PDF nativo,
  hash de integridade e assinatura ICP-Brasil permanecem fora desta sprint e
  seguem o backlog v1.3/v2.0 já definido no PRD.

**Matriz de obrigatoriedade ao concluir:**

| Grupo | Obrigatórios |
|---|---|
| Identidade | O.S., tenant, cliente, balança, tipo, serviço, cidade, data e técnico autenticado |
| Equipamento | snapshots de marca/modelo/série, capacidade, E(kg), tipo e classe quando cadastrada |
| Serviço | serviço executado, certificado/placa do peso padrão quando houver peso padrão, selos conforme a O.S. |
| Ensaios | todas as colunas das 3 + 6 + 22 posições; `applied_load_kg` para excentricidade |
| Assinaturas | assinatura do proprietário conforme plano; técnico identificado pelo usuário da O.S. |
| Cancelamento | `canceled_reason` obrigatório; nenhum ensaio é apagado |

**Critérios de aceite mensuráveis:**

1. Uma O.S. de balança classificada como `RODOVIARIA`, `FERROVIARIA` ou
   `RODOFERROVIARIA` exibe a ação do relatório; balanças sem classificação ou
   com tipo não suportado não exibem a ação e recebem HTTP 404/403 ao tentar
   acessar a rota diretamente.
2. O formulário exibe os dados de cliente, balança, O.S. e tenant sem permitir
   sua edição ou duplicação no relatório.
3. Um relatório salvo possui exatamente uma relação com a O.S., três posições de
   fidelidade, seis de excentricidade e 22 de pesagem.
4. O sistema rejeita a conclusão quando faltar qualquer medição obrigatória,
   identificação do serviço, data, técnico ou assinatura exigida pelo plano.
5. O relatório impresso reproduz em uma página A4 o cabeçalho do tenant, a
   identificação do cliente/equipamento, os três ensaios, selos, Inmetro, IPEM,
   peso padrão, assinaturas e observação legal do formulário de referência.
6. Usuários de um tenant não conseguem consultar ou alterar relatório de outro
   tenant; técnicos só acessam relatórios das próprias O.S.; `STAFF` e `ADMIN`
   acessam os relatórios do tenant.
7. Criar, editar, concluir, cancelar e imprimir o relatório gera auditoria sem
   registrar CNPJ/CPF completo nos metadados do `AuditLog`.
8. A suíte automatizada cobre, no mínimo, 100% das regras acima, isolamento
   entre dois tenants, bloqueio por tipo de balança e persistência dos 31
   registros de ensaio.

#### 4.5.2 FEATURE 2 — Especificação pendente

O pedido de alteração contém o marcador `[FEATURE 2: descrição]`, mas não informa
qual comportamento deve ser criado. Nenhuma decisão de produto, modelagem,
endpoint ou sprint específica será inventada. Antes do desenvolvimento, devem ser
fornecidos objetivo, persona, fluxo, dados, permissões e critério de aceite.

#### 4.5.3 CORREÇÃO 1 — Especificação pendente

O pedido também contém o marcador `[CORREÇÃO 1: descrição]`, sem indicar o
comportamento atual incorreto nem o resultado esperado. O item fica registrado
como bloqueado para evitar uma correção especulativa. O solicitante deverá
informar reprodução, impacto, ambiente, resultado atual e resultado esperado.

---

## 5. Arquitetura Técnica

### 5.1 Diagrama Geral

```mermaid
flowchart TB
  subgraph Client[Navegador / Tablet de campo]
    B[HTML + Bootstrap 5 + jQuery + SignaturePad]
  end

  subgraph Edge[Edge]
    N[Nginx — TLS, static, media]
    U[uWSGI — múltiplos workers]
  end

  subgraph App[Django 6.0 — Python 3.12+]
    MW[TenantMiddleware + Auth]
    V[Class-Based Views — server-rendered templates]
    A[App ai — LangGraph agents + tools]
    RAG[Retriever pgvector]
  end

  subgraph Data[Persistência]
    PG[(PostgreSQL 16 + pgvector)]
    CACHE[(Cache: DB ou Redis)]
  end

  subgraph LLM[Provedores de IA]
    O[OpenAI]
    C[Anthropic]
    M[Mock / Local]
  end

  B -->|HTTPS| N --> U --> MW --> V
  V --> PG
  A --> RAG --> PG
  A --> O
  A --> C
  A --> M
  V --> CACHE
  A --> CACHE
```

### 5.2 Multi-Tenant (shared database / shared schema)

**Regra crítica.** Implementação:

1. Modelo `Tenant` (razão social, CNPJ, logo, registro IPEM/PR, plano, status).
2. `TenantMiddleware` resolve o tenant a partir de `request.user.tenant` após autenticação; armazena em `request.tenant` e em context var para uso em managers.
3. **Todo model de domínio** herda `TimeStampedModel` + possui `tenant = FK(Tenant, on_delete=CASCADE, related_name='+', db_index=True)`.
4. `TenantManager(BaseManager)` filtra automaticamente `queryset.filter(tenant=current_tenant)`; `objects` = manager global (superuser/admin Django), `scoped` = manager do tenant.
5. Formularios/`ModelForm` injetam `tenant` do request antes do `save()` (nunca confiar em input).
6. Unique constraints compostas com `tenant` (ex.: `UniqueConstraint(fields=['tenant', 'document'])`).
7. Views CBV sempre partem do `request.tenant`; 404 se usuário sem tenant ativo.
8. **Defense in depth (opcional Fase 2):** PostgreSQL Row-Level Security com `SET app.tenant_id` por conexão — não bloqueante para o MVP, previsto como hardening.

**Justificativa:** shared schema mantém migrações únicas e custo de infra baixo (ideal para SaaS early-stage com muitos tenants pequenos); o risco de vazamento é endereçado por manager + constraints + testes de isolamento obrigatórios (ver §11.1).

### 5.3 Fluxo de Autenticação

```mermaid
sequenceDiagram
  participant U as Usuário
  participant V as LoginView
  participant DB as PostgreSQL
  participant M as TenantMiddleware
  U->>V: POST /auth/login/ (email, password)
  V->>DB: SELECT user WHERE email=?
  alt credenciais inválidas
    V-->>U: 200 + erro de formulário
  else válidas
    V->>DB: login() → session
    V-->>U: 302 /app/
    U->>M: requisição autenticada
    M->>DB: carrega user.tenant (select_related)
    M-->>U: request.tenant pronto para as views
  end
```

- Backend de auth: `accounts.backends.EmailBackend` (`USERNAME_FIELD = 'email'`).
- `LOGIN_URL = '/auth/login/'`, `LOGIN_REDIRECT_URL = '/app/'`.
- Todas as telas de negócio com `LoginRequiredMixin` / `@login_required`.
- Convite de usuário (v1.1): ADMIN cria usuário com email+role; token de convite expira em 72h; primeiro acesso define senha.

### 5.4 Fluxo do Agente de IA (LangGraph)

```mermaid
flowchart TD
  IN[Pergunta do usuário + session_id] --> CTX[Carregar histórico + tenant context]
  CTX --> CACHE{Cache semântico?}
  CACHE -->|hit| RESP[Resposta em cache]
  CACHE -->|miss| ROUTER[Nó router LangGraph]
  ROUTER -->|intenção factual operacional| TOOLS[Nó tools: query OS / cliente / selo]
  ROUTER -->|conhecimento procedural| RET[RAG: pgvector top-k]
  ROUTER -->|resumo/redação| SUM[Nó LLM de síntese]
  TOOLS --> GUARD[Guard de tenant isolation — só dados do request.tenant]
  RET --> GUARD
  SUM --> GUARD
  GUARD --> SYN[Nó síntese final streaming]
  SYN --> STORE[Persistir mensagens + token usage]
  STORE --> RESP
  RESP --> UI[Streaming para o template de chat]
```

**Justificativa LangGraph:** o fluxo acima é um grafo com ramificação (tools vs. RAG vs. resumo), checkpoints por sessão (`checkpointer`) e falhas tratáveis por nó — algo frágil em cadeias lineares de LangChain pura.

### 5.5 Diagrama de Implantação

```mermaid
flowchart LR
  subgraph Prod["Produção — EC2/AWS (domínio próprio)"]
    NG[Nginx — TLS domínio real] --> WS[uWSGI uwsgi.ini] --> DJ[Django]
    DJ --> PG[(PostgreSQL + pgvector)]
    DJ --> C[(Cache DB/Redis)]
    NG --> ST[/static/]
    NG --> MD[/media/]
  end
  subgraph Stage[Staging — Fase 1]
    NG2[Nginx staging] --> DJ2[Django branch multi-tenant]
    DJ2 --> PG2[(PostgreSQL staging)]
  end
  CI[GitHub Actions: lint + pytest] --> NG2
  CI --> NG
```

**Nota v1.1:** produção atual (EC2 + domínio próprio, empresa única) **não pode ser quebrada** — mesmo sem clientes pagantes, é o ambiente de demonstração. Toda a Fase 1 é desenvolvida e validada em **staging**; a troca de produção (migração multi-tenant) ocorre em janela única com snapshot + rollback, quando o MVP estiver aprovado no gate §13.5.

---

## 6. Estrutura de Apps Django

| App | Responsabilidade | Dono do domínio |
|---|---|---|
| `core` | `TimeStampedModel`, `TenantScopedModel`, managers, mixins de permissão, constantes, utilitários (formatação CNPJ, números de O.S.) | transversal |
| `accounts` | `User` custom (email), backend de auth, views de login/logout/registro/convite, gestão de usuários do tenant | identidade |
| `tenants` | `Tenant`, `Plan`, `Subscription`, middleware de tenant, limites de uso | multi-tenancy / billing |
| `clients` | `Client` (CNPJ/CPF, endereço, contato) | cadastro |
| `assets` | `Unit`, `Scale` (balanças/patrimônio) | cadastro |
| `stamps` | `Stamp`, `StampDelivery`, máquina de estados, distribuição | rastreabilidade regulatória |
| `service_orders` | `ServiceOrder`, `ServicePart`, `ServiceTime`, numeração sequencial, impressão A4, assinatura | núcleo do produto |
| `ai` | `ChatSession`, `ChatMessage`, `SourceDocument`, `TokenUsage`, cache semântico, grafos LangGraph, tools, retriever, providers | inteligência |
| `billing` (v1.2) | `PlanLimit`, uso vs. limites, bloqueio, relatórios de consumo | monetização |

**Regras de separação:**
- Uma app nunca importa `views`/`forms` de outra app; dependências apenas via `models` ou `services` (camada `services.py` para lógica transversal, ex.: `service_orders/services.py` consome `stamps` via API pública `stamps/services.py::consume_stamp()`).
- Signals somente em `signals.py` da app dona; preferir `services.py` quando houver lógica com múltiplas escritas transacionais.
- Código em **inglês**; interface em **pt-BR**.

---

## 7. Modelagem de Dados

### 7.1 Convenções

- Todo model concreto herda `TimeStampedModel` (`created_at auto_now_add`, `updated_at auto_now`) — **regra crítica**.
- Todo model de domínio herda `TenantScopedModel(TimestampedModel)` com `tenant`.
- **Decisão de PK:** `BigAutoField` (simplicidade Django); expor `uuid = UUIDField(unique=True, default=uuid4)` apenas em `ServiceOrder` para links/impressão não enumeráveis.
- Idioma dos identificadores em inglês; `choices` em inglês com labels pt-BR no display.
- PEP 8; aspas simples.

### 7.2 Tabela de Models

#### `core.TimeStampedModel` (abstract)

| Campo | Tipo | Restrições |
|---|---|---|
| `created_at` | DateTimeField | `auto_now_add=True` |
| `updated_at` | DateTimeField | `auto_now=True` |

#### `core.TenantScopedModel` (abstract)

| Campo | Tipo | Restrições |
|---|---|---|
| (herda TimeStampedModel) | | |
| `tenant` | FK → `tenants.Tenant` | `on_delete=CASCADE`, `db_index=True`, `related_name='+'` |

#### `accounts.User`

| Campo | Tipo | Restrições |
|---|---|---|
| `id` | BigAutoField | PK |
| `email` | EmailField | **unique**, `USERNAME_FIELD`, normalizado lower |
| `first_name`, `last_name` | CharField(150) | blank |
| `role` | CharField(20) | choices: `TECHNICIAN`, `STAFF`, `ADMIN`; default `TECHNICIAN` |
| `tenant` | FK → Tenant | `PROTECT` (não apagar tenant com usuários), `related_name='users'`, null=True para superuser interno |
| `is_active`, `is_staff`, `is_superuser` | BooleanField | defaults Django |
| `phone` | CharField(20) | blank |
| `invite_token` | CharField(64) | null, blank, index |
| `invite_expires_at` | DateTimeField | null |

**Constraints:** `UniqueConstraint(fields=['email'], name='uniq_user_email')`.
**Justificativa email como USERNAME_FIELD:** identificador universal para SaaS, evita ambiguidade de username, alinhado à regra crítica de auth.

#### `tenants.Tenant`

| Campo | Tipo | Restrições |
|---|---|---|
| `name` | CharField(150) | razão social / nome fantasia |
| `legal_name` | CharField(150) | blank |
| `document` | CharField(18) | **CNPJ único no sistema** (índice) |
| `state_registration` | CharField(20) | blank — Inscrição Estadual |
| `zip_code`, `street`, `neighborhood`, `city`, `state` | CharField | endereço |
| `phone` | CharField(20) | blank |
| `email` | EmailField | contato |
| `logo` | ImageField(upload_to='tenants/logos/', blank) | Pillow; validação JPEG/PNG ≤ 2 MB |
| `ipem_register` | CharField(50) | **nº registro IPEM/PR**; blank com aviso na O.S. |
| `status` | CharField | `TRIAL`, `ACTIVE`, `SUSPENDED`, `CANCELED` |
| `timezone` | CharField(50) | default `America/Sao_Paulo` |

**Índices:** `document` unique.

#### `tenants.Plan` (v1.2; tabela seed no MVP)

| Campo | Tipo | Restrições |
|---|---|---|
| `code` | SlugField | unique — `basic`, `pro`, `enterprise` |
| `name` | CharField(80) | |
| `price_monthly_cents` | IntegerField | ≥ 0 |
| `max_technicians` | IntegerField | null = ilimitado |
| `max_service_orders_per_month` | IntegerField | null = ilimitado |
| `max_ai_credits_per_month` | IntegerField | null = ilimitado |
| `ai_enabled` | BooleanField | default True |
| `required_signature` | BooleanField | default False |
| `is_active` | BooleanField | |

#### `tenants.Subscription`

| Campo | Tipo | Restrições |
|---|---|---|
| `tenant` | FK Tenant | UNIQUE, CASCADE |
| `plan` | FK Plan | PROTECT |
| `status` | CharField | `PAST_DUE`, `TRIALING`, `ACTIVE` |
| `current_period_start/end` | DateTimeField | |
| `seats_used` | IntegerField | default 0 |

#### `clients.Client` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `name` | CharField(150) | razão social ou nome |
| `document` | CharField(18) | CNPJ/CPF — **unique por tenant** |
| `state_registration` | CharField(20) | blank |
| `zip_code` … `state` | CharFields | endereço completo |
| `contact_name`, `phone`, `email` | CharField/EmailField | blank |
| `notes` | TextField | blank |

**Constraints:** `UniqueConstraint(fields=['tenant', 'document'], name='uniq_client_tenant_document')`.
**Validação:** limpar máscara no `clean()`; comparar só dígitos.

#### `assets.Unit`

| Campo | Tipo | Restrições |
|---|---|---|
| `name` | CharField(30) | ex.: `kg`, `g` |
| `symbol` | CharField(10) | |

**Constraints:** `UniqueConstraint(['tenant', 'name'])`.

#### `assets.Scale` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `brand` | CharField(80) | marca |
| `model_name` | CharField(80) | `model` é atributo reservado Django → nome `model_name` |
| `serial_number` | CharField(64) | **unique por tenant+cliente** |
| `capacity_kg` | DecimalField(10,2) | > 0 |
| `division_e_kg` | DecimalField(10,3) | **divisão E(kg)** > 0 |
| `unit` | FK Unit | PROTECT |
| `tag` | CharField(30) | TAG interna, blank |
| `inmetro_inventory` | CharField(50) | **N° Inventário Inmetro**, blank |
| `portaria` | CharField(50) | **Portaria/Ano**, blank |
| `owner` | FK Client | CASCADE, `related_name='scales'` |
| `is_active` | BooleanField | default True |

**Constraints:** `UniqueConstraint(['tenant', 'owner', 'serial_number'], name='uniq_scale_serial_per_client')`.
**Índices:** `(tenant, owner)`, `(tenant, serial_number)`.

#### `stamps.Stamp` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `number` | CharField(30) | **unique por tenant** |
| `status` | CharField(20) | choices em inglês: `AVAILABLE`, `DISTRIBUTED`, `DAMAGED` (label pt-BR) |

> **Nota de implementação:** choices do código em inglês com labels pt-BR — consistente com a regra de código em inglês. O modelo legado usava strings em português; a migração de dados normaliza para o novo domínio.

**Constraints:** `UniqueConstraint(['tenant', 'number'])`.

#### `stamps.StampDelivery` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `stamp` | FK Stamp | CASCADE, `related_name='deliveries'` |
| `user` | FK accounts.User | PROTECT, `related_name='stamp_deliveries'` |
| `delivered_at` | DateTimeField | default `timezone.now` |
| `status` | CharField(20) | `AVAILABLE` (com técnico), `USED`, `DAMAGED` |
| `used_on` | FK ServiceOrder | null, blank, SET_NULL |

**Máquina de estados (serviço `stamps/services.py`):**

| Evento | De | Para |
|---|---|---|
| criar estoque | — | Stamp `AVAILABLE` |
| distribuir a técnico | Stamp `AVAILABLE` | Stamp `DISTRIBUTED` + StampDelivery `AVAILABLE` |
| usar em O.S. | Delivery `AVAILABLE` | Delivery `USED`; Stamp `DISTRIBUTED` (estoque do técnico diminui) |
| marcar danificado | Delivery `AVAILABLE` | `DAMAGED`; Stamp `DAMAGED` |

Transições validadas em service com `transaction.atomic()` + `select_for_update()` no Stamp — **evita race condition** de duplo consumo do mesmo selo.

#### `service_orders.ServiceOrder` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `uuid` | UUIDField | unique, default uuid4, editable=False |
| `number` | PositiveIntegerField | **sequencial por tenant** — ver numeração |
| `client` | FK Client | PROTECT, `related_name='service_orders'` |
| `scale` | FK Scale | PROTECT, `related_name='service_orders'` |
| `created_by` | FK User | PROTECT, `related_name='authored_service_orders'` |
| `performed_at` | DateTimeField | data/hora do serviço; default now |
| `corrective_maintenance` | BooleanField | serviço 1 — manutenção corretiva |
| `preventive_maintenance` | BooleanField | serviço 2 — manutenção preventiva |
| `certification_standard_weights` | BooleanField | serviço 3 — certificação com pesos padrão |
| `adjustment_standard_weights` | BooleanField | serviço 4 — ajustes com pesos padrão |
| `conformity_certificate` | BooleanField | serviço 5 — certificado de conformidade |
| `platform_repair` | BooleanField | serviço 6 — reparo em plataforma/estrutura |
| `electronic_repair` | BooleanField | serviço 7 — reparo eletroeletrônico |
| `communication_repair` | BooleanField | serviço 8 — reparo em comunicação/exterior |
| `services_observation` | TextField | blank |
| `verified_by_inmetro` | BooleanField | "Equipamento verificado pelo INMETRO este ano" |
| `new_installation` | BooleanField | "Instalação nova" |
| `hosting` | BooleanField | "Hospedagem" |
| `meals` | BooleanField | "Refeição" |
| `stamp` | FK Stamp | null, blank, PROTECT — selo **aplicado** |
| `stamp_retired` | CharField(30) | blank — nº selo retirado |
| `signature` | TextField | blank — dataURL PNG canvas |
| `client_signer_name` | CharField(120) | blank — nome da pessoa que assinou a O.S. |
| `signed_at` | DateTimeField | null |
| `status` | CharField(20) | `DRAFT`, `COMPLETED`, `CANCELED` — default `COMPLETED` (MVP); `DRAFT` em v1.2 |

**Numeração sequencial por tenant (justificativa):**
- Campo `number` + incremento com lock via `service_orders/services.py::next_os_number(tenant)`.
- Formatação de exibição: `str(number).zfill(5)` → `00042`.
- **Constraints:** `UniqueConstraint(['tenant', 'number'], name='uniq_os_number_per_tenant')`.
- Justificativa: numeração fiscal/regulatória contínua por empresa; sequência com lock evita `Max()` em alta concorrência.

**Índices:** `(tenant, -created_at)`, `(tenant, created_by)`, `(tenant, client)`, `(tenant, performed_at)`.

#### `service_orders.ServicePart` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `service_order` | FK ServiceOrder | CASCADE, `related_name='parts'` |
| `code` | CharField(30) | blank |
| `quantity` | PositiveIntegerField | default 1, > 0 |
| `serial_number` | CharField(64) | blank |
| `description` | CharField(200) | |
| `exchange_base` | CharField(100) | **base de troca**, blank |

#### `service_orders.ServiceTime` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `service_order` | FK ServiceOrder | CASCADE, `related_name='times'` |
| `day` | DateField | |
| `start_time` | TimeField | blank |
| `stop_time` | TimeField | blank |
| `total_hours` | DecimalField(5,2) | ≥ 0 |
| `car` | DecimalField(5,2) | horas de carro, default 0 |
| `truck` | DecimalField(5,2) | horas de caminhão, default 0 |

#### `assets.Scale` — extensão para classificação metrológica rodoviária

| Campo | Tipo | Restrições |
|---|---|---|
| `scale_type` | CharField(20) | nullable/blank; choices `RODOVIARIA`, `FERROVIARIA`, `RODOFERROVIARIA`; label pt-BR; vazio para os demais tipos |
| `minimum_capacity_kg` | DecimalField(10,2) | `null/blank`; > 0 quando informado; unidade kg |
| `metrological_class` | CharField(10) | `blank`; classe exibida no relatório |

Os nomes finais devem seguir os nomes canônicos de `assets.Scale` em §7.2. Como
o código atual ainda usa o modelo legado `service_order.Scale` e campos textuais
de capacidade/divisão, a migração deverá preservar os valores existentes e
normalizá-los em etapa separada, sem conversão silenciosa de unidades.

#### `service_orders.TechnicalReport` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `service_order` | OneToOneField ServiceOrder | `CASCADE`; único; relatório da visita |
| `status` | CharField(20) | `DRAFT`, `COMPLETED`, `CANCELED`; default `DRAFT` |
| `owner_code` | CharField(40) | blank; código do proprietário |
| `service_type` | CharField(20) | `REPARO`, `REFORMA`, `INSTRUMENTO_NOVO` |
| `standard_weight_certificate` | CharField(80) | blank |
| `truck_plate_snapshot` | CharField(20) | snapshot da placa do caminhão informada nos tempos da O.S. |
| `scale_type_snapshot` | CharField(20) | obrigatório ao concluir; cópia de `Scale.scale_type` |
| `minimum_capacity_snapshot_kg` | DecimalField(10,2) | obrigatório quando o cadastro possuir valor |
| `metrological_class_snapshot` | CharField(10) | cópia da classe na conclusão |
| `capacity_snapshot` / `division_snapshot` | valores do cadastro | snapshot dos valores legados, sem conversão silenciosa |
| `stamp_applied_snapshot` / `stamp_retired_snapshot` | CharField | snapshot dos selos da O.S. |
| `technician_name` | CharField(120) | snapshot de `ServiceOrder.user`; somente leitura |
| `completed_at`, `canceled_at` | DateTimeField | null; preenchidos pela transição de estado |
| `canceled_reason` | TextField | obrigatório ao cancelar |
| `observation` | TextField | blank |

**Constraints:** `UniqueConstraint(['tenant', 'service_order'],
`uniq_report_tenant_service_order`)`, além do `OneToOneField`.

#### `service_orders.TechnicalTestMeasurement` (ou tabelas especializadas)

O desenho preferencial é uma tabela especializada por ensaio para manter
constraints simples e relatórios previsíveis: `FidelityTest` (3 posições),
`EccentricityTest` (6) e `WeighingTest` (22).

| Campo | Tipo | Restrições |
|---|---|---|
| `technical_report` | FK TechnicalReport | `CASCADE`, tenant herdado do relatório |
| `sequence` | PositiveSmallIntegerField | único por relatório/ensaio; faixa fixa do formulário |
| `load_kg`, `indication_kg`, `error_kg`, `ema_kg` | DecimalField(12,3) | `null` em rascunho; unidade kg explícita; `error_kg = indication_kg - load_kg` |

`EccentricityTest` acrescenta `applied_load_kg` no cabeçalho do conjunto, não
em cada linha, reproduzindo o campo “CARGA APLICADA” do PDF.

`error_kg` é calculado pelo backend e exibido como somente leitura. O técnico
preenche carga e indicação; não existe um segundo campo manual para erro.

#### `ai.ChatSession` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `user` | FK User | CASCADE, `related_name='ai_sessions'` |
| `title` | CharField(200) | blank, auto-gerado no 1º turno |
| `is_active` | BooleanField | default True |
| `model_provider` | CharField(30) | default de settings; null = global |
| `model_name` | CharField(80) | override por sessão |

#### `ai.ChatMessage` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `session` | FK ChatSession | CASCADE, `related_name='messages'` |
| `role` | CharField(10) | `user`, `assistant`, `system`, `tool` |
| `content` | TextField | |
| `tool_calls` | JSONField | null — trace de tools |
| `token_prompt` | IntegerField | default 0 |
| `token_completion` | IntegerField | default 0 |
| `latency_ms` | IntegerField | null |

#### `ai.SourceDocument` (herda TenantScopedModel) — corpus RAG

| Campo | Tipo | Restrições |
|---|---|---|
| `title` | CharField(200) | |
| `content` | TextField | texto limpo |
| `doc_type` | CharField(30) | `MANUAL`, `NORM`, `TEMPLATE`, `POLICY` |
| `file` | FileField | optional upload |
| `chunk` | TextField | chunk versionado |
| `embedding` | VectorField(dim=1536) | **pgvector** |
| `content_hash` | CharField(64) | unique por tenant → **dedup / cache de embedding** |
| `is_active` | BooleanField | |

**Constraints:** `UniqueConstraint(['tenant', 'content_hash'], name='uniq_source_hash_per_tenant')`.
**Índice HNSW/IVFFlat:** `embedding` (cosine ops).

**Justificativa pgvector:** banco único (backup/ACID/tenancy iguais), custo zero de infra extra; 1536 dim = `text-embedding-3-small` (default) com coluna upgradable via migração para 3072 se trocar de modelo — dim encapsulada em settings.

#### `ai.TokenUsage` (herda TenantScopedModel)

| Campo | Tipo |
|---|---|
| `session` | FK ChatSession, null |
| `user` | FK User, PROTECT |
| `provider`, `model_name` | CharField |
| `prompt_tokens`, `completion_tokens` | IntegerField |
| `cached_tokens` | IntegerField default 0 |
| `cost_usd` | DecimalField(12,6) default 0 |

#### `ai.SemanticCache` (herda TenantScopedModel)

| Campo | Tipo | Restrições |
|---|---|---|
| `question_normalized` | CharField(500) | hash normalizado (lower, sem acento) |
| `question_embedding` | VectorField(1536) | |
| `answer` | TextField | |
| `model_name` | CharField(80) | cache é por modelo |
| `hit_count` | IntegerField | default 0 |
| `expires_at` | DateTimeField | TTL 7 dias |

**Justificativa do cache:** reduz custo/tokens em perguntas repetitivas operacionais ("o que é E(kg)?", "como imprimir a O.S.?") mantendo respostas frescas para dados vivos (O.S.) — **cache só para intents estáticos/RAG**, nunca para queries factuais sobre O.S. sem invalidação.

### 7.3 Diagrama ER

```mermaid
erDiagram
  Tenant ||--o{ User : has
  Tenant ||--o| Subscription : has
  Plan ||--o{ Subscription : plans
  Tenant ||--o{ Client : owns
  Tenant ||--o{ Scale : owns
  Client ||--o{ Scale : owns
  Unit ||--o{ Scale : measures
  Tenant ||--o{ ServiceOrder : owns
  Client ||--o{ ServiceOrder : receives
  Scale ||--o{ ServiceOrder : targets
  User ||--o{ ServiceOrder : authors
  ServiceOrder ||--o| TechnicalReport : extends
  TechnicalReport ||--o{ FidelityTest : measures
  TechnicalReport ||--o{ EccentricityTest : measures
  TechnicalReport ||--o{ WeighingTest : measures
  ServiceOrder ||--o{ ServicePart : has
  ServiceOrder ||--o{ ServiceTime : has
  Tenant ||--o{ Stamp : owns
  Stamp ||--o{ StampDelivery : delivered_as
  User ||--o{ StampDelivery : receives
  ServiceOrder }o--|| Stamp : applies
  StampDelivery }o--o| ServiceOrder : used_on
  Tenant ||--o{ ChatSession : owns
  User ||--o{ ChatSession : opens
  ChatSession ||--o{ ChatMessage : contains
  Tenant ||--o{ SourceDocument : indexes
  Tenant ||--o{ TokenUsage : accrues
  Tenant ||--o{ SemanticCache : caches
```

---

## 8. Especificação de Endpoints/Views

**Convenção:** CBV (`LoginRequiredMixin` + mixins de role + `TenantRequiredMixin`), templates server-side, mensagens Django em pt-BR, POST sempre com CSRF.

### 8.1 Autenticação (`accounts`)

| Rota | Método | View (CBV/fn) | Permissão | Template | Observação |
|---|---|---|---|---|---|
| `/auth/login/` | GET/POST | `LoginView` (django.contrib.auth adaptado) | anônimo | `accounts/login.html` | login por email; redireciona `/app/` |
| `/auth/logout/` | POST | `LogoutView` | autenticado | — | |
| `/auth/convite/<token>/` | GET/POST | `InviteAcceptView` | anônimo (token válido) | `accounts/invite.html` | define senha, aceita termos |

### 8.2 Painel (`core`)

| Rota | Método | View | Permissão | Template |
|---|---|---|---|---|
| `/app/` | GET | `HomeView(TemplateView)` | autenticado | `home.html` — atalhos O.S./Clientes/Balanças + chat IA |
| `/perfil/` | GET/POST | `ProfileUpdateView` | autenticado | `profile.html` |

### 8.3 Clientes (`clients`)

| Rota | Método | View | Permissão | Observação |
|---|---|---|---|---|
| `/clientes/` | GET | `ClientListView(ListView)` | autenticado | busca `?q=` CNPJ (servidor) + filtro client-side |
| `/clientes/novo/` | GET/POST | `ClientCreateView(CreateView)` | `ADMIN`/`STAFF` | valida doc duplicado no tenant |
| `/clientes/<pk>/` | GET | `ClientDetailView(DetailView)` | autenticado | lista balanças + busca série |
| `/clientes/<pk>/editar/` | GET/POST | `ClientUpdateView(UpdateView)` | `ADMIN`/`STAFF` | |
| `/clientes/buscar/` | GET | `ClientSearchView(ListView)` | autenticado | tela de busca por CNPJ para gerar O.S. |

### 8.4 Balanças (`assets`)

| Rota | Método | View | Permissão | Observação |
|---|---|---|---|---|
| `/balancas/` | GET | `ScaleListView` | autenticado | |
| `/balancas/nova/` | GET/POST | `ScaleCreateView` | `ADMIN`/`STAFF` | select2 proprietário; série única por cliente |
| `/balancas/<pk>/` | GET | `ScaleDetailView` | autenticado | |
| `/balancas/<pk>/editar/` | GET/POST | `ScaleUpdateView` | `ADMIN`/`STAFF` | |
| `/balancas/<pk>/excluir/` | GET/POST | `ScaleDeleteView(DeleteView)` | `ADMIN` | confirmação; PROTECT se houver O.S. |
| `/balancas/buscar/` | GET | `ScaleSearchView` | autenticado | por nº de série |
| `/select2/` | GET | django-select2 | autenticado | autocomplete AJAX + cache |

### 8.5 Ordens de Serviço (`service_orders`)

| Rota | Método | View | Permissão | Observação |
|---|---|---|---|---|
| `/os/nova/<int:client_id>/<int:scale_id>/` | GET/POST | `ServiceOrderCreateView(View)` | autenticado | form + 2 formsets; só selos do técnico `AVAILABLE`; consome selo na transação; assinatura no POST |
| `/os/` | GET | `ServiceOrderListView(ListView)` | autenticado | não-admin: filtra `created_by=request.user`; busca `q` + `date_from/date_to` |
| `/os/<int:pk>/` | GET | `ServiceOrderDetailView(DetailView)` | autenticado | documento A4; escopo por tenant; técnico só a própria (ou 404) |
| `/os/<int:pk>/editar/` | GET/POST | `ServiceOrderUpdateView` | `STAFF`/`ADMIN` | formsets editáveis; selo não devolvido automaticamente (devolver via admin — documentar) |
| `/os/<int:pk>/excluir/` | GET/POST | `ServiceOrderDeleteView` | `ADMIN` | devolve selo para `AVAILABLE` do técnico via service |
| `/os/<int:pk>/imprimir/` | GET | `ServiceOrderPrintView(DetailView)` | autenticado | template `print` sem chrome UI |

**Formulário da O.S. — blocos:**
01 Cliente (read-only) · 02 Balança (read-only) · 03 Serviços (8 checkboxes + selo aplicado/retirado + observações + data/hora) · 04 Informações complementares (INMETRO ano, instalação nova, hospedagem, refeição) · 05 Peças (formset) · 06 Tempo de serviço (formset) · Assinatura canvas (`SignaturePad`, `touch-action: none`).

### 8.6 Selo / Admin operacional (`stamps`)

| Rota | Método | View | Permissão | Observação |
|---|---|---|---|---|
| `/selos/` | GET | `StampListView` | `ADMIN` | status + técnico atual |
| `/selos/distribuir/` | GET/POST | `StampDeliveryCreateView` | `ADMIN` | só stamps `AVAILABLE`; cria Delivery |
| `/selos/<pk>/danificar/` | POST | `StampDamageView` | `ADMIN` | transição `DAMAGED` |

(Complementar: Django Admin para seeds e suporte.)

### 8.7 Usuários (`accounts` / `tenants`)

| Rota | Método | View | Permissão |
|---|---|---|---|
| `/usuarios/` | GET | `UserListView` | `ADMIN` (tenant) |
| `/usuarios/novo/` | GET/POST | `UserInviteCreateView` | `ADMIN` |
| `/usuarios/<pk>/editar/` | GET/POST | `UserUpdateView` | `ADMIN` |
| `/empresa/` | GET/POST | `TenantUpdateView` | `ADMIN` |

### 8.8 IA (`ai`) — v1.1

| Rota | Método | View | Permissão | Observação |
|---|---|---|---|---|
| `/ia/` | GET | `ChatIndexView` | autenticado | lista sessões do usuário |
| `/ia/sessao/nova/` | POST | `ChatSessionCreateView` | autenticado | |
| `/ia/sessao/<pk>/` | GET | `ChatDetailView` | dono da sessão + tenant | |
| `/ia/sessao/<pk>/mensagem/` | POST | `ChatMessageSendView` | dono | orquestra LangGraph; resposta **streaming** (SSE/chunked) |
| `/ia/fontes/` | GET/POST | `SourceDocumentListView/Create` | `ADMIN` | upload corpus RAG |
| `/ia/config/` | GET/POST | `AIConfigUpdateView` | `ADMIN` | provider/model em runtime |
| `/api/ia/sessao/<pk>/eventos/` | GET | `ChatStreamView` | dono | SSE |

### 8.9 Permissões (resumo matricial)

| Recurso | TECHNICIAN | STAFF | ADMIN |
|---|---|---|---|
| Ver suas O.S. | ✅ | ✅ | ✅ |
| Ver todas O.S. do tenant | ❌ | ✅ | ✅ |
| Criar O.S. | ✅ | ✅ | ✅ |
| Editar O.S. | ❌ | ✅ | ✅ |
| Excluir O.S. | ❌ | ❌ | ✅ |
| CRUD clientes/balanças | ❌ | ✅ | ✅ |
| Distribuir selos | ❌ | ❌ | ✅ |
| Gestão de usuários/empresa/planos | ❌ | ❌ | ✅ |
| IA (chat) | ✅ (limitado a seus dados) | ✅ | ✅ |
| Config provider IA / corpus | ❌ | ❌ | ✅ |
| Criar relatório técnico da própria O.S. rodoviária | ✅ | ✅ | ✅ |
| Editar relatório técnico concluído | ❌ | ✅ | ✅ |
| Imprimir relatório técnico do tenant | ✅ própria O.S. | ✅ | ✅ |

**Implementação:** `core/permissions.py` → `RoleRequiredMixin(roles=('STAFF','ADMIN'))`; teste automatizado obrigatório para cada célula da matriz.

### 8.10 Relatório técnico rodoviário (`service_orders`)

| Rota | Método | View | Permissão | Observação |
|---|---|---|---|---|
| `/os/<int:pk>/relatorio-tecnico/` | GET/POST | `TechnicalReportView` | autenticado com escopo da O.S. | cria ou edita o relatório 1:1; somente escala classificada em uma das três opções; POST com CSRF e formsets dos ensaios |
| `/os/<int:pk>/relatorio-tecnico/imprimir/` | GET | `TechnicalReportPrintView` | autenticado com escopo da O.S. | exige relatório concluível; documento A4 sem chrome; impressão via `window.print()` no MVP |

**Regras de fluxo:**

- `TECHNICIAN` pode criar o relatório da própria O.S. durante o atendimento, mas
  não pode editar relatório concluído.
- `STAFF` e `ADMIN` podem revisar/editar relatórios do tenant; cancelamento e
  reabertura exigem `ADMIN` ou política explícita de `STAFF` documentada.
- O queryset deve filtrar tenant antes do `pk` e aplicar o mesmo escopo técnico
  usado pela O.S.; nunca confiar apenas no parâmetro da URL.
- A view deve usar `transaction.atomic()` para salvar cabeçalho e todos os
  ensaios. Falha em uma linha não pode deixar relatório parcial.
- A ação de impressão não cria nem altera dados e deve carregar o cabeçalho do
  tenant com logo e registro IPEM/PR.

---

## 9. Integração com IA

### 9.1 Frameworks e Justificativa

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Orquestração de agentes | **LangGraph** | Grafo explícito router→tools/RAG→síntese, checkpointer por sessão, retomada e observabilidade por nó. |
| Conectores/loaders | **LangChain** | Utils de prompts, splitters de documento, integrações de providers maduras. |
| Embeddings + vetor | **pgvector** no PostgreSQL | Shared schema mantido; sem novo serviço; tenant filtering natural. |
| Modelo default | OpenAI (chat + `text-embedding-3-small`) configurável | Qualidade/latência; troca em runtime para Anthropic etc. |
| Streaming | SSE + templates JS | UX de chat sem infra de WebSocket (justificativa: uWSGI/Nginx simples). |

### 9.2 Casos de Uso de IA habilitados

1. **Consulta operacional factual** (tools): listar/resumir O.S., contar por filtro, dados de cliente/balança/selo — sempre com `tenant_id` fixado no filtro da tool.
2. **RAG procedimental:** perguntas sobre normas/manuais carregados pelo tenant → top-k chunks com citação `[[fonte: título]]`.
3. **Redação assistida:** rascunho de observações de laudo a partir dos serviços marcados (input: objeto `ServiceOrder` serializado).
4. **Indicadores em linguagem natural:** "quantas O.S. com selo danificado no mês?" → tool `aggregate_service_orders`.

### 9.3 Ferramentas (tools) — contrato

```python
# ai/tools/registry.py (referência de assinatura)
TOOLS = {
    'search_service_orders': search_service_orders,   # filtros: client_cnpj, date range, service flags
    'get_service_order': get_service_order,           # args: uuid ou number
    'get_client': get_client,
    'list_scale_history': list_scale_history,
    'aggregate_service_orders': aggregate_service_orders,
    'draft_service_report': draft_service_report,
}
```

Regras:
- Toda tool recebe `tenant_id` explícito injetado pelo runtime (**nunca** vindo do LLM).
- Tools são `StructuredTool` com Pydantic schema (entrada/saída tipadas).
- Resultados limitados (`limit ≤ 50`, paginação) para proteger janela de contexto.
- Tool failure → nó de tratamento devolve mensagem amigável em pt-BR, sem stack trace.

### 9.4 Gestão de Contexto e Histórico

| Política | Regra |
|---|---|
| Histórico | Últimos N turnos cabendo em **~60% da janela** do modelo (config `AI_HISTORY_MAX_TOKENS`, default 6000). |
| Truncamento | FIFO por mensagem; mensagens antigas viram **resumo** (`summary` system message) quando excedentes — nó `condense_history` no grafo. |
| Sessão | `ChatSession` + LangGraph `checkpointer` (PostgreSQL) → retomada e multi-device. |
| System prompt | Base fixa (papel: assistente Aferix, pt-BR, só dados do tenant) + perfil (`role`, nome, tenant) + top-k RAG quando aplicável. |
| PII | Ferramentas mascaram documento completo em logs (`CNPJ **1234/56**`). |

### 9.5 Cache para Otimização de Tokens

1. **Cache semântico** (`ai.SemanticCache`): similaridade cos ≥ 0.95 e mesmo `model_name` → resposta reutilizada (apenas para intents estáticos / RAG; **nunca** para tools factuais).
2. **Cache exato** (Django cache): hash SHA-256 de `(tenant, normalized_question, model)` → hit imediato.
3. **Embedding cache:** `SourceDocument.content_hash` evita re-embed de chunk inalterado.
4. **Prompt prefix caching:** system prompt estável por sessão para habilitar caching do provedor quando suportado.
5. Métricas: `TokenUsage.cached_tokens` por request.

### 9.6 Troca de Modelo em Runtime + Multi-Provider

```mermaid
flowchart LR
  CFG[AIConfig — tenant/global no BD ou settings] --> FAC[LLMFactory]
  FAC -->|provider=openai| O[ChatOpenAI]
  FAC -->|provider=anthropic| A[ChatAnthropic]
  FAC -->|provider=mock| M[MockLLM testes]
  FAC --> EM[EmbeddingsFactory — mesmo padrão]
```

- `ai/providers/base.py`: `BaseChatProvider.complete(messages, **kwargs) -> LLMResult`.
- Ordem de resolução: **override da sessão → AIConfig do tenant → settings global → default**.
- Secrets **somente** em variáveis de ambiente (§15); o BD guarda apenas o *nome* do provedor/modelo.
- Estrutura extensível: novo provedor = implementar base + registrar no factory + settings da chave — sem tocar no grafo.
- Circuit breaker simples: X falhas consecutivas → fallback para `mock`/segundo provedor + flag na UI.

### 9.7 Isolamento Multi-Tenant na IA (crítico)

- `TenantContext` injetado no `Configurable` do LangGraph.
- Retrieval: `WHERE tenant_id = %s` obrigatório antes do `ORDER BY embedding <=> %s`.
- Tools: filtro obrigatório; **testes de vazamento** (pergunta do tenant A não retorna dados do B) — suíte obrigatória.

---

## 10. Design System

### 10.1 Referência

> **Arquivo único de verdade:** `@design_system/design-system.html` (repositório).

Todas as cores, tipografias, espaçamentos, raios, sombras e componentes (botões, tabelas, cards, formulários, sidebar, modais, toasts, chat) **devem ser referenciados desse arquivo**. Nenhum CSS de tela inventa token próprio.

### 10.2 Regras

| # | Regra |
|---|---|
| DS-01 | Usar apenas tokens (CSS variables) definidos no design system: `--color-primary`, `--color-surface`, `--font-sans`, `--space-4`, etc. |
| DS-02 | Componentes base: Bootstrap 5 **customizado pelos tokens**, não classes utilitárias com cores fixas arbitrárias. |
| DS-03 | Sidebar com acordeão e nav items já especificados no DS — reutilizar markup. |
| DS-04 | Estados: `default / hover / focus-visible / disabled / error / success` para todo controle interativo; foco visível (a11y). |
| DS-05 | Tipografia: escala do DS (ex.: 14/16/20/24/32); nada de font-size inline. |
| DS-06 | Ícones: Bootstrap Icons (já no produto). |
| DS-07 | Modo de impressão (O.S. A4) usa layout próprio **mas** tipografia/cabeçalho coerentes com o DS. |
| DS-08 | Interface 100% **pt-BR**; código em inglês. |
| DS-09 | Responsivo mobile-first para tablet de campo (alvo mínimo viewport 768px). |
| DS-10 | Tema claro no MVP; tokens preparados para dark (variáveis), escopo futuro. |

### 10.3 Exemplo de token (ilustrativo — prevalece o arquivo do DS)

```css
/* static/css/tokens.css — espelha @design_system/design-system.html */
:root {
  --color-primary: #0d6efd;
  --color-surface: #ffffff;
  --color-border: #dee2e6;
  --font-sans: 'Inter', system-ui, sans-serif;
  --space-4: 1rem;
  --radius-md: 0.5rem;
}
```

### 10.4 Aplicação no relatório técnico

- O formulário usa os tokens do arquivo `static/css/tokens.css`; não criar
  cores, espaçamentos, raios ou sombras ad hoc em template.
- A tela é mobile-first e deve ser confortável em tablet com viewport mínimo de
  768px, priorizando entrada rápida das 31 medições.
- Tabelas de ensaio devem ter cabeçalho persistente, unidade explícita `(kg)` e
  estado de erro por célula sem depender apenas de cor.
- A impressão é uma composição A4 própria, mas mantém tipografia e cabeçalho
  coerentes com o design system. Elementos de navegação e ações são ocultados
  em `@media print`.
- O texto visível permanece em pt-BR; nomes de classes, rotas, modelos e
  identificadores permanecem em inglês.

---

## 11. Requisitos Não-Funcionais

### 11.1 Segurança

| ID | Requisito | Aceite |
|---|---|---|
| SEC-01 | Isolamento multi-tenant em todas as queries de domínio | Testes automatizados: usuário do tenant A nunca lê/escreve dados do B (suite `test_tenant_isolation.py`) |
| SEC-02 | Auth por email, senha com `PASSWORD_HASHERS` Django moderno, sessão segura | `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `Secure`/`HttpOnly`/`SameSite=Lax` |
| SEC-03 | RBAC por role conforme matriz §8.9 | Teste por célula da matriz (403 esperado) |
| SEC-04 | Proteção CSRF em todos os POST; `TRUSTED_ORIGINS` explícitos por ambiente | |
| SEC-05 | Uploads: validação de MIME/extensão/tamanho (logo ≤ 2 MB; corpus PDF/TXT ≤ 10 MB) | Pillow `verify()`; path aleatório em `media/` |
| SEC-06 | Segredos só em env; **nunca** commitados; `.env` no `.gitignore` | |
| SEC-07 | Rate limiting em login e endpoints de IA | login: 5 tentativas/5 min/IP |
| SEC-08 | Logs sem PII plena (documento mascarado); auditoria de ações críticas (distribuição de selo, exclusão de O.S.) em `AuditLog` (v1.2) | |
| SEC-09 | Tools/RAG com filtro de tenant obrigatório + testes anti-vazamento | |
| SEC-10 | Conformidade com LGPD (§11.4) | |
| SEC-11 | Relatório técnico isolado por tenant e O.S. | Teste A/B retorna 404/403 para leitura e escrita cruzadas; technician não acessa O.S. de outro usuário |
| SEC-12 | Assinaturas do relatório tratadas como dado pessoal | Reutilizar assinatura da O.S.; não duplicar em logs; aplicar retenção e anonimização previstas em §11.4 |

### 11.2 Performance

| ID | Requisito | Alvo |
|---|---|---|
| PER-01 | TTFB das telas de lista autenticadas | < 500 ms p95 |
| PER-02 | Query counts em listagens | ≤ 10 queries por request (select_related/prefetch) |
| PER-03 | Índices obrigatórios | §7.2; `EXPLAIN` sem seq scan em tabelas de O.S. acima de 100k linhas |
| PER-04 | Cache | select2 e home com cache (DatabaseCache ou Redis se `REDIS_URL`) |
| PER-05 | Impressão A4 | sem requisições extras bloqueantes; assets inline mínimos |
| PER-08 | Relatório técnico | Formulário e impressão com no máximo 10 queries adicionais usando `select_related/prefetch_related`; impressão sem chamadas externas bloqueantes |
| PER-06 | IA | 1º token streaming < 2 s p95 com cache miss moderado |
| PER-07 | uWSGI | ≥ 4 workers configuráveis; timeouts; `max-requests` para reciclagem |

### 11.3 Escalabilidade

- Stateless app (sessão em DB ou cache) → horizontal por workers/máquinas atrás do Nginx.
- PostgreSQL primeiro (vertical + read replica futuro); particionamento de `ServiceOrder` por `tenant` só se necessário.
- Fila para jobs pesados (embeddings em lote, envio de e-mails) em v1.2: **Redis + Celery** (justificativa: mantém request cycles livres; só introduce se houver job > 500 ms).
- Multi-tenant shared schema escala bem até ~10³ tenants mid-size com índices + particionamento lógico opcional (RLS).

### 11.4 LGPD

| Item | Implementação |
|---|---|
| Base legal | Execução de contrato (prestação de serviço de O.S.); interesse legítimo para logs de segurança |
| Papéis | Tenant = **controlador** dos dados de clientes finais; Aferix = **operador** |
| Direitos do titular | v1.2: fluxo de exportação/anonimização de `Client`/assinatura via ADMIN do tenant |
| Dados sensíveis | Assinatura gráfica é dado pessoal → criptografia em repouso recomendada (v1.2: `signature` com server-side key ou hash+URL expirável) |
| Retenção | Política por plano; O.S. mantidas ≥ 5 anos (boa prática fiscal/regulatória — configurável) |
| DPA | Anexo contratual no onboarding enterprise |
| Subprocessor IA | Opt-out por tenant (`ai_enabled=False`) e providers com DPA; documentar em /privacidade |

### 11.5 Qualidade

- Lint: `ruff` (PEP 8) + format alinhado; type-check `mypy` gradual (models/services primeiro).
- Testes: Django TestCase, meta **≥ 80%** em `service_orders`, `stamps`, `tenants`, `ai` (tools/isolamento).
- CI: ruff → mypy (tolerante) → `manage.py test --settings=app.settings.test` → build Docker.
- Idioma: `LANGUAGE_CODE='pt-br'`, `TIME_ZONE='America/Sao_Paulo'`.

---

## 12. Planos e Monetização

### 12.1 Quem assina a plataforma

**A empresa prestadora de serviço (tenant)** assina. Não há assinatura de cliente final (da O.S.). O plano é por tenant, com limite de **assentos (técnicos+staff)**, **O.S./mês** e **créditos de IA**.

### 12.2 Estrutura de planos

| Plano | Preço (sugestão) | Técnicos (assentos) | O.S./mês | Créditos IA/mês | Assinatura obrigatória | Suporte |
|---|---|---:|---:|---:|---|---|
| **Trial** 14 dias | R$ 0 | 3 | 30 | 50 | não | email |
| **Básico** | R$ 149/mês | 3 | 100 | 200 | não | email |
| **Profissional** | R$ 349/mês | 10 | 500 | 1.000 | sim | prioritário |
| **Enterprise** | sob consulta | ilimitado | ilimitado | dedicado | sim | SLA + onboarding |

> Preços são **baseline**; validar com piloto. Cobrança via gateway (v1.2 — Stripe/PagBank); MVP: `Plan` seed + limites soft manualmente.

### 12.3 Relações entre entidades (billing)

```mermaid
flowchart LR
  Tenant -->|1:1| Subscription -->|N:1| Plan
  Tenant -->|usage| Meter[Contadores: OS/mês, assentos, créditos IA]
  Meter --> Gate{Abaixo do limite?}
  Gate -->|sim| OK[Permite ação]
  Gate -->|não| Soft[Bloqueio suave + CTA upgrade]
  Soft -->|Enterprise hard| Hard[Bloqueio de criação]
```

### 12.4 Política de limites

- **Soft block:** excedeu O.S./mês → aviso persistente + allow-read + criação bloqueada no dia seguinte (evita travar campo no meio do turno) — decisão de UX; admin recebe banner.
- **Créditos IA:** 1 crédito ≈ 1 turno de chat padrão (calibrar com logs `TokenUsage`).
- Upgrade imediato prorrogando período; downgrade no fim do ciclo.

---

## 13. Roadmap de Desenvolvimento em Fases

> Estimas em semanas de 1 dev full-time sênior + apoio parcial; ajustar com velocity real.

> **Nota v1.1 (sem clientes reais):** **não existe Fase 0 de migração de produção** — os dados atuais são de teste. A Fase 1 é a **fundação multi-tenant from scratch sobre o schema legado**, a ser concluída **antes** da aquisição dos primeiros clientes. O ambiente EC2/domínio próprio permanece como produção; recomenda-se subir um **staging** novo (branch + banco separado) para desenvolver a Fase 1 sem tocar na instância atual.

### Fase 1 — MVP Multi-Tenant (Semana 1–8)

> **Objetivo:** transformar o sistema empresa única (EC2, sem clientes) em fundação SaaS multi-tenant, antes do 1º cliente.

- [x] **Sprint 1.0 — Ambiente e baseline (Semana 0–1)**
  - [ ] Staging novo (EC2 ou AMI/branch + banco separado) com cópia do código atual de produção. *(pendente de provisionamento na AWS)*
  - [ ] Snapshot do banco de produção (mesmo sem clientes reais) + runbook de rollback. *(runbook criado em `docs/runbook_snapshot_rollback.md`; `pg_dump` do EC2 pendente de acesso)*
  - [x] Gap analysis: models/views legados vs. §§7–8 deste PRD (o que manter, renomear, recriar). *(`docs/gap_analysis.md`)*
  - [x] Normalização inicial: choices de status em pt-BR → inglês (labels continuam pt-BR).
  - [x] Ajustar `DJANGO_ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` para o **domínio próprio real** (remover ngrok de produção).
  - [x] CI mínima apontando para staging (ruff + testes legados verdes como baseline).
- [x] **Sprint 1.1 — Fundação multi-tenant (Semana 1–2)**
  - [x] Bootstrap do repo: estrutura de apps (§6), `requirements.txt` pinado, `pyproject.toml`, ruff/black/mypy.
  - [x] `core`: `TimeStampedModel`, `TenantScopedModel`, managers (`TenantManager`), mixins de role/tenant.
  - [x] `tenants`: models `Tenant`, `Plan`, `Subscription`; `TenantMiddleware`; settings (`AUTH_USER_MODEL`, middlewares, caches).
  - [x] `accounts`: `User` (email USERNAME_FIELD), `EmailBackend`, migração inicial, login/logout views + templates.
  - [x] Testes: auth por email, middleware coloca `request.tenant`, 403 sem login.
  - [x] CI: ruff + testes no GitHub Actions.
- [x] **Sprint 1.2 — Cadastros (Semana 3–4)**
  - [x] `clients`: model, form com validação `document` único por tenant, CBVs (list/create/detail/update/search).
  - [x] `assets`: `Unit`, `Scale`, form com `ModelSelect2Widget`, validação série única por cliente, CRUD + delete com confirmação.
  - [x] Templates conforme design system; filtros client-side (`filter.js`, `scale_filter.js`).
  - [x] Django Admin registrado para suporte (superuser).
  - [x] Testes: CRUD, duplicidades, isolamento tenant A/B.
- [x] **Sprint 1.3 — Selo e O.S. core (Semana 5–6)**
  - [x] `stamps`: `Stamp`, `StampDelivery`, service de transição com lock; views de listagem/distribuição/danificar.
  - [x] `service_orders`: models completos (OS, Part, Time), `next_os_number` com lock por tenant.
  - [x] Form O.S.: blocos 01–06, formsets dinâmicos, select de selo filtrado por técnico, consumo atômico no save.
  - [x] Assinatura canvas (`SignaturePad`, touch, dataURL) + persistência + exibição.
  - [x] Testes: consumo único de selo concorrência, numeração sem duplicatas, formsets.
- [x] **Sprint 1.4 — Listagem, A4 e permissões (Semana 7–8)**
  - [x] List O.S. com busca/filtro data; escopo técnico vs. admin.
  - [x] Detalhe A4 + CSS print + rota de impressão; cabeçalho da empresa + IPEM/PR.
  - [x] Matriz de permissões completa + testes por célula.
  - [x] Testes de regressão migrados/expandidos da suíte legada (≥ 40 testes).
  - [x] Deploy: Dockerfile + uWSGI + Nginx sample; `.env.example`; smoke test em staging *(staging EC2 pendente de infra AWS)*.
  - [x] **Gate de release MVP:** checklist §13.5 *(itens de QA visual/touch/staging dependem de ambiente físico/AWS)*.

### Fase 2 — v1.1 IA (Semana 9–14)

- [x] **Sprint 2.1 — Infra IA (Semana 9–10)**
  - [x] Instalar `pgvector`; migration `VectorField`; índice HNSW.
  - [x] `ai` models: `ChatSession`, `ChatMessage`, `SourceDocument`, `TokenUsage`, `SemanticCache`.
  - [x] `providers/base.py` + `OpenAIProvider` + `AnthropicProvider` + `MockProvider`; `LLMFactory`; settings/env.
  - [x] `AIConfig` por tenant (tela ADMIN); troca de modelo em runtime.
  - [x] Testes: factory, fallback, resolução de ordem (sessão → tenant → global).
- [x] **Sprint 2.2 — Grafo e tools (Semana 11–12)**
  - [x] LangGraph: nós `router`, `tools`, `retrieve`, `condense_history`, `synthesize`, `persist`; checkpointer PG.
  - [x] Tools tipadas com `tenant_id` injetado (lista §9.3); rate limit por usuário.
  - [x] Gestão de contexto: truncamento + resumo; system prompt estável.
  - [x] Cache semântico + exato; gravação em `TokenUsage`.
  - [x] Testes: ferramentas com dados corretos; **anti-vazamento cross-tenant**; cache hit; resumo de histórico.
- [x] **Sprint 2.3 — UI de chat + RAG (Semana 13–14)**
  - [x] Telas `/ia/` (sessões, thread, streaming SSE, markdown seguro).
  - [x] Upload/listagem/deleção de `SourceDocument` + pipeline de chunk+embed (management command `embed_sources`).
  - [x] Retriever com filtro tenant + citação de fonte na resposta.
  - [x] Métricas no ADMIN (tokens/dia por tenant).
  - [x] Testes de E2E do chat (client de teste com provider mock).

### Fase 3 — v1.2 Monetização e Operação (Semana 15–20)

- [x] **Sprint 3.1 — Planos e limites (Semana 15–16)**
  - [x] Seed idempotente de planos; `Subscription` vigente/trial; contadores por ciclo (O.S., assentos, créditos IA).
  - [x] `check_plan_limit` + bloqueio na criação de O.S./uso de IA; banner de limite com acesso ao faturamento.
  - [x] Tela de billing somente leitura, com plano, período, consumo e planos disponíveis (gateway depois).
  - [x] Testes de seed, limites, isolamento/contagem e bloqueios (8 testes dedicados; suíte total: 155 testes verdes).
- [x] **Sprint 3.2 — Operação (Semana 17–18)**
  - [x] Dashboard de indicadores (`/dashboard/`, STAFF/ADMIN): O.S. no ciclo, por status, por técnico e tempo médio apontado; `status` da O.S. adicionado (PRD §7.2, migração 0041).
  - [x] Export CSV (`/export/os/?tipo=os|pecas|tempos`) com escopo tenant + técnico (UTF-8 BOM, ;).
  - [x] E-mails transacionais via `EMAIL_BACKEND` (console/SMTP): convite (leve 72h), O.S. assinada (admins do tenant) e limite atingido (throttle 1/dia/recurso).
  - [x] Gestão de usuários do tenant (US-12): lista/convite/edição ADMIN-only com limite de assentos (convite e aceite) e proteção do último ADMIN; aceite em `/convite/<token>/`.
  - [x] Assinatura obrigatória quando `plan.required_signature` no fluxo de emissão.
  - [x] Testes: 24 novos (dashboard/export/assinatura obrigatória/convites/e-mails de limite); suíte total 179 verdes.
- [x] **Sprint 3.3 — LGPD e hardening (Semana 19–20)**
  - [x] `AuditLog` para ações críticas, com mascaramento de documentos, índices por tenant e retenção via `purge_audit_logs`.
  - [x] Exportação/anonimização de dados do titular em `/privacidade/clientes/<pk>/...`, restrita a ADMIN e isolada por tenant.
  - [x] Rate limiting de login por IP, headers de segurança e CSP gradual (`ENABLE_CSP`), além de backup/restore diário documentado em `docs/runbook_snapshot_rollback.md`.
  - [x] Load test leve em `tests/k6/listings.js`; índices de auditoria e consultas de listagem preservados.
  - [x] Testes: auditoria, LGPD, isolamento, retenção, rate limiting e headers; suíte total: 185 verdes.

### Fase 4 — Backlog v1.3+ (não comprometido)

- [ ] PDF nativo assinado com hash de integridade.
- [ ] API REST pública + webhooks.
- [ ] Fila Celery (embeds lote, e-mails, relatórios).
- [ ] PostgreSQL RLS como hardening extra.
- [ ] Assinatura ICP-Brasil (provedor).
- [ ] PWA/offline para campo com sincronização.
- [ ] Multi-idioma (en-US).

### 13.5 Gate de Release MVP (definição de pronto)

- [x] Todos os testes da suíte verdes em CI. *(71 testes OK localmente; workflow em `.github/workflows/ci.yml`)*
- [x] Matriz de permissões coberta por testes. *(PermissionMatrixTests)*
- [x] Teste de isolamento de tenant aprovado. *(TenantIsolationTests A/B)*
- [ ] O.S. impressa bate com layout A4 (qa visual em Chrome/Firefox/Safari). *(rota `/os/<pk>/imprimir/` criada; QA visual pendente)*
- [ ] Assinatura funciona em iPad/Android tablet (touch). *(SignaturePad com `touch-action: none`; validação em dispositivo pendente)*
- [ ] `.env.example` completo e deploy staging ok. *(`.env.example` + Docker/Nginx/uWSGI prontos; staging EC2 pendente de infra AWS)*
- [x] Sem `print`/`TODO`/`pdb` no código; ruff limpo. *(ruff check OK; scan sem ocorrências)*

### Fase 5 — Relatório técnico rodoviário (planejada; após clarificação das solicitações)

> **Objetivo:** digitalizar o formulário de Relatório Técnico fornecido, manter
> a O.S. como fonte dos dados comuns e gerar um documento A4 rastreável apenas
> para balanças rodoviárias. A Sprint 5.1 foi fechada por especificação
> documental; as sprints de implementação e validação em staging permanecem
> desmarcadas.

- [x] **Sprint 5.1 — Fechamento de requisitos e desenho de dados (Semana 21)**
  - [x] Validar documentalmente os nomes, unidades e obrigatoriedade de cada campo do PDF; UAT presencial permanece na Sprint 5.5.
  - [x] Confirmar que classe, capacidade mínima e tipo pertencem ao cadastro permanente e que snapshots regulatórios são congelados na conclusão.
  - [x] Definir estados `DRAFT`, `COMPLETED`, `CANCELED` e regras de reabertura auditada por `ADMIN`.
  - [x] Definir assinatura do técnico obrigatória na conclusão e reutilização da assinatura da O.S. para o proprietário.
  - [x] Registrar ADR `docs/adr/0001-relatorio-tecnico-rodoviario.md` sobre `window.print()` no MVP e PDF nativo/hash em fase posterior.

- [x] **Sprint 5.2 — Modelagem e migração multi-tenant (Semana 22)**
  - [x] Adicionar classificação metrológica da balança preservando dados legados e sem converter unidades silenciosamente.
  - [x] Criar `TechnicalReport` 1:1 com `ServiceOrder`, herdando timestamp e tenant.
  - [x] Criar modelos/tabelas de fidelidade (3), excentricidade (6) e pesagem (22), com `DecimalField(12,3)` em kg e unique por sequência.
  - [x] Criar migration, índice por tenant/O.S. e validação de integridade entre tenant da O.S. e tenant do relatório.
  - [x] Cobrir migration em banco de teste vazio e compatibilidade com balanças/O.S. legadas.

- [x] **Sprint 5.3 — Fluxo de negócio, permissões e auditoria (Semana 23)**
  - [x] Implementar ação contextual somente para `RODOVIARIA` e negar acesso direto a outros tipos.
  - [x] Implementar criação por `TECHNICIAN` na própria O.S. e revisão/edição por `STAFF`/`ADMIN` conforme §8.10.
  - [x] Salvar cabeçalho e 31 medições em uma única transação atômica.
  - [x] Reaproveitar cliente, balança, O.S., selo, assinatura e tenant sem duplicação de dados.
  - [x] Auditar criação, alteração, conclusão, cancelamento, reabertura e impressão com metadados mascarados.
  - [x] Adicionar testes de permissão, tenant A/B, duplicidade 1:1, bloqueio de tipo e persistência das medições.

- [x] **Sprint 5.4 — Formulário responsivo e design system (Semana 24)**
  - [x] Construir o formulário mobile-first para viewport mínimo de 768px usando tokens de `design_system/design-system.html` e `static/css/tokens.css`.
  - [x] Reproduzir as seções do PDF: identificação, tipo, serviço, fidelidade, excentricidade, pesagem, peso padrão, selos e assinaturas.
  - [x] Aplicar estados `default`, `focus-visible`, `error`, `disabled` e `success` em todos os campos editáveis.
  - [x] Validar entrada numérica, unidade kg, casas decimais, sequência fixa e mensagens pt-BR.
  - [x] Integrar captura touch da assinatura do técnico sem substituir a assinatura já coletada na O.S.

- [x] **Sprint 5.5 — Impressão, QA regulatório e release (Semana 25)** *(implementação concluída; UAT visual/staging externo pendente)*
  - [x] Criar visualização A4 sem chrome e com cabeçalho/logo/IPEM do tenant.
  - [ ] Validar impressão em Chrome, Firefox, Safari e PDF do sistema operacional, sem corte das tabelas ou assinaturas.
  - [ ] Comparar visualmente o documento com o PDF de referência e registrar divergências aprovadas.
  - [x] Executar a suíte automatizada (191 testes), `ruff` e `manage.py check --deploy` com ambiente de produção simulado.
  - [ ] Validar retenção mínima de cinco anos, exportação/anonimização LGPD e ausência de PII integral nos logs do novo documento em staging.
  - [ ] Atualizar runbook de rollback, documentação de operação e checklist do gate de release após o UAT.

- [ ] **Sprint 5.6 — FEATURE 2 (bloqueada até especificação)**
  - [ ] Receber descrição, persona, fluxo, modelo de dados, permissões e critérios mensuráveis da FEATURE 2.
  - [ ] Estimar impacto em escopo, sprints, banco, design system, testes e deploy.

- [ ] **Sprint 5.7 — CORREÇÃO 1 (bloqueada até reprodução)**
  - [ ] Receber resultado atual, resultado esperado, passos de reprodução, severidade e ambiente da correção.
  - [ ] Adicionar teste de regressão antes de alterar a implementação.

---

## 14. Estrutura de Diretórios

```text
aferix/
├── manage.py
├── pyproject.toml              # ruff, black, mypy, deps
├── requirements.txt            # pinos: Django~=6.0, psycopg[binary], pgvector,
│                               # langchain, langgraph, openai, anthropic, pillow,
│                               # django-select2, gunicorn/uwsgi, python-dotenv
├── .env.example
├── .gitignore
├── docker-compose.yml          # app + postgres(pgvector) + redis(optional)
├── Dockerfile
├── nginx/
│   └── default.conf
├── uwsgi.ini
├── design_system/
│   └── design-system.html      # fonte da verdade visual
├── docs/
│   ├── prd.md                  # este documento
│   └── adr/                    # decisões de arquitetura
├── app/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── test.py             # SQLite/pgvector local ou DB de teste
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── templates/
│       ├── base.html
│       ├── home.html
│       └── includes/           # sidebar, navbar
├── core/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py               # TimeStampedModel, TenantScopedModel
│   ├── managers.py
│   ├── permissions.py          # RoleRequiredMixin, TenantRequiredMixin
│   ├── middleware.py           # (ou em tenants) TenantMiddleware
│   ├── utils.py                # cnpj, zfill_os_number, mask helpers
│   ├── services.py
│   ├── signals.py
│   └── tests/
├── accounts/
│   ├── __init__.py
│   ├── models.py               # User
│   ├── backends.py             # EmailBackend
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── signals.py
│   ├── templates/accounts/
│   │   ├── login.html
│   │   └── invite.html
│   └── tests.py
├── tenants/
│   ├── __init__.py
│   ├── models.py               # Tenant, Plan, Subscription
│   ├── middleware.py
│   ├── admin.py
│   ├── views.py
│   ├── urls.py
│   ├── services.py             # limites de plano
│   ├── templates/tenants/
│   └── tests.py
├── clients/
│   ├── __init__.py
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── templates/clients/
│   │   ├── client_list.html
│   │   ├── client_form.html
│   │   ├── client_detail.html
│   │   └── client_search.html
│   └── tests.py
├── assets/
│   ├── __init__.py
│   ├── models.py               # Unit, Scale
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── templates/assets/
│   └── tests.py
├── stamps/
│   ├── __init__.py
│   ├── models.py               # Stamp, StampDelivery
│   ├── services.py             # transições com lock
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── signals.py
│   ├── templates/stamps/
│   └── tests.py
├── service_orders/
│   ├── __init__.py
│   ├── models.py               # ServiceOrder, ServicePart, ServiceTime
│   ├── forms.py                # ServiceOrderForm, PartFormset, TimeFormset
│   ├── services.py             # next_os_number, delete_returns_stamp
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── signals.py
│   ├── templates/service_orders/
│   │   ├── service_order_form.html
│   │   ├── service_order_list.html
│   │   ├── service_order_detail.html   # A4 + print CSS
│   │   └── service_order_print.html
│   └── tests.py
├── ai/
│   ├── __init__.py
│   ├── models.py               # ChatSession, ChatMessage, SourceDocument, ...
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── config.py               # AIConfig resolution
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   └── mock_provider.py
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py            # AgentState TypedDict
│   │   ├── nodes.py            # router, tools, retrieve, synthesize...
│   │   └── build.py            # compilador do grafo + checkpointer
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   └── service_order_tools.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── ingest.py           # chunk + embed
│   │   ├── retriever.py
│   │   └── cache.py            # SemanticCache
│   ├── prompts/
│   │   ├── system.py
│   │   └── condense.py
│   ├── services.py             # send_message orchestrator
│   ├── templates/ai/
│   │   ├── chat_index.html
│   │   └── chat_detail.html
│   ├── management/commands/embed_sources.py
│   └── tests/
│       ├── test_tools.py
│       ├── test_isolation.py
│       └── test_cache.py
├── billing/                    # fase 3
│   └── ...
├── static/
│   ├── css/
│   │   ├── tokens.css
│   │   ├── styles.css
│   │   ├── os_detail.css
│   │   └── chat.css
│   ├── js/
│   │   ├── signature.js
│   │   ├── os_form.js
│   │   ├── filter.js
│   │   └── chat.js
│   └── img/
├── templates/                  # se preferir templates globais
├── media/                      # logos, uploads (gitignored)
├── locale/
└── tests_e2e/                  # opcional: Playwright
```

---

## 15. Variáveis de Ambiente

`.env.example`:

```bash
# ---------- Core ----------
DJANGO_SETTINGS_MODULE=app.settings.development
DJANGO_SECRET_KEY=change-me-long-random
DJANGO_DEBUG=True
# Domínio próprio em produção (EC2) — ex.: aferix.com.br,www.aferix.com.br
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
# Produção: CSRF_TRUSTED_ORIGINS=https://seu-dominio.com.br
# Nunca usar ngrok em produção — remover das trusted origins do legado

# ---------- Database (PostgreSQL + pgvector) ----------
DATABASE_URL=postgresql://aferix:aferix@localhost:5432/aferix
# Alternativa local simples:
POSTGRES_DB=aferix
POSTGRES_USER=aferix
POSTGRES_PASSWORD=aferix
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# ---------- Cache ----------
# empty => database cache (django_cache)
REDIS_URL=
CACHE_TTL_SECONDS=300

# ---------- Storage ----------
MEDIA_ROOT=media/
MEDIA_URL=/media/
MAX_UPLOAD_LOGO_MB=2
MAX_UPLOAD_RAG_MB=10

# ---------- Segurança / Sessão ----------
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_AGE=43200          # 12h
LOGIN_URL=/auth/login/

# ---------- Rate limiting ----------
RATELIMIT_LOGIN_PER_MIN=5
RATELIMIT_AI_PER_MIN=20

# ---------- IA — abstração multi-provider ----------
AI_ENABLED=True
AI_DEFAULT_PROVIDER=openai            # openai | anthropic | mock
AI_DEFAULT_MODEL=gpt-5.4-mini         # modelo de chat default
AI_FALLBACK_PROVIDER=mock
AI_DEFAULT_EMBEDDING_MODEL=text-embedding-3-small
AI_EMBEDDING_DIM=1536
AI_HISTORY_MAX_TOKENS=6000
AI_MAX_OUTPUT_TOKENS=1024
AI_TEMPERATURE=0.2
AI_RAG_TOP_K=5
AI_SEMANTIC_CACHE_THRESHOLD=0.95
AI_SEMANTIC_CACHE_TTL_DAYS=7
AI_TOOL_RESULT_LIMIT=50

# Chave usada APENAS pelo provedor selecionado; nunca no BD
OPENAI_API_KEY=
OPENAI_BASE_URL=
ANTHROPIC_API_KEY=

# ---------- Features de fase ----------
AI_STRICT_TENANT_ISOLATION=True      # nunca desligar em produção
ENABLE_PLAN_LIMITS=False             # True na fase 3
ENABLE_AUDIT_LOG=False
CELERY_BROKER_URL=

# ---------- E-mail ----------
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@aferix.com.br

# ---------- Produção ----------
WEB_CONCURRENCY=10
UWSGI_MODULE=app.wsgi:application
```

---

## 16. Riscos e Mitigações

| # | Risco | Impacto | Prob. | Mitigação |
|---|---|---|---|---|
| R1 | Vazamento de dados entre tenants (bug em manager/view) | Crítico | Média | Managers scoping + constraints + **suíte de isolamento obrigatória em CI** + revisão de PR com checklist “query tem tenant?”; futuro RLS. |
| R2 | Race condition de selo (mesmo selo em 2 O.S.) | Alto | Média | `select_for_update` + transação + teste de concorrência; constraint de estado. |
| R3 | Numeração de O.S. duplicada sob carga | Alto | Baixa | Sequência com lock por tenant + unique constraint; teste de carga. |
| R4 | Custo/token de IA disparar | Médio | Média | Cache semântico/exato, limites de plano, `TokenUsage` com alerta, `max_tokens`, temperature baixa. |
| R5 | LLM alucina números de O.S. | Alto | Média | Ferramentas tipadas obrigatórias para dados factuais; instrução “não invente números”; citação de fonte; modo RAG vs. tools no router. |
| R6 | Vazamento via tools/RAG | Crítico | Baixa | `tenant_id` injetado pelo runtime; testes anti-vazamento; denylist de parâmetros. |
| R7 | Assinatura não vale como prova legal | Alto | Média | Combinar com hash de documento + IP/timestamp (v1.2); comunicar limitação; roadmap ICP-Brasil. |
| R8 | Impressão inconsistente entre navegadores | Médio | Alta | CSS print testado em Chrome/Firefox/Safari; checklist visual no gate. |
| R9 | Adiar o multi-tenant até chegar cliente/O.S. real (migrar `tenant_id` depois) | Crítico (se adiado) | **Baixa (se feito agora)** | **Multi-tenant na Fase 1, antes do 1º cliente** (§1.5); hoje não há dados reais — backfill de um único tenant ou recriação limpa em staging. Risco residual: só choices legadas em pt-BR (normalizar no Sprint 1.0). |
| R10 | pgvector/dim mismatch ao trocar modelo de embeddings | Médio | Média | Dim em settings; coluna por modelo no futuro (`embedding_v2`); command de re-embed. |
| R11 | Adoção baixa de campo (técnico resiste ao tablet) | Alto | Média | UX de formulário 1 tela, offline-friendly futuramente, treinamento, métrica de tempo de emissão. |
| R12 | Dependência de APIs externas de IA (queda) | Médio | Média | Fallback de provedor + cache de respostas estáticas + modo degradado (sem IA). |
| R13 | LGPD (assinatura/BI) | Alto | Baixa | DPA, retenção, mascaramento em logs, opt-out de IA por tenant. |
| R14 | Escopo inflado (features “úteis” fora da missão) | Médio | Alta | Escopo §4 é contrato; qualquer adição exige ADR + corte equivalente. |

---

## 17. Glossário

| Termo | Definição |
|---|---|
| **Aferix** | Nome do produto/SaaS; interface marca “Ordem de Serviço WEB”. |
| **O.S. (Service Order)** | Documento formal de visita técnica; unidade central do produto. |
| **Tenant** | Empresa contratante do SaaS; fronteira de isolamento de dados. |
| **Técnico (`TECHNICIAN`)** | Usuário de campo que emite O.S.; vê apenas as suas. |
| **`STAFF`** | Usuário que edita O.S. existentes do tenant. |
| **`ADMIN`** | Gestor do tenant: cadastros, selos, usuários, planos. |
| **Selo / lacre (`Stamp`)** | Numeração de conferência aplicada ao equipamento; rastreada do estoque à O.S. |
| **`StampDelivery`** | Vínculo de um selo a um técnico em um momento do tempo. |
| **Divisão E(kg)** | Menor incremento de massa que a balança indica; campo regulatório. |
| **Inventário Inmetro** | Número de inventário do equipamento no Inmetro. |
| **Portaria** | Ato normativo/ano de homologação da balança. |
| **IPEM/PR** | Instituto de Pesos e Medidas do Paraná — registro exibido no cabeçalho. |
| **Assinatura canvas** | Assinatura manuscrita do cliente capturada em `<canvas>` (dataURL PNG). |
| **Formset** | Conjunto dinâmico de formulários Django (peças, tempos). |
| **CBV** | Class-Based View do Django. |
| **RAG** | Retrieval-Augmented Generation — geração com base em trechos recuperados (pgvector). |
| **Vector store** | Banco de embeddings; aqui pgvector dentro do PostgreSQL. |
| **Embedding** | Representação vetorial de texto para similaridade semântica. |
| **Tool (agente)** | Função tipada que o LLM pode chamar para ler dados do sistema. |
| **Nó do grafo** | Etapa do LangGraph (router, tools, synthesize…). |
| **Checkpointer** | Persistência de estado da conversa do agente. |
| **Cache semântico** | Reuso de resposta quando a pergunta é similar a outra cacheada. |
| **Crédito de IA** | Unidade de cobrança de uso do assistente por plano. |
| **Shared schema** | Estratégia multi-tenant: todos os tenants na mesma tabela/schema, separados por coluna. |
| **RLS** | Row-Level Security do PostgreSQL (hardening futuro). |
| **LGPD** | Lei Geral de Proteção de Dados (Brasil). |
| **Soft block** | Limitação de uso que avisa e restringe progressivamente sem travar operação em andamento. |
| **Legado** | Código em produção (EC2, domínio próprio, empresa única, sem clientes reais) que a Fase 1 converte em base multi-tenant. |
| **Staging** | Ambiente espelho de produção usado para desenvolver e validar a Fase 1 sem afetar o ambiente atual. |
| **Fase 0** | **Inexistente neste PRD (v1.1)** — migração de dados reais dispensada por não haver clientes em operação. |

---

**Fim do documento — PRD v1.1 (fonte única de verdade para o desenvolvimento do Aferix).**
**v1.1:** contexto de produção (EC2 + domínio próprio), sem clientes reais — Fase 0 removida, Fase 1 = fundação multi-tenant from scratch em staging, R9 trivializado, KPIs divididos em fase comercial e operacional.
