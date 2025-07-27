FROM node:18

WORKDIR /app

# Copy package files
COPY package.json ./

# Optimized install command that doesn't require package-lock.json
RUN npm install --legacy-peer-deps --force --no-audit --no-fund --prefer-offline

# Copy the rest of the app
COPY . .

# Expose the application port (make sure Vite is configured to bind to 0.0.0.0)
EXPOSE 9711
ENV PORT=9711

# Start the React development server
CMD ["npx", "vite", "--host", "0.0.0.0"]
