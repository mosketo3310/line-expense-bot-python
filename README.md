# LINE OA บันทึกค่าใช้จ่าย (เวอร์ชัน Python + Gemini Flash)

Stack: FastAPI + line-bot-sdk + **Gemini Flash Vision** + Supabase + Render

## สิ่งที่เปลี่ยนแปลงจากเวอร์ชันเดิม

| เดิม (Tesseract) | ใหม่ (Gemini Flash) |
|---|---|
| `pytesseract` + regex | `google-generativeai` + Gemini prompt |
| ต้องลง Tesseract binary ใน Docker | ไม่ต้อง — แค่ pip install |
| แยก OCR กับ parse ออกจากกัน | Gemini อ่านและดึงข้อมูลพร้อมกันในครั้งเดียว |
| อาจอ่านภาษาไทยได้ไม่ดี | Gemini รองรับภาษาไทยได้ดีกว่ามาก |

## Environment Variables ที่ต้องตั้งค่า

```
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...
SUPABASE_URL=...
SUPABASE_KEY=...
GEMINI_API_KEY=...        ← อันใหม่ที่ต้องเพิ่ม
```

รับ GEMINI_API_KEY ได้ฟรีที่: https://aistudio.google.com/app/apikey

## รันทดสอบในเครื่องตัวเอง

```bash
pip install -r requirements.txt
cp .env.example .env   # แล้วใส่ค่าจริง (รวม GEMINI_API_KEY)
uvicorn main:app --reload
```

## ไฟล์ในโปรเจกต์

- `main.py` — FastAPI webhook รับรูปจาก LINE
- `ocr.py` — อ่านรูปและดึงข้อมูลด้วย Gemini Flash Vision
- `database.py` — บันทึก/อ่านข้อมูลผ่าน Supabase
- `requirements.txt` — Python dependencies
- `Dockerfile` — สำหรับ deploy บน Render (เล็กลงมากเพราะไม่ต้อง Tesseract)
- `render.yaml` — Render blueprint
- `supabase_schema.sql` — สร้างตาราง `expenses` ใน Supabase
