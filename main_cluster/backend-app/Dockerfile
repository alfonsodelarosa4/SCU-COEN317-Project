# Python runtime parent image
FROM python:3.9-slim-buster

# set working directory to /app
WORKDIR /app

# copy the requirements file -> the container
COPY requirements.txt .

# install packages from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# copy application's source code -> the container
COPY . .

# port 5000
EXPOSE 5000

# environment variable for Flask for production mode
ENV FLASK_ENV=production

# run the command to start the Flask app
CMD ["python", "app.py"]
