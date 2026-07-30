from services.import_profile import ImportProfileStore


class ColumnMappingStore(ImportProfileStore):
    """Compatibilidade com o nome anterior do repositório."""

    def load(self, colunas) -> dict | None:
        profile = self.match(colunas)
        return profile["mapeamento"] if profile else None

    def save(self, colunas, mapeamento: dict):
        return super().save(colunas, mapeamento, confirmado=True)
