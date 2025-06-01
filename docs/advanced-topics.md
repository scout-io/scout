# Advanced Topics

This section delves into some of the more nuanced aspects of using Scout and understanding the principles behind self-optimizing AB tests. While Scout is designed to be developer-friendly and abstract away much of the complexity, a deeper understanding can help you design more effective tests and interpret results more accurately.

## Understanding Bandit Algorithms (Conceptual)

Scout uses the `mabwiser` library under the hood, which provides several multi-armed bandit algorithms. While you don't typically choose the algorithm directly via Scout's API (Scout uses sensible defaults like LinUCB for contextual and Thompson Sampling for non-contextual), understanding the general types can be insightful:

*   **Epsilon-Greedy:** A simple yet effective algorithm. Most of the time (the "greedy" part, with probability `1-epsilon`), it chooses the variant that currently has the highest estimated reward. A small fraction of the time (with probability `epsilon`), it chooses a variant randomly to ensure continued exploration.
    *   *Pros:* Easy to understand and implement, guarantees some exploration.
    *   *Cons:* Random exploration can be inefficient. The choice of `epsilon` can be tricky.

*   **Upper Confidence Bound (UCB):** UCB algorithms select variants based not just on their current estimated average reward, but also an "uncertainty bonus." This bonus is higher for variants that have been tried less often or whose performance is more uncertain. This encourages exploration of less-tried arms that *could potentially* be better.
    *   *Pros:* More strategic exploration than epsilon-greedy. Often performs very well.
    *   *Cons:* Can be more complex to tune the exact UCB formula (though `mabwiser` handles this).

*   **Thompson Sampling (Bayesian Bandits):** This algorithm takes a probabilistic approach. It maintains a probability distribution for the expected reward of each variant. To choose a variant, it samples a value from each variant's distribution and picks the variant with the highest sample. Variants with higher uncertainty and/or higher mean rewards are more likely to be chosen.
    *   *Pros:* Generally performs very well, often considered state-of-the-art. Balances exploration/exploitation naturally.
    *   *Cons:* Conceptually more complex as it involves Bayesian updating.

*   **Contextual Bandits (e.g., LinUCB, Linear Thompson Sampling):** These are extensions of the algorithms above that can incorporate contextual information. They essentially learn a separate reward model (or a shared model with feature interactions) for different contexts.
    *   **LinUCB:** Uses a linear model to predict rewards based on context features and variant choice, then applies a UCB-like selection strategy.
    *   Scout's `WrappedMAB` seems to lean towards a LinUCB-like approach when context is provided, automatically handling feature encoding and model fitting.

**Why this matters for Scout users:**

*   You can be confident that Scout is using robust, well-established algorithms.
*   Understanding the exploration/exploitation trade-off is key. Initially, results might fluctuate as the bandit explores. Over time, it should stabilize towards the better-performing variants.
*   Contextual bandits are powerful but require thoughtful feature engineering.

## Contextual Features: Best Practices

Contextual bandits allow Scout to make personalized decisions. The quality of your contextual features significantly impacts performance.

**Choosing Contextual Features:**

*   **Relevance:** Select features that you hypothesize will actually influence which variant is optimal. Irrelevant features add noise and complexity.
    *   *Good examples:* User segment (new/returning), device type (mobile/desktop), time of day, user location (country/region), user preferences explicitly stated.
    *   *Potentially less useful:* User ID (if too granular and doesn't generalize), obscure browser version (unless a known compatibility issue is being tested).
*   **Cardinality:** Be mindful of features with very high cardinality (many unique values), like exact timestamps or highly unique user agent strings.
    *   These can lead to sparse data for each specific context, making it hard for the model to learn.
    *   *Solutions:* Bin continuous features (e.g., `hour_of_day` instead of exact timestamp), group categorical features (e.g., `browser_family` instead of full user agent), or use embeddings if you have many categorical features (though Scout's direct support for pre-computed embeddings as context is not explicit from `app.py`).
*   **Availability:** Features must be available at the time of `fetch_recommended_variant`.

**Encoding Contextual Features:**

Scout's backend (`app.py` in the `encode_context` and `encode_value` functions) appears to handle some automatic encoding:
*   **Numerical Features:** Seem to be used directly as floats.
*   **Boolean Features:** Converted to `1.0` (True) or `0.0` (False).
*   **String (Categorical) Features:** The backend maintains a list of seen (string) feature values per model (`_feature_value_counts`). It seems to be implicitly doing a one-hot-encoding or similar categorical transformation when building the context vector for `mabwiser`.
    *   This means if you send `{"country": "US"}` and later `{"country": "CA"}`, the model learns to treat these as distinct categorical inputs for the feature `country`.

**Tips for Context:**

*   **Start Simple:** Begin with a few, highly relevant contextual features. You can always add more later if needed.
*   **Consistency:** Ensure the context keys and value types you send in `fetch_recommended_variant` are consistent with what you intend to use in `update_model` (if you are *not* using `request_id` to link them, though using `request_id` is highly recommended).
*   **Monitor `model_details`:** The `/api/model_details/{cb_model_id}` endpoint might offer insights into learned features or their importance, depending on what `compute_feature_prediction_data` in `app.py` exposes.
*   **Interaction Effects:** Contextual bandits can implicitly learn interaction effects (e.g., "Variant A is good for mobile users *in the morning*").

## Metrics and Monitoring (Scout & Prometheus)

Scout provides data for monitoring test performance both through its API (`/api/model_details`) and by exporting metrics to Prometheus (`/metrics`).

**Key Metrics from `/api/model_details/{cb_model_id}`:**

*   **`total_predictions`, `total_updates`:** Overall activity of the model.
*   **`performance_summary` (per variant):**
    *   `predictions`: How many times each variant was chosen.
    *   `updates`: How many times reward feedback was given for this variant.
    *   `reward_sum`, `average_reward`: Crucial for understanding raw performance.
    *   `current_prediction_ratio`: The proportion of recent recommendations for this variant. This shows how the bandit is currently allocating traffic.
*   **`prediction_trail`, `update_trail`:** Recent raw data for debugging and fine-grained analysis.
*   **`context_feature_analysis` (if available):** Could provide insights into which context features are influential.
*   **`exploitation_exploration_ratio` (if available):** A direct measure of the bandit's behavior.

**Interpreting Model Performance:**

*   **Convergence:** Initially, `current_prediction_ratio` might fluctuate. As the model gathers more data, these ratios should start to stabilize, with better-performing variants getting higher ratios.
*   **Average Reward:** This is your primary indicator of variant quality. Compare average rewards across variants.
*   **Lift:** Calculate the percentage improvement of a variant's average reward over a baseline or control variant.
*   **Statistical Significance:** While bandits optimize dynamically, if you need to make a definitive statement about one variant being better than another with a certain confidence level, you might still need to apply traditional statistical tests to the accumulated data (e.g., comparing average rewards and sample sizes/updates per variant). Scout provides the raw data; the statistical testing layer is external.
*   **Contextual Performance:** If using contextual features, try to segment your analysis if the UI or detailed data allows. A variant might be best overall but perform poorly in a specific context, or vice-versa.

**Key Prometheus Metrics (from `/metrics` endpoint, scraped by Prometheus):**

*   `http_requests_total (method, endpoint, status)`: Monitor API health, request rates, error rates.
*   `http_request_duration_seconds (method, endpoint)`: Track API latency.
*   `model_predictions_total (model_id, variant_id)`: Count of predictions per variant for each model.
*   `model_updates_total (model_id, variant_id)`: Count of updates per variant for each model.
*   `model_rewards_total (model_id, variant_id)`: Sum of rewards per variant (can be used with `model_updates_total` to calculate average reward in Prometheus).
*   `model_reward_average (model_id, variant_id)`: A gauge of the recent average reward.
*   `redis_operations_total (operation, status)`: Monitor Redis interaction health.
*   `active_models`: How many tests are currently running.
*   `model_creation_timestamp (model_id)`: Track when models were created.

**Using Prometheus for Monitoring:**

*   **Dashboarding (e.g., with Grafana):** Create dashboards to visualize these metrics over time.
    *   Track API error rates and latencies.
    *   Plot average rewards per variant for key tests.
    *   Monitor the number of predictions and updates to ensure data is flowing.
*   **Alerting:** Set up alerts in Prometheus/Alertmanager for critical conditions:
    *   High API error rates.
    *   No updates received for an active model for an extended period.
    *   Drastic drops in average reward for a model that was previously performing well.
    *   Redis connectivity issues.

By combining insights from Scout's API and the detailed metrics in Prometheus, you can gain a comprehensive understanding of your self-optimizing tests' behavior and performance, ensuring they are delivering value and operating correctly. 