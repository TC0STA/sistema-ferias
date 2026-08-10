"""Rotas do módulo pesquisa."""

from flask import Blueprint

import backend
from backend import *  # noqa: F401,F403
from services.auth_service import current_user


bp = Blueprint("pesquisa", __name__)


@bp.route("/pesquisa")
def pesquisa_global():
    termo = request.args.get("q", "").strip()
    resultados = {
        "colaboradores": [],
        "organizacao": [],
        "importacoes": [],
        "calendario": [],
        "historico": [],
        "auditoria": [],
        "relatorios": [],
        "configuracoes": []
    }
    if termo:
        termo_normalizado = normalizar_texto(termo)
        todos_colaboradores = obter_colaboradores()
        colaboradores = [
            item for item in todos_colaboradores
            if termo_normalizado in normalizar_texto(item["nome"])
            or termo_normalizado in normalizar_texto(item["departamento"])
            or termo_normalizado in normalizar_texto(item["cargo"])
            or termo_normalizado in normalizar_texto(item["filial"])
        ]
        for item in colaboradores[:20]:
            resultados["colaboradores"].append({
                "titulo": item["nome"],
                "descricao": f"{item['departamento']} · {item['status']}",
                "href": f"/colaboradores/{item['slug']}"
            })
            if item["periodo_atual"]:
                resultados["calendario"].append({
                    "titulo": item["nome"],
                    "descricao": (
                        f"{item['periodo_atual']['inicio_formatado']} a "
                        f"{item['periodo_atual']['fim_formatado']}"
                    ),
                    "href": f"/calendario?busca={quote(item['nome'])}"
                })

        departamentos = sorted({
            item["departamento"] for item in todos_colaboradores
            if termo_normalizado in normalizar_texto(item["departamento"])
        })
        filiais = sorted({
            item["filial"] for item in todos_colaboradores
            if termo_normalizado in normalizar_texto(item["filial"])
        })
        for departamento in departamentos[:8]:
            total = sum(
                1 for item in todos_colaboradores
                if item["departamento"] == departamento
            )
            resultados["organizacao"].append({
                "titulo": departamento,
                "descricao": f"Departamento · {total} colaborador(es)",
                "href": f"/relatorios?departamento={quote(departamento)}"
            })
        for filial in filiais[:8]:
            total = sum(
                1 for item in todos_colaboradores
                if item["filial"] == filial
            )
            resultados["organizacao"].append({
                "titulo": filial,
                "descricao": f"Filial · {total} colaborador(es)",
                "href": "/colaboradores"
            })

        for caminho in reversed(planilhas_importadas()):
            nome_arquivo = os.path.basename(caminho)
            if termo_normalizado not in normalizar_texto(nome_arquivo):
                continue
            momento = datetime.fromtimestamp(os.path.getmtime(caminho))
            resultados["importacoes"].append({
                "titulo": nome_arquivo,
                "descricao": momento.strftime("Importada em %d/%m/%Y às %H:%M"),
                "href": "/historico"
            })
            if len(resultados["importacoes"]) == 12:
                break

        for item in obter_historico():
            texto_historico = " ".join([
                str(item["nome"]), str(item["status"]),
                str(item["data_bloqueio"]), str(item["data_execucao"])
            ])
            if termo_normalizado in normalizar_texto(texto_historico):
                resultados["historico"].append({
                    "titulo": item["nome"],
                    "descricao": f"{item['status']} em {item['data_execucao']}",
                    "href": f"/historico?busca={quote(item['nome'])}"
                })
        resultados["historico"] = resultados["historico"][:20]

        if colaboradores:
            departamentos_encontrados = sorted({
                item["departamento"] for item in colaboradores
            })
            resultados["relatorios"].append({
                "titulo": f"Relatório filtrado por “{termo}”",
                "descricao": (
                    f"{len(colaboradores)} colaborador(es) · "
                    f"{', '.join(departamentos_encontrados[:3])}"
                ),
                "href": f"/relatorios?q={quote(termo)}"
            })
        inicializar_tabelas_sistema()
        conn = sqlite3.connect(backend.DATABASE_PATH)
        logs = conn.execute(
            """
            SELECT acao, detalhe, usuario, data_hora
            FROM auditoria
            WHERE lower(acao) LIKE ? OR lower(detalhe) LIKE ?
               OR lower(usuario) LIKE ?
            ORDER BY datetime(data_hora) DESC
            LIMIT 12
            """,
            tuple([f"%{termo.lower()}%"] * 3)
        ).fetchall()
        conn.close()
        for acao, detalhe, usuario, data_hora in logs:
            try:
                momento = datetime.fromisoformat(data_hora)
                quando = momento.strftime("%d/%m às %H:%M")
            except (TypeError, ValueError):
                quando = "Data não informada"
            resultados["auditoria"].append({
                "titulo": acao,
                "descricao": f"{usuario} · {quando} · {detalhe or 'Sem detalhes'}",
                "href": f"/auditoria?q={quote(termo)}"
            })
        resultados["auditoria"] = resultados["auditoria"][:12]

        atalhos = {
            "calendario": [
                ("Calendário de férias", "Visualizar férias, inícios e retornos", "/calendario")
            ],
            "relatorios": [
                ("Relatórios gerenciais", "Indicadores e análises do período", "/relatorios"),
                ("Relatório de colaboradores", "Visão consolidada da equipe", "/relatorios?q=" + quote(termo))
            ],
            "configuracoes": [
                ("Configurações do sistema", "Preferências gerais do Fokus Férias", "/configuracoes"),
                ("Configurações de importação", "Validação, backup e processamento", "/configuracoes"),
                ("Notificações", "Alertas e preferências de comunicação", "/configuracoes"),
                ("Backup", "Proteção e recuperação dos dados", "/configuracoes#backup")
            ]
        }
        nomes_meses = [
            "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
        ]
        for indice, nome_mes in enumerate(nomes_meses, start=1):
            if termo_normalizado not in normalizar_texto(nome_mes):
                continue
            resultados["relatorios"].append({
                "titulo": f"Relatório de {nome_mes}",
                "descricao": "Indicadores mensais de férias e colaboradores",
                "href": f"/relatorios?periodo={datetime.now().year}-{indice:02d}"
            })
        for categoria, itens in atalhos.items():
            for titulo, descricao, href in itens:
                texto_pesquisavel = normalizar_texto(f"{titulo} {descricao}")
                if termo_normalizado in texto_pesquisavel:
                    resultados[categoria].append({
                        "titulo": titulo,
                        "descricao": descricao,
                        "href": href
                    })
        registrar_auditoria(
            "Realizou pesquisa global",
            f"Termo: {termo}"
        )

    profile = current_user().perfil
    if profile not in {"admin", "rh"}:
        resultados["importacoes"] = []
        resultados["historico"] = []
    if profile != "admin":
        resultados["auditoria"] = []
        resultados["configuracoes"] = []

    total_resultados = sum(len(itens) for itens in resultados.values())
    agora = datetime.now()
    return render_template(
        "pesquisa.html",
        termo=termo,
        resultados=resultados,
        total_resultados=total_resultados,
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )
