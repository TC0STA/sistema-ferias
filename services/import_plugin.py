from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


IMPORT_HOOKS = (
    "importacao_iniciada",
    "arquivo_lido",
    "colunas_mapeadas",
    "dados_validados",
    "mapeamento_necessario",
    "validacao_falhou",
    "comparacao_concluida",
    "backup_criado",
    "dados_salvos",
    "auditoria_registrada",
    "dashboard_atualizado",
    "importacao_concluida",
    "importacao_falhou",
)


@dataclass
class ImportPluginContext:
    operation_id: str = field(default_factory=lambda: uuid4().hex)
    hook: str = ""
    filename: str = ""
    user: str = "Sistema"
    ip: str = "Local"
    data: dict = field(default_factory=dict)
    results: list[dict] = field(default_factory=list)


class ImportPlugin:
    """Contrato mínimo para extensões do processo de importação."""

    name = ""
    description = ""
    hooks: tuple[str, ...] = ()
    priority = 100
    enabled_by_default = True
    critical = False

    def execute(self, context: ImportPluginContext):
        raise NotImplementedError


class PluginExecutionError(RuntimeError):
    def __init__(self, plugin_name: str, hook: str, original_error: Exception):
        super().__init__(
            f'Plugin crítico "{plugin_name}" falhou no evento "{hook}".'
        )
        self.plugin_name = plugin_name
        self.hook = hook
        self.original_error = original_error
