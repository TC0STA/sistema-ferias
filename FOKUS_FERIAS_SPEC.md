# Fokus Férias — Especificação de Regras de Negócio

> Documento vivo e fonte oficial das regras de negócio do Fokus Férias.

| Item | Valor |
|---|---|
| Documento | `FOKUS_FERIAS_SPEC.md` |
| Versão | 1.1.0 |
| Status | Especificação inicial |
| Escopo desta versão | Importação e Perfis de Importação |
| Última atualização | 30/07/2026 |

## 1. Finalidade

Este documento define **o que** o Fokus Férias deve fazer e quais condições o sistema deve respeitar. Arquitetura, banco de dados, APIs, telas e decisões de implementação devem derivar destas regras, sem alterá-las silenciosamente.

O fluxo de evolução do produto será:

```text
IDEIA
  ↓
ESPECIFICAÇÃO
  ↓
ARQUITETURA
  ↓
CÓDIGO
  ↓
TESTE
  ↓
INTEGRAÇÃO
  ↓
DEPLOY
```

### 1.1 Regra de governança

- Toda nova funcionalidade deve ser descrita neste documento antes da arquitetura e do código.
- Toda regra deve possuir um identificador único e permanente.
- Alterações de comportamento devem atualizar a versão e o histórico deste documento.
- Regras removidas não devem ter seus identificadores reutilizados.
- Em caso de divergência entre o sistema e este documento, a divergência deve ser registrada e resolvida explicitamente.

## 2. Visão do produto

O Fokus Férias centraliza informações de férias recebidas de diferentes áreas, empresas, filiais ou unidades, mesmo quando cada origem utiliza um modelo de planilha próprio.

O sistema deve:

1. reduzir o trabalho manual de padronização;
2. impedir a entrada de dados estruturalmente inválidos;
3. explicar ao usuário o que precisa ser corrigido;
4. reaproveitar mapeamentos já confirmados;
5. manter rastreabilidade de cada importação;
6. disponibilizar dados confiáveis aos demais módulos.

## 3. Escopo

### 3.1 Incluído na versão 1.0

- leitura de arquivos Excel;
- identificação automática da linha de cabeçalho;
- reconhecimento de nomes alternativos de colunas;
- mapeamento manual;
- validação estrutural e validação dos registros;
- prévia antes da confirmação;
- Perfis de Importação reutilizáveis;
- comparação com a base anterior;
- confirmação e registro da importação;
- auditoria, versionamento e recuperação por backup.

### 3.2 Evoluções previstas

- importação de CSV;
- regras específicas por empresa, filial ou convenção coletiva;
- fluxo de aprovação;
- notificações e integrações externas;
- permissões detalhadas por perfil de usuário;
- aprendizado assistido de novos aliases;
- processamento simultâneo de múltiplos arquivos.

Itens previstos não são requisitos da versão 1.0 até serem detalhados e aprovados neste documento.

## 4. Glossário

| Termo | Definição |
|---|---|
| Campo canônico | Nome interno e único usado pelo sistema, independentemente do nome da coluna de origem. |
| Cabeçalho | Linha da planilha que contém os nomes das colunas. |
| Alias | Nome alternativo aceito para um campo canônico. |
| Mapeamento | Associação entre uma coluna da planilha e um campo canônico. |
| Assinatura do modelo | Identificador calculado a partir da estrutura das colunas para reconhecer um layout já utilizado. |
| Perfil de Importação | Mapeamento salvo e reutilizável para um modelo de planilha. |
| Origem | Área, unidade, filial, empresa ou responsável que forneceu a planilha. |
| Prévia | Amostra dos dados interpretados antes da importação definitiva. |
| Importação | Processo confirmado que torna uma nova versão de dados disponível ao sistema. |
| Registro | Uma linha de férias de um colaborador. |

## 5. Modelo canônico de dados

### 5.1 Campos obrigatórios

| Campo canônico | Nome exibido | Tipo | Regra básica |
|---|---|---|---|
| `usuario` | Usuário | Texto | Deve identificar o colaborador e não pode estar vazio. |
| `data_inicio` | Data de início | Data | Deve ser uma data válida. |
| `data_fim` | Data de fim | Data | Deve ser uma data válida e não pode ser anterior à data de início. |

### 5.2 Campos opcionais

| Campo canônico | Nome exibido | Tipo |
|---|---|---|
| `matricula` | Matrícula | Texto |
| `departamento` | Departamento | Texto |
| `cargo` | Cargo | Texto |
| `centro_custo` | Centro de custo | Texto |
| `gestor` | Gestor | Texto |
| `filial` | Filial | Texto |
| `empresa` | Empresa | Texto |
| `observacao` | Observação | Texto |

Campos opcionais ausentes não impedem a importação. Quando uma coluna opcional estiver presente, seus valores devem ser preservados e associados ao registro.

### 5.3 Identidade do colaborador

Na versão 1.0:

- `matricula`, quando presente e preenchida, é o identificador preferencial do colaborador;
- na ausência de matrícula, o sistema utiliza o `usuario` normalizado para comparação;
- dois colaboradores diferentes não devem compartilhar a mesma matrícula dentro da mesma importação;
- a estratégia de identidade deve ser apresentada ao usuário quando afetar a comparação com dados anteriores.

## 6. Módulo: Importação

### 6.1 Objetivo

Importar informações de férias a partir de planilhas com layouts variados, convertendo-as para o modelo canônico do Fokus Férias de forma segura, explicável e reutilizável.

### 6.2 Entradas

| Formato | Situação |
|---|---|
| Excel `.xlsx` | Obrigatório na versão 1.0 |
| Excel `.xls` | Suportado quando o ambiente possuir leitor compatível |
| CSV `.csv` | Futuro |

“Importar qualquer planilha” significa aceitar diferentes nomes de colunas e diferentes posições do cabeçalho dentro dos formatos suportados. Não significa aceitar arquivos corrompidos, protegidos, vazios ou sem os dados mínimos exigidos.

### 6.3 Fluxo obrigatório

```text
Selecionar arquivo
       ↓
Validar arquivo e localizar cabeçalho
       ↓
Reconhecer Perfil de Importação ou mapear colunas
       ↓
Validar registros
       ↓
Exibir erros, prévia e comparação
       ↓
Confirmação explícita do usuário
       ↓
Backup e importação
       ↓
Auditoria e atualização dos módulos consumidores
```

### 6.4 Regras de arquivo e leitura

#### RN-IMP-001 — Formatos permitidos

O sistema deve aceitar apenas os formatos habilitados para a versão em uso. Arquivos com extensão não permitida devem ser recusados antes da leitura dos dados.

**Critério de aceite:** um arquivo não suportado não altera os dados atuais e produz mensagem com os formatos aceitos.

#### RN-IMP-002 — Validade do arquivo

O sistema não deve importar arquivo inexistente, vazio, ilegível, corrompido ou cujo conteúdo não corresponda ao formato declarado.

**Critério de aceite:** a falha deve ser informada em linguagem clara e registrada sem expor detalhes técnicos ao usuário final.

#### RN-IMP-003 — Detecção automática do cabeçalho

O sistema deve procurar automaticamente a linha de cabeçalho, mesmo quando houver título, texto explicativo ou linhas vazias antes dela.

**Critério de aceite:** ao localizar uma linha que permita mapear os três campos obrigatórios, essa linha deve ser utilizada como cabeçalho e as anteriores devem ser ignoradas como dados.

#### RN-IMP-004 — Ausência de cabeçalho reconhecível

Se nenhuma linha puder ser identificada com segurança como cabeçalho, o sistema não deve importar e deve solicitar correção do arquivo ou mapeamento assistido, quando tecnicamente possível.

#### RN-IMP-005 — Seleção de planilha interna

Quando o arquivo Excel possuir mais de uma aba com dados possíveis, o sistema deve informar as abas encontradas e exigir uma escolha quando não houver uma única opção segura.

**Situação:** evolução planejada; até sua implementação, a primeira aba legível será considerada e essa limitação deve ser informada.

### 6.5 Regras de reconhecimento de colunas

#### RN-IMP-006 — Nomes alternativos

O sistema deve aceitar nomes diferentes para o mesmo campo canônico, desconsiderando diferenças de maiúsculas, minúsculas, acentuação e espaços externos.

Exemplos iniciais:

| Campo canônico | Aliases iniciais |
|---|---|
| `usuario` | Usuário, Nome, Funcionário, Colaborador, Nome do colaborador |
| `data_inicio` | Início, Data início, Data de início, Início das férias, Data inicial |
| `data_fim` | Fim, Data fim, Data de fim, Data final, Retorno, Volta |
| `matricula` | Matrícula, Registro, Código funcionário, ID funcionário |
| `departamento` | Departamento, Depto, Setor, Área, Lotação |

A lista é extensível e não deve exigir alteração do arquivo de origem para cada novo alias aprovado.

#### RN-IMP-007 — Correspondência única

Uma coluna da planilha não pode representar mais de um campo canônico na mesma importação.

#### RN-IMP-008 — Ambiguidade

Se mais de uma coluna puder representar o mesmo campo, o sistema não deve escolher silenciosamente. Deve apresentar as opções para confirmação manual.

#### RN-IMP-009 — Campo obrigatório não identificado

Se qualquer campo obrigatório não for identificado, a importação deve permanecer bloqueada e a mensagem deve listar os campos ausentes.

#### RN-IMP-010 — Mapeamento manual

O usuário deve poder associar manualmente cada campo canônico necessário a uma coluna existente na planilha.

#### RN-IMP-011 — Confirmação do mapeamento

Um mapeamento manual somente pode ser utilizado após confirmação explícita. A confirmação deve gerar ou atualizar um Perfil de Importação.

#### RN-IMP-012 — Colunas desconhecidas

Colunas que não correspondam a campos canônicos não devem impedir a importação. Elas devem ser ignoradas e identificadas como não utilizadas na tela de validação.

#### RN-IMP-013 — Alias confirmado

Um novo nome de coluna confirmado manualmente pode ser proposto como alias reutilizável. Sua adoção global deve ser uma ação explícita e auditável para evitar associações incorretas em outras origens.

### 6.6 Regras de validação dos registros

#### RN-IMP-014 — Validação antes da gravação

Todos os registros devem ser validados antes de qualquer alteração na base ativa.

#### RN-IMP-015 — Usuário obrigatório

Registros sem `usuario` devem ser inválidos.

#### RN-IMP-016 — Datas obrigatórias e válidas

Registros sem `data_inicio`, sem `data_fim` ou com data não reconhecível devem ser inválidos.

#### RN-IMP-017 — Ordem do período

`data_inicio` não pode ser posterior a `data_fim`. O mesmo dia é um período válido.

#### RN-IMP-018 — Linhas totalmente vazias

Linhas totalmente vazias após o cabeçalho devem ser desconsideradas quando estiverem apenas no final da área de dados. Uma linha vazia intercalada em registros deve ser sinalizada, mas não pode criar um registro.

#### RN-IMP-019 — Duplicidade exata

Dois registros com a mesma identidade de colaborador, a mesma data de início e a mesma data de fim, dentro do mesmo arquivo, constituem duplicidade.

#### RN-IMP-020 — Matrícula duplicada

A repetição de matrícula não é erro por si só quando representar períodos de férias diferentes do mesmo colaborador. É erro quando a mesma matrícula estiver associada a usuários incompatíveis.

> Esta regra substitui a interpretação simplificada de que toda matrícula repetida seria inválida.

#### RN-IMP-021 — Sobreposição de períodos

Períodos sobrepostos para o mesmo colaborador devem ser sinalizados para revisão. A política de bloqueio será configurável; na versão 1.0, a confirmação deve ser bloqueada até correção ou aceite explícito por usuário autorizado.

#### RN-IMP-022 — Campos opcionais presentes

Se uma coluna opcional existir, valores vazios nessa coluna devem gerar aviso, não erro, salvo quando uma regra específica da organização tornar o campo obrigatório.

#### RN-IMP-023 — Resultado detalhado

A validação deve informar:

- total de registros encontrados;
- quantidade de válidos e inválidos;
- número da linha original;
- campo afetado;
- descrição do erro ou aviso;
- prévia dos registros interpretados;
- estado final: pronto, requer mapeamento ou contém erros.

#### RN-IMP-024 — Política de atomicidade

Na versão 1.0, a importação é atômica: se houver qualquer erro bloqueante, nenhum registro do arquivo será importado.

### 6.7 Regras de comparação e confirmação

#### RN-IMP-025 — Comparação com a versão vigente

Antes da confirmação, o sistema deve comparar o arquivo validado com os dados vigentes e apresentar, no mínimo:

- registros novos;
- registros removidos;
- registros alterados;
- registros sem alteração.

#### RN-IMP-026 — Critério de alteração

Um registro é alterado quando a identidade do colaborador é a mesma, mas pelo menos um campo canônico relevante difere da versão vigente.

#### RN-IMP-027 — Confirmação explícita

Validar ou analisar um arquivo não equivale a importá-lo. A gravação somente deve ocorrer após ação explícita de confirmação.

#### RN-IMP-028 — Substituição da versão vigente

Por padrão, uma importação confirmada representa a nova fotografia completa dos dados de férias. Registros ausentes no novo arquivo serão classificados como removidos.

Importações incrementais deverão ser especificadas como um modo separado antes de serem permitidas.

#### RN-IMP-029 — Revalidação

Se o arquivo, o mapeamento ou os dados forem alterados após a validação, a validação anterior perde a validade e deve ser executada novamente.

#### RN-IMP-030 — Idempotência

Reenviar e confirmar o mesmo arquivo, com o mesmo conteúdo e mapeamento, não deve criar dados duplicados. O sistema deve informar que não existem alterações ou registrar uma nova execução sem duplicar os registros, conforme a política de auditoria.

### 6.8 Regras de conclusão, segurança e recuperação

#### RN-IMP-031 — Backup anterior

Antes de substituir a versão vigente, o sistema deve criar um ponto de recuperação válido. Se o backup obrigatório falhar, a importação deve ser interrompida.

#### RN-IMP-032 — Falha durante a importação

Se ocorrer falha após o início da gravação, a operação deve ser revertida e a última versão válida deve permanecer disponível.

#### RN-IMP-033 — Versionamento

Cada importação concluída deve receber uma versão sequencial e imutável.

#### RN-IMP-034 — Auditoria

O sistema deve registrar, no mínimo:

- usuário responsável;
- data e hora;
- nome do arquivo;
- assinatura ou hash do conteúdo;
- Perfil de Importação utilizado;
- totais de registros novos, alterados, removidos e mantidos;
- resultado da operação;
- duração;
- versão gerada;
- motivo da falha, quando aplicável.

#### RN-IMP-035 — Atualização dos consumidores

Após uma importação concluída, os módulos que consomem férias devem ser atualizados ou invalidados para recarregar a nova versão.

#### RN-IMP-036 — Preservação em caso de erro

Erros de arquivo, mapeamento, validação, backup, extensão ou integração não podem apagar nem substituir a versão vigente.

#### RN-IMP-037 — Arquivo de origem

O arquivo efetivamente importado deve ser preservado ou referenciado de forma recuperável, respeitando a política de retenção e proteção de dados.

### 6.9 Preview e Simulador de Importação

#### RN-IMP-038 — Preview obrigatório

Toda importação definitiva deve apresentar um Preview após a leitura, o mapeamento, a validação e a comparação, mas antes de qualquer alteração nos dados vigentes.

#### RN-IMP-039 — Estatísticas do Preview

O Preview deve apresentar, no mínimo:

- nome do arquivo;
- registros encontrados;
- usuários únicos;
- primeiro início e último fim encontrados;
- quantidade de departamentos;
- datas inválidas;
- duplicidades;
- colunas obrigatórias identificadas;
- novos, alterados, removidos e sem alteração.

Quando uma estatística não puder ser calculada, o sistema deve exibir “Não disponível” em vez de assumir zero.

#### RN-IMP-040 — Ações do Preview

O Preview de uma planilha pronta deve oferecer as ações “Cancelar” e “Confirmar importação”. Arquivos com erros bloqueantes não podem oferecer confirmação.

#### RN-IMP-041 — Escolha do modo

Antes da análise, o usuário deve escolher entre:

- **Simular importação:** executa leitura, mapeamento, validação, comparação e estatísticas;
- **Importar definitivamente:** executa a mesma análise e permite confirmação posterior.

A seleção inicial recomendada deve ser “Simular importação”.

#### RN-IMP-042 — Simulação sem persistência

A simulação não deve alterar dados, arquivos vigentes, Perfis de Importação, contadores, auditoria, versões, backups nem estado de atualização do dashboard. Arquivos temporários utilizados na análise devem expirar e ser descartados.

#### RN-IMP-043 — Resultado da simulação

O resultado deve estar identificado visualmente como “Simulação” e declarar que nenhuma alteração foi gravada.

#### RN-IMP-044 — Conversão para importação definitiva

Alterar o modo de “Simulação” para “Importação definitiva” invalida a análise anterior. O arquivo deve ser analisado novamente no modo definitivo antes da confirmação.

#### RN-IMP-045 — Atualização do dashboard

Somente uma importação definitiva concluída deve atualizar ou invalidar o dashboard e os demais módulos consumidores. Simulações nunca disparam essa atualização.

## 7. Módulo: Perfis de Importação

### 7.1 Objetivo

Reconhecer e reutilizar automaticamente os diferentes modelos de planilha enviados por cada origem.

Exemplos:

```text
RH Goiás      → Perfil Goiás
RH São Paulo  → Perfil São Paulo
RH Minas      → Perfil Minas
RH Matriz     → Perfil Matriz
```

### 7.2 Dados mínimos do perfil

Cada perfil deve possuir:

| Dado | Finalidade |
|---|---|
| Identificador | Referência interna estável |
| Nome | Identificação amigável, por exemplo “RH Goiás” |
| Assinatura do modelo | Reconhecimento automático da estrutura |
| Lista de colunas | Conferência do layout original |
| Mapeamento | Associação de colunas aos campos canônicos |
| Origem | Unidade, área, empresa ou responsável |
| Arquivo de referência | Rastreabilidade |
| Estado | Ativo ou inativo |
| Confirmação | Indica se houve validação humana |
| Datas de criação, alteração e último uso | Auditoria |
| Quantidade de utilizações | Acompanhamento |

### 7.3 Regras

#### RN-PRF-001 — Criação

O sistema deve permitir salvar como perfil todo mapeamento completo e confirmado.

#### RN-PRF-002 — Nome do perfil

O perfil deve possuir nome não vazio. O sistema pode sugerir um nome a partir do arquivo ou da origem, mas o usuário pode alterá-lo.

#### RN-PRF-003 — Reconhecimento automático

Ao receber uma planilha cuja assinatura corresponda a um perfil ativo, o sistema deve aplicar seu mapeamento automaticamente.

#### RN-PRF-004 — Transparência

Quando um perfil for aplicado, o sistema deve informar qual perfil foi reconhecido e permitir revisar o mapeamento antes da confirmação.

#### RN-PRF-005 — Segurança da correspondência

O perfil somente pode ser aplicado se todas as colunas referenciadas por seu mapeamento estiverem presentes. Correspondência incompleta deve retornar ao reconhecimento automático ou ao mapeamento manual.

#### RN-PRF-006 — Assinatura estrutural

A assinatura deve considerar os nomes normalizados e a estrutura das colunas. Alterações relevantes no conjunto ou na ordem definida pela estratégia de assinatura devem produzir um modelo diferente.

#### RN-PRF-007 — Variação do modelo

Quando uma origem alterar seu layout, o sistema deve:

1. informar que o modelo conhecido não corresponde integralmente;
2. preservar o perfil anterior;
3. permitir ajustar o mapeamento;
4. permitir atualizar o perfil ou criar uma nova versão, mediante confirmação.

#### RN-PRF-008 — Conflito de perfis

Uma mesma assinatura não pode apontar silenciosamente para mapeamentos divergentes. O conflito deve exigir escolha ou consolidação por usuário autorizado.

#### RN-PRF-009 — Ativação

Somente perfis ativos participam do reconhecimento automático.

#### RN-PRF-010 — Desativação

Um perfil pode ser desativado sem apagar seu histórico. A desativação deve ser auditada.

#### RN-PRF-011 — Exclusão

Perfis que já tenham sido utilizados não devem ser excluídos fisicamente. Devem ser inativados para preservar a rastreabilidade.

#### RN-PRF-012 — Renomeação

Renomear um perfil não altera sua assinatura nem seu mapeamento.

#### RN-PRF-013 — Contagem de uso

Uma utilização deve ser contabilizada quando o perfil participar de uma validação concluída. Importações canceladas ou reprovadas podem ser registradas separadamente, mas não contam como importações concluídas.

#### RN-PRF-014 — Aprendizado controlado

“O sistema aprende” significa salvar e reaplicar decisões humanas confirmadas. A versão 1.0 não deve inferir autonomamente mudanças globais sem confirmação.

#### RN-PRF-015 — Isolamento por origem

Perfis de origens diferentes podem mapear o mesmo nome de coluna de formas diferentes. Um mapeamento específico do perfil tem precedência sobre aliases globais.

#### RN-PRF-016 — Ordem de decisão

O reconhecimento deve respeitar a seguinte prioridade:

1. mapeamento manual confirmado para a operação atual;
2. Perfil de Importação ativo e compatível;
3. aliases globais;
4. solicitação de mapeamento manual.

## 8. Mensagens e experiência do usuário

#### RN-UX-001 — Linguagem clara

Mensagens devem explicar o problema e a ação esperada, evitando somente códigos ou termos técnicos.

Exemplo:

> Não foi possível identificar a coluna “Data de início”. Selecione a coluna correspondente para continuar.

#### RN-UX-002 — Localização do erro

Erros de registro devem mostrar o número da linha no arquivo original, não apenas a posição interna após a leitura.

#### RN-UX-003 — Separação entre erro e aviso

- **Erro:** bloqueia a confirmação.
- **Aviso:** exige ciência ou atenção, mas pode permitir confirmação.
- **Informação:** descreve o resultado sem exigir ação.

#### RN-UX-004 — Persistência da análise

Uma análise temporária deve expirar por segurança. Ao expirar, o usuário deve selecionar e validar novamente o arquivo; o sistema não deve reutilizar silenciosamente dados temporários antigos.

#### RN-UX-005 — Resumo final

Após a importação, o sistema deve apresentar arquivo, versão, perfil utilizado e totais de novos, alterados, removidos, mantidos e rejeitados.

## 9. Requisitos não funcionais vinculados ao negócio

#### RNF-001 — Integridade

Nenhuma falha parcial pode deixar a base ativa em estado inconsistente.

#### RNF-002 — Rastreabilidade

Deve ser possível descobrir quando, por quem, de qual arquivo e com qual perfil uma versão foi criada.

#### RNF-003 — Proteção de dados

Arquivos e registros de colaboradores devem ser acessíveis somente a usuários autorizados e não devem aparecer em logs técnicos além do necessário.

#### RNF-004 — Desempenho percebido

Durante análises demoradas, a interface deve indicar processamento em andamento e impedir confirmações duplicadas.

#### RNF-005 — Compatibilidade

Nomes e valores textuais devem preservar caracteres da língua portuguesa, incluindo acentos e cedilha.

#### RNF-006 — Observabilidade

Falhas técnicas devem possuir identificador de correlação para diagnóstico, sem revelar informações sensíveis na mensagem apresentada ao usuário.

## 10. Critérios de aceite do módulo

O módulo de Importação estará funcionalmente aceito quando:

- importar um `.xlsx` válido com os três campos obrigatórios;
- localizar cabeçalho abaixo da primeira linha;
- reconhecer os aliases aprovados;
- bloquear arquivo sem campo obrigatório;
- solicitar confirmação em caso de ambiguidade;
- permitir e salvar mapeamento manual;
- reconhecer novamente os modelos de Goiás, São Paulo, Minas e Matriz;
- validar datas, períodos e duplicidades conforme esta especificação;
- apresentar prévia e comparação antes de gravar;
- apresentar período, departamentos, usuários únicos, duplicidades e datas inválidas;
- executar uma simulação completa sem modificar o banco ou a versão vigente;
- não alterar a base antes da confirmação;
- preservar a versão vigente diante de qualquer erro;
- criar backup, versão e auditoria na conclusão;
- atualizar os módulos consumidores;
- passar pelos testes derivados de cada regra aplicável.

## 11. Matriz inicial de testes de negócio

| Teste | Regras principais | Resultado esperado |
|---|---|---|
| Excel padrão válido | RN-IMP-001, 003, 014–017 | Pronto para confirmação |
| Cabeçalho na linha 5 | RN-IMP-003 | Cabeçalho detectado e linhas anteriores ignoradas |
| Coluna “Funcionário” | RN-IMP-006 | Mapeada para `usuario` |
| Sem data de fim | RN-IMP-009 | Importação bloqueada e campo listado |
| Duas possíveis datas de início | RN-IMP-008 | Confirmação manual exigida |
| Mapeamento manual Goiás | RN-IMP-010, RN-PRF-001 | Perfil Goiás salvo |
| Nova planilha com modelo Goiás | RN-PRF-003 | Perfil aplicado e informado |
| Modelo Goiás alterado | RN-PRF-007 | Ajuste solicitado sem apagar perfil anterior |
| Data inicial posterior à final | RN-IMP-017 | Linha inválida |
| Mesmo período duplicado | RN-IMP-019 | Importação bloqueada |
| Mesma matrícula em períodos diferentes | RN-IMP-020 | Permitida se a identidade for compatível |
| Arquivo idêntico ao vigente | RN-IMP-030 | Nenhum registro duplicado |
| Falha no backup | RN-IMP-031, 036 | Importação interrompida e base preservada |
| Falha durante gravação | RN-IMP-032 | Operação revertida |
| Perfil desativado | RN-PRF-009, 010 | Não aplicado automaticamente |
| Preview estatístico | RN-IMP-038, 039 | Resumo, período e indicadores exibidos antes da confirmação |
| Cancelamento no Preview | RN-IMP-040 | Nenhuma alteração realizada |
| Simulação válida | RN-IMP-041–043 | Resultado exibido e banco inalterado |
| Troca de simulação para definitivo | RN-IMP-044 | Nova análise exigida |
| Simulação e dashboard | RN-IMP-045 | Estado dos módulos permanece inalterado |

## 12. Decisões pendentes

As decisões abaixo devem ser fechadas antes da respectiva implementação:

| ID | Decisão | Impacto |
|---|---|---|
| DP-001 | Limite de tamanho do arquivo e de registros | Segurança e desempenho |
| DP-002 | Prazo de retenção dos arquivos importados e backups | Privacidade e recuperação |
| DP-003 | Perfis de usuário autorizados a importar, aceitar sobreposição e administrar perfis | Segurança |
| DP-004 | Formatos de data aceitos e tratamento de datas ambíguas, como `01/02/2026` | Integridade |
| DP-005 | Obrigatoriedade de matrícula por empresa ou origem | Identidade |
| DP-006 | Regra definitiva para múltiplas abas | Leitura |
| DP-007 | Estratégia para atualizar ou versionar um Perfil de Importação alterado | Rastreabilidade |
| DP-008 | Política para períodos de férias sobrepostos | Validação |
| DP-009 | Regras de importação incremental | Comparação |
| DP-010 | Política de inclusão de novos aliases globais | Aprendizado controlado |

## 13. Rastreabilidade da implementação atual

Esta seção é informativa e não substitui as regras acima.

Na data desta versão, o projeto já possui componentes para:

- leitura de Excel e detecção de cabeçalho;
- aliases e mapeamento de colunas;
- validação de registros;
- Perfis de Importação;
- comparação entre versões;
- backup;
- logs e auditoria;
- eventos e extensões de importação;
- atualização de módulos consumidores.

Algumas regras desta especificação ampliam ou corrigem comportamentos existentes. Em especial:

- os campos opcionais além de matrícula e departamento ainda precisam ser incorporados ao modelo canônico;
- matrícula repetida deve considerar a identidade e os períodos, conforme RN-IMP-020;
- sobreposição de períodos precisa seguir RN-IMP-021;
- múltiplas abas precisam seguir RN-IMP-005;
- retenção, permissões e datas ambíguas dependem das decisões pendentes.

## 14. Histórico de versões

| Versão | Data | Alteração |
|---|---|---|
| 1.0.0 | 30/07/2026 | Criação da especificação central; definição dos módulos Importação e Perfis de Importação. |
| 1.1.0 | 30/07/2026 | Inclusão do Preview estatístico e do Simulador de Importação da Sprint 1. |
