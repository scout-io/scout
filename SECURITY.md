# Security Guide

This document outlines the security features and best practices for deploying Scout in production.

## 🔒 Security Features

### Network Policies
Scout uses network policies to restrict pod-to-pod communication:
- **Frontend → Backend**: Frontend can only communicate with Backend on port 8000
- **Nginx → Frontend/Backend**: Nginx can communicate with Frontend (port 3000) and Backend (port 8000)
- **Backend → Redis**: Backend can only communicate with Redis on port 6379
- **Prometheus → Backend**: Prometheus can scrape Backend metrics on port 8000
- **External Access**: Configurable external access to Nginx on port 80

### Pod Security Standards
All Scout containers follow security best practices:
- **Non-root execution**: All containers run as user ID 1000
- **Read-only filesystem**: Root filesystem is read-only (except /tmp)
- **Dropped capabilities**: All Linux capabilities are dropped
- **No privilege escalation**: Containers cannot escalate privileges

### RBAC (Role-Based Access Control)
- **Service Account**: Dedicated service account for Backend
- **Minimal permissions**: Only necessary permissions granted
- **Namespace-scoped**: All permissions limited to Scout namespace

### Secrets Management
- **Kubernetes Secrets**: Sensitive data stored in encrypted secrets
- **Base64 encoding**: All secret values are base64 encoded
- **Configurable authentication**: Token-based API protection
- **Redis authentication**: Optional Redis password protection

## 🚀 Deployment Security

### Enable Security Features

```bash
# Enable all security features
kubectl apply -f k8s/security/
kubectl apply -f k8s/
```

### Generate Secure Tokens

```bash
# Generate API authentication token
openssl rand -base64 32

# Generate Redis password
openssl rand -base64 32
```

### Production Security Checklist

- [ ] **Network policies enabled**
- [ ] **Pod security standards enabled**
- [ ] **RBAC enabled with minimal permissions**
- [ ] **Authentication token configured**
- [ ] **Redis authentication enabled**
- [ ] **Secrets used instead of ConfigMaps**
- [ ] **Resource limits configured**
- [ ] **Health checks enabled**
- [ ] **Non-root containers running**

## 🔧 Security Configuration

### Network Policy Configuration

```yaml
networkPolicy:
  enabled: true
  allowExternalAccess: true  # Allow external access to nginx
```

### Pod Security Configuration

```yaml
security:
  podSecurity:
    enabled: true
    runAsNonRoot: true
    readOnlyRootFilesystem: true
    dropAllCapabilities: true
```

### RBAC Configuration

```yaml
rbac:
  create: true
  minimalPermissions: true
```

### Authentication Configuration

```yaml
auth:
  protectedAPI: true
  token: "your-secure-token"
  tokenExpiration: 24  # hours
```

### Redis Security

```yaml
redis:
  authEnabled: true
  password: "your-redis-password"
```

## 🛡️ Security Best Practices

### 1. Use Strong Authentication
- Generate secure tokens using `openssl rand -base64 32`
- Rotate tokens regularly
- Use different tokens for different environments

### 2. Enable Network Policies
- Restrict pod-to-pod communication
- Only allow necessary ports
- Monitor network traffic

### 3. Implement Pod Security
- Run containers as non-root
- Use read-only filesystems
- Drop unnecessary capabilities

### 4. Manage Secrets Properly
- Use Kubernetes secrets, not ConfigMaps
- Rotate secrets regularly
- Use external secret management for production

### 5. Monitor and Audit
- Enable Prometheus metrics
- Set up alerting for security events
- Review logs regularly

## 🔍 Security Monitoring

### Prometheus Metrics
Scout exposes security-related metrics:
- `scout_api_requests_total`: API request count
- `scout_auth_failures_total`: Authentication failures
- `scout_redis_connections`: Redis connection status

### Health Checks
- **Liveness probe**: `/docs` endpoint
- **Readiness probe**: `/docs` endpoint
- **Startup probe**: Configurable delay

### Logging
- **Structured logging**: JSON format
- **Security events**: Authentication and authorization logs
- **Error tracking**: Failed requests and errors

## 🚨 Incident Response

### Security Breach Response
1. **Isolate affected pods**: Scale down to 0 replicas
2. **Rotate secrets**: Update all authentication tokens
3. **Review logs**: Analyze security event logs
4. **Update security**: Patch vulnerabilities
5. **Monitor**: Watch for additional attacks

### Recovery Procedures
1. **Backup restoration**: Restore from secure backups
2. **Secret rotation**: Update all credentials
3. **Network isolation**: Review and update network policies
4. **Audit review**: Analyze security logs

## 📚 Additional Resources

- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)

## 🤝 Contributing to Security

If you discover a security vulnerability:
1. **Do not disclose publicly**
2. **Report privately** to the maintainers
3. **Provide detailed information** about the issue
4. **Allow time for patching** before disclosure

---

**Remember**: Security is an ongoing process. Regularly review and update security configurations as threats evolve. 