# Examples & Use Cases

This section provides practical examples and common use cases for Scout, demonstrating how you can leverage self-optimizing AB tests to improve your application.

## 1. Simple A/B/n Test (Non-Contextual)

This is the most straightforward use case, similar to traditional A/B testing but with the benefits of dynamic optimization.

**Scenario:** You want to test three different call-to-action (CTA) button texts on your product page to see which one leads to the most sign-ups.

*   **Variants:**
    *   Variant 0: "Get Started Now"
    *   Variant 1: "Sign Up Free"
    *   Variant 2: "Create Your Account"
*   **Reward:** A sign-up event is a reward of `1`. No sign-up (or a timeout) could be `0`.

**Implementation Steps:**

1.  **Create the Test (Model) via API or UI:**
    *   Name: `ProductPageCTATest`
    *   Variants: As defined above.
    *   Scout returns a `cb_model_id` (e.g., `model_abc123`).

    *API Example:*
    ```bash
    curl -X POST http://localhost:8000/api/create_model \
         -H "Content-Type: application/json" \
         -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
         -d '{
               "name": "ProductPageCTATest",
               "variants": {
                 "0": "Get Started Now",
                 "1": "Sign Up Free",
                 "2": "Create Your Account"
               }
             }'
    ```

2.  **Fetch Recommended Variant in Your Application Code:**
    When a user loads the product page, your backend calls Scout:

    *Python (requests library) Example:*
    ```python
    import requests
    import uuid

    scout_api_url = "http://localhost:8000/api/fetch_recommended_variant"
    model_id = "model_abc123"
    # Generate a unique request_id, though not strictly necessary for non-contextual updates if not storing context
    # it's good practice for potential future debugging or if you might add context later.
    current_request_id = str(uuid.uuid4())

    payload = {
        "cb_model_id": model_id,
        "request_id": current_request_id 
        # No "context" field for this simple test
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer YOUR_AUTH_TOKEN"
    }

    try:
        response = requests.post(scout_api_url, json=payload, headers=headers)
        response.raise_for_status() # Raise an exception for HTTP errors
        recommendation = response.json()
        
        chosen_variant_label = recommendation.get("variant_label")
        chosen_variant_id = recommendation.get("variant_id")
        # Store chosen_variant_id and current_request_id in the user's session or pass to frontend
        print(f"Scout recommended: {chosen_variant_label} (ID: {chosen_variant_id})")
        # Your app then displays this CTA text to the user.
    except requests.exceptions.RequestException as e:
        print(f"Error fetching variant from Scout: {e}")
        # Fallback: display a default CTA text
    ```

3.  **Update Scout with Feedback (Reward):**
    After the user has had a chance to interact (e.g., they sign up, or navigate away):

    *Python (requests library) Example:*
    ```python
    # Assume user_signed_up = True or False based on user action
    # Assume chosen_variant_id and current_request_id were stored from the fetch step

    scout_update_url = f"http://localhost:8000/api/update_model/{model_id}"
    reward_value = 1 if user_signed_up else 0

    update_payload = {
        "updates": [
            {
                "request_id": current_request_id, # Important to link the decision to the reward
                "variant_id": chosen_variant_id, # The ID of the variant that was actually shown
                "reward": reward_value,
                "context_used_for_prediction": False # As no context was sent in fetch for this simple test
            }
        ]
    }

    try:
        response = requests.post(scout_update_url, json=update_payload, headers=headers)
        response.raise_for_status()
        print(f"Scout model updated: {response.json().get('message')}")
    except requests.exceptions.RequestException as e:
        print(f"Error updating Scout model: {e}")
    ```

**Outcome:** Over time, Scout will automatically start recommending the CTA text that leads to more sign-ups more frequently.

## 2. Contextual Personalization

This is where Scout truly shines. You can personalize experiences based on user or environmental context.

**Scenario:** You want to personalize the type of articles recommended to users on your news site based on their subscription status (`free` or `premium`) and the time of day (`morning`, `afternoon`, `evening`).

*   **Variants (Recommendation Strategies):**
    *   Variant 0: "Trending News Algorithm"
    *   Variant 1: "Deep Dive Analysis Algorithm"
    *   Variant 2: "Quick Reads Algorithm"
*   **Context Features:**
    *   `subscription_status`: "free", "premium"
    *   `time_of_day`: "morning", "afternoon", "evening"
*   **Reward:** User clicks on a recommended article (`1`), or doesn't (`0`).

**Implementation Steps:**

1.  **Create the Test (Model):**
    *   Name: `PersonalizedArticleRecommendations`
    *   Variants: As defined above.
    *   `cb_model_id` (e.g., `model_xyz789`).

2.  **Fetch Recommended Variant (with Context):**
    When a user visits the news site:

    *Python (requests library) Example:*
    ```python
    # ... (similar setup as before for scout_api_url, headers) ...
    model_id = "model_xyz789"
    current_request_id = str(uuid.uuid4())
    
    # Get user's context
    user_subscription = "premium" # This would come from your user data
    current_time_period = "afternoon" # This would be determined by server time

    context_data = {
        "subscription_status": user_subscription,
        "time_of_day": current_time_period
    }

    payload = {
        "cb_model_id": model_id,
        "context": context_data,
        "request_id": current_request_id
    }
    # ... (make request, get recommendation: chosen_reco_strategy_label, chosen_reco_strategy_id) ...
    # Your app then uses the chosen_reco_strategy_id to fetch and display articles.
    ```

3.  **Update Scout with Feedback (with `request_id`):**
    After the user interacts (or a suitable time passes):

    *Python (requests library) Example:*
    ```python
    # ... (similar setup for scout_update_url, headers) ...
    # Assume user_clicked_article = True or False
    # Assume chosen_reco_strategy_id and current_request_id were stored

    reward_value = 1 if user_clicked_article else 0

    update_payload = {
        "updates": [
            {
                "request_id": current_request_id, # Crucial for linking context
                "variant_id": chosen_reco_strategy_id,
                "reward": reward_value,
                "context_used_for_prediction": True # Tell Scout to use the context stored with this request_id
            }
        ]
    }
    # ... (make update request) ...
    ```

**Outcome:** Scout will learn which recommendation strategy works best for different combinations of subscription status and time of day. For example, it might learn that premium users in the evening prefer "Deep Dive Analysis," while free users in the morning engage more with "Quick Reads."

## 3. Feature Flag Rollouts with Dynamic Adaptation

Scout can be used to manage the rollout of new features, not just by percentage, but by performance.

**Scenario:** You are launching a new, resource-intensive search algorithm (`NewSearchAlgo`) and want to compare it against the old one (`OldSearchAlgo`). You want to gradually roll it out if it performs well (e.g., faster results, more relevant clicks) but quickly roll back if it causes issues or performs poorly.

*   **Variants:**
    *   Variant 0: `OldSearchAlgo`
    *   Variant 1: `NewSearchAlgo`
*   **Context (Optional but Recommended):** You might include context like `query_complexity` or `user_type` if you suspect performance differs.
*   **Reward:** A composite score. For example:
    *   High reward (e.g., `1.0`) if search is fast and user clicks a result.
    *   Medium reward (e.g., `0.5`) if search is a bit slow but user clicks.
    *   Low reward (e.g., `0.1`) if search is fast but no click.
    *   Negative reward (e.g., `-1.0`) if search errors out or is extremely slow.

**Implementation Steps:**

1.  **Create the Test (Model):**
    *   Name: `SearchAlgorithmRollout`
    *   Variants: `OldSearchAlgo`, `NewSearchAlgo`.

2.  **Fetch Recommended Variant (Which Search Algo to Use):**
    When a user performs a search:
    ```python
    # ... fetch recommendation from Scout ...
    # payload = {"cb_model_id": "search_model_id", "request_id": req_id, "context": {"query_complexity": "high"}}
    # chosen_search_algo_id = recommendation.get("variant_id")
    ```
    Your application then routes the search query to the chosen algorithm implementation.

3.  **Update Scout with Performance Feedback:**
    After the search results are returned (or an error occurs):
    ```python
    # ... calculate reward based on speed, relevance, errors ...
    # update_payload = {
    #     "updates": [{
    #         "request_id": req_id,
    #         "variant_id": chosen_search_algo_id,
    #         "reward": calculated_reward,
    #         "context_used_for_prediction": True
    #     }]
    # }
    # ... send update to Scout ...
    ```

**Initial Phase & Safety:**
*   **Initial Exploration:** Scout will naturally try both algorithms.
*   **Manual Override:** You can use the "Rollout Global Variant" feature in the UI/API to force `OldSearchAlgo` if `NewSearchAlgo` shows critical early issues, effectively pausing the bandit's control.
*   **Minimum Updates:** The `minimum_update_requests` setting in model config ensures that the bandit doesn't heavily switch before getting some initial data.

**Outcome:**
*   If `NewSearchAlgo` performs consistently better according to your reward metric, Scout will automatically allocate more and more traffic to it.
*   If it performs poorly, its traffic share will decrease. The system adapts to performance in real-time.
*   This provides a more intelligent way to roll out features than simple percentage-based flags, as it directly ties rollout proportion to observed quality.

These examples illustrate the flexibility of Scout. The key is to define your variants, determine what context (if any) is relevant, and establish a clear reward signal that aligns with your optimization goals. 