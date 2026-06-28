"""
อ่านข้อมูลจากรูปบิล/สลิป ด้วย Groq Vision (llama-4-scout)
ดึง วันที่ / เวลา / ยอดเงิน ออกมาแบบอัตโนมัติ
"""

import os
import json
import base64
import logging
import time
from datetime import datetime
from io import BytesIO

from PIL import Image
from groq import Groq

logger = logging.getLogger("expense-bot")

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
client = Groq(api_key=GROQ_API_KEY)

MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"

MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]

PROMPT = """คุณคือ AI ผู้เชี่ยวชาญอ่านบิลและสลิปโอนเงิน (ภาษาไทยและอังกฤษ)
จากรูปที่ได้รับ ให้ดึงข้อมูลต่อไปนี้แล้วตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:

{"amount": <float>, "date": <dd/mm/yyyy หรือ dd/mm/yy>, "time": <HH:MM หรือ "">}

กฎ amount:
- ใช้ ยอดรวม / ยอดสุทธิ / total / จำนวน เท่านั้น
- ห้ามใช้ เงินสด / cash / เงินทอน / change
- เป็น float เท่านั้น ไม่มีหน่วย

กฎ date: อ่านวันที่ตามที่ปรากฏบนสลิปจริง ๆ ห้ามแปลงปีเอง (ระบบจะแปลงปีให้เองภายหลัง)
- ตอบกลับเป็น dd/mm/yyyy หรือ dd/mm/yy ตามจำนวนหลักของปีที่เห็นจริงบนสลิป
- ปีอาจเป็น ค.ศ. 4 หลัก (เช่น 2025), พ.ศ. 4 หลัก (เช่น 2568) หรือ พ.ศ. แบบย่อ 2 หลัก (เช่น 68, 69) ก็ได้ ให้ใส่ตัวเลขปีตามที่เห็นเป๊ะๆ
ตัวอย่าง:
- สลิปเขียน "6 มิ.ย 69"      -> ตอบ "06/06/69"
- สลิปเขียน "6/6/2569"       -> ตอบ "06/06/2569"
- สลิปเขียน "06/06/2025"     -> ตอบ "06/06/2025"

กฎ time: อ่านเวลาจากสลิปโดยตรง รูปแบบ HH:MM (24 ชม.) ถ้าไม่มีให้ใส่ ""

ตอบ JSON บริสุทธิ์ ไม่มี markdown"""


def _image_to_base64(image_bytes: bytes) -> str:
    image = Image.open(BytesIO(image_bytes))
    max_size = 1280
    if max(image.size) > max_size:
        image.thumbnail((max_size, max_size), Image.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def extract_expense_from_image(image_bytes: bytes) -> dict:
    today_str = datetime.now().strftime("%d/%m/%Y")

    try:
        image_b64 = _image_to_base64(image_bytes)
    except Exception as e:
        logger.error(f"เปิดรูปไม่ได้: {e}")
        return _fallback_result(today_str)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        {"type": "text", "text": PROMPT},
                    ],
                }],
                max_tokens=256,
                temperature=0,
            )

            raw_text = response.choices[0].message.content.strip()
            raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            logger.info(f"Groq response: {raw_text}")

            parsed = json.loads(raw_text)
            return {
                "amount":   float(parsed.get("amount", 0.0)),
                "date":     str(parsed.get("date", today_str)),
                "time":     str(parsed.get("time", "")),
                "raw_text": raw_text,
                "shop":     "",
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON ผิดรูปแบบ: {e} | raw: {raw_text!r}")
            return _fallback_result(today_str)

        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "429" in err_str or "rate_limit" in err_str or "too many" in err_str:
                wait = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 30
                logger.warning(f"rate limit attempt {attempt+1}/{MAX_RETRIES} รอ {wait}s...")
                time.sleep(wait)
                continue
            logger.error(f"เรียก Groq ไม่สำเร็จ: {e}")
            return _fallback_result(today_str)

    logger.error(f"หมด retry: {last_error}")
    return _fallback_result(today_str, rate_limited=True)


def _fallback_result(today_str: str, rate_limited: bool = False) -> dict:
    shop = "อ่านข้อมูลไม่สำเร็จ (rate limit)" if rate_limited else "อ่านข้อมูลไม่สำเร็จ"
    return {"amount": 0.0, "date": today_str, "time": "", "raw_text": "", "shop": shop}
