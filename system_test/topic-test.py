import csv, subprocess, time, random, sys, os
from collections import defaultdict
from locust import HttpUser, task, between, events, TaskSet, SequentialTaskSet
from test_helper import  generate_pod_info, get_output_of_command

# retrieve portforwarding commands, base url, and pod names of the p2p-nodes
kubectl_output = get_output_of_command("kubectl get pods")
commands = generate_pod_info(kubectl_output)
pod_info = [(True if index == 0 else False,port_forward_command, url,pod_name) for index,(port_forward_command, url,pod_name) in enumerate(commands)]

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
    # portforward to communicate to kubernetes pod
    def start_port_forward(self):
        command = self.port_forward_command.split()
        self.port_forward_process = subprocess.Popen(command)
        # give it some time to establish the connection
        time.sleep(2)

    # TASKS
    @task
    def create_subscribed_topic(self):
        # publish a post
        self.client.post(self.base_url + '/create-subscribed-topic', json={"name": "food"})

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

