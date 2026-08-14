# Migração dos usuários para PostgreSQL

Em produção no Render, `DATABASE_URL` é a única fonte de usuários. O arquivo
`database/usuarios.db` continua disponível apenas no desenvolvimento local e
como backup temporário; a aplicação em produção não lê nem grava esse arquivo.

## Variáveis no Render

- `DATABASE_URL`: URI de conexão PostgreSQL fornecida pelo Supabase. Use a URI
  do pooler indicada no painel e mantenha `sslmode=require` quando fornecido.
- `FOKUS_SECRET_KEY`: segredo aleatório longo e estável para assinar as sessões.

Não configure `USER_DATABASE_PATH` no Render e não salve nenhuma dessas
variáveis no repositório.

## Migração única

Faça um backup de `database/usuarios.db`. Em uma máquina que tenha acesso ao
projeto e ao Supabase, instale `requirements.txt`, defina `DATABASE_URL` apenas
na sessão do terminal e execute:

```powershell
python scripts/migrar_usuarios_postgresql.py --sqlite database/usuarios.db
```

O processo cria a tabela se necessário, exige que o destino esteja vazio,
confere a existência de um administrador ativo, copia IDs e hashes de senha em
uma única transação e mantém o SQLite intacto. Depois, configure no Render a
mesma `DATABASE_URL` e faça o deploy. Valide o login do administrador antes de
arquivar o backup.

Se a tabela PostgreSQL já tiver usuários, o script cancela sem copiar nada. Ele
não sincroniza os dois bancos e nunca grava no SQLite.
