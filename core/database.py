from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import math
import os
from pathlib import Path
import re
import secrets
import smtplib
from dotenv import load_dotenv
from supabase import Client, create_client

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

# Optional public anon fallback config for standalone builds when .env is absent.
# Never put private SMTP App Passwords or Supabase service_role keys here.
DEFAULT_SUPABASE_URL = "https://vbnmgzyoxboxfgwkitxr.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_xJssg4ghO0ir77eiLYfVPQ_xHateup0"

PBKDF2_ITERATIONS = 200_000

_CLIENT: Client | None = None


class DatabaseError(Exception):
    """Domain-specific exception for database and authentication errors."""


def _sanitize_user(row: dict | None) -> dict:
    """Removes sensitive or internal columns before returning user data."""
    if not isinstance(row, dict):
        return {}
    safe = dict(row)
    for key in ("password_hash", "salt", "reset_otp", "reset_otp_expires", "reset_otp_attempts"):
        safe.pop(key, None)
    return safe


def _get_env_or_default(key: str, default: str = "") -> str:
    val = (os.getenv(key) or "").strip()
    return val if val else default


def get_client() -> Client:
    """Returns a singleton Supabase client instance."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    url = _get_env_or_default("SUPABASE_URL", DEFAULT_SUPABASE_URL)
    key = _get_env_or_default("SUPABASE_KEY", DEFAULT_SUPABASE_KEY)

    if not url or not key:
        raise DatabaseError("Missing SUPABASE_URL or SUPABASE_KEY in environment configuration.")

    try:
        _CLIENT = create_client(url, key)
        return _CLIENT
    except Exception as ex:
        raise DatabaseError(f"Failed to initialize Supabase client: {ex}")


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hashes a password using PBKDF2-HMAC-SHA256 with a random per-user salt."""
    if not isinstance(password, str) or len(password) < 6:
        raise DatabaseError("Password must be at least 6 characters.")
    use_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        use_salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return digest, use_salt


def _verify_password(password: str, stored_hash: str, salt: str | None = None) -> bool:
    """Verifies a plaintext password against a stored hash (supports salted and legacy formats)."""
    if not password or not stored_hash:
        return False
    if salt:
        computed, _ = _hash_password(password, salt=salt)
        return secrets.compare_digest(computed, stored_hash)
    if "$" in stored_hash:
        legacy_salt, legacy_hash = stored_hash.split("$", 1)
        computed, _ = _hash_password(password, salt=legacy_salt)
        return secrets.compare_digest(computed, legacy_hash)
    legacy_sha = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return secrets.compare_digest(legacy_sha, stored_hash)


def _normalize_username(username: str) -> str:
    clean = (username or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,24}", clean):
        raise DatabaseError("Username must be 3-24 characters (letters, numbers, underscores only).")
    return clean


def _normalize_email(email: str) -> str:
    clean = "".join((email or "").split()).lower()
    parts = clean.split("@")
    if len(parts) != 2 or not parts[0] or "." not in parts[1] or len(clean) > 120:
        raise DatabaseError("Please enter a valid email address.")
    local, domain = parts
    domain_parts = domain.split(".")
    if any(not p for p in domain_parts) or len(domain_parts[-1]) < 2:
        raise DatabaseError("Please enter a valid email address.")
    return f"{local}@{domain}"


def _normalize_name(name: str) -> str:
    clean = " ".join((name or "").strip().split())
    if len(clean) < 2 or len(clean) > 80:
        raise DatabaseError("Display name must be between 2 and 80 characters.")
    return clean


def _require_non_empty_id(value: str, label: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise DatabaseError(f"Missing {label}.")
    return clean


def _is_member_of_trip(db: Client, trip_id: str, user_id: str) -> bool:
    mem = (
        db.table("trip_members")
        .select("id")
        .eq("trip_id", trip_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return bool(mem.data)


# ---------------- AUTHENTICATION & PROFILE ----------------

def register_user(name: str, username: str, password: str, email: str = "") -> dict:
    """Registers a new user with salted PBKDF2 password hashing."""
    clean_name = _normalize_name(name)
    clean_username = _normalize_username(username)
    clean_email = _normalize_email(email) if (email or "").strip() else None

    if not password or len(password) < 6:
        raise DatabaseError("Password must be at least 6 characters.")

    pw_hash, salt = _hash_password(password)
    db = get_client()

    payload = {
        "name": clean_name,
        "username": clean_username,
        "password_hash": f"{salt}${pw_hash}",
        "email": clean_email,
    }

    try:
        res = db.table("users").insert(payload).execute()
    except Exception as ex:
        msg = str(ex).lower()
        if "duplicate" in msg or "unique" in msg or "23505" in msg:
            raise DatabaseError("Username or email is already registered.")
        raise DatabaseError(f"Registration failed: {ex}")

    if not res.data:
        raise DatabaseError("Registration did not return user data.")

    return _sanitize_user(res.data[0])


def login_user(username: str, password: str) -> dict:
    """Authenticates a user by username and password."""
    clean_username = _normalize_username(username)
    if not password:
        raise DatabaseError("Please enter your password.")

    db = get_client()
    try:
        res = (
            db.table("users")
            .select("*")
            .eq("username", clean_username)
            .limit(1)
            .execute()
        )
    except Exception as ex:
        raise DatabaseError(f"Login failed: {ex}")

    if not res.data:
        raise DatabaseError("Invalid username or password.")

    row = res.data[0]
    if not _verify_password(password, row.get("password_hash", "")):
        raise DatabaseError("Invalid username or password.")

    return _sanitize_user(row)


def update_user_profile(user_id: str, name: str, username: str, email: str) -> dict:
    """Updates Name, Username, and Email for the signed-in user."""
    clean_uid = _require_non_empty_id(user_id, "user session")
    clean_name = _normalize_name(name)
    clean_username = _normalize_username(username)
    clean_email = _normalize_email(email)

    db = get_client()
    try:
        res = (
            db.table("users")
            .update({
                "name": clean_name,
                "username": clean_username,
                "email": clean_email,
            })
            .eq("id", clean_uid)
            .execute()
        )
    except Exception as ex:
        msg = str(ex).lower()
        if "duplicate" in msg or "unique" in msg or "23505" in msg:
            raise DatabaseError("That username or email is already in use.")
        raise DatabaseError(f"Profile update failed: {ex}")

    if not res.data:
        raise DatabaseError("User profile not found.")

    return _sanitize_user(res.data[0])


def _send_otp_email(to_email: str, otp_code: str) -> None:
    smtp_email = _get_env_or_default("SMTP_EMAIL")
    smtp_password = _get_env_or_default("SMTP_APP_PASSWORD").replace(" ", "")
    if not smtp_email or not smtp_password:
        raise DatabaseError("Email OTP service is not configured on this build.")

    msg = EmailMessage()
    msg["Subject"] = "Trip Hisaab - Password Reset OTP"
    msg["From"] = smtp_email
    msg["To"] = to_email
    msg.set_content(
        f"Your Trip Hisaab password reset OTP is: {otp_code}\n\n"
        "This code expires in 10 minutes. If you did not request this, ignore this email."
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
    except Exception as ex:
        raise DatabaseError(f"Could not send OTP email: {ex}")


def request_password_reset_otp(email: str) -> None:
    """Generates a 6-digit OTP valid for 10 minutes and emails it if the account exists."""
    clean_email = _normalize_email(email)
    db = get_client()

    try:
        res = (
            db.table("users")
            .select("id, email")
            .eq("email", clean_email)
            .limit(1)
            .execute()
        )
    except Exception as ex:
        raise DatabaseError(f"Password reset lookup failed: {ex}")

    if not res.data:
        raise DatabaseError("No account found with that email address.")

    user_id = res.data[0]["id"]
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    try:
        db.table("users").update({
            "reset_otp": otp_code,
            "reset_otp_expires": expires_at,
        }).eq("id", user_id).execute()
    except Exception as ex:
        raise DatabaseError(f"Failed to store OTP: {ex}")

    _send_otp_email(clean_email, otp_code)


def _clear_otp(db: Client, user_id: str) -> None:
    try:
        db.table("users").update({
            "reset_otp": None,
            "reset_otp_expires": None,
        }).eq("id", user_id).execute()
    except Exception:
        pass


def reset_password_with_otp(email: str, otp_code: str, new_password: str) -> None:
    """Verifies non-expired OTP, updates password hash, and clears OTP fields."""
    clean_email = _normalize_email(email)
    clean_otp = (otp_code or "").strip()
    if not re.fullmatch(r"\d{6}", clean_otp):
        raise DatabaseError("Enter the 6-digit OTP code.")
    if not new_password or len(new_password) < 6:
        raise DatabaseError("New password must be at least 6 characters.")

    db = get_client()
    try:
        res = (
            db.table("users")
            .select("id, reset_otp, reset_otp_expires")
            .eq("email", clean_email)
            .limit(1)
            .execute()
        )
    except Exception as ex:
        raise DatabaseError(f"OTP verification failed: {ex}")

    if not res.data:
        raise DatabaseError("Invalid email or OTP.")

    row = res.data[0]
    user_id = row["id"]
    stored_otp = str(row.get("reset_otp") or "").strip()
    expires_raw = row.get("reset_otp_expires")

    if not stored_otp or not expires_raw:
        raise DatabaseError("No active OTP found. Request a new one.")

    try:
        exp_dt = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp_dt:
            _clear_otp(db, user_id)
            raise DatabaseError("OTP has expired. Request a new one.")
    except DatabaseError:
        raise
    except Exception:
        _clear_otp(db, user_id)
        raise DatabaseError("Invalid OTP expiry record. Request a new OTP.")

    if not secrets.compare_digest(stored_otp, clean_otp):
        raise DatabaseError("Invalid or expired OTP.")

    pw_hash, salt = _hash_password(new_password)
    try:
        db.table("users").update({
            "password_hash": f"{salt}${pw_hash}",
            "reset_otp": None,
            "reset_otp_expires": None,
        }).eq("id", user_id).execute()
    except Exception as ex:
        raise DatabaseError(f"Failed to update password: {ex}")

def verify_otp_and_reset_password(email: str, otp_code: str, new_password: str) -> None:
    """Alias wrapper for OTP verification and password reset expected by auth_view."""
    reset_password_with_otp(email=email, otp_code=otp_code, new_password=new_password)



# ---------------- TRIPS, MEMBERS & EXPENSES ----------------

def generate_unique_trip_code(length: int = 6, max_attempts: int = 10) -> str:
    """Generates a random trip code not currently in use."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    db = get_client()
    for _ in range(max_attempts):
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        try:
            existing = db.table("trips").select("id").eq("join_code", code).limit(1).execute()
            if not existing.data:
                return code
        except Exception:
            continue
    raise DatabaseError("Could not generate a unique trip code. Try again.")


def create_trip(
    trip_name: str,
    host_id: str,
    join_code: str,
    start_date: str | None = None,
    budget: float | None = None,
) -> dict:
    """Creates a new trip and adds the host to trip_members."""
    clean_host_id = _require_non_empty_id(host_id, "host")
    clean_name = _normalize_name(trip_name)
    clean_code = (join_code or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{6}", clean_code):
        raise DatabaseError("Invalid trip join code.")

    clean_budget = None
    if budget is not None:
        try:
            val = float(budget)
        except (TypeError, ValueError):
            raise DatabaseError("Budget must be a valid number.")
        if not math.isfinite(val) or val <= 0:
            raise DatabaseError("Budget must be a positive number.")
        clean_budget = round(val, 2)

    db = get_client()
    payload = {
        "trip_name": clean_name,
        "host_id": clean_host_id,
        "join_code": clean_code,
        "status": "active",
    }
    if start_date and start_date.strip():
        payload["start_date"] = start_date.strip()
    if clean_budget is not None:
        payload["budget"] = clean_budget

    try:
        res = db.table("trips").insert(payload).execute()
        if not res.data:
            raise DatabaseError("Failed to create trip.")
        created = res.data[0]
        db.table("trip_members").insert({
            "trip_id": created["id"],
            "user_id": clean_host_id,
        }).execute()
        return created
    except DatabaseError:
        raise
    except Exception as ex:
        raise DatabaseError(f"Could not create trip: {ex}")


def join_trip_by_code(join_code: str, user_id: str) -> dict:
    """Joins an active trip using its 6-character join code."""
    clean_uid = _require_non_empty_id(user_id, "user")
    clean_code = (join_code or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{6}", clean_code):
        raise DatabaseError("Enter a valid 6-character trip code.")

    db = get_client()
    try:
        trip_res = db.table("trips").select("*").eq("join_code", clean_code).limit(1).execute()
        if not trip_res.data:
            raise DatabaseError("No trip found with that code.")

        trip = trip_res.data[0]
        if trip.get("status") == "ended":
            raise DatabaseError("This trip has already ended and is locked.")

        if not _is_member_of_trip(db, trip["id"], clean_uid):
            db.table("trip_members").insert({
                "trip_id": trip["id"],
                "user_id": clean_uid,
            }).execute()
        return trip
    except DatabaseError:
        raise
    except Exception as ex:
        raise DatabaseError(f"Could not join trip: {ex}")


def get_user_trips(user_id: str) -> list[dict]:
    """Returns all trips where the user is a member, ordered newest first."""
    clean_uid = _require_non_empty_id(user_id, "user")
    db = get_client()
    try:
        mem_res = db.table("trip_members").select("trip_id").eq("user_id", clean_uid).execute()
        trip_ids = list({row["trip_id"] for row in (mem_res.data or []) if row.get("trip_id")})
        if not trip_ids:
            return []

        trips_res = db.table("trips").select("*").in_("id", trip_ids).order("created_at", desc=True).execute()
        return trips_res.data or []
    except Exception as ex:
        raise DatabaseError(f"Failed to load trips: {ex}")


def _fetch_members_for_trip(trip_id: str) -> list[dict]:
    db = get_client()
    mem_res = db.table("trip_members").select("user_id").eq("trip_id", trip_id).execute()
    user_ids = list({r["user_id"] for r in (mem_res.data or []) if r.get("user_id")})
    if not user_ids:
        return []
    users_res = db.table("users").select("id, name, username").in_("id", user_ids).execute()
    return [_sanitize_user(u) for u in (users_res.data or [])]


def _fetch_expenses_for_trip(trip_id: str) -> list[dict]:
    db = get_client()
    exp_res = (
        db.table("expenses")
        .select("*, users(id, name, username)")
        .eq("trip_id", trip_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = exp_res.data or []
    for r in rows:
        if isinstance(r.get("users"), dict):
            r["users"] = _sanitize_user(r["users"])
    return rows


def get_trip_full_data(trip_id: str, requester_user_id: str | None = None) -> dict:
    """Fetches trip metadata, members, and expenses in parallel."""
    clean_tid = _require_non_empty_id(trip_id, "trip")
    db = get_client()
    try:
        trip_res = db.table("trips").select("*").eq("id", clean_tid).limit(1).execute()
        if not trip_res.data:
            raise DatabaseError("Trip not found.")
        trip = trip_res.data[0]

        if requester_user_id:
            clean_uid = _require_non_empty_id(requester_user_id, "user")
            if not _is_member_of_trip(db, clean_tid, clean_uid):
                raise DatabaseError("You are not a member of this trip.")

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_members = pool.submit(_fetch_members_for_trip, clean_tid)
            f_expenses = pool.submit(_fetch_expenses_for_trip, clean_tid)
            members = f_members.result()
            expenses = f_expenses.result()

        return {"trip": trip, "members": members, "expenses": expenses}
    except DatabaseError:
        raise
    except Exception as ex:
        raise DatabaseError(f"Failed to load trip details: {ex}")


def add_expense(
    trip_id: str,
    user_id: str,
    amount: float,
    remarks: str,
    expense_date: str | None = None,
    expense_time: str | None = None,
) -> dict:
    """Adds an expense to an active trip for a valid member."""
    clean_tid = _require_non_empty_id(trip_id, "trip")
    clean_uid = _require_non_empty_id(user_id, "user")

    try:
        amt = float(amount)
    except (TypeError, ValueError):
        raise DatabaseError("Amount must be a valid number.")
    if not math.isfinite(amt) or amt <= 0 or amt > 100_000_000:
        raise DatabaseError("Enter a valid positive amount.")

    clean_remarks = " ".join((remarks or "").strip().split())
    if not clean_remarks or len(clean_remarks) > 160:
        raise DatabaseError("Please enter a valid remark (up to 160 characters).")

    db = get_client()
    try:
        trip_res = db.table("trips").select("id, status").eq("id", clean_tid).limit(1).execute()
        if not trip_res.data:
            raise DatabaseError("Trip not found.")
        if trip_res.data[0].get("status") != "active":
            raise DatabaseError("Cannot add expenses because this trip is already ended.")
        if not _is_member_of_trip(db, clean_tid, clean_uid):
            raise DatabaseError("Only trip members can add expenses.")

        payload = {
            "trip_id": clean_tid,
            "user_id": clean_uid,
            "amount": round(amt, 2),
            "remarks": clean_remarks,
        }
        if expense_date and expense_date.strip():
            payload["expense_date"] = expense_date.strip()
        if expense_time and expense_time.strip():
            payload["expense_time"] = expense_time.strip()

        res = db.table("expenses").insert(payload).execute()
        if not res.data:
            raise DatabaseError("Expense could not be saved.")
        return res.data[0]
    except DatabaseError:
        raise
    except Exception as ex:
        raise DatabaseError(f"Failed to add expense: {ex}")


def end_trip(trip_id: str, actor_user_id: str) -> dict:
    """Marks a trip as ended if actor_user_id is the trip host."""
    clean_tid = _require_non_empty_id(trip_id, "trip")
    clean_uid = _require_non_empty_id(actor_user_id, "user")
    db = get_client()
    try:
        trip_res = db.table("trips").select("*").eq("id", clean_tid).limit(1).execute()
        if not trip_res.data:
            raise DatabaseError("Trip not found.")
        trip = trip_res.data[0]
        if trip.get("host_id") != clean_uid:
            raise DatabaseError("Only the trip host can end this trip.")
        if trip.get("status") == "ended":
            return trip

        upd = (
            db.table("trips")
            .update({"status": "ended"})
            .eq("id", clean_tid)
            .eq("host_id", clean_uid)
            .execute()
        )
        return upd.data[0] if upd.data else {**trip, "status": "ended"}
    except DatabaseError:
        raise
    except Exception as ex:
        raise DatabaseError(f"Failed to end trip: {ex}")


def delete_trip(trip_id: str, actor_user_id: str) -> None:
    """Deletes a trip and its expenses/memberships if actor_user_id is the host."""
    clean_tid = _require_non_empty_id(trip_id, "trip")
    clean_uid = _require_non_empty_id(actor_user_id, "user")
    db = get_client()
    try:
        trip_res = db.table("trips").select("id, host_id").eq("id", clean_tid).limit(1).execute()
        if not trip_res.data:
            raise DatabaseError("Trip not found.")
        if trip_res.data[0].get("host_id") != clean_uid:
            raise DatabaseError("Only the trip host can delete this trip.")

        db.table("expenses").delete().eq("trip_id", clean_tid).execute()
        db.table("trip_members").delete().eq("trip_id", clean_tid).execute()
        deleted = (
            db.table("trips")
            .delete()
            .eq("id", clean_tid)
            .eq("host_id", clean_uid)
            .execute()
        )
        if not deleted.data:
            raise DatabaseError("Trip could not be deleted.")
    except DatabaseError:
        raise
    except Exception as ex:
        raise DatabaseError(f"Failed to delete trip: {ex}")