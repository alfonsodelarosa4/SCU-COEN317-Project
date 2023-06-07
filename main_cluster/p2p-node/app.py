import hashlib
from flask import Flask, request, jsonify, session, g
from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient
from bson.objectid import ObjectId
from collections import defaultdict
import requests, socket, logging, time, sys, threading,os,hashlib
import random
import math
import signal


# CONSTANTS
RETRY_COUNT = 3

'''
GLOBAL VARIABLES
when using global variables, use the global_var dictionary
'''
global_var = defaultdict(lambda: None)

# creates app
app = Flask(__name__)

# scheduler
scheduler = APScheduler()

'''
PRINT STATEMENTS DO NOT WORK
since print() statements will not be visible outside of if __name__ == "__main__":

INSTEAD USE THE FOLLOWING
the following can be used to output debug messages to kubectl logs: 
# app.logger.debug("message")
'''
# following line makes debug messages visible in kubectl logs
app.logger.setLevel(logging.DEBUG)

# MongoDB database
mongo_client = MongoClient('mongodb://localhost:27017')
db = mongo_client.my_database
subscribed_topics_db = db['subscribed_topics']
topic_neighbors_db = db['topic_neighbors']
posts_db = db['posts']

# lock mechanism
class ReadAndWriteLock():
    def __init__(self):
        self.write_lock = threading.Lock()
        self.readers_lock = threading.Lock()
        self.readers_count = 0
    
    def acquire_writelock(self):
        self.write_lock.acquire()

    def release_writelock(self):
        self.write_lock.release()

    def acquire_readlock(self):
        self.readers_lock.acquire()
        self.readers_count += 1
        if self.readers_count == 1:
            self.write_lock.acquire()
        self.readers_lock.release()

    def release_readlock(self):
        self.readers_lock.acquire()
        self.readers_count -= 1
        if self.readers_count == 0:
            self.write_lock.release()
        self.readers_lock.release()
    
rw_locks = defaultdict(lambda:ReadAndWriteLock())

class SubscribedTopic:
    def __init__(self,name):
        self.name = name

class TopicNeighbor:
    def __init__(self,ip_address,topic,p2p_id):
        self.ip_address = ip_address
        self.p2p_id = p2p_id
        self.topic = topic

class Post:
    def __init__(self, topic,ip_address,text,timestamp,hash_id):
        self.topic = topic
        self.ip_address = ip_address
        self.text = text
        self.timestamp = timestamp
        self.hash_id = hash_id


# LEADER
# set the leader
def set_leader(ip_address,p2p_id):
    # concurrency: read-write lock
    rw_locks["leader"].acquire_writelock()
    global_var["leader"] = (ip_address,p2p_id)
    rw_locks["leader"].release_writelock()

# get the leader
# return ip address of the leader
def get_leader():
    # concurrency: read-write lock
    rw_locks["leader"].acquire_readlock()
    leader_info = global_var["leader"]
    rw_locks["leader"].release_readlock()
    if leader_info == None:
        app.logger.debug("no leader")
        return None
    else:
        return leader_info

# SubscribedTopic
@app.route('/create-subscribed-topic', methods=['POST'])
def http_create_subscribed_topic():
    name = str(request.json.get('name'))
    create_subscribed_topic(name)
    if name == "" or name == None:
        return ({"error":"invalid name"})
    else:
        return jsonify({"message": f'created {name}'})

# create topic
def create_subscribed_topic(name):
    # concurrency: read-write lock
    rw_locks["topic"].acquire_writelock()
    topic = subscribed_topics_db.find_one({'name':name})
    if topic is not None:
        rw_locks["topic"].release_writelock()
        app.logger.debug("topic already exists")
        return False
    new_topic = SubscribedTopic(name=name)
    topic_id = subscribed_topics_db.insert_one(new_topic.__dict__).inserted_id
    rw_locks["topic"].release_writelock()
    return True

# get subscribed topics
def get_subscribed_topics():
    # concurrency: read-write lock
    rw_locks["topic"].acquire_readlock()
    topics = subscribed_topics_db.find()
    rw_locks["topic"].release_readlock()   
    return [topic["name"] for topic in topics]

# get specific subscribed topic
def get_subscribed_topic(name):
    # concurrency: read-write lock
    rw_locks["topic"].acquire_readlock()
    topic = subscribed_topics_db.find_one({'name':name})
    rw_locks["topic"].release_readlock()   
    return topic

# delete subscribed topic
# returns whether deleted
def delete_subscribed_topic(name):
    # concurrency: read-write lock
    rw_locks["topic"].acquire_writelock()
    result = subscribed_topics_db.delete_one({'name': name})
    if result.deleted_count != 1:
        app.logger.debug("topic not found")
    rw_locks["topic"].release_writelock()

# TopicNeighbor
# create topic neighbor
@app.route('/create-topic-neighbor', methods=['POST'])
def http_create_topic_neighbor():
    # concurrency: read-write lock
    ip_address = str(request.json.get('ip_address'))
    topic = str(request.json.get('topic'))
    p2p_id = str(request.json.get('p2p_id'))
    return jsonify({"message": str(create_topic_neighbor(ip_address,topic,p2p_id))})

def create_topic_neighbor(ip_address,topic,p2p_id):
    # concurrency: read-write lock
    rw_locks["topic-neighbor"].acquire_writelock()
    new_neighbor = TopicNeighbor(ip_address=ip_address,topic=topic,p2p_id=p2p_id)
    topic_id = topic_neighbors_db.insert_one(new_neighbor.__dict__).inserted_id
    rw_locks["topic-neighbor"].release_writelock()
    return str(topic_id)

@app.route('/get-all-topic-neighbors')
def get_all_topic_neighbors():
    rw_locks["topic-neighbor"].acquire_readlock()
    entries = topic_neighbors_db.find()
    rw_locks["topic-neighbor"].release_readlock()
    neighbors = [str(entry) for entry in entries]
    return jsonify({"neighbors":str(neighbors)})

# get topic neighbors
# return list of ip addresses
def get_topic_neighbors(topic):
    # concurrency: read-write lock
    rw_locks["topic-neighbor"].acquire_readlock()
    neighbors = topic_neighbors_db.find({'topic':topic})
    rw_locks["topic-neighbor"].release_readlock()
    return [neighbor["ip_address"] for neighbor in neighbors]

# gets ip addresses of each topic neighbor
# return list of ip addresses
def get_topic_neighbors_from_all_topics():
    # concurrency: read-write lock
    rw_locks["topic-neighbor"].acquire_readlock()
    neighbors = topic_neighbors_db.find()
    rw_locks["topic-neighbor"].release_readlock()
    return list(set([neighbor["ip_address"] for neighbor in neighbors]))

# gets p2p_ids of each topic neighbor
# return list of p2p_ids
def get_p2pids_of_all_neighbors():
    # concurrency: read-write lock
    rw_locks["topic-neighbor"].acquire_readlock()
    neighbors = topic_neighbors_db.find()
    rw_locks["topic-neighbor"].release_readlock()
    neighbor_hash = dict()
    for neighbor in neighbors:
        neighbor_hash[neighbor["ip_address"]] = neighbor["p2p_id"]
    return neighbor_hash

# delete a neighbor from all topics
def delete_neighbor_from_all_topics(ip_address):
    # concurrency: read-write lock
    rw_locks["topic-neighbor"].acquire_writelock()
    result = topic_neighbors_db.delete_many({'ip_address':ip_address})
    rw_locks["topic-neighbor"].release_writelock()

# delete all neighbors of from a topics
def delete_all_neighbors_from_a_topic(topic):
    # concurrency: read-write lock
    rw_locks["topic-neighbor"].acquire_writelock()
    results = topic_neighbors_db.delete_many({'topic':topic})
    rw_locks["topic-neighbor"].release_writelock()

# Post
# create post
def create_post(topic,ip_address,text,timestamp,hash_id):
    # concurrency: read-write lock
    rw_locks["post"].acquire_writelock()
    new_post = Post(topic=topic,ip_address=ip_address,text=text,timestamp=timestamp,hash_id=hash_id)
    post_id = posts_db.insert_one(new_post.__dict__).inserted_id
    app.logger.debug
    rw_locks["post"].release_writelock()

# get posts by topic
def get_posts_by_topic(topic):
    # concurrency: read-write lock
    rw_locks["post"].acquire_readlock()
    posts = posts_db.find({'topic':topic})
    rw_locks["post"].release_readlock()
    return [post for post in posts]

#get post by hashid
def get_post(hash_id):
    # concurrency: read-write lock
    rw_locks["post"].acquire_readlock()
    post = posts_db.find_one({'hash_id': hash_id})
    rw_locks["post"].release_readlock()
    return post

'''
# example of a function scheduled periodically with scheduler
def print_job():
    app.logger.debug("print job")
    app.logger.debug(global_var["ip_address"])
    app.logger.debug(global_var["p2p_id"])

    if not global_var["turn"]:
        app.logger.debug("create tom hanks user")
        create_user(name="Tom Hanks", email="tomhanks@gmail.com")

        global_var["turn"] = True
    else:
        users = get_users()
        app.logger.debug(users)

        global_var["turn"] = False
'''

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

'''
given a request_func, attempt_request attempts to
send request call once with a timeout used for failure monitoring.
'''
def attempt_one_request(request_func):
    # attempt to send request
    try:            
        response = request_func()
        response.raise_for_status() 
        app.logger.debug("request successful!")
        return response
    # if error when sending request
    except requests.exceptions.RequestException as e:
        app.logger.error(f"request attempt failed")
        app.logger.error(f"{e}")   
    return None

# join network and update ["p2p_id"]
def join_network():
    # get current ip address
    global_var["ip_address"] = str(socket.gethostbyname(socket.gethostname()))
    app.logger.debug("ip address: " + str(global_var["ip_address"]))
    # create values that will be sent to backend-pod as parameters
    args = {
        "ip_address": global_var["ip_address"]
    }

    # send post request to backend-pod via backend-service with 5 retries
    response = attempt_request(lambda: requests.post("http://backend-service:5000/join-network",json=args))
    # if no response, exit
    if response == None:
        sys.exit()   

    # get value from response
    global_var["p2p_id"] = str(response.json().get("p2p_id"))
    app.logger.debug("p2p_id: " + str(global_var["p2p_id"]))

    app.logger.debug("p2p node joined network")

# get the information of leader from backend.
def get_leader_backend():
# send get request to backend-pod via backend-service
    app.logger.debug("get_leader process")
    app.logger.debug("get_leader: retrieve leader from backend")
    response = attempt_request(lambda: requests.get("http://backend-service:5000/get-leader-backend"))
    if response is None:
        #No response from backend server, assuming server failure
        #update all p2p nodes about server failer
        app.logger.debug("Backend server hasn't replied back")
        send_post("system","Backend failed")
    message = response.json().get("message")
    if message == "no leader":
        app.logger.debug("get_leader: backend does not have leader")
        app.logger.debug("get_leader: current node will attempt to be first leader")
        # no leader
        # create POST request to backend service
        args = {
            "ip_address": global_var["ip_address"],
            "p2p_id": global_var["p2p_id"]
        }
        response = attempt_request(lambda: requests.post("http://backend-service:5000/set-first-leader",json=args))
        if response is None:
            #No response from backend server, assuming server failure
            #update all p2p nodes about server failer
            app.logger.debug("Backend server hasn't replied back")
            send_post("system","Backend failed")

        message = response.json().get("message")
        # if current p2p node is assigned leader
        if message == "you are leader":
            app.logger.debug("get_leader: current node won. current will be first leader.")
            # updates leader to ip address and p2p_id of current p2p node
            set_leader(ip_address=global_var["ip_address"],p2p_id=global_var["p2p_id"])
            leader_setup()
            app.logger.debug(f'leader information: {global_var["leader"]}')
            
        # if a different p2p node is assigned leader
        else:
            app.logger.debug("get_leader: current failed to be first leader.")
            # updates leader to ip address and p2p_id from the values of the response
            # ip address and p2p_id retrieved from 
            leader_ip_address =  response.json().get("ip_address") 
            leader_p2p_id = response.json().get("p2p_id")
            set_leader(ip_address=leader_ip_address,p2p_id=leader_p2p_id)
            app.logger.debug(f'leader information: {global_var["leader"]}')
        
    else:
        app.logger.debug("get_leader: backend does have leader")
        # leader already exists and that information is received from backend
        ip_address = response.json().get("ip_address")
        p2p_id = response.json().get("p2p_id")
        set_leader(ip_address=ip_address,p2p_id=p2p_id)
        app.logger.debug(f'leader information: {global_var["leader"]}')

# retrieve topics and update to global_var["topics"]
def get_topics():
    # send get request to backend-pod via backend-service
    response = attempt_request(lambda: requests.get("http://backend-service:5000/get-topics"))
    # if no response
    if response == None:
        #No response from backend server, assuming server failure
        #update all p2p nodes about server failer
        app.logger.debug("Backend server hasn't replied back")
        send_post("system","Backend failed")
        return

    # get topics and assign topics
    global_var["topics"] = response.json().get("topics",[])

    app.logger.debug("p2p node retrieved topics:")
    app.logger.debug(f'{global_var["topics"]}')

# http endpoint: send posts to the nodes
@app.route('/send_post', methods=['POST'])
def http_send_post():
    topic = str(request.json.get('topic'))
    text = str(request.json.get('text'))
    return jsonify({"message": str(send_post(topic,text))})

# create hash id based on ip address, topic, text, and timestamp
def generate_unique_id(ip_address, topic,text,timestamp):
    concatenated_string = ip_address + topic + text + str(timestamp)
    hash_object = hashlib.sha256(concatenated_string.encode())
    # Get the hexadecimal representation of the hash
    unique_id = str(hash_object.hexdigest())
    return unique_id

# function: send post as publisher and send to neighbor of topic
def send_post(topic,text):
    timestamp = time.time()
    hash_id = generate_unique_id(global_var["ip_address"], topic,text,timestamp)
    post_id = create_post(topic,global_var["ip_address"],text,timestamp,hash_id)
    post = posts_db.find_one({"_id": post_id})
    # if system post, get neighbors of all topics
    if topic == "system" or "delete_node":
        neighbors = get_topic_neighbors_from_all_topics()
    # if not system post, get neighbors of one topic
    else:
        neighbors = get_topic_neighbors(topic)
    app.logger.debug(f'send_post: this current p2p node will create the following post: topic({topic}), text({text}), timestamp({timestamp})')
    # iterate through each neighbor, send post to neighbor
    for neighbor in neighbors:
        args = {
            "author_ip_address": global_var["ip_address"],
            "sender_ip_address": global_var["ip_address"],
            "text": text,
            "hash_id": hash_id,
            "timestamp": str(timestamp),
            "topic": topic,
        }
        app.logger.debug(f'send_post: sending post to p2p node with ip address ({neighbor})')
        url = f"http://{neighbor}:5000/relay_post"
        response = attempt_request(lambda: requests.post(url,json=args))
        
        if response is None:
            app.logger.debug(f"{neighbor} did not receive the post related to the topic{topic}")
    app.logger.debug(f"finished sending post related to the topic: {topic}")

# http endpoint: receive post and send to neighbors except sender. if duplicate, ignore
@app.route('/relay_post', methods=['POST'])
def http_relay_post():
    # get info from JSON body in http message
    data = request.get_json()
    hash_id = data.get('hash_id')
    topic = data.get('topic')
    text = data.get('text')
    timestamp = data.get('timestamp')
    topic = data.get('topic')
    author_ip_address = data.get('author_ip_address')
    sender_ip_address = data.get('sender_ip_address')
    app.logger.debug(f'relay_post: received post with the following information: topic ({topic}), text ({text}), timestamp({timestamp})')
    # check if post already exists
    existing_post = get_post(hash_id)
    # if duplicate hash id,
    if existing_post is not None:
        # check if other values are the same too
        if (existing_post["ip_address"] == author_ip_address and existing_post["topic"] == topic and existing_post["text"] == text and existing_post["timestamp"] == timestamp):
            # A post with this post_id already exists, so the incoming post is a duplicate
            app.logger.debug("relay_post: duplicate post received ")
            return jsonify({"message": "Duplicate post received"})
    # store post as entry
    create_post(topic,author_ip_address,text,timestamp,hash_id)
    # if system post, get neighbors of all topics
    if topic == "system" or "delete_node":
        neighbors = get_topic_neighbors_from_all_topics()
    # if not system post, get neighbors of one topic
    else:
        neighbors = get_topic_neighbors(topic)
    # if post is delete node
    if topic == "delete_node":
        delete_neighbor_from_all_topics(text)
    app.logger.debug(f'relay_post: p2p node will now relay the post to other topic neighbors')
    # iterate through each neighbor, send post to neighbor
    for neighbor in neighbors:
        # do not sent post to sender
        if neighbor == author_ip_address or sender_ip_address:
            continue
        app.logger.debug(f'relay_post: p2p node will now relay the post to p2p node with ip address {neighbor}')
        args = {
            "sender_ip_address": global_var["ip_address"],
            "author_ip_address": author_ip_address,
            "text": text,
            "hash_id": hash_id,
            "timestamp": str(timestamp),
            "topic": topic
        }
        url = f"http://{neighbor}:5000/relay_post"
        response = attempt_request(lambda: requests.post(url,json=args))
        if response is None:
            app.logger.debug(f"relay_post: {neighbor} did not receive the post related to the topic{topic}")
    # Send a response back to the originating node
    return jsonify({"message": "Post received and saved"})

# check backend for failure
def checking_backend():
    app.logger.debug("checking_backend: checking backend for failure")
    # get current learder's ip_address
    args = {
        "ip_address": global_var["ip_address"],
        "message": "checking on backend server"
    }
    url = f"http://backend-service:5000/failure-ping"
    response = attempt_one_request(lambda: requests.post(url,json=args, timeout=5))
    # if no response, assume failure
    if response is None:
        #No response from backend server, assuming server failure
        #update all p2p nodes about server failer
        app.logger.debug("checking_backend: Backend server hasn't replied back. Backend server failed. Will send 'backend server terminated' message to all neighbors.")
        send_post("system","Backend failed")
    else:
        app.logger.debug("checking_backend: Backend server responded")

# ping-ack protocol: receive failure ping, send ack
@app.route('/failure-ping', methods=['POST'])
def failure_ping():
    return jsonify({"message": f"Message received and Acknowledged"})

# check random node for failure
def checking_random_node():
    app.logger.debug("checking_random_node: random p2p node ping monitor: checking random p2p node for failure")
    # get ip addresses of all neighbors
    ip_addresses = get_topic_neighbors_from_all_topics()
    (leader_ip_address, _ ) = get_leader()
    if leader_ip_address in ip_addresses:
        ip_addresses.remove(leader_ip_address)
    if len(ip_addresses) == 0:
        app.logger.debug("checking_random_node: no neighbors")
        return
    # pick a random one
    random_ip_address = random.choice(ip_addresses)
    args = {
        "message": "checking on random node"
    }
    # check that ip address
    url = f"http://{random_ip_address}:5000/failure-ping"
    response = attempt_one_request(lambda: requests.post(url,json=args, timeout=5))
    # if no response, assume failure
    if response is None:
        #No response from thenode, assuming node failure
        #update all p2p nodes about node failer
        app.logger.debug(f"checking_random_node: node with ip address {random_ip_address} hasn't replied back")
        app.logger.debug(f"checking_random_node: sending all neighbors that the following p2p node has failed: {random_ip_address}")
        delete_neighbor_from_all_topics(random_ip_address)
        # tell leader node
        (leader_ip_address,p2p_id) = get_leader()
        url = f"http://{leader_ip_address}:5000/failed-node"
        response = attempt_request(lambda: requests.post(url,json={"message":f"{random_ip_address}"}))
    else:
        app.logger.debug(f"checking_random_node: Node {random_ip_address} responded")

# if node failed, send failure node post to everyone
@app.route('/failed-node', methods=['POST'])
def failed_node():
    topic = "delete_node"
    text = request.json.get('message')
    delete_neighbor_from_all_topics(text)
    return jsonify({"message": str(send_post(topic,text))})

# start leader election: bully algorithm
@app.route('/start-election', methods=['POST'])
def start_election():
    app.logger.debug("backed or other p2p node called an election")
    thread = threading.Thread(target=election)
    thread.start()
    return jsonify({'message': "election started" })

# actual election: bully algorithm
def election():
    app.logger.debug("leader election: starting leader election in this node")
    rw_locks["election"].acquire_writelock()
    # STEP 1: see if current p2p_id is bigger than p2p_id of p2p neighbors
    # get p2p_id of current p2p node
    p2p_id = int(global_var["p2p_id"])

    # get p2p_ids of all other topic neighbors
    p2p_hash = get_p2pids_of_all_neighbors()

    # whether the p2p ids of neighbors are bigger than p2p of current p2p node
    neighbors_are_bigger = False

    # bigger_neighbors[ip_address] = p2p_id
    bigger_neighbors_hash = dict()

    # check if any of the p2p ids of the neighbors are bigger than the p2p id of this current node
    for ip_address, other_p2p_id in p2p_hash.items():
        other_p2p_id = int(other_p2p_id)

        if other_p2p_id > p2p_id:
            neighbors_are_bigger = True
            bigger_neighbors_hash[ip_address] = other_p2p_id

    # STEP 2: If the p2p ids of the p2p neighbors are bigger, send start election to them
    # call others
    if neighbors_are_bigger:
        app.logger.debug('leader election: the p2p ids of neighbors are bigger')
        bigger_neighbors_list = list(bigger_neighbors_hash.items())
        # sort by p2p id
        bigger_neighbors_list.sort(key= lambda value:value[1])
        # reverse order
        bigger_neighbors_list.reverse()
        for ip_address,p2p_id in bigger_neighbors_list:
            app.logger.debug(f"leader election: leader election request will be sent to {ip_address}")
            # send start election command to that ip address
            url = f"http://{ip_address}:5000/start-election"
            response = attempt_request(lambda: requests.post(url))

            if response is not None:
                app.logger.debug(f"leader election: {ip_address} will perform election")
                rw_locks["election"].release_writelock()
                return
            else:
                app.logger.debug(f"leader election: {ip_address} did not responsed")
        app.logger.debug("leader election: Since none of the neighbors responded,")

    # STEP 3: If the other p2p nodes are not candidates or did not respond
    # curent p2p node will elect itself
    # elect itself
    app.logger.debug("leader election: current p2p node will elect itself")
    leader_ip_address = global_var["ip_address"]
    leader_p2p_id =global_var["p2p_id"]
    leader_setup()
    set_leader(leader_ip_address,leader_p2p_id)
    args = {
        "ip_address": global_var["ip_address"],
        "p2p_id": global_var["p2p_id"]
    }
    url = f"http://backend-service:5000/update-leader"
    response = attempt_request(lambda: requests.post(url,json=args))
    if response is None:
        #No response from backend server, assuming server failure
        #update all p2p nodes about server failer
        app.logger.debug("Backend server hasn't replied back")
        send_post("system","Backend failed")

    # send coordinator messages to neighbors
    thread = threading.Thread(target=send_coordinator_message,args=(leader_ip_address,leader_p2p_id,"",))
    thread.start()
    rw_locks["election"].release_writelock()

# send coordinator message to p2p node neighbors
def send_coordinator_message(leader_ip_address,leader_p2p_id,sender_ip_address):
    # get all neighbors
    ip_addresses = get_topic_neighbors_from_all_topics()
    app.logger.debug("coordinator message: current p2p node will send coordinator message to neighbors")
    # iterate through each ip address
    for ip_address in ip_addresses:
        # do not send coordinator message to sender
        if sender_ip_address == ip_address:
            continue
        app.logger.debug(f'coordinator message: coordinator message send to {ip_addresses}')
        args = {
            "ip_address": leader_ip_address,
            "p2p_id": leader_p2p_id,
            "sender" : global_var["ip_address"],
        }
        url = f"http://{ip_address}:5000/relay-coordinator-message"
        response = attempt_request(lambda: requests.post(url,json=args))

        if response is None:
            app.logger.debug(f"{ip_address} did not receive coordinator message")
    app.logger.debug("finished sending coordinator messages")

# http endponit: to relay coordinator messages
@app.route('/relay-coordinator-message',methods=['POST'])
def relay_coordinator_message():
    app.logger.debug("relay coordinator message: p2p node received relay-coordinator-message")
    # get json info from http request
    leader_ip_address = request.json.get('ip_address')
    leader_p2p_id = request.json.get('p2p_id')
    sender_ip_address = request.json.get('sender')
    (current_leader_ip_address,p2p_id) = get_leader()
    # if leader is same, ignore
    if current_leader_ip_address == leader_ip_address:
        message = f'relay coordinator message: {current_leader_ip_address} was already elected. ignore message'
        app.logger.debug(message)
        return jsonify({"message":message})
    # if leader not the same, update leader and send message to coordinator
    else:
        message = f'relay coordinator message: {current_leader_ip_address} is new leader. coordinator message will be sent'
        set_leader(leader_ip_address,leader_p2p_id)
        thread = threading.Thread(target=send_coordinator_message,args=(leader_ip_address,leader_p2p_id,sender_ip_address))
        thread.start()
        return jsonify({"message":message})

# http endpoint: closest member is calculated based on distance of geo co ordinates and they are made neighbours to reduce number of hops
@app.route('/get-closest-topic-neighbor', methods=['GET'])
def get_closest_topic_member():
    # get json infom from http request
    new_subscriber_lat = int(request.json.get('new_subscriber_lat'))
    new_subscriber_long = int(request.json.get('new_subscriber_long'))
    topic = request.json.get('topic')
    # get all neighbors of topic
    neighbor_ip_list = get_topic_neighbors(topic)
    # temp values for closest subscriber
    closest_ip_address = ""
    closest_distance = math.inf
    app.logger.debug("getting geo location for all neighbours using get-geo-location")
    # call all neighbors of topic
    for neighbor_ip in neighbor_ip_list:
        # get geo location of neighbor
        response = attempt_request(lambda: requests.get(f'http://{neighbor_ip}:5000/get-geo-location'))
        if response == None:
            return
        received_lat = int(response.json().get("geo_lat"))
        received_long = int(response.json().get("geo_long"))
        # calculate distance
        distance = (received_lat - new_subscriber_lat)**2 + (received_long - new_subscriber_long)**2
        # if closer, then update distance
        if distance < closest_distance:
            closest_ip_address = neighbor_ip
            closest_distance = distance
    
    # check if current node is closer
    distance = (global_var["geo_lat"] - new_subscriber_lat)**2 + (global_var["geo_lat"] - new_subscriber_long)**2
    app.logger.debug("calculated distance and checking for closest node")
    # if current p2p node is closer, send p2p node
    if distance < closest_distance:
        # current node was closer, stop searching
        closest_ip_address = global_var["ip_address"]
        app.logger.debug("returning the closest node")
        return jsonify({"message":"stop search",
                        "ip_address": closest_ip_address,
                        "p2p_id": global_var["p2p_id"]})
    # if p2p node is not closer
    else:
        # neighbor was closer, continue searching
        app.logger.debug("returning continue search")
        return jsonify({"message":"continue search",
                        "ip_address": closest_ip_address})

# Returns whether P2P node is leader
@app.route('/is-leader', methods=['GET'])
def is_leader():
    # retreive leader info stored
    leader_info = get_leader()
    # if no leader, return False
    if leader_info == None:
        return jsonify({"message": "No leader elected yet","value": "False"})
    # retrieve leader info
    (current_leader_ip_address,p2p_id) =  leader_info

    # if p2p node is leader return True
    if current_leader_ip_address == global_var["ip_address"]:
        return jsonify({"message": "P2P node is leader","value": "True"})
    # if not, return False
    else:
        return jsonify({"message": "P2P node is not leader","value": "False"})

# subscribing the node to a topic
@app.route('/subscribe', methods=['POST'])
def http_join_topic():
    topic = str(request.json.get('topic'))
    # create separate thread to handle subscription
    thread = threading.Thread(target=join_topic, args=(topic,))
    thread.start()
    return jsonify({'message': "joining topic started" })

# http endpoint so that leader receives subscription for new node
@app.route('/leader-subscribe', methods=['POST'])
def leader_subscribe():
    topic = request.json.get('topic')
    new_ip_address = request.json.get('ip_address')

    args = {
        "ip_address": new_ip_address,
        "topic": topic,
    }
    
    app.logger.debug(f'leader_subscribe: this leader p2p node received subscription request for topic {topic} from this p2p node: {new_ip_address}')
    app.logger.debug(f'leader_subscribe: this leader p2p node will contact backend to set the p2p node {new_ip_address} as topic member for {topic}')
    # leader subscribe
    response = attempt_request(lambda: requests.post("http://backend-service:5000/p2p-node-subscribe",json=args))
    if response == None:
        app.logger.error(f'leader_subscribe: the p2p node {new_ip_address} was not able to become topic member for {topic}')
        return jsonify({"message": "server error"}), 500
    else:
        app.logger.error(f'leader_subscribe: the p2p node {new_ip_address} is now topic member for {topic}')
        app.logger.error(f'leader_subscribe: messaging {new_ip_address} now with closest topic member')
        return jsonify({"ip_address": response.json().get("ip_address"),"message": response.json().get("message")})

# join topic
def join_topic(topic):
    # contact leader node with endpoint to subscribe to a topic
    app.logger.debug('join_topic: p2p node will join the following topic: {topic}')
    args = {
        "topic": topic,
        "ip_address": global_var["ip_address"]
    }
    app.logger.debug('join_topic: p2p node will communicate to leader p2p node to join: {topic}')

    leader_info = get_leader()
    if leader_info == None:
        app.logger.debug("join_topic: there is no leader")
        return
    (current_leader_ip_address,p2p_id) = leader_info

    response = attempt_request(lambda: requests.post(f"http://{current_leader_ip_address}:5000/leader-subscribe",json=args))

    if response == None:
        app.logger.debug("join_topic: no response from backend")
        return
    
    message_received = response.json().get("message")

    if message_received == "no other node":
        app.logger.debug("join_topic: there weren't other topic members to connect with")
        return

    # succesfully received a random p2pnode of a topic from backend
    app.logger.debug(f'join_topic: p2pid and ip_address of random node in topic {topic} are retrieved')
    closest_ip_address = response.json().get("ip_address")
    closest_p2p_id = None
    # for all nodes in the topic calculate the closest ip address to make them neighbors
    while True:
        app.logger.debug("join_topic: calling closest topic neighbour")
        args = {
            "new_subscriber_lat": str(global_var["geo_lat"]),
            "new_subscriber_long": str(global_var["geo_long"])
        }
        # get the closest neighbor
        app.logger.debug(f'join_topic: contacting p2p with the following ip_address for closest neighbor: {closest_ip_address}')
        response = attempt_request(lambda: requests.get(f'http://{closest_ip_address}:5000/get-closest-topic-neighbor',json=args))
        if response == None:
            app.logger.debug("no response from closest subscriber")
            break
        message = response.json().get("message")
        # if there's another close neighbor keep searching
        if message == "continue search":
            old_ip_address = closest_ip_address
            # update ip_address
            closest_ip_address = response.json().get("ip_address")
            app.logger.debug(f'join_topic: p2p node {old_ip_address} recommends contacting this p2p node {closest_ip_address}')
            
        # if p2p node contacted was the closest neighbor, set both of them as neighbor
        else:
            # update closest_ip_address
            closest_ip_address = response.json().get("ip_address")
            closest_p2p_id = response.json().get("p2p_id")
            app.logger.debug(f'join_topic: closest ip address retrieved {closest_ip_address}')
            break
    
    # make both joining p2p node and closest subscriber neighbors
    app.logger.debug(f'join_topic: both of the following ip addresses will be neighbors for topic {topic}: {global_var["ip_address"]} and {closest_ip_address}')

    # makes closest p2p node neighbor of current node
    create_topic_neighbor(closest_ip_address,topic,closest_p2p_id)
    # makes current node neighbor of closest p2p node

    args = {
        "ip_address": global_var["ip_address"],
        "p2p_id": global_var["p2p_id"],
        "topic" : topic,
    }
    url = f'http://{closest_ip_address}:5000/create-topic-neighbor'
    response = attempt_request(lambda: requests.post(url,json=args))

# set random value for geo_lat and geo_long
def set_geo_location():
    # value b/w 0 to 100
    global_var["geo_lat"] = random.randint(0,100)
    global_var["geo_long"] = random.randint(0,100)
    app.logger.debug(f'geo: {global_var["geo_lat"]}, {global_var["geo_long"]}')

# http endpoint: get geo location of p2p node
@app.route('/get-geo-location',methods=['GET'])
def send_geo_location():
    geo_lat = global_var["geo_lat"]
    geo_long = global_var["geo_long"]
    return jsonify({"geo_lat":str(geo_lat),"geo_long":str(geo_long)})

# terminates the flask app to simulate node failure
@app.route('/terminate', methods=['POST'])
def http_terminate():
    os.kill(os.getpid(), signal.SIGINT)
    return jsonify({'message': "terminating" })

def leader_setup():
    scheduler.add_job(id='checking_backend', func=checking_backend, trigger='interval', seconds=10)

if __name__ == "__main__":
    # join network and get topics
    join_network()
    get_leader_backend()
    get_topics()
    set_geo_location()

    # if no topics retrieved, exit
    if global_var["topics"] == None:
        sys.exit()

    scheduler.init_app(app)
    scheduler.start()

    # add job
    # jobs can be added and removed add any time
    # even in functions and route functions
    # scheduler.add_job(id='print_job', func=print_job, trigger='interval', seconds=10)
    # scheduler.add_job(id='checking_random_node', func=checking_random_node, trigger='interval', seconds=10)

    # run flask app
    app.run(host="0.0.0.0", port=5000)