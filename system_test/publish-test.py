import csv, subprocess, time, random, sys, os, json
from collections import defaultdict
from locust import HttpUser, task, between, events, TaskSet, SequentialTaskSet
from test_helper import  generate_pod_info, get_output_of_command

# retrieve portforwarding commands, base url, and pod names of the p2p-nodes
kubectl_output = get_output_of_command("kubectl get pods")
commands = generate_pod_info(kubectl_output)
pod_info = [(True if index == 0 else False,port_forward_command, url,pod_name) for index,(port_forward_command, url,pod_name) in enumerate(commands)]

# sample messages
text_list = [
    "Italian pasta is better than American pizza. You have to try it. 🍝🍝",
    "You can't go to New York without trying deep dish pizza 🍕🗽",
    "I can't imagine life without sushi 🍣😤",
    "Have you tried buttercream chocolates? They're amazing! 🍫"
    "A well-made burger is a work of art 🍔🤩",
    "Ice cream is the ultimate dessert 🍦",
    "A good cup of coffee can make any day better ☕",
    "Mexican street tacos in San Diego are a must-try 🌮🌮",
    "Japanese ramen is a soul-soothing dish 🍜😌",
    "Fresh seafood by the beach is an unmatched experience 🍤🍢",
    "Gelato is smoother and creamier than regular ice cream 🍨",
]

# class of test user
class TestUser(HttpUser):
    wait_time = between(5, 15)
    
    # when user is created, it retrieves information of one pod
    # with this information, the user can communicate to the pod
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # called before any test is ran
    def on_start(self):
        my_pod_info = pod_info.pop()
        self.first_pod = my_pod_info[0]
        self.port_forward_command = my_pod_info[1]
        self.base_url = my_pod_info[2] 
        self.pod_name = my_pod_info[3]
        self.received_ip_address = False
        self.start_port_forward()
        self.setup()
    # portforward to communicate to kubernetes pod
    def start_port_forward(self):
        command = self.port_forward_command.split()
        self.port_forward_process = subprocess.Popen(command)
        # give it some time to establish the connection
        time.sleep(2)
    
    # get whether node is leader
    # if not leader, subscribe to topic
    def setup(self):
        # CHECK IF LEADER
        # send http get request to check if leader
        response = self.client.get(self.base_url + 'is-leader')
        # values from response
        response_data = json.loads(response.text)
        is_leader_str = response_data.get("value")
        # if leader:
        if is_leader_str == "True":
            self.is_leader = True
        # if not leader:
        else:
            self.is_leader = False

        # IF NOT LEADER, SUBSCRIBE
        if not self.is_leader:
            # SUBSCRIBE TO FOOD
            # send http subscribe request
            response = self.client.post(self.base_url + "subscribe", json={"name":"food"})

    # TASKS
    @task
    def publish(self):
        # IF NOT LEADER, SUBSCRIBE
        if not self.is_leader:
            # get random text
            text = random.choice(text_list)

            # send http post reqest publish a post
            self.client.post(self.base_url + 'send_post', json={"topic": "food", "text":text})

    # called after tests finish
    def on_stop(self):
        self.stop_port_forward()  
    def stop_port_forward(self):
        if self.port_forward_process:
            self.port_forward_process.terminate()
            self.port_forward_process = None

# Event listeners
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("A new test is starting")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("A test is ending")

