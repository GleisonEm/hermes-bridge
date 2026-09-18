#!/bin/bash
# Hermes Bridge MCP — Automatic Setup & Verification
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON_EXEC="$HOME/.hermes/hermes-agent/venv/bin/python"

if [ ! -f "$PYTHON_EXEC" ]; then
  PYTHON_EXEC="$(command -v python3 || true)"
fi

echo "======================================================="
echo "   Hermes Bridge MCP — Installer & Diagnostics         "
echo "======================================================="
echo "==> Diretório local: $HERE"
echo "==> Python utilizado: $PYTHON_EXEC"

# 1. Permissões de execução
chmod +x "$HERE/hermes_bridge_mcp.py"
chmod +x "$HERE/bin/hermes-superbrain"

# 2. Instalar CLI no ~/.local/bin se existir ou ~/.hermes/bin
BIN_TARGET="$HOME/.local/bin"
if [ ! -d "$BIN_TARGET" ]; then
  mkdir -p "$BIN_TARGET"
fi
cp -f "$HERE/bin/hermes-superbrain" "$BIN_TARGET/hermes-superbrain"
chmod +x "$BIN_TARGET/hermes-superbrain"
echo "==> CLI hermes-superbrain instalada em: $BIN_TARGET/hermes-superbrain"

# 3. Instalar Skill nos Harnesses detectados globalmente
echo "==> Detectando Harnesses de IA para instalação da Skill..."
SKILL_SRC="$HERE/skills/hermes-superbrain/SKILL.md"

if [ -d "$HOME/.claude" ]; then
  mkdir -p "$HOME/.claude/skills/hermes-superbrain"
  cp -f "$SKILL_SRC" "$HOME/.claude/skills/hermes-superbrain/SKILL.md"
  echo "  ✓ Skill instalada no Anthropic Claude Code: ~/.claude/skills/hermes-superbrain/"
fi

if [ -d "$HOME/.codex" ]; then
  mkdir -p "$HOME/.codex/skills/hermes-superbrain"
  cp -f "$SKILL_SRC" "$HOME/.codex/skills/hermes-superbrain/SKILL.md"
  echo "  ✓ Skill instalada no OpenAI Codex: ~/.codex/skills/hermes-superbrain/"
fi

if [ -d "$HOME/.gemini" ]; then
  mkdir -p "$HOME/.gemini/antigravity/builtin/skills/hermes-superbrain"
  cp -f "$SKILL_SRC" "$HOME/.gemini/antigravity/builtin/skills/hermes-superbrain/SKILL.md"
  echo "  ✓ Skill instalada no Google Antigravity: ~/.gemini/antigravity/builtin/skills/hermes-superbrain/"
fi

# 4. Teste rápido de conectividade com Hermes
echo "==> Testando comunicação com o Hermes..."
TEST_OUTPUT=$("$PYTHON_EXEC" -c "
import sys
sys.path.insert(0, '$HERE')
import hermes_bridge_mcp
print(hermes_bridge_mcp._tool_profile_list())
" 2>/dev/null || true)

if [ -n "$TEST_OUTPUT" ]; then
  echo "✅ Conexão com o banco do Hermes bem-sucedida!"
else
  echo "⚠️ Aviso: ~/.hermes não encontrado ou sem histórico ainda. O bridge funcionará normalmente assim que o Hermes for iniciado."
fi

# 5. Configuração automática do Claude Code (se o CLI 'claude' existir)
if command -v claude >/dev/null 2>&1; then
  echo ""
  echo "==> Claude Code detectado no PATH!"
  read -p "Deseja registrar o hermes-bridge no Claude Code agora? (s/N) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Ss]$ ]]; then
    claude mcp add hermes-bridge -- "$PYTHON_EXEC" "$HERE/hermes_bridge_mcp.py"
    echo "✅ hermes-bridge registrado no Claude Code com sucesso!"
  fi
fi

echo ""
echo "======================================================="
echo "          Configurações Prontas por Harness            "
echo "======================================================="
echo ""
echo "--- [1] Anthropic Claude Code (~/.claude.json ou ~/.claude/settings.json) ---"
cat << JSON
{
  "mcpServers": {
    "hermes-bridge": {
      "type": "stdio",
      "command": "$PYTHON_EXEC",
      "args": [
        "$HERE/hermes_bridge_mcp.py"
      ]
    }
  }
}
JSON

echo ""
echo "--- [2] OpenAI Codex (~/.codex/config.toml) ---"
cat << TOML
[mcp_servers.hermes-bridge]
command = "$PYTHON_EXEC"
args = [ "$HERE/hermes_bridge_mcp.py" ]
TOML

echo ""
echo "--- [3] Google Antigravity (~/.gemini/config/mcp_config.json) ---"
cat << JSON
{
  "mcpServers": {
    "hermes-bridge": {
      "command": "$PYTHON_EXEC",
      "args": [
        "$HERE/hermes_bridge_mcp.py"
      ]
    }
  }
}
JSON

echo ""
echo "--- [4] Cursor (.cursor/mcp.json ou ~/.cursor/mcp.json) ---"
cat << JSON
{
  "mcpServers": {
    "hermes-bridge": {
      "command": "$PYTHON_EXEC",
      "args": [
        "$HERE/hermes_bridge_mcp.py"
      ]
    }
  }
}
JSON

echo ""
echo "--- [5] Zed (~/.config/zed/settings.json) ---"
cat << JSON
{
  "context_servers": [
    {
      "id": "hermes-bridge",
      "command": {
        "path": "$PYTHON_EXEC",
        "args": ["$HERE/hermes_bridge_mcp.py"]
      }
    }
  ]
}
JSON

echo ""
echo "🎉 Instalação concluída! Teste no terminal com:"
echo "   hermes-superbrain list 3"
echo "======================================================="
