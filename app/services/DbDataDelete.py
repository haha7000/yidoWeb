from app.core.database import SessionLocal
from app.models.models import Receipt, Passport, ReceiptMatchLog, UnrecognizedImage

with SessionLocal() as db:
    db.query(Receipt).delete()
    db.query(Passport).delete()
    db.query(ReceiptMatchLog).delete()
    db.query(UnrecognizedImage).delete()
    db.commit()