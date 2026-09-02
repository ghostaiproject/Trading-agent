# Trading Agent Dashboard

A real-time web dashboard for monitoring your trading agent, account state, and decision logs.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the dashboard API server

In one terminal, run:

```bash
python -m trading_agent.dashboard_api
```

This will start a read-only FastAPI server on `http://127.0.0.1:8000`.

### 3. Open the dashboard

```bash
# Option A: Open the HTML file in a browser
open trading_agent/dashboard.html

# Option B: Serve it with a simple HTTP server
python -m http.server --directory trading_agent 8080
```

Then navigate to `http://127.0.0.1:8080/dashboard.html` (if using Option B).

### 4. Start the trading agent normally

In another terminal:

```bash
python -m trading_agent.main
# or
python -m trading_agent.main --loop --interval 900
```

The dashboard will poll the API every 10 seconds and display:
- **Account**: net liquidation, cash balance, buying power
- **Positions**: live holdings and their current values
- **Decisions**: recent proposals, risk checks, and approvals (from `logs/decisions-*.jsonl`)
- **Status**: connection indicator showing if the API is reachable

## Architecture

- **dashboard_api.py**: FastAPI server that runs independently of the trading loop
  - Connects to IBKR on startup to fetch account & positions (cached 30s to avoid overload)
  - Reads `logs/decisions-*.jsonl` for the decision audit trail
  - Exposes `/api/state` endpoint returning account, positions, and recent logs
  - Listens only on `127.0.0.1:8000` (localhost) for safety

- **dashboard.html**: Single-page app styled in cyberpunk theme
  - Fetches `/api/state` every 10 seconds
  - Updates account balances and position values in real-time
  - No modifications needed to the trading loop or its operation

## Customization

### Change API port
Edit `dashboard_api.py`, line ~141:
```python
uvicorn.run(app, host="127.0.0.1", port=9000, ...)  # change port here
```

Then update `dashboard.html`, line ~1490:
```javascript
const API_BASE = 'http://127.0.0.1:9000';  // match here
```

### Cache TTL for broker data
Edit `dashboard_api.py`, line ~30:
```python
self.cache_ttl = 30  # seconds between IBKR queries
```

Increase this if IBKR is slow; decrease for more real-time data.

### Display scale, theme
Use the gear icon (⚙) in the dashboard top-right to adjust theme, display scale, and username.

## API Endpoints

### `GET /api/state`
Returns current account state, positions, and recent decision logs.

```json
{
  "timestamp": "2026-09-02T15:32:07.123456Z",
  "account": {
    "net_liquidation": 38500.00,
    "cash_balance": 19000.00,
    "buying_power": 28000.00
  },
  "positions": {
    "AAPL": {
      "quantity": 25,
      "avg_cost": 190.50,
      "market_price": 228.60,
      "market_value": 5715.00
    }
  },
  "recent_decisions": [...]
}
```

### `GET /api/health`
Liveness check.

## Safety & Design

- **Read-only**: The API reads logs and account state; it **never** places orders.
- **Independent**: Dashboard runs in a separate process; if it crashes, the trading loop continues.
- **Localhost only**: Listens on `127.0.0.1` by design — not exposed to the network.
- **Caching**: Broker queries are cached 30s to avoid hammering IBKR with every dashboard refresh.

## Troubleshooting

**Dashboard shows "✗ Offline"**
- Ensure the API server is running (`python -m trading_agent.dashboard_api`)
- Check for CORS/connection errors in the browser console

**Account balances not updating**
- Verify IBKR/TWS is running with API enabled
- Check `logs/` directory has `decisions-*.jsonl` files with recent entries

**API connects but no positions show**
- Positions only appear if you hold any stocks
- Check IBKR that you have open positions in your account
