"""Configure Railway services with start commands via GraphQL API."""
import json
import sys
import urllib.request

token = sys.argv[1]

QUERY = """
mutation($id: String!, $envId: String!, $input: ServiceUpdateInput!) {
  serviceUpdate(id: $id, environmentId: $envId, input: $input) { id }
}
"""

ENV_ID = "6bd1f064-e980-47e0-86a7-4c9a787ab2b9"

SERVICES = [
    {
        "name": "backend",
        "id": "8a00f283-98d1-4fee-94b0-89ebd4f7d539",
        "buildCommand": "pip install -e .",
        "startCommand": "uvicorn rawl.main:create_app --factory --host 0.0.0.0 --port 8080",
        "rootDirectory": "packages/backend",
    },
    {
        "name": "worker",
        "id": "c9fe435e-e6b7-49de-8969-51fbbb725f38",
        "buildCommand": "pip install -e .",
        "startCommand": "celery -A rawl.celery_app worker -l info --pool=prefork --concurrency=2",
        "rootDirectory": "packages/backend",
    },
    {
        "name": "beat",
        "id": "6b31e468-4365-4d61-a988-e172c652cc25",
        "buildCommand": "pip install -e .",
        "startCommand": "celery -A rawl.celery_app beat -l info",
        "rootDirectory": "packages/backend",
    },
]

for svc in SERVICES:
    payload = {
        "query": QUERY,
        "variables": {
            "id": svc["id"],
            "envId": ENV_ID,
            "input": {
                "buildCommand": svc["buildCommand"],
                "startCommand": svc["startCommand"],
                "rootDirectory": svc["rootDirectory"],
            },
        },
    }
    req = urllib.request.Request(
        "https://backboard.railway.app/graphql/v2",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read().decode())
        print(f"{svc['name']}: OK - {json.dumps(result)}")
    except Exception as e:
        print(f"{svc['name']}: FAILED - {e}")
        if hasattr(e, 'read'):
            print(f"  Response: {e.read().decode()}")
