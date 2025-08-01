# Scout

<div align="center"><img src="https://github.com/user-attachments/assets/191d481a-ba00-4a13-ba1a-32b2325ff51d" alt="" width="200"></div>

&#x20;                                                   [![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/scout-io/scout) [![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md) [![GitHub stars](https://img.shields.io/github/stars/scout-io/scout.svg?style=social)](https://github.com/scout-io/scout) [![Documentation](https://img.shields.io/badge/docs-GitBook-orange.svg)](https://scout-3.gitbook.io/scout-docs)

<div align="center"><img src="https://github.com/user-attachments/assets/b5a98742-cf7a-43de-abcd-a940228a8078" alt="" width="700"></div>

**Scout** is an open-source tool that empowers developers to run and manage **self-optimizing AB tests**.

Scout provides a user-friendly interface and a straightforward API to create, monitor, and get recommendations from fully autonomous bandit models, allowing your application to learn and adapt in real-time.

***

### Table of Contents

* [Why Scout?](./#why-scout)
* [Features](./#features)
* [Documentation](./#documentation)
* [Getting Started](./#getting-started)
  * [Prerequisites](./#prerequisites)
  * [Installation](./#installation)
  * [Running Scout](./#running-scout)
* [Quick Example](./#quick-example)
* [Contributing](./#contributing)
* [License](./#license)
* [Contact](./#contact)

***

### Why Scout?

Traditional AB testing can be slow and cumbersome. You set up variants, wait for statistical significance, and then manually roll out the winner. Self-optimizing AB tests, powered by multi-armed bandits, offer a more dynamic approach:

* **Faster Optimization**: Bandits start directing more traffic to better-performing variants earlier, maximizing positive outcomes even while the test is running.
* **Contextual Decisions**: Go beyond simple A/B. Scout allows you to use contextual information (e.g., user device, time of day, user segment) to personalize experiences. The best variant might be different for different contexts.
* **Always Learning**: The system continuously learns from new data, adapting to changing user behavior or preferences.
* **Developer-Friendly**: Scout is designed for developers. No deep ML knowledge is required to get started.

Scout makes these advanced techniques accessible, providing the infrastructure and tools to implement them efficiently.

***

### Features

* **Intuitive Test Creation**: Define experiments with multiple variants and optional contextual features through a clean UI or simple API calls.
* **Real-time Dynamic Updates**: Feed user interactions (e.g., clicks, conversions, rewards) back to your models. Scout learns on the fly.
* **Contextual Recommendations**: Fetch the optimal variant for a given user or situation, leveraging the power of contextual bandits.
* **Admin Dashboard**:
  * Secure your API with token-based authentication.
  * Manage and monitor all your active tests.
  * View performance metrics and logs in real-time.
* **Dockerized & Scalable**: Easy to deploy and manage using Docker. Built with FastAPI and Redis for performance.
* **Kubernetes Ready**: Production-ready Kubernetes manifests with auto-scaling, monitoring, and persistent storage.
* **Helm Chart**: Professional Helm chart for easy deployment and customization across environments.
* **Security Hardened**: Network policies, RBAC, pod security standards, and secrets management for production deployments.
* **Prometheus Integration**: Key metrics are exposed for monitoring and alerting. Prometheus is configured to automatically discover and scrape each backend worker.

***

### Documentation

For comprehensive documentation, including tutorials, API references, and advanced topics, please visit our **GitBook documentation site:** [**https://scout-3.gitbook.io/scout-docs**](https://scout-3.gitbook.io/scout-docs).

The `docs` directory in this repository contains the source files for our GitBook.

***

### Getting Started

#### Prerequisites

* [Docker](https://www.docker.com/get-started)
* [Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop)

#### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/scout-io/scout.git
    cd scout
    ```
2.  **Environment Variables (Optional but Recommended for Production):**\
    Scout uses Redis for data storage. By default, it will use a Redis container managed by Docker Compose. For production, you might want to configure external Redis or customize settings. You can create a `.env` file in the root directory to override default environment variables used in `docker-compose.yml` and `backend/config.json`. Refer to these files for available options.

    Example `.env` file:

    ```env
    # backend/config.json overrides
    # SCOUT_PROTECTED_API=true
    # SCOUT_AUTH_TOKEN=your_secure_token_here

    # docker-compose.yml overrides for Redis
    # REDIS_HOST=your_external_redis_host
    # REDIS_PORT=your_external_redis_port
    ```

#### Running Scout

**Local Development (Docker Compose):**

Build and start the application using Docker Compose:

```bash
docker-compose up --build -d
```

The `-d` flag runs the containers in detached mode.

Once the containers are up and running:

* **Scout API** will be available at `http://localhost:8000` (or your configured host/port).
* **Scout UI** will be accessible at `http://localhost:3000` (served by Nginx, which proxies API requests to the backend).
* **Prometheus** UI is available at `http://localhost:9090`. It is configured to automatically discover and scrape all backend containers for their metrics.
* **Logs** can be viewed via `docker-compose logs -f` or through the Scout UI's log streaming feature.

To stop the application:

```bash
docker-compose down
```

**Kubernetes Deployment:**

For production deployment on Kubernetes:

```bash
# Option 1: Manual YAML deployment
./k8s/build-images.sh
./k8s/deploy.sh

# Option 2: Helm chart deployment (recommended)
./helm-chart/deploy.sh

# Access via port-forward
kubectl port-forward -n scout svc/scout-nginx 8080:80
```

See the [Kubernetes deployment guide](k8s/README.md) and [Helm chart documentation](helm-chart/README.md) for detailed instructions, configuration options, and troubleshooting.

**Security**: For production deployments, see our [Security Guide](SECURITY.md) for best practices including network policies, RBAC, and secrets management.

**Deployment**: See our [Deployment Guide](DEPLOYMENT.md) for detailed instructions and troubleshooting.

***

### Quick Example

Here's a conceptual overview of how you might use Scout:

1. **Define a Test:**\
   You want to test two headlines for your landing page: "Headline A" and "Headline B".
   * Via UI: Navigate to "Create Test", name it "LandingPageHeadline", and add "Headline A" and "Headline B" as variants.
   *   Via API:

       ```bash
       curl -X POST http://localhost:8000/api/create_model \
            -H "Content-Type: application/json" \
            -d '{
                  "name": "LandingPageHeadline",
                  "variants": {
                    "0": "Headline A",
                    "1": "Headline B"
                  }
                }'
       # Note the returned cb_model_id
       ```
2.  **Fetch a Recommendation:**\
    When a user visits your landing page:

    *   Via API:

        ```bash
        curl -X POST http://localhost:8000/api/fetch_recommended_variant \
             -H "Content-Type: application/json" \
             -d '{
                   "cb_model_id": "your_cb_model_id_from_step_1",
                   "context": {"user_country": "US"}, # Optional context
                   "request_id": "unique_request_identifier_for_this_user_session"
                 }'
        # Response will give you the chosen variant (e.g., "Headline A") and its ID.
        ```

    Your application then displays the recommended headline to the user. Scout stores the `context` and `request_id` to link this decision to future feedback.
3.  **Update with Feedback:**\
    The user clicks (or doesn't click) on the headline. Let's say a click is a positive reward of `1`.

    *   Via API:

        ```bash
        curl -X POST http://localhost:8000/api/update_model/your_cb_model_id_from_step_1 \
             -H "Content-Type: application/json" \
             -d '{
                   "updates": [
                     {
                       "request_id": "unique_request_identifier_for_this_user_session",
                       "variant_id": 0, # ID of the variant shown (e.g., 0 for "Headline A")
                       "reward": 1,
                       "context_used_for_prediction": true # Important: tells Scout to link to stored context
                     }
                   ]
                 }'
        ```

    Scout updates the "LandingPageHeadline" model. Over time, it will learn which headline (possibly under different contexts) performs better.

***

### Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](broken-reference) and our [Code of Conduct](broken-reference) for details.

***

### License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

***

Project Link: [https://github.com/scout-io/scout](https://github.com/scout-io/scout)
# Trigger workflow
