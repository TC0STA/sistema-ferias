# Plugins de importação

Cada arquivo Python desta pasta pode registrar extensões sem alterar o núcleo.

Contrato mínimo:

```python
from services.import_plugin import ImportPlugin


class MeuPlugin(ImportPlugin):
    name = "meu_plugin"
    description = "Executa uma ação após a importação."
    hooks = ("importacao_concluida",)
    priority = 100
    critical = False

    def execute(self, context):
        # Use context.filename, context.user, context.ip e context.data.
        return {"mensagem": "Executado"}


def register_plugins(manager):
    manager.register(MeuPlugin(), source=__file__)
```

Plugins não críticos são isolados: uma falha é registrada, mas não interrompe
a importação. Plugins críticos interrompem o processo no evento configurado.
