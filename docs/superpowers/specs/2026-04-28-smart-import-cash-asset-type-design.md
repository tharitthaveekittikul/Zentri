# Design: Cash Accounts, Asset Type Auto-Detection & Smart Import Pipeline

**Date:** 2026-04-28  
**Status:** Approved

---

## Overview

Four interconnected features:
1. **Cash accounts** — track bank account balances as a portfolio asset class
2. **Asset type expansion + auto-detection** — add `cash` and `etf`, auto-infer type via per-row template rules
3. **Smart import pipeline** — LLM generates a reusable mapping template per platform; subsequent imports are template-only (no LLM cost)
4. **LLM provider configuration** — multi-provider support (Anthropic, OpenAI, Gemini, Ollama, OpenRouter) with per-feature model selection and editable system prompts

---

## 1. Cash Accounts

### Concept
Cash accounts (KBANK, DIME USD, DIME FCD, GSB, etc.) are treated as assets of type `cash`. No transaction-level tracking — user manually enters a balance snapshot per account per date.

### Data Model

**Asset** (new `cash` type):
```
symbol:     e.g. "KBANK_SAVINGS", "DIME_USD", "GSB"
asset_type: "cash"
currency:   "THB" | "USD" | "FCD" | ...
name:       human-readable label e.g. "KBANK Savings"
```

**CashBalance** (new table — balance snapshots):
```
id
asset_id    FK → Asset
user_id     FK → User
balance     Decimal
date        Date  (snapshot date)
notes       str (optional)
created_at
```

No buy/sell transactions for cash. Balance = latest snapshot for that account.

### UI Flow
- Settings → Cash Accounts → Add Account (name, currency, bank)
- Dashboard or dedicated page → "Update Balance" button → enter current balance + date
- History shows past snapshots as a sparkline

---

## 2. Asset Type Expansion & Auto-Detection

### Updated Asset Types
```python
ASSET_TYPES = ("us_stock", "thai_stock", "th_fund", "etf", "crypto", "gold", "cash")
```

`etf` is distinct from `us_stock` — same price source (yfinance) but treated separately in allocation analysis and portfolio categorization.

### Auto-Detection Priority Chain
```
1. Template per-row rules   (field-based: exchange/currency/symbol pattern per row)
2. Platform fallback        (if no rule matches)
3. LLM inference            (truly ambiguous rows only)
4. User override in preview (always available)
```

### Platform Examples
| Platform        | Has per-row rules? | Fallback        |
|-----------------|--------------------|-----------------|
| Finnomena       | No (all th_fund)   | `th_fund`       |
| Bualuang        | No (all thai_stock)| `thai_stock`    |
| DIME            | Yes (multi-type)   | `us_stock`      |
| Crypto exchange | No (all crypto)    | `crypto`        |

### Per-Row Rules (for multi-asset platforms like DIME)
LLM generates these rules once during template creation:
```json
"asset_type_rules": [
  { "field": "exchange", "values": ["XNAS", "XNYS", "XASE", "ARCX"], "asset_type": "us_stock" },
  { "field": "exchange", "values": ["XBKK"],                          "asset_type": "thai_stock" },
  { "field": "symbol",   "pattern": "^(GLD|IAU|GOLD|SGOL)$",         "asset_type": "gold" },
  { "field": "symbol",   "pattern": "^(SPY|QQQ|VTI|VOO|ARKK)$",      "asset_type": "etf" }
],
"asset_type_fallback": "us_stock"
```
Rules are evaluated top-to-bottom; first match wins.

### Currency Display (Settings Toggle)
- **Default currency**: user sets in Settings (e.g. THB)
- **Show conversion hint**: toggle ON/OFF in Settings
  - When ON: amounts in foreign currency show `≈ 31,000 THB` in small text below
  - Uses latest FX rate fetched by pipeline

---

## 3. Smart Import Pipeline

### Canonical Transaction Schema (Central Template)
All platforms normalize to this schema before import:

```
symbol        str        ticker or fund code
date          date       trade/settlement date
type          enum       BUY | SELL | DIVIDEND | REWARD | DEPOSIT | WITHDRAW
units         float      number of shares/units (null for cash)
price         float      price per unit in native currency
currency      str        USD | THB | ...
total_thb     float      total value in THB
fee_thb       float      fee in THB (default 0)
asset_type    str        from auto-detection chain
notes         str        optional
```

### Mapping Template (stored per platform in DB)

```json
{
  "platform_id": "uuid",
  "file_format": "csv | json",
  "json_path": "[].transactions[]",
  "column_signature": "sha256_of_headers",
  "field_map": {
    "share_name": "symbol",
    "unit": "units",
    "net_amount": "total_thb",
    "trade_date": "date"
  },
  "asset_type_rules": [
    { "field": "exchange", "values": ["XNAS", "XNYS", "XASE", "ARCX"], "asset_type": "us_stock" },
    { "field": "symbol",   "pattern": "^(SPY|QQQ|VTI|VOO)$",           "asset_type": "etf" },
    { "field": "symbol",   "pattern": "^(GLD|IAU|GOLD)$",              "asset_type": "gold" }
  ],
  "asset_type_fallback": "us_stock",
  "currency_default": "USD"
}
```

### Import Flow

```
User selects Platform (dropdown, can add new)
    ↓
User uploads file (CSV or JSON)
    ↓
System reads structure (headers / JSON keys)
    ↓
Template exists?
    ├── YES + signature matches  → Apply template directly (no LLM)
    ├── YES + signature mismatch → Warn: "File format may have changed"
    │                              Offer: Re-learn template or continue anyway
    └── NO template              → Send sample only (3 rows + headers) to LLM
                                   LLM returns mapping template JSON
                                   Show user template for confirm/edit
                                   Save template to DB
    ↓
Apply template → normalize all rows to canonical schema
    ↓
Fill asset_type using auto-detection priority chain
    ↓
LLM called only for rows with truly ambiguous fields
(not covered by template or platform default)
    ↓
Preview table (all rows, editable per cell)
    ↓
User confirms → rows inserted into transactions DB
```

### Key Constraints
- **LLM never sees full file** — only structure + 3 sample rows (privacy + token cost)
- **Template is idempotent** — can be regenerated any time from Settings
- **Template is user-editable** — power users can view/fix field_map in Settings → Platforms → Edit Template
- **Import batch audit** — store which template version (+ timestamp) was used per import batch

---

## 4. Portfolio Overview — Cash Display

- Cash grouped as one **"Cash"** row in overview allocation chart
- Drilldown available: expand to see per-account breakdown
- All values converted to default currency for display
- Conversion hint (≈ THB) shown below foreign-currency values when toggle is ON

---

## 5. LLM Provider Configuration

### Concept
Users configure one or more LLM providers in Settings. Each feature that uses LLM can independently select its provider and model. System prompts are user-editable per feature; human prompts are hardcoded in code and never exposed.

### Data Models

**ProviderConfig** (per user, one row per provider):
```
id
user_id          FK → User
provider         enum  anthropic | openai | gemini | ollama | openrouter
api_key          encrypted (AESGCM — existing encryption layer)
host_url         str   (Ollama only: e.g. http://localhost:11434)
is_connected     bool  (result of last connection test)
models_cache     JSONB (list of available model IDs fetched from provider)
models_fetched_at datetime
created_at
updated_at
```

**FeatureLLMConfig** (per user per feature):
```
id
user_id              FK → User
feature_key          str   (see Feature Keys below)
provider_config_id   FK → ProviderConfig
model                str   (selected from models_cache)
system_prompt        text  (user-editable; seeded from DEFAULT_SYSTEM_PROMPTS)
is_prompt_customized bool  (false = using default; true = user-modified)
created_at
updated_at
```

### Feature Keys
| feature_key | Usage |
|---|---|
| `import_template_generator` | Generate field mapping template from file sample |
| `transaction_classifier` | Classify ambiguous asset_type per row during import |
| `portfolio_analysis` | AI portfolio insights on overview page |
| `chat` | Conversational assistant with portfolio context |

### Fetching Models Per Provider
Model list fetched once and cached in `models_cache`. Refresh via manual button (never on every page load). Cache has no hard TTL — user-triggered only.

| Provider | Endpoint | Notes |
|---|---|---|
| Anthropic | `GET /v1/models` | Filter `type=model` |
| OpenAI | `GET /v1/models` | Filter IDs starting with `gpt-` |
| Gemini | `GET /v1/models` | Filter `supportedGenerationMethods` includes `generateContent` |
| Ollama | `GET /api/tags` | Returns locally installed models |
| OpenRouter | `GET /api/v1/models` | Large list — show name + pricing info |

### LLM Gateway (Backend Architecture)
Single entry point for all LLM calls — no feature ever calls a provider SDK directly:

```python
class LLMGateway:
    async def complete(feature_key: str, user_id: UUID, variables: dict) -> str:
        config = await get_feature_llm_config(feature_key, user_id)
        system = config.system_prompt
        human  = HUMAN_PROMPTS[feature_key].format(**variables)  # hardcoded, never exposed
        adapter = build_adapter(config.provider, config.api_key, config.host_url)
        return await adapter.complete(system, human, config.model)
```

Adapters: `AnthropicAdapter`, `OpenAIAdapter`, `GeminiAdapter`, `OllamaAdapter`, `OpenRouterAdapter` — all implement the same `.complete(system, human, model) → str` interface.

If provider not connected at runtime → raise explicit error, no silent fallback.

### Prompt Architecture
- **System prompt**: stored in DB, user-editable, seeded from `DEFAULT_SYSTEM_PROMPTS` dict in code
- **Human prompt**: hardcoded `str.format()` template in code, substitutes runtime variables, never shown to user
- **Reset to Default**: restores `system_prompt` from `DEFAULT_SYSTEM_PROMPTS[feature_key]` and sets `is_prompt_customized = false`
- **Update notice**: when app ships an improved default prompt, users with `is_prompt_customized = false` auto-receive it; customized users see a banner "A new default is available — Reset to apply"

### Settings UI Flow
```
Settings → AI & LLM
  ├── Providers
  │     ├── Anthropic   [API Key] [Test Connection ✅] [Refresh Models]
  │     ├── OpenAI      [API Key] [Test Connection ❌ Not configured]
  │     ├── Gemini      [API Key] [Test Connection]
  │     ├── Ollama      [Host URL] [Test Connection]
  │     └── OpenRouter  [API Key] [Test Connection]
  │
  └── Feature Prompts
        ├── Import Template Generator
        │     Provider [Ollama ▼]  Model [llama3.2 ▼]
        │     System Prompt [textarea] [Reset to Default]
        ├── Transaction Classifier
        │     Provider [Anthropic ▼]  Model [claude-haiku-4-5 ▼]
        │     System Prompt [textarea] [Reset to Default]
        ├── Portfolio Analysis
        │     Provider [Anthropic ▼]  Model [claude-sonnet-4-6 ▼]
        │     System Prompt [textarea] [Reset to Default]
        └── Chat
              Provider [OpenAI ▼]  Model [gpt-4o ▼]
              System Prompt [textarea] [Reset to Default]
```
Model dropdown shows only models from the selected provider's `models_cache`. If provider not connected → warning shown, save blocked.

---

## Out of Scope (YAGNI)

- Auto-scheduling imports (email parsing, file watching)
- Merging duplicate transactions across platforms automatically
- Bond / real estate asset types (add later if needed)
- Automatic fallback chain between providers (explicit error preferred)
- LLM usage cost tracking per feature
- Prompt versioning history

---

## Affected Files (Estimated)

| Layer | Files |
|-------|-------|
| Models | `asset.py` (add `cash`, `etf`), new `cash_balance.py`, new `import_template.py` |
| Schemas | `asset.py`, new `cash_balance.py`, new `import_template.py` |
| Services | new `cash_balance.py`, new `import_pipeline.py` (replaces `csv_import.py`) |
| API | `assets.py`, new `cash_balance.py`, `portfolio.py` |
| Migrations | new Alembic migration for `cash_balances`, `import_templates`, `provider_configs`, `feature_llm_configs` tables |
| Frontend | Overview page (cash row + drilldown), Settings (currency toggle, platform templates, AI providers, feature prompts), new Import page |
