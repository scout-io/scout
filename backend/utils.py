from collections import defaultdict
from datetime import datetime
from typing import Dict, Any


def bucket_data(recent_counts: Dict[datetime, Dict[Any, int]]) -> list:
    # recent_counts is already in the structure: Dict[time_bucket, Dict[variant, count]]
    # Create a defaultdict for storing frequency counts in each time bucket
    # buckets = defaultdict(lambda: defaultdict(int)) # REMOVED

    # Iterate through the input data
    # for value, timestamp in data: # REMOVED
    # Create a time bucket by rounding down to the nearest minute # REMOVED
    # time_bucket = datetime( # REMOVED
    # timestamp.year, # REMOVED
    # timestamp.month, # REMOVED
    # timestamp.day, # REMOVED
    # timestamp.hour, # REMOVED
    # timestamp.minute, # REMOVED
    # ) # REMOVED
    # Increment the count for the value in the appropriate time bucket # REMOVED
    # buckets[time_bucket][value] += 1 # REMOVED

    # Format the output as a list of dictionaries
    output = []
    # for time_bucket, frequency in sorted(buckets.items()): # REMOVED
    # The input `recent_counts` is already bucketed by time.
    # We just need to sort it and format it.
    for time_bucket, frequency_map in sorted(recent_counts.items()):
        output.append(
            {"time_bucket": time_bucket.isoformat(), "frequency": dict(frequency_map)}
        )

    return output


def estimate_exploitation_exploration_ratio(model) -> dict:
    if not model.exploitation_history:
        return {"exploitation": 0.0}

    n_requests, exploitation_ratio = model.exploitation_history[-1]

    return {
        "exploitation": round(exploitation_ratio, 2),
    }


def estimate_exploitation_over_time(model) -> list:
    if not model.exploitation_history:
        return []

    response = []
    for n_requests, ratio_percent in model.exploitation_history:
        response.append({"n": n_requests, "exploitation": round(ratio_percent, 2)})
    return response
