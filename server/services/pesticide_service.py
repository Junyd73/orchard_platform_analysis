# -*- coding: utf-8 -*-
"""농약 재고 조회 서비스 — SCR-020 · PC MN12/MN13 읽기 전용."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.core.ops_biz_date import today_ops
from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection
from app.schemas.pesticide import (
    PesticideRecentUsageDayDto,
    PesticideRecentUsageLineDto,
    PesticideRecentUsageResponse,
    PesticideStockDetailResponse,
    PesticideStockItemDetailDto,
    PesticideStockItemDto,
    PesticideStockListResponse,
    PesticideStockSummaryDto,
    PesticideUsageListResponse,
    PesticideUsageRowDto,
)
from app.services._core_path import ensure_repo_root_on_path
from app.services.pesticide_ops import PesticideOpsMixin

ensure_repo_root_on_path()
from core.pesticide_constants import (  # noqa: E402
    PESTICIDE_DEFAULT_WARN_PIECE_BELOW,
    is_low_stock,
    resolve_warn_threshold,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _item_nm_sort_key(name: str) -> str:
    """품목명 가나다·알파벳 정렬용(대소문자 무시)."""
    return str(name or "").strip().casefold()
# PSIS는 병해충마다 info 행이 갈라지므로, 연결 info와 동일 품목명·제조사 행의
# 대상병해충을 모아 표시·검색한다.
_PEST_TARGET_AGG_SQL = """
(
  SELECT GROUP_CONCAT(x.pest_nm, ', ')
  FROM (
    SELECT DISTINCT TRIM(mp.pest_nm) AS pest_nm
    FROM m_pesticide_pest_map mp
    INNER JOIN m_pesticide_info sib
      ON sib.info_id = mp.info_id
     AND IFNULL(sib.use_yn, 'Y') = 'Y'
    INNER JOIN m_pesticide_info linked
      ON linked.info_id = it.info_id
    WHERE it.info_id IS NOT NULL
      AND IFNULL(mp.use_yn, 'Y') = 'Y'
      AND TRIM(IFNULL(mp.pest_nm, '')) <> ''
      AND TRIM(IFNULL(sib.pesticide_nm, ''))
          = TRIM(IFNULL(linked.pesticide_nm, ''))
      AND TRIM(IFNULL(sib.maker_nm, ''))
          = TRIM(IFNULL(linked.maker_nm, ''))
  ) x
)
"""
_ITEM_LIST_SQL = f"""
    SELECT it.*,
           inf.pesticide_nm AS info_pesticide_nm,
           inf.ingredient_nm AS ingredient_nm,
           {_PEST_TARGET_AGG_SQL.strip()} AS pest_target_nm
    FROM m_pesticide_item it
    LEFT JOIN m_pesticide_info inf ON inf.info_id = it.info_id
    WHERE it.farm_cd = ? AND IFNULL(it.use_yn, 'Y') = 'Y'
"""
_USAGE_FARM_WHERE = """
    u.farm_cd = ?
    AND IFNULL(u.use_yn, 'Y') = 'Y'
    AND IFNULL(u.cancel_yn, 'N') != 'Y'
    AND IFNULL(u.stock_applied_yn, 'N') = 'Y'
"""
_USAGE_BASE_WHERE = """
    u.farm_cd = ?
    AND l.item_id = ?
    AND IFNULL(u.use_yn, 'Y') = 'Y'
    AND IFNULL(u.cancel_yn, 'N') != 'Y'
    AND IFNULL(u.stock_applied_yn, 'N') = 'Y'
"""
_USAGE_UNIT_DEFAULT = "개"


def _s(v: Any) -> str:
    return str(v or "").strip()


def _row_warn_piece_below(row: dict[str, Any]) -> int | None:
    raw = row.get("warn_piece_below")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _map_item_row(row: dict[str, Any]) -> PesticideStockItemDto:
    warn_pb = _row_warn_piece_below(row)
    threshold, warn_source = resolve_warn_threshold(warn_pb)
    qty = int(row.get("qty_piece") or 0)
    info_id = row.get("info_id")
    return PesticideStockItemDto(
        item_id=int(row["item_id"]),
        item_nm=_s(row.get("item_nm")) or f"품목{row['item_id']}",
        spec_nm=_s(row.get("spec_nm")) or None,
        pest_category_nm=_s(row.get("pest_category_nm")) or None,
        qty_piece=qty,
        warn_piece_below=warn_pb,
        warn_threshold=threshold,
        warn_source=warn_source,
        is_low=is_low_stock(qty, warn_pb),
        info_id=int(info_id) if info_id is not None else None,
        info_pesticide_nm=_s(row.get("info_pesticide_nm")) or None,
        ingredient_nm=_s(row.get("ingredient_nm")) or None,
        pest_target_nm=_s(row.get("pest_target_nm")) or None,
    )


def _map_usage_row(row: dict[str, Any]) -> PesticideUsageRowDto:
    use_dt = _s(row.get("use_dt"))
    if len(use_dt) >= 10:
        use_dt = use_dt[:10]
    return PesticideUsageRowDto(
        use_id=int(row["use_id"]),
        use_line_id=int(row["use_line_id"]),
        use_dt=use_dt,
        use_qty=int(row.get("use_qty") or 0),
        purpose_nm=_s(row.get("purpose_nm")) or None,
        work_id=_s(row.get("work_id")) or None,
        worker_nm=_s(row.get("worker_nm")) or None,
        site_nm=_s(row.get("site_nm")) or None,
        item_nm=_s(row.get("item_nm")) or _s(row.get("item_nm_snapshot")) or None,
    )


class PesticideService(PesticideOpsMixin):
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)

    def _ensure_farm(self, farm_cd: str) -> str:
        farm = _s(farm_cd)
        if not farm:
            raise BusinessRuleError("농장 코드가 없습니다.")
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
                (farm,),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Farm not found")
        return farm

    def _fetch_items(
        self,
        farm: str,
        *,
        keyword: str = "",
        low_only: bool = False,
    ) -> list[PesticideStockItemDto]:
        sql = _ITEM_LIST_SQL
        params: list[Any] = [farm]
        kw = _s(keyword)
        if kw:
            sql += """
                AND (
                    IFNULL(it.item_nm, '') LIKE ?
                    OR IFNULL(inf.pesticide_nm, '') LIKE ?
                    OR IFNULL(it.pest_category_nm, '') LIKE ?
                    OR IFNULL(inf.ingredient_nm, '') LIKE ?
                    OR EXISTS (
                      SELECT 1
                      FROM m_pesticide_pest_map mp
                      INNER JOIN m_pesticide_info sib
                        ON sib.info_id = mp.info_id
                       AND IFNULL(sib.use_yn, 'Y') = 'Y'
                      INNER JOIN m_pesticide_info linked
                        ON linked.info_id = it.info_id
                      WHERE it.info_id IS NOT NULL
                        AND IFNULL(mp.use_yn, 'Y') = 'Y'
                        AND TRIM(IFNULL(sib.pesticide_nm, ''))
                            = TRIM(IFNULL(linked.pesticide_nm, ''))
                        AND TRIM(IFNULL(sib.maker_nm, ''))
                            = TRIM(IFNULL(linked.maker_nm, ''))
                        AND IFNULL(mp.pest_nm, '') LIKE ?
                    )
                )
            """
            like = f"%{kw}%"
            params.extend([like, like, like, like, like])
        sql += " ORDER BY IFNULL(it.sort_ord, 0), it.item_nm"
        with get_sqlite_connection(self._db_path) as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        items = [_map_item_row(dict(r)) for r in (rows or [])]
        if low_only:
            items = [it for it in items if it.is_low]
        return items

    def list_items(
        self,
        farm_cd: str,
        *,
        keyword: str = "",
        low_only: bool = False,
        sort: str = "low_first",
    ) -> PesticideStockListResponse:
        farm = self._ensure_farm(farm_cd)
        items = self._fetch_items(farm, keyword=keyword, low_only=low_only)
        if sort == "name":
            items.sort(key=lambda x: _item_nm_sort_key(x.item_nm))
        else:
            items.sort(
                key=lambda x: (not x.is_low, _item_nm_sort_key(x.item_nm))
            )
        low_count = sum(1 for it in items if it.is_low)
        return PesticideStockListResponse(
            summary=PesticideStockSummaryDto(
                total_count=len(items),
                low_count=low_count,
                default_warn_piece_below=PESTICIDE_DEFAULT_WARN_PIECE_BELOW,
                last_spray_dt=self._fetch_last_spray_dt(farm),
            ),
            items=items,
        )

    def list_recent_usage(
        self,
        farm_cd: str,
        *,
        days: int = 30,
        max_days: int = 10,
    ) -> PesticideRecentUsageResponse:
        farm = self._ensure_farm(farm_cd)
        span = max(1, min(int(days), 90))
        day_cap = max(1, min(int(max_days), 30))
        date_from = (today_ops() - timedelta(days=span - 1)).isoformat()
        last_dt = self._fetch_last_spray_dt(farm)
        sql = f"""
            SELECT
                substr(IFNULL(u.use_dt, ''), 1, 10) AS use_dt,
                IFNULL(NULLIF(TRIM(l.item_nm_snapshot), ''), '품목') AS item_nm,
                SUM(IFNULL(l.use_qty, 0)) AS use_qty
            FROM t_pesticide_use_line l
            INNER JOIN t_pesticide_use u ON u.use_id = l.use_id
            WHERE {_USAGE_FARM_WHERE.strip()}
              AND length(IFNULL(u.use_dt, '')) >= 10
              AND substr(IFNULL(u.use_dt, ''), 1, 10) >= ?
            GROUP BY substr(IFNULL(u.use_dt, ''), 1, 10),
                     IFNULL(NULLIF(TRIM(l.item_nm_snapshot), ''), '품목')
            ORDER BY use_dt DESC, item_nm
        """
        with get_sqlite_connection(self._db_path) as conn:
            rows = conn.execute(sql, (farm, date_from)).fetchall()
        by_day: dict[str, list[PesticideRecentUsageLineDto]] = {}
        order: list[str] = []
        for r in rows or []:
            d = dict(r)
            use_dt = _s(d.get("use_dt"))[:10]
            if not _DATE_RE.match(use_dt):
                continue
            if use_dt not in by_day:
                if len(order) >= day_cap:
                    continue
                by_day[use_dt] = []
                order.append(use_dt)
            by_day[use_dt].append(
                PesticideRecentUsageLineDto(
                    item_nm=_s(d.get("item_nm")) or "품목",
                    use_qty=int(d.get("use_qty") or 0),
                    unit=_USAGE_UNIT_DEFAULT,
                )
            )
        return PesticideRecentUsageResponse(
            last_spray_dt=last_dt,
            days=[
                PesticideRecentUsageDayDto(use_dt=dt, lines=by_day[dt])
                for dt in order
            ],
        )

    def _fetch_last_spray_dt(self, farm: str) -> str | None:
        sql = f"""
            SELECT MAX(substr(IFNULL(u.use_dt, ''), 1, 10)) AS last_dt
            FROM t_pesticide_use u
            INNER JOIN t_pesticide_use_line l ON l.use_id = u.use_id
            INNER JOIN m_pesticide_item it
              ON it.farm_cd = u.farm_cd AND it.item_id = l.item_id
            WHERE {_USAGE_FARM_WHERE.strip()}
              AND length(IFNULL(u.use_dt, '')) >= 10
              AND TRIM(IFNULL(it.pest_category_nm, '')) != '영양제'
        """
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(sql, (farm,)).fetchone()
        if not row:
            return None
        last = _s(row["last_dt"])[:10]
        return last if _DATE_RE.match(last) else None

    def get_item_detail(
        self,
        farm_cd: str,
        item_id: int,
        *,
        recent_limit: int = 20,
    ) -> PesticideStockDetailResponse:
        farm = self._ensure_farm(farm_cd)
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                f"{_ITEM_LIST_SQL} AND it.item_id = ? LIMIT 1",
                (farm, int(item_id)),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Pesticide item not found")
        base = _map_item_row(dict(row))
        row_d = dict(row)
        detail = PesticideStockItemDetailDto(
            **base.model_dump(),
            rmk=_s(row_d.get("rmk")) or None,
        )
        usage = self._list_usage_rows(
            farm,
            int(item_id),
            offset=0,
            limit=max(1, min(recent_limit, 100)),
        )
        return PesticideStockDetailResponse(item=detail, recent_usage=usage)

    def list_item_usage(
        self,
        farm_cd: str,
        item_id: int,
        *,
        date_from: str = "",
        date_to: str = "",
        offset: int = 0,
        limit: int = 20,
    ) -> PesticideUsageListResponse:
        farm = self._ensure_farm(farm_cd)
        iid = int(item_id)
        with get_sqlite_connection(self._db_path) as conn:
            exists = conn.execute(
                """
                SELECT 1 FROM m_pesticide_item
                WHERE farm_cd = ? AND item_id = ? AND IFNULL(use_yn, 'Y') = 'Y'
                LIMIT 1
                """,
                (farm, iid),
            ).fetchone()
        if not exists:
            raise EntityNotFoundError("Pesticide item not found")
        df = _s(date_from)
        dt = _s(date_to)
        if df and not _DATE_RE.match(df):
            raise BusinessRuleError("date_from 형식은 YYYY-MM-DD 입니다.")
        if dt and not _DATE_RE.match(dt):
            raise BusinessRuleError("date_to 형식은 YYYY-MM-DD 입니다.")
        lim = max(1, min(int(limit), 100))
        off = max(0, int(offset))
        total = self._count_usage(farm, iid, date_from=df, date_to=dt)
        rows = self._list_usage_rows(
            farm,
            iid,
            date_from=df,
            date_to=dt,
            offset=off,
            limit=lim,
        )
        return PesticideUsageListResponse(
            item_id=iid,
            total=total,
            offset=off,
            limit=lim,
            rows=rows,
        )

    def _usage_where(
        self,
        farm: str,
        item_id: int,
        *,
        date_from: str = "",
        date_to: str = "",
    ) -> tuple[str, list[Any]]:
        wh = [_USAGE_BASE_WHERE.strip()]
        params: list[Any] = [farm, item_id]
        if date_from:
            wh.append("substr(IFNULL(u.use_dt,''), 1, 10) >= ?")
            params.append(date_from)
        if date_to:
            wh.append("substr(IFNULL(u.use_dt,''), 1, 10) <= ?")
            params.append(date_to)
        return " AND ".join(wh), params

    def _count_usage(
        self,
        farm: str,
        item_id: int,
        *,
        date_from: str = "",
        date_to: str = "",
    ) -> int:
        where, params = self._usage_where(
            farm, item_id, date_from=date_from, date_to=date_to
        )
        sql = f"""
            SELECT COUNT(*) AS c
            FROM t_pesticide_use_line l
            INNER JOIN t_pesticide_use u ON u.use_id = l.use_id
            LEFT JOIN m_farm_site s
                ON u.site_id = s.site_id AND u.farm_cd = s.farm_cd
            WHERE {where}
        """
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return int(row["c"] or 0) if row else 0

    def _list_usage_rows(
        self,
        farm: str,
        item_id: int,
        *,
        date_from: str = "",
        date_to: str = "",
        offset: int = 0,
        limit: int = 20,
    ) -> list[PesticideUsageRowDto]:
        where, params = self._usage_where(
            farm, item_id, date_from=date_from, date_to=date_to
        )
        sql = f"""
            SELECT
                u.use_id,
                l.use_line_id,
                u.use_dt,
                l.use_qty,
                l.purpose_nm,
                l.item_nm_snapshot AS item_nm,
                u.work_id,
                u.worker_nm,
                s.site_nm AS site_nm
            FROM t_pesticide_use_line l
            INNER JOIN t_pesticide_use u ON u.use_id = l.use_id
            LEFT JOIN m_farm_site s
                ON u.site_id = s.site_id AND u.farm_cd = s.farm_cd
            WHERE {where}
            ORDER BY u.use_dt DESC, u.use_id DESC, l.line_no, l.use_line_id
            LIMIT ? OFFSET ?
        """
        params.extend([int(limit), int(offset)])
        with get_sqlite_connection(self._db_path) as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_map_usage_row(dict(r)) for r in (rows or [])]
