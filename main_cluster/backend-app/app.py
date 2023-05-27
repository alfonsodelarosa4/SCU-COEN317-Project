from flask import Flask, request, jsonify, session, request, g
from flask_apscheduler import APScheduler
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests, hashlib, logging,time
from collections import defaultdict
import requests, socket, logging, time, sys, threading,os

app = Flask(__name__)

# scheduler
scheduler = APScheduler()

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

# SQL database
mongo_client = MongoClient('mongodb://localhost:27017')
db = mongo_client.my_database

users_db = db['users']

p2pnodes_db = db['p2p_nodes']
topics_db = db['topics']
leaders_db = db['leaders']
topic_members_db = db['topic_members_db']

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

class P2PNode:
    def __init__(self,ip_address,p2p_id):
        self.ip_address = ip_address
        self.p2p_id = p2p_id

class Topic:
    def __init__(self,name):
        self.name = name

class Leader:
    def __init__(self,ip_address):
        self.ip_address = ip_address

class TopicMember:
    def __init__(self,topic,ip_address):
        self.ip_address = ip_address
        self.topic = topic

# P2PNodes
# create p2pnode
def create_p2pnode(ip_address,p2p_id):
    rw_locks["p2pnode"].acquire_writelock()
    try:
        new_p2pnode = P2PNode(ip_address,p2p_id)
        node_id = p2pnodes_db.insert_one(new_p2pnode.__dict__).inserted_id
        p2pnode = p2pnodes_db.find_one({'_id': ObjectId(node_id)})
        p2pnode["_id"] = str(p2pnode["_id"])
        return p2pnode
    except:
        app.logger.error("create_p2pnode")
        return None
    finally:
        rw_locks["p2pnode"].release_writelock()

# get p2pnode
def get_p2pnode(ip_address):
    rw_locks["p2pnode"].acquire_readlock()
    if ip_address == None or ip_address == "":
        rw_locks["p2pnode"].release_writelock()
        app.logger.error('user_id is missing')
        return
    p2pnode = p2pnodes_db.find_one({'ip_address': ip_address})

    if p2pnode:
        p2pnode["_id"] = str(p2pnode["_id"])
        rw_locks["p2pnode"].release_readlock()
        return p2pnode
    else:
        rw_locks["p2pnode"].release_readlock()
        app.logger.error('p2pnode not found')

# get p2pnode
def get_firstp2pnode():
    rw_locks["p2pnode"].acquire_readlock()
    p2pnode = p2pnodes_db.find_one()
    if p2pnode:
        p2pnode["_id"] = str(p2pnode["_id"])
        rw_locks["p2pnode"].release_readlock()
        return p2pnode
    else:
        rw_locks["p2pnode"].release_readlock()
        app.logger.error('p2pnode not found')

# delete p2pnode
def delete_p2pnode(ip_address):
    rw_locks["p2pnode"].acquire_writelock()
    result = p2pnodes_db.delete_one({'ip_address': ip_address})
    if result.deleted_count != 1:
        app.logger.error('User not found')
    rw_locks["p2pnode"].release_writelock()

# TOPIC
def create_topic(name):
    rw_locks["topic"].acquire_writelock()
    topic = topics_db.find_one({'name':name})
    if topic is not None:
        rw_locks["topic"].release_writelock()
        app.logger.debug("topic already exists")
        return False
    new_topic = Topic(name=name)
    topic_id = topics_db.insert_one(new_topic.__dict__).inserted_id
    rw_locks["topic"].release_writelock()

# get subscribed topics
def get_topics():
    rw_locks["topic"].acquire_readlock()
    topics = topics_db.find()
    rw_locks["topic"].release_readlock()   
    return [topic["name"] for topic in topics]

# get specific subscribed topic
def get_topic(name):
    rw_locks["topic"].acquire_readlock()
    topic = topics_db.find_one({'name':name})
    rw_locks["topic"].release_readlock()   
    return topic

def delete_topic(name):
    rw_locks["topic"].acquire_writelock()
    result = topics_db.delete_one({'name': name})
    if result.deleted_count != 1:
        app.logger.debug("topic not found")
    rw_locks["topic"].release_writelock()


# LEADER
# set the leader
def set_leader(ip_address):
    rw_locks["leader"].acquire_writelock()
    for leader in leaders_db.find():
        leader__id = str(leader['_id'])
        result = leaders_db.delete_one({'_id': ObjectId(leader__id)})
        if result.deleted_count != 1:
            app.logger.error('Leader not found')
        
    new_leader = Leader(ip_address=ip_address)
    leaders_db.insert_one(new_leader.__dict__).inserted_id
    rw_locks["leader"].release_writelock()

# get the leader
# return ip address of the leader
def get_leader():
    rw_locks["leader"].acquire_readlock()
    leader = leaders_db.find_one()
    rw_locks["leader"].release_readlock()

    if leader is not None:
        app.logger.debug("leader found")
        return leader
    else:
        app.logger.debug("leader not found")
        return None

# TopicMember
# create topic member
def create_topic_member(ip_address,topic):
    rw_locks["topic-member"].acquire_writelock()
    new_topic = TopicMember(ip_address=ip_address,topic=topic)
    topic_id = topic_members_db.insert_one(new_topic.__dict__).inserted_id
    rw_locks["topic-member"].release_writelock()
    return str(topic_id)

# get topic members
# return list of ip addresses
def get_topic_members(topic):
    rw_locks["topic-member"].acquire_readlock()
    members = topic_members_db.find({'topic':topic})
    rw_locks["topic-member"].release_readlock()
    return [member["ip_address"] for member in members]

# gets ip addresses of each topic member
# return list of ip addresses
def get_topic_members_from_all_topics():
    rw_locks["topic-member"].acquire_readlock()
    members = topic_members_db.find()
    rw_locks["topic-member"].release_readlock()
    return list(set([member["ip_address"] for member in members]))

# delete a member from all topics
def delete_member_from_all_topics(ip_address):
    rw_locks["topic-member"].acquire_writelock()
    result = topic_members_db.delete_many({'ip_address':ip_address})
    rw_locks["topic-member"].release_writelock()

# delete all members of from a topics
def delete_all_members_from_a_topic(topic):
    rw_locks["topic-member"].acquire_writelock()
    results = topic_members_db.delete_many({'topic':topic})
    rw_locks["topic-member"].release_writelock()

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
# NEEDS TO CHANGE
@app.route('/get-topics', methods=['GET'])
def send_topics():
    app.logger.debug("sent topics")
    return jsonify({'topics': ["food", "tech", "finance"]})

# join network
# NEEDS TO CHANGE
@app.route('/join-network', methods=['POST'])
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

# start election
@app.route('/start-election', methods=['POST'])
def start_election():
    # get random ip address from list of p2p nodes
    p2p_node = get_firstp2pnode()
    ip_address = p2p_node["ip_address"]

    # send start election command to that ip address
    url = f"http://{ip_address}:5000/start-election"

    # get response
    response = attempt_request(lambda: requests.post(url))
    if response == None:
        app.logger.debug("start election not sent")
        return jsonify({'message': "start election not sent" })
    else:
        return jsonify({'message': f"start election sent to {ip_address}" })

if __name__ == "__main__":
    scheduler.init_app(app)
    scheduler.start()

    # run flask app
    app.run(host="0.0.0.0", port=5000)
