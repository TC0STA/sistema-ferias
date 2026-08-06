"""Rotas do módulo pesquisa."""

from flask import Blueprint

import backend
from backend import *  # noqa: F401,F403


bp = Blueprint("pesquisa", __name__)


@bp.route("/pesquisa")
def pesquisa_global():
    termo = request.args.get("q", "").strip()
    resultados = {
        "colaboradores": [],
        "calendario": [],
        "historico": [],
        "relatorios": []
    }
    if termo:
        termo_normalizado = normalizar_texto(termo)
        colaboradores = [
            item for item in obter_colaboradores()
            if termo_normalizado in normalizar_texto(item["nome"])
            or termo_normalizado in normalizar_texto(item["departamento"])
            or termo_normalizado in normalizar_texto(item["cargo"])
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

        for item in obter_historico():
            if termo_normalizado in normalizar_texto(item["nome"]):
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
            resultados["historico"].append({
                "titulo": acao,
                "descricao": f"{usuario} · {quando} · {detalhe or 'Sem detalhes'}",
                "href": f"/auditoria?q={quote(termo)}"
            })
        resultados["historico"] = resultados["historico"][:20]
        registrar_auditoria(
            "Realizou pesquisa global",
            f"Termo: {termo}"
        )

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
