# Use a lightweight Python base image
FROM python

# Set working directory
WORKDIR /app

# Copy and install dependencies separately for layer caching
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the application port
EXPOSE 6559

# Run the application
CMD ["python", "app.py"]
