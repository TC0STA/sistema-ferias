from __future__ import annotations

import os

from services.audit_service import AuditService
from services.backup_service import BackupService
from services.column_mapper import ColumnMapper
from services.column_alias_store import ColumnAliasStore
from services.compare_service import CompareService
from services.dashboard_updater import DashboardUpdater
from services.events import EventBus
from services.file_reader import FileReader
from services.import_log import ImportLogger
from services.import_plugin import ImportPluginContext
from services.import_preview import ImportPreview
from services.import_profile import ImportProfileStore
from services.import_utils import calcular_hash
from services.import_validator import ImportValidationResult, ImportValidator
from services.plugin_manager import ImportPluginManager


EMPTY_COMPARISON = {
    "novos": 0,
    "removidos": 0,
    "alterados": 0,
    "iguais": 0
}


class ImportService:
    """Orquestra serviços independentes sem conter regras de tela ou rota."""

    def __init__(
        self,
        *,
        database_path: str,
        backups_root: str,
        event_bus: EventBus | None = None,
        file_reader: FileReader | None = None,
        column_mapper: ColumnMapper | None = None,
        validator: ImportValidator | None = None,
        compare_service: CompareService | None = None,
        audit_service: AuditService | None = None,
        dashboard_updater: DashboardUpdater | None = None,
        plugin_manager: ImportPluginManager | None = None,
        preview: ImportPreview | None = None,
        persist_plugin_registry: bool = True
    ):
        self.database_path = database_path
        self.file_reader = file_reader or FileReader()
        self.column_alias_store = ColumnAliasStore(database_path)
        self.column_mapper = column_mapper or ColumnMapper(
            alias_store=self.column_alias_store
        )
        self.validator = validator or ImportValidator()
        self.compare_service = compare_service or CompareService()
        self.preview = preview or ImportPreview()
        self.logger = ImportLogger(database_path)
        self.profile_store = ImportProfileStore(database_path)
        self.backup_service = BackupService(backups_root)
        self.audit_service = audit_service or AuditService(database_path)
        self.dashboard_updater = (
            dashboard_updater or DashboardUpdater(database_path)
        )
        self.event_bus = event_bus or EventBus()
        self.plugin_manager = (
            plugin_manager or ImportPluginManager(
                database_path,
                ensure_schema=persist_plugin_registry
            )
        )
        self.plugin_manager.discover(persist=persist_plugin_registry)

    def _invalid_analysis(
        self,
        filename: str,
        message: str,
        context: ImportPluginContext,
        *,
        dry_run: bool = False
    ) -> dict:
        result = ImportValidationResult.for_file_error(
            os.path.basename(filename),
            message,
            self.validator.colunas_obrigatorias
        ).to_dict()
        result["perfil_importacao"] = None
        result["comparacao"] = dict(EMPTY_COMPARISON)
        context.data["validacao"] = result
        if not dry_run:
            self.plugin_manager.dispatch("validacao_falhou", context)
        result["resumo"] = {
            "registros_encontrados": 0,
            "usuarios_unicos": 0,
            "departamentos": 0,
            "periodo": {"inicio": None, "fim": None},
            "datas_invalidas": 0,
            "duplicados": 0,
            "colunas_identificadas": []
        }
        result["simulacao"] = dry_run
        result["operacao_id"] = context.operation_id
        result["plugins"] = list(context.results)
        return result

    def analyze(
        self,
        new_path: str,
        previous_path: str | None = None,
        *,
        confirmed_mapping: dict | None = None,
        profile_name: str | None = None,
        profile_origin: str | None = None,
        actor_user: str = "Sistema",
        actor_ip: str = "Local",
        dry_run: bool = False
    ) -> dict:
        context = ImportPluginContext(
            filename=os.path.basename(new_path),
            user=actor_user,
            ip=actor_ip,
            data={
                "caminho_novo": new_path,
                "caminho_anterior": previous_path
            }
        )
        def dispatch(hook: str):
            if not dry_run:
                self.plugin_manager.dispatch(hook, context)

        dispatch("importacao_iniciada")
        try:
            current = self.file_reader.read(new_path)
        except Exception as error:
            return self._invalid_analysis(
                new_path,
                str(error) or "Não foi possível ler o arquivo Excel.",
                context,
                dry_run=dry_run
            )
        context.filename = current.filename
        context.data["arquivo"] = {
            "nome": current.filename,
            "extensao": current.extension,
            "tamanho_bytes": current.size_bytes,
            "linha_cabecalho": current.header_row
        }
        context.data["dataframe"] = current.dataframe
        dispatch("arquivo_lido")

        profile = self.profile_store.match(
            current.dataframe.columns,
            count_usage=not dry_run
        )
        saved_mapping = profile["mapeamento"] if profile else None
        mapping = self.column_mapper.discover(
            current.dataframe.columns,
            obrigatorias=self.validator.colunas_obrigatorias,
            mapeamento_salvo=saved_mapping,
            mapeamento_confirmado=confirmed_mapping
        )
        context.data["mapeamento"] = mapping
        dispatch("colunas_mapeadas")
        validation = self.validator.validate_dataframe(
            current.dataframe,
            filename=current.filename,
            header_row=current.header_row,
            mapping=mapping,
            file_info={
                "ok": True,
                "extensao": current.extension,
                "tamanho_bytes": current.size_bytes
            }
        ).to_dict()
        context.data["validacao"] = validation
        dispatch("dados_validados")
        if validation["status"] == "MAPEAMENTO_NECESSARIO":
            dispatch("mapeamento_necessario")
        elif not validation["pronta"]:
            dispatch("validacao_falhou")

        if mapping.get("completo") and not dry_run:
            saved_profile = self.profile_store.save(
                current.columns,
                mapping["colunas"],
                nome=profile_name,
                arquivo_referencia=current.filename,
                origem=profile_origin,
                confirmado=bool(confirmed_mapping)
            )
            validation["perfil_importacao"] = {
                **saved_profile,
                "novo": profile is None,
                "confirmacao_recomendada": not saved_profile["confirmado"]
            }
            if confirmed_mapping:
                self.audit_service.record(
                    "Salvou mapeamento de colunas",
                    (
                        f"Perfil: {saved_profile['nome']} · "
                        f"Modelo: {mapping['assinatura'][:12]}"
                    ),
                    user=actor_user,
                    ip=actor_ip
                )
                self.event_bus.emit("mapeamento_colunas_salvo", {
                    "assinatura": mapping["assinatura"],
                    "mapeamento": mapping["colunas"],
                    "perfil": validation["perfil_importacao"]
                })
        else:
            validation["perfil_importacao"] = (
                {**profile, "novo": False, "confirmacao_recomendada": False}
                if profile else None
            )

        validation["comparacao"] = dict(EMPTY_COMPARISON)
        if validation["pronta"]:
            validation["comparacao"] = self._compare(
                previous_path,
                current.dataframe,
                mapping["colunas"]
            )
            context.data["comparacao"] = validation["comparacao"]
            dispatch("comparacao_concluida")
        validation["resumo"] = self.preview.build(
            current.dataframe,
            mapping=mapping,
            validation=validation
        )
        validation["simulacao"] = dry_run
        validation["operacao_id"] = context.operation_id
        validation["plugins"] = list(context.results)
        return validation

    def _compare(
        self,
        previous_path: str | None,
        current_dataframe,
        current_mapping: dict
    ) -> dict:
        if not previous_path:
            return self.compare_service.compare(
                None,
                current_dataframe,
                current_mapping=current_mapping
            )
        try:
            previous = self.file_reader.read(previous_path)
            previous_profile = self.profile_store.match(previous.columns)
            previous_mapping = (
                previous_profile["mapeamento"]
                if previous_profile
                else self.column_mapper.discover(
                    previous.columns,
                    obrigatorias=self.validator.colunas_obrigatorias
                )["colunas"]
            )
            return self.compare_service.compare(
                previous.dataframe,
                current_dataframe,
                previous_mapping=previous_mapping,
                current_mapping=current_mapping
            )
        except Exception:
            return self.compare_service.compare(
                None,
                current_dataframe,
                current_mapping=current_mapping
            )

    def prepare_import(
        self,
        *,
        operation_id: str | None = None,
        filename: str = "",
        user: str = "Sistema",
        ip: str = "Local"
    ) -> str:
        backup = self.backup_service.before_import(self.database_path)
        context = ImportPluginContext(
            operation_id=operation_id or ImportPluginContext().operation_id,
            filename=filename,
            user=user,
            ip=ip,
            data={"backup": backup}
        )
        self.plugin_manager.dispatch("backup_criado", context)
        return backup

    def record_validation(
        self,
        *,
        resultado: dict,
        tempo_segundos: float,
        usuario: str,
        ip: str
    ):
        context = ImportPluginContext(
            operation_id=resultado.get(
                "operacao_id",
                ImportPluginContext().operation_id
            ),
            filename=resultado["arquivo"],
            user=usuario,
            ip=ip,
            data={"validacao": resultado}
        )
        payload = {
            "arquivo": resultado["arquivo"],
            "quantidade": resultado["total_registros"],
            "tempo_segundos": tempo_segundos,
            "erros": resultado["total_erros"],
            "usuario": usuario,
            "ip": ip
        }
        if resultado["status"] == "MAPEAMENTO_NECESSARIO":
            payload["mapeamento"] = resultado["mapeamento"]
            self.audit_service.record(
                "Solicitou mapeamento de colunas",
                f"Arquivo: {resultado['arquivo']}",
                user=usuario,
                ip=ip,
                result="Pendente"
            )
            self.plugin_manager.dispatch("auditoria_registrada", context)
            self.event_bus.emit("mapeamento_colunas_necessario", payload)
            return
        if resultado["pronta"]:
            self.audit_service.record(
                "Validou planilha",
                (
                    f"Arquivo: {resultado['arquivo']} · "
                    f"{resultado['total_registros']} registro(s) · 0 erro(s)"
                ),
                user=usuario,
                ip=ip
            )
            self.plugin_manager.dispatch("auditoria_registrada", context)
            self.event_bus.emit("planilha_validada", payload)
            return
        self.record_failure(
            **payload,
            mensagem="A planilha foi reprovada pelo motor de validação.",
            operation_id=context.operation_id
        )

    def record_failure(
        self,
        *,
        arquivo: str,
        quantidade: int,
        tempo_segundos: float,
        erros: int,
        usuario: str,
        ip: str,
        mensagem: str,
        operation_id: str | None = None
    ):
        self.logger.record_failure(
            arquivo=arquivo,
            quantidade=quantidade,
            tempo_segundos=tempo_segundos,
            erros=erros,
            usuario=usuario,
            ip=ip
        )
        self.audit_service.record(
            "Importou planilha",
            f"Arquivo: {arquivo} · {erros} erro(s) · {mensagem}",
            user=usuario,
            ip=ip,
            result="Falha"
        )
        context = ImportPluginContext(
            operation_id=operation_id or ImportPluginContext().operation_id,
            filename=arquivo,
            user=usuario,
            ip=ip,
            data={
                "quantidade": quantidade,
                "tempo_segundos": tempo_segundos,
                "erros": erros,
                "mensagem": mensagem
            }
        )
        self.plugin_manager.dispatch("auditoria_registrada", context)
        self.plugin_manager.dispatch("importacao_falhou", context)
        self.event_bus.emit("importacao_falhou", {
            "arquivo": arquivo,
            "quantidade": quantidade,
            "tempo_segundos": tempo_segundos,
            "erros": erros,
            "usuario": usuario,
            "ip": ip,
            "mensagem": mensagem
        })

    def complete(
        self,
        *,
        caminho_arquivo: str,
        arquivo: str,
        registros: int,
        duracao_segundos: float,
        usuario: str,
        ip: str,
        comparacao: dict,
        backup: str,
        extra_payload: dict | None = None,
        operation_id: str | None = None
    ) -> int:
        context = ImportPluginContext(
            operation_id=operation_id or ImportPluginContext().operation_id,
            filename=arquivo,
            user=usuario,
            ip=ip,
            data={
                "arquivo_salvo": caminho_arquivo,
                "registros": registros,
                "comparacao": comparacao,
                "backup": backup
            }
        )
        self.plugin_manager.dispatch("dados_salvos", context)
        version = self.logger.record_success(
            arquivo=arquivo,
            registros=registros,
            erros=0,
            duracao_segundos=duracao_segundos,
            usuario=usuario,
            ip=ip,
            comparacao=comparacao,
            hash_arquivo=calcular_hash(caminho_arquivo),
            arquivo_armazenado=os.path.basename(caminho_arquivo)
        )
        self.audit_service.record(
            "Importou planilha",
            (
                f"Versão {version} · Arquivo: {arquivo} · "
                f"{registros} registro(s) · {duracao_segundos:.3f}s"
            ),
            user=usuario,
            ip=ip
        )
        self.audit_service.record(
            "Backup antes da importação",
            f"Arquivo: {backup}",
            user="Sistema",
            ip=ip
        )
        context.data["versao"] = version
        self.plugin_manager.dispatch("auditoria_registrada", context)
        updated_modules = self.dashboard_updater.update_all(version)
        self.audit_service.record(
            "Atualizou módulos após importação",
            "Dashboard, Calendário, Histórico e Centro de Operações",
            user="Sistema",
            ip=ip
        )
        context.data["modulos_atualizados"] = updated_modules
        self.plugin_manager.dispatch("dashboard_atualizado", context)
        payload = {
            "versao": version,
            "arquivo": arquivo,
            "registros": registros,
            "duracao_segundos": duracao_segundos,
            "usuario": usuario,
            "ip": ip,
            "comparacao": comparacao,
            "backup": backup,
            "modulos_atualizados": updated_modules
        }
        if extra_payload:
            payload.update(extra_payload)
        self.plugin_manager.dispatch("importacao_concluida", context)
        payload["plugins"] = list(context.results)
        self.event_bus.emit("importacao_concluida", payload)
        return version
