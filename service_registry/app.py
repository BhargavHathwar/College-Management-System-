from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory registry: {"student_service": "http://127.0.0.1:5002"}
services = {}


@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Service Registry is running"})


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data or "name" not in data or "url" not in data:
        return jsonify({"error": "name and url are required"}), 400
    services[data["name"]] = data["url"]
    return jsonify({
        "message": "Service registered",
        "name": data["name"],
        "url": data["url"],
    }), 201


@app.route("/discover/<service_name>", methods=["GET"])
def discover(service_name):
    if service_name not in services:
        return jsonify({"error": "Service not found"}), 404
    return jsonify({"name": service_name, "url": services[service_name]})


@app.route("/services", methods=["GET"])
def list_services():
    return jsonify(services)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)