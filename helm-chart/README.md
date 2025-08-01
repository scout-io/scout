# Scout Helm Chart

A Helm chart for deploying Scout - Self-optimizing AB testing tool to Kubernetes.

## 🚀 Quick Start

### Prerequisites

- Kubernetes cluster (v1.19+)
- Helm 3.x
- kubectl configured

### Installation

```bash
# Add the Scout repository
helm repo add scout https://scout-io.github.io/scout
helm repo update

# Install Scout
helm install scout scout/scout

# Or install from local chart
helm install scout ./helm-chart
```

### Basic Configuration

```bash
# Install with custom values
helm install scout ./helm-chart \
  --set backend.replicas=3 \
  --set frontend.replicas=2 \
  --set redis.persistence.size=5Gi

# Or use a values file
helm install scout ./helm-chart -f my-values.yaml
```

## 📋 Configuration

### Values File Structure

The chart supports extensive customization through the `values.yaml` file:

```yaml
# Global settings
global:
  environment: production
  imageRegistry: ""

# Component configuration
backend:
  enabled: true
  replicas: 2
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi

frontend:
  enabled: true
  replicas: 1
  resources:
    requests:
      cpu: 50m
      memory: 128Mi

redis:
  enabled: true
  persistence:
    enabled: true
    size: 1Gi

prometheus:
  enabled: true
  persistence:
    enabled: true
    size: 5Gi
```

### Common Configuration Options

#### Scaling

```bash
# Scale backend to 5 replicas
helm upgrade scout ./helm-chart --set backend.replicas=5

# Enable auto-scaling
helm upgrade scout ./helm-chart \
  --set hpa.backend.enabled=true \
  --set hpa.backend.maxReplicas=10
```

#### Resources

```bash
# Increase backend memory
helm upgrade scout ./helm-chart \
  --set backend.resources.limits.memory=1Gi \
  --set backend.resources.requests.memory=512Mi
```

#### Storage

```bash
# Increase Redis storage
helm upgrade scout ./helm-chart \
  --set redis.persistence.size=10Gi

# Use specific storage class
helm upgrade scout ./helm-chart \
  --set redis.persistence.storageClass=fast-ssd
```

#### Authentication

```bash
# Enable API protection
helm upgrade scout ./helm-chart \
  --set auth.protectedAPI=true \
  --set auth.authToken="your-secure-token"
```

#### Ingress

```bash
# Configure ingress with custom domain
helm upgrade scout ./helm-chart \
  --set nginx.ingress.hosts[0].host=scout.mycompany.com
```

## 🏗️ Architecture

The Helm chart deploys the following components:

- **Namespace**: Isolated environment for Scout
- **Redis**: Data persistence with configurable storage
- **Backend**: FastAPI application with auto-scaling
- **Frontend**: React UI with configurable replicas
- **Nginx**: Reverse proxy with ingress support
- **Prometheus**: Monitoring with Kubernetes service discovery
- **HPA**: Automatic scaling based on CPU/memory

## 📊 Monitoring

### Prometheus Integration

Prometheus is automatically configured to scrape metrics from all Scout services:

```bash
# Access Prometheus
kubectl port-forward -n scout svc/scout-prometheus 9090:9090
# Visit http://localhost:9090
```

### Metrics Available

- **Backend**: Request rates, response times, error rates
- **Redis**: Memory usage, connection counts
- **System**: CPU, memory, disk usage

## 🔧 Advanced Configuration

### Development Environment

```yaml
# values-dev.yaml
backend:
  replicas: 1
  resources:
    requests:
      cpu: 50m
      memory: 128Mi

frontend:
  replicas: 1

redis:
  persistence:
    size: 100Mi

prometheus:
  enabled: false
```

### Production Environment

```yaml
# values-prod.yaml
backend:
  replicas: 5
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 1Gi

redis:
  persistence:
    size: 10Gi

prometheus:
  persistence:
    size: 20Gi
  retention:
    time: "90d"
```

### High Availability

```yaml
# values-ha.yaml
backend:
  replicas: 3
  autoscaling:
    enabled: true
    maxReplicas: 10

frontend:
  replicas: 2

nginx:
  replicas: 2

podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

## 🚀 Deployment Examples

### Local Development

```bash
# Install for local development
helm install scout-dev ./helm-chart \
  --set backend.replicas=1 \
  --set frontend.replicas=1 \
  --set prometheus.enabled=false \
  --set redis.persistence.size=100Mi
```

### Production with Custom Domain

```bash
# Install for production
helm install scout-prod ./helm-chart \
  --set backend.replicas=3 \
  --set auth.protectedAPI=true \
  --set auth.authToken="$(openssl rand -base64 32)" \
  --set nginx.ingress.hosts[0].host=scout.company.com \
  --set redis.persistence.size=10Gi \
  --set prometheus.persistence.size=20Gi
```

### Multi-Environment Setup

```bash
# Development
helm install scout-dev ./helm-chart -f values-dev.yaml

# Staging
helm install scout-staging ./helm-chart -f values-staging.yaml

# Production
helm install scout-prod ./helm-chart -f values-prod.yaml
```

## 🔄 Upgrades and Rollbacks

### Upgrading

```bash
# Upgrade to new version
helm upgrade scout ./helm-chart

# Upgrade with new values
helm upgrade scout ./helm-chart \
  --set backend.replicas=5 \
  --set redis.persistence.size=20Gi
```

### Rollbacks

```bash
# List releases
helm list

# Rollback to previous version
helm rollback scout 1

# Rollback to specific version
helm rollback scout 2
```

## 🧹 Cleanup

### Uninstall Scout

```bash
# Remove Scout deployment
helm uninstall scout

# Remove namespace (if created by chart)
kubectl delete namespace scout
```

### Complete Cleanup

```bash
# Remove all Scout resources
helm uninstall scout
kubectl delete namespace scout

# Remove cluster-scoped resources
kubectl delete clusterrole scout-prometheus
kubectl delete clusterrolebinding scout-prometheus
```

## 🔍 Troubleshooting

### Common Issues

#### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n scout

# Check pod logs
kubectl logs -n scout deployment/scout-backend

# Describe pod for events
kubectl describe pod -n scout <pod-name>
```

#### Image Pull Errors

```bash
# Check image pull secrets
kubectl get secrets -n scout

# Create image pull secret
kubectl create secret docker-registry regcred \
  --docker-server=your-registry.com \
  --docker-username=your-username \
  --docker-password=your-password \
  -n scout
```

#### Ingress Not Working

```bash
# Check ingress controller
kubectl get pods -n ingress-nginx

# Check ingress status
kubectl get ingress -n scout

# Check ingress controller logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

### Useful Commands

```bash
# View all resources
kubectl get all -n scout

# Follow backend logs
kubectl logs -f -n scout -l app.kubernetes.io/component=backend

# Execute into backend pod
kubectl exec -it -n scout deployment/scout-backend -- /bin/bash

# Port forward services
kubectl port-forward -n scout svc/scout-nginx 8080:80 &
kubectl port-forward -n scout svc/scout-prometheus 9090:9090 &

# Scale deployments
kubectl scale deployment scout-backend --replicas=3 -n scout
```

## 📚 Additional Resources

- [Scout Documentation](https://scout-3.gitbook.io/scout-docs)
- [Helm Documentation](https://helm.sh/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)

## 🤝 Contributing

When contributing to the Helm chart:

1. Follow the existing naming conventions
2. Add appropriate labels and annotations
3. Include resource limits and health checks
4. Update this README with any new configuration options
5. Test on a local cluster before submitting

## 📄 License

This Helm chart is licensed under the MIT License. 