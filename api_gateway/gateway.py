
from flask import Flask, request, jsonify, Response
import requests
import time
from threading import Lock

app = Flask(__name__)

GATEWAY_PORT = 5001
REGISTRY_URL = "http://127.0.0.1:5002"

FAILURE_THRESHOLD = 3
RECOVERY_TIMEOUT = 10

# Each service maintains its own circuit-breaker state.
circuit_breakers = {}
circuit_lock = Lock()


def get_circuit(service):
    with circuit_lock:
        if service not in circuit_breakers:
            circuit_breakers[service] = {
                "state": "CLOSED",
                "failures": 0,
                "opened_at": None
            }
        return circuit_breakers[service]



def circuit_allows_request(service):
    with circuit_lock:
        circuit = circuit_breakers.setdefault(service, {
            "state": "CLOSED",
            "failures": 0,
            "opened_at": None
        })

        if circuit["state"] == "OPEN":
            elapsed = time.monotonic() - circuit["opened_at"]

            if elapsed >= RECOVERY_TIMEOUT:
                circuit["state"] = "HALF_OPEN"
                return True

            return False

        if circuit["state"] == "HALF_OPEN":
            return False

        return True


def record_success(service):
    with circuit_lock:
        circuit = circuit_breakers.setdefault(service, {
            "state": "CLOSED",
            "failures": 0,
            "opened_at": None
        })

        circuit["state"] = "CLOSED"
        circuit["failures"] = 0
        circuit["opened_at"] = None


def record_failure(service):
    with circuit_lock:
        circuit = circuit_breakers.setdefault(service, {
            "state": "CLOSED",
            "failures": 0,
            "opened_at": None
        })

        circuit["failures"] += 1

        if (
            circuit["state"] == "HALF_OPEN"
            or circuit["failures"] >= FAILURE_THRESHOLD
        ):
            circuit["state"] = "OPEN"
            circuit["opened_at"] = time.monotonic()


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "service": "API Gateway",
        "status": "UP",
        "port": GATEWAY_PORT
    }), 200


@app.route("/circuit-status", methods=["GET"])
def circuit_status():
    with circuit_lock:
        return jsonify({
            service: {
                "state": circuit["state"],
                "failures": circuit["failures"]
            }
            for service, circuit in circuit_breakers.items()
        }), 200


def discover_service(service_name):
    try:
        response = requests.get(
            f"{REGISTRY_URL}/discover/{service_name}",
            timeout=3
        )

        if response.status_code != 200:
            return None

        return response.json().get("url")

    except (requests.RequestException, ValueError):
        return None


@app.route(
    "/api/<version>/<service>/<path:path>",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
def route_request(version, service, path):
    # Only explicitly supported API versions are accepted.
    if version not in ("v1", "v2"):
        return jsonify({
            "error": "Unsupported API version",
            "supported_versions": ["v1", "v2"]
        }), 400

    if not circuit_allows_request(service):
        return jsonify({
            "error": "Circuit breaker is OPEN",
            "service": service,
            "retry_after_seconds": RECOVERY_TIMEOUT
        }), 503

    service_url = discover_service(service)

    if not service_url:
        record_failure(service)
        return jsonify({
            "error": "Service unavailable",
            "service": service
        }), 503

    target_url = f"{service_url.rstrip('/')}/{path.lstrip('/')}"

    try:
        response = requests.request(
            method=request.method,
            url=target_url,
            headers={
                key: value
                for key, value in request.headers
                if key.lower() not in ("host", "content-length")
            },
            params=request.args,
            data=request.get_data(),
            timeout=5,
            allow_redirects=False
        )

        # Only server-side failures count toward opening the breaker.
        # Normal client errors such as 400 or 404 are not service failures.
        if response.status_code >= 500:
            record_failure(service)
        else:
            record_success(service)

        excluded_headers = {
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection"
        }

        headers = [
            (key, value)
            for key, value in response.headers.items()
            if key.lower() not in excluded_headers
        ]

        return Response(
            response.content,
            status=response.status_code,
            headers=headers
        )

    except requests.RequestException:
        record_failure(service)
        return jsonify({
            "error": "Unable to reach downstream service",
            "service": service
        }), 503


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=GATEWAY_PORT,
        debug=False
    )
