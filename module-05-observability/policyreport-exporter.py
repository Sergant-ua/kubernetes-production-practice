import json
import os
import ssl
import time
import urllib.request
from datetime import datetime, timezone

API = "https://kubernetes.default.svc"
SA = "/var/run/secrets/kubernetes.io/serviceaccount"

NAMESPACES = ("student01", "student02", "student03")
POLICY = "require-readonly-rootfs"
INTERVAL = 30

with open(f"{SA}/token") as f:
    token = f.read().strip()

context = ssl.create_default_context(
    cafile=f"{SA}/ca.crt"
)

# Deduplification within one exporter process.
seen = set()


def fetch_reports(namespace):
    url = (
        f"{API}/apis/wgpolicyk8s.io/v1alpha2/"
        f"namespaces/{namespace}/policyreports"
    )

    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"}
    )

    with urllib.request.urlopen(
        req, context=context, timeout=10
    ) as response:
        return json.load(response)["items"]


def check():
    current = set()

    for namespace in NAMESPACES:
        reports = fetch_reports(namespace)

        for report in reports:
            scope = report.get("scope", {})

            # Track Pods only, avoiding duplicate results
            # from Deployment and ReplicaSet reports.
            if scope.get("kind") != "Pod":
                continue

            pod = scope.get("name", "unknown")
            uid = scope.get("uid", pod)

            for result in report.get("results", []):
                if result.get("policy") != POLICY:
                    continue

                if result.get("result") != "fail":
                    continue

                key = (
                    namespace,
                    uid,
                    result.get("policy"),
                    result.get("rule"),
                    result.get("message"),
                )

                current.add(key)

                if key in seen:
                    continue

                event = {
                    "timestamp": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "event": "kyverno_audit_failure",
                    "namespace": namespace,
                    "pod": pod,
                    "policy": POLICY,
                    "rule": result.get("rule"),
                    "result": "fail",
                    "message": result.get("message"),
                }

                print(json.dumps(event), flush=True)

    # Re-emit if a violation disappears and later reappears.
    seen.intersection_update(current)
    seen.update(current)


print("PolicyReport exporter started", flush=True)

while True:
    try:
        check()
    except Exception as error:
        print(
            json.dumps({
                "event": "exporter_error",
                "message": str(error),
            }),
            flush=True,
        )

    time.sleep(INTERVAL)
