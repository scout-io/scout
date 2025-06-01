import numpy as np
import requests
import random
import time
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict


def get_recommended_variant(base_url, model_id, context):
    """
    Makes a POST request to fetch the recommended variant given the context.
    Returns the recommended variant (string) and request_id.
    """
    url = f"{base_url}/api/fetch_recommended_variant"
    payload = {"cb_model_id": model_id, "context": context}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    response_data = resp.json()
    return response_data["recommended_variant"], response_data["request_id"]


def update_model(base_url, model_id, decision, reward, request_id):
    """
    Makes a POST request to update the model with the provided decision and reward.
    Uses request_id to retrieve context from Redis.
    """
    url = f"{base_url}/api/update_model/{model_id}"
    payload = {"updates": []}
    update_dict = {
        "decision": decision,
        "reward": reward,
        "request_id": request_id,
        # No need to include context - it will be retrieved from Redis using request_id
    }
    payload["updates"].append(update_dict)

    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


def simulate_bandit(base_url, model_id, n_iterations=1000, sleep_between_calls=0.0):
    """
    Simulates repeated requests to the bandit model.

    Args:
        base_url (str): The root URL of your CB service (e.g. 'http://localhost:3000').
        model_id (str): The ID of the model to use.
        n_iterations (int): How many times we run the [predict -> reward -> update] cycle.
        sleep_between_calls (float): How many seconds to sleep between each iteration
                                     (sometimes helps if the server needs a break).

    Returns:
        pd.DataFrame: A DataFrame containing the simulation history:
                      columns = ['iteration', 'feature_example', 'recommended_variant', 'reward', 'request_id'].
    """
    data_records = []

    for i in range(n_iterations):
        # 1) Randomly pick feature_example in {"red", "blue"}
        feature_val = random.choice(["red", "blue"])
        context = {"feature_example": feature_val}

        # 2) Make a prediction request - now also returns request_id
        recommended_variant, request_id = get_recommended_variant(
            base_url, model_id, context
        )

        # 3) Compute a reward
        #    If feature_example = "red", variant 'a' has a very slightly higher reward.
        #    If feature_example =  "blue", variant 'b' has a very slightly higher reward.
        if feature_val == "red" and recommended_variant == "a":
            reward = 1.5
        elif feature_val == "blue" and recommended_variant == "b":
            reward = 1.5
        else:
            reward = 1.00

        # 4) Update the model with the result - using request_id instead of context
        update_result = update_model(
            base_url, model_id, recommended_variant, reward, request_id
        )

        # Record data
        data_records.append(
            {
                "iteration": i + 1,
                "feature_example": feature_val,
                "recommended_variant": recommended_variant,
                "reward": reward,
                "request_id": request_id,  # Store request_id for reference
                "processed": update_result.get(
                    "processed_updates", 1
                ),  # Track if update was processed
            }
        )

        # Log progress periodically
        if (i + 1) % 50 == 0:
            print(f"Completed {i + 1}/{n_iterations} iterations")

        # Sleep if desired (optional)
        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    # Convert to DataFrame
    df = pd.DataFrame(data_records)
    return df


def plot_results(df):
    """
    Creates several plots to visualize how the bandit is behaving.
    Plots include:
      1) Proportion of each recommended variant grouped by feature_example.
      2) How the proportion of each variant changes over iterations.
      3) Average reward over time.
    """
    # 1) Proportion of variants by feature_example
    grouped = (
        df.groupby(["feature_example", "recommended_variant"])
        .size()
        .reset_index(name="count")
    )
    total_counts = df.groupby("feature_example").size().reset_index(name="total")
    merged = pd.merge(grouped, total_counts, on="feature_example")
    merged["proportion"] = merged["count"] / merged["total"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Plot the proportion bar chart
    for idx, feat_val in enumerate(sorted(df["feature_example"].unique())):
        sub_df = merged[merged["feature_example"] == feat_val]
        axes[idx].bar(
            sub_df["recommended_variant"], sub_df["proportion"], color=["C0", "C1"]
        )
        axes[idx].set_title(f"feature_example = {feat_val}")
        axes[idx].set_xlabel("Variant")
        axes[idx].set_ylabel("Proportion")
        axes[idx].set_ylim(0, 1)
        for x, y in zip(sub_df["recommended_variant"], sub_df["proportion"]):
            axes[idx].text(x, y + 0.01, f"{y:.2f}", ha="center")

    plt.suptitle("Variant Proportions by Feature Value", fontsize=14)
    plt.tight_layout()
    plt.savefig("variant_proportions.png")
    plt.show()

    # 2) Proportion of variants over iterations
    window_size = 50  # change as needed to smooth out
    df["count_a"] = (df["recommended_variant"] == "a").astype(int)
    df["count_b"] = (df["recommended_variant"] == "b").astype(int)

    # We'll do separate data for feature_example = "red" and = "blue"
    fig, ax = plt.subplots(figsize=(10, 6))

    for feat_val, color in zip(sorted(df["feature_example"].unique()), ["red", "blue"]):
        sub_df = df[df["feature_example"] == feat_val].copy()
        # Sort by iteration
        sub_df = sub_df.sort_values("iteration")
        sub_df[f"rolling_prop_a"] = (
            sub_df["count_a"].rolling(window_size, min_periods=1).mean()
        )
        sub_df[f"rolling_prop_b"] = (
            sub_df["count_b"].rolling(window_size, min_periods=1).mean()
        )
        ax.plot(
            sub_df["iteration"],
            sub_df["rolling_prop_a"],
            label=f"Prop of 'a' (feat={feat_val})",
            linestyle="--",
            color=color,
        )
        ax.plot(
            sub_df["iteration"],
            sub_df["rolling_prop_b"],
            label=f"Prop of 'b' (feat={feat_val})",
            color=color,
            alpha=0.7,
        )

    ax.set_xlabel("Iteration")
    ax.set_ylabel(f"Rolling proportion (window={window_size})")
    ax.set_title("Evolution of Recommended Variant Proportions")
    ax.legend()
    plt.tight_layout()
    plt.savefig("variant_evolution.png")
    plt.show()

    # 3) Plot average reward over time
    df["rolling_reward"] = df["reward"].rolling(window_size, min_periods=1).mean()
    plt.figure(figsize=(10, 5))
    plt.plot(df["iteration"], df["rolling_reward"], label="Rolling Average Reward")
    plt.title("Rolling Average Reward Over Time")
    plt.xlabel("Iteration")
    plt.ylabel("Reward")
    plt.legend()
    plt.savefig("reward_over_time.png")
    plt.show()

    # 4) New: Check if all updates were processed successfully
    update_success_rate = df["processed"].mean() * 100
    print(f"Update success rate: {update_success_rate:.2f}%")

    # Optionally, save the DataFrame for later analysis
    df.to_csv("simulation_results.csv", index=False)


def main():
    # Configuration
    BASE_URL = "http://localhost"  # Updated default port to match Docker config
    CB_MODEL_ID = "eae58fef-d38b-403b-9243-fc6830e74651"
    N_ITERATIONS = 500  # How many times to run the simulation loop

    # Run the simulation
    print("\nStarting simulation...")
    start_time = time.time()
    df_results = simulate_bandit(
        base_url=BASE_URL,
        model_id=CB_MODEL_ID,
        n_iterations=N_ITERATIONS,
        sleep_between_calls=0.01,  # Increase if you need to throttle requests
    )
    end_time = time.time()
    print(f"Simulation completed in {end_time - start_time:.2f} seconds.")

    # Create plots
    print("\nPlotting results...")
    plot_results(df_results)
    print("\nAll done! Check the generated plot images for results.")


if __name__ == "__main__":
    main()
