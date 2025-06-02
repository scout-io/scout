# Examples

This section provides practical examples of how Scout can be used to optimize different aspects of your application. These examples demonstrate how to define Tests, integrate with the Scout API, and leverage its capabilities for dynamic optimization.

## 1. Basic A/B/n Test

This example illustrates a common use case: testing multiple variations of a user-facing element, similar to traditional A/B testing, but with Scout's dynamic learning.

**Scenario:** You want to test three different call-to-action (CTA) button texts on your product page to determine which one results in the most sign-ups.

*   **Test Name:** `ProductPageCTATest`
*   **Variants:**
    *   `0`: "Get Started Now"
    *   `1`: "Sign Up Free"
    *   `2`: "Create Your Account"
*   **Reward Metric:** A user sign-up event is a reward of `1`. No sign-up is `0`.

**Implementation:**

1.  **Create the Test (via API or UI):**
    Assign the name `ProductPageCTATest` and define the variants. Scout will return a `cb_model_id` (e.g., `model_abc123`) for this Test.

    *API Example (curl):*
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

2.  **Fetch Recommended Variant in Your Application:**
    When a user loads the product page, your application requests a variant from Scout.

    *Python Example:*
    ```python
    import requests
    import uuid

    SCOUT_API_URL = "http://localhost:8000/api/fetch_recommended_variant"
    MODEL_ID = "model_abc123" # Replace with your actual cb_model_id
    AUTH_TOKEN = "YOUR_AUTH_TOKEN" # Replace with your actual token
    REQUEST_ID = str(uuid.uuid4())

    payload = {
        "cb_model_id": MODEL_ID,
        "request_id": REQUEST_ID
        # No "context" is sent for this basic Test
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }

    try:
        response = requests.post(SCOUT_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        recommendation = response.json()
        
        chosen_variant_label = recommendation.get("variant_label")
        chosen_variant_id = recommendation.get("variant_id")
        
        # Store chosen_variant_id and REQUEST_ID (e.g., in user session)
        # to use later for the reward update.
        print(f"Scout recommended: {chosen_variant_label} (ID: {chosen_variant_id})")
        # Your application then displays this CTA text to the user.

    except requests.exceptions.RequestException as e:
        print(f"Error fetching variant from Scout: {e}")
        # Implement fallback logic (e.g., display a default CTA text)
    ```

3.  **Update Scout with Reward Feedback:**
    After the user has an opportunity to interact (e.g., they sign up, or navigate away), send the outcome to Scout.

    *Python Example:*
    ```python
    # Assume user_signed_up = True or False based on actual user action
    # Assume chosen_variant_id and REQUEST_ID were stored from the fetch step

    SCOUT_UPDATE_URL = f"http://localhost:8000/api/update_model/{MODEL_ID}"
    REWARD_VALUE = 1 if user_signed_up else 0

    update_payload = {
        "updates": [
            {
                "request_id": REQUEST_ID,
                "variant_id": chosen_variant_id, # The ID of the variant shown
                "reward": REWARD_VALUE,
                "context_used_for_prediction": False # No context was used
            }
        ]
    }

    try:
        response = requests.post(SCOUT_UPDATE_URL, json=update_payload, headers=headers)
        response.raise_for_status()
        print(f"Scout Test updated: {response.json().get('message')}")
    except requests.exceptions.RequestException as e:
        print(f"Error updating Scout Test: {e}")
    ```

**Outcome:** Scout will dynamically adjust the frequency of each CTA variant shown, favoring the one that leads to more sign-ups over time.

## 2. Test with Contextual Data

This example demonstrates how to use context to personalize choices for different user segments.

**Scenario:** You want to personalize article recommendations on a news site based on the user's subscription status (`free` or `premium`) and the time of day (`morning`, `afternoon`, `evening`).

*   **Test Name:** `PersonalizedArticleRecommendations`
*   **Variants (Recommendation Strategies/Algorithms):**
    *   `0`: "Trending News"
    *   `1`: "In-Depth Analysis"
    *   `2`: "Quick Reads"
*   **Context Features:**
    *   `subscription_status`: "free", "premium"
    *   `time_of_day`: "morning", "afternoon", "evening"
*   **Reward Metric:** User clicks on a recommended article (`1`), or doesn't (`0`).

**Implementation:**

1.  **Create the Test (via API or UI):**
    Name: `PersonalizedArticleRecommendations`, define variants. Let's say the `cb_model_id` is `model_xyz789`.

2.  **Fetch Recommended Variant (with Context):**
    When a user visits the news site, provide their context to Scout.

    *Python Example:*
    ```python
    # ... (similar setup: SCOUT_API_URL, AUTH_TOKEN, MODEL_ID = "model_xyz789") ...
    REQUEST_ID = str(uuid.uuid4())
    
    # Example: Determine user's context
    user_subscription = "premium" # Would come from your user authentication system
    current_time_period = "afternoon" # Would be determined from server/client time

    context_data = {
        "subscription_status": user_subscription,
        "time_of_day": current_time_period
    }

    payload = {
        "cb_model_id": MODEL_ID,
        "context": context_data,
        "request_id": REQUEST_ID
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }
    
    # ... (make request, get recommendation: chosen_strategy_label, chosen_strategy_id) ...
    # Your application then uses the chosen strategy to display relevant articles.
    ```

3.  **Update Scout with Reward Feedback:**
    After the user interacts, send the feedback, ensuring `context_used_for_prediction` is `True`.

    *Python Example:*
    ```python
    # ... (similar setup: SCOUT_UPDATE_URL, AUTH_TOKEN, headers) ...
    # Assume user_clicked_article = True or False
    # Assume chosen_strategy_id and REQUEST_ID were stored

    REWARD_VALUE = 1 if user_clicked_article else 0

    update_payload = {
        "updates": [
            {
                "request_id": REQUEST_ID, # Crucial for linking context
                "variant_id": chosen_strategy_id,
                "reward": REWARD_VALUE,
                "context_used_for_prediction": True # Essential for contextual learning
            }
        ]
    }
    # ... (make update request) ...
    ```

**Outcome:** Scout learns which recommendation strategy is most effective for different combinations of subscription status and time of day (e.g., premium users in the evening might prefer "In-Depth Analysis").

## 3. Using Scout for Feature Flags

Scout can manage the rollout of new features, adapting the rollout based on performance rather than just a fixed percentage.

**Scenario:** You are launching a new search algorithm (`NewSearch`) and want to compare its performance (speed, relevance) against the current one (`OldSearch`).

*   **Test Name:** `SearchAlgorithmRollout`
*   **Variants:**
    *   `0`: `OldSearch`
    *   `1`: `NewSearch`
*   **Context (Optional):** `query_complexity: "high"/"low"`, `user_type: "guest"/"registered"`.
*   **Reward Metric:** A composite score reflecting search quality (e.g., `1.0` for fast, relevant results; `0.5` for slow but relevant; `-1.0` for errors).

**Implementation:**

1.  **Create the Test (via API or UI).**

2.  **Fetch Recommended Variant (Which Search Algorithm to Use):**
    When a user performs a search, ask Scout which algorithm to use, providing context if applicable.

3.  **Update Scout with Performance Feedback:**
    After the search, calculate a reward score and send it to Scout.

**Rollout Management:**
*   **Initial Phase:** Scout will explore both algorithms.
*   **Safety:** If `NewSearch` shows critical issues, you can use Scout's UI/API to temporarily force all traffic to `OldSearch` (using a feature like "force variant" if available, or by adjusting variant parameters if not) while issues are addressed.

**Outcome:** Scout dynamically adjusts traffic. If `NewSearch` consistently outperforms `OldSearch` based on your reward metric, it will receive more traffic, effectively automating a performance-based rollout. If it performs poorly, its traffic is reduced.

These examples illustrate Scout's versatility. The key is to clearly define your variants, identify relevant context (if any), and establish a meaningful reward signal that aligns with your optimization goals. 