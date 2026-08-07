"""Rotas do módulo importacao."""

from flask import Blueprint

import backend
from backend import *  # noqa: F401,F403
from services.auth_service import current_actor


bp = Blueprint("importacao", __name__)


@bp.route("/importar")
def importar():
    agora = datetime.now()
    return render_template(
        "index.html",
        data_atual=agora.strftime("%d/%m/%Y %H:%M"),
        data_hoje=agora.strftime("%d/%m/%Y")
    )


@bp.route("/api/importacao/validar", methods=["POST"])
def validar_importacao():
    inicio_validacao = time.perf_counter()
    arquivo = request.files.get("arquivo")
    modo = request.form.get("modo", "definitivo").strip().lower()
    simulacao = modo == "simulacao"
    if not arquivo or not arquivo.filename:
        return {
            "ok": False,
            "mensagem": "Selecione uma planilha para iniciar a análise."
        }, 400

    nome_original = os.path.basename(arquivo.filename)
    _, extensao = os.path.splitext(nome_original)
    extensao = extensao.lower()
    if extensao not in {".xlsx", ".xls"}:
        return {
            "ok": False,
            "mensagem": "Formato inválido. Envie um arquivo Excel .xlsx ou .xls."
        }, 400

    limpar_validacoes_temporarias()
    token = uuid.uuid4().hex
    os.makedirs(backend.VALIDACOES_DIR, exist_ok=True)
    caminho = os.path.join(backend.VALIDACOES_DIR, f"{token}{extensao}")
    arquivo.save(caminho)
    motor = obter_motor_importacao(readonly=simulacao)
    ip = obter_ip_requisicao()

    try:
        resultado = motor.analyze(
            caminho,
            planilha_mais_recente(),
            actor_user=current_actor(),
            actor_ip=ip,
            dry_run=simulacao
        )
        resultado["arquivo"] = nome_original
        duracao = round(time.perf_counter() - inicio_validacao, 3)
        metadados = {
            "token": token,
            "arquivo": nome_original,
            "extensao": extensao,
            "modo": "simulacao" if simulacao else "definitivo",
            "criado_em": datetime.now().isoformat(timespec="seconds"),
            "duracao_validacao": duracao,
            "resultado": resultado
        }
        with open(
            caminho_metadados_validacao(token), "w", encoding="utf-8"
        ) as arquivo_metadados:
            json.dump(
                metadados,
                arquivo_metadados,
                ensure_ascii=False,
                indent=2
            )
    except PluginExecutionError as erro:
        if os.path.exists(caminho):
            os.remove(caminho)
        if not simulacao:
            motor.record_failure(
                arquivo=nome_original,
                quantidade=0,
                tempo_segundos=round(
                    time.perf_counter() - inicio_validacao,
                    3
                ),
                erros=1,
                usuario=current_actor(),
                ip=ip,
                mensagem=str(erro)
            )
        return {
            "ok": False,
            "mensagem": (
                "A validação foi interrompida por uma etapa adicional "
                "configurada. Consulte os logs do sistema."
            )
        }, 400
    except Exception as erro:
        # Arquivos externos podem falhar em diferentes leitores do Excel.
        if os.path.exists(caminho):
            os.remove(caminho)
        if not simulacao:
            motor.record_failure(
                arquivo=nome_original,
                quantidade=0,
                tempo_segundos=round(
                    time.perf_counter() - inicio_validacao,
                    3
                ),
                erros=1,
                usuario=current_actor(),
                ip=ip,
                mensagem=f"Falha ao ler o arquivo: {erro}"
            )
        return {
            "ok": False,
            "mensagem": (
                "Não foi possível analisar a planilha. "
                "Verifique se o arquivo está íntegro."
            )
        }, 400

    if not simulacao:
        motor.record_validation(
            resultado=resultado,
            tempo_segundos=duracao,
            usuario=current_actor(),
            ip=ip
        )
    return {
        "ok": True,
        "token": token,
        "duracao_segundos": duracao,
        "validacao": resultado
    }


@bp.route("/api/importacao/mapeamento", methods=["POST"])
def confirmar_mapeamento_importacao():
    inicio_validacao = time.perf_counter()
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token", "")).strip().lower()
    mapeamento = payload.get("mapeamento")
    metadados = carregar_validacao_temporaria(token)
    if not metadados:
        return {
            "ok": False,
            "mensagem": "A validação expirou. Selecione a planilha novamente."
        }, 404
    if not isinstance(mapeamento, dict) or not mapeamento:
        return {
            "ok": False,
            "mensagem": "Informe o mapeamento de colunas para continuar."
        }, 400

    simulacao = metadados.get("modo") == "simulacao"
    motor = obter_motor_importacao(readonly=simulacao)
    resultado = motor.analyze(
        metadados["caminho"],
        planilha_mais_recente(),
        confirmed_mapping=mapeamento,
        profile_name=payload.get("nome_perfil"),
        profile_origin=payload.get("origem"),
        actor_user=current_actor(),
        actor_ip=obter_ip_requisicao(),
        dry_run=simulacao
    )
    resultado["arquivo"] = metadados["arquivo"]
    duracao = round(time.perf_counter() - inicio_validacao, 3)
    metadados["resultado"] = resultado
    metadados["duracao_validacao"] = duracao
    metadados["mapeamento_confirmado_em"] = datetime.now().isoformat(
        timespec="seconds"
    )
    with open(
        metadados["caminho_metadados"], "w", encoding="utf-8"
    ) as arquivo_metadados:
        json.dump(
            {
                chave: valor
                for chave, valor in metadados.items()
                if chave not in {"caminho", "caminho_metadados"}
            },
            arquivo_metadados,
            ensure_ascii=False,
            indent=2
        )
    if not simulacao:
        motor.record_validation(
            resultado=resultado,
            tempo_segundos=duracao,
            usuario=current_actor(),
            ip=obter_ip_requisicao()
        )
    return {
        "ok": True,
        "token": token,
        "duracao_segundos": duracao,
        "validacao": resultado
    }


@bp.route("/api/importacao/perfis", methods=["GET"])
def listar_perfis_importacao():
    motor = obter_motor_importacao()
    incluir_inativos = request.args.get("incluir_inativos") == "1"
    return {
        "ok": True,
        "perfis": motor.profile_store.list(
            active_only=not incluir_inativos
        )
    }


@bp.route("/api/importacao/atualizacoes", methods=["GET"])
def listar_atualizacoes_importacao():
    motor = obter_motor_importacao()
    return {
        "ok": True,
        "modulos": motor.dashboard_updater.status()
    }


@bp.route("/api/importacao/plugins", methods=["GET"])
def listar_plugins_importacao():
    motor = obter_motor_importacao()
    return {
        "ok": True,
        "plugins": motor.plugin_manager.list(),
        "erros_carregamento": motor.plugin_manager.load_errors
    }


@bp.route("/api/importacao/plugins/<string:nome>", methods=["PATCH"])
def configurar_plugin_importacao(nome):
    payload = request.get_json(silent=True) or {}
    ativo = payload.get("ativo") if "ativo" in payload else None
    prioridade = (
        payload.get("prioridade")
        if "prioridade" in payload else None
    )
    if ativo is not None and not isinstance(ativo, bool):
        return {
            "ok": False,
            "mensagem": "O campo ativo deve ser verdadeiro ou falso."
        }, 400
    motor = obter_motor_importacao()
    try:
        alterado = motor.plugin_manager.configure(
            nome,
            enabled=ativo,
            priority=prioridade
        )
    except ValueError as erro:
        return {"ok": False, "mensagem": str(erro)}, 400
    if not alterado:
        return {
            "ok": False,
            "mensagem": "Plugin de importação não encontrado."
        }, 404
    registrar_auditoria(
        "Configurou plugin de importação",
        (
            f"Plugin: {nome} · "
            f"Ativo: {ativo if ativo is not None else 'inalterado'} · "
            f"Prioridade: "
            f"{prioridade if prioridade is not None else 'inalterada'}"
        ),
        usuario=current_actor(),
        ip=obter_ip_requisicao()
    )
    return {"ok": True}


@bp.route("/api/importacao/perfis/<int:perfil_id>", methods=["PATCH"])
def atualizar_perfil_importacao(perfil_id):
    payload = request.get_json(silent=True) or {}
    motor = obter_motor_importacao()
    alterado = False
    detalhes = []
    try:
        if "nome" in payload:
            alterado = motor.profile_store.rename(
                perfil_id,
                payload["nome"]
            ) or alterado
            detalhes.append(f"Nome: {str(payload['nome']).strip()}")
        if "ativo" in payload:
            if not isinstance(payload["ativo"], bool):
                raise ValueError(
                    "O campo ativo deve ser verdadeiro ou falso."
                )
            ativo = payload["ativo"]
            alterado = motor.profile_store.set_active(
                perfil_id,
                ativo
            ) or alterado
            detalhes.append("Ativo" if ativo else "Inativo")
    except ValueError as erro:
        return {"ok": False, "mensagem": str(erro)}, 400
    if not alterado:
        return {
            "ok": False,
            "mensagem": "Perfil de importação não encontrado."
        }, 404
    registrar_auditoria(
        "Atualizou perfil de importação",
        f"Perfil {perfil_id} · {' · '.join(detalhes)}",
        usuario=current_actor(),
        ip=obter_ip_requisicao()
    )
    return {"ok": True}


@bp.route("/upload", methods=["POST"])
def upload():
    inicio_importacao = time.perf_counter()
    configuracoes_importacao = carregar_configuracoes()
    motor = obter_motor_importacao()
    ip = obter_ip_requisicao()
    token = request.form.get("validacao_token", "").strip().lower()
    metadados = carregar_validacao_temporaria(token)
    arquivo = request.files.get("arquivo")

    if metadados and metadados.get("modo") == "simulacao":
        return render_template(
            "resultado.html",
            usuarios=[],
            erro=(
                "Uma simulação não pode ser confirmada como importação. "
                "Selecione o modo definitivo e analise a planilha novamente."
            )
        ), 400

    if metadados:
        caminho = metadados["caminho"]
        nome_arquivo = metadados["arquivo"]
        caminho_metadados = metadados["caminho_metadados"]
    elif arquivo and arquivo.filename:
        nome_arquivo = os.path.basename(arquivo.filename)
        _, extensao = os.path.splitext(nome_arquivo)
        extensao = extensao.lower()
        if extensao not in {".xlsx", ".xls"}:
            return render_template(
                "resultado.html",
                usuarios=[],
                erro="Formato inválido. Envie uma planilha Excel .xlsx ou .xls."
            )
        token = uuid.uuid4().hex
        os.makedirs(backend.VALIDACOES_DIR, exist_ok=True)
        caminho = os.path.join(backend.VALIDACOES_DIR, f"{token}{extensao}")
        caminho_metadados = None
        arquivo.save(caminho)
    else:
        return render_template(
            "resultado.html",
            usuarios=[],
            erro="Selecione e analise uma planilha antes de importar."
        )

    caminho_anterior = planilha_mais_recente()
    try:
        resultado_validacao = motor.analyze(caminho, caminho_anterior)
        resultado_validacao["arquivo"] = nome_arquivo
        if not resultado_validacao["pronta"]:
            primeiros_erros = "; ".join(
                f"Linha {item['linha']}: {item['mensagem']}"
                for item in resultado_validacao["erros"][:3]
            )
            raise ValueError(
                f"Foram encontrados {resultado_validacao['total_erros']} erro(s). "
                f"{primeiros_erros}"
            )
        df = carregar_planilha(
            caminho,
            resultado_validacao["mapeamento"]["colunas"]
        )
    except Exception as erro:
        # A confirmação nunca deve expor um erro técnico ao usuário.
        if os.path.exists(caminho):
            os.remove(caminho)
        if caminho_metadados and os.path.exists(caminho_metadados):
            os.remove(caminho_metadados)
        motor.record_failure(
            arquivo=nome_arquivo,
            quantidade=resultado_validacao.get("total_registros", 0)
            if "resultado_validacao" in locals() else 0,
            tempo_segundos=round(
                time.perf_counter() - inicio_importacao,
                3
            ),
            erros=resultado_validacao.get("total_erros", 1)
            if "resultado_validacao" in locals() else 1,
            usuario=current_actor(),
            ip=ip,
            mensagem=f"Falha na validação: {erro}"
        )
        return render_template(
            "resultado.html",
            usuarios=[],
            erro=str(erro)
        )

    try:
        caminho_backup = motor.prepare_import(
            operation_id=resultado_validacao.get("operacao_id"),
            filename=nome_arquivo,
            user=current_actor(),
            ip=ip
        )
    except PluginExecutionError as erro:
        motor.record_failure(
            arquivo=nome_arquivo,
            quantidade=resultado_validacao["total_registros"],
            tempo_segundos=round(
                time.perf_counter() - inicio_importacao,
                3
            ),
            erros=1,
            usuario=current_actor(),
            ip=ip,
            mensagem=str(erro),
            operation_id=resultado_validacao.get("operacao_id")
        )
        return render_template(
            "resultado.html",
            usuarios=[],
            erro=(
                "A importação foi interrompida por uma etapa adicional "
                "configurada. Consulte os logs do sistema."
            )
        )
    except (OSError, sqlite3.Error) as erro:
        motor.record_failure(
            arquivo=nome_arquivo,
            quantidade=resultado_validacao["total_registros"],
            tempo_segundos=round(
                time.perf_counter() - inicio_importacao,
                3
            ),
            erros=1,
            usuario=current_actor(),
            ip=ip,
            mensagem=f"Backup obrigatório não realizado: {erro}"
        )
        return render_template(
            "resultado.html",
            usuarios=[],
            erro=(
                "A importação foi interrompida porque o backup obrigatório "
                "não pôde ser criado."
            )
        )

    pasta_planilhas = obter_pasta_planilhas()
    caminho_final = os.path.join(pasta_planilhas, nome_arquivo)

    if configuracoes_importacao.get("substituir_planilha") == "1":
        for nome_antigo in os.listdir(pasta_planilhas):
            caminho_antigo = os.path.join(pasta_planilhas, nome_antigo)
            if (
                caminho_antigo != caminho_final
                and os.path.isfile(caminho_antigo)
                and nome_antigo.lower().endswith((".xlsx", ".xls"))
            ):
                os.remove(caminho_antigo)
    os.replace(caminho, caminho_final)
    if caminho_metadados and os.path.exists(caminho_metadados):
        os.remove(caminho_metadados)

    dados = []

    for _, row in df.iterrows():

        try:

            nome = str(row["Nome"]).strip()

            bloqueio = row["Data de Bloqueio"]

            if nome == "nan":
                continue

            dados.append({
                "Nome": nome,
                "Bloqueio": bloqueio.date()
                if pd.notnull(bloqueio)
                else None
            })

        except (KeyError, TypeError, ValueError):
            continue

    hoje = datetime.now().date()

    usuarios = []
    bloqueios_registrados = []

    conn = sqlite3.connect(backend.DATABASE_PATH)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bloqueios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            data_bloqueio TEXT,
            data_execucao TEXT,
            UNIQUE(nome, data_bloqueio)
        )
    """)

    for d in dados:

        if d["Bloqueio"] is None:
            continue

        if d["Bloqueio"] == hoje:
            usuarios.append(d["Nome"])

        if d["Bloqueio"] <= hoje:
            cursor.execute("""
                INSERT OR IGNORE INTO bloqueios
                (nome, data_bloqueio, data_execucao)
                VALUES (?, ?, ?)
            """, (
                d["Nome"],
                str(d["Bloqueio"]),
                str(datetime.now())
            ))
            if cursor.rowcount:
                bloqueios_registrados.append(d["Nome"])

    conn.commit()

    conn.close()

    duracao_importacao = round(time.perf_counter() - inicio_importacao, 3)
    comparacao = resultado_validacao["comparacao"]
    motor.complete(
        caminho_arquivo=caminho_final,
        arquivo=nome_arquivo,
        registros=resultado_validacao["total_registros"],
        duracao_segundos=duracao_importacao,
        usuario=current_actor(),
        ip=ip,
        comparacao=comparacao,
        backup=caminho_backup,
        extra_payload={
            "bloqueios_registrados": bloqueios_registrados
        },
        operation_id=resultado_validacao.get("operacao_id")
    )

    if configuracoes_importacao.get("mostrar_resumo_importacao") == "1":
        return render_template(
            "resultado.html",
            usuarios=usuarios,
            importado=True
        )
    return redirect(url_for("dashboard", importado="1"))
