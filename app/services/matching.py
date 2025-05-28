from app.models.models import Receipt, ReceiptMatchLog
from app.core.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text


def matchingResult():
    sql = """
    SELECT DISTINCT r.receipt_number,
           CASE
               WHEN e."receiptNumber" IS NOT NULL THEN TRUE
               ELSE FALSE 
           END AS is_matched
    FROM receipts r
    LEFT JOIN excel_data e
      ON r.receipt_number = e."receiptNumber"
    """

    with SessionLocal() as session:
        results = session.execute(text(sql)).fetchall()

        for row in results:
            match_log = ReceiptMatchLog(
                receipt_number=row[0],
                is_matched=row[1]
            )
            session.add(match_log)

        session.commit()
        print("매칭 결과 저장 완료")



def fetch_results():
    with SessionLocal() as db:
        # 매칭된 영수증 번호 조회
        matched_sql = """
        SELECT DISTINCT r.*
        FROM receipts r
        JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
        WHERE rml.is_matched = TRUE
        """
        matched = db.execute(text(matched_sql)).fetchall()

        # 매칭되지 않은 영수증 번호 조회
        unmatched_sql = """
        SELECT DISTINCT r.*
        FROM receipts r
        JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
        WHERE rml.is_matched = FALSE
        """
        unmatched = db.execute(text(unmatched_sql)).fetchall()

        return matched, unmatched
    

matchingResult()