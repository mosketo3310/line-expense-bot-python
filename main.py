"""
LINE OA - บันทึกค่าใช้จ่ายจากรูปบิล/สลิป
Webhook: รับรูป -> ตอบทันที -> OCR + อัปโหลดสลิป + บันทึก DB ใน background
"""

import os
import logging
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, MessagingApiBlob,
    ReplyMessageRequest, PushMessageRequest, TextMessage,
)
from linebot.v3.webhooks import MessageEvent, ImageMessageContent
from ocr import extract_expense_from_image
from database import save_expense, upload_slip

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("expense-bot")

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET       = os.environ["LINE_CHANNEL_SECRET"]

app = FastAPI(title="LINE Expense Bot")
parser        = WebhookParser(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

THAI_MONTHS = ["","ม.ค.","ก.พ.","มี.ค.","เม.ย.","พ.ค.","มิ.ย.",
               "ก.ค.","ส.ค.","ก.ย.","ต.ค.","พ.ย.","ธ.ค."]


@app.get("/")
def health_check():
    return {"status": "ok", "service": "line-expense-bot"}


@app.post("/api/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str = Header(None, alias="X-Line-Signature"),
):
    body      = await request.body()
    body_text = body.decode("utf-8")

    if not x_line_signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    try:
        events = parser.parse(body_text, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, ImageMessageContent):
            _reply_processing(event.reply_token)
            background_tasks.add_task(process_image, event)

    return "OK"


def _reply_processing(reply_token: str):
    try:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="⏳ กำลังอ่านสลิปอยู่ครับ รอแป๊บนึง...")],
                )
            )
    except Exception:
        logger.exception("reply processing ล้มเหลว")


def process_image(event: MessageEvent):
    message_id = event.message.id
    user_id    = event.source.user_id if event.source else None

    if not user_id:
        return

    try:
        with ApiClient(configuration) as api_client:
            image_bytes = MessagingApiBlob(api_client).get_message_content(message_id)

            # OCR ก่อน — สำคัญกว่า upload รูป
            result = extract_expense_from_image(image_bytes)

            # upload รูป — ถ้าล้มเหลวก็ยังบันทึกข้อมูลได้
            try:
                slip_url = upload_slip(image_bytes, ext="jpg")
            except Exception as e:
                logger.warning(f"upload_slip ล้มเหลว (ไม่หยุด): {e}")
                slip_url = None

            if "rate limit" in result.get("shop", ""):
                text = "⚠️ ระบบโดน rate limit ชั่วคราวครับ\nกรุณาส่งรูปใหม่อีกครั้งใน 1 นาที"
            else:
                saved = save_expense(
                    date=result["date"],
                    amount=result["amount"],
                    time=result.get("time", ""),
                    slip_url=slip_url,
                    user_id=user_id,
                )
                text = build_reply_text(result, saved)

            MessagingApi(api_client).push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text=text)])
            )

    except Exception:
        logger.exception("process_image ล้มเหลว")
        try:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).push_message(
                    PushMessageRequest(to=user_id, messages=[TextMessage(
                        text="❌ เกิดข้อผิดพลาด กรุณาส่งรูปใหม่อีกครั้งครับ"
                    )])
                )
        except Exception:
            logger.exception("push error ล้มเหลว")


def build_reply_text(result: dict, saved: dict) -> str:
    if result["amount"] == 0.0:
        return "❌ อ่านข้อมูลจากรูปไม่สำเร็จครับ\nลองส่งรูปที่ชัดขึ้นครับ"

    day      = saved.get("day", "-")
    month    = saved.get("month", 0)
    year     = saved.get("year", "-")
    time_str = saved.get("time_str", "-")
    amount   = saved.get("amount", 0)
    month_th = THAI_MONTHS[month] if 1 <= month <= 12 else "-"

    return (
        "บันทึกค่าใช้จ่ายแล้วครับ ✅\n"
        f"วันที่: {day} {month_th} {year}\n"
        f"เวลา: {time_str} น.\n"
        f"ยอดเงิน: {amount:,.2f} บาท\n\n"
        "เช็คข้อมูลได้ที่เว็บ dashboard https://dashboard-eosin-ten-52.vercel.app/ ครับ\n"
        "ถ้าข้อมูลผิด แก้ไขในเว็บ dashboard ได้เลยครับ"
    )
