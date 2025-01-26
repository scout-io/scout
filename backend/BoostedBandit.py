# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0

from copy import deepcopy
from typing import Callable, Dict, List, Optional, Union

import numpy as np
import lightgbm as lgb

from mabwiser.base_mab import BaseMAB
from mabwiser.greedy import _EpsilonGreedy
from mabwiser.linear import _Linear
from mabwiser.popularity import _Popularity
from mabwiser.rand import _Random
from mabwiser.softmax import _Softmax
from mabwiser.thompson import _ThompsonSampling
from mabwiser.ucb import _UCB1
from mabwiser.utils import Arm, Num, _BaseRNG, argmax, create_rng


class BoostedBandit(BaseMAB):
    """
    A 'TreeBandit' style MAB that uses one LightGBM model per arm to
    predict the expected reward. We do *not* replicate local leaf-based
    logic; we simply call model.predict() for each arm.

    For partial_fit, we demonstrate a LightGBM 'warm start' approach:
      - The first time we train an arm, we do a full train from scratch
      - Subsequent times, we pass init_model=<existing booster> plus new data

    This avoids storing all past data in memory, but also means the model
    sees only new data at each partial_fit call.
    """

    def __init__(
        self,
        rng: _BaseRNG,
        arms: List[Arm],
        n_jobs: int,
        backend: Optional[str],
        lp: Union[
            _EpsilonGreedy,
            _Linear,
            _Popularity,
            _Random,
            _Softmax,
            _ThompsonSampling,
            _UCB1,
        ],
        lgb_params: Dict,
    ):
        """
        lgb_params: Dict of parameters for lightGBM.
          E.g. {
            'objective': 'regression',
            'learning_rate': 0.1,
            'num_leaves': 31,
            'verbose': -1,
            ...
          }
        """
        super().__init__(rng, arms, n_jobs, backend)
        self.lp = lp
        self.lgb_params = deepcopy(lgb_params)

        # One model per arm. We'll store them as trained boosters.
        self.arm_to_model = {arm: None for arm in self.arms}

        # Track whether each arm has been fit at least once.
        # (So we know whether to train from scratch or warm start.)
        self.arm_is_fit = {arm: False for arm in self.arms}

    def fit(
        self, decisions: np.ndarray, rewards: np.ndarray, contexts: np.ndarray = None
    ) -> None:
        """
        Fit from scratch on the given (decisions, rewards, contexts).

        Because we are not storing all data, this effectively trains only
        on the data we receive in this 'fit' call. If your application
        has a large initial batch, this can serve as the 'offline' start.
        """
        # Reset everything
        for arm in self.arms:
            self.arm_to_model[arm] = None
            self.arm_is_fit[arm] = False

        # If TS with binarizer, convert rewards first
        if isinstance(self.lp, _ThompsonSampling) and self.lp.binarizer:
            self.lp.is_contextual_binarized = False
            rewards = self.lp._get_binary_rewards(decisions, rewards)
            self.lp.is_contextual_binarized = True

        self._parallel_fit(decisions, rewards, contexts)

    def partial_fit(
        self, decisions: np.ndarray, rewards: np.ndarray, contexts: np.ndarray = None
    ) -> None:
        """
        Incorporate new data for each arm via a 'warm start' approach with LightGBM.

        We do NOT store older data. If you need to mix old & new data each time,
        consider storing a rolling buffer or custom sampling approach.
        """
        # If TS with binarizer
        if isinstance(self.lp, _ThompsonSampling) and self.lp.binarizer:
            self.lp.is_contextual_binarized = False
            rewards = self.lp._get_binary_rewards(decisions, rewards)
            self.lp.is_contextual_binarized = True

        self._parallel_fit(decisions, rewards, contexts)

    def predict(self, contexts: np.ndarray = None) -> Union[Arm, List[Arm]]:
        """
        For each context, pick the arm with the highest predicted reward.
        If EpsilonGreedy, incorporate epsilon exploration.
        """
        return self._parallel_predict(contexts, is_predict=True)

    def predict_expectations(
        self, contexts: np.ndarray = None
    ) -> Union[Dict[Arm, Num], List[Dict[Arm, Num]]]:
        """
        Return a dictionary {arm: predicted_reward} for each context.
        """
        return self._parallel_predict(contexts, is_predict=False)

    def _fit_arm(
        self,
        arm: Arm,
        decisions: np.ndarray,
        rewards: np.ndarray,
        contexts: Optional[np.ndarray] = None,
    ):
        """
        For each arm, gather data from this batch, then either:
          - Train from scratch (if first time)
          - Warm start from existing booster, using only the new data
        """
        # Subset for this arm
        mask = decisions == arm
        arm_contexts = contexts[mask]
        arm_rewards = rewards[mask]

        # If no data for this arm, skip
        if arm_contexts.size == 0:
            return

        # Build a LightGBM Dataset from new data
        train_data = lgb.Dataset(arm_contexts, label=arm_rewards, free_raw_data=True)

        # Train from scratch if first time
        if not self.arm_is_fit[arm]:
            booster = lgb.train(
                params=self.lgb_params,
                train_set=train_data,
                num_boost_round=50,  # Adjust as needed
                verbose_eval=False,
            )
            self.arm_to_model[arm] = booster
            self.arm_is_fit[arm] = True

        else:
            # Warm start from existing booster
            booster = lgb.train(
                params=self.lgb_params,
                train_set=train_data,
                num_boost_round=50,  # Adjust or tune for your data
                init_model=self.arm_to_model[arm],
                keep_training_booster=True,
                verbose_eval=False,
            )
            self.arm_to_model[arm] = booster

    def _predict_contexts(
        self,
        contexts: np.ndarray,
        is_predict: bool,
        seeds: Optional[np.ndarray] = None,
        start_index: Optional[int] = None,
    ) -> List:
        """
        For each context, predict each arm's reward and either:
          - Return the best arm (if is_predict == True)
          - Return a dictionary of {arm: expected_reward} (if is_predict == False)
        """
        arms = self.arms  # local copy
        predictions = [None] * len(contexts)

        for i, row in enumerate(contexts):
            # row-specific RNG
            rng = create_rng(seeds[i]) if seeds is not None else self.rng

            arm_to_expectation = {}
            for arm in arms:
                model = self.arm_to_model[arm]
                if model is None:
                    # Not fitted => unknown reward => assume 0 or some fallback
                    arm_to_expectation[arm] = 0.0
                else:
                    # Predict
                    pred = model.predict(row.reshape(1, -1))[0]
                    arm_to_expectation[arm] = pred

            if is_predict:
                # Epsilon-greedy if relevant
                if isinstance(self.lp, _EpsilonGreedy) and rng.rand() < self.lp.epsilon:
                    predictions[i] = arms[rng.randint(0, len(arms))]
                else:
                    predictions[i] = argmax(arm_to_expectation)
            else:
                # Return the entire dictionary
                predictions[i] = arm_to_expectation

        return predictions

    # Below methods can be no-ops or placeholders
    def warm_start(
        self, arm_to_features: Dict[Arm, List[Num]], distance_quantile: float
    ):
        pass

    def _copy_arms(self, cold_arm_to_warm_arm):
        pass

    def _uptake_new_arm(
        self, arm: Arm, binarizer: Callable = None, scaler: Callable = None
    ):
        """
        Add a new arm at runtime if needed. Initialize its model to None.
        """
        self.lp.add_arm(arm, binarizer)
        self.arm_to_model[arm] = None
        self.arm_is_fit[arm] = False

    def _drop_existing_arm(self, arm: Arm):
        """
        Remove an existing arm at runtime if needed.
        """
        self.lp.remove_arm(arm)
        self.arm_to_model.pop(arm, None)
        self.arm_is_fit.pop(arm, None)
