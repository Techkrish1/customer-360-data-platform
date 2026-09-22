# Local Environment Setup

## Python Virtual Environment

```bash
# From the repo root
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Mac/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r shared/requirements.txt
```

## PostgreSQL via Docker (when Docker is installed)

```bash
docker run --name retail-postgres \
  -e POSTGRES_USER=retailco \
  -e POSTGRES_PASSWORD=retailco123 \
  -e POSTGRES_DB=retail \
  -p 5432:5432 \
  -d postgres:15
```

Connect via SQLTools in VSCode:
- Host: localhost
- Port: 5432
- Database: retail
- Username: retailco
- Password: retailco123

## Config

```bash
cp shared/config/config.template.yaml shared/config/config.yaml
# Edit config.yaml with your actual credentials
# config.yaml is in .gitignore — never commit it
```

## VSCode Extensions Installed

| Extension | Purpose |
|-----------|---------|
| hediet.vscode-drawio | Architecture diagrams (.drawio files) |
| ms-python.python | Python language support |
| ms-toolsai.jupyter | Jupyter notebooks |
| mtxr.sqltools | SQL query runner |
| mtxr.sqltools-driver-pg | PostgreSQL connection in SQLTools |
| mhutchie.git-graph | Visual git history |
| anthropic.claude-code | Claude Code AI assistant |
