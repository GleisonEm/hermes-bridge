---
name: hermes-superbrain
description: MANDATÓRIO: Consulte SEMPRE o Hermes (harness, memórias, sessões anteriores, tool calls e skills de domínio) como fonte primária de inteligência (Superbrain) antes de planejar, codificar ou diagnosticar qualquer tarefa neste workspace, e INCREMENTE a memória persistente com novas decisões duráveis aprendidas.
---

# Hermes Superbrain — Inteligência Compartilhada Antigravity ↔ Hermes

## Princípio Fundamental: Antigravity como Executor, Hermes como Superbrain

O **Antigravity** é o executor nativo (editor de arquivos, terminal, testes, streaming). O **Hermes Agent** é a base de conhecimento viva e acumulada (memória persistente, 110+ skills curadas de domínio, decisões de arquitetura e histórico de mais de 63.000 mensagens e tool calls).

**Regra de ouro bidirecional**:
1. **Leitura**: Nunca adivinhe regras de negócio, comandos, credenciais locais ou decisões passadas. **Consulte sempre o Hermes primeiro** via MCP `hermes-bridge`.
2. **Escrita / Incremento**: Quando uma nova decisão importante for tomada, um bug recorrente for desvendado ou o usuário definir uma regra durável ("lembre disso", "sempre faça assim"), **grave imediatamente na memória do Hermes** via `memory_record`.

---

## Como Consultar o Hermes (Leitura)

### 1. Início de Qualquer Tarefa ou Dúvida de Arquitetura
Antes de propor soluções em fluxos como SimPay, AgroRota, Uneplus/Sub, pagamentos, webhooks, infraestrutura ou regras de banco:
- Chame a ferramenta `context_pack` ou `memory_search` para capturar as restrições duráveis do usuário e as skills recomendadas pelo Hermes:
  ```json
  call_mcp_tool(
    ServerName: "hermes-bridge",
    ToolName: "context_pack",
    Arguments: {
      "task_description": "Descreva os termos centrais da tarefa (ex: webhook pix mercado pago)",
      "profile": "simpay",
      "max_skills": 3
    }
  )
  ```

### 2. Investigação de Erros, Histórico ou Decisões Passadas ("Como fizemos antes?")
Quando o usuário perguntar *"como resolvemos isso?"*, *"onde está tal configuração?"* ou quando um bug misterioso acontecer:
- **Busca Full-Text (FTS5)** em todo o histórico do Hermes:
  ```json
  call_mcp_tool(
    ServerName: "hermes-bridge",
    ToolName: "session_search",
    Arguments: {
      "query": "termo do erro ou funcionalidade",
      "profile": "simpay"
    }
  )
  ```
- **Inspecionar Tool Calls Reais** executadas pelo Hermes naquela sessão (para ver os comandos exatos que deram certo ou o retorno das APIs):
  ```json
  call_mcp_tool(
    ServerName: "hermes-bridge",
    ToolName: "session_tool_calls",
    Arguments: {
      "session_id": "<id_da_sessao>",
      "profile": "simpay"
    }
  )
  ```
- **Ler o Transcript da Conversa** para resgatar o raciocínio do modelo:
  ```json
  call_mcp_tool(
    ServerName: "hermes-bridge",
    ToolName: "session_get",
    Arguments: {
      "session_id": "<id_da_sessao>",
      "limit": 30,
      "profile": "simpay"
    }
  )
  ```

---

## Como Incrementar o Hermes (Escrita Durável)

Quando descobrir um fato operacional importante (ex: porta de serviço, segredo/env necessário, peculiaridade de um endpoint, decisão arquitetural acordada com o usuário):
- **Grave na memória durável** usando `memory_record`:
  ```json
  call_mcp_tool(
    ServerName: "hermes-bridge",
    ToolName: "memory_record",
    Arguments: {
      "content": "Fato conciso de 50-250 caracteres descrevendo a regra ou decisão.",
      "target": "memory",
      "action": "add",
      "profile": "simpay"
    }
  )
  ```
- Use `target: "memory"` para fatos do projeto/código e `target: "user"` para preferências do usuário.
- Se uma regra antiga ficou obsoleta, use `action: "replace"` com `old_text` para manter a memória compacta dentro do orçamento do Hermes.

---

## Seleção de Perfis

- **`simpay`**: Perfil principal de pagamentos, gateway SimPay, infraestrutura VPS, mercadopago, etc. (~500MB de histórico).
- **`sub`**: Perfil dedicado especificamente ao subacquirer Uneplus (`/Users/gemanuel/dev/sub`).
- **`default`**: Base geral do Hermes.

---

## Ferramentas Disponíveis no MCP `hermes-bridge`

| Ferramenta | Objetivo | Tipo |
| :--- | :--- | :--- |
| **`context_pack`** | Reúsa o harness oficial do Hermes para trazer Memória + Top Skills pontuadas | Leitura |
| **`memory_record`** | Incrementa, atualiza (`replace`) ou remove itens de `MEMORY.md` e `USER.md` usando o `MemoryStore` oficial | Escrita |
| **`memory_search`** | Busca linhas no `MEMORY.md` e `USER.md` de qualquer perfil | Leitura |
| **`session_search`** | Busca instantânea FTS5 em todas as mensagens do Hermes | Leitura |
| **`session_tool_calls`** | Raio-x das ferramentas chamadas (comandos do shell, SQL, retornos) | Leitura |
| **`session_get`** | Conversa completa de uma sessão | Leitura |
| **`session_list`** | Lista as últimas sessões gravadas | Leitura |
| **`skill_list` / `skill_view`** | Lista e lê os `SKILL.md` instalados no Hermes | Leitura |
| **`profile_list`** | Lista os perfis do Hermes | Leitura |

---

## Espelhamento de Sessões Antigravity ↔ Hermes (`session_sync`)

Você pode refletir e persistir conversas ativas do Antigravity diretamente no banco `state.db` do Hermes:
- **Por que usar**: Permite que o usuário abra o Hermes Desktop ou CLI (`hermes -s <id>`) e **continue exatamente de onde o Antigravity parou**, inclusive trocando de modelo ou usando ferramentas próprias do Hermes.
- **Chamada MCP**:
  ```json
  call_mcp_tool(
    ServerName: "hermes-bridge",
    ToolName: "session_sync",
    Arguments: {
      "conversation_id": "<id_da_conversa_antigravity>",
      "title": "Título descritivo da tarefa",
      "model_name": "gemini-3.8-flash",
      "profile": "simpay"
    }
  )
  ```
  *(Nota: se `model_name` for omitido, o MCP detecta e normaliza automaticamente o modelo ativo na sessão, ex: `gemini-3.8-flash`)*.
- **CLI Terminal**:
  ```bash
  hermes-superbrain -p simpay sync "<conversation_id>" "Título da tarefa"
  ```

---

## Padrão de Commits pós Rodada de Feature

Sempre que concluir uma rodada de desenvolvimento, implementação ou ajuste de feature:
1. **Formato obrigatório da mensagem de commit**:
   ```
   <modelo-atual>: <descrição concisa da feature ou alteração>
   ```
   *Exemplos*:
   - `gemini-3.8: Resolução de Payouts Pix (Telefone / Status / Reconciliação SimPay)`
   - `gpt-5.6-luna: Implementação de webhook idempotente e retry policy`
   - `claude-3.7-sonnet: Ajuste na tela de conciliação bancária do painel admin`

2. **Identificação do Modelo**:
   - Use o nome do modelo atualmente em execução no agente/sessão (ex: `gemini-3.8`, `gpt-5.6-luna`, `claude-3.7-sonnet`).
   - Mantenha a descrição objetiva, clara e em português ou inglês conforme o contexto do repositório.
