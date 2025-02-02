from collections import defaultdict
from datetime import datetime


def bucket_data(data):
    # Create a defaultdict for storing frequency counts in each time bucket
    buckets = defaultdict(lambda: defaultdict(int))

    # Iterate through the input data
    for value, timestamp in data:
        # Create a time bucket by rounding down to the nearest minute
        time_bucket = datetime(
            timestamp.year,
            timestamp.month,
            timestamp.day,
            timestamp.hour,
            timestamp.minute,
        )
        # Increment the count for the value in the appropriate time bucket
        buckets[time_bucket][value] += 1

    # Format the output as a list of dictionaries
    output = []
    for time_bucket, frequency in sorted(buckets.items()):
        output.append({"time_bucket": time_bucket, "frequency": dict(frequency)})

    return output


def estimate_exploitation_exploration_ratio(model) -> dict:
    if not model.prediction_request_trail:
        return {"exploitation": 0.0}

    n_requests, exploitation_ratio = model.exploitation_history[-1]

    return {
        "exploitation": round(exploitation_ratio, 2),
    }


def estimate_relative_reward_increase(model) -> dict:
    # Calculate actual total reward from the model's decisions
    actual_total_reward = sum(
        [reward for variant, reward in model.update_request_trail]
    )

    variant_sum = defaultdict(float)
    variant_count = defaultdict(int)

    for variant, reward in model.update_request_trail:
        variant_sum[variant] += reward
        variant_count[variant] += 1

    # Calculate average reward per variant
    variant_avg = {
        variant: variant_sum[variant] / variant_count[variant]
        for variant in variant_sum
    }

    n_variants = len(model.arms)
    if n_variants == 0:
        return {"relative_increase": 0}

    n_updates = len(model.update_request_trail)

    flattened_updates_per_variant = n_updates / n_variants

    random_total_reward = sum(
        [
            flattened_updates_per_variant * avg_reward
            for avg_reward in variant_avg.values()
        ]
    )

    if random_total_reward == 0:
        return {"relative_increase": 0}

    relative_increase = (
        actual_total_reward - random_total_reward
    ) / random_total_reward

    return {
        "total_reward": actual_total_reward,
        "random_total_rewards": random_total_reward,
        "relative_increase": round(relative_increase * 100, 2),
    }


def estimate_exploitation_over_time(model) -> list:
    if not model.prediction_request_trail:
        return [{"n": 0, "exploitation": 0}]

    response = []
    for n_requests, ratio_percent in model.exploitation_history:
        response.append({"n": n_requests, "exploitation": round(ratio_percent, 2)})
    return response
