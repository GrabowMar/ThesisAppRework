FROM alpine
WORKDIR /app
COPY . .
RUN ls -R analyzer/services
