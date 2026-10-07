from flask import Flask, request, jsonify

app = Flask(__name__)

services = {}


# GET - Get all registered services
@app.route("/services", methods=["GET"])
def get_services():
    return jsonify(services)


# POST - Register a new service
@app.route("/services", methods=["POST"])
def register_service():
    data = request.json

    service_name = data.get("name")
    service_url = data.get("url")

    if not service_name or not service_url:
        return jsonify({"error": "name and url are required"}), 400

    services[service_name] = {
        "name": service_name,
        "url": service_url
    }

    return jsonify({
        "message": "Service registered successfully",
        "service": services[service_name]
    }), 201


# PUT - Update an existing service
@app.route("/services/<service_name>", methods=["PUT"])
def update_service(service_name):
    if service_name not in services:
        return jsonify({"error": "Service not found"}), 404

    data = request.json

    services[service_name]["url"] = data.get(
        "url",
        services[service_name]["url"]
    )

    return jsonify({
        "message": "Service updated successfully",
        "service": services[service_name]
    })


# DELETE - Remove a service
@app.route("/services/<service_name>", methods=["DELETE"])
def delete_service(service_name):
    if service_name not in services:
        return jsonify({"error": "Service not found"}), 404

    deleted_service = services.pop(service_name)

    return jsonify({
        "message": "Service deleted successfully",
        "service": deleted_service
    })


@app.route("/")
def home():
    return jsonify({
        "message": "Service Registry is running"
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)