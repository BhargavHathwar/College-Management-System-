from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

GATEWAY_PORT = 5001
REGISTRY_URL = "http://127.0.0.1:5002"

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "service": "API Gateway",
        "status": "UP",
        "port": 5001
    }), 200


def discover_service(service_name):
    try:
        response = requests.get(
            f"{REGISTRY_URL}/discover/{service_name}",
            timeout=3
        )

        if response.status_code != 200:
            return None

        data = response.json()

        return data.get("url")

    except requests.RequestException:
        return None


@app.route("/api/v1/<service>/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def route_request(service, path):

    service_url = discover_service(service)

    if not service_url:
        return jsonify({
            "error": "Service unavailable",
            "service": service
        }), 503

    target_url = f"{service_url}/{path}"

    try:
        response = requests.request(
            method=request.method,
            url=target_url,
            headers={
                key: value
                for key, value in request.headers
                if key.lower() != "host"
            },
            params=request.args,
            json=request.get_json(silent=True),
            timeout=5
        )

        return (
            response.content,
            response.status_code,
            response.headers.items()
        )

    except requests.RequestException:
        return jsonify({
            "error": "Unable to reach downstream service",
            "service": service
        }), 503


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=GATEWAY_PORT,
        debug=True
    )