# Advanced Usage

This section covers more nuanced aspects of configuring and interpreting Tests in Scout. While Scout aims to simplify dynamic optimization, a deeper understanding of certain concepts can help you design more effective Tests and analyze their performance more thoroughly.

## Understanding Test Behavior: Exploration vs. Exploitation

Scout's Tests are designed to automatically balance two key activities:

*   **Exploitation:** Showing the variant that, based on current data, appears to be the best performer to maximize immediate positive outcomes.
*   **Exploration:** Showing other, less-certain variants to gather more data. This is crucial for discovering if a variant that initially looked suboptimal might actually be better in the long run, or under specific conditions.

**How Scout Manages This:**

Scout employs statistical algorithms (often from the family of multi-armed bandits) that inherently manage this trade-off. You don't typically need to configure the specific algorithm, as Scout uses robust defaults suitable for common scenarios (e.g., methods like LinUCB for Tests with context and Thompson Sampling for non-contextual Tests).

**What to Expect:**

*   **Initial Fluctuation:** When a Test first starts, especially with little data, the proportion of users seeing each variant might change frequently as the system explores.
*   **Gradual Convergence:** As more data (rewards) are collected, Scout will increasingly favor (exploit) the variants that consistently show better performance. However, it will usually continue some minimal exploration to remain adaptable.
*   **Contextual Adaptation:** If you are using context, Scout learns the best variant *for each context*. This means a variant might be heavily favored for one user segment but rarely shown to another.

Understanding this balance is key to interpreting Test results. Early on, focus on data collection. Over time, look for trends where Scout consistently allocates more users to specific variants.

## Working with Contextual Features

Using context allows Scout to personalize decisions. The effectiveness of these contextual Tests depends heavily on the quality and relevance of the contextual features you provide.

**Choosing Good Contextual Features:**

*   **Relevance:** Select features that you believe will genuinely influence which variant is optimal for a user. Irrelevant features can add noise and make it harder for the system to learn.
    *   *Good examples:* User segment (e.g., `new`, `returning`), device type (`mobile`, `desktop`), user's geographical region, subscription tier.
    *   *Consider carefully:* Features with extremely high numbers of unique values (e.g., raw user IDs, precise timestamps) might be too granular unless aggregated or transformed.
*   **Availability:** Ensure the features you choose are readily available in your application at the moment you need to request a variant from Scout.
*   **Data Types:** Scout's backend handles common data types for context values (strings, numbers, booleans). It automatically encodes these for the underlying models.
    *   For example, if you send `{"country": "US"}` for one request and `{"country": "CA"}` for another, Scout treats `country` as a categorical feature and learns distinct effects for "US" and "CA".

**Tips for Using Context:**

*   **Start Simple:** Begin with a few, high-impact contextual features. You can refine and add more as you learn.
*   **Consistency:** Use consistent key names and data types for your context features across requests.
*   **Monitor Performance:** Observe if providing context leads to different variants being favored for different contextual segments. The Scout UI and API can provide data to help with this analysis.

## Monitoring Test Performance

Scout provides several ways to monitor the performance of your Tests, both through its API (primarily the `/api/model_details/{cb_model_id}` endpoint) and by exposing metrics for systems like Prometheus (via the `/metrics` endpoint).

**Key Information from Model Details (API):**

The `/api/model_details/{cb_model_id}` endpoint provides a snapshot of a Test's status, including:

*   **Overall Activity:** `total_predictions` (how many times Scout recommended a variant) and `total_updates` (how many times reward feedback was received).
*   **Performance per Variant:**
    *   `predictions`: The number of times each specific variant was recommended.
    *   `updates`: The number of reward updates received for each variant.
    *   `reward_sum` and `average_reward`: These are critical for understanding the raw performance of each variant. A higher average reward generally indicates better performance.
    *   `current_prediction_ratio`: The proportion of recent recommendations for this variant, indicating how Scout is currently prioritizing it.
*   **Data Trails:** Recent prediction and update records, useful for debugging or detailed inspection (`prediction_trail`, `update_trail`).
*   **Context Insights (if applicable):** Some information about how context features might be influencing decisions.

**Interpreting Test Performance Data:**

*   **Average Reward:** Compare the average reward across your variants. This is a primary indicator of which variants are more effective according to your defined reward metric.
*   **Prediction Ratios:** Observe how the `current_prediction_ratio` for variants changes over time. As Scout learns, variants with higher average rewards should generally receive higher prediction ratios.
*   **Number of Updates:** Ensure all variants are receiving a reasonable number of updates. If a variant has very few updates, its average reward might not yet be a reliable indicator of its true performance.
*   **Statistical Confidence:** While Scout dynamically optimizes, if you need to make a definitive statement about whether one variant is statistically significantly better than another, you may need to apply traditional statistical tests (e.g., t-tests, chi-squared tests) to the accumulated data (rewards and number of updates per variant). Scout provides the raw data; such statistical analysis is typically performed externally.

**Leveraging Prometheus Metrics:**

If you have Prometheus integrated, Scout exposes a rich set of metrics via its `/metrics` endpoint, including:

*   **API Health:** `http_requests_total` (by method, endpoint, status code), `http_request_duration_seconds` (latency).
*   **Test-Specific Metrics:**
    *   `model_predictions_total{model_id, variant_id}`: Total predictions for each variant of each Test.
    *   `model_updates_total{model_id, variant_id}`: Total reward updates for each variant.
    *   `model_rewards_total{model_id, variant_id}`: Sum of rewards for each variant.
    *   `model_reward_average{model_id, variant_id}`: A gauge representing the recent average reward for each variant.
*   **System Metrics:** `active_models`, Redis operation counts, etc.

**Using Prometheus for Enhanced Monitoring:**

*   **Dashboards (e.g., with Grafana):** Visualize key metrics over time. Track API error rates, request latencies, average rewards per variant for important Tests, and the flow of predictions and updates.
*   **Alerting:** Configure alerts for critical conditions, such as:
    *   High API error rates or latency.
    *   No reward updates being received for an active Test for an extended period.
    *   Significant, unexpected drops in average reward for a previously well-performing Test.
    *   Issues with dependent services like Redis.

By combining the direct insights from Scout's API with the time-series data and alerting capabilities of Prometheus, you can maintain a comprehensive view of your Tests' behavior, performance, and overall system health. 