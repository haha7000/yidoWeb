from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Integer
from app.models.models import ReceiptMatchLog, ShillaReceipt

def get_dashboard_stats(db: Session, user_id: int) -> dict:
    """
    사용자별 대시보드 통계 데이터를 조회합니다.
    """
    try:
        # 롯데 통계: receipt_match_log에서 집계
        lotte_stats = db.query(
            func.count(ReceiptMatchLog.id).label("total"),
            func.sum(cast(ReceiptMatchLog.is_matched, Integer)).label("matched"),
            func.sum(ReceiptMatchLog.commission_fee).label("commission")
        ).filter(
            ReceiptMatchLog.user_id == user_id,
            ReceiptMatchLog.duty_free_type == 'lotte'
        ).first()

        # 신라 통계: receipt_match_log에서 집계
        shilla_stats = db.query(
            func.count(ReceiptMatchLog.id).label("total"),
            func.sum(cast(ReceiptMatchLog.is_matched, Integer)).label("matched"),
            func.sum(ReceiptMatchLog.commission_fee).label("commission")
        ).filter(
            ReceiptMatchLog.user_id == user_id,
            ReceiptMatchLog.duty_free_type == 'shilla'
        ).first()

        lotte_total = lotte_stats.total if lotte_stats and lotte_stats.total else 0
        lotte_matched = lotte_stats.matched if lotte_stats and lotte_stats.matched else 0
        lotte_commission = lotte_stats.commission if lotte_stats and lotte_stats.commission else 0

        shilla_total = shilla_stats.total if shilla_stats and shilla_stats.total else 0
        shilla_matched = shilla_stats.matched if shilla_stats and shilla_stats.matched else 0
        shilla_commission = shilla_stats.commission if shilla_stats and shilla_stats.commission else 0

        total_receipts = lotte_total + shilla_total
        matched_receipts = lotte_matched + shilla_matched
        total_commission = (lotte_commission or 0) + (shilla_commission or 0)

        match_rate = (matched_receipts / total_receipts * 100) if total_receipts > 0 else 0

        return {
            "total_receipts": total_receipts,
            "matched_receipts": matched_receipts,
            "match_rate": match_rate,
            "total_commission": total_commission,
            "lotte_receipts": lotte_total,
            "shilla_receipts": shilla_total,
        }
    except Exception as e:
        print(f"대시보드 통계 조회 오류: {e}")
        db.rollback()
        return {
            "total_receipts": 0,
            "matched_receipts": 0,
            "match_rate": 0,
            "total_commission": 0,
            "lotte_receipts": 0,
            "shilla_receipts": 0,
        }
