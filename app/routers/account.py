"""
Account management — /api/account

Endpoints:
  GET    /api/account    current user's profile + preferences
  PATCH  /api/account    update display_name and/or default_modes
  DELETE /api/account    permanently delete the account

Design choices:
- Every route requires get_current_user; there's no id in the URL to scope
  by — the endpoint always acts on the caller's own account.
- PATCH uses exclude_unset (same pattern as itinerary PATCH) so a request
  can update just display_name, just default_modes, or both, without
  clobbering the field it didn't mention. default_modes is written into
  User.preferences rather than replacing the whole dict, so future
  preference keys survive a display-name-only update.
- DELETE removes the Supabase auth identity *before* the local row: if the
  Supabase Admin API call fails, nothing has changed yet and the client can
  safely retry. If the Supabase call succeeds but the local delete then
  fails, the user is signed-out-forever but their itinerary data survives
  for support/manual cleanup — the safer of the two half-failure states.
  A 404 from Supabase (identity already gone) is treated as success so a
  retried DELETE stays idempotent. The local delete itself is a single
  `db.delete(user)` — itineraries and tags cascade via their FK
  ondelete="CASCADE", so there's no window where they can be orphaned.
"""

import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas_account import AccountOut, AccountUpdate

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("", response_model=AccountOut)
def get_account(user: User = Depends(get_current_user)):
    return user


@router.patch("", response_model=AccountOut)
def update_account(
    body: AccountUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)
    if "display_name" in updates:
        user.display_name = updates["display_name"]
    if "default_modes" in updates:
        user.preferences = {**(user.preferences or {}), "default_modes": updates["default_modes"]}
    db.commit()
    db.refresh(user)
    return user


def _delete_supabase_identity(user_id: str) -> None:
    """Delete the Supabase auth user via the Admin API (service_role key,
    server-side only). Raises HTTPException(502) on any failure that isn't
    "already deleted"."""
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not service_key:
        log.warning(
            "SUPABASE_SERVICE_KEY/SUPABASE_URL not configured — skipping "
            "Supabase identity deletion for user %s (local data still removed)",
            user_id,
        )
        return

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.delete(
                f"{supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {service_key}", "apikey": service_key},
            )
    except httpx.HTTPError as exc:
        log.error("Supabase admin user delete request failed for %s: %s", user_id, exc)
        raise HTTPException(status_code=502, detail="Could not delete account — please try again.") from exc

    if resp.status_code not in (200, 204, 404):
        log.error("Supabase admin user delete failed for %s (%s): %s", user_id, resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail="Could not delete account — please try again.")


@router.delete("", status_code=204)
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _delete_supabase_identity(user.id)
    db.delete(user)
    db.commit()
