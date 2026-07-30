from __future__ import annotations

import importlib.util
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from services.import_plugin import (
    IMPORT_HOOKS,
    ImportPlugin,
    ImportPluginContext,
    PluginExecutionError,
)


CRITICAL_PRE_SAVE_HOOKS = {
    "importacao_iniciada",
    "arquivo_lido",
    "colunas_mapeadas",
    "dados_validados",
    "mapeamento_necessario",
    "validacao_falhou",
    "comparacao_concluida",
    "backup_criado",
}


class ImportPluginManager:
    """Registra, configura, descobre e executa plugins por evento."""

    def __init__(
        self,
        database_path: str,
        plugins_dir: str | None = None,
        *,
        ensure_schema: bool = True
    ):
        self.database_path = database_path
        self.plugins_dir = Path(
            plugins_dir
            or Path(__file__).resolve().parents[1] / "plugins" / "importacao"
        )
        self._plugins: dict[str, ImportPlugin] = {}
        self._sources: dict[str, str] = {}
        self.load_errors: list[dict] = []
        self._persist_registration = True
        if ensure_schema:
            self.ensure_schema()

    def ensure_schema(self):
        conn = sqlite3.connect(self.database_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS plugins_importacao (
                    nome TEXT PRIMARY KEY,
                    descricao TEXT NOT NULL,
                    origem TEXT NOT NULL,
                    ativo INTEGER NOT NULL,
                    prioridade INTEGER NOT NULL,
                    critico INTEGER NOT NULL,
                    registrado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execucoes_plugins_importacao (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operacao_id TEXT NOT NULL,
                    plugin TEXT NOT NULL,
                    evento TEXT NOT NULL,
                    resultado TEXT NOT NULL,
                    duracao_ms REAL NOT NULL,
                    erro TEXT,
                    executado_em TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def register(self, plugin: ImportPlugin, *, source="interno"):
        name = str(plugin.name).strip()
        if not name:
            raise ValueError("Todo plugin precisa possuir um nome.")
        invalid_hooks = set(plugin.hooks) - set(IMPORT_HOOKS)
        if invalid_hooks:
            raise ValueError(
                f"Plugin {name} possui eventos inválidos: "
                f"{', '.join(sorted(invalid_hooks))}."
            )
        self._plugins[name] = plugin
        self._sources[name] = source
        if not self._persist_registration:
            return plugin
        now = datetime.now().isoformat(timespec="seconds")
        conn = sqlite3.connect(self.database_path)
        try:
            conn.execute(
                """
                INSERT INTO plugins_importacao (
                    nome, descricao, origem, ativo, prioridade,
                    critico, registrado_em, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(nome) DO UPDATE SET
                    descricao = excluded.descricao,
                    origem = excluded.origem,
                    critico = excluded.critico,
                    atualizado_em = excluded.atualizado_em
                """,
                (
                    name,
                    str(plugin.description),
                    source,
                    int(plugin.enabled_by_default),
                    int(plugin.priority),
                    int(plugin.critical),
                    now,
                    now
                )
            )
            conn.commit()
        finally:
            conn.close()
        return plugin

    def discover(self, *, persist: bool = True) -> list[str]:
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        loaded = []
        self.load_errors = []
        previous_persistence = self._persist_registration
        self._persist_registration = persist
        try:
            for path in sorted(self.plugins_dir.glob("*.py")):
                if path.name.startswith("_"):
                    continue
                module_name = (
                    "fokus_import_plugin_"
                    + path.stem
                    + "_"
                    + str(abs(hash(str(path.resolve()))))
                )
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name,
                        path
                    )
                    if not spec or not spec.loader:
                        raise ImportError("Não foi possível criar o módulo.")
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    register = getattr(module, "register_plugins", None)
                    if not callable(register):
                        raise ImportError(
                            "O arquivo deve expor register_plugins(manager)."
                        )
                    before = set(self._plugins)
                    register(self)
                    loaded.extend(sorted(set(self._plugins) - before))
                    for name in set(self._plugins) - before:
                        self._sources[name] = str(path)
                except Exception as error:
                    self.load_errors.append({
                        "arquivo": str(path),
                        "erro": str(error)
                    })
        finally:
            self._persist_registration = previous_persistence
        return loaded

    def configure(
        self,
        name: str,
        *,
        enabled: bool | None = None,
        priority: int | None = None
    ) -> bool:
        changes = []
        values = []
        if enabled is not None:
            changes.append("ativo = ?")
            values.append(int(enabled))
        if priority is not None:
            if not isinstance(priority, int) or priority < 0:
                raise ValueError(
                    "A prioridade deve ser um número inteiro não negativo."
                )
            changes.append("prioridade = ?")
            values.append(priority)
        if not changes:
            return False
        changes.append("atualizado_em = ?")
        values.append(datetime.now().isoformat(timespec="seconds"))
        values.append(name)
        conn = sqlite3.connect(self.database_path)
        try:
            cursor = conn.execute(
                f"""
                UPDATE plugins_importacao
                SET {", ".join(changes)}
                WHERE nome = ?
                """,
                values
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list(self) -> list[dict]:
        conn = sqlite3.connect(self.database_path)
        try:
            rows = conn.execute(
                """
                SELECT nome, descricao, origem, ativo, prioridade,
                       critico, registrado_em, atualizado_em
                FROM plugins_importacao
                ORDER BY prioridade, nome COLLATE NOCASE
                """
            ).fetchall()
        finally:
            conn.close()
        return [{
            "nome": row[0],
            "descricao": row[1],
            "origem": row[2],
            "ativo": bool(row[3]),
            "prioridade": row[4],
            "critico": bool(row[5]),
            "registrado_em": row[6],
            "atualizado_em": row[7],
            "carregado": row[0] in self._plugins
        } for row in rows]

    def _active_configuration(self, name: str):
        conn = sqlite3.connect(self.database_path)
        try:
            return conn.execute(
                """
                SELECT ativo, prioridade, critico
                FROM plugins_importacao WHERE nome = ?
                """,
                (name,)
            ).fetchone()
        finally:
            conn.close()

    def _record_execution(
        self,
        *,
        context: ImportPluginContext,
        plugin_name: str,
        result: str,
        duration_ms: float,
        error: str | None = None
    ):
        conn = sqlite3.connect(self.database_path)
        try:
            conn.execute(
                """
                INSERT INTO execucoes_plugins_importacao (
                    operacao_id, plugin, evento, resultado,
                    duracao_ms, erro, executado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    context.operation_id,
                    plugin_name,
                    context.hook,
                    result,
                    duration_ms,
                    error,
                    datetime.now().isoformat(timespec="seconds")
                )
            )
            conn.commit()
        finally:
            conn.close()

    def dispatch(
        self,
        hook: str,
        context: ImportPluginContext
    ) -> list[dict]:
        if hook not in IMPORT_HOOKS:
            raise ValueError(f"Evento de plugin desconhecido: {hook}.")
        context.hook = hook
        candidates = []
        for name, plugin in self._plugins.items():
            if hook not in plugin.hooks:
                continue
            config = self._active_configuration(name)
            if config and config[0]:
                candidates.append((config[1], name, bool(config[2]), plugin))
        candidates.sort(key=lambda item: (item[0], item[1].lower()))

        executions = []
        for _, name, critical, plugin in candidates:
            started = time.perf_counter()
            try:
                value = plugin.execute(context)
                if not isinstance(
                    value,
                    (type(None), str, int, float, bool, dict, list, tuple)
                ):
                    value = repr(value)
                if isinstance(value, tuple):
                    value = list(value)
                duration = round(
                    (time.perf_counter() - started) * 1000,
                    3
                )
                item = {
                    "plugin": name,
                    "evento": hook,
                    "resultado": "Sucesso",
                    "retorno": value,
                    "duracao_ms": duration
                }
                context.results.append(item)
                executions.append(item)
                self._record_execution(
                    context=context,
                    plugin_name=name,
                    result="Sucesso",
                    duration_ms=duration
                )
            except Exception as error:
                duration = round(
                    (time.perf_counter() - started) * 1000,
                    3
                )
                item = {
                    "plugin": name,
                    "evento": hook,
                    "resultado": "Falha",
                    "erro": str(error),
                    "duracao_ms": duration
                }
                context.results.append(item)
                executions.append(item)
                self._record_execution(
                    context=context,
                    plugin_name=name,
                    result="Falha",
                    duration_ms=duration,
                    error=str(error)
                )
                if critical and hook in CRITICAL_PRE_SAVE_HOOKS:
                    raise PluginExecutionError(name, hook, error) from error
        return executions
