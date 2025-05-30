from app.models.models import Receipt, ReceiptMatchLog, User, DutyFreeType, ShillaReceipt
from app.core.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text


def matchingResult(user_id):
    """롯데 면세점 매칭 로직 - 컬럼명 수정"""
    sql = """
    SELECT DISTINCT r.receipt_number,
           CASE
               WHEN e."receiptNumber" IS NOT NULL THEN TRUE
               ELSE FALSE 
           END AS is_matched
    FROM receipts r
    LEFT JOIN lotte_excel_data e
      ON r.receipt_number = e."receiptNumber"
    WHERE r.user_id = :user_id
    """

    with SessionLocal() as session:
        results = session.execute(text(sql), {"user_id": user_id}).fetchall()

        for row in results:
            match_log = ReceiptMatchLog(
                user_id=user_id,
                receipt_number=row[0],
                is_matched=row[1]
            )
            session.add(match_log)

        session.commit()
        print("롯데 매칭 결과 저장 완료")


def fetch_results(user_id):
    """사용자의 면세점 타입에 따라 적절한 결과 반환"""
    with SessionLocal() as db:
        # 사용자 조회
        user = db.query(User).filter(User.id == user_id).first()
        
        if user.duty_free_type == DutyFreeType.SHILLA:
            # 신라 면세점 결과 조회
            from app.services.shilla_matching import fetch_shilla_results
            return fetch_shilla_results(user_id)
        else:
            # 롯데 면세점 결과 조회
            # 사용자별 매칭된 영수증 번호 조회
            matched_sql = """
            SELECT DISTINCT r.*
            FROM receipts r
            JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
            WHERE rml.is_matched = TRUE AND r.user_id = :user_id AND rml.user_id = :user_id
            """
            matched = db.execute(text(matched_sql), {"user_id": user_id}).fetchall()

            # 사용자별 매칭되지 않은 영수증 번호 조회
            unmatched_sql = """
            SELECT DISTINCT r.*
            FROM receipts r
            JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
            WHERE rml.is_matched = FALSE AND r.user_id = :user_id AND rml.user_id = :user_id
            """
            unmatched = db.execute(text(unmatched_sql), {"user_id": user_id}).fetchall()

            return matched, unmatched
        
