# --- Base Image ---
# Use an official Python runtime as a parent image.
# The 'slim' version is a good balance of size and functionality.
FROM python:3.11-slim

# --- Environment Variables ---
# Prevents Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE 1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1
# Set the container port. 8080 is a common default for cloud services like Cloud Run.
ENV PORT 8080

# --- Working Directory ---
# Set the working directory inside the container.
WORKDIR /app

# --- Install Dependencies ---
# Copy the requirements file first to leverage Docker's layer caching.
# This layer is only rebuilt if requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Copy Application Code ---
# Copy the rest of your application's code into the working directory.
COPY . .

# --- Create Runtime Directories ---
# Create directories for logs and sessions so the application has write permissions.
RUN mkdir -p /app/app_logs /app/chat_sessions && \
    chown -R www-data:www-data /app/app_logs /app/chat_sessions
# Switch to a non-root user for better security
USER www-data

# --- Expose Port ---
# Expose the port the app will run on.
EXPOSE 8080

# --- Run Command ---
# Use Gunicorn, a production-grade WSGI server, to run the application.
# The '--bind 0.0.0.0:$PORT' command tells the server to listen on all network interfaces
# on the port specified by the PORT environment variable.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]