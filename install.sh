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
echo "==> Local directory: $HERE"
echo "==> Python interpreter: $PYTHON_EXEC"

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

# 3. Teste rápido de conectividade
echo "==> Testando comunicação com o Hermes..."
TEST_OUTPUT=$("$PYTHON_EXEC" -c "
import sys
sys.path.insert(0, '$HERE')
import hermes_bridge_mcp
print(hermes_bridge_mcp._tool_profile_list())
" 2>/dev/null || true)

if [ -n "$TEST_OUTPUT" ]; then
  echo "✅ Conexão com Hermes bem-sucedida!"
else
  echo "⚠️ Aviso: ~/.hermes não encontrado ou sem histórico ainda. O bridge funcionará normalmente assim que o Hermes for iniciado."
fi

# 4. Configuração automática do Claude Code (se o CLI 'claude' existir)
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
echo "               Configurações Prontas                   "
echo "======================================================="
echo ""
echo "Copie e cole a configuração abaixo no seu editor/agente:"
echo ""
echo "--- [1] Anthropic Claude Code (~/.claude/settings.json ou ~/.claude.json) ---"
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
echo "--- [4] Cursor / Zed / Claude Desktop ---"
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
echo "🎉 Instalação concluída! Teste no terminal com:"
echo "   hermes-superbrain list 3"
echo "======================================================="
