# Deployment Guide

This guide covers different deployment options for Scout, from simple local deployment to production-ready setups.

## 🚀 Quick Start

```bash
# Deploy Scout using Kubernetes manifests
kubectl apply -f k8s/
```

## 🔧 Advanced Deployment Options

### Production Deployment with Security

```bash
# Generate secure tokens
API_TOKEN=$(openssl rand -base64 32)
REDIS_PASSWORD=$(openssl rand -base64 32)

# Deploy with all security features
kubectl apply -f k8s/security/
kubectl apply -f k8s/
```

### Development Deployment

```bash
# Deploy with minimal resources for development
kubectl create namespace scout-dev
kubectl apply -f k8s/ --namespace scout-dev
```

## 🏗️ Image Registry

Scout uses **GitHub Container Registry (ghcr.io)** for its Docker images:

- **Free** for public repositories
- **Integrated** with GitHub Actions for automated builds
- **No rate limits** for public images
- **Simple** deployment process

## 📋 Deployment Checklist

### Pre-deployment
- [ ] **Kubernetes cluster** running
- [ ] **kubectl** configured
- [ ] **kubectl** configured
- [ ] **Image registry** chosen
- [ ] **Namespace** created (optional)

### Security (Production)
- [ ] **Network policies** enabled
- [ ] **RBAC** configured
- [ ] **Secrets** generated
- [ ] **Pod security** standards enabled
- [ ] **Resource limits** set

### Monitoring
- [ ] **Prometheus** enabled
- [ ] **Health checks** configured
- [ ] **Logging** set up
- [ ] **Alerting** configured

## 🔍 Troubleshooting

### Image Pull Errors

```bash
# Check if images exist
docker pull ghcr.io/scout-io/scout-backend:latest
docker pull ghcr.io/scout-io/scout-frontend:latest

# Check pod events
kubectl describe pod -n scout -l app.kubernetes.io/component=backend
```

### Network Issues

```bash
# Check network policies
kubectl get networkpolicies -n scout

# Test pod connectivity
kubectl exec -n scout deployment/scout-backend -- curl -s http://scout-redis:6379

# Check service endpoints
kubectl get endpoints -n scout
```

### Resource Issues

```bash
# Check resource usage
kubectl top pods -n scout

# Check node capacity
kubectl describe nodes

# Scale up if needed
kubectl scale deployment scout-backend -n scout --replicas=3
```

## 🚀 Accessing Scout

### Port Forwarding (Development)

```bash
# Access via port forwarding
kubectl port-forward -n scout svc/scout-nginx 8080:80

# Access the application
open http://localhost:8080
```

### LoadBalancer (Production)

```bash
# Create LoadBalancer service
kubectl expose deployment scout-nginx -n scout --type=LoadBalancer --port=80

# Get external IP
kubectl get service scout-nginx -n scout
```

### Ingress (Production)

```bash
# Install with Ingress
kubectl apply -f k8s/ingress/
```

## 📊 Monitoring

### Prometheus Metrics

```bash
# Access Prometheus
kubectl port-forward -n scout svc/scout-prometheus 9090:9090

# View metrics
open http://localhost:9090
```

### Application Logs

```bash
# View backend logs
kubectl logs -n scout deployment/scout-backend -f

# View frontend logs
kubectl logs -n scout deployment/scout-frontend -f
```

## 🔄 Upgrading

### Kubernetes Deployment Upgrade

```bash
# Update deployment
kubectl apply -f k8s/
```

### Image Update

```bash
# Update to specific image tag
kubectl set image deployment/scout-backend scout-backend=ghcr.io/scout-io/scout-backend:v1.2.0 -n scout
kubectl set image deployment/scout-frontend scout-frontend=ghcr.io/scout-io/scout-frontend:v1.2.0 -n scout
```

## 🧹 Cleanup

### Remove Scout

```bash
# Uninstall Scout
kubectl delete -f k8s/

# Delete namespace
kubectl delete namespace scout
```

### Remove Images

```bash
# Remove local images
docker rmi scout-backend:latest scout-frontend:latest
```

## 📚 Additional Resources

- [Security Guide](SECURITY.md) - Production security best practices
- [Kubernetes Documentation](https://kubernetes.io/docs/) - Kubernetes concepts
- [Kubernetes Documentation](https://kubernetes.io/docs/) - Kubernetes concepts
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) - Image registry documentation 