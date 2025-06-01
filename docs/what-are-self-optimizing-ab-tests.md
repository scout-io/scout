# What are Self-Optimizing AB Tests?

At its core, Scout helps you run **self-optimizing AB tests**. But what does that mean, and how does it differ from traditional AB testing?

## Traditional AB Testing: The Classic Approach

In a standard AB test (or A/B/n test), you typically define a few distinct versions (variants) of a feature, a webpage, a headline, etc. You then randomly assign users to experience one of these variants. After a predetermined period or a certain number of observations, you analyze the results (e.g., conversion rates, click-through rates) to determine which variant performed best. Finally, you manually roll out the winning variant to all users.

**Key characteristics of traditional AB testing:**

*   **Explore then Exploit**: There's a distinct phase for exploration (gathering data on all variants) followed by exploitation (rolling out the winner).
*   **Fixed Allocation**: Traffic is usually split evenly (or according to predefined ratios) among variants for the duration of the test.
*   **Potential for Regret**: While testing, a significant portion of your users might be exposed to suboptimal variants, leading to missed opportunities (often called "regret").
*   **Static Winner**: The winning variant is chosen at the end and typically remains the winner until a new test is run.

## Self-Optimizing AB Tests: The Bandit Approach

Scout uses **multi-armed bandit (MAB)** algorithms to power its self-optimizing AB tests. The name comes from a thought experiment involving a gambler at a row of slot machines (one-armed bandits). The gambler wants to maximize their winnings by figuring out which machine has the best payout and pulling its lever more often.

In the context of web optimization or feature testing:

*   Each **variant** (e.g., "Headline A", "Button Color Blue", "Algorithm X") is like a **slot machine lever**.
*   A user interacting with a variant and the resulting outcome (e.g., a click, a purchase, a sign-up) is like **pulling a lever and receiving a reward**.

**How bandit algorithms work (in simple terms):**

1.  **Initial Exploration**: To begin, the bandit algorithm doesn't know which variant is best, so it might show each variant to a small number of users to gather initial performance data.
2.  **Dynamic Adaptation (Exploit & Explore Simultaneously)**: As data comes in, the algorithm starts to learn which variants are performing better. It then dynamically allocates more traffic to the current best-performing variants (exploitation). However, it *also* continues to allocate a smaller amount of traffic to other, less certain variants to keep learning and ensure it doesn't prematurely settle on a suboptimal choice (exploration).
3.  **Continuous Learning**: The system constantly updates its understanding based on the latest feedback. If a previously poor-performing variant starts to do well (perhaps due to changing user preferences or external factors), the bandit can detect this and shift traffic accordingly.

**Key advantages of self-optimizing AB tests with Scout:**

*   **Reduced Regret / Faster Optimization**: By shifting traffic towards better-performing options earlier, you minimize the exposure of users to underperforming variants, leading to better overall results even *during* the testing phase.
*   **Always On Optimization**: There isn't a fixed "end" to the test in the traditional sense. The system can run continuously, always learning and adapting.
*   **Contextual Bandits (Personalization)**: This is a powerful extension Scout supports. Instead of just finding the single best variant for *all* users, contextual bandits can learn the best variant for *specific contexts*. A context is a set of features you provide, such_as:
    *   User device (mobile vs. desktop)
    *   Time of day
    *   User segment (new vs. returning)
    *   Geographic location
    Scout can then learn, for example, that "Headline A" is best for mobile users in the US, while "Headline B" is better for desktop users in Europe.
*   **Automated Rollout**: The "rollout" is inherent in the process. The best-performing options naturally receive the most traffic.

## When to Use Self-Optimizing Tests?

Self-optimizing tests are particularly useful when:

*   You want to optimize quickly and minimize the cost of showing users less effective options.
*   You suspect the best variant might change over time or differ for various user segments.
*   You want to automate the process of finding and serving the best experience.
*   You are dealing with many variants and want an efficient way to manage them.

Scout provides the platform to easily implement these powerful bandit strategies, abstracting away much of the underlying complexity and allowing you to focus on defining your tests and understanding the results. 