from flask import Flask, request, jsonify, session, g
from flask_apscheduler import APScheduler
from pymongo import MongoClient
from bson.objectid import ObjectId
from collections import defaultdict
import requests, socket, logging, time, sys, threading,os

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

# SQL database
mongo_client = MongoClient('mongodb://localhost:27017')
db = mongo_client.my_database

users_db = db['users']

leaders_db = db['leaders']
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

class User:
    def __init__(self,name,email):
        self.name = name
        self.email = email

class Leader:
    def __init__(self,ip_address):
        self.ip_address = ip_address

class SubscribedTopic:
    def __init__(self,name):
        self.name = name

class TopicNeighbor:
    def __init__(self,ip_address,topic):
        self.ip_address = ip_address
        self.topic = topic

class Post:
    def __init__(self, topic,ip_address,text,timestamp):
        self.topic = topic
        self.ip_address = ip_address
        self.text = text
        self.timestamp = timestamp

# USER
# create user
# returns mongodb_id of user
'''
@app.route('/create_user', methods=['POST'])
def http_create_user():
    name = request.json.get('name')
    email = request.json.get('email')
    user = create_user(name, email)
    app.logger.debug(user)
'''

# create user
def create_user(name,email):
    new_user = User(name, email)
    user_id = users_db.insert_one(new_user.__dict__).inserted_id
    user = users_db.find_one({'_id': ObjectId(user_id)})
    user["_id"] = str(user["_id"])
    return user_id

# get users
# returns list of users
def get_users():
    users = []
    for user in users_db.find():
        user['_id'] = str(user['_id'])
        users.append(user)
    return users

# get user
def get_user(user_id):
    if user_id == None or user_id == "":
        raise ValueError('user_id is missing')

    user = users_db.find_one({'_id': ObjectId(user_id)})

    if user:
        user["_id"] = str(user["_id"])
        return user
    else:
        raise ValueError('User not found')

# update user
def update_user(user_id,name,email):
    if user_id == None or user_id == "":
        raise ValueError('user_id is missing')
    if name == None or name == "":
        raise ValueError('name is missing')
    if email == None or email == "":
        raise ValueError('email is missing')
    
    result = users_db.update_one(
        {'_id': ObjectId(user_id)}, 
        {'$set': {'name': name, 'email': email}}
    )
    if result.modified_count != 1:
        raise ValueError('User not found')

# delete user
def delete_user(user_id):
    result = users_db.delete_one({'_id': ObjectId(user_id)})
    if result.deleted_count != 1:
        raise ValueError('User not found')

# LEADER
# set the leader
def set_leader(ip_address):
    rw_locks["leader"].acquire_writelock()
    for leader in leaders_db.find():
        leader__id = str(leader['_id'])
        result = leaders_db.delete_one({'_id': ObjectId(leader__id)})
        if result.deleted_count != 1:
            raise ValueError('Leader not found')
        
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
        return leader["ip_address"]
    else:
        app.logger.debug("leader not found")
        return None

# SubscribedTopic
# create topic
def create_subscribed_topic(name):
    rw_locks["topic"].acquire_writelock()
    topic = subscribed_topics_db.find_one({'name':name})
    if topic is not None:
        rw_locks["topic"].release_writelock()
        app.logger.debug("topic already exists")
        return False
    new_topic = SubscribedTopic(name=name)
    topic_id = subscribed_topics_db.insert_one(new_topic.__dict__).inserted_id
    rw_locks["topic"].release_writelock()

# get subscribed topics
def get_subscribed_topics():
    rw_locks["topic"].acquire_readlock()
    topics = subscribed_topics_db.find()
    rw_locks["topic"].release_readlock()   
    return [topic["name"] for topic in topics]

# get specific subscribed topic
def get_subscribed_topic(name):
    rw_locks["topic"].acquire_readlock()
    topic = subscribed_topics_db.find_one({'name':name})
    rw_locks["topic"].release_readlock()   
    return topic

# delete subscribed topic
# returns whether deleted
def delete_subscribed_topic(name):
    rw_locks["topic"].acquire_writelock()
    result = subscribed_topics_db.delete_one({'name': name})
    if result.deleted_count != 1:
        app.logger.debug("topic not found")
    rw_locks["topic"].release_writelock()

# TopicNeighbor
# create topic neighbor
def create_topic_neighbor(ip_address,topic):
    rw_locks["topic-neighbor"].acquire_writelock()
    new_neighbor = TopicNeighbor(ip_address=ip_address,topic=topic)
    topic_id = topic_neighbors_db.insert_one(new_neighbor.__dict__).inserted_id
    rw_locks["topic-neighbor"].release_writelock()
    return str(topic_id)

# get topic neighbors
# return list of ip addresses
def get_topic_neighbors(topic):
    rw_locks["topic-neighbor"].acquire_readlock()
    neighbors = topic_neighbors_db.find({'topic':topic})
    rw_locks["topic-neighbor"].release_readlock()
    return [neighbor["ip_address"] for neighbor in neighbors]

# gets ip addresses of each topic neighbor
# return list of ip addresses
def get_topic_neighbors_from_all_topics():
    rw_locks["topic-neighbor"].acquire_readlock()
    neighbors = topic_neighbors_db.find()
    rw_locks["topic-neighbor"].release_readlock()
    return list(set([neighbor["ip_address"] for neighbor in neighbors]))

# delete a neighbor from all topics
def delete_neighbor_from_all_topics(ip_address):
    rw_locks["topic-neighbor"].acquire_writelock()
    result = topic_neighbors_db.delete_many({'ip_address':ip_address})
    rw_locks["topic-neighbor"].release_writelock()

# delete all neighbors of from a topics
def delete_all_neighbors_from_a_topic(topic):
    rw_locks["topic-neighbor"].acquire_writelock()
    results = topic_neighbors_db.delete_many({'topic':topic})
    rw_locks["topic-neighbor"].release_writelock()

# Post
# create post
def create_post(topic,ip_address,text,timestamp):
    rw_locks["post"].acquire_writelock()
    new_post = Post(topic=topic,ip_address=ip_address,text=text,timestamp=timestamp)
    post_id = posts_db.insert_one(new_post.__dict__).inserted_id
    rw_locks["post"].release_writelock()

# get posts by topic
def get_posts_by_topic(topic):
    rw_locks["post"].acquire_readlock()
    posts = posts_db.find({'topic':topic})
    rw_locks["post"].release_readlock()
    return [post for post in posts]

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

    scheduler.init_app(app)
    scheduler.start()

    # add job
    # jobs can be added and removed add any time
    # even in functions and route functions
    # scheduler.add_job(id='print_job', func=print_job, trigger='interval', seconds=10)


    # run flask app
    app.run(host="0.0.0.0", port=5000)