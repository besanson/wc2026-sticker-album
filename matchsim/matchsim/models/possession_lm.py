"""Tier 3 (optional/experimental): a small GRU generative model over SPADL
action tokens (spec section 5). Only built because Tiers 1 and 2 already pass
their tests. This is an unconditional stub -- it has no team-identity
conditioning, so it generates "an average match" rather than a specific
fixture's, and is evaluated exactly like that (one shared scoreline
distribution scored against every held-out match, same as a naive baseline).
A production version would add team/player embeddings; that's future work,
not this stub.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

ZONE_X_BINS = 3
ZONE_Y_BINS = 3
GOAL_TOKEN_TYPES = {"shot"}


def _zone_bucket(x: float, y: float) -> int:
    xi = min(int(max(x, 0) / 105.0 * ZONE_X_BINS), ZONE_X_BINS - 1)
    yi = min(int(max(y, 0) / 68.0 * ZONE_Y_BINS), ZONE_Y_BINS - 1)
    return xi * ZONE_Y_BINS + yi


@dataclass
class Vocab:
    token_to_id: dict
    id_to_token: list  # list of (is_home, type_name, result_name, zone) tuples
    end_id: int


def _token_of(row, is_home: bool) -> tuple:
    zone = _zone_bucket(row["start_x"], row["start_y"])
    return (is_home, row["type_name"], row["result_name"], zone)


def tokenize(actions: pd.DataFrame, games: pd.DataFrame) -> tuple[list[list[int]], Vocab]:
    """One token per action; one sequence per game, terminated by an END token."""
    home_by_game = dict(zip(games["game_id"], games["home_team_id"]))
    token_to_id: dict = {}
    id_to_token: list = []

    def get_id(tok) -> int:
        if tok not in token_to_id:
            token_to_id[tok] = len(id_to_token)
            id_to_token.append(tok)
        return token_to_id[tok]

    end_id = get_id(("END", "END", "END", "END"))

    sequences = []
    for game_id, group in actions.groupby("game_id", sort=False):
        home_team = home_by_game.get(game_id)
        if home_team is None:
            continue
        seq = [get_id(_token_of(row, row["team_id"] == home_team)) for _, row in group.iterrows()]
        seq.append(end_id)
        sequences.append(seq)

    return sequences, Vocab(token_to_id=token_to_id, id_to_token=id_to_token, end_id=end_id)


class GRULanguageModel(nn.Module):
    def __init__(self, vocab_size: int, embed_size: int = 32, hidden_size: int = 64):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_size)
        self.gru = nn.GRU(embed_size, hidden_size, batch_first=True)
        self.head = nn.Linear(hidden_size, vocab_size)

    def forward(self, tokens: torch.Tensor, hidden=None):
        x = self.embed(tokens)
        out, hidden = self.gru(x, hidden)
        return self.head(out), hidden


def fit_possession_lm(
    sequences: list[list[int]], vocab_size: int, epochs: int = 8, batch_size: int = 16, seed: int = 0
) -> GRULanguageModel:
    torch.manual_seed(seed)
    model = GRULanguageModel(vocab_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=2e-3)
    loss_fn = nn.CrossEntropyLoss(ignore_index=-1)

    max_len = max(len(s) for s in sequences)
    padded = torch.full((len(sequences), max_len), -1, dtype=torch.long)
    for i, s in enumerate(sequences):
        padded[i, : len(s)] = torch.tensor(s)

    n = len(sequences)
    for _epoch in range(epochs):
        perm = torch.randperm(n)
        for start in range(0, n, batch_size):
            batch = padded[perm[start : start + batch_size]]
            inputs, targets = batch[:, :-1], batch[:, 1:]
            inputs_for_embed = inputs.clamp(min=0)
            logits, _ = model(inputs_for_embed)
            loss = loss_fn(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    return model


@torch.no_grad()
def sample_matches(
    model: GRULanguageModel, vocab: Vocab, n_simulations: int, max_length: int, seed: int = 0
) -> list[tuple[int, int]]:
    """Batched autoregressive sampling: n_simulations full matches generated in
    parallel (one forward pass per timestep, batched over simulations, not one
    pass per simulation) so this stays fast. Returns (home_goals, away_goals)
    per simulation, counting successful "shot" tokens by side."""
    torch.manual_seed(seed)
    model.eval()

    current = torch.zeros((n_simulations, 1), dtype=torch.long)  # start token id 0
    hidden = None
    home_goals = np.zeros(n_simulations, dtype=int)
    away_goals = np.zeros(n_simulations, dtype=int)
    finished = np.zeros(n_simulations, dtype=bool)

    for _ in range(max_length):
        logits, hidden = model(current, hidden)
        probs = torch.softmax(logits[:, -1, :], dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)
        ids = next_token.squeeze(-1).numpy()

        for sim_idx, tok_id in enumerate(ids):
            if finished[sim_idx]:
                continue
            is_home, type_name, result_name, _zone = vocab.id_to_token[tok_id]
            if type_name == "END":
                finished[sim_idx] = True
                continue
            if type_name in GOAL_TOKEN_TYPES and result_name == "success":
                if is_home:
                    home_goals[sim_idx] += 1
                else:
                    away_goals[sim_idx] += 1

        current = next_token
        if finished.all():
            break

    return list(zip(home_goals.tolist(), away_goals.tolist()))
