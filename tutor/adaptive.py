"""Adaptive learning helpers: BKT and tiny DKT wrapper."""

from typing import List

import math


class BKT:
    """Simple Bayesian Knowledge Tracing implementation.

    Parameters are in probability space:
    - p_L0: initial probability learned
    - p_T: transition (learn) probability
    - p_G: guess probability
    - p_S: slip probability
    """

    def __init__(self, p_L0=0.2, p_T=0.1, p_G=0.2, p_S=0.1):
        self.p_L = float(p_L0)
        self.p_T = float(p_T)
        self.p_G = float(p_G)
        self.p_S = float(p_S)

    def predict_correct(self) -> float:
        """Predict probability of correct response at current knowledge state."""
        return self.p_L * (1 - self.p_S) + (1 - self.p_L) * self.p_G

    def update(self, correct: bool):
        """Update internal belief given an observed response (True=correct)."""
        p = self.p_L
        # P(observation | known) and |unknown
        if correct:
            o_known = 1 - self.p_S
            o_unknown = self.p_G
        else:
            o_known = self.p_S
            o_unknown = 1 - self.p_G

        # Bayes update
        num = p * o_known
        den = num + (1 - p) * o_unknown
        if den == 0:
            posterior_known = 0.0
        else:
            posterior_known = num / den

        # transition
        self.p_L = posterior_known + (1 - posterior_known) * self.p_T


try:
    import torch
    import torch.nn as nn

    class DKTModel(nn.Module):
        def __init__(self, input_size: int, hidden_size: int = 16):
            super().__init__()
            self.gru = nn.GRU(input_size, hidden_size, batch_first=True)
            self.out = nn.Linear(hidden_size, 1)

        def forward(self, x):
            # x: (B, T, input_size)
            h, _ = self.gru(x)
            # take last timestep
            last = h[:, -1, :]
            return torch.sigmoid(self.out(last)).squeeze(-1)

    class DKTWrapper:
        """Wrapper that manages a tiny GRU-based DKT model. Training utilities are minimal.

        This is intentionally tiny for on-device experimentation.
        """

        def __init__(self, input_size: int = 2, hidden_size: int = 16):
            self.device = torch.device("cpu")
            self.model = DKTModel(input_size, hidden_size).to(self.device)
            self.loss = nn.BCELoss()
            self.opt = torch.optim.Adam(self.model.parameters(), lr=1e-3)

        def predict(self, seq_tensor):
            self.model.eval()
            with torch.no_grad():
                return self.model(seq_tensor.to(self.device)).cpu().numpy()

        def train_step(self, batch_x, batch_y):
            self.model.train()
            pred = self.model(batch_x.to(self.device))
            loss = self.loss(pred, batch_y.to(self.device))
            self.opt.zero_grad()
            loss.backward()
            self.opt.step()
            return float(loss.item())

except Exception:
    # Fallback when torch isn't available
    DKTWrapper = None


def elo_baseline(history: List[int], k: float = 32.0) -> float:
    """Simple Elo-style baseline that returns a score in [0,1] for correctness prediction.

    `history` should be a list of 1/0 outcomes; we map Elo into [0,1] via logistic.
    """
    # start at 1500, adjust
    rating = 1500.0
    for o in history:
        outcome = float(o)
        expected = 1 / (1 + math.pow(10, (1500 - rating) / 400))
        rating += k * (outcome - expected)
    # map rating to probability via sigmoid around 1500
    return 1 / (1 + math.exp(-(rating - 1500) / 200.0))
