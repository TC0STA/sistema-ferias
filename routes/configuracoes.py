"""Rotas do módulo configuracoes."""

from flask import Blueprint

import backend
from backend import *  # noqa: F401,F403


bp = Blueprint("configuracoes", __name__)


@bp.route("/auditoria")
def auditoria():
    inicializar_tabelas_sistema()
    pesquisa = request.args.get("q", "").strip()
    acao_filtro = request.args.get("acao", "").strip()
    usuario_filtro = request.args.get("usuario", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()
    conn = sqlite3.connect(backend.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    consulta = """
        SELECT id, data_hora, acao, detalhe, usuario, ip, resultado
        FROM auditoria WHERE 1=1
    """
    parametros = []
    if pesquisa:
        consulta += " AND (acao LIKE ? OR detalhe LIKE ? OR usuario LIKE ? OR ip LIKE ?)"
        termo = f"%{pesquisa}%"
        parametros.extend([termo, termo, termo, termo])
    if acao_filtro:
        consulta += " AND acao = ?"
        parametros.append(acao_filtro)
    if usuario_filtro:
        consulta += " AND usuario = ?"
        parametros.append(usuario_filtro)
    if data_inicio:
        consulta += " AND substr(data_hora, 1, 10) >= ?"
        parametros.append(data_inicio)
    if data_fim:
        consulta += " AND substr(data_hora, 1, 10) <= ?"
        parametros.append(data_fim)
    consulta += " ORDER BY datetime(data_hora) DESC LIMIT 300"
    registros = conn.execute(consulta, parametros).fetchall()
    acoes = [
        item[0] for item in conn.execute(
            "SELECT DISTINCT acao FROM auditoria ORDER BY acao"
        ).fetchall()
    ]
    usuarios = [
        item[0] for item in conn.execute(
            "SELECT DISTINCT usuario FROM auditoria ORDER BY usuario"
        ).fetchall()
    ]
    total = conn.execute("SELECT COUNT(*) FROM auditoria").fetchone()[0]
    hoje_iso = datetime.now().strftime("%Y-%m-%d")
    hoje_total = conn.execute(
        "SELECT COUNT(*) FROM auditoria WHERE substr(data_hora, 1, 10) = ?",
        (hoje_iso,)
    ).fetchone()[0]
    conn.close()

    dados = []
    for item in registros:
        try:
            momento = datetime.fromisoformat(item["data_hora"])
        except (TypeError, ValueError):
            momento = datetime.now()
        dados.append({
            "id": item["id"],
            "data": momento.strftime("%d/%m/%Y"),
            "hora": momento.strftime("%H:%M"),
            "acao": item["acao"],
            "detalhe": item["detalhe"] or "Sem detalhes adicionais",
            "usuario": item["usuario"],
            "ip": item["ip"] or "Não registrado",
            "resultado": item["resultado"] or "Sucesso"
        })

    agora = datetime.now()
    return render_template(
        "auditoria.html",
        registros=dados,
        acoes=acoes,
        usuarios=usuarios,
        pesquisa=pesquisa,
        acao_filtro=acao_filtro,
        usuario_filtro=usuario_filtro,
        data_inicio=data_inicio,
        data_fim=data_fim,
        total=total,
        hoje_total=hoje_total,
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/configuracoes", methods=["GET", "POST"])
def configuracoes():
    erro = None
    if request.method == "POST":
        hora_rotina = request.form.get("hora_rotina", "08:00").strip()
        dias_antes = request.form.get("dias_antes_bloqueio", "3").strip()
        pasta_padrao = request.form.get("pasta_padrao", "").strip()
        manter_backups = request.form.get("manter_backups", "10").strip()
        try:
            datetime.strptime(hora_rotina, "%H:%M")
            dias_numero = int(dias_antes)
            manter_numero = int(manter_backups)
            if not 0 <= dias_numero <= 30:
                raise ValueError
            if not pasta_padrao or not 1 <= manter_numero <= 100:
                raise ValueError
        except ValueError:
            erro = "Revise os valores. A antecedência deve estar entre 0 e 30 dias."
        else:
            caixas = {
                "notificacoes_ativas", "som_notificacoes",
                "substituir_planilha", "validar_planilha",
                "mostrar_resumo_importacao", "backup_antes_importacao",
                "mostrar_popup", "notificar_importacao",
                "pdf_logo", "pdf_rodape", "pdf_numero_pagina", "pdf_data",
                "excel_autofiltro", "excel_ajustar_colunas",
                "excel_congelar_cabecalho",
                "limpeza_backups"
            }
            valores = {
                "nome_empresa": request.form.get(
                    "nome_empresa", "Grupo Fokus Logística"
                ).strip(),
                "nome_sistema": request.form.get(
                    "nome_sistema", "Fokus Férias"
                ).strip(),
                "versao": request.form.get("versao", "2.0").strip(),
                "banco": request.form.get("banco", "SQLite").strip(),
                "ambiente": request.form.get("ambiente", "Produção").strip(),
                "hora_rotina": hora_rotina,
                "dias_antes_bloqueio": str(dias_numero),
                "pasta_padrao": pasta_padrao,
                "tema": request.form.get("tema", "claro"),
                "cor_principal": request.form.get(
                    "cor_principal", "azul-fokus"
                ),
                "tamanho_fonte": request.form.get("tamanho_fonte", "normal"),
                "manter_backups": str(manter_numero),
            }
            valores.update({
                chave: "1" if request.form.get(chave) == "1" else "0"
                for chave in caixas
            })
            inicializar_tabelas_sistema()
            conn = sqlite3.connect(backend.DATABASE_PATH)
            anteriores = dict(
                conn.execute("SELECT chave, valor FROM configuracoes").fetchall()
            )
            agora_iso = datetime.now().isoformat()
            for chave, valor in valores.items():
                conn.execute(
                    """
                    INSERT INTO configuracoes (chave, valor, atualizado_em)
                    VALUES (?, ?, ?)
                    ON CONFLICT(chave) DO UPDATE SET
                        valor=excluded.valor,
                        atualizado_em=excluded.atualizado_em
                    """,
                    (chave, valor, agora_iso)
                )
            conn.commit()
            conn.close()
            alteracoes = [
                chave for chave, valor in valores.items()
                if anteriores.get(chave) != valor
            ]
            nomes_campos = {
                "hora_rotina": "horário",
                "pasta_padrao": "pasta de importação",
                "dias_antes_bloqueio": "antecedência das notificações",
                "tema": "tema",
                "cor_principal": "cor principal",
                "tamanho_fonte": "tamanho da interface"
            }
            if alteracoes:
                resumo = ", ".join(
                    nomes_campos.get(chave, chave.replace("_", " "))
                    for chave in alteracoes[:5]
                )
                registrar_auditoria(
                    "Alterou configurações",
                    f"Campos alterados: {resumo}"
                )
            return redirect(url_for("configuracoes", salvo="1"))

    agora = datetime.now()
    backups = listar_backups()
    ultimo_backup = None
    if backups:
        momento = datetime.fromtimestamp(os.path.getmtime(backups[0]))
        ultimo_backup = {
            "data": momento.strftime("%d/%m/%Y"),
            "hora": momento.strftime("%H:%M"),
            "nome": os.path.basename(backups[0])
        }
    inicializar_tabelas_sistema()
    conn = sqlite3.connect(backend.DATABASE_PATH)
    historico_configuracoes = conn.execute(
        """
        SELECT data_hora, detalhe, usuario
        FROM auditoria
        WHERE acao = 'Alterou configurações'
        ORDER BY datetime(data_hora) DESC
        LIMIT 6
        """
    ).fetchall()
    conn.close()
    historico = []
    for data_hora, detalhe, usuario in historico_configuracoes:
        try:
            momento = datetime.fromisoformat(data_hora)
        except (TypeError, ValueError):
            momento = agora
        historico.append({
            "data": momento.strftime("%d/%m"),
            "hora": momento.strftime("%H:%M"),
            "detalhe": detalhe,
            "usuario": usuario
        })
    return render_template(
        "configuracoes.html",
        configuracoes=carregar_configuracoes(),
        ultimo_backup=ultimo_backup,
        historico_configuracoes=historico,
        saude_sistema=obter_saude_sistema(),
        salvo=request.args.get("salvo") == "1",
        restaurado=request.args.get("restaurado") == "1",
        padrao_restaurado=request.args.get("padrao") == "1",
        teste_notificacao=request.args.get("teste_notificacao") == "1",
        backups_limpos=request.args.get("backups_limpos"),
        historico_limpo=request.args.get("historico_limpo"),
        erro_backup=request.args.get("erro_backup"),
        erro=erro,
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/backup/gerar", methods=["POST"])
def gerar_backup():
    caminho_backup = criar_backup("manual")
    nome_arquivo = os.path.basename(caminho_backup)
    return send_file(
        caminho_backup,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/zip"
    )


@bp.route("/backup/limpar", methods=["POST"])
def limpar_backups():
    removidos = limpar_backups_antigos()
    registrar_auditoria(
        "Limpou backups antigos",
        f"{removidos} arquivo(s) removido(s)"
    )
    return redirect(url_for("configuracoes", backups_limpos=str(removidos)))


@bp.route("/configuracoes/restaurar-padrao", methods=["POST"])
def restaurar_configuracoes_padrao():
    inicializar_tabelas_sistema()
    conn = sqlite3.connect(backend.DATABASE_PATH)
    agora_iso = datetime.now().isoformat()
    for chave, valor in backend.CONFIGURACOES_PADRAO.items():
        conn.execute(
            """
            INSERT INTO configuracoes (chave, valor, atualizado_em)
            VALUES (?, ?, ?)
            ON CONFLICT(chave) DO UPDATE SET
                valor=excluded.valor, atualizado_em=excluded.atualizado_em
            """,
            (chave, valor, agora_iso)
        )
    conn.commit()
    conn.close()
    registrar_auditoria(
        "Alterou configurações",
        "Restaurou todas as configurações padrão"
    )
    return redirect(url_for("configuracoes", padrao="1"))


@bp.route("/configuracoes/testar-notificacao", methods=["POST"])
def testar_notificacao():
    registrar_auditoria(
        "Testou notificações",
        "Central de notificações respondeu corretamente"
    )
    return redirect(url_for("configuracoes", teste_notificacao="1"))


@bp.route("/configuracoes/limpar-historico", methods=["POST"])
def limpar_historico_configuracoes():
    try:
        dias = int(request.form.get("dias", "90"))
    except ValueError:
        dias = 90
    if dias not in {30, 90, 180}:
        dias = 90
    limite = (datetime.now() - timedelta(days=dias)).isoformat()
    inicializar_tabelas_sistema()
    conn = sqlite3.connect(backend.DATABASE_PATH)
    cursor = conn.execute(
        """
        DELETE FROM auditoria
        WHERE acao = 'Alterou configurações' AND data_hora < ?
        """,
        (limite,)
    )
    removidos = cursor.rowcount
    conn.commit()
    conn.close()
    registrar_auditoria(
        "Limpou histórico de configurações",
        f"Período: {dias} dias · {removidos} registro(s) removido(s)"
    )
    return redirect(url_for(
        "configuracoes", historico_limpo=str(removidos)
    ))


@bp.route("/backup/restaurar", methods=["POST"])
def restaurar_backup():
    arquivo = request.files.get("backup")
    if not arquivo or not arquivo.filename.lower().endswith((".zip", ".db")):
        return redirect(url_for("configuracoes", erro_backup="arquivo"))
    try:
        criar_backup("pré-restauração")
        banco_temporario = backend.DATABASE_PATH + ".restauracao"
        if arquivo.filename.lower().endswith(".db"):
            with open(banco_temporario, "wb") as destino:
                destino.write(arquivo.read())
        else:
            conteudo = BytesIO(arquivo.read())
            with zipfile.ZipFile(conteudo) as pacote:
                if "database/ferias.db" not in pacote.namelist():
                    raise ValueError
                with open(banco_temporario, "wb") as destino:
                    destino.write(pacote.read("database/ferias.db"))
        teste_conn = sqlite3.connect(banco_temporario)
        integridade = teste_conn.execute("PRAGMA integrity_check").fetchone()[0]
        teste_conn.close()
        if integridade != "ok":
            raise ValueError
        os.replace(banco_temporario, backend.DATABASE_PATH)
        inicializar_tabelas_sistema()
        registrar_auditoria(
            "Restaurou backup",
            f"Arquivo: {os.path.basename(arquivo.filename)}"
        )
    except (zipfile.BadZipFile, KeyError, ValueError, OSError, sqlite3.Error):
        if os.path.exists(backend.DATABASE_PATH + ".restauracao"):
            os.remove(backend.DATABASE_PATH + ".restauracao")
        registrar_auditoria(
            "Restaurou backup",
            f"Falha no arquivo: {os.path.basename(arquivo.filename)}",
            resultado="Falha"
        )
        return redirect(url_for("configuracoes", erro_backup="invalido"))
    return redirect(url_for("configuracoes", restaurado="1"))


@bp.route("/sobre")
def sobre():
    agora = datetime.now()
    return render_template(
        "sobre.html",
        configuracoes=carregar_configuracoes(),
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/manutencao")
def manutencao():
    return render_template(
        "estado_sistema.html",
        codigo="FOKUS FÉRIAS",
        titulo="Estamos realizando uma atualização",
        mensagem="Voltaremos em instantes. Esta página será atualizada automaticamente.",
        acao_href=None,
        acao_icone=None,
        acao_texto=None,
        atualizar=True
    ), 503


@bp.before_app_request
def verificar_modo_manutencao():
    if (
        os.environ.get("FOKUS_MODO_MANUTENCAO") == "1"
        and request.endpoint not in {"manutencao", "static"}
    ):
        return manutencao()


@bp.app_errorhandler(404)
def pagina_nao_encontrada(_erro):
    return render_template(
        "estado_sistema.html",
        codigo="404",
        titulo="Página não encontrada",
        mensagem="O endereço informado não existe ou foi movido.",
        acao_href=url_for("dashboard"),
        acao_icone="layout-dashboard",
        acao_texto="Voltar ao Dashboard",
        atualizar=False
    ), 404
