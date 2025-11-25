# ThesisApp Rework

A comprehensive platform for analyzing AI-generated applications. This system orchestrates multiple AI models to generate web applications, then subjects them to rigorous static, dynamic, performance, and AI-based analysis.

## Key Features

- **Multi-Model Generation**: Support for 25+ AI models (OpenAI, Anthropic, Google, etc.).
- **Automated Analysis**:
  - **Static Analysis**: Bandit, Semgrep, ESLint, JSHint.
  - **Dynamic Analysis**: OWASP ZAP integration.
  - **Performance Testing**: Locust-based load testing.
  - **AI Analysis**: Advanced code review using LLMs.
- **Real-time Dashboard**: Monitor analysis progress and results.
- **Containerized Architecture**: Microservices for scalable analysis.

## Documentation

- [Quick Start](QUICKSTART.md): Get up and running in minutes.
- [Architecture](ARCHITECTURE.md): System design and component overview.
- [Development Guide](DEVELOPMENT_GUIDE.md): How to contribute and extend the platform.
- [Operations](OPERATIONS.md): Deployment, maintenance, and troubleshooting.
