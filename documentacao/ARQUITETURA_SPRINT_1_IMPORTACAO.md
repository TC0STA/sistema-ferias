# Arquitetura da Sprint 1 — Importação

## 1. Objetivo

Separar o fluxo de importação em componentes com responsabilidade única e garantir que nenhuma gravação definitiva ocorra antes da confirmação do usuário.

## 2. Fluxo

```text
Interface
   │
   ├── modo: simulação
   │      ↓
   │   ImportService.analyze(dry_run=True)
   │      ├── FileReader
   │      ├── ColumnMapper
   │      ├── ImportValidator
   │      ├── CompareService
   │      └── ImportPreview
   │
   └── modo: definitivo
          ↓
       ImportService.analyze(dry_run=False)
          ↓
       Preview + confirmação explícita
          ↓
       backup → salvar arquivo/dados → versionar
          ↓
       DashboardUpdater
```

## 3. Componentes

### 3.1 FileReader

Responsabilidade única:

1. receber o caminho;
2. verificar se o arquivo pode ser aberto;
3. ler o Excel;
4. devolver o `DataFrame` e metadados de leitura.

Não mapeia, valida, compara ou persiste dados.

### 3.2 ColumnMapper

Recebe os cabeçalhos e devolve a associação entre campos canônicos e colunas reais, além de ausências e ambiguidades.

Exemplo:

```json
{
  "usuario": "Colaborador",
  "data_inicio": "Início",
  "data_fim": "Retorno"
}
```

### 3.3 ImportValidator

Recebe somente o `DataFrame`, o mapeamento e os metadados necessários para localizar as linhas.

Devolve:

```json
{
  "status": "SUCESSO",
  "pronta": true,
  "erros": [],
  "avisos": []
}
```

Não lê arquivo, não grava banco e não atualiza interface.

### 3.4 CompareService

Compara o `DataFrame` validado com a versão vigente e informa novos, removidos, alterados e iguais. Não persiste o resultado.

### 3.5 ImportPreview

Componente puro que recebe `DataFrame`, mapeamento e validação. Produz:

- registros encontrados;
- usuários únicos;
- departamentos;
- período;
- datas inválidas;
- duplicidades;
- colunas identificadas.

### 3.6 ImportService

Orquestra os componentes. Não contém HTML nem comportamento específico de tela.

No modo `dry_run=True`:

- não salva nem contabiliza Perfis de Importação;
- não cria auditoria ou log;
- não executa plugins com efeitos colaterais;
- não cria backup ou versão;
- não atualiza o dashboard.

### 3.7 Camada HTTP e interface

- `POST /api/importacao/validar`: analisa em modo definitivo ou simulação;
- `POST /api/importacao/mapeamento`: confirma associações manuais;
- `POST /upload`: aceita somente análise definitiva válida e realiza a confirmação;
- `/importar`: apresenta escolha de modo, Preview, Cancelar e Confirmar.

## 4. Estado temporário

O arquivo analisado e o resultado ficam em armazenamento temporário identificados por token. O token registra o modo da análise.

Um token de simulação:

- não pode ser usado em `/upload`;
- expira como as demais análises temporárias;
- não representa uma versão de dados.

## 5. Limites de persistência

| Ação | Banco | Backup | Dashboard |
|---|---:|---:|---:|
| Simular | Não | Não | Não |
| Analisar para importação | Apenas metadados operacionais já previstos | Não | Não |
| Confirmar importação | Sim | Sim | Sim |
| Cancelar | Não | Não | Não |

## 6. Estratégia de testes

- teste unitário de cada componente com entradas em memória;
- teste do Preview com datas, departamentos e usuários repetidos;
- teste de integração provando que simulação não altera tabelas;
- teste de segurança impedindo uso de token de simulação no upload;
- teste do fluxo definitivo provando backup, versão e atualização dos módulos.
