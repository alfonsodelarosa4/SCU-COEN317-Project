# COEN317 P2P-Publish/Subscribe-Decentralized Social Network Project

Group Members:
- Abhishek Shukla
- Alfonso De La Rosa
- Gnana Mounika Jasti
- Gouthami Edamalapati

## CONTENTS:
0. Setup
1. Steps to Run Main Cluster
2. Steps to Run Test Cluster

---
## Setup
1. Install Docker, Docker Desktop
2. Test if Docker installed
```
docker version
```
3. Enable Kubernetes on Docker Desktop
4. Install Kubernetes separately
5. Test if Kubernetes installed
```
kubectl version
```
6. Start Docker Desktop

---
## STEPS TO RUN MAIN CLUSTER

### Running Cluster
1. cd into **main_cluster** folder
```
cd main_cluster
```
2. Build container images
```
docker build -t p2p-node:v1 ./p2p-node/
docker build -t backend-app:v1 ./backend-app/
```
3. If not first time, delete **registry** container in Docker Desktop
4. Run registry container with the following code [The registry container will host Docker container images, such as flask app container image. When Kubernetes cluster is deployed, Kubernetes will retrieve the container images from the registry container]
```
docker run -d -p 5000:5000 --name registry registry:2
```
5. Tag and push container images to registry container
```
docker tag p2p-node:v1 localhost:5000/p2p-node:v1
docker push localhost:5000/p2p-node:v1
docker tag backend-app:v1 localhost:5000/backend-app:v1
docker push localhost:5000/backend-app:v1
```
6. Deploy backend-app pods and service
```
kubectl apply -f ./backend-deployment.yaml
```
7. Deploy p2p-node pods and service
```
kubectl apply -f ./p2p-deployment.yaml
```

### VIEW LOGS/PRINT STATEMENTS OF A POD
1. Get the name of the pod you want to view with the following command
```
kubectl get pods
```
2. Open a new terminal
3. Enter the following command to view the logs of the pod with the pod name
```
kubectl logs -f POD_NAME
```

### Terminate Test Cluster
1. Terminate Kubernetes cluster and Kubernetes service
```
kubectl delete deployment backend-app
kubectl delete deployment p2p-node
kubectl delete service backend-service
kubectl delete service p2p-service
```
2. Delete registry container on Docker Desktop

---
## STEPS TO RUN TEST CLUSTER
### About
This is a Kubernetes cluster of 4 pods. Each pod has a Docker container of a Flask app. Each Flask app will send a message to a range of ip addresses. 

### Running Test Cluster
1. cd into **test_cluster** folder
```
cd test_cluster
```
2. Build container image
```
docker build -t my-p2p-test_node:v1 ./test_node/
```
3. If not first time, delete **registry** container in Docker Desktop
4. Run registry container with the following code [The registry container will host Docker container images, such as flask app container image. When Kubernetes cluster is deployed, Kubernetes will retrieve the container images from the registry container]
```
docker run -d -p 5000:5000 --name registry registry:2
```
5. Tag and push container image to registry container
```
docker tag my-p2p-test_node:v1 localhost:5000/my-p2p-test_node:v1
docker push localhost:5000/my-p2p-test_node:v1
```
6. Deploy Kubernetes cluster and Kubernetes service
```
kubectl apply -f ./deployment.yaml
kubectl apply -f ./service.yaml
```

### View the terminal of Flask App of a Pod in Kubernetes cluster
1. Get the container id of a pod
```
docker ps
```
2. Open new terminal
3. Run the following command of the logs
```
docker logs -f <container_id>
```

### Terminate Test Cluster
1. Terminate Kubernetes cluster and Kubernetes service
```
kubectl delete deployment flask-app
kubectl delete service flask-app-service
```
2. Delete registry container on Docker Desktop

### Warning for Test Cluster
If the Kubernetes cluster is ran too many times, the ip address of the pods of subsquent Kubernetes clusters will not be within range. 
To fix this, 
1. Look at the ip addresses of the pods with the following command:
```
kubectl get pods -o wide
```
2. change line 17 in the app.py file to a bigger range (the highest ip address, highest ip address + 100)
3. Terminate Kubernetes cluster and service
4. Deploy Kubernetes cluster and service again
