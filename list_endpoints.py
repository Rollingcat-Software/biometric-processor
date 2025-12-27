#!/usr/bin/env python3
"""List all API endpoints from OpenAPI spec."""
import json
import httpx

response = httpx.get("http://localhost:8001/openapi.json", timeout=10)
data = response.json()

print("=" * 120)
print("ALL API ENDPOINTS")
print("=" * 120)
print()

for path, methods in sorted(data['paths'].items()):
    for method, info in methods.items():
        if method != 'parameters':
            print(f"{method.upper():8} {path:60} {info.get('summary', '')}")
