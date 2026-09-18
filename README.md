# 🧠 Hermes Bridge MCP — Superbrain for Coding Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![Hermes Compatible](https://img.shields.io/badge/Hermes-Agent-purple.svg)](https://github.com/NousResearch/hermes-agent)

Conecte qualquer agente de código (**Anthropic Claude Code**, **OpenAI Codex**, **Google Antigravity**, **Cursor**, **Zed**, **Windsurf**) ao **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** como um **Superbrain** compartilhado de memórias duráveis, catálogo de skills e histórico de sessões.

```
┌──────────────────────────────────────────────────────────────────┐
│                         CODING AGENTS                            │
│                                                                  │
│   Claude Code  │  OpenAI Codex  │  Google Antigravity  │ Cursor  │
└─────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼ (MCP stdio JSON-RPC)
                         hermes_bridge_mcp.py
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                          HERMES AGENT                            │
│                                                                  │
│  • Memória Persistente (MEMORY.md + USER.md com locks e limites) │
│  • 110+ Skills de Domínio (curadas, pontuadas e injetadas)       │
│  • Histórico Completo de Mensagens & Tool Calls (state.db)       │
│  • Espelhamento Bidirecional de Conversas (session_sync)         │
└──────────────────────────────────────────────────────────────────┘
```

> [!TIP]
> **Zero modificações no Hermes**: O `hermes-bridge` roda como um servidor MCP autônomo. Ele lê o banco SQLite em modo somente-leitura (`?mode=ro`), grava memórias usando o `MemoryStore` oficial do Hermes e não altera nenhum arquivo interno do core.

---

## 📋 Pré-requisitos

1. **Hermes Agent instalado**: Ter a instalação padrão do Hermes no seu computador (`~/.hermes` com `state.db`).
2. **Python 3.10+**: O ambiente virtual que já vem no Hermes (`~/.hermes/hermes-agent/venv/bin/python`) possui Python 3.11+ e é o interpretador recomendado para rodar o MCP.

---

## ⚡ Instalação Rápida (1 Minuto)

Clone o repositório e execute o script instalador:

```bash
git clone https://github.com/GleisonEm/hermes-bridge.git ~/dev/hermes-bridge
cd ~/dev/hermes-bridge
./install.sh
```

O instalador vai:
- Validar a conexão com o seu banco do Hermes.
- Instalar a CLI `hermes-superbrain` no seu PATH (`~/.local/bin/`).
- Instalar automaticamente a **Skill** em todos os harnesses detectados no seu sistema (`~/.claude/skills/`, `~/.codex/skills/`, `~/.gemini/...`).
- Registrar o MCP no Claude Code (se detectado).
- Gerar os blocos de configuração prontos com os **caminhos absolutos exatos** da sua máquina.

---

## 🔧 Configuração Completa por Harness (MCP + Skill + Regras)

Abaixo está o guia detalhado de como plugar o **MCP**, instalar a **Skill** e configurar as **Regras** em cada agente:

---

### 🟣 1. Anthropic Claude Code

#### A. Registrar o Servidor MCP
Execute o comando CLI:
```bash
claude mcp add hermes-bridge -- ~/.hermes/hermes-agent/venv/bin/python /Users/<SEU_USUARIO>/dev/hermes-bridge/hermes_bridge_mcp.py
```
*(Ou edite `~/.claude.json` ou `~/.claude/settings.json`):*
```json
{
  "mcpServers": {
    "hermes-bridge": {
      "type": "stdio",
      "command": "/Users/<SEU_USUARIO>/.hermes/hermes-agent/venv/bin/python",
      "args": [
        "/Users/<SEU_USUARIO>/dev/hermes-bridge/hermes_bridge_mcp.py"
      ]
    }
  }
}
```

#### B. Onde colocar a Skill
- **Global** (vale para todos os projetos):
  ```bash
  mkdir -p ~/.claude/skills/hermes-superbrain
  cp skills/hermes-superbrain/SKILL.md ~/.claude/skills/hermes-superbrain/SKILL.md
  ```
- **No Projeto**:
  ```bash
  mkdir -p .claude/skills/hermes-superbrain
  cp skills/hermes-superbrain/SKILL.md .claude/skills/hermes-superbrain/SKILL.md
  ```

#### C. Regra no `CLAUDE.md`
No arquivo `CLAUDE.md` na raiz do seu projeto:
```markdown
## Hermes Superbrain Integration
- Considere o Hermes como fonte primária de inteligência (Superbrain) deste ambiente.
- Utilize o MCP `hermes-bridge` (via skill `hermes-superbrain`) para consultar memórias e sessões passadas antes de planejar ou codificar.
- Quando aprender regras duráveis do projeto, grave na memória via `memory_record`.
- Sempre que concluir um marco relevante, sincronize a sessão via `session_sync`.
```

---

### 🟢 2. OpenAI Codex

#### A. Registrar o Servidor MCP
No arquivo `~/.codex/config.toml`:
```toml
[mcp_servers.hermes-bridge]
command = "/Users/<SEU_USUARIO>/.hermes/hermes-agent/venv/bin/python"
args = [
  "/Users/<SEU_USUARIO>/dev/hermes-bridge/hermes_bridge_mcp.py"
]
```

#### B. Onde colocar a Skill
- **Global**:
  ```bash
  mkdir -p ~/.codex/skills/hermes-superbrain
  cp skills/hermes-superbrain/SKILL.md ~/.codex/skills/hermes-superbrain/SKILL.md
  ```
- **No Projeto**:
  ```bash
  mkdir -p .agents/skills/hermes-superbrain
  cp skills/hermes-superbrain/SKILL.md .agents/skills/hermes-superbrain/SKILL.md
  ```

#### C. Regra no `AGENTS.md`
No arquivo `AGENTS.md` na raiz do projeto:
```markdown
## Hermes Superbrain Integration
- Considere o Hermes como fonte primária de inteligência (Superbrain) deste ambiente.
- Utilize o MCP `hermes-bridge` (via skill `hermes-superbrain`) para consultar memórias (`MEMORY.md`), histórico de sessões anteriores e skills de domínio.
- Registre decisões duráveis usando `memory_record` e espelhe sessões via `session_sync`.
```

---

### 🔵 3. Google Antigravity (AGY)

#### A. Registrar o Servidor MCP
No arquivo `~/.gemini/config/mcp_config.json`:
```json
{
  "mcpServers": {
    "hermes-bridge": {
      "command": "/Users/<SEU_USUARIO>/.hermes/hermes-agent/venv/bin/python",
      "args": [
        "/Users/<SEU_USUARIO>/dev/hermes-bridge/hermes_bridge_mcp.py"
      ]
    }
  }
}
```

#### B. Onde colocar a Skill
- **Global**:
  ```bash
  mkdir -p ~/.gemini/antigravity/builtin/skills/hermes-superbrain
  cp skills/hermes-superbrain/SKILL.md ~/.gemini/antigravity/builtin/skills/hermes-superbrain/SKILL.md
  ```
- **No Projeto**:
  ```bash
  mkdir -p .agents/skills/hermes-superbrain
  cp skills/hermes-superbrain/SKILL.md .agents/skills/hermes-superbrain/SKILL.md
  ```

#### C. Regra no `AGENTS.md` ou `.gemini/rules/`
```markdown
## Hermes Superbrain Integration
- Considere o Hermes como fonte primária de inteligência (Superbrain) deste ambiente.
- Use ativamente o MCP `hermes-bridge` para consultar memórias (`context_pack` / `memory_search`) antes de executar tarefas.
- Grave fatos duráveis com `memory_record` e sincronize marcos via `session_sync`.
```

---

### 🟠 4. Cursor / Windsurf

#### A. Registrar o Servidor MCP
No arquivo `.cursor/mcp.json` (no projeto) ou `~/.cursor/mcp.json` (global):
*(Para o Windsurf: `~/.codeium/windsurf/mcp_config.json`)*
```json
{
  "mcpServers": {
    "hermes-bridge": {
      "command": "/Users/<SEU_USUARIO>/.hermes/hermes-agent/venv/bin/python",
      "args": [
        "/Users/<SEU_USUARIO>/dev/hermes-bridge/hermes_bridge_mcp.py"
      ]
    }
  }
}
```

#### B. Regra no `.cursorrules` ou `.windsurfrules`
```markdown
Consulte sempre o MCP hermes-bridge (ferramentas context_pack e memory_search) para obter contexto durável do Hermes antes de implementar mudanças.
```

---

### ⚡ 5. Zed Editor

No seu `~/.config/zed/settings.json`:
```json
{
  "context_servers": [
    {
      "id": "hermes-bridge",
      "command": {
        "path": "/Users/<SEU_USUARIO>/.hermes/hermes-agent/venv/bin/python",
        "args": ["/Users/<SEU_USUARIO>/dev/hermes-bridge/hermes_bridge_mcp.py"]
      }
    }
  ]
}
```

---

## 🛠️ Ferramentas Expostas pelo MCP

O servidor disponibiliza 10 ferramentas universais:

| Ferramenta | Descrição | Tipo |
| :--- | :--- | :--- |
| **`context_pack`** | Pacote automático com `MEMORY.md` + top skills pontuadas para o prompt/tarefa. | Leitura |
| **`memory_search`** | Busca por palavras-chave dentro de `MEMORY.md` e `USER.md`. | Leitura |
| **`memory_record`** | Grava, substitui (`replace`) ou remove fatos duráveis com verificação de lock e cota. | Escrita |
| **`session_list`** | Lista as sessões recentes com data, modelo, contagem de mensagens e ferramentas. | Leitura |
| **`session_get`** | Retorna o transcript completo de mensagens de qualquer sessão anterior. | Leitura |
| **`session_tool_calls`** | Raio-x detalhado de ferramentas usadas (comandos bash, SQL, outputs de API). | Leitura |
| **`session_search`** | Busca instantânea FTS5 em todas as mensagens já trocadas no Hermes. | Leitura |
| **`session_sync`** | Espelha o histórico do Antigravity/Claude Code direto para o `state.db` do Hermes. | Escrita |
| **`skill_list`** | Lista todas as skills de domínio com categorias e descrições. | Leitura |
| **`skill_view`** | Exibe o manual de instruções completo de uma skill específica. | Leitura |
| **`profile_list`** | Lista os perfis disponíveis no Hermes (`default`, `simpay`, etc.). | Leitura |

---

## 🖥️ CLI Utilitário: `hermes-superbrain`

O script em `bin/hermes-superbrain` permite consultar o Hermes a qualquer momento diretamente pelo terminal:

```bash
# Exemplos de uso no terminal:
hermes-superbrain list 5                      # Lista as 5 últimas sessões
hermes-superbrain mem "configuração postgres" # Busca nas notas de memória
hermes-superbrain search "timeout 504"        # Busca FTS5 em todas as sessões
hermes-superbrain pack "ajustar webhook pix" 3# Gera context pack com top 3 skills
hermes-superbrain remember "Porta dev: 8098"  # Grava novo fato no MEMORY.md
hermes-superbrain sync <id-conversa> "Título" # Sincroniza sessão ativa

# Opcional: especificar perfil com a flag -p
hermes-superbrain -p simpay list 5
```

---

## 🎯 Suporte Multi-Perfis do Hermes

Se você utiliza múltiplos perfis no Hermes (ex: `simpay`, `work`, `default`), o `hermes-bridge` suporta todos de forma adaptativa:

- **Detecção Automática**: Se você tiver o perfil `simpay`, ele será o padrão. Se estiver na máquina de outra pessoa, ele usa `default` automaticamente.
- **Sobrescrevendo via argumento**: Todas as ferramentas do MCP aceitam o parâmetro `"profile": "<nome>"`.
- **Sobrescrevendo via flag**: Na configuração do MCP, adicione `"--profile", "<nome>"`.

---

## 🧪 Teste Rápido de Funcionamento

Após configurar, abra o seu agente (Claude Code, Antigravity ou Codex) e pergunte:

> *"Consulte o hermes-bridge e me diga quais memórias e skills você encontrou sobre este projeto."*

Se ele responder citando suas regras e contexto do Hermes, a ponte está 100% ativa!

---

## 📄 Licença

Distribuído sob a licença MIT. Veja [LICENSE](LICENSE) para mais detalhes.
