from flask import Flask, request, jsonify, session, request
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import socket

'''
This Flask app will send a message to other the flask apps
in the other pods.
'''

app = Flask(__name__)

# sends message to neighbors
def send_message():
    my_ip = socket.gethostbyname(socket.gethostname())
    # iterate through each node
    for i in range(0,100):
        neighbor_ip = "127.0.0." + str(i) + ":5000"
        # if the address is not it's own address
        if neighbor_ip != my_ip:
            # create message and url
            message = f"Hello from {my_ip}"
            url = f"http://{neighbor_ip}/receive-message"
            try:
                # send message
                response = requests.post(url, json={"message": message})
                print(f"Message sent to {neighbor_ip}. Response: {response.text}")
            except requests.exceptions.RequestException as e:
                pass
                # print(f"Failed to send message to {neighbor_ip}. Error: {e}")

# receive message
@app.route("/receive-message", methods=["POST"])
def receive_message():
    message = request.json["message"]
    print(f"Received message: {message}")
    return "Message received"

if __name__ == "__main__":
    # Create a background scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_message, "interval", seconds=10)

    # Start the scheduler
    scheduler.start()

    # Get the container IP address
    container_ip = socket.gethostbyname(socket.gethostname())

    # # Get the container port
    # container_port = request.environ.get('SERVER_PORT')

    # print(f"Container IP: {container_ip}")
    # print(f"Container Port: {container_port}")

    # Run the Flask app
    app.run(host="0.0.0.0", port=5000)
