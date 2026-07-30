from services.import_service import ImportService


class ImportEngine(ImportService):
    """Nome legado mantido para integrações existentes."""

    def analyze(
        self,
        caminho_novo,
        caminho_anterior=None,
        *,
        mapeamento_confirmado=None,
        nome_perfil=None,
        origem_perfil=None,
        usuario="Sistema",
        ip="Local",
        simulacao=False
    ):
        return super().analyze(
            caminho_novo,
            caminho_anterior,
            confirmed_mapping=mapeamento_confirmado,
            profile_name=nome_perfil,
            profile_origin=origem_perfil,
            actor_user=usuario,
            actor_ip=ip,
            dry_run=simulacao
        )
