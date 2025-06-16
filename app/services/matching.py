from app.models.models import Receipt, ReceiptMatchLog, User, DutyFreeType, ShillaReceipt
from app.core.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text


def matchingResult(user_id):
    """롯데 면세점 매칭 로직 - 여권 정보 포함"""
    sql = """
    SELECT DISTINCT 
        r.receipt_number,
        CASE
            WHEN e."receiptNumber" IS NOT NULL THEN TRUE
            ELSE FALSE 
        END AS is_matched,
        e.name as excel_name,
        p.passport_number,
        p.birthday
    FROM receipts r
    LEFT JOIN lotte_excel_data e ON r.receipt_number = e."receiptNumber"
    LEFT JOIN passports p ON e.name = p.name AND p.user_id = :user_id
    WHERE r.user_id = :user_id
    """

    with SessionLocal() as session:
        results = session.execute(text(sql), {"user_id": user_id}).fetchall()
        print(f"매칭 처리할 영수증: {len(results)}개")

        # 1단계: 영수증 매칭 로그 저장 (여권 정보 포함)
        for row in results:
            receipt_number, is_matched, excel_name, passport_number, birthday = row
            print(f"영수증: {receipt_number}, 매칭: {is_matched}, 이름: {excel_name}, 여권번호: {passport_number}")
            
            match_log = ReceiptMatchLog(
                user_id=user_id,
                receipt_number=receipt_number,
                is_matched=is_matched,
                excel_name=excel_name if is_matched else None,
                passport_number=passport_number if is_matched else None,
                birthday=birthday if is_matched else None
            )
            session.add(match_log)

        # 먼저 영수증 매칭 로그 커밋
        session.commit()
        print("영수증 매칭 로그 저장 완료")

        # 2단계: 여권 매칭 상태 업데이트
        passport_update_sql = """
        UPDATE passports p
        SET is_matched = TRUE
        FROM lotte_excel_data e
        WHERE p.name = e.name 
        AND p.user_id = :user_id
        AND e."receiptNumber" IN (
            SELECT rml.receipt_number 
            FROM receipt_match_log rml 
            WHERE rml.user_id = :user_id AND rml.is_matched = TRUE
        )
        """
        updated_passports = session.execute(text(passport_update_sql), {"user_id": user_id}).rowcount
        print(f"여권 매칭 상태 업데이트: {updated_passports}개")

        session.commit()
        print("롯데 매칭 결과 저장 완료")


def fetch_results(user_id, duty_free_type="lotte"):
    """면세점 타입에 따라 적절한 결과 반환"""
    with SessionLocal() as db:
        if duty_free_type == "shilla":
            # 신라 면세점 결과 조회
            from app.services.shilla_matching import fetch_shilla_results_with_receipt_ids
            return fetch_shilla_results_with_receipt_ids(user_id)
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