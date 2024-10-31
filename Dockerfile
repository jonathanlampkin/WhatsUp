# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set environment variables
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Copy only requirements.txt first to leverage Docker layer caching
COPY requirements.txt /app

# Install the Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application code into the container
COPY . /app

# Expose the port (default to 5000 if PORT environment variable isn't set)
EXPOSE $PORT

# Health check to ensure the container is up and running
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Run the app using gunicorn and bind it to the specified PORT
CMD ["gunicorn", "app.main:app", "--bind", "0.0.0.0:${PORT}"]
