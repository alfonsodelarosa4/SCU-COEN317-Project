# COEN317 P2P-Publish/Subscribe-Decentralized Social Network Project

Names:
- Abhishek Shukla
- Alfonso De La Rosa
- Gnana Mounika Jasti
- Gouthami Edamalapati

## Test Cluster
### About
This is a Kubernetes cluster of 4 pods. Each pod has a Docker 
container of a Flask app. Each Flask app will send a message 
to a range of ip addresses. 

### Setup
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

### Running Test Cluster
1. cd into **test_cluster** folder
2. Build container image
```
docker build -t my-p2p-test_node:v1 ./test_node/
```
3. If not first time, delete **registry** container in Docker Desktop
4. Run registry container [The registry container will host Docker container images, such as flask app container image. When Kubernetes cluster is deployed, Kubernetes will retrieve the container images fro the registry container]
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
3. Run the following command
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

### Warning
If the Kubernetes cluster is ran too many times, the ip address of 
the pods of subsquent Kubernetes clusters will not be within range. 
To fix this, 
1. Look at the ip addresses of the pods with the following command:
```
kubectl get pods -o wide
```
2. change line 17 in the app.py file to a bigger range (the highest ip address, highest ip address + 100)
3. Terminate Kubernetes cluster and service
4. Deploy Kubernetes cluster and service again
