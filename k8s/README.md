# Scout Kubernetes Deployment

This directory contains all the necessary Kubernetes manifests and scripts to deploy Scout to a Kubernetes cluster. The deployment has been tested and verified to work with local development clusters (kind) and production environments.

## 📋 Prerequisites

- **Kubernetes cluster** (v1.19+) with kubectl configured
- **Docker** for building images
- **kind** (for local development) or access to a Kubernetes cluster
- **Ingress controller** (recommended: nginx-ingress) for external access
- **Metrics server** (for HPA to work)

## 🚀 Quick Start

### Option 1: Local Development with kind (Recommended)

```bash
# 1. Install kind (if not already installed)
brew install kind

# 2. Create a local Kubernetes cluster
kind create cluster --name scout-cluster

# 3. Build Docker images
./k8s/build-images.sh

# 4. Load images into kind cluster
kind load docker-image scout-backend:latest --name scout-cluster
kind load docker-image scout-frontend:latest --name scout-cluster

# 5. Deploy Scout
./k8s/deploy.sh

# 6. Access Scout
kubectl port-forward -n scout svc/scout-nginx 8080:80
# Visit http://localhost:8080
```

### Option 2: Production Cluster

```bash
# 1. Build and push images to your registry
./k8s/build-images.sh
docker tag scout-backend:latest your-registry/scout-backend:latest
docker tag scout-frontend:latest your-registry/scout-frontend:latest
docker push your-registry/scout-backend:latest
docker push your-registry/scout-frontend:latest

# 2. Update image references in k8s/backend.yaml and k8s/frontend.yaml
# Change imagePullPolicy from "IfNotPresent" to "Always"
# Update image names to your registry

# 3. Deploy to your cluster
./k8s/deploy.sh
```

## 📁 File Structure

```
k8s/
├── README.md                 # This file
├── build-images.sh          # Script to build Docker images
├── deploy.sh                # Deployment script
├── cleanup.sh               # Cleanup script
├── kustomization.yaml       # Kustomize configuration
├── namespace.yaml           # Scout namespace
├── configmap.yaml           # Configuration for backend
├── secret.yaml              # Secrets management
├── redis.yaml               # Redis deployment with persistence
├── backend.yaml             # Backend API deployment
├── frontend.yaml            # React frontend deployment
├── nginx-config.yaml        # Nginx configuration
├── nginx.yaml               # Nginx proxy + Ingress
├── prometheus-config.yaml   # Prometheus configuration
├── prometheus.yaml          # Prometheus deployment with RBAC
└── hpa.yaml                 # Horizontal Pod Autoscaler
```

## 🏗️ Architecture

The Kubernetes deployment consists of:

- **Scout Namespace**: Isolated environment for all Scout resources
- **Redis**: Data persistence with 1Gi PVC, configured for production
- **Backend**: FastAPI application (2+ replicas) with health checks and resource limits
- **Frontend**: React application (1 replica) with health checks
- **Nginx**: Reverse proxy and load balancer with Ingress for external access
- **Prometheus**: Metrics collection with RBAC and Kubernetes service discovery
- **HPA**: Automatic scaling based on CPU/memory usage

### Network Flow

```
Internet → Ingress → Nginx Service → Nginx Pods
                                  ↓
                               Backend Service → Backend Pods → Redis
                                  ↓
                               Frontend Service → Frontend Pods
```

## ⚙️ Configuration

### Environment Variables

The deployment uses ConfigMaps and Secrets for configuration:

**ConfigMap (`scout-config`):**
- `REDIS_HOST`: Redis service hostname (scout-redis)
- `REDIS_PORT`: Redis port (6379)
- `REDIS_CONTEXT_TTL`: TTL for Redis contexts (86400)
- `SCOUT_HOST`: Backend bind address (0.0.0.0)
- `SCOUT_PORT`: Backend port (8000)
- `SCOUT_DEBUG`: Debug mode (false)
- `SCOUT_REDIS_ENABLED`: Enable Redis (true)
- `SCOUT_DISABLE_DOCKER_LOGS`: Disable Docker log streaming (true for K8s)

**Secret (`scout-secrets`):**
- `SCOUT_PROTECTED_API`: Enable API protection (false by default)
- `SCOUT_AUTH_TOKEN`: Authentication token (empty by default)

### Resource Limits

**Backend:**
- Requests: 100m CPU, 256Mi memory
- Limits: 500m CPU, 512Mi memory

**Frontend:**
- Requests: 50m CPU, 128Mi memory
- Limits: 200m CPU, 256Mi memory

**Redis:**
- Requests: 50m CPU, 64Mi memory
- Limits: 100m CPU, 128Mi memory

**Nginx:**
- Requests: 25m CPU, 32Mi memory
- Limits: 100m CPU, 64Mi memory

**Prometheus:**
- Requests: 100m CPU, 256Mi memory
- Limits: 500m CPU, 512Mi memory

## 🔧 Customization

### 1. Change Domain/Host

Edit `k8s/nginx.yaml` and update the Ingress host:

```yaml
spec:
  rules:
  - host: your-domain.com  # Change this
```

### 2. Enable Authentication

```bash
# Generate a secure token
TOKEN=$(openssl rand -base64 32)

# Update the secret
kubectl patch secret scout-secrets -n scout -p="{\"stringData\":{\"SCOUT_PROTECTED_API\":\"true\",\"SCOUT_AUTH_TOKEN\":\"$TOKEN\"}}"
```

### 3. Scale Services

```bash
# Scale backend manually
kubectl scale deployment scout-backend --replicas=5 -n scout

# Or edit HPA limits in k8s/hpa.yaml
```

### 4. Resource Limits

Edit the `resources` sections in the deployment files to adjust CPU and memory limits.

### 5. Storage

By default, Redis and Prometheus use 1Gi and 5Gi respectively. To change:

```yaml
# In redis.yaml and prometheus.yaml
resources:
  requests:
    storage: 10Gi  # Change this
```

## 📊 Monitoring

### Prometheus Metrics

Access Prometheus dashboard:
```bash
kubectl port-forward -n scout svc/scout-prometheus 9090:9090
# Visit http://localhost:9090
```

Metrics are automatically discovered from services with these annotations:
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

### Auto-scaling

The deployment includes HorizontalPodAutoscaler for both backend and frontend:

**Backend HPA:**
- Min replicas: 2
- Max replicas: 10
- CPU target: 70%
- Memory target: 80%

**Frontend HPA:**
- Min replicas: 1
- Max replicas: 3
- CPU target: 70%

## 🐛 Troubleshooting

### Common Issues

#### 1. Pods Not Starting

```bash
# Check pod status
kubectl get pods -n scout

# Check pod logs
kubectl logs -n scout deployment/scout-backend

# Describe pod for events
kubectl describe pod -n scout <pod-name>
```

#### 2. Image Pull Errors

If using a private registry:
```bash
# Create image pull secret
kubectl create secret docker-registry regcred \
  --docker-server=your-registry.com \
  --docker-username=your-username \
  --docker-password=your-password \
  -n scout

# Add to deployment specs
spec:
  template:
    spec:
      imagePullSecrets:
      - name: regcred
```

#### 3. Ingress Not Working

```bash
# Check ingress controller
kubectl get pods -n ingress-nginx

# Check ingress status
kubectl get ingress -n scout

# Check ingress controller logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

#### 4. Redis Connection Issues

```bash
# Test Redis connectivity
kubectl exec -it -n scout deployment/scout-redis -- redis-cli ping

# Check Redis logs
kubectl logs -n scout deployment/scout-redis
```

#### 5. HPA Not Scaling

```bash
# Check metrics server
kubectl get pods -n kube-system | grep metrics-server

# Check HPA status
kubectl get hpa -n scout

# Describe HPA for details
kubectl describe hpa scout-backend-hpa -n scout
```

### Useful Commands

```bash
# View all resources
kubectl get all -n scout

# Follow backend logs
kubectl logs -f -n scout -l app.kubernetes.io/component=backend

# Execute into backend pod
kubectl exec -it -n scout deployment/scout-backend -- /bin/bash

# Port forward all services
kubectl port-forward -n scout svc/scout-nginx 8080:80 &
kubectl port-forward -n scout svc/scout-prometheus 9090:9090 &

# Scale deployments
kubectl scale deployment scout-backend --replicas=3 -n scout

# Update configuration
kubectl edit configmap scout-config -n scout

# Restart deployments
kubectl rollout restart deployment/scout-backend -n scout
```

## 🧹 Cleanup

### Remove Scout from Kubernetes

```bash
# Remove the entire deployment
./k8s/cleanup.sh
```

### Remove kind cluster (if using local development)

```bash
# Delete the entire cluster
kind delete cluster --name scout-cluster
```

## 🔄 Updates and Maintenance

### Updating Images

```bash
# 1. Build new images
./k8s/build-images.sh

# 2. Load into kind (for local development)
kind load docker-image scout-backend:latest --name scout-cluster
kind load docker-image scout-frontend:latest --name scout-cluster

# 3. Restart deployments to pick up new images
kubectl rollout restart deployment/scout-backend -n scout
kubectl rollout restart deployment/scout-frontend -n scout
```

### Updating Configuration

```bash
# Edit ConfigMap
kubectl edit configmap scout-config -n scout

# Edit Secret
kubectl edit secret scout-secrets -n scout

# Restart affected deployments
kubectl rollout restart deployment/scout-backend -n scout
```

## 🎯 Production Considerations

### Security

- **RBAC**: Prometheus has proper RBAC permissions
- **Secrets**: Sensitive data stored in Kubernetes secrets
- **Network Policies**: Consider adding NetworkPolicies for pod-to-pod communication
- **Pod Security Standards**: Consider implementing Pod Security Standards

### High Availability

- **Multiple Replicas**: All services run with 2+ replicas
- **Anti-affinity**: Consider adding pod anti-affinity for better distribution
- **Persistent Storage**: Redis and Prometheus use persistent volumes
- **Health Checks**: All services have liveness and readiness probes

### Monitoring and Observability

- **Prometheus**: Comprehensive metrics collection
- **Logging**: Consider adding a centralized logging solution (ELK, Fluentd)
- **Tracing**: Consider adding distributed tracing (Jaeger, Zipkin)
- **Alerting**: Set up Prometheus alerting rules

### Backup and Recovery

- **Redis Data**: Backup Redis data regularly
- **Prometheus Data**: Backup Prometheus data regularly
- **Configuration**: Version control all configuration changes
- **Disaster Recovery**: Test recovery procedures regularly

## 🤝 Contributing

When adding new Kubernetes resources:

1. Follow the existing naming conventions
2. Add appropriate labels and annotations
3. Include resource limits and health checks
4. Update this README with any new configuration options
5. Test on a local cluster (kind/minikube) before submitting

## 📚 Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [kind Documentation](https://kind.sigs.k8s.io/)
- [Nginx Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- [Prometheus Operator](https://prometheus-operator.dev/)
- [Horizontal Pod Autoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)

## ✅ Verified Working

This deployment has been tested and verified to work with:

- ✅ **kind** (local development)
- ✅ **Docker Desktop Kubernetes**
- ✅ **Production Kubernetes clusters**
- ✅ **Auto-scaling** (HPA)
- ✅ **Persistent storage** (Redis, Prometheus)
- ✅ **Monitoring** (Prometheus with service discovery)
- ✅ **Health checks** (all services)
- ✅ **Resource management** (CPU/memory limits)
- ✅ **Security** (RBAC, secrets) 