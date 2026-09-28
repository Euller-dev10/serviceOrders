# Manual do Sistema Aferix

## 1. Acesso ao sistema

### Login

1. Informe o e-mail e a senha cadastrados.
2. Após o login, o usuário é direcionado para a página inicial.
3. Usuários não autenticados não conseguem acessar os dados da empresa.

### Usuários e permissões

- **Técnico:** trabalha nas próprias ordens de serviço, clientes, balanças e relatórios técnicos.
- **Equipe/Staff:** visualiza e administra os registros do tenant conforme as permissões configuradas.
- **Administrador:** gerencia usuários, selos, distribuições e operações administrativas.
- **Superusuário:** possui acesso global para administração do sistema.

Cada usuário comum pertence a uma empresa (tenant). Os dados de uma empresa não ficam disponíveis para outra.

## 2. Página inicial

A página inicial apresenta os principais módulos do sistema:

- Ordens de serviço.
- Clientes.
- Balanças.
- Relatórios técnicos.
- Aferix IA.
- Controle de selos.

Os cartões servem para identificar os recursos disponíveis. A navegação é feita pelo menu lateral.

## 3. Clientes

### Cadastro

Permite registrar:

- Razão social ou nome.
- CNPJ/CPF.
- Inscrição estadual ou RG.
- Endereço, bairro, cidade, UF e CEP.
- Contato e e-mail.

O documento é validado dentro do tenant. O mesmo documento pode existir em empresas diferentes sem conflito.

### Consulta e edição

Na listagem é possível pesquisar clientes e abrir o cadastro para visualizar ou editar os dados. Clientes vinculados a outra empresa não aparecem.

## 4. Balanças

### Cadastro

Uma balança pode conter:

- Marca e modelo.
- Número de série.
- Capacidade e unidade.
- Divisão (E).
- TAG.
- Portaria/Inmetro.
- Tipo de balança.
- Classe metrológica e capacidade mínima.

O número de série é controlado por cliente e tenant para evitar duplicidade.

### Tipos disponíveis

O relatório técnico fica disponível para balanças classificadas como:

- Rodoviária.
- Ferroviária.
- Rodoviária/Ferroviária.

## 5. Ordens de serviço

### Criação

Para criar uma O.S.:

1. Acesse **Ordens de Serviço > Gerar O.S.**
2. Selecione o cliente e a balança.
3. Informe os serviços executados.
4. Preencha observações, selo, assinatura e demais informações.
5. Adicione peças utilizadas e tempos de serviço, quando necessário.
6. Salve a O.S.

O sistema gera um número sequencial próprio para cada tenant.

### Dados da O.S.

Uma ordem pode conter:

- Serviços de manutenção, reparo, certificação e ajustes.
- Selo retirado e selo aplicado.
- Observações.
- Verificação anual pelo Inmetro.
- Instalação nova.
- Alimentação e hospedagem.
- Peças utilizadas.
- Tempo de serviço, veículo e caminhão.
- Assinatura do cliente.

### Listagem

A listagem permite:

- Pesquisar por número, cliente, documento ou cidade.
- Filtrar por data ou período.
- Clicar na linha para abrir os detalhes.
- Editar a O.S.
- Imprimir a O.S.
- Excluir a O.S. conforme a permissão do usuário.

## 6. Relatórios técnicos

### Criação e edição

O relatório é vinculado à O.S., mas possui numeração própria e sequencial por tenant.

Ao abrir o relatório:

- Se não existir relatório, o formulário é aberto para preenchimento.
- Se existir um rascunho, o formulário continua editável.
- Se existir um relatório concluído, a O.S. oferece acesso direto à visualização/impressão.
- O relatório continua editável conforme a permissão do usuário.

O número do relatório é gerado automaticamente e não pode ser preenchido manualmente.

### Dados do relatório

O formulário contém:

- Serviço executado.
- Certificado do peso padrão.
- Placa do caminhão.
- Observações.
- Carga aplicada no ensaio de excentricidade.
- Dados derivados da O.S., como técnico, cidade, selos e data.

Os campos do relatório são opcionais, salvo regras específicas que venham a ser configuradas futuramente.

### Ensaios

O relatório possui três tabelas:

1. **Ensaio de fidelidade**.
2. **Ensaio de excentricidade — carga em diferentes pontos da plataforma**.
3. **Ensaio de pesagem — determinação do erro em função da carga**.

Cada linha pode receber carga, indicação e E.M.A. O erro é calculado automaticamente pela fórmula:

```text
Erro = Indicação - Carga
```

Os campos numéricos aceitam formato decimal brasileiro. Na impressão, os valores são exibidos sem casas decimais.

Linhas de pesagem totalmente vazias não são exibidas no documento impresso.

### Impressão

A impressão possui:

- Cabeçalho da empresa.
- Logo e registro IPEM.
- Número próprio do relatório.
- Número da O.S. vinculada.
- Dados organizados um abaixo do outro.
- Tabelas dos ensaios.
- Assinatura do responsável técnico.
- Assinatura reaproveitada do cliente na O.S.

Os campos não preenchidos permanecem vazios no documento.

### Listagem

Em **Ordens de Serviço > Relatórios técnicos**, é possível:

- Pesquisar por número do relatório, número da O.S. ou cliente.
- Filtrar por status.
- Clicar na linha para abrir o relatório.
- Editar.
- Imprimir.
- Excluir, quando permitido.

## 7. Selos

### Cadastro de selos em lote

Como os selos normalmente chegam em lotes, o cadastro permite incluir vários números de uma só vez.

1. Acesse **Selo > Adicionar Selo**.
2. Cole ou digite os números no campo **Números dos selos**.
3. Informe um número por linha, por exemplo:

```text
S-000123
S-000124
S-000125
```

Também é possível separar os números por vírgula ou ponto e vírgula:

```text
S-000123, S-000124; S-000125
```

4. Clique em **Cadastrar lote**.

O sistema valida:

- Se foi informado pelo menos um número.
- Se não existem repetições no mesmo lote.
- Se algum número já existe no tenant.

Todos os selos válidos são criados como **disponíveis** em uma única operação.

### Distribuição

Os selos disponíveis podem ser distribuídos:

- Individualmente para um técnico.
- Em lote para um técnico.

Ao distribuir, o selo passa de disponível para distribuído e fica associado ao técnico.

### Uso e dano

- Ao aplicar o selo em uma O.S., ele passa para usado.
- Um selo danificado pode ser marcado como danificado/cancelado.
- O sistema impede distribuição de selo indisponível.

## 8. Aferix IA

O Assistente IA permite:

- Criar conversas.
- Fazer perguntas sobre O.S., clientes, balanças e normas da empresa.
- Consultar fontes técnicas cadastradas.
- Visualizar referências utilizadas nas respostas.
- Configurar os recursos de IA conforme a permissão.

As conversas ficam organizadas por sessão e podem ser reabertas posteriormente.

## 9. Dashboard e relatórios administrativos

O dashboard reúne indicadores operacionais do tenant, como volume de O.S. e situação dos registros disponíveis para o usuário.

Também há exportação de dados de O.S. para uso administrativo, conforme as permissões configuradas.

## 10. Auditoria e segurança

As principais operações são registradas em auditoria, incluindo:

- Criação e edição de O.S.
- Criação e edição de relatórios.
- Cadastro e distribuição de selos.
- Impressão e exportação de documentos.
- Exclusões autorizadas.

O sistema aplica isolamento por tenant, valida permissões por perfil e protege operações sensíveis com confirmação e requisição autenticada.

## 11. Impressão e PDF

As telas de impressão possuem:

- Layout A4.
- Ocultação de menus e botões durante a impressão.
- Cabeçalho com logo e dados da empresa.
- Tabelas com o padrão visual institucional.
- Campos vazios sem textos artificiais.
- Área de assinatura do técnico e do cliente.

Para gerar um PDF, abra a tela de impressão e use a opção **Imprimir / salvar PDF** do navegador.
