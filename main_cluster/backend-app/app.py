from flask import Flask, request, jsonify, session, request, g
import requests, hashlib, logging,time
from collections import defaultdict

app = Flask(__name__)

'''
PRINT STATEMENTS DO NOT WORK
since print() statements will not be visible outside of if __name__ == "__main__":

the following can be used to output debug messages to kubectl logs: 
# app.logger.debug("message")
'''
# uncomment the following line to display debug messages to kubectl logs
app.logger.setLevel(logging.DEBUG)

'''
GLOBAL VARIABLES
When using global variables, use the global_var dictionary
'''
global_var = defaultdict(lambda: None)

# CONSTANTS
M_BITS = 64
RETRY_COUNT = 3

'''
given a request_func, attempt_request attempts to
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

# get topics
@app.route('/get_topics', methods=['GET'])
def get_topics():
    app.logger.debug("sent topics")
    return jsonify({'topics':[
        "food","tech","finance"
    ]})

# join network
@app.route('/join_network', methods=['POST'])
def new_p2p():
    # get ip address of new p2p node
    ip_address = str(request.json.get('ip_address'))
    app.logger.debug("ip address")
    app.logger.debug(ip_address)
    app.logger.debug(request.json)

    # calculate new p2p_id
    temp = hashlib.sha1(ip_address.encode()).hexdigest()
    p2p_id = str(int(temp[:M_BITS // 4], 16))

    app.logger.debug("new node joined")

    return jsonify({'p2p_id': p2p_id })

if __name__ == "__main__":
    # run flask app
    app.run(host="0.0.0.0", port=5000)
