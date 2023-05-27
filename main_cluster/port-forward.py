import re,subprocess

# given pod names form kubectl get pods, create port-forwarding commands
def generate_port_forwarding_commands(pods_output):
    # split lines of output into list of strings
    # remove first line
    lines = pods_output.split("\n")[1:]
    # iterate through each line
    commands = []
    for i,line in enumerate(lines):
        # if empty, skip
        if line.strip() == "":
            continue
        # get first segment before first space
        pod_name = re.findall(r'^\S+', line)[0]
        port_number = i + 2000
        # get command and url
        port_forward_command = f"kubectl port-forward {pod_name} {port_number}:5000"
        log_command = f"kubectl logs -f {pod_name}"
        url = f"http://localhost:{port_number}/"
        # add command to list of commands
        commands.append((port_forward_command, log_command, url))
    return commands

# get the terminal output of a command
def get_output_of_command(command):
    result = subprocess.run(command, capture_output=True, text=True)
    return result.stdout.strip()

# get "kubectl get pods" output
kubectl_output = get_output_of_command("kubectl get pods")
# get list of port forwarding commands for each pod name
commands = generate_port_forwarding_commands(kubectl_output)
# iterate through each pod and output command and url
for port_forward_command, log_command, url in commands:
    print(port_forward_command)
    print(log_command)
    print(url)
    print()
