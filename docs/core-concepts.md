# Core Concepts

To effectively use Scout, it's helpful to understand a few core concepts. This page explains the fundamental building blocks of how Scout manages and optimizes your Tests.

## What is a Test?

A **Test** (also referred to as a model or `cb_model_id` in the API) represents a single experiment you are running. For example:

*   Testing different headlines for a webpage.
*   Comparing various call-to-action button texts.
*   Evaluating different promotional offers.

Each Test you create in Scout operates independently and learns from the data specific to it.

## Variants

**Variants** are the different options you are testing within a single Test. 

*   If you're testing headlines, your variants might be: "Get Started Today", "Sign Up and Save", "Explore Our Features".
*   If you're testing button colors, variants could be: "Blue Button", "Green Button", "Orange Button".

Scout's goal is to determine which of these variants performs best according to the metrics you define.

## Context

**Context** refers to situational information that might influence which variant is most effective. You can provide Scout with contextual data as key-value pairs when you request a variant. Examples include:

*   `{"user_segment": "new", "device_type": "mobile"}`
*   `{"region": "emea", "language": "fr"}`
*   `{"time_of_day": "evening", "product_category": "electronics"}`

If context is provided, Scout can learn to make personalized decisions, choosing the best variant not just overall, but for specific contexts. For instance, "Variant A" might be optimal for mobile users, while "Variant B" is better for desktop users.

## Metrics & Rewards

To determine how well variants are performing, Scout needs feedback in the form of **rewards**. A **reward** is a numerical value you send to Scout that indicates the outcome after a user has been exposed to a variant.

*   **Higher rewards should indicate better outcomes.** For example, a click could be a reward of `1`, while no click could be `0`.
*   If you're optimizing for revenue, the reward could be the actual transaction amount.

These rewards are the **metrics** Scout uses to learn. By consistently reporting rewards, you enable Scout to identify which variants lead to the desired results.

## Request ID (`request_id`)

A **`request_id`** is a unique identifier that your application should generate when requesting a variant recommendation from Scout. This ID is crucial for correctly associating the subsequent user action (and its reward) back to the specific recommendation and the context in which it was given.

When you later send a reward update to Scout, you will include this same `request_id`.

## System Architecture Overview

Scout is designed as a set of services that work together, typically run using Docker:

1.  **Your Application**: This is where your code integrates with Scout by calling its API.
2.  **Scout API (Backend)**: The core engine built with FastAPI. It handles:
    *   Creating and managing Tests.
    *   Receiving requests for variants and returning recommendations.
    *   Accepting reward updates to train the Test models.
    *   Storing Test configurations and learning data in Redis.
3.  **Scout UI (Frontend)**: A React-based web interface for:
    *   Creating and managing Tests visually.
    *   Monitoring Test performance.
    *   Administering system settings.
4.  **Redis**: An in-memory data store used for:
    *   Storing active Test models.
    *   Caching contextual information temporarily for linking predictions to updates.
    *   Managing queues and locks for robust operation.
5.  **Nginx**: A web server that serves the Scout UI and acts as a reverse proxy for API requests to the backend.
6.  **Prometheus (Optional Integration)**: Scout exposes a `/metrics` endpoint that Prometheus can scrape for monitoring system health and Test performance.

This architecture allows Scout to be scalable and manageable for production environments.

## Lifecycle of a Test

Here's a typical interaction flow when using Scout:

1.  **Test Creation (via UI or API):**
    *   You define a new Test (e.g., "WebsiteHeadlineTest").
    *   You specify the variants (e.g., "Headline A", "Headline B").
    *   Scout creates a new model instance for this Test and stores it.

2.  **Recommendation Request (Your Application → Scout API):**
    *   A user visits your website where the headline needs to be chosen.
    *   Your application calls the Scout API (`/api/fetch_recommended_variant`) with:
        *   The `cb_model_id` for "WebsiteHeadlineTest".
        *   A unique `request_id` you generate for this event.
        *   (Optional) `context` data (e.g., `{"user_device": "mobile"}`).
    *   Scout's backend selects a variant based on its current learning and returns it to your application.

3.  **Variant Display (Your Application):**
    *   Your application displays the headline variant recommended by Scout to the user.

4.  **Reward Reporting (Your Application → Scout API):**
    *   The user interacts with your website (e.g., clicks a link, spends time on page, makes a purchase).
    *   Your application determines an appropriate reward based on this interaction.
    *   Your application calls the Scout API (`/api/update_model/{cb_model_id}`) with:
        *   The original `request_id`.
        *   The `variant_id` that was shown.
        *   The calculated `reward`.
        *   Indication if context was used in the original prediction, so Scout can link the reward to the correct context.
    *   Scout's backend updates the specified Test model with this new reward data, refining its understanding.

5.  **Continuous Optimization:**
    *   Steps 2-4 repeat for subsequent users.
    *   The Test model continuously learns and adapts, gradually favoring variants that lead to higher rewards, potentially personalizing choices if context is used.

6.  **Monitoring (via UI or API):**
    *   You can monitor the performance of your Tests through the Scout UI or by querying API endpoints.

This lifecycle enables dynamic, real-time optimization, making Scout a powerful tool for continuously improving user experiences. 