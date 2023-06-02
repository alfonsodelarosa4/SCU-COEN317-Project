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
        commands.append((port_forward_command, log_command, url,pod_name))
    return commands

# get the terminal output of a command
def get_output_of_command(command):
    command_list = command.split()
    result = subprocess.run(command_list, capture_output=True, text=True)
    return result.stdout.strip()