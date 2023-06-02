# COEN317 P2P-Publish/Subscribe-Decentralized Social Network Project

## Group Members:
- Abhishek Shukla
- Alfonso De La Rosa
- Gnana Mounika Jasti
- Gouthami Edamalapati

## CONTENTS:
1. Setup
2. Run Main Cluster
3. Quickly start up and shut down cluster
4. Testing Cluster
5. Making a Pull Request

---
## SETUP
1. Install Docker and Docker Desktop
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
1. cd into **main_cluster** folder:
```
cd main_cluster
```
2. Build container images:
```
docker build -t p2p-node:v1 ./p2p-node/
docker build -t backend-app:v1 ./backend-app/
```
3. If first time, download the MongoDB Docker image:
```
docker pull mongo:latest
```
4. Delete **registry** container in Docker Desktop, if not first time.
5. Run registry container with the following code [The registry container will host Docker container images, such as flask app container image. When Kubernetes cluster is deployed, Kubernetes will retrieve the container images from the registry container]
```
docker run -d -p 5010:5000 --name registry registry:2
```
6. Tag and push container images to registry container with the following command:
```
docker tag p2p-node:v1 localhost:5010/p2p-node:v1
docker push localhost:5010/p2p-node:v1
docker tag backend-app:v1 localhost:5010/backend-app:v1
docker push localhost:5010/backend-app:v1
docker tag mongo:latest localhost:5010/mongo:latest
docker push localhost:5010/mongo:latest
```
6. Deploy backend-app pods and service:
```
kubectl apply -f ./backend-deployment.yaml
```
7. Deploy p2p-node pods and service:
```
kubectl apply -f ./p2p-deployment.yaml
```

### Terminate Main Cluster
1. Terminate Kubernetes cluster and Kubernetes service:
```
kubectl delete deployment backend-mongo-app
kubectl delete deployment p2p-mongo-app
kubectl delete service backend-service
kubectl delete service p2p-mongo-service
```
2. Delete registry container:
```
docker rm -f registry
```

## QUICKLY STARTING UP/SHUTTING DOWN CLUSTER (TESTING)
0. Ensure that you are in **main_cluster** folder
1. Quickly starting up cluster:
```
docker build -t p2p-node:v1 ./p2p-node/
docker build -t backend-app:v1 ./backend-app/
docker run -d -p 5010:5000 --name registry registry:2
docker tag p2p-node:v1 localhost:5010/p2p-node:v1
docker push localhost:5010/p2p-node:v1
docker tag backend-app:v1 localhost:5010/backend-app:v1
docker push localhost:5010/backend-app:v1
docker tag mongo:latest localhost:5010/mongo:latest
docker push localhost:5010/mongo:latest
kubectl apply -f ./backend-deployment.yaml
kubectl apply -f ./p2p-deployment.yaml
kubectl get pods
```
2. Testing
3. Quickly shutting down cluster
```
kubectl delete deployment backend-mongo-app
kubectl delete deployment p2p-mongo-app
kubectl delete service backend-service
kubectl delete service p2p-mongo-service
docker rm -f registry
```

## TESTING CLUSTER

### View logs of a pod
1. Get the **name** of the pod you want to view with the following command:
```
kubectl get pods
```
2. Open a new terminal
3. Enter the following command to view the logs of the pod with the pod name as they happen. (remove -f if you want to see the logs at that instant)
```
kubectl logs -f POD_NAME
```

### Access the endpoints of a specific Flask app deployed within a Kubernetes pod (backend or p2p)
1. Get the **pod-name** of the pod you wish to access with the following command:
```
kubectl get pods
```
2. Use the following number as the **pod-port** for either backend or p2p: 5000 (This number was obtained from the targetPort from the kubernetes yaml files)
4. Pick a **local-port** value from the following range: 1024-49151. (If you are connecting to multiple pods at the same time, the **local-port** value must different for each pod you are accessing.)
5. Open a separate terminal and enter the following command:
```
kubectl port-forward <pod-name> <local-port>:<pod-port>
```
6. Use the following URL to access the pod
```
http://localhost:<local-port>/endpoint
```
7. Open Postman and use the URL provided

### Or, get port-forwarding commands and url with the following .py file in /main_cluster folder
```
python port-forward.py
```

## MAKING A PULL REQUEST
0. Make sure your repo is updated
```
git pull
```
1. Create a new branch for task and check it out
```
git checkout -b <branch-name>
```
2. Make changes
3. Test
4. cd back to the main repository
5. Add new files
```
git add .
```
6. Commit
```
git commit -m "brief description"
```
7. Push your code
```
git push
```
8. You might get a message in the terminal. Execute suggested command
9. On GitHub repo, create pull request. Do not merge


### SYSTEM TEST

1. Run kubernetes cluster with commands mentioned earlier (Ensure that Docker Desktop is running):
2. cd in to **testing** folder
3. notes on time 20s, 3m, 2h, 1h20m, 3h30m10s
```
locust -f topic-test.py --users 4 --spawn-rate 2 --run-time 20s
```
3. Run test and put results in csv with the following command



### Google Cloud Kubernetes Engine Setup
0. Create Google Cloud account and install on your machine. (Should be able to run **gcloud --version** command). In addition, you must create a project
1. cd into **main_cluster** folder
2. Create and push the docker images of the project
```
docker build -t p2p-node:v1 ./p2p-node/
docker build -t backend-app:v1 ./backend-app/
docker tag p2p-node:v1 gcr.io/coen317project/p2p-node:v1
docker push gcr.io/coen317project/p2p-node:v1
docker tag backend-app:v1 gcr.io/coen317project/backend-app:v1
docker push gcr.io/coen317project/backend-app:v1
docker tag mongo:latest gcr.io/coen317project/mongo:latest
docker push gcr.io/coen317project/mongo:latest
```
Based on:
```
docker tag <IMAGE_NAME> gcr.io/<PROJECT_ID>/<IMAGE_NAME>:<TAG>
docker push gcr.io/<PROJECT_ID>/<IMAGE_NAME>:<TAG>
```
```
kubectl apply -f ./backend-gke-deployment.yaml
kubectl apply -f ./p2p-gke-deployment.yaml
kubectl get pods
```
