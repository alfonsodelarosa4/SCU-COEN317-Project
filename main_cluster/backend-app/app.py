from flask import Flask, request, jsonify, session, request, g
from flask_apscheduler import APScheduler
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests, hashlib, logging,time
from collections import defaultdict
import requests, socket, logging, time, sys, threading,os
import signal

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

# MongoDB Database
mongo_client = MongoClient('mongodb://localhost:27017')
db = mongo_client.my_database
p2pnodes_db = db['p2p_nodes']
topics_db = db['topics']
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

class TopicMember:
    def __init__(self,topic,ip_address):
        self.ip_address = ip_address
        self.topic = topic

# P2PNodes
# create p2pnode
def create_p2pnode(ip_address,p2p_id):
    # concurrency: read-write lock
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
    # concurrency: read-write lock
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
    # concurrency: read-write lock
    rw_locks["p2pnode"].acquire_readlock()
    p2pnode = p2pnodes_db.find_one()
    if p2pnode:
        p2pnode["_id"] = str(p2pnode["_id"])
        rw_locks["p2pnode"].release_readlock()
        return p2pnode
    else:
        rw_locks["p2pnode"].release_readlock()
        app.logger.error('p2pnode not found')

def get_p2pnode_avoid_ip(ip_address):
    rw_locks["p2pnode"].acquire_readlock()
    p2pnode = p2pnodes_db.find_one({"ip_address": {"$ne": ip_address}})
    rw_locks["p2pnode"].release_readlock()
    return p2pnode

# delete p2pnode
def delete_p2pnode(ip_address):
    # concurrency: read-write lock
    rw_locks["p2pnode"].acquire_writelock()
    result = p2pnodes_db.delete_one({'ip_address': ip_address})
    if result.deleted_count != 1:
        app.logger.error('User not found')
    rw_locks["p2pnode"].release_writelock()

@app.route('/create-topic-db', methods=['POST'])
def http_create_topic_db():
    name = str(request.json.get('name'))
    create_topic(name)
    if name == "" or name == None:
        return ({"error":"invalid name"})
    else:
        return jsonify({"message": f'created {name}'})

# TOPIC
def create_topic(name):
    # concurrency: read-write lock
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
    # concurrency: read-write lock
    rw_locks["topic"].acquire_readlock()
    topics = topics_db.find()
    rw_locks["topic"].release_readlock()   
    return [topic["name"] for topic in topics]

# get specific subscribed topic
def get_topic(name):
    # concurrency: read-write lock
    rw_locks["topic"].acquire_readlock()
    topic = topics_db.find_one({'name':name})
    rw_locks["topic"].release_readlock()   
    return topic

def delete_topic(name):
    # concurrency: read-write lock
    rw_locks["topic"].acquire_writelock()
    result = topics_db.delete_one({'name': name})
    if result.deleted_count != 1:
        app.logger.debug("topic not found")
    rw_locks["topic"].release_writelock()

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

# TopicMember
# http create topic member
@app.route('/create-topic-member-db', methods=['POST'])
def http_create_topic_member_db():
    ip_address = str(request.json.get('ip_address'))
    topic = str(request.json.get('topic'))
    return jsonify({"message": str(create_topic_member(ip_address,topic))})

# create topic member
def create_topic_member(ip_address,topic):
    # concurrency: read-write lock
    rw_locks["topic-member"].acquire_writelock()
    new_topic = TopicMember(ip_address=ip_address,topic=topic)
    topic_id = topic_members_db.insert_one(new_topic.__dict__).inserted_id
    rw_locks["topic-member"].release_writelock()
    return str(topic_id)

@app.route('/get-all-topic-members-db', methods=['GET'])
def http_get_all_topic_members_db():
    # concurrency: read-write lock
    return jsonify({"message": str(get_topic_members_from_all_topics())})

# get topic members
# return list of ip addresses
def get_topic_members(topic):
    # concurrency: read-write lock
    rw_locks["topic-member"].acquire_readlock()
    members = topic_members_db.find({'topic':topic})
    rw_locks["topic-member"].release_readlock()
    return [member["ip_address"] for member in members]

def get_firsttopicmember(topic,ip_address):
    # concurrency: read-write lock
    rw_locks["p2pnode"].acquire_readlock()
    p2pnode = topic_members_db.find_one({'topic':topic,"ip_address": {"$ne": ip_address}})
    rw_locks["p2pnode"].release_readlock()
    if p2pnode:        
        return p2pnode
    else:
        app.logger.error('p2pnode not found')
        return None
    
# gets ip addresses of each topic member
# return list of ip addresses
def get_topic_members_from_all_topics():
    # concurrency: read-write lock
    rw_locks["topic-member"].acquire_readlock()
    members = topic_members_db.find()
    rw_locks["topic-member"].release_readlock()
    return list(set([member["ip_address"] for member in members]))

# delete a member from all topics
def delete_member_from_all_topics(ip_address):
    # concurrency: read-write lock
    rw_locks["topic-member"].acquire_writelock()
    result = topic_members_db.delete_many({'ip_address':ip_address})
    rw_locks["topic-member"].release_writelock()

# delete all members of from a topics
def delete_all_members_from_a_topic(topic):
    # concurrency: read-write lock
    rw_locks["topic-member"].acquire_writelock()
    results = topic_members_db.delete_many({'topic':topic})
    rw_locks["topic-member"].release_writelock()

def delete_topic_member(ip_address,topic):	
    rw_locks["topic-member"].acquire_writelock()	
    result = topic_members_db.delete_many({'ip_address':ip_address,'topic':topic})	
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

# get topics, return topics
@app.route('/get-topics', methods=['GET'])
def send_topics():
    app.logger.debug("sent topics: " + str(get_topics()))
    return jsonify({'topics': str(get_topics())})

# get leader from backend, return leader leader
@app.route('/get-leader-backend', methods=['GET'])
def send_leader_backend():
    # get leader
    leader_info = get_leader()
    # if no leader, send "no leader"
    if leader_info == None:
        app.logger.debug("get-leader-backend: no leader in backend")
        return jsonify({'message': "no leader"})
    # if leader, send leader info
    else:
        app.logger.debug("get-leader-backend: leader is present")
        (ip_address,p2p_id) = leader_info
        app.logger.debug(f'leader information: {str(leader_info)}')
        return jsonify({'message': 'Found',
                        'ip_address':ip_address,
                        'p2p_id':p2p_id})

# set first leader in backend
@app.route('/set-first-leader', methods=['POST'])
def set_first_leader_backend():
    # concurrency: read-write lock
    rw_locks["leader"].acquire_writelock()
    ip_address = str(request.json.get('ip_address'))
    p2p_id = str(request.json.get('p2p_id'))
    # if no leader
    if global_var["leader"] == None:
        # change leader to received ip address p2p id
        app.logger.debug(f'set-first-leader: The following P2P node made it first and will be the leader: {ip_address}')
        global_var["leader"] = (ip_address,p2p_id)
        rw_locks["leader"].release_writelock()
        return jsonify({'message': 'you are leader'})
    # if leader exists
    else:
        # receive and send leader info
        app.logger.debug(f'set-first-leader: The following P2P node failed to be the first leader: {ip_address}')
        (ip_address,p2p_id) = global_var["leader"]
        rw_locks["leader"].release_writelock()
        return jsonify({'message': 'Found',
                        'ip_address':ip_address,
                        'p2p_id':p2p_id})

# join network
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
    inserted_id = create_p2pnode(ip_address,p2p_id)
    # send new p2p id
    if inserted_id is not None:
        app.logger.debug("new node is succesfully inserted in database")
        return jsonify({'p2p_id': p2p_id })
    else:
        app.logger.debug("new node not inserted in db")
        return jsonify({'message': "error: node not inserted"})
   
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

# ping-ack protocol: receive failure ping, send ack
@app.route('/failure-ping', methods=['POST'])
def failure_ping():
    ip_address = str(request.json.get('ip_address'))
    return jsonify({"message": f"Message received from leader node {ip_address} and Acknowledged"})

# get p2pnode
@app.route('/p2p-node-subscribe', methods=['POST'])
def http_get_firsttopicmember():
    topic = request.json.get('topic')
    ip_address = request.json.get('ip_address')
    create_topic(topic)
    app.logger.debug(f'p2p_node_subscribe: setting p2p node {ip_address} as topic member for {topic}')
    create_topic_member(ip_address,topic)
    app.logger.debug(f'p2p_node_subscribe: returning closest topic member to p2p node {ip_address}')
    node = get_firsttopicmember(topic,ip_address)
    if node:
        return jsonify({"message":"another node","ip_address": node["ip_address"]})
    else:
        return jsonify({"message":"no other node", "ip_address": "none"})

@app.route("/update-leader",methods=['POST'])
def update_leader():
    p2p_id = request.json.get('p2p_id')
    ip_address = request.json.get('ip_address')
    global_var["bad leader"] = False
    set_leader(ip_address,p2p_id)
    return jsonify({"message": f'update_leader: the following p2p node is the new leader: {ip_address}'})

# ping-ack protocol: send leader ack
def checking_leader():
    app.logger.debug("checking_leader: checking leader for failure")
    leader_info = get_leader()
    # leader info retrieved
    if leader_info == None:
        app.logger.debug("checking_leader: no leader. exiting leader monitor")
        return
    if global_var["bad leader"] == True:
        app.logger.debug("checking_leader: bad leader. exiting leader monitor")
        return
    # get current learder's ip_address
    (leader_ip_address,p2p_id) = leader_info
    app.logger.debug(f'checking_leader: leader ip address: {leader_ip_address}')
    args = {
        "message": "checking on leader node"
    }
    # send ping ack to leader
    url = f"http://{leader_ip_address}:5000/failure-ping"
    response = attempt_one_request(lambda: requests.post(url,json=args, timeout=5))
    
    # if no response, assume leader failed
    if response is None:
        #No response from leader node, assuming node failure
        #update all p2p nodes about leader failer
        app.logger.debug("checking_leader: Leader node hasn't replied back")
        global_var["bad leader"] = True
        p2pnode = get_p2pnode_avoid_ip(leader_ip_address)
        ip_address = p2pnode['ip_address']
        url = f"http://{ip_address}:5000/start-election"
        app.logger.debug(f'checking_leader: starting election to {ip_address}')
        response = attempt_request(lambda: requests.post(url))
    else:
        app.logger.debug("Leader node responded")

@app.route('/unsubscribe-node', methods=['POST'])	
def unsubscribe_node():	
    topic = request.json.get('topic')	
    ip_address = request.json.get('ip_address')	
    delete_topic_member(ip_address,topic)	
    return jsonify({'message': f'node with ip address({ip_address}) unsubscribed from topic({topic})'})	

# terminates the flask app to simulate backend failure
@app.route('/terminate', methods=['POST'])
def http_terminate():
    os.kill(os.getpid(), signal.SIGINT)
    return jsonify({'message': "terminating" })

if __name__ == "__main__":
    scheduler.init_app(app)
    scheduler.start()

    scheduler.add_job(id='checking_leader', func=checking_leader, trigger='interval', seconds=10)
    # run flask app
    app.run(host="0.0.0.0", port=5000)
