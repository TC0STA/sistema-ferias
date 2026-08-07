"""Rotas do módulo dashboard."""

from flask import Blueprint

import backend
from backend import *  # noqa: F401,F403


bp = Blueprint("dashboard", __name__)


@bp.app_context_processor
def contexto_notificacoes():
    hoje = datetime.now().date()
    amanha = hoje + timedelta(days=1)
    notificacoes = []
    caminhos = planilhas_importadas()
    configuracoes = carregar_configuracoes()

    if configuracoes.get("notificacoes_ativas") != "1":
        return {
            "notificacoes_topo": [],
            "notificacoes_total": 0,
            "versao_sistema": configuracoes.get("versao", "2.0"),
            "ultima_atualizacao_sistema": "27/07/2026",
            "mostrar_popup_notificacoes": False,
            "som_notificacoes_ativo": False,
            "notificacao_em_teste": False
        }

    if caminhos:
        caminho = caminhos[-1]
        try:
            df = carregar_planilhas(caminhos)
            linhas_bloqueio = df[df["Data de Bloqueio"].dt.date == hoje]
            linhas_amanha = df[df["Inicio"].dt.date == amanha]
            hora_rotina = configuracoes["hora_rotina"]
            if len(linhas_bloqueio):
                notificacoes.append({
                    "tipo": "danger",
                    "icone": "lock-keyhole",
                    "rotulo": "Bloquear hoje",
                    "titulo": f"{len(linhas_bloqueio)} colaborador(es) precisam ser bloqueados hoje.",
                    "descricao": "Usuários aguardando bloqueio de acesso.",
                    "href": "/dashboard#alertas",
                    "itens": [
                        {"nome": str(item["Nome"]), "meta": hora_rotina}
                        for _, item in linhas_bloqueio.head(5).iterrows()
                    ]
                })
            if len(linhas_amanha):
                notificacoes.append({
                    "tipo": "warning",
                    "icone": "calendar-clock",
                    "rotulo": "Próximas férias",
                    "titulo": f"{len(linhas_amanha)} colaborador(es) iniciam férias amanhã.",
                    "descricao": "Confira os colaboradores programados.",
                    "href": "/calendario",
                    "itens": [
                        {"nome": str(item["Nome"]), "meta": amanha.strftime("%d/%m")}
                        for _, item in linhas_amanha.head(5).iterrows()
                    ]
                })
        except (ValueError, OSError, KeyError):
            pass

        if configuracoes.get("notificar_importacao") == "1":
            notificacoes.append({
                "tipo": "success",
                "icone": "file-check-2",
                "rotulo": "Importação",
                "titulo": "Nova planilha importada.",
                "descricao": datetime.fromtimestamp(
                    os.path.getmtime(caminho)
                ).strftime("Planilha atualizada em %d/%m às %H:%M."),
                "href": "/dashboard",
                "itens": [{
                    "nome": os.path.basename(caminho),
                    "meta": datetime.fromtimestamp(
                        os.path.getmtime(caminho)
                    ).strftime("%H:%M")
                }]
            })

    backups = listar_backups()
    if backups:
        momento_backup = datetime.fromtimestamp(os.path.getmtime(backups[0]))
        notificacoes.append({
            "tipo": "success",
            "icone": "database-backup",
            "rotulo": "Backup concluído",
            "titulo": "Os dados do sistema estão protegidos.",
            "descricao": momento_backup.strftime(
                "Último backup em %d/%m/%Y às %H:%M."
            ),
            "href": "/configuracoes#backup",
            "itens": []
        })

    if request.args.get("teste_notificacao") == "1":
        notificacoes.insert(0, {
            "tipo": "success",
            "icone": "badge-check",
            "rotulo": "Notificação de teste",
            "titulo": "Sistema funcionando corretamente",
            "descricao": "A central de notificações está pronta para uso.",
            "href": "/configuracoes",
            "itens": []
        })

    return {
        "notificacoes_topo": notificacoes,
        "notificacoes_total": len(notificacoes),
        "versao_sistema": configuracoes.get("versao", "2.0"),
        "ultima_atualizacao_sistema": "27/07/2026",
        "mostrar_popup_notificacoes": configuracoes.get("mostrar_popup") == "1",
        "som_notificacoes_ativo": configuracoes.get("som_notificacoes") == "1",
        "notificacao_em_teste": request.args.get("teste_notificacao") == "1"
    }


@bp.route("/")
def index():
    agora = datetime.now()
    inteligencia = obter_inteligencia_sistema()
    return render_template(
        "inicio.html",
        resumo=obter_resumo_sistema(),
        timeline=obter_timeline_sistema(8),
        inteligencia=inteligencia,
        saude_sistema=obter_saude_sistema(),
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/alertas")
def centro_alertas():
    agora = datetime.now()
    return render_template(
        "inteligencia_painel.html",
        painel="alertas",
        dados=obter_inteligencia_sistema(),
        timeline=obter_timeline_sistema(8),
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/operacoes")
def centro_operacoes():
    agora = datetime.now()
    return render_template(
        "inteligencia_painel.html",
        painel="operacoes",
        dados=obter_inteligencia_sistema(),
        timeline=obter_timeline_sistema(10),
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/dashboard/<tipo>")
def dashboard_especializado(tipo):
    if tipo not in {"executivo", "rh", "ti"}:
        return redirect(url_for("dashboard"))
    agora = datetime.now()
    return render_template(
        "inteligencia_painel.html",
        painel=tipo,
        dados=obter_inteligencia_sistema(),
        timeline=obter_timeline_sistema(10),
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/dashboard")
def dashboard():

    agora = datetime.now()
    data_atual = agora.strftime("%d/%m/%Y %H:%M")
    data_hoje = agora.strftime("%d/%m/%Y")
    resumo_inteligente = obter_resumo_sistema()
    timeline_sistema = obter_timeline_sistema()

    caminhos = planilhas_importadas()
    caminho = planilha_mais_recente()

    if not caminhos:
        return render_template(
            "dashboard.html",
            hoje=[],
            proximos=[],
            bloqueados=[],
            todos=[],
            em_ferias=[],
            bloqueios_hoje_total=0,
            labels=[],
            valores=[],
            data_atual=data_atual,
            data_hoje=data_hoje,
            resumo_inteligente=resumo_inteligente,
            timeline_sistema=timeline_sistema,
            planilha_nome="Nenhuma planilha importada",
            ultima_importacao="Sem importação"
        )

    try:
        df = carregar_planilhas(caminhos)
    except ValueError as erro:
        return str(erro)

    hoje = datetime.now().date()

    # 🔴 HOJE (inclui bloqueios marcados e quem inicia férias hoje)
    hoje_lista = df[
        (
            df["Data de Bloqueio"].dt.date == hoje
        ) |
        (
            df["Inicio"].dt.date == hoje
        )
    ]
    bloqueios_hoje_total = int(
        (df["Data de Bloqueio"].dt.date == hoje).sum()
    )

    # 🟡 PRÓXIMOS DIAS
    proximos = df[
        (
            df["Data de Bloqueio"].dt.date > hoje
        ) &
        (
            df["Data de Bloqueio"].dt.date
            <= hoje + pd.Timedelta(days=3)
        )
    ]

    em_ferias = df[
        (
            df["Inicio"].dt.date <= hoje
        ) &
        (
            df["Fim"].dt.date >= hoje
        )
    ]

    grafico = (
        df.dropna(subset=["Data de Bloqueio"])
        .groupby(df["Data de Bloqueio"].dt.strftime("%d/%m/%Y"))
        .size()
        .sort_index()
    )

    labels = grafico.index.tolist()
    valores = grafico.values.tolist()

    hoje_lista = formatar_datas(hoje_lista)
    proximos = formatar_datas(proximos)
    em_ferias = formatar_datas(em_ferias)
    df = formatar_datas(df)

    # 🟢 HISTÓRICO
    conn = sqlite3.connect(backend.DATABASE_PATH)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bloqueios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            data_bloqueio TEXT,
            data_execucao TEXT
        )
    """)

    cursor.execute(
        "SELECT nome FROM bloqueios"
    )

    bloqueados = [
        x[0]
        for x in cursor.fetchall()
    ]

    conn.close()

    planilha_nome = os.path.basename(caminho)
    ultima_importacao = datetime.fromtimestamp(
        os.path.getmtime(caminho)
    ).strftime("%d/%m/%Y %H:%M")

    return render_template(
        "dashboard.html",
        hoje=hoje_lista.to_dict(orient="records"),
        proximos=proximos.to_dict(orient="records"),
        bloqueados=bloqueados,
        todos=df.to_dict(orient="records"),
        em_ferias=em_ferias.to_dict(orient="records"),
        bloqueios_hoje_total=bloqueios_hoje_total,
        labels=labels,
        valores=valores,
        data_atual=data_atual,
        data_hoje=data_hoje,
        resumo_inteligente=resumo_inteligente,
        timeline_sistema=timeline_sistema,
        planilha_nome=planilha_nome,
        ultima_importacao=ultima_importacao
    )


@bp.route("/detalhe/<secao>")
def detalhe(secao):

    caminhos = planilhas_importadas()

    if not caminhos:
        # para bloqueados ainda vamos buscar do banco
        if secao == "bloqueados":
            conn = sqlite3.connect(backend.DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT nome FROM bloqueios")
            bloqueados = [x[0] for x in cursor.fetchall()]
            conn.close()
            return render_template("detalhe.html", secao=secao, items=bloqueados)

        return render_template("detalhe.html", secao=secao, items=[])

    try:
        df = carregar_planilhas(caminhos)
    except ValueError:
        return render_template("detalhe.html", secao=secao, items=[])

    hoje = datetime.now().date()

    hoje_lista = df[
        (
            df["Data de Bloqueio"].dt.date == hoje
        ) |
        (
            df["Inicio"].dt.date == hoje
        )
    ]

    proximos = df[
        (
            df["Data de Bloqueio"].dt.date > hoje
        ) &
        (
            df["Data de Bloqueio"].dt.date
            <= hoje + pd.Timedelta(days=3)
        )
    ]

    df = formatar_datas(df)
    hoje_lista = formatar_datas(hoje_lista)
    proximos = formatar_datas(proximos)

    # histórico bloqueados
    conn = sqlite3.connect(backend.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS bloqueios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, data_bloqueio TEXT, data_execucao TEXT)")
    cursor.execute("SELECT nome FROM bloqueios")
    bloqueados = [x[0] for x in cursor.fetchall()]
    conn.close()

    mapping = {
        'hoje': hoje_lista.to_dict(orient='records'),
        'proximos': proximos.to_dict(orient='records'),
        'bloqueados': bloqueados,
        'todos': df.to_dict(orient='records')
    }

    items = mapping.get(secao, [])

    return render_template('detalhe.html', secao=secao, items=items)


@bp.route("/calendario")
def calendario():
    agora = datetime.now()
    mes_parametro = request.args.get("mes", agora.strftime("%Y-%m"))

    try:
        ano, mes = [int(parte) for parte in mes_parametro.split("-", 1)]
        primeiro_dia = datetime(ano, mes, 1).date()
    except (TypeError, ValueError):
        primeiro_dia = agora.date().replace(day=1)
        ano, mes = primeiro_dia.year, primeiro_dia.month

    if mes == 12:
        proximo_primeiro = datetime(ano + 1, 1, 1).date()
    else:
        proximo_primeiro = datetime(ano, mes + 1, 1).date()
    ultimo_dia = proximo_primeiro - timedelta(days=1)
    mes_anterior = (primeiro_dia - timedelta(days=1)).replace(day=1)

    ferias = []
    caminhos = planilhas_importadas()
    if caminhos:
        try:
            df = carregar_planilhas(caminhos)
            coluna_departamento = encontrar_coluna(
                df,
                ["departamento", "depto / setor", "depto", "setor"]
            )
            coluna_filial = encontrar_coluna(
                df,
                ["filial", "unidade"]
            )
            df_mes = df[
                (df["Inicio"].dt.date <= ultimo_dia)
                & (df["Fim"].dt.date >= primeiro_dia)
            ].copy()

            for indice, (_, linha) in enumerate(df_mes.sort_values("Inicio").iterrows()):
                inicio = linha["Inicio"].date()
                fim = linha["Fim"].date()
                if inicio <= agora.date() <= fim:
                    status = "Em férias"
                    status_classe = "active"
                elif inicio > agora.date():
                    status = "Programada"
                    status_classe = "scheduled"
                else:
                    status = "Concluída"
                    status_classe = "completed"

                nome = str(linha["Nome"])
                departamento = (
                    str(linha[coluna_departamento]).strip()
                    if coluna_departamento
                    and pd.notna(linha[coluna_departamento])
                    else "Não informado"
                )
                filial = (
                    str(linha[coluna_filial]).strip()
                    if coluna_filial
                    and pd.notna(linha[coluna_filial])
                    else "Não informada"
                )
                bloqueio = (
                    linha["Data de Bloqueio"].date()
                    if pd.notna(linha["Data de Bloqueio"])
                    else None
                )
                ferias.append({
                    "id": indice,
                    "nome": nome,
                    "departamento": departamento,
                    "filial": filial,
                    "inicio": inicio,
                    "fim": fim,
                    "bloqueio": bloqueio,
                    "inicio_formatado": inicio.strftime("%d/%m/%Y"),
                    "fim_formatado": fim.strftime("%d/%m/%Y"),
                    "bloqueio_formatado": bloqueio.strftime("%d/%m/%Y") if bloqueio else "-",
                    "periodo_curto": f"{inicio:%d/%m} - {fim:%d/%m}",
                    "status": status,
                    "status_classe": status_classe,
                    "cor": sum(ord(letra) for letra in nome) % 4
                })
        except ValueError:
            ferias = []

    calendario_base = calendar_module.Calendar(firstweekday=0)
    semanas = []
    for semana in calendario_base.monthdatescalendar(ano, mes):
        dias = []
        for data in semana:
            eventos = [
                evento for evento in ferias
                if evento["inicio"] <= data <= evento["fim"]
            ]
            dias.append({
                "data": data,
                "numero": data.day,
                "mes_atual": data.month == mes,
                "hoje": data == agora.date(),
                "eventos": eventos
            })
        semanas.append(dias)

    nomes_meses = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    agenda = sorted(
        ferias,
        key=lambda item: (
            item["inicio"] < agora.date(),
            item["inicio"]
        )
    )[:6]

    return render_template(
        "calendario.html",
        semanas=semanas,
        ferias=ferias,
        ferias_json=[
            {
                "id": item["id"],
                "nome": item["nome"],
                "departamento": item["departamento"],
                "filial": item["filial"],
                "inicio": item["inicio_formatado"],
                "fim": item["fim_formatado"],
                "bloqueio": item["bloqueio_formatado"],
                "status": item["status"],
                "status_classe": item["status_classe"],
                "cor": item["cor"]
            }
            for item in ferias
        ],
        agenda=agenda,
        mes_nome=nomes_meses[mes],
        ano=ano,
        mes_parametro=f"{ano}-{mes:02d}",
        mes_anterior=mes_anterior.strftime("%Y-%m"),
        proximo_mes=proximo_primeiro.strftime("%Y-%m"),
        ferias_hoje=sum(1 for item in ferias if item["status_classe"] == "active"),
        proximas=sum(1 for item in ferias if item["status_classe"] == "scheduled"),
        iniciando_hoje=sum(1 for item in ferias if item["inicio"] == agora.date()),
        finalizando_hoje=sum(1 for item in ferias if item["fim"] == agora.date()),
        colaboradores=len({item["nome"] for item in ferias}),
        busca=request.args.get("busca", ""),
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/calendario/exportar/pdf")
def exportar_calendario_pdf():
    agora = datetime.now()
    mes_parametro = request.args.get("mes", agora.strftime("%Y-%m"))
    try:
        ano, mes = [int(parte) for parte in mes_parametro.split("-", 1)]
        primeiro_dia = datetime(ano, mes, 1).date()
    except (TypeError, ValueError):
        primeiro_dia = agora.date().replace(day=1)
        ano, mes = primeiro_dia.year, primeiro_dia.month
    proximo_primeiro = (
        datetime(ano + 1, 1, 1).date()
        if mes == 12
        else datetime(ano, mes + 1, 1).date()
    )
    ultimo_dia = proximo_primeiro - timedelta(days=1)
    ferias = []
    for colaborador in obter_colaboradores():
        for periodo in colaborador["periodos"]:
            if periodo["inicio"] <= ultimo_dia and periodo["fim"] >= primeiro_dia:
                ferias.append({
                    "nome": colaborador["nome"],
                    "departamento": colaborador["departamento"],
                    "inicio_formatado": periodo["inicio_formatado"],
                    "fim_formatado": periodo["fim_formatado"],
                    "bloqueio_formatado": periodo["bloqueio_formatado"],
                    "status": (
                        "Em ferias"
                        if periodo["inicio"] <= agora.date() <= periodo["fim"]
                        else "Programada"
                        if periodo["inicio"] > agora.date()
                        else "Concluida"
                    )
                })
    nomes_meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    registrar_auditoria(
        "Gerou PDF",
        f"Calendário de férias · {nomes_meses[mes]}/{ano}"
    )
    arquivo = BytesIO(gerar_pdf_calendario(ferias, nomes_meses[mes], ano))
    return send_file(
        arquivo,
        as_attachment=True,
        download_name=f"calendario_ferias_{ano}_{mes:02d}.pdf",
        mimetype="application/pdf"
    )


@bp.route("/colaboradores")
def colaboradores():
    dados = obter_colaboradores()
    agora = datetime.now()
    return render_template(
        "colaboradores.html",
        colaboradores=dados,
        total=len(dados),
        em_ferias=sum(1 for item in dados if item["status_classe"] == "active"),
        programadas=sum(1 for item in dados if item["status_classe"] == "scheduled"),
        departamentos=sorted({
            item["departamento"] for item in dados
            if item["departamento"] != "Não informado"
        }),
        total_departamentos=len({
            item["departamento"] for item in dados
            if item["departamento"] != "Não informado"
        }),
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/colaboradores/<path:nome>")
def colaborador_detalhe(nome):
    colaborador = next(
        (item for item in obter_colaboradores() if normalizar_texto(item["nome"]) == normalizar_texto(nome)),
        None
    )
    if colaborador is None:
        return "Colaborador não encontrado.", 404

    conn = sqlite3.connect(backend.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT data_bloqueio, data_execucao
        FROM bloqueios
        WHERE lower(nome) = lower(?)
        ORDER BY datetime(data_execucao) DESC
    """, (colaborador["nome"],))
    bloqueios = cursor.fetchall()
    conn.close()

    historico_bloqueios = []
    acoes = []
    for data_bloqueio, data_execucao in bloqueios:
        try:
            bloqueio_dt = datetime.fromisoformat(str(data_bloqueio))
        except (TypeError, ValueError):
            bloqueio_dt = None
        try:
            execucao_dt = datetime.fromisoformat(str(data_execucao))
        except (TypeError, ValueError):
            execucao_dt = None
        historico_bloqueios.append({
            "data_bloqueio": bloqueio_dt.strftime("%d/%m/%Y") if bloqueio_dt else str(data_bloqueio or "-"),
            "data_execucao": execucao_dt.strftime("%d/%m/%Y %H:%M") if execucao_dt else str(data_execucao or "-")
        })
        if execucao_dt:
            acoes.append({
                "data": execucao_dt,
                "titulo": "Bloqueio executado",
                "descricao": f"Acesso bloqueado em {execucao_dt:%d/%m/%Y às %H:%M}",
                "tipo": "success"
            })

    for periodo in colaborador["periodos"]:
        acoes.extend([
            {
                "data": datetime.combine(periodo["inicio"], datetime.min.time()),
                "titulo": "Início das férias",
                "descricao": f"Período iniciado em {periodo['inicio_formatado']}",
                "tipo": "vacation"
            },
            {
                "data": datetime.combine(periodo["bloqueio"], datetime.min.time()) if periodo["bloqueio"] else datetime.combine(periodo["inicio"], datetime.min.time()),
                "titulo": "Bloqueio programado",
                "descricao": f"Bloqueio previsto para {periodo['bloqueio_formatado']}",
                "tipo": "scheduled"
            }
        ])

    anos = {}
    for periodo in colaborador["periodos"]:
        anos.setdefault(periodo["inicio"].year, []).append(periodo)

    agora = datetime.now()
    return render_template(
        "colaborador_detalhe.html",
        colaborador=colaborador,
        anos=sorted(anos.items(), reverse=True),
        historico_bloqueios=historico_bloqueios,
        acoes=sorted(acoes, key=lambda item: item["data"], reverse=True)[:6],
        editar=request.args.get("editar") == "1",
        salvo=request.args.get("salvo") == "1",
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/colaboradores/<path:nome>/editar", methods=["POST"])
def colaborador_editar(nome):
    colaborador = next(
        (item for item in obter_colaboradores() if normalizar_texto(item["nome"]) == normalizar_texto(nome)),
        None
    )
    if colaborador is None:
        return "Colaborador não encontrado.", 404

    conn = sqlite3.connect(backend.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO colaborador_perfis
        (nome, departamento, cargo, matricula, filial, atualizado_em)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(nome) DO UPDATE SET
            departamento=excluded.departamento,
            cargo=excluded.cargo,
            matricula=excluded.matricula,
            filial=excluded.filial,
            atualizado_em=excluded.atualizado_em
    """, (
        colaborador["nome"],
        request.form.get("departamento", "").strip(),
        request.form.get("cargo", "").strip(),
        request.form.get("matricula", "").strip(),
        request.form.get("filial", "").strip(),
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    registrar_auditoria(
        "Editou colaborador",
        f"Perfil atualizado: {colaborador['nome']}"
    )
    return redirect(url_for("colaborador_detalhe", nome=colaborador["nome"], salvo="1"))


@bp.route("/api/versao-dados")
def versao_dados():
    caminho = planilha_mais_recente()
    if not caminho or not os.path.exists(caminho):
        return {"versao": "sem-planilha"}
    estado = os.stat(caminho)
    return {
        "versao": f"{estado.st_mtime_ns}-{estado.st_size}",
        "atualizado_em": datetime.fromtimestamp(
            estado.st_mtime
        ).isoformat(timespec="seconds")
    }


@bp.route('/imagens/<path:filename>')
def imagens(filename):
    return send_from_directory('Imagens', filename)


@bp.route('/uploads/<path:filename>')
def uploads_files(filename):
    return send_from_directory(obter_pasta_planilhas(), filename)
