# ADR-0001: Relatório Técnico Rodoviário

**Status:** Aceita para implementação na Fase 5
**Data:** 2026-09-24
**Escopo:** Sprint 5.1 / Feature 1

## Contexto

O sistema já possui `Client`, `Scale`, `ServiceOrder`, selos e assinatura do
cliente. O formulário de referência é um relatório técnico de uma página para
balança rodoviária, com dados de identificação e três ensaios metrológicos:
fidelidade (3 posições), excentricidade (6 posições) e pesagem (22 posições).

O documento precisa permanecer rastreável mesmo quando o cadastro operacional
da balança for corrigido depois. O PRD também exige isolamento por tenant,
permissões por role, auditoria e impressão A4 coerente com o design system.

## Decisões

1. O relatório será um recurso `TechnicalReport` 1:1 com `ServiceOrder` e só
   poderá ser aberto para uma `Scale` classificada como `RODOVIARIA`.
2. A classificação da balança, capacidade mínima e classe metrológica serão
   atributos permanentes de `Scale`. Ao concluir o relatório, esses valores e os
   valores regulatórios exibidos serão copiados como snapshots imutáveis do
   documento.
3. Os ensaios serão persistidos em tabelas estruturadas especializadas, com
   sequências fixas de 3, 6 e 22 linhas. Não será usado JSON para substituir as
   relações ou uma imagem do formulário.
4. O campo `applied_load_kg` ficará no conjunto de excentricidade, pois o PDF
   informa uma carga aplicada comum ao ensaio.
5. O estado do relatório será `DRAFT`, `COMPLETED` ou `CANCELED`. Rascunhos
   podem ser incompletos; conclusão valida todos os campos obrigatórios;
   cancelamento é auditado e não exclui o documento.
6. O número do relatório será o número da O.S. formatado em cinco dígitos. Não
   será criada uma sequência independente.
7. A assinatura do proprietário e o nome do responsável serão reutilizados de
   `ServiceOrder.signature` e `ServiceOrder.client_signer_name`. O responsável
   técnico será o usuário da O.S.; o relatório não solicitará uma segunda
   assinatura ou RG.
8. Data, cidade, selos e placa do caminhão serão derivados da O.S. e dos tempos
   de serviço. O erro das medições será calculado como indicação menos carga.
9. O MVP usará `window.print()` e CSS de impressão A4. PDF nativo, hash de
   integridade e ICP-Brasil permanecem no roadmap posterior.

## Consequências

- A edição do cadastro da balança não altera relatório concluído.
- A migração precisa preservar capacidade/divisão textuais legadas e não pode
  converter unidades sem confirmação.
- A conclusão exige transação única para o cabeçalho e as 31 medições.
- A tela deverá usar tokens do design system, Bootstrap customizado e estados
  acessíveis; a impressão terá layout próprio sem navegação.
- A Sprint 5.5 ainda precisa validar o layout contra o PDF em navegadores e com
  técnicos reais. A validação documental da Sprint 5.1 não substitui esse UAT.

## Alternativas rejeitadas

- **Um JSON com todo o formulário:** dificulta constraints, exportação, auditoria
  e futuras consultas da IA.
- **Duplicar cliente e balança integralmente no relatório:** cria divergência e
  viola o reaproveitamento de dados da O.S.; apenas snapshots regulatórios são
  justificados.
- **Gerar relatório automaticamente ao criar O.S.:** criaria documentos vazios
  para visitas que não são rodoviárias.
- **PDF nativo nesta sprint:** aumenta dependências e não é necessário para o
  fluxo atual, que já usa impressão A4 do navegador.
