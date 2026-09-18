# Hermes Bridge MCP — Superbrain for Coding Agents

Conecte qualquer agente de código (**Google Antigravity**, **Anthropic Claude Code**, **OpenAI Codex**, **Cursor**, **Zed**) ao **Hermes Agent** como um **Superbrain** de memória compartilhada, catálogo de skills e histórico de conversas.

```
┌─────────────────────────────────────────────────────────────┐
│                      CODING AGENTS                          │
│                                                             │
│   Claude Code │ OpenAI Codex │ Antigravity │ Cursor │ Zed   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼ (MCP stdio JSON-RPC)
                      hermes_bridge_mcp.py
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                       HERMES AGENT                          │
│                                                             │
│  • Memória Persistente (MEMORY.md + USER.md)                │
│  • 110+ Skills de Domínio (curadas e pontuadas)             │
│  • Histórico Completo de Mensagens & Tool Calls (state.db)  │
│  • Espelhamento Bidirecional de Sessões (session_sync)      │
└─────────────────────────────────────────────────────────────┘
```

> [!TIP]
> **Zero modificação no Hermes**: O `hermes-bridge` roda como um servidor MCP standalone e seguro. Ele lê o banco SQLite em modo somente-leitura (`?mode=ro`), respeita os locks de memória oficiais do Hermes e não altera nenhum código interno.

---

## 🚀 Como Configurar em Cada Agente

### 1. Anthropic Claude Code

Você pode adicionar diretamente via CLI:
```bash
claude mcp add hermes-bridge -- /Users/<SEU_USUARIO>/.hermes/hermes-agent/venv/bin/python /Users/<SEU_USUARIO>/dev/hermes-bridge/hermes_bridge_mcp.py
```

Ou no seu `~/.claude/settings.json`:
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

---

### 2. OpenAI Codex

No seu `~/.codex/config.toml`:
```toml
[mcp_servers.hermes-bridge]
command = "/Users/<SEU_USUARIO>/.hermes/hermes-agent/venv/bin/python"
args = [
  "/Users/<SEU_USUARIO>/dev/hermes-bridge/hermes_bridge_mcp.py"
]
```

---

### 3. Google Antigravity

No seu `~/.gemini/config/mcp_config.json`:
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

---

### 4. Cursor / Zed / Claude Desktop

No arquivo de configuração do seu cliente (`.cursor/mcp.json` ou `claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "hermes-bridge": {
      "command": "/Users/<SEU_USUARIO>/.hermes/hermes-agent/venv/bin/python",
      "args": [
        "/caminho/para/hermes-bridge/hermes_bridge_mcp.py"
      ]
    }
  }
}
```

> **Por que usar o Python do venv do Hermes?**  
> O Hermes vem com um ambiente virtual próprio (`~/.hermes/hermes-agent/venv/bin/python`) com Python 3.11+ e suporte nativo ao SQLite atualizado, garantindo que tudo rode sem conflito com o Python do sistema operacional.

---

## 🛠️ Ferramentas Disponíveis

| Ferramenta | Descrição | Tipo |
| :--- | :--- | :--- |
| `context_pack` | Context pack automatizado com `MEMORY.md` + top skills pontuadas para o prompt atual. | Leitura |
| `memory_search` | Busca termos específicos dentro de `MEMORY.md` e `USER.md`. | Leitura |
| `memory_record` | Adiciona, substitui (`replace`) ou remove fatos da memória durável com lock e validação. | Escrita |
| `session_list` | Lista as últimas sessões do Hermes com contagem de mensagens e ferramentas. | Leitura |
| `session_get` | Recupera mensagens e histórico de uma conversa específica. | Leitura |
| `session_tool_calls` | Raio-x das ferramentas chamadas (comandos shell, SQL, saídas de API). | Leitura |
| `session_search` | Busca rápida em SQLite FTS5 em todas as mensagens do Hermes. | Leitura |
| `session_sync` | Espelha transcripts do Antigravity/Claude para dentro do Hermes Desktop (`state.db`). | Escrita |
| `skill_list` / `skill_view` | Lista e lê instruções completas de qualquer skill do Hermes. | Leitura |
| `profile_list` | Lista todos os perfis disponíveis no Hermes (`default`, `simpay`, etc.). | Leitura |

---

## 📦 Instalando a Skill no seu Agente

Copie a skill incluída neste repositório para o seu projeto:

```bash
# Para Antigravity / Claude Code / Codex
mkdir -p .agents/skills/hermes-superbrain
cp skills/hermes-superbrain/SKILL.md .agents/skills/hermes-superbrain/SKILL.md
```

E adicione ao seu arquivo de regras (`AGENTS.md` ou `CLAUDE.md`):
```markdown
## Hermes Superbrain Integration
- Considere o Hermes como fonte primária de inteligência (Superbrain) deste ambiente.
- Utilize o MCP `hermes-bridge` (via skill `hermes-superbrain`) para consultar memórias e sessões passadas antes de tarefas complexas.
- Sempre que concluir um marco relevante, sincronize a sessão via `session_sync`.
```

---

## ⚡ CLI Utilitário: `hermes-superbrain`

O script em `bin/hermes-superbrain` permite consultar e operar tudo pelo terminal:

```bash
# Adicione ao seu PATH
cp bin/hermes-superbrain ~/.local/bin/hermes-superbrain

# Exemplos de uso:
hermes-superbrain list 5                      # Lista últimas 5 sessões
hermes-superbrain mem "pagamento pix"         # Busca na memória persistente
hermes-superbrain search "erro 502"           # Busca FTS5 em todas as sessões
hermes-superbrain pack "ajustar webhook" 3    # Gera context pack com top 3 skills
hermes-superbrain remember "Porta dev: 8098"  # Grava na memória durável
hermes-superbrain sync <id-conversa> "Título" # Sincroniza sessão
```

---

## Licença

MIT — veja [LICENSE](LICENSE).
