# WebSocket-Based Testing Infrastructure Architecture

## Overview
This document outlines the new WebSocket-based testing infrastructure that replaces the RESTful API approach with real-time, bidirectional communication.

## Key Advantages of WebSocket Architecture
1. **Real-time Communication**: Instant status updates and progress monitoring
2. **Bidirectional**: Services can push updates without client polling
3. **Lower Latency**: No HTTP overhead for continuous communication
4. **Persistent Connections**: Reduced connection establishment overhead
5. **Event-Driven**: Natural fit for asynchronous testing operations

## Architecture Components

### 1. WebSocket Gateway (`websocket_gateway.py`)
- Central hub for all WebSocket connections
- Routes messages between clients and testing services
- Manages connection lifecycle and health monitoring
- Implements message authentication and validation

### 2. Testing Services (WebSocket-enabled containers)
- **Security Scanner**: Real-time security analysis with live progress
- **Performance Tester**: Live performance metrics streaming
- **ZAP Scanner**: Real-time vulnerability discovery updates
- **AI Analyzer**: Streaming AI analysis results
- **Test Coordinator**: Orchestrates batch operations

### 3. WebSocket Message Protocol
```json
{
  "type": "test_request|test_result|status_update|error|heartbeat",
  "id": "unique_message_id",
  "service": "security|performance|zap|ai|coordinator",
  "data": { /* service-specific payload */ },
  "timestamp": "2025-08-08T12:00:00Z",
  "client_id": "requesting_client_identifier"
}
```

### 4. Connection Management
- Client registration and authentication
- Service discovery and health checks
- Automatic reconnection handling
- Message queuing for offline services

## Message Flow Examples

### Test Request Flow
1. Client sends test request via WebSocket
2. Gateway validates and routes to appropriate service
3. Service acknowledges request and begins processing
4. Service streams progress updates in real-time
5. Service sends final results when complete

### Batch Operation Flow
1. Client requests batch operation
2. Coordinator breaks down into individual tests
3. Each test streams progress independently
4. Coordinator aggregates and reports overall progress
5. Final batch results sent when all tests complete

## Implementation Strategy
1. Replace REST endpoints with WebSocket message handlers
2. Implement message routing and validation
3. Add real-time progress tracking
4. Update containers for WebSocket communication
5. Maintain backward compatibility with existing data models
