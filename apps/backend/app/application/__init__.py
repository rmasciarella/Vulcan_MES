"""
Application Layer

This layer contains application services that orchestrate domain operations
and coordinate between different layers. It implements use cases and handles
cross-cutting concerns like transactions, logging, and security.

The application layer is responsible for:
- Use case implementations (application services)
- Transaction management
- Security and authorization
- Input validation and transformation
- Coordination between domain services

Components:
- scheduling/: Use cases and application services for production scheduling
"""
