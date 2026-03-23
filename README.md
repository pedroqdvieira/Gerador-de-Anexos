# Gerador de Anexos – SEMED

Desenvolvido por **Pedro Quinellato Dutra Vieira** com auxílio de **Claude Sonnet 4.6** (Anthropic).

Sistema web para geração automática dos anexos de pagamento de notas fiscais de contratos municipais: Anexo III, Anexo VI, Anexo IX e Ateste — todos com papel timbrado da Prefeitura de Vila Velha.

---

## Changelog

### v0.4.0
- Dashboard home com métricas de contratos e empenhos
- Sistema de login com autenticação por sessão e senha hash (werkzeug/scrypt)
- Proteção de todas as rotas — sistema bloqueado sem login
- Suporte a PostgreSQL (Railway) com fallback automático para SQLite local
- Arquivos de deploy: `Procfile`, `railway.json`, `pyproject.toml`
- Página de Manual do Usuário
- Botão de logout na navbar com nome do usuário

### v0.3.0
- Meatball menu (···) em todas as páginas de listagem
- Download de todos os PDFs como ZIP com arquivos separados
- Datas em dd/mm/yyyy em toda a interface
- Importador de contratos via API de Transparência de Vila Velha
- Correção: edição de empresas não abria o modal (tojson inline)
- Decreto corrigido para 157/2025 no Ateste

### v0.2.0
- Histórico com busca, filtro por contrato, paginação e exportação CSV
- Relatório de empenhos por contrato
- Histórico de alterações de contratos e empenhos
- Prorrogação de vigência com registro de histórico
- Alertas de vencimento de contrato (badge + tooltip)

### v0.1.0
- Sistema base: contratos, empresas, pessoas, empenhos
- Geração de PDFs: Anexo III, VI, IX e Ateste com papel timbrado
- Controle de saldo de empenho (rascunho → confirmação → cancelamento)
- Validação de CNPJ pelo algoritmo da Receita Federal

---

## Usando o executável (.exe)

1. Copie `GeradorAnexos.exe` para uma pasta de sua preferência
2. Execute com duplo clique — o navegador abre automaticamente
3. Faça login com as credenciais configuradas
4. O banco de dados `semed.db` é criado na mesma pasta do `.exe`

**Pré-requisito:** Windows 10 64-bit. Em caso de erro `VCRUNTIME140.dll`, instale o [Visual C++ Redistributable 2022 x64](https://aka.ms/vs/17/release/vc_redist.x64.exe).

---

## Rodando via Python (desenvolvimento local)

```bash
# Instalar dependências
pip install flask reportlab pypdf werkzeug

# Iniciar
python app.py
```

Acesse: **http://localhost:5000**

---

## Deploy no Railway (produção)

### Pré-requisitos
- Conta no [Railway](https://railway.app)
- Repositório no GitHub com o projeto

### Passo a passo

**1. Suba para o GitHub**
```bash
git init
git add .
git commit -m "v0.4.0"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/gerador-anexos.git
git push -u origin main
```

**2. Crie o projeto no Railway**
- New Project → Deploy from GitHub repo → selecione o repositório

**3. Adicione o banco PostgreSQL**
- No painel: + New → Database → PostgreSQL
- A variável `DATABASE_URL` é configurada automaticamente

**4. Configure as variáveis de ambiente**

| Variável | Valor |
|---|---|
| `SECRET_KEY` | String aleatória longa |
| `ADMIN_USERNAME` | `admin` (ou outro) |
| `ADMIN_PASSWORD_HASH` | Hash gerado com `generate_password_hash()` |

**Gerar novo hash de senha:**
```bash
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('NOVA_SENHA'))"
```

**5. Gere o domínio público**
- Settings → Generate Domain

O Railway faz deploy automático a cada `git push`.

---

## Gerando o .exe

```bash
pip install pyinstaller
python -m PyInstaller --onefile --noconsole --add-data "templates;templates" --add-data "static;static" --add-data "pdf_generator;pdf_generator"  --name "GeradorAnexos" app.py
```

O executável gerado fica em `dist/GeradorAnexos.exe`.

---

## Importando contratos da API de Transparência

```bash
python importar_api.py
```

Consulta a API pública de Vila Velha, lista os contratos da SEMED e permite importar para o banco.

---

## Estrutura do projeto

```
semed_anexos/
├── app.py               # Ponto de entrada, configuração Flask, proteção de rotas
├── database.py          # Camada de dados (SQLite local / PostgreSQL Railway)
├── utils.py             # Funções: extenso, CNPJ, datas
├── routes/
│   ├── auth.py          # Login, logout, decorator login_required
│   ├── pessoas.py       # CRUD gestores e fiscais
│   ├── empresas.py      # CRUD empresas
│   ├── contratos.py     # CRUD contratos, empenhos, prorrogações
│   └── anexos.py        # Geração de NFs, PDFs, histórico, dashboard
├── pdf_generator/
│   └── __init__.py      # Geração dos 4 anexos em PDF (ReportLab)
├── templates/           # HTML Jinja2
├── static/              # CSS, JS, imagens
├── Procfile             # Comando de start para Railway/Heroku
├── railway.json         # Configuração Railway
├── pyproject.toml       # Metadados e dependências do projeto
├── requirements.txt     # Dependências pip
└── importar_api.py      # Script de importação via API de Transparência
```

---

## Aviso

Protótipo em desenvolvimento ativo. Versão atual: **v0.4.3**. Verifique os documentos gerados antes de uso oficial.
