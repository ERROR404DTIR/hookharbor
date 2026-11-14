<div align="center"><img src="assets/banner.svg" width="100%"><h1>HookHarbor</h1><p>A local inbox for webhooks. Catch, inspect and export requests without exposing a public endpoint.</p></div>

## Features
- Local dashboard with auto-refreshing event list and request details.
- Captures method, path, headers, content type and raw request body.
- SQLite persistence; events survive restarts.
- JSON API for listing and inspecting captured events.
- 1 MB request-body limit and loopback-only binding.

## Run
```bash
python app.py
```
Open http://127.0.0.1:8765. Send a test request:
```bash
curl -X POST http://127.0.0.1:8765/hook/demo -H "Content-Type: application/json" -d '{"hello":"world"}'
```
Use `python app.py --port 9000 --db ./events.sqlite3` to customize.

Python 3.9+, standard library only. Data is stored in `hookharbor.sqlite3`. The server binds to 127.0.0.1 intentionally; it is not an internet-facing webhook relay.

## Tests
```bash
python -m unittest discover -s tests -v
```

MIT License.