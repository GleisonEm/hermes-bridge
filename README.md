# 🧠 Hermes Bridge MCP — Superbrain for Coding Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![Hermes Compatible](https://img.shields.io/badge/Hermes-Agent-purple.svg)](https://github.com/NousResearch/hermes-agent)

Conecte qualquer agente de código (**Anthropic Claude Code**, **OpenAI Codex**, **Google Antigravity**, **Cursor**, **Zed**) ao **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** como um **Superbrain** compartilhado de memórias duráveis, catálogo de skills e histórico de sessões.

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

1. **Hermes Agent instalado**: Você só precisa ter a instalação padrão do Hermes no seu computador (`~/.hermes` com `state.db`).
2. **Python 3.10+**: O ambiente virtual que já vem no Hermes (`~/.hermes/hermes-agent/venv/bin/python`) possui Python 3.11+ e é o interpretador recomendado.

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
- Se detectar o Claude Code instalado, perguntará se deseja adicioná-lo automaticamente via CLI.
- Gerar os blocos de configuração prontos com os **caminhos absolutos exatos** da sua máquina.

---

## 🔧 Configuração Manual por Agente

Caso prefira configurar manualmente no seu editor ou agente favorito, use os blocos abaixo:

### 1. Anthropic Claude Code

Você pode adicionar em um único comando no terminal:
```bash
claude mcp add hermes-bridge -- ~/.hermes/hermes-agent/venv/bin/python /Users/<SEU_USUARIO>/dev/hermes-bridge/hermes_bridge_mcp.py
```

Ou editando diretamente o seu arquivo de configuração global (`~/.claude.json` ou `~/.claude/settings.json`):
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

---

### 2. OpenAI Codex

No seu arquivo `~/.codex/config.toml`:
```toml
[mcp_servers.hermes-bridge]
command = "/Users/<SEU_USUARIO>/.hermes/hermes-agent/venv/bin/python"
args = [
  "/Users/<SEU_USUARIO>/dev/hermes-bridge/hermes_bridge_mcp.py"
]
```

---

### 3. Google Antigravity

No seu arquivo `~/.gemini/config/mcp_config.json`:
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

### 4. Cursor / Windsurf / Claude Desktop / Zed

No arquivo de configuração de MCPs (`.cursor/mcp.json` ou `claude_desktop_config.json`):
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

> **Por que usar o Python do venv do Hermes?**  
> O interpretador em `~/.hermes/hermes-agent/venv/bin/python` já inclui Python 3.11 e os drivers SQLite mais recentes (sem o bug de WAL reset), evitando erros de versões antigas do Python do sistema.

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

## 📦 Como Ensinar seu Agente a Usar o Hermes

Este repositório inclui uma skill pronta para uso em [`skills/hermes-superbrain/SKILL.md`](skills/hermes-superbrain/SKILL.md).

### 1. Copie a skill para o seu projeto:
```bash
# Antigravity / Claude Code / Codex
mkdir -p .agents/skills/hermes-superbrain
cp skills/hermes-superbrain/SKILL.md .agents/skills/hermes-superbrain/SKILL.md
```

### 2. Adicione as instruções ao seu arquivo de regras (`AGENTS.md` ou `CLAUDE.md`):
```markdown
## Hermes Superbrain Integration
- Considere o Hermes como fonte primária de inteligência (Superbrain) deste ambiente.
- Utilize o MCP `hermes-bridge` (via skill `hermes-superbrain`) para consultar memórias e sessões passadas antes de planejar ou codificar.
- Quando aprender regras duráveis do projeto, grave na memória via `memory_record`.
- Sempre que concluir um marco relevante, sincronize a sessão via `session_sync`.
```

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
