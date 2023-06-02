import re,subprocess

from port_forward_helper import generate_port_forwarding_commands, get_output_of_command

# get "kubectl get pods" output
kubectl_output = get_output_of_command("kubectl get pods")
# get list of port forwarding commands for each pod name
commands = generate_port_forwarding_commands(kubectl_output)
# iterate through each pod and output command and url
for port_forward_command, log_command, url, _ in commands:
    print(port_forward_command)
    print(log_command)
    print(url)
    print()
