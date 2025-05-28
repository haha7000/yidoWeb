import pandas as pd
from sqlalchemy import create_engine
import sys

# DB 연결 정보
user = 'test_user'
password = '0000'
host = 'localhost'
port = '5432'
database = 'my_test_db'

try:
    # psycopg2 드라이버를 명시적으로 사용
    SQLALCHEMY_DATABASE_URL = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'
    db_engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    # 데이터베이스 연결 테스트
    with db_engine.connect() as connection:
        print("데이터베이스 연결 성공!")
        
        # 엑셀 파일 경로
        excel_path = "/Users/gimdonghun/Downloads/testExcel_1.xlsx"
        print(f"엑셀 파일 읽기: {excel_path}")
        
        # 엑셀 파일 읽기
        df = pd.read_excel(excel_path, header=[0, 1])
        # 병합된 멀티헤더를 1단 컬럼으로 변환
        df.columns = [f"{str(a).strip()}_{str(b).strip()}" if 'Unnamed' not in str(b) else str(a).strip()
                    for a, b in df.columns]

        # "매출_" 접두어 제거
        df.columns = [col.replace("매출_", "") for col in df.columns]

        columns_to_remove = ['순번', '0', '여행사', '여행사코드', '수입/로컬']
        df = df.drop(columns=[col for col in columns_to_remove if col in df.columns], errors='ignore')
        
        # 컬럼명 변경
        df = df.rename(columns={'교환권번호': 'receiptNumber', '고객명': 'name'})
        print(f"엑셀 데이터 읽기 완료: {len(df)} 행")

        
        
        # 테이블로 저장
        df.to_sql('excel_data', connection, if_exists='append', index=False)
        print("데이터베이스 저장 완료!")

except Exception as e:
    print(f"오류 발생: {str(e)}", file=sys.stderr)
    sys.exit(1)

