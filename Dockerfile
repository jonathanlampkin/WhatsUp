# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose the port the app runs on (make sure it matches the port your app uses)
EXPOSE 5000

# Define the command to run your app using gunicorn
CMD ["gunicorn", "main.app:app", "--bind", "0.0.0.0:5000"]
