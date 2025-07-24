import os
import shutil
import tempfile
import time
import zipfile
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, Request, Depends, File, Form, UploadFile, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text, create_engine, Text, Numeric, BigInteger, Integer, String

from app.core.auth import get_current_user
from app.core.database import get_db, SQLALCHEMY_DATABASE_URL
from app.core.config import settings
from app.models.models import User, DutyFreeType
from app.services.LotteFinder import LotteAiOcr
from app.services.ShillaFinder import ShillaAiOcr
from app.services.matching import matchingResult, fetch_results
from app.services.passportMatching import matching_passport
from app.services.shilla_matching import shilla_matching_result

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# 진행 상황 추적을 위한 전역 변수
progress = {"done": 0, "total": 0}

def fix_excel_datetime_format(excel_path):
    """
    엑셀 파일에서 잘못된 날짜 형식(20250222T000000)을 올바른 형식으로 수정
    """
    import tempfile
    import zipfile
    import xml.etree.ElementTree as ET
    
    try:
        # 임시 디렉토리 생성
        temp_dir = tempfile.mkdtemp()
        
        # 엑셀 파일을 ZIP으로 복사
        excel_as_zip = os.path.join(temp_dir, "excel_as_zip.zip")
        shutil.copy2(excel_path, excel_as_zip)
        
        # ZIP 파일 압축 해제
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir)
        
        with zipfile.ZipFile(excel_as_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # 수정된 항목 개수
        modified_count = 0
        
        # 1. sharedStrings.xml 파일 찾기 및 수정
        shared_strings_path = os.path.join(extract_dir, "xl", "sharedStrings.xml")
        
        if os.path.exists(shared_strings_path):
            print(f"sharedStrings.xml 파일 발견, 날짜 형식 수정 중...")
            
            # XML 파일 읽기
            tree = ET.parse(shared_strings_path)
            root = tree.getroot()
            
            # 네임스페이스 정의
            namespace = {'': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            
            # 모든 문자열 항목 검사
            for si in root.findall('.//si', namespace):
                t_elem = si.find('.//t', namespace)
                if t_elem is not None and t_elem.text:
                    text_content = t_elem.text.strip()
                    
                    # 잘못된 날짜 형식 패턴 감지 (예: 20250222T000000)
                    if len(text_content) == 15 and 'T' in text_content and text_content.endswith('000000'):
                        try:
                            # 20250222T000000 -> 2025-02-22T00:00:00 형식으로 변환
                            date_part = text_content.split('T')[0]  # 20250222
                            if len(date_part) == 8 and date_part.isdigit():
                                year = date_part[:4]
                                month = date_part[4:6]  
                                day = date_part[6:8]
                                
                                # 유효한 날짜인지 확인
                                datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                                
                                # 올바른 형식으로 변경
                                new_text = f"{year}-{month}-{day}T00:00:00"
                                t_elem.text = new_text
                                modified_count += 1
                                print(f"sharedStrings 날짜 형식 수정: {text_content} -> {new_text}")
                                
                        except ValueError:
                            # 유효하지 않은 날짜면 원본 유지
                            continue
            
            if modified_count > 0:
                # 수정된 XML 저장
                tree.write(shared_strings_path, encoding='utf-8', xml_declaration=True)
                print(f"sharedStrings에서 {modified_count}개 날짜 형식 수정 완료")
        else:
            print("sharedStrings.xml 파일을 찾을 수 없습니다.")
        
        # 2. 워크시트 파일들에서 날짜 형식 수정
        worksheets_dir = os.path.join(extract_dir, "xl", "worksheets")
        if os.path.exists(worksheets_dir):
            print(f"워크시트 파일에서 날짜 형식 수정 중...")
            
            for worksheet_file in os.listdir(worksheets_dir):
                if worksheet_file.endswith('.xml'):
                    worksheet_path = os.path.join(worksheets_dir, worksheet_file)
                    
                    try:
                        # 워크시트 XML 파일 읽기
                        tree = ET.parse(worksheet_path)
                        root = tree.getroot()
                        
                        # 네임스페이스 정의
                        namespace = {'': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        
                        # 모든 값(v) 태그 검사
                        worksheet_modified = 0
                        for v in root.findall('.//v', namespace):
                            if v.text and len(v.text) == 15 and 'T' in v.text and v.text.endswith('000000'):
                                try:
                                    # 20250222T000000 -> 2025-02-22T00:00:00 형식으로 변환
                                    date_part = v.text.split('T')[0]  # 20250222
                                    if len(date_part) == 8 and date_part.isdigit():
                                        year = date_part[:4]
                                        month = date_part[4:6]  
                                        day = date_part[6:8]
                                        
                                        # 유효한 날짜인지 확인
                                        datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                                        
                                        # 올바른 형식으로 변경
                                        new_text = f"{year}-{month}-{day}T00:00:00"
                                        old_text = v.text
                                        v.text = new_text
                                        worksheet_modified += 1
                                        modified_count += 1
                                        print(f"워크시트 날짜 형식 수정: {old_text} -> {new_text}")
                                        
                                except ValueError:
                                    # 유효하지 않은 날짜면 원본 유지
                                    continue
                        
                        if worksheet_modified > 0:
                            # 수정된 워크시트 XML 저장
                            tree.write(worksheet_path, encoding='utf-8', xml_declaration=True)
                            print(f"{worksheet_file}에서 {worksheet_modified}개 날짜 형식 수정 완료")
                    
                    except Exception as e:
                        print(f"워크시트 {worksheet_file} 처리 중 오류: {e}")
                        continue
        
        if modified_count > 0:
            # 수정된 파일들을 다시 ZIP으로 압축
            fixed_excel_path = os.path.join(temp_dir, f"fixed_{os.path.basename(excel_path)}")
            
            with zipfile.ZipFile(fixed_excel_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                for root_dir, dirs, files in os.walk(extract_dir):
                    for file in files:
                        file_path = os.path.join(root_dir, file)
                        arcname = os.path.relpath(file_path, extract_dir)
                        zip_ref.write(file_path, arcname)
            
            print(f"수정된 엑셀 파일 생성: {fixed_excel_path}")
            print(f"총 {modified_count}개 날짜 형식 수정 완료")
            return fixed_excel_path
        else:
            print("수정할 날짜 형식이 없습니다.")
            return None
            
    except Exception as e:
        print(f"날짜 형식 수정 중 오류 발생: {e}")
        return None


def generate_upload_id() -> str:
    """업로드 세션용 고유 ID 생성"""
    import uuid
    return str(uuid.uuid4())


def assign_upload_id_to_data(user_id: int, upload_id: str, db: Session):
    """처리된 데이터에 업로드 ID 할당"""
    try:
        # 롯데 데이터 업데이트
        lotte_update_sql = text("""
            UPDATE receipts 
            SET upload_id = :upload_id 
            WHERE user_id = :user_id AND upload_id IS NULL
        """)
        
        # 신라 데이터 업데이트  
        shilla_update_sql = text("""
            UPDATE shilla_receipts 
            SET upload_id = :upload_id 
            WHERE user_id = :user_id AND upload_id IS NULL
        """)
        
        # 여권 데이터 업데이트
        passport_update_sql = text("""
            UPDATE passports 
            SET upload_id = :upload_id 
            WHERE user_id = :user_id AND upload_id IS NULL
        """)
        
        # 실행
        db.execute(lotte_update_sql, {"upload_id": upload_id, "user_id": user_id})
        db.execute(shilla_update_sql, {"upload_id": upload_id, "user_id": user_id})
        db.execute(passport_update_sql, {"upload_id": upload_id, "user_id": user_id})
        db.commit()
        
        print(f"업로드 ID {upload_id} 할당 완료 (사용자 {user_id})")
        
    except Exception as e:
        print(f"업로드 ID 할당 중 오류: {e}")
        db.rollback()


def calculate_fully_matched_customers(user_id: int, duty_free_type: str, db: Session) -> int:
    """영수증과 여권이 모두 매칭된 고객 수 계산"""
    try:
        if duty_free_type == "lotte":
            sql = text("""
                SELECT COUNT(DISTINCT rml.excel_name) 
                FROM receipt_match_log rml
                JOIN passports p ON LOWER(TRIM(rml.excel_name)) = LOWER(TRIM(p.name))
                WHERE rml.user_id = :user_id 
                AND p.user_id = :user_id
                AND rml.is_matched = TRUE
                AND rml.excel_name IS NOT NULL 
                AND rml.excel_name != ''
                AND p.name IS NOT NULL 
                AND p.name != ''
            """)
        else:  # shilla
            sql = text("""
                SELECT COUNT(DISTINCT se.name) 
                FROM shilla_receipts sr
                JOIN shilla_excel_data se ON sr.receipt_number = se."receiptNumber"::text
                JOIN passports p ON LOWER(TRIM(se.name)) = LOWER(TRIM(p.name))
                WHERE sr.user_id = :user_id 
                AND p.user_id = :user_id
                AND se.name IS NOT NULL 
                AND se.name != ''
                AND p.name IS NOT NULL 
                AND p.name != ''
            """)
        
        result = db.execute(sql, {"user_id": user_id})
        return result.scalar() or 0
        
    except Exception as e:
        print(f"완전 매칭 고객 수 계산 오류: {e}")
        db.rollback()  # 트랜잭션 롤백
        return 0


def calculate_passport_statistics(user_id: int, duty_free_type: str, db: Session) -> dict:
    """여권 통계 계산"""
    try:
        # 전체 여권 수
        total_sql = text("SELECT COUNT(*) FROM passports WHERE user_id = :user_id")
        total_passports = db.execute(total_sql, {"user_id": user_id}).scalar() or 0
        
        # 매칭된 여권 수
        if duty_free_type == "lotte":
            matched_sql = text("""
                SELECT COUNT(DISTINCT p.id) 
                FROM passports p
                JOIN receipt_match_log rml ON LOWER(TRIM(p.name)) = LOWER(TRIM(rml.excel_name))
                WHERE p.user_id = :user_id AND rml.user_id = :user_id
                AND rml.is_matched = TRUE
                AND p.name IS NOT NULL AND p.name != ''
                AND rml.excel_name IS NOT NULL AND rml.excel_name != ''
            """)
        else:  # shilla
            matched_sql = text("""
                SELECT COUNT(DISTINCT p.id) 
                FROM passports p
                JOIN shilla_receipts sr ON sr.user_id = p.user_id
                JOIN shilla_excel_data se ON sr.receipt_number = se."receiptNumber"::text
                WHERE p.user_id = :user_id AND sr.user_id = :user_id
                AND LOWER(TRIM(p.name)) = LOWER(TRIM(se.name))
                AND p.name IS NOT NULL AND p.name != ''
                AND se.name IS NOT NULL AND se.name != ''
            """)
        
        matched_passports = db.execute(matched_sql, {"user_id": user_id}).scalar() or 0
        unmatched_passports = total_passports - matched_passports
        
        return {
            "total_passports": total_passports,
            "matched_passports": matched_passports,
            "unmatched_passports": unmatched_passports
        }
        
    except Exception as e:
        print(f"여권 통계 계산 오류: {e}")
        db.rollback()  # 트랜잭션 롤백
        return {
            "total_passports": 0,
            "matched_passports": 0,
            "unmatched_passports": 0
        }


@router.get("/upload/")
def form(
    request: Request, 
    completed: bool = False,
    current_user: User = Depends(get_current_user)
):
    """업로드 페이지 - 완료 메시지 지원"""
    context = {
        "request": request,
        "user": current_user
    }
    
    if completed:
        context["success_message"] = "이전 세션이 성공적으로 완료되었습니다. 새로운 처리를 시작하세요."
    
    return templates.TemplateResponse("input.html", context)


@router.post("/upload-excel/")
async def upload_excel(
    excel_file: UploadFile = File(...),
    duty_free_type: str = Form(...),  # 폼에서 면세점 타입 받기
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tmp_path = None
    try:
        start_time = time.time()
        
        # openpyxl 날짜 파싱 오류 우회를 위한 강력한 패치
        try:
            # 모든 가능한 경로에서 패치 적용
            import openpyxl.utils.datetime
            from openpyxl.utils.datetime import from_ISO8601
            from openpyxl.worksheet._reader import WorksheetReader
            
            original_from_ISO8601 = from_ISO8601
            
            def patched_from_ISO8601(formatted_string):
                try:
                    return original_from_ISO8601(formatted_string)
                except ValueError as e:
                    if "Invalid datetime value" in str(e):
                        # 잘못된 날짜 형식을 문자열로 반환
                        print(f"⚠️ 잘못된 날짜 형식을 문자열로 처리: {formatted_string}")
                        return str(formatted_string)
                    else:
                        raise e
            
            # 모든 경로에 패치 적용
            openpyxl.utils.datetime.from_ISO8601 = patched_from_ISO8601
            
            # WorksheetReader에서도 사용하는 경우 대비
            if hasattr(WorksheetReader, 'from_ISO8601'):
                WorksheetReader.from_ISO8601 = patched_from_ISO8601
            
            print("✅ openpyxl 강력한 날짜 파싱 패치 적용 완료")
        except Exception as patch_error:
            print(f"⚠️ openpyxl 패치 실패 (계속 진행): {patch_error}")
        
        # 추가: pandas에서 엑셀 엔진을 강제로 openpyxl 대신 다른 방법 사용
        import warnings
        warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
        
        # 면세점 타입 변환
        duty_free_enum = DutyFreeType.LOTTE if duty_free_type == "lotte" else DutyFreeType.SHILLA
        
        # 엑셀 파일 임시 저장
        import tempfile
        # tmp_path = f"/tmp/{excel_file.filename}"
        temp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(temp_dir, excel_file.filename)
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(excel_file.file, f)
        
        # 엑셀 파일의 날짜 형식 자동 수정
        try:
            print("📝 엑셀 파일 날짜 형식 검사 및 수정 중...")
            fixed_path = fix_excel_datetime_format(tmp_path)
            if fixed_path:
                tmp_path = fixed_path
                print("✅ 엑셀 파일 날짜 형식 수정 완료")
            else:
                print("ℹ️ 날짜 형식 수정이 필요하지 않습니다")
        except Exception as fix_error:
            print(f"⚠️ 날짜 형식 수정 실패 (원본 사용): {fix_error}")
        
        records_before = 0
        records_added = 0
        
        # 면세점 타입에 따라 다른 처리 로직
        if duty_free_enum == DutyFreeType.LOTTE:
            table_name = 'lotte_excel_data'
            
            # 롯데 엑셀 데이터 처리
            try:
                # 멀티헤더 엑셀 파일 읽기 (날짜 자동 파싱 비활성화)
                df = pd.read_excel(tmp_path, header=[0, 1], dtype=str)
                
                # 병합된 멀티헤더를 1단 컬럼으로 변환
                df.columns = [f"{str(a).strip()}_{str(b).strip()}" if 'Unnamed' not in str(b) else str(a).strip()
                            for a, b in df.columns]
                
                print(f"원본 컬럼들: {list(df.columns)}")
                
                # "매출_" 접두어 제거
                df.columns = [col.replace("매출_", "") for col in df.columns]
                
                # 불필요한 컬럼 제거
                columns_to_remove = ['순번', '0', '여행사', '여행사코드']
                df = df.drop(columns=[col for col in columns_to_remove if col in df.columns], errors='ignore')
                
                # 컬럼명 변경 - 핵심 컬럼들만 확인
                rename_mapping = {}
                for col in df.columns:
                    if '교환권번호' in col or 'receiptNumber' in col:
                        rename_mapping[col] = 'receiptNumber'
                    elif '고객명' in col or 'name' in col:
                        rename_mapping[col] = 'name'
                
                print(f"컬럼 매핑: {rename_mapping}")
                df = df.rename(columns=rename_mapping)
                
                # 필수 컬럼 확인
                required_columns = ['receiptNumber', 'name']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    raise Exception(f"필수 컬럼이 없습니다: {missing_columns}")
                
                print(f"최종 컬럼들: {list(df.columns)}")
                print(f"데이터 샘플: {df.head()}")
                
            except Exception as e:
                # 단순 헤더 파일로 다시 시도
                print(f"멀티헤더 처리 실패, 단순 헤더로 재시도: {e}")
                df = pd.read_excel(tmp_path, dtype=str)
                print(f"단순 헤더 컬럼들: {list(df.columns)}")
                
                # 컬럼명 변경
                rename_mapping = {}
                for col in df.columns:
                    if '교환권번호' in str(col) or 'receiptNumber' in str(col):
                        rename_mapping[col] = 'receiptNumber'
                    elif '고객명' in str(col) or 'name' in str(col):
                        rename_mapping[col] = 'name'
                
                df = df.rename(columns=rename_mapping)
                
                # 필수 컬럼 확인
                if 'receiptNumber' not in df.columns or 'name' not in df.columns:
                    raise Exception("필수 컬럼(receiptNumber, name)을 찾을 수 없습니다.")
                
                
        
        else:
            table_name = 'shilla_excel_data'
            
            # 신라 엑셀 데이터 처리 (단순한 헤더 구조)
            df = pd.read_excel(tmp_path, dtype=str)
            print(f"신라 엑셀 원본 컬럼들: {list(df.columns)}")

            # 컬럼명 변경
            df.rename(columns={'BILL 번호': 'receiptNumber', '고객명': 'name'}, inplace=True)
            
            # 필수 컬럼 확인
            if 'receiptNumber' not in df.columns:
                raise Exception("영수증 번호 컬럼(BILL 번호)을 찾을 수 없습니다.")
            if 'name' not in df.columns:
                raise Exception("고객명 컬럼을 찾을 수 없습니다.")
            
            # receiptNumber를 문자열로 변환 (중요!)
            df['receiptNumber'] = df['receiptNumber'].astype(str)
            
            # 신라 전용: passport_number 컬럼 추가 (매칭 시 업데이트용)
            df['passport_number'] = None
            
            # 중복 컬럼 제거 (같은 이름으로 매핑된 컬럼들)
            df = df.loc[:, ~df.columns.duplicated()]
            
            print(f"신라 최종 컬럼들: {list(df.columns)}")
            print(f"신라 데이터 샘플:\n{df.head()}")
            print(f"receiptNumber 타입: {df['receiptNumber'].dtype}")
        
        # 새로운 엔진 연결로 트랜잭션 분리
        temp_engine = create_engine(SQLALCHEMY_DATABASE_URL)
        
        with temp_engine.connect() as connection:
            # 자동커밋 모드로 각 작업을 독립적으로 실행
            connection.execute(text("BEGIN"))
            
            try:
                # 기존 데이터 수 조회
                try:
                    count_sql = text(f"SELECT COUNT(*) FROM {table_name}")
                    records_before = connection.execute(count_sql).scalar()
                    print(f"기존 레코드 수: {records_before}")
                except Exception as count_error:
                    print(f"기존 데이터 조회 실패 (테이블이 없을 수 있음): {count_error}")
                    records_before = 0
                    # 트랜잭션 재시작
                    connection.execute(text("ROLLBACK"))
                    connection.execute(text("BEGIN"))
                
                # 기존 데이터와 중복 체크
                existing_receipts = set()
                try:
                    existing_sql = text(f'SELECT "receiptNumber" FROM {table_name}')
                    existing_data = connection.execute(existing_sql).fetchall()
                    existing_receipts = {row[0] for row in existing_data if row[0]}
                    print(f"기존 영수증 번호 수: {len(existing_receipts)}")
                except Exception as existing_error:
                    print(f"기존 데이터 조회 실패 (테이블이 없을 수 있음): {existing_error}")
                    existing_receipts = set()
                    # 트랜잭션 재시작
                    connection.execute(text("ROLLBACK"))
                    connection.execute(text("BEGIN"))
                
                # 중복되지 않은 데이터만 필터링
                if existing_receipts:
                    df_new = df[~df['receiptNumber'].isin(existing_receipts)]
                else:
                    df_new = df.copy()
                
                # 📌 테이블별 데이터 타입 정의
                if table_name == 'lotte_excel_data':
                    # 롯데 엑셀 데이터 타입 정의 (금액 관련 컬럼들을 numeric으로 강제)
                    dtype_mapping = {
                        'receiptNumber': Text,
                        'name': Text,
                        '점구분': Text,
                        '원매출일자': Text,
                        '매출일자': Text,
                        '수입/로컬': Text,
                        '단체번호': Text,
                        'VIP번호': Text,
                        '교환권상태': Text,
                        '카테고리': Text,
                        '브랜드': Text,
                        '상품명': Text,
                        '상품구분': Text,
                        '상품코드': Text,
                        'Ref.No': Text,
                        'Color': Text,
                        '배송구분': Text,
                        '판매방식': Text,
                        '판매수량': Numeric,
                        '판매가($)': Numeric,
                        '총매출액($)': Numeric,
                        '순매출액($)': Numeric,
                        '할인액($)': Numeric,
                        '총매출액(\)': Numeric,
                        '순매출액(\)': Numeric,
                        '할인액(\)': Numeric
                    }
                    
                    # 📌 금액 컬럼들의 데이터 정제 (빈 문자열, 'nan', '-' 등을 0으로 변환)
                    numeric_columns = ['판매수량', '판매가($)', '총매출액($)', '순매출액($)', '할인액($)', 
                                     '총매출액(\)', '순매출액(\)', '할인액(\)']
                    
                    for col in numeric_columns:
                        if col in df_new.columns:
                            # 빈 문자열, NaN, '-', 'nan' 등을 0으로 변환
                            df_new[col] = df_new[col].astype(str).replace(['', 'nan', '-', 'NaN', 'null', 'None'], '0')
                            # 숫자가 아닌 문자 제거 (콤마, 공백 등)
                            df_new[col] = df_new[col].str.replace(',', '').str.replace(' ', '')
                            # 빈 문자열이 되면 0으로 설정
                            df_new[col] = df_new[col].replace('', '0')
                            # numeric으로 변환
                            df_new[col] = pd.to_numeric(df_new[col], errors='coerce').fillna(0)
                    
                elif table_name == 'shilla_excel_data':
                    dtype_mapping = {
                        'receiptNumber': String(50),  # shilla_receipts와 동일한 타입으로 통일
                        'name': Text,
                        'passport_number': Text,
                        # 금액 관련 컬럼들을 Numeric으로 강제 (실제 컬럼명으로 수정)
                        '할인액(￦)': Numeric,
                        '판매가($)': Numeric,
                        '순매출액(￦)': Numeric,
                        # 기타 컬럼들 (실제 사용되는 컬럼명으로 수정)
                        '매출일자': Text,
                        '카테고리': Text,
                        '브랜드명': Text,
                        '상품코드': Text,
                        '점': Text
                    }
                    
                    # 📌 신라 금액 컬럼들의 데이터 정제
                    shilla_numeric_columns = ['할인액(￦)', '판매가($)', '순매출액(￦)']
                    
                    for col in shilla_numeric_columns:
                        if col in df_new.columns:
                            # 빈 문자열, NaN, '-', 'nan' 등을 0으로 변환
                            df_new[col] = df_new[col].astype(str).replace(['', 'nan', '-', 'NaN', 'null', 'None'], '0')
                            # 숫자가 아닌 문자 제거 (콤마, 공백 등)
                            df_new[col] = df_new[col].str.replace(',', '').str.replace(' ', '')
                            # 빈 문자열이 되면 0으로 설정
                            df_new[col] = df_new[col].replace('', '0')
                            # numeric으로 변환
                            df_new[col] = pd.to_numeric(df_new[col], errors='coerce').fillna(0)
                
                else:
                    # 기타 테이블은 기본 처리
                    dtype_mapping = None
                
                records_added = len(df_new)
                print(f"추가할 레코드 수: {records_added}")
                
                if records_added > 0:
                    # 📌 데이터 저장 시도 (dtype 매개변수 추가)
                    try:
                        # 먼저 append로 시도
                        if dtype_mapping:
                            df_new.to_sql(table_name, connection, if_exists='append', index=False, dtype=dtype_mapping)
                        else:
                            df_new.to_sql(table_name, connection, if_exists='append', index=False)
                        print(f"✅ {table_name} 테이블에 {records_added}개 레코드 추가 완료")
                    except Exception as append_error:
                        print(f"append 실패, replace로 재시도: {append_error}")
                        # append 실패 시 rollback 후 replace로 시도
                        connection.execute(text("ROLLBACK"))
                        connection.execute(text("BEGIN"))
                        
                        # 📌 전체 데이터로 테이블 새로 생성 (dtype 매개변수 추가)
                        if dtype_mapping:
                            # 전체 df에도 동일한 데이터 정제 적용
                            if table_name == 'lotte_excel_data':
                                for col in numeric_columns:
                                    if col in df.columns:
                                        df[col] = df[col].astype(str).replace(['', 'nan', '-', 'NaN', 'null', 'None'], '0')
                                        df[col] = df[col].str.replace(',', '').str.replace(' ', '')
                                        df[col] = df[col].replace('', '0')
                                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                            elif table_name == 'shilla_excel_data':
                                # 신라 금액 컬럼들의 데이터 정제 (replace 시에도 적용)
                                for col in shilla_numeric_columns:
                                    if col in df.columns:
                                        df[col] = df[col].astype(str).replace(['', 'nan', '-', 'NaN', 'null', 'None'], '0')
                                        df[col] = df[col].str.replace(',', '').str.replace(' ', '')
                                        df[col] = df[col].replace('', '0')
                                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                            
                            df.to_sql(table_name, connection, if_exists='replace', index=False, dtype=dtype_mapping)
                        else:
                            df.to_sql(table_name, connection, if_exists='replace', index=False)
                        records_added = len(df)
                        print(f"✅ {table_name} 테이블을 새로 생성하고 {records_added}개 레코드 추가 완료")
                        records_before = 0  # 새로 생성했으므로 이전 데이터는 0
                else:
                    print("추가할 새로운 데이터가 없습니다.")
                
                # 트랜잭션 커밋
                connection.execute(text("COMMIT"))
                print("✅ 트랜잭션 커밋 완료")
                
            except Exception as e:
                # 오류 발생 시 롤백
                print(f"데이터베이스 작업 중 오류: {e}")
                connection.execute(text("ROLLBACK"))
                raise e
        
        # 임시 파일 삭제
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        # 임시 디렉토리도 삭제
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        processing_time = f"{time.time() - start_time:.2f}초"
        
        return {
            "success": True,
            "records_added": records_added,
            "total_records": records_before + records_added,
            "processing_time": processing_time,
            "duty_free_type": duty_free_enum.value
        }
        
    except Exception as e:
        # 전체 오류 처리
        print(f"엑셀 처리 오류: {str(e)}")
        
        # 임시 파일 정리
        if tmp_path and os.path.exists(tmp_path):
            # fix_excel_datetime_format에서 생성된 임시 디렉토리도 정리
            if 'fixed_' in os.path.basename(tmp_path):
                # 수정된 파일의 임시 디렉토리 정리
                fixed_temp_dir = os.path.dirname(tmp_path)
                if os.path.exists(fixed_temp_dir):
                    shutil.rmtree(fixed_temp_dir)
            else:
                os.remove(tmp_path)
        # 원본 임시 디렉토리도 삭제
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        raise HTTPException(status_code=500, detail=f"엑셀 처리 중 오류: {str(e)}")


@router.get("/excel-upload/")
def excel_upload_page(
    request: Request, 
    duty_free: str = "lotte",  # URL 파라미터로 면세점 타입 받기
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # URL 파라미터로 받은 면세점 타입 처리
    duty_free_type = "롯데면세점" if duty_free == "lotte" else "신라면세점"
    
    # 현재 저장된 데이터 통계
    total_records = 0
    unique_customers = 0
    
    try:
        if duty_free == "lotte":
            total_records = db.execute(text("SELECT COUNT(*) FROM lotte_excel_data")).scalar()
            unique_customers = db.execute(text("SELECT COUNT(DISTINCT name) FROM lotte_excel_data")).scalar()
        else:
            total_records = db.execute(text("SELECT COUNT(*) FROM shilla_excel_data")).scalar()
            unique_customers = db.execute(text("SELECT COUNT(DISTINCT name) FROM shilla_excel_data")).scalar()
    except Exception as e:
        print(f"데이터 통계 조회 오류: {e}")
        # 테이블이 존재하지 않는 경우 0으로 설정
        total_records = 0
        unique_customers = 0
    
    return templates.TemplateResponse("excel_upload.html", {
        "request": request,
        "user": current_user,
        "duty_free_type": duty_free_type,
        "duty_free_value": duty_free,  # 폼 전송용
        "total_records": total_records,
        "unique_customers": unique_customers
    })


@router.get("/progress/")
def get_progress():
    return progress


@router.post("/result/")
async def result(
    request: Request,
    folder: UploadFile = File(...),
    duty_free_type: str = Form(...),  # 폼에서 면세점 타입 받기
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 시작 시간 기록
        start_time = datetime.now()
        print(f"\n처리 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"선택된 면세점 타입: {duty_free_type}")

        # 업로드 ID 생성
        upload_id = generate_upload_id()
        print(f"생성된 업로드 ID: {upload_id}")

        # 면세점 타입 변환
        duty_free_enum = DutyFreeType.LOTTE if duty_free_type == "lotte" else DutyFreeType.SHILLA

        # uploads 디렉토리 설정 (settings에서 설정된 변수 사용)
        user_uploads_dir = settings.get_user_uploads_dir(current_user.id)
        
        # 1) ZIP 저장·해제
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, folder.filename)
        with open(path, "wb") as f: 
            shutil.copyfileobj(folder.file, f)
        with zipfile.ZipFile(path) as z: 
            z.extractall(tmp)

        # 2) 이미지 목록 (macOS 메타데이터 파일 제외)
        imgs = []
        for r,d,fs in os.walk(tmp):
            for f in fs:
                # macOS 메타데이터 파일과 __MACOSX 디렉토리 제외
                if (not f.startswith('._') and 
                    not r.endswith('__MACOSX') and 
                    f.lower().endswith((".jpg",".png",".jpeg"))):
                    # 이미지를 uploads 디렉토리로 복사
                    src_path = os.path.join(r, f)
                    dst_path = os.path.join(settings.uploads_dir, f)
                    shutil.copy2(src_path, dst_path)
                    imgs.append(dst_path)

        if not imgs:
            end_time = datetime.now()
            print(f"처리 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"총 처리 시간: 0초")
            return templates.TemplateResponse(
                "result.html",
                {
                    "request": request,
                    "error": "ZIP 파일에 처리 가능한 이미지가 없습니다.",
                    "results": [],
                    "unmatched_receipts": [],
                    "user": current_user,
                    "duty_free_type": duty_free_type
                }
            )

        # 3) OCR→DB 저장 (면세점 타입에 따라 분기)
        progress["total"] = len(imgs); progress["done"]=0
        print(f"전체 이미지 수: {progress['total']}")
        
        for img in imgs:
            try:
                if duty_free_enum == DutyFreeType.LOTTE:
                    # 롯데 면세점 처리
                    LotteAiOcr(img, current_user.id)
                else:
                    # 신라 면세점 처리
                    ShillaAiOcr(img, current_user.id)
            except Exception as e:
                print(f"이미지 처리 중 오류 발생: {img} - {str(e)}")
            finally:
                progress["done"] += 1
                print(f"처리 완료: {progress['done']}/{progress['total']}")

        # 4) 매칭 실행 (면세점 타입에 따라 분기)
        if duty_free_enum == DutyFreeType.LOTTE:
            matchingResult(current_user.id)
        else:
            shilla_matching_result(current_user.id)

        # 5) 업로드 ID 할당
        assign_upload_id_to_data(current_user.id, upload_id, db)
        
        # 6) 조회용 리스트 생성 (duty_free_type 매개변수 추가)
        matched, unmatched = fetch_results(current_user.id, duty_free_type)
        
        # 여권 정보 조회
        passport_info = matching_passport(current_user.id, duty_free_type)
        
        # 영수증과 여권이 모두 매칭된 고객 수 계산
        fully_matched_customers = calculate_fully_matched_customers(current_user.id, duty_free_type, db)
        
        # 여권 통계 계산
        passport_stats = calculate_passport_statistics(current_user.id, duty_free_type, db)
        
        # 7) 임시 디렉터리 삭제
        shutil.rmtree(tmp)

        # 종료 시간 기록 및 처리 시간 계산
        end_time = datetime.now()
        processing_time = end_time - start_time
        print(f"처리 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"총 처리 시간: {processing_time.seconds}초 {processing_time.microseconds // 1000}밀리초")
        
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "results": passport_info,
                "unmatched_receipts": unmatched,
                "fully_matched_customers": fully_matched_customers,
                "passport_stats": passport_stats,
                "user": current_user,
                "duty_free_type": duty_free_type
            }
        )
    except Exception as e:
        end_time = datetime.now()
        print(f"처리 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"오류 발생으로 인한 처리 시간: {end_time - start_time}")
        print(f"처리 중 오류 발생: {str(e)}")
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "error": f"처리 중 오류가 발생했습니다: {str(e)}",
                "results": [],
                "unmatched_receipts": [],
                "fully_matched_customers": 0,
                "passport_stats": {"total_passports": 0, "matched_passports": 0, "unmatched_passports": 0},
                "user": current_user,
                "duty_free_type": duty_free_type if 'duty_free_type' in locals() else 'lotte'
            }
        ) 