from flask import Flask, request, jsonify, session, g
from flask_apscheduler import APScheduler
from collections import defaultdict

import requests, socket, logging, time, sys

# creates app
app = Flask(__name__)

'''
PRINT STATEMENTS DO NOT WORK
since print() statements will not be visible outside of if __name__ == "__main__":

INSTEAD USE THE FOLLOWING
the following can be used to output debug messages to kubectl logs: 
# app.logger.debug("message")
'''
# following line makes debug messages visible in kubectl logs
app.logger.setLevel(logging.DEBUG)

'''
GLOBAL VARIABLES
when using global variables, use the global_var dictionary
'''
global_var = defaultdict(lambda: None)

# CONSTANTS
RETRY_COUNT = 3

# scheduler
scheduler = APScheduler()

'''
given a request call, attempt_request attempts to
send request call several times and retries 5 seconds
after failure. attempt_request attempts to send request
call every RETRY_COUNT times.
'''
def attempt_request(request_func):
    # initial number of attempts
    attempts = RETRY_COUNT
    while attempts > 0:
        # attempt to send request
        try:            
            response = request_func()
            response.raise_for_status() 
            app.logger.debug("request successful!")
            return response
        # if error when sending request
        except requests.exceptions.RequestException as e:
            app.logger.error(f"request attempt {RETRY_COUNT - attempts} failed")
            app.logger.error(f"{e}")
            # reduces attempt count by 1
            attempts = attempts - 1
            # if more attempts, retries in 5 seconds
            if attempts > 0:
                app.logger.error("retrying in 5 seconds")
                time.sleep(5)    
    return None

# example of a function scheduled periodically with scheduler
def print_job():
    app.logger.debug("print job")
    app.logger.debug(global_var["ip_address"])
    app.logger.debug(global_var["p2p_id"])

# join network and update ["p2p_id"]
def join_network():
    # get current ip address
    global_var["ip_address"] = str(socket.gethostbyname(socket.gethostname()))
    # create values that will be sent to backend-pod as parameters
    args = {
        "ip_address": global_var["ip_address"]
    }

    # send post request to backend-pod via backend-service with 5 retries
    response = attempt_request(lambda: requests.post("http://backend-service:5000/join_network",json=args))
    # if no response, exit
    if response == None:
        sys.exit()

    # get value from response
    global_var["p2p_id"] = str(response.json().get("p2p_id"))

    app.logger.debug("p2p node joined network")

# retrieve topics and update to global_var["topics"]
def get_topics():
    # send get request to backend-pod via backend-service
    response = attempt_request(lambda: requests.get("http://backend-service:5000/get_topics"))
    
    if response == None:
        # empty topics
        global_var["topics"] = None
        return

    # get topics
    global_var["topics"] = response.json().get("topics")

    app.logger.debug("p2p node retrieved topics")

if __name__ == "__main__":

    # join network and get topics
    join_network()
    get_topics()

    # if no topics retrieved, exit
    if global_var["topics"] == None:
        sys.exit()

    # initialize and start scheduler
    # the following two lines are executed once
    scheduler.init_app(app)
    scheduler.start()

    # add job
    # jobs can be added and removed add any time
    # even in functions and route functions
    scheduler.add_job(id='print_job', func=print_job, trigger='interval', seconds=10)

    # run flask app
    app.run(host="0.0.0.0", port=5000)