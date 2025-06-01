# Using the Scout UI

Scout comes with an integrated web interface (UI) built with React, providing a user-friendly way to manage and monitor your self-optimizing AB tests. This guide will walk you through the main sections and functionalities of the Scout UI.

*(Note: As the UI evolves, some visual details or layouts might change. This guide focuses on the core functionalities accessible through the interface.)*

Assuming Scout is running (see [Getting Started](getting-started.md)), you can typically access the UI by navigating to `http://localhost:3000` in your web browser.

## Dashboard Overview

Upon logging in or accessing the main page, you'll usually be greeted by a dashboard. This area provides a high-level overview of your Scout instance and active tests.

**Key information and actions on the Dashboard might include:**

*   **List of Active Tests:** A summary table or cards showing all current self-optimizing tests (bandit models).
    *   For each test, you might see its name, creation date, number of variants, and perhaps some top-level performance indicators (e.g., total predictions, total updates).
*   **Create New Test Button:** A prominent button or link to navigate to the test creation form.
*   **System Status Indicators:** Basic health indicators for connected services like Redis.
*   **Navigation Menu:** Links to other sections of the UI, such as Admin Controls, Log Viewer, and documentation.

<p align="center">
  <em>(TODO: Add a screenshot of the main dashboard if available)</em>
</p>

## Creating a New Test

One of the primary functions of the UI is to allow easy creation of new self-optimizing tests.

**Steps to create a new test typically involve:**

1.  Navigate to the "Create Test" or "New Model" section (often from the dashboard).
2.  Fill out a form with the following details:
    *   **Test Name:** A descriptive name for your test (e.g., `HomePageHeroButtonTest`, `ArticleRecommendationStrategy`). This name is for your reference.
    *   **Variants:** Define the different options you want to test.
        *   You'll usually be able to add multiple variants.
        *   For each variant, you'll provide a **Label** (e.g., "Red Button", "Learn More Link", "Algorithm V2"). Scout will assign an internal ID to each variant (typically starting from 0).
        *   *Contextual vs. Non-Contextual:* While the core model creation API (`/api/create_model`) doesn't explicitly differentiate contextual/non-contextual at creation (it's determined by whether context is sent during `fetch_recommended_variant` and `update_model`), the UI might offer a checkbox or information about how to make a test contextual.
3.  Submit the form.

Upon successful creation, Scout will:
*   Register the new bandit model with the backend.
*   Assign it a unique `cb_model_id` (Contextual Bandit Model ID).
*   The new test will appear in your list of active tests on the dashboard.

<p align="center">
  <em>(TODO: Add a screenshot of the test creation form if available)</em>
</p>

## Managing Existing Tests

Once tests are created, you can manage them through the UI.

**Actions available for existing tests (usually by selecting a test from the dashboard list):**

*   **View Details / Performance:** Clicking on a test name or a "details" button will take you to a dedicated page for that test (see next section).
*   **Delete Test:** An option to permanently delete a test and all its associated data. This action is usually irreversible and should be used with caution.
    *   Corresponds to the `POST /api/delete_model/{cb_model_id}` API endpoint.
*   **Rollout Global Variant (Override):** For a specific test, you might have an option to temporarily or permanently force all recommendations to be a single, specific variant. This is useful for fully rolling out a winner or for incident management.
    *   Corresponds to `POST /api/rollout_global_variant/{cb_model_id}`.
*   **Clear Global Variant Rollout:** If a global variant rollout is active, an option to clear it and return to normal bandit operation.
    *   Corresponds to `POST /api/clear_global_variant/{cb_model_id}`.
*   *(Possibly Deactivate/Activate: While the backend `WrappedMAB` has a `deactivate()` method, a direct API endpoint for this isn't obvious from `app.py` other than full deletion. If this feature exists in the UI, it would likely pause predictions and updates for a model without deleting it.)*

## Viewing Test Performance & Details

Drilling into a specific test provides detailed insights into its operation and performance.

**Information and visualizations you might find on a test detail page:**

*   **Test Information:** Name, `cb_model_id`, creation date, list of variants (ID and label).
*   **Performance Metrics (often with charts):**
    *   **Reward Trends:** Average reward over time for each variant and overall.
    *   **Variant Performance:** Cumulative rewards, number of times each variant was chosen (predictions), number of updates received.
    *   **Prediction Ratios:** The proportion of times each variant has been recommended by the bandit.
    *   **Exploitation vs. Exploration Ratio:** (If calculated and exposed) A metric indicating how much the bandit is exploiting known good variants versus exploring less certain ones.
    *   **Contextual Feature Importance:** (For contextual bandits, if available) Insights into which contextual features are most influential in the model's decisions.
*   **Recent Activity/Trail:** A log or table showing recent prediction requests and updates for this specific model (timestamps, chosen variants, rewards, context snippets if applicable).
*   **Configuration Details:** Information about the model's learning policy or other parameters (though deep configuration of the bandit algorithm itself might be limited via UI, favoring sensible defaults).

<p align="center">
  <em>(TODO: Add a screenshot of a test detail/performance page if available)</em>
</p>

## Admin Controls

The Admin section of the UI allows for managing system-wide settings and security.

**Key functionalities in the Admin Controls area:**

*   **API Protection:**
    *   View current status (whether API protection is enabled or disabled).
    *   Toggle API protection on/off (`POST /admin/set_protection`).
*   **Authentication Token:**
    *   Generate a new authentication token (`POST /admin/generate_token`). The new token will be displayed for you to copy and use in your API requests if protection is enabled.
    *   (Note: The UI might not display the *current* token for security reasons after its initial generation, only allow generating a new one).
*   **Configuration Viewer/Editor:**
    *   View current system configuration (`GET /admin/system_config`), model defaults (`GET /admin/model_config`), and Redis settings (`GET /admin/redis_health` might show connection status, `GET /admin/system_config` might include some Redis params like TTL from `config.json`).
    *   Possibly edit some of these configurations (`POST /admin/model_config`, `POST /admin/system_config`, `POST /admin/redis_config`).
*   **Redis Health Check:** An indicator or button to check the connectivity and health of the Redis instance (`GET /admin/redis_health`).

<p align="center">
  <em>(TODO: Add a screenshot of the admin controls section if available)</em>
</p>

## Log Viewer

Scout often includes a real-time log streaming feature in the UI.

*   **Live Log Stream:** Displays logs from the backend application as they happen.
    *   Corresponds to the `GET /logs/stream` API endpoint.
*   **Filtering/Search (Optional):** The UI might offer basic filtering or search capabilities for the logs.

This is extremely useful for debugging, monitoring requests in real-time, and understanding system behavior without needing to access server-side container logs directly.

By familiarizing yourself with these sections, you can effectively leverage the Scout UI to manage your self-optimizing AB tests and gain valuable insights into their performance. 