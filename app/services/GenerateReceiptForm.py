from sqlalchemy import text
from app.core.database import SessionLocal
import openpyxl
import shutil
import os
from openpyxl.styles import Alignment
from datetime import datetime

def get_matched_name_and_payback():
    TEMPLATE_PATH = "/Users/gimdonghun/Downloads/수령증양식.xlsx"
    OUTPUT_DIR = "/Users/gimdonghun/Downloads/수령증_완성본"
    
    # 기존 디렉토리가 있다면 삭제
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 두 테이블 비교해서 view테이블에서 조회만 할 수 있게 하기
    sql1 = """
    SELECT e."name", e."PayBack"
    FROM excel_data e
    JOIN receipt_match_log m
    ON e."receiptNumber" = m.receipt_number
    WHERE m.is_matched = TRUE;
    """

    sql2 = """
    SELECT p.passport_number, p.birthday, p.name
    FROM passports p
    WHERE p.name = :name;
    """

    with SessionLocal() as session:
        results = session.execute(text(sql1)).fetchall()
        printed_people = set()

        for name, payback in results:
            passport_result = session.execute(
                text(sql2), {"name": name}
            ).fetchone()

            if passport_result:
                passport_number, birthday, name= passport_result
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
                ws["D7"].alignment = alignment # 가운데 정렬
                ws["D8"] = passport_number
                ws["D8"].alignment = alignment # 가운데 정렬
                ws["D9"] = birthday
                ws["D9"].alignment = alignment # 가운데 정렬
                ws["D10"] = payback # 테스트
                ws["D10"].alignment = alignment # 가운데 정렬
                today = datetime.today()
                formatted_date = f"{today.year}년    {today.month:02}월    {today.day:02}일"
                ws["B16"] = formatted_date
                ws["B16"].alignment = alignment  # 가운데 정렬
                wb.save(output_path)
                
    return OUTPUT_DIR