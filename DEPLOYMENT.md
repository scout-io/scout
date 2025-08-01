# Deployment Guide

This guide covers different deployment options for Scout, from simple local deployment to production-ready setups.

## 🚀 Quick Start (Recommended)

### Option 1: GitHub Container Registry (Default)

```bash
# Add the Helm repository
helm repo add scout https://scout-io.github.io/scout
helm repo update

# Install Scout (uses GitHub Container Registry by default)
helm install scout scout/scout --namespace scout --create-namespace
```

### Option 2: Docker Hub

```bash
# Install with Docker Hub images
helm install scout scout/scout --namespace scout --create-namespace \
  --set global.imageRegistry=docker.io
```

### Option 3: Google Container Registry

```bash
# Install with GCR images
helm install scout scout/scout --namespace scout --create-namespace \
  --set global.imageRegistry=gcr.io \
  --set images.backend.repository=YOUR_PROJECT/scout-backend \
  --set images.frontend.repository=YOUR_PROJECT/scout-frontend
```

## 🔧 Advanced Deployment Options

### Production Deployment with Security

```bash
# Generate secure tokens
API_TOKEN=$(openssl rand -base64 32)
REDIS_PASSWORD=$(openssl rand -base64 32)

# Install with all security features
helm install scout scout/scout --namespace scout --create-namespace \
  --set security.networkPolicy.enabled=true \
  --set security.podSecurity.enabled=true \
  --set rbac.create=true \
  --set auth.token="$API_TOKEN" \
  --set redis.authEnabled=true \
  --set redis.password="$REDIS_PASSWORD" \
  --set backend.replicas=3 \
  --set frontend.replicas=2
```

### Development Deployment

```bash
# Install with minimal resources for development
helm install scout-dev scout/scout --namespace scout-dev --create-namespace \
  --set backend.replicas=1 \
  --set frontend.replicas=1 \
  --set prometheus.enabled=false \
  --set backend.resources.requests.memory=128Mi \
  --set frontend.resources.requests.memory=64Mi
```

## 🏗️ Image Registry Options

### GitHub Container Registry (ghcr.io) - Default
- **Pros**: Free, integrated with GitHub, automatic builds
- **Cons**: Rate limits for anonymous pulls
- **Best for**: Open source projects, GitHub users

### Docker Hub (docker.io)
- **Pros**: Widely supported, good documentation
- **Cons**: Rate limits, requires account
- **Best for**: General use, Docker ecosystem

### Google Container Registry (gcr.io)
- **Pros**: Fast, integrated with GKE
- **Cons**: Requires Google Cloud account
- **Best for**: GKE deployments, Google Cloud users

### Custom Registry
- **Pros**: Full control, no rate limits
- **Cons**: Requires infrastructure
- **Best for**: Enterprise deployments

## 📋 Deployment Checklist

### Pre-deployment
- [ ] **Kubernetes cluster** running
- [ ] **Helm** installed
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

# Check image pull secrets
kubectl get secrets -n scout
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
helm install scout scout/scout --namespace scout --create-namespace \
  --set nginx.ingress.enabled=true \
  --set nginx.ingress.hosts[0].host=scout.yourdomain.com
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

### Helm Chart Upgrade

```bash
# Update repository
helm repo update

# Upgrade deployment
helm upgrade scout scout/scout --namespace scout
```

### Image Update

```bash
# Update to specific image tag
helm upgrade scout scout/scout --namespace scout \
  --set images.backend.tag=v1.2.0 \
  --set images.frontend.tag=v1.2.0
```

## 🧹 Cleanup

### Remove Scout

```bash
# Uninstall Scout
helm uninstall scout -n scout

# Delete namespace
kubectl delete namespace scout
```

### Remove Images

```bash
# Remove local images
docker rmi scout-backend:latest scout-frontend:latest

# Remove from registry (if you have access)
docker rmi ghcr.io/scout-io/scout-backend:latest
docker rmi ghcr.io/scout-io/scout-frontend:latest
```

## 📚 Additional Resources

- [Security Guide](SECURITY.md) - Production security best practices
- [Kubernetes Documentation](https://kubernetes.io/docs/) - Kubernetes concepts
- [Helm Documentation](https://helm.sh/docs/) - Helm usage guide
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) - Image registry documentation 