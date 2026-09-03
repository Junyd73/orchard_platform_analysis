# -*- coding: utf-8 -*-
"""경매 Core 예외 → FastAPI envelope. HTTP 매핑 SSOT."""

from __future__ import annotations

from app.core.exceptions import (
    BusinessRuleError,
    DataIntegrityError,
    EntityNotFoundError,
    ExternalDependencyError,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.auction_candidate_constants import (  # noqa: E402
    CODE_AUCTION_CANDIDATE_FARM_ORIGIN,
    CODE_AUCTION_CANDIDATE_NOT_FOUND,
    CODE_AUCTION_CANDIDATE_REALTIME_SOURCE,
    CODE_AUCTION_CANDIDATE_SETTLEMENT_SOURCE,
    CODE_AUCTION_CANDIDATE_STALE,
    CODE_AUCTION_CANDIDATE_STATUS,
    CODE_AUCTION_CANDIDATE_TRADE_DT,
    MSG_AUCTION_CANDIDATE_STALE,
)
from core.auction_match_constants import (
    CODE_AUCTION_CORRECTION_MATCH,
    CODE_AUCTION_CORRECTION_PAYMENT,
    CODE_AUCTION_CORRECTION_RETURN,
    CODE_AUCTION_CORRECTION_SALES,
    CODE_AUCTION_CORRECTION_STATUS,
    CODE_AUCTION_MATCH_AMBIGUOUS_SPEC,
    CODE_AUCTION_MATCH_DISCREPANCY,
    CODE_AUCTION_MATCH_DUPLICATE_SOURCE,
    CODE_AUCTION_MATCH_GRADE,
    CODE_AUCTION_MATCH_INTEGRITY,
    CODE_AUCTION_MATCH_RETURN,
    CODE_AUCTION_MATCH_SALES,
    CODE_AUCTION_MATCH_SCHEMA,
    CODE_AUCTION_MATCH_SPEC_UNMATCHED,
    CODE_AUCTION_MATCH_STALE,
    CODE_AUCTION_MATCH_STATUS,
    CODE_AUCTION_MATCH_UNRESOLVED,
)
from core.auction_ship_constants import (
    CODE_AUCTION_SHIP_CANCEL_MATCHED,
    CODE_AUCTION_SHIP_CANCEL_STATUS,
    CODE_AUCTION_SHIP_DUPLICATE_OUT,
    CODE_AUCTION_SHIP_NOT_FOUND,
    CODE_AUCTION_SHIP_QTY_UNAVAILABLE,
    CODE_AUCTION_SHIP_SCHEMA,
    CODE_AUCTION_SHIP_STOCK_LOG_MISMATCH,
    CODE_AUCTION_SHIP_STOCK_SCHEMA,
)

_NOT_FOUND = frozenset(
    {
        CODE_AUCTION_SHIP_NOT_FOUND,
        CODE_AUCTION_CANDIDATE_NOT_FOUND,
        "AUCTION_SHIP_CUSTM",
    }
)
_CONFLICT = frozenset(
    {
        CODE_AUCTION_SHIP_SCHEMA,
        CODE_AUCTION_SHIP_STOCK_SCHEMA,
        CODE_AUCTION_SHIP_QTY_UNAVAILABLE,
        CODE_AUCTION_SHIP_CANCEL_STATUS,
        CODE_AUCTION_SHIP_CANCEL_MATCHED,
        CODE_AUCTION_SHIP_STOCK_LOG_MISMATCH,
        CODE_AUCTION_SHIP_DUPLICATE_OUT,
        "AUCTION_SHIP_INTEGRITY",
        CODE_AUCTION_CORRECTION_STATUS,
        CODE_AUCTION_CORRECTION_MATCH,
        CODE_AUCTION_CORRECTION_SALES,
        CODE_AUCTION_CORRECTION_RETURN,
        CODE_AUCTION_CORRECTION_PAYMENT,
        CODE_AUCTION_CANDIDATE_STATUS,
        CODE_AUCTION_MATCH_STATUS,
        CODE_AUCTION_MATCH_DUPLICATE_SOURCE,
        CODE_AUCTION_MATCH_STALE,
        CODE_AUCTION_CANDIDATE_STALE,
        CODE_AUCTION_MATCH_INTEGRITY,
        CODE_AUCTION_MATCH_SCHEMA,
        CODE_AUCTION_MATCH_SALES,
        CODE_AUCTION_MATCH_RETURN,
    }
)
_SOURCE = frozenset(
    {
        CODE_AUCTION_CANDIDATE_SETTLEMENT_SOURCE,
        CODE_AUCTION_CANDIDATE_REALTIME_SOURCE,
    }
)
_VALIDATION = frozenset(
    {
        CODE_AUCTION_CANDIDATE_TRADE_DT,
        CODE_AUCTION_CANDIDATE_FARM_ORIGIN,
        CODE_AUCTION_MATCH_DISCREPANCY,
        CODE_AUCTION_MATCH_GRADE,
        CODE_AUCTION_MATCH_AMBIGUOUS_SPEC,
        CODE_AUCTION_MATCH_SPEC_UNMATCHED,
        CODE_AUCTION_MATCH_UNRESOLVED,
        "AUCTION_SHIP_FARM",
        "AUCTION_SHIP_DATE",
        "AUCTION_SHIP_MARKET",
        "AUCTION_SHIP_CORP",
        "AUCTION_SHIP_LINES",
        "AUCTION_SHIP_QTY",
        "AUCTION_SHIP_SPEC",
    }
)


def _not_found(message: str, code: str) -> EntityNotFoundError:
    err = EntityNotFoundError(message)
    err.error_code = code
    return err


def map_auction_error(exc: Exception, *, default_code: str) -> Exception:
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", None) or exc)
    if code in {CODE_AUCTION_MATCH_STALE, CODE_AUCTION_CANDIDATE_STALE}:
        return DataIntegrityError(
            MSG_AUCTION_CANDIDATE_STALE,
            error_code=CODE_AUCTION_CANDIDATE_STALE,
        )
    if code in _NOT_FOUND:
        return _not_found(message, code or "ENTITY_NOT_FOUND")
    if code in _SOURCE:
        return ExternalDependencyError(message, error_code=code)
    if code in _CONFLICT:
        return DataIntegrityError(message, error_code=code or "AUCTION_CONFLICT")
    if code in _VALIDATION:
        return BusinessRuleError(message, error_code=code or default_code)
    return BusinessRuleError(message, error_code=code or default_code)
