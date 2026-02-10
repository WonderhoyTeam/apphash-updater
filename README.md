# wonderhoy-apphash-updater

Hosted API that automatically extracts and serves `clientAppHash` and version data from Project Sekai APKs across all regions.

Based on [Sekai-World/sekai-apphash-updater](https://github.com/Sekai-World/sekai-apphash-updater).

## API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | All regions' cached data |
| `/{region}` | GET | Single region (`JP`, `EN`, `TW`, `KR`, `CN`) |
| `/health` | GET | Health check |
| `/admin/refresh?region=JP` | POST | Force refresh (requires `X-API-Key` header) |

Response example for `GET /JP`:
```json
{
  "appVersion": "4.0.5",
  "appHash": "...",
  "assetHash": "...",
  "dataVersion": "4.0.5",
  "multiPlayVersion": "4.0.0",
  "updatedAt": "2025-01-01T00:00:00+00:00"
}
```

## Configuration

All env vars use the `WONDERHOY_` prefix.

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind host |
| `PORT` | `8000` | Bind port |
| `REFRESH_INTERVAL_MINUTES` | `5` | Auto-refresh interval |
| `ADMIN_API_KEY` | *(empty)* | Required for `/admin/*` endpoints |
| `HTTP_PROXY` | *(none)* | Proxy for outbound requests |
| `ENABLED_REGIONS` | `JP,EN,TW,KR,CN` | Comma-separated regions to track |
| `UNITY_VERSION` | `2022.3.21f1` | Fallback Unity version for asset parsing |

## Running

```bash
uv sync
uv run wonderhoy
```

Or with Docker:

```bash
docker build -t wonderhoy .
docker run -p 8000:8000 -e WONDERHOY_ADMIN_API_KEY=secret wonderhoy
```

## License

MIT
