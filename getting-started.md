# Getting Started with Scout

This guide will walk you through the process of setting up and running Scout on your local machine or server. Scout is designed for easy deployment using Docker and Docker Compose.

## Prerequisites

Before you begin, ensure you have the following installed:

* **Docker**: Scout runs in Docker containers. Download and install Docker Desktop for your operating system from [Docker's official website](https://www.docker.com/get-started).
* **Docker Compose**: This tool is used to define and run multi-container Docker applications. Docker Compose is typically included with Docker Desktop. If not, follow the installation instructions [here](https://docs.docker.com/compose/install/).
* **Git**: You'll need Git to clone the Scout repository. Download it from [git-scm.com](https://git-scm.com/).

## Installation

1.  **Clone the Scout Repository:**\
    Open your terminal or command prompt and navigate to the directory where you want to install Scout. Then, clone the official repository:

    ```bash
    git clone https://github.com/scout-io/scout.git
    cd scout
    ```
2.  **Review Configuration (Optional but Recommended):**\
    Scout comes with default configurations that work out-of-the-box for local development. The main configuration files are:

    * `docker-compose.yml`: Defines the services (backend, frontend, Redis, Nginx, Prometheus).
    * `backend/config.json`: Contains settings for the backend API, such as API protection, token, and model behavior defaults.

    For production deployments or if you need to customize settings (e.g., use an external Redis instance, change ports, set a persistent auth token), you can:

    * **Modify `docker-compose.yml` directly** (e.g., to change exposed ports or mount volumes).
    *   **Create a `.env` file** in the root `scout` directory. This file can override environment variables used in `docker-compose.yml` and certain settings in `backend/config.json`.

        Example `.env` file:

        ```env
        # Backend API settings (these will update backend/config.json on startup)
        # SCOUT_PROTECTED_API=true
        # SCOUT_AUTH_TOKEN=your_very_secure_auth_token_here
        # SCOUT_TRAIL_TIME_WINDOW_MINUTES=120 

        # Docker Compose Redis settings
        # REDIS_HOST=your_external_redis_host.com
        # REDIS_PORT=6379

        # Change frontend/backend exposed ports (also update nginx/default.conf if changing backend)
        # FRONTEND_PORT=3001
        # BACKEND_PORT=8001 
        ```

        Refer to the comments within `docker-compose.yml` and the structure of `backend/config.json` for more variables you can set.

## Running Scout

Once you have cloned the repository and (optionally) configured your environment:

1.  **Build and Start the Services:**\
    Navigate to the root `scout` directory in your terminal and run:

    ```bash
    docker-compose up --build -d
    ```

    * `--build`: This flag tells Docker Compose to build the images before starting the containers (e.g., if you've made changes to the Dockerfiles or it's the first run).
    * `-d`: This flag runs the containers in detached mode, meaning they run in the background.

    The first time you run this, Docker Compose will download necessary base images and build the Scout frontend and backend images. This might take a few minutes.
2. **Accessing Scout:**\
   After the containers have started successfully, you can access the different parts of Scout:
   * **Scout UI (Frontend):** Open your web browser and go to `http://localhost:3000` (or `http://localhost:YOUR_FRONTEND_PORT` if you changed it).
   * **Scout API (Backend):** The API service will be running at `http://localhost:8000` (or `http://localhost:YOUR_BACKEND_PORT`). The UI interacts with this API. You can also directly interact with it using tools like `curl` or Postman.
   * **Prometheus Metrics:** View metrics collected by Prometheus by navigating to `http://localhost:9090`.
   * **Redis Commander (Optional Redis GUI):** The `docker-compose.yml` includes a commented-out service for `redis-commander`. If you uncomment it, you can access a Redis GUI at `http://localhost:8081`.
3.  **Checking Logs:**\
    To view the logs from all running containers:

    ```bash
    docker-compose logs -f
    ```

    To view logs for a specific service (e.g., the backend):

    ```bash
    docker-compose logs -f backend
    ```

    The Scout UI also provides a live log streaming feature from the backend.
4.  **Stopping Scout:**\
    To stop all Scout services, navigate to the root `scout` directory and run:

    ```bash
    docker-compose down
    ```

    If you want to remove the volumes (which store Redis data if you're using the default setup), you can add the `-v` flag:

    ```bash
    docker-compose down -v
    ```

## Next Steps

Now that Scout is running, you can proceed to:

* [Using the Scout UI](using-the-scout-ui.md) to create your first Test.
* Explore the [API Reference](api-reference.md) for programmatic control.
* Dive into [Core Concepts](docs/core-concepts.md) for a deeper understanding.
