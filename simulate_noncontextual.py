import numpy as np
import requests
import random
import time
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict


def get_recommended_variant(base_url, model_id):
    """
    Makes a POST request to fetch the recommended variant.
    In the non-contextual case, we omit any context from the payload.
    Returns the recommended variant (string).
    """
    url = f"{base_url}/api/fetch_recommended_variant"
    payload = {"cb_model_id": model_id}  # no 'context' key provided
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()["recommended_variant"]


def update_model(base_url, model_id, decision, reward):
    """
    Makes a POST request to update the model with the provided (decision, reward).
    In the non-contextual case, no context is provided.
    """
    url = f"{base_url}/api/update_model/{model_id}"
    # No context is provided in the update payload.
    payload = {"updates": [{"decision": decision, "reward": reward}]}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


def simulate_bandit(base_url, model_id, n_iterations=1000, sleep_between_calls=0.0):
    """
    Simulates repeated requests to the bandit model in the non-contextual case.
    For each iteration:
      1) Make a prediction request (with no context).
      2) Compute a reward: variant 'a' receives a slightly higher reward than 'b'.
      3) Update the model with the (decision, reward) pair.

    Returns:
        pd.DataFrame: A DataFrame containing the simulation history:
                      columns = ['iteration', 'recommended_variant', 'reward'].
    """
    data_records = []

    for i in range(n_iterations):
        # 1) Get a recommended variant without any context
        recommended_variant = get_recommended_variant(base_url, model_id)

        # 2) Compute reward:
        #    For this toy model variant 'a' gets reward 1.5 and variant 'b' gets reward 1.0.
        if recommended_variant == "a":
            reward = 1.005
        else:
            reward = 1.0

        # 3) Update the model with the result (no context provided)
        update_model(base_url, model_id, recommended_variant, reward)

        # Record the iteration data.
        data_records.append(
            {
                "iteration": i + 1,
                "recommended_variant": recommended_variant,
                "reward": reward,
            }
        )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    df = pd.DataFrame(data_records)
    return df


def plot_results(df):
    """
    Creates two plots to visualize how the bandit is behaving:
      1) The evolution of the rolling proportion of each recommended variant.
      2) The rolling average reward over iterations.
    """
    window_size = 50
    # Compute indicator columns for each variant
    df["count_a"] = (df["recommended_variant"] == "a").astype(int)
    df["count_b"] = (df["recommended_variant"] == "b").astype(int)

    # Plot rolling proportions of recommended variants.
    fig, ax = plt.subplots(figsize=(10, 6))
    df = df.sort_values("iteration")
    df["rolling_prop_a"] = df["count_a"].rolling(window_size, min_periods=1).mean()
    df["rolling_prop_b"] = df["count_b"].rolling(window_size, min_periods=1).mean()
    ax.plot(
        df["iteration"],
        df["rolling_prop_a"],
        label="Prop of 'a'",
        linestyle="--",
        color="C0",
    )
    ax.plot(df["iteration"], df["rolling_prop_b"], label="Prop of 'b'", color="C1")
    ax.set_xlabel("Iteration")
    ax.set_ylabel(f"Rolling Proportion (window = {window_size})")
    ax.set_title("Evolution of Recommended Variant Proportions")
    ax.legend()
    plt.tight_layout()
    plt.show()

    # Plot rolling average reward.
    df["rolling_reward"] = df["reward"].rolling(window_size, min_periods=1).mean()
    plt.figure(figsize=(10, 5))
    plt.plot(
        df["iteration"],
        df["rolling_reward"],
        label="Rolling Average Reward",
        color="C2",
    )
    plt.title("Rolling Average Reward Over Time")
    plt.xlabel("Iteration")
    plt.ylabel("Reward")
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    # Configuration (adjust these as needed)
    BASE_URL = "http://localhost:3000"  # URL of your CB service
    CB_MODEL_ID = "44f7e9ec-f47b-4c84-bed0-b844e501f2df"  # The model ID you created
    N_ITERATIONS = 500  # Number of simulation iterations

    print("Starting simulation (non-contextual)...")
    df_results = simulate_bandit(
        base_url=BASE_URL,
        model_id=CB_MODEL_ID,
        n_iterations=N_ITERATIONS,
        sleep_between_calls=0.01,
    )
    print("Simulation completed.")

    print("Plotting results...")
    plot_results(df_results)
    print("All done!")


if __name__ == "__main__":
    main()
