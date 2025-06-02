# API Reference

Scout exposes a RESTful API for all its operations. This allows for programmatic control over Test creation, management, recommendations, and system administration.

The base URL for the API is typically `http://localhost:8000` when running locally with default Docker Compose settings.

## Authentication

API endpoints can be protected. If API protection is enabled (via Admin controls or `SCOUT_PROTECTED_API` env var), requests to protected endpoints must include an `Authorization` header with a Bearer token.

`Authorization: Bearer YOUR_AUTH_TOKEN`

You can generate an auth token via the Admin UI or the `POST /admin/generate_token` endpoint.

Endpoints that require authentication are marked with **(Protected)**.

## Admin Endpoints

These endpoints are for managing the Scout system itself.

### Get Protection Status

*   **GET** `/admin/get_protection`
*   **Description:** Checks if API protection is currently enabled.
*   **Response:**
    ```json
    {
      "protected_api": true_or_false
    }
    ```

### Set Protection Status

*   **POST** `/admin/set_protection`
*   **Description:** Enables or disables API protection.
*   **Request Body:**
    ```json
    {
      "protected_api": true 
    }
    ```
*   **Response:**
    ```json
    {
      "message": "API protection status updated",
      "protected_api": true_or_false
    }
    ```

### Generate Authentication Token

*   **POST** `/admin/generate_token`
*   **Description:** Generates a new authentication token. If API protection is enabled, this token will be required for protected endpoints. The current token (if one exists) will be invalidated/replaced.
*   **Response:**
    ```json
    {
      "auth_token": "your_new_long_secure_token"
    }
    ```

### Check Redis Health

*   **GET** `/admin/redis_health`
*   **Description:** Checks the connection to Redis and provides some basic stats.
*   **Response:**
    ```json
    {
      "redis_is_connected": true_or_false,
      "redis_total_keys": 123, // Example
      "error_message": "optional message if not connected"
    }
    ```

### Get Test Default Configuration

*   **GET** `/admin/model_config`
*   **Description:** Retrieves the default configuration settings for new Tests.
*   **Response (example values):**
    ```json
    {
      "trail_time_window_minutes": 60,
      "trail_bucket_granularity_seconds": 60,
      "minimum_update_requests": 10
    }
    ```

### Update Test Default Configuration

*   **POST** `/admin/model_config`
*   **Description:** Updates the default configuration settings for new Tests.
*   **Request Body:**
    ```json
    {
      "time_window_minutes": 120,
      "bucket_granularity_seconds": 30,
      "min_update_requests": 5
    }
    ```
*   **Response:**
    ```json
    {
      "message": "Test default config updated successfully",
      "config": {
        "trail_time_window_minutes": 120,
        "trail_bucket_granularity_seconds": 30,
        "minimum_update_requests": 5
      }
    }
    ```

### Get System Configuration

*   **GET** `/admin/system_config`
*   **Description:** Retrieves general system configuration settings.
*   **Response (example values):**
    ```json
    {
      "host": "127.0.0.1",
      "port": 8000,
      "debug": false,
      "protected_api": true,
      "auth_token": "current_masked_or_null_token", // For security, actual token may not be shown
      "trail_time_window_minutes": 60, // Part of global config, also default for new Tests
      "trail_bucket_granularity_seconds": 60, // Part of global config, also default for new Tests
      "minimum_update_requests": 10 // Part of global config, also default for new Tests
    }
    ```

### Update System Configuration

*   **POST** `/admin/system_config`
*   **Description:** Updates general system configuration settings. Restart might be needed for some changes (e.g., host/port).
*   **Request Body:**
    ```json
    {
      "host": "0.0.0.0",
      "port": 8080,
      "debug": true
    }
    ```
*   **Response:**
    ```json
    {
      "message": "System config updated successfully. Restart may be required for some changes.",
      "config": { ... updated config ... }
    }
    ```

### Update Redis Configuration (Live)

*   **POST** `/admin/redis_config`
*   **Description:** Updates Redis connection parameters (host, port) and context Time-To-Live (TTL) live. Note that changing these for an active system could disrupt operations if the new Redis is not a mirror or if context TTL changes drastically.
*   **Request Body:**
    ```json
    {
      "host": "new_redis_host",
      "port": 6380,
      "ttl": 72000 // New context TTL in seconds
    }
    ```
*   **Response:**
    ```json
    {
      "message": "Redis config updated. Connection re-established.",
      "redis_host": "new_redis_host",
      "redis_port": 6380,
      "redis_context_ttl": 72000
    }
    ```
    *(Or an error message if connection to new Redis fails)*

## Test Endpoints

These endpoints are for creating, managing, and interacting with Tests.

### Create Test

*   **POST** `/api/create_model` **(Protected)**
*   **Description:** Creates a new Test.
*   **Request Body (`CreateModelRequest`):**
    ```json
    {
      "name": "My New Test Name",
      "variants": {
        "0": "Variant A Label", // Key is integer variant ID, value is string/int label
        "1": "Variant B Label",
        "2": "Variant C Label"
      }
    }
    ```
*   **Response:**
    ```json
    {
      "message": "Test created successfully",
      "cb_model_id": "unique_test_identifier_string", // This is the Test ID
      "name": "My New Test Name",
      "variants": {
        "0": "Variant A Label",
        "1": "Variant B Label",
        "2": "Variant C Label"
      }
    }
    ```

### Delete Test

*   **POST** `/api/delete_model/{cb_model_id}` **(Protected)**
*   **Description:** Deletes a Test and all its associated data.
*   **Path Parameter:**
    *   `cb_model_id` (string): The ID of the Test to delete.
*   **Response:**
    ```json
    {
      "message": "Test cb_model_id successfully deleted.",
      "cb_model_id": "unique_test_identifier_string"
    }
    ```
    *(Or a 404 if Test not found)*

### List Tests

*   **GET** `/api/models`
*   **Description:** Retrieves a list of all active Tests with summary information.
*   **Response (Array of Test summaries):**
    ```json
    [
      {
        "cb_model_id": "id1", // Test ID
        "name": "Test Alpha",
        "num_variants": 2,
        "total_predictions": 1500,
        "total_updates": 700,
        "created_at": "timestamp",
        "last_prediction_at": "timestamp_or_null",
        "last_update_at": "timestamp_or_null",
        "is_active": true,
        "global_variant_rollout": null_or_variant_id
      },
      { ... another Test ... }
    ]
    ```

### Get Test Details

*   **GET** `/api/model_details/{cb_model_id}`
*   **Description:** Retrieves detailed information and performance metrics for a specific Test.
*   **Path Parameter:**
    *   `cb_model_id` (string): The ID of the Test.
*   **Response (example, structure may vary with details):**
    ```json
    {
      "cb_model_id": "id1",
      "name": "Test Alpha",
      "variants": {"0": "Option X", "1": "Option Y"},
      "created_at": "timestamp",
      "last_prediction_at": "timestamp_or_null",
      "last_update_at": "timestamp_or_null",
      "is_active": true,
      "global_variant_rollout": null_or_variant_id,
      "total_predictions": 1500,
      "total_updates": 700,
      "minimum_update_requests_for_stats": 10, 
      "performance_summary": {
        "0": { "predictions": 750, "updates": 350, "reward_sum": 150, "average_reward": 0.42, "current_prediction_ratio": 0.5 },
        "1": { "predictions": 750, "updates": 350, "reward_sum": 180, "average_reward": 0.51, "current_prediction_ratio": 0.5 }
      },
      "prediction_trail": [ { "timestamp": "ts", "variant_id": 0, "context_keys": ["user_type"] }, ... ],
      "update_trail": [ { "timestamp": "ts", "variant_id": 1, "reward": 1, "context_keys": [] }, ... ],
      "context_feature_analysis": { /* if contextual, potential analysis here */ },
      "exploitation_exploration_ratio": { /* data */ }
    }
    ```
    *(Or a 404 if Test not found)*

### Update Test (Report Rewards)

*   **POST** `/api/update_model/{cb_model_id}` **(Protected)**
*   **Description:** Updates a Test with new reward data. This is how the Test learns.
*   **Path Parameter:**
    *   `cb_model_id` (string): The ID of the Test to update.
*   **Request Body (`UpdateModelRequest`):**
    ```json
    {
      "updates": [
        {
          "request_id": "unique_id_from_fetch_if_context_was_used", // Optional, but crucial if context_used_for_prediction is true
          "variant_id": 0, // The ID of the variant that was shown
          "reward": 1.0,   // The observed reward (numeric)
          "context": {"feature1": "value1"}, // Optional: Provide context directly if not relying on request_id lookup
          "context_used_for_prediction": true // Set to true if context stored via request_id should be used.
                                              // If false, or request_id is null, inline context (if provided) will be used.
        },
        { ... more updates ... }
      ]
    }
    ```
*   **Response:**
    ```json
    {
      "message": "Test updated successfully with X records (Y failures).",
      "cb_model_id": "id1",
      "processed_updates": X,
      "failed_updates": Y 
    }
    ```

### Fetch Recommended Variant

*   **POST** `/api/fetch_recommended_variant` **(Protected)**
*   **Description:** Fetches a recommended variant from the specified Test. Optionally stores context for the decision if `request_id` is provided.
*   **Request Body (`FetchActionRequest`):**
    ```json
    {
      "cb_model_id": "id1",
      "context": { // Optional: context features for the decision
        "user_segment": "premium",
        "device": "mobile"
      },
      "request_id": "your_unique_request_identifier" // Optional: If provided, context is stored against this ID for later update.
    }
    ```
*   **Response:**
    ```json
    {
      "cb_model_id": "id1",
      "variant_id": 1, // The ID of the chosen variant
      "variant_label": "Variant B Label", // The label of the chosen variant
      "request_id": "your_unique_request_identifier_if_provided",
      "is_global_rollout": false // True if this decision was due to a global variant rollout
    }
    ```

### Rollout Global Variant

*   **POST** `/api/rollout_global_variant/{cb_model_id}` **(Protected)**
*   **Description:** Forces all future recommendations from this Test to be a specific variant, overriding the bandit logic.
*   **Path Parameter:**
    *   `cb_model_id` (string): The ID of the Test.
*   **Request Body (`RolloutGlobalVariantRequest`):**
    ```json
    {
      "variant": 0 // The integer ID of the variant to roll out globally
                   // Or the string label of the variant, e.g., "Variant A Label"
    }
    ```
*   **Response:**
    ```json
    {
      "message": "Global variant rollout for Test id1 set to variant X.",
      "cb_model_id": "id1",
      "global_variant_id": 0,
      "global_variant_label": "Variant A Label"
    }
    ```

### Clear Global Variant Rollout

*   **POST** `/api/clear_global_variant/{cb_model_id}` **(Protected)**
*   **Description:** Clears any active global variant rollout for the Test, returning it to normal bandit operation.
*   **Path Parameter:**
    *   `cb_model_id` (string): The ID of the Test.
*   **Response:**
    ```json
    {
      "message": "Global variant rollout cleared for Test id1.",
      "cb_model_id": "id1"
    }
    ```

## Log Streaming

### Stream Logs

*   **GET** `/logs/stream`
*   **Description:** Streams application logs in real-time. This is a `StreamingResponse`.
*   **Response Type:** `text/event-stream`
*   **Output:** A stream of Server-Sent Events (SSE), where each event data is a JSON string representing a log entry. Example log entry structure:
    ```json
    {
        "timestamp": "2023-10-27T12:34:56.789Z",
        "level": "INFO",
        "message": "User authentication successful for user_id: 123",
        "service": "backend-app.py:auth_module:25"
        // ... other fields from structured logging if used ...
    }
    ```
    (Actual log format depends on the application's logging configuration.)

## Metrics

### Get Prometheus Metrics

*   **GET** `/metrics`
*   **Description:** Exposes application and Test metrics in Prometheus format.
*   **Response Type:** `text/plain; version=0.0.4; charset=utf-8`
*   **Output:** Standard Prometheus metrics exposition format, including counters, gauges, histograms for things like:
    *   HTTP request counts and latencies (`http_requests_total`, `http_request_duration_seconds`)
    *   Test predictions, updates, rewards (`model_predictions_total`, `model_updates_total`, `model_rewards_total`, `model_reward_average`)
    *   Redis operations (`redis_operations_total`, `redis_operation_duration_seconds`)
    *   Active Test counts (`active_models`)
    *   And more, as defined in `metrics.py`.

This API reference should provide a solid foundation for developers integrating with Scout. 