from services.import_plugin import ImportPlugin


class ErrorNotificationExample(ImportPlugin):
    name = "notificacao_erro_exemplo"
    description = (
        "Exemplo desativado de notificação após erro de validação/importação."
    )
    hooks = ("validacao_falhou", "importacao_falhou")
    priority = 200
    enabled_by_default = False
    critical = False

    def execute(self, context):
        return {
            "destino": "administrador",
            "assunto": f"Erro ao importar {context.filename}",
            "observacao": (
                "Substitua este retorno por uma integração de e-mail."
            )
        }


def register_plugins(manager):
    manager.register(ErrorNotificationExample(), source=__file__)
