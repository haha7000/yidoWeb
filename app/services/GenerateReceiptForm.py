# app/services/GenerateReceiptForm.py 수정

from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.models import User, DutyFreeType
import openpyxl
import shutil
import os
from openpyxl.styles import Alignment
from datetime import datetime

def get_matched_name_and_payback(user_id):
    TEMPLATE_PATH = "/Users/gimdonghun/Downloads/수령증양식.xlsx"
    OUTPUT_DIR = "/Users/gimdonghun/Downloads/수령증_완성본"
    
    # 기존 디렉토리가 있다면 삭제
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with SessionLocal() as session:
        # 사용자의 면세점 타입 확인
        user = session.query(User).filter(User.id == user_id).first()
        
        if user.duty_free_type == DutyFreeType.LOTTE:
            # 롯데 면세점 데이터 조회 (동적 테이블)
            sql1 = """
            SELECT e.name, e."PayBack"
            FROM lotte_excel_data e
            JOIN receipt_match_log m
            ON e."receiptNumber" = m.receipt_number
            WHERE m.is_matched = TRUE AND m.user_id = :user_id;
            """
        else:
            # 신라 면세점 데이터 조회 (동적 테이블)
            sql1 = """
            SELECT e.name, e."PayBack"
            FROM shilla_excel_data e
            JOIN receipt_match_log m
            ON e."receiptNumber" = m.receipt_number
            WHERE m.is_matched = TRUE AND m.user_id = :user_id;
            """

        sql2 = """
        SELECT p.passport_number, p.birthday, p.name
        FROM passports p
        WHERE p.name = :name AND p.user_id = :user_id;
        """

        try:
            results = session.execute(text(sql1), {"user_id": user_id}).fetchall()
        except Exception as e:
            print(f"엑셀 데이터 조회 오류: {e}")
            # 테이블이 없는 경우 빈 결과 반환
            results = []
            
        printed_people = set()

        for name, payback in results:
            try:
                passport_result = session.execute(
                    text(sql2), {"name": name, "user_id": user_id}
                ).fetchone()

                if passport_result:
                    passport_number, birthday, name = passport_result
                    person = (name, payback, passport_number, birthday)

                    if person in printed_people:
                        continue
                    printed_people.add(person)

                    output_path = os.path.join(OUTPUT_DIR, f"{name}_수령증.xlsx")
                    shutil.copy(TEMPLATE_PATH, output_path)

                    wb = openpyxl.load_workbook(output_path)
                    ws = wb.active
                    alignment = Alignment(horizontal="center", vertical="center")
                    ws["D7"] = name
                    ws["D7"].alignment = alignment
                    ws["D8"] = passport_number
                    ws["D8"].alignment = alignment
                    ws["D9"] = birthday
                    ws["D9"].alignment = alignment
                    ws["D10"] = payback
                    ws["D10"].alignment = alignment
                    today = datetime.today()
                    formatted_date = f"{today.year}년    {today.month:02}월    {today.day:02}일"
                    ws["B16"] = formatted_date
                    ws["B16"].alignment = alignment
                    wb.save(output_path)
            except Exception as e:
                print(f"개별 수령증 생성 오류: {e}")
                continue
                
    return OUTPUT_DIR