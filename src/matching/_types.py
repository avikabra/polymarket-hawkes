"""Shared types for the matching pipeline. No heavy imports."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VerificationResult(BaseModel):
    is_match: bool
    match_strength: float = Field(ge=0.0, le=1.0)
    directional_impact: Literal[-1, 0, 1]
    magnitude: float = Field(ge=0.0, le=1.0)
    news_type: Literal["quantitative", "qualitative", "high_attention", "ambiguous"]
    reasoning: str
