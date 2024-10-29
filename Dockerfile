# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy only requirements.txt first to leverage Docker layer caching
COPY requirements.txt /app

# Install the Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application code into the container
COPY . /app

# Expose the port the app runs on (make sure it matches the port your app uses)
EXPOSE 5000

# Define the command to run your app using gunicorn and use the environment variable $PORT
CMD ["gunicorn", "main.app:app", "--bind", "0.0.0.0:${PORT:-5000}"]
