# Using the Scout UI

Scout comes with an integrated web interface (UI) built with React, providing a user-friendly way to manage and monitor your Tests. This guide will walk you through the main sections and functionalities of the Scout UI.

*(Note: As the UI evolves, some visual details or layouts might change. This guide focuses on the core functionalities accessible through the interface.)*

Assuming Scout is running (see [Getting Started](getting-started.md)), you can typically access the UI by navigating to `http://localhost:3000` in your web browser.

## Dashboard Overview

Upon logging in or accessing the main page, you are typically greeted by a dashboard. This area provides a high-level overview of your Scout instance and active Tests.

**Key information and actions on the Dashboard include:**

*   **List of Active Tests:** A summary table or list displaying all current Tests.
    *   For each Test, common details shown include its name, creation date, number of variants, and potentially top-level performance indicators (e.g., total predictions, total updates).
*   **Create New Test Button:** A prominent button or link to navigate to the Test creation form.
*   **System Status Indicators:** Basic health indicators for connected services like Redis.
*   **Navigation Menu:** Links to other sections of the UI, such as Admin Controls, Log Viewer, and documentation.

<p align="center">
  <em>(TODO: Add a screenshot of the main dashboard if available)</em>
</p>

## Creating a New Test

One of the primary functions of the UI is to facilitate the creation of new Tests.

**Steps to create a new Test typically involve:**

1.  Navigate to the "Create Test" or "New Test" section (often from the dashboard).
2.  Fill out a form with the following details:
    *   **Test Name:** A descriptive name for your Test (e.g., `HomePageHeroButtonTest`, `ArticleRecommendationStrategy`). This name is for your reference.
    *   **Variants:** Define the different options you want to test.
        *   You will usually be able to add multiple variants.
        *   For each variant, you will provide a **Label** (e.g., "Red Button", "Learn More Link", "Algorithm V2"). Scout will assign an internal ID to each variant (typically starting from 0).
    *   The UI may provide options or guidance on setting up Tests that utilize contextual data.
3.  Submit the form.

Upon successful creation, Scout will:
*   Register the new Test with the backend.
*   Assign it a unique `cb_model_id` (Test ID).
*   The new Test will appear in your list of active Tests on the dashboard.

<p align="center">
  <em>(TODO: Add a screenshot of the test creation form if available)</em>
</p>

## Managing Existing Tests

Once Tests are created, you can manage them through the UI.

**Actions available for existing Tests include (usually by selecting a Test from the dashboard list):**

*   **View Details / Performance:** Clicking on a Test name or a "details" button will take you to a dedicated page for that Test (see next section).
*   **Delete Test:** An option to permanently delete a Test and all its associated data. This action is usually irreversible and should be used with caution.
    *   Corresponds to the `POST /api/delete_model/{cb_model_id}` API endpoint.
*   **Rollout Global Variant (Override):** For a specific Test, the UI may allow you to temporarily or permanently force all recommendations to a single, specific variant. This is useful for fully rolling out a winner or for incident management.
    *   Corresponds to `POST /api/rollout_global_variant/{cb_model_id}`.
*   **Clear Global Variant Rollout:** If a global variant rollout is active, an option to clear it and return to normal Test operation.
    *   Corresponds to `POST /api/clear_global_variant/{cb_model_id}`.

## Viewing Test Performance & Details

Selecting a specific Test provides detailed insights into its operation and performance.

**Information and visualizations you can find on a Test detail page:**

*   **Test Information:** Name, `cb_model_id`, creation date, list of variants (ID and label).
*   **Performance Metrics (often with charts):**
    *   **Reward Trends:** Average reward over time for each variant and overall.
    *   **Variant Performance:** Cumulative rewards, number of times each variant was chosen (predictions), number of updates received.
    *   **Prediction Ratios:** The proportion of times each variant has been recommended.
    *   **Contextual Feature Insights:** (For Tests using context, if available) Information about how contextual features might be influencing decisions.
*   **Recent Activity/Trail:** A log or table showing recent prediction requests and updates for this specific Test (timestamps, chosen variants, rewards, context snippets if applicable).
*   **Configuration Details:** Information about the Test's configuration (though deep configuration of the underlying statistical methods might be limited via the UI, which typically favors robust defaults).

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
    *   View current system configuration (`GET /admin/system_config`), Test defaults (`GET /admin/model_config`), and Redis settings (`GET /admin/redis_health` might show connection status; `GET /admin/system_config` may include some Redis parameters).
    *   Possibly edit some of these configurations (`POST /admin/model_config`, `POST /admin/system_config`, `POST /admin/redis_config`).
*   **Redis Health Check:** An indicator or button to check the connectivity and health of the Redis instance (`GET /admin/redis_health`).

<p align="center">
  <em>(TODO: Add a screenshot of the admin controls section if available)</em>
</p>

## Log Viewer

Scout includes a real-time log streaming feature in the UI.

*   **Live Log Stream:** Displays logs from the backend application as they happen.
    *   Corresponds to the `GET /logs/stream` API endpoint.
*   **Filtering/Search (Optional):** The UI might offer basic filtering or search capabilities for the logs.

This is extremely useful for debugging, monitoring requests in real-time, and understanding system behavior without needing to access server-side container logs directly.

By familiarizing yourself with these sections, you can effectively leverage the Scout UI to manage your Tests and gain valuable insights into their performance. 