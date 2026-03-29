# Testes — Gerador de Anexos

## Executar

```bash
# Com pytest (recomendado):
pip install pytest
python -m pytest tests/ -v

# Sem pytest (Python puro):
python3 -c "
import sys; sys.path.insert(0, '.')
from tests.test_utils import *

passed = failed = 0
for cls in [TestValorPorExtenso, TestValidarCNPJ, TestFormatarCNPJ, TestMesNome, TestDateFmt]:
    obj = cls()
    for name in [m for m in dir(obj) if m.startswith('test_')]:
        try:
            getattr(obj, name)(); passed += 1
        except Exception as e:
            print(f'FAIL {cls.__name__}.{name}: {e}'); failed += 1
print(f'{passed} passed, {failed} failed')
"
```

## Cobertura

| Módulo | Funções testadas | Cobertura |
|--------|-----------------|-----------|
| `utils.py` | `valor_por_extenso`, `validar_cnpj`, `formatar_cnpj`, `mes_nome`, `DATE_FMT` | ~90% |

## Próximos testes a implementar

- `tests/test_database.py` — DBConn, PGRow, init_db com SQLite em memória
- `tests/test_routes.py` — endpoints Flask com app.test_client()
- `tests/test_pdf_generator.py` — smoke test de geração de PDFs
