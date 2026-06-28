"""
บันทึก/อ่านข้อมูลค่าใช้จ่ายผ่าน Supabase
เก็บ: วัน / เดือน / ปี / เวลา (จากสลิป) / ยอดเงิน / URL รูปสลิป
"""

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta

from supabase import create_client, Client

logger = logging.getLogger("expense-bot")

TZ_BANGKOK = timezone(timedelta(hours=7))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLE_NAME  = "expenses"
BUCKET_NAME = "slips"


def upload_slip(image_bytes: bytes, ext: str = "jpg") -> str | None:
    try:
        filename = f"{uuid.uuid4().hex}.{ext}"
        supabase.storage.from_(BUCKET_NAME).upload(
            path=filename,
            file=image_bytes,
            file_options={"content-type": f"image/{ext}"},
        )
        return supabase.storage.from_(BUCKET_NAME).get_public_url(filename)
    except Exception as e:
        logger.error(f"upload_slip ล้มเหลว: {e}")
        return None


def _to_christian_year(year: int) -> int:
    """
    แปลงปีจากสลิปให้เป็น ค.ศ. (Gregorian) เสมอ ไม่ว่าสลิปจะเขียนปีแบบไหนมา:
      - ค.ศ. 4 หลัก      เช่น 2024, 2025      -> คืนค่าเดิม (ไม่แปลง)
      - พ.ศ. 4 หลัก      เช่น 2567, 2569      -> ลบ 543  -> 2024, 2026
      - พ.ศ. แบบย่อ 2 หลัก เช่น 67, 69          -> สลิปไทยมักย่อปีแบบนี้เป็น พ.ศ. เสมอ
                                                  (เช่น "6 มิ.ย 69" หมายถึง พ.ศ. 2569)
                                                  เติมเป็น พ.ศ. 4 หลักก่อน (2500 + yy) แล้วลบ 543
                                                  -> 67 -> 2024, 69 -> 2026
    """
    if year < 100:
        year += 2500       # เติมให้เป็น พ.ศ. 4 หลัก (ปี 2 หลักบนสลิปไทยคือ พ.ศ. เสมอ)
    if year > 2500:
        year -= 543         # พ.ศ. 4 หลัก -> ค.ศ.
    return year


def save_expense(
    date: str,
    amount: float,
    time: str = "",
    slip_url: str | None = None,
    user_id: str | None = None,
    **_,
) -> dict:
    now = datetime.now(TZ_BANGKOK)

    try:
        day, month, year = [int(x) for x in date.split("/")]
        year = _to_christian_year(year)
    except Exception:
        day, month, year = now.day, now.month, now.year

    # ใช้เวลาจากสลิปถ้าอ่านได้ ไม่งั้น fallback เวลาปัจจุบัน
    time_str = time.strip() if time and time.strip() else now.strftime("%H:%M")

    payload = {
        "day":        day,
        "month":      month,
        "year":       year,
        "time_str":   time_str,
        "amount":     amount,
        "slip_url":   slip_url,
        "user_id":    user_id,
        "created_at": now.isoformat(),
    }

    response = supabase.table(TABLE_NAME).insert(payload).execute()
    return response.data[0] if response.data else payload


def list_recent_expenses(limit: int = 10) -> list[dict]:
    response = (
        supabase.table(TABLE_NAME)
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data
