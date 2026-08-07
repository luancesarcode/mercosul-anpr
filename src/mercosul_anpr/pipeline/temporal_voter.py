"""Temporal stabilization for OCR outputs and debugger overlay state."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from mercosul_anpr.core.config import TrackingConfig
from mercosul_anpr.vision.ocr_rules import normalizar_texto_placa, validar_e_corrigir_placa, validar_padrao_placa


@dataclass
class TemporalVoter:
    """Hold temporal voting and debugger history per tracked vehicle."""

    config: TrackingConfig
    vote_state: dict[int, dict[str, Any]] = field(default_factory=dict)
    debugger_state: dict[int, dict[str, Any]] = field(default_factory=dict)

    def vote(
        self,
        track_id: int | None,
        text: str,
        score: float,
        frame_idx: int,
        pattern: str | None = None,
    ) -> tuple[str, float, str | None]:
        """Apply temporal vote to stabilize OCR text per track."""
        _ = pattern
        resolved = validar_e_corrigir_placa(text)
        if track_id is None:
            if resolved is None:
                return "", 0.0, None
            text_fix, pat, _changes = resolved
            return text_fix, float(score), pat

        state = self._get_or_create_vote_state(track_id)
        history = state["history"]
        if resolved is not None:
            fixed_text, fixed_pattern, changes = resolved
            adjusted_score = max(0.0, float(score) - (changes * 3.0))
            history.append({"text": fixed_text, "score": adjusted_score, "pattern": fixed_pattern, "frame": frame_idx})

        aggregate = self._aggregate_history(history)
        return self._resolve_stable_text(state, aggregate)

    def cleanup(self, active_track_ids: set[int], frame_idx: int) -> None:
        """Remove stale temporal and debugger states."""
        self._cleanup_vote(active_track_ids, frame_idx)
        self._cleanup_debugger(active_track_ids, frame_idx)

    def update_debugger(self, plates: list[dict[str, Any]], frame_idx: int) -> None:
        """Store OCR history for top-left debugger panel."""
        for plate in plates:
            track_id = plate.get("vehicle_track_id")
            if track_id is None:
                continue
            try:
                tid = int(track_id)
            except (TypeError, ValueError):
                continue

            text = normalizar_texto_placa(plate.get("text"))
            if not text or text == "NA":
                continue
            state = self._get_or_create_debug_state(tid, frame_idx)
            state["history"].append({"text": text, "score": float(plate.get("text_conf", 0.0)), "frame": frame_idx})
            state["last_frame"] = frame_idx

    def debugger_lines(self) -> list[str]:
        """Build debugger text lines with most frequent plate per track."""
        lines: list[str] = []
        for track_id in sorted(self.debugger_state.keys()):
            state = self.debugger_state.get(track_id)
            if not isinstance(state, dict):
                continue
            history = state.get("history")
            if not isinstance(history, deque) or not history:
                continue
            best = self._most_frequent_plate(history)
            if best is None:
                continue
            lines.append(f"ID:{int(track_id):02d} {best[0]}")
        return lines

    def get_stable_prediction(self, track_id: int) -> tuple[str, float, str | None]:
        """Return current stable prediction for a track without updating state."""
        state = self.vote_state.get(track_id)
        if not isinstance(state, dict):
            return "", 0.0, None
        text = normalizar_texto_placa(str(state.get("stable_text") or ""))
        if not text or validar_padrao_placa(text) is None:
            return "", 0.0, None
        return text, float(state.get("stable_score", 0.0)), state.get("stable_pattern")

    def _get_or_create_vote_state(self, track_id: int) -> dict[str, Any]:
        state = self.vote_state.get(track_id)
        if isinstance(state, dict):
            history = state.get("history")
            if isinstance(history, deque) and history.maxlen == self.config.plate_vote_window:
                return state

        state = {
            "history": deque(maxlen=self.config.plate_vote_window),
            "stable_text": "",
            "stable_score": 0.0,
            "stable_pattern": None,
            "candidate_text": "",
            "candidate_streak": 0,
        }
        self.vote_state[track_id] = state
        return state

    def _aggregate_history(self, history: deque[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        aggregate: dict[str, dict[str, Any]] = {}
        for item in history:
            resolved = validar_e_corrigir_placa(str(item.get("text") or ""))
            if resolved is None:
                continue
            plate_text, item_pattern, _changes = resolved
            slot = aggregate.setdefault(plate_text, {"count": 0, "score_sum": 0.0, "best_score": 0.0, "pattern": None})
            score = float(item.get("score", 0.0))
            slot["count"] = int(slot["count"]) + 1
            slot["score_sum"] = float(slot["score_sum"]) + score
            slot["best_score"] = max(float(slot["best_score"]), score)
            if slot["pattern"] is None:
                slot["pattern"] = str(item_pattern)
        return aggregate

    def _resolve_stable_text(
        self,
        state: dict[str, Any],
        aggregate: dict[str, dict[str, Any]],
    ) -> tuple[str, float, str | None]:
        stable_text = normalizar_texto_placa(str(state.get("stable_text") or ""))
        if not aggregate:
            if stable_text and validar_padrao_placa(stable_text):
                return self._visible_or_empty(state, aggregate)
            return "", 0.0, None

        best_text, best_data = max(aggregate.items(), key=self._vote_sort_key)
        count = max(1, int(best_data["count"]))
        avg_score = float(best_data["score_sum"]) / count
        best_pattern = best_data["pattern"] or validar_padrao_placa(best_text)

        if not stable_text:
            self._set_stable(state, best_text, avg_score, best_pattern)
            return best_text, avg_score, best_pattern
        if best_text == stable_text:
            self._set_stable(state, stable_text, avg_score, best_pattern)
            return self._visible_or_empty(state, aggregate)
        if self._should_switch(state, best_text):
            self._set_stable(state, best_text, avg_score, best_pattern)
            return self._visible_or_empty(state, aggregate)
        return self._visible_or_empty(state, aggregate)

    def _vote_sort_key(self, item: tuple[str, dict[str, Any]]) -> tuple[float, float, float]:
        data = item[1]
        count = max(1, int(data["count"]))
        avg = float(data["score_sum"]) / count
        return float(data["count"]), avg, float(data["best_score"])

    def _should_switch(self, state: dict[str, Any], best_text: str) -> bool:
        candidate_text = normalizar_texto_placa(str(state.get("candidate_text") or ""))
        if best_text == candidate_text:
            state["candidate_streak"] = int(state.get("candidate_streak", 0)) + 1
        else:
            state["candidate_text"] = best_text
            state["candidate_streak"] = 1
        return int(state.get("candidate_streak", 0)) >= self.config.plate_switch_dominance_frames

    def _set_stable(self, state: dict[str, Any], text: str, score: float, pattern: str | None) -> None:
        state["stable_text"] = text
        state["stable_score"] = float(score)
        state["stable_pattern"] = pattern
        state["candidate_text"] = ""
        state["candidate_streak"] = 0

    def _visible_or_empty(
        self,
        state: dict[str, Any],
        aggregate: dict[str, dict[str, Any]],
    ) -> tuple[str, float, str | None]:
        text = normalizar_texto_placa(str(state.get("stable_text") or ""))
        if not text:
            return "", 0.0, None
        if not self._meets_visibility_threshold(text, state, aggregate):
            return "", 0.0, None
        return text, float(state.get("stable_score", 0.0)), state.get("stable_pattern")

    def _meets_visibility_threshold(
        self,
        stable_text: str,
        state: dict[str, Any],
        aggregate: dict[str, dict[str, Any]],
    ) -> bool:
        slot = aggregate.get(stable_text)
        if isinstance(slot, dict):
            count = max(1, int(slot.get("count", 0)))
            avg = float(slot.get("score_sum", 0.0)) / count
            return count >= self.config.plate_min_occurrences and avg >= self.config.plate_min_score
        return float(state.get("stable_score", 0.0)) >= self.config.plate_min_score

    def _cleanup_vote(self, active_ids: set[int], frame_idx: int) -> None:
        stale: list[int] = []
        for track_id, state in self.vote_state.items():
            history = state.get("history") if isinstance(state, dict) else None
            if not isinstance(history, deque):
                stale.append(track_id)
                continue
            last_frame = max((int(item.get("frame", -1)) for item in history), default=-1)
            if track_id not in active_ids and (frame_idx - last_frame) > self.config.track_max_age:
                stale.append(track_id)
        for track_id in stale:
            self.vote_state.pop(track_id, None)

    def _cleanup_debugger(self, active_ids: set[int], frame_idx: int) -> None:
        stale: list[int] = []
        for track_id, state in self.debugger_state.items():
            if not isinstance(state, dict):
                stale.append(track_id)
                continue
            last_frame = int(state.get("last_frame", -1))
            if track_id not in active_ids and (frame_idx - last_frame) > self.config.track_max_age:
                stale.append(track_id)
        for track_id in stale:
            self.debugger_state.pop(track_id, None)

    def _get_or_create_debug_state(self, track_id: int, frame_idx: int) -> dict[str, Any]:
        state = self.debugger_state.get(track_id)
        if isinstance(state, dict):
            history = state.get("history")
            if isinstance(history, deque) and history.maxlen == self.config.debugger_window_frames:
                return state

        state = {
            "history": deque(maxlen=self.config.debugger_window_frames),
            "last_frame": frame_idx,
        }
        self.debugger_state[track_id] = state
        return state

    def _most_frequent_plate(self, history: deque[dict[str, Any]]) -> tuple[str, float] | None:
        aggregate: dict[str, dict[str, float | int]] = {}
        for item in history:
            text = normalizar_texto_placa(str(item.get("text") or ""))
            if not text:
                continue
            score = float(item.get("score", 0.0))
            slot = aggregate.setdefault(text, {"count": 0, "score_sum": 0.0})
            slot["count"] = int(slot["count"]) + 1
            slot["score_sum"] = float(slot["score_sum"]) + score

        if not aggregate:
            return None

        text, data = max(aggregate.items(), key=self._frequency_key)
        count = max(1, int(data["count"]))
        return text, float(data["score_sum"]) / count

    def _frequency_key(self, item: tuple[str, dict[str, float | int]]) -> tuple[int, float]:
        data = item[1]
        count = max(1, int(data["count"]))
        return int(data["count"]), float(data["score_sum"]) / count
