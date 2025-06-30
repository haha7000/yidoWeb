import pandas as pd
import os
import platform
from datetime import datetime
from pathlib import Path

class LotteExporter:
    def __init__(self):
        pass
    
    def get_downloads_folder(self):
        """운영체제별 다운로드 폴더 경로 반환"""
        system = platform.system()
        
        if system == "Windows":
            # Windows: %USERPROFILE%\Downloads
            downloads_path = Path.home() / "Downloads"
        elif system == "Darwin":  # macOS
            # macOS: ~/Downloads
            downloads_path = Path.home() / "Downloads"
        elif system == "Linux":
            # Linux: ~/Downloads (대부분의 배포판)
            downloads_path = Path.home() / "Downloads"
        else:
            # 기타 OS: 현재 디렉토리 사용
            downloads_path = Path.cwd()
            print(f"⚠️ 알 수 없는 운영체제: {system}, 현재 디렉토리에 저장합니다.")
        
        # 다운로드 폴더가 없으면 생성
        if not downloads_path.exists():
            try:
                downloads_path.mkdir(parents=True, exist_ok=True)
                print(f"📁 다운로드 폴더 생성: {downloads_path}")
            except Exception as e:
                print(f"❌ 다운로드 폴더 생성 실패: {e}")
                downloads_path = Path.cwd()
                print(f"📁 현재 디렉토리 사용: {downloads_path}")
        
        return downloads_path
    
    def save_to_excel(self, sales_data, filename=None):
        """pandas로 엑셀 파일 저장 (다운로드 폴더에)"""
        if not sales_data:
            print("❌ 저장할 데이터가 없습니다.")
            return None
        
        # 다운로드 폴더 경로 가져오기
        downloads_folder = self.get_downloads_folder()
        
        # 파일명 설정
        if filename is None:
            filename = f"매출데이터_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # 확장자가 없으면 추가
        if not filename.endswith('.xlsx'):
            filename += '.xlsx'
        
        # 전체 파일 경로
        file_path = downloads_folder / filename
        
        try:
            df = pd.DataFrame(sales_data)
            
            # 컬럼 순서 재정렬 (점구분을 strCd 다음에 배치)
            if '점구분' in df.columns and 'strCd' in df.columns:
                columns = df.columns.tolist()
                columns.remove('점구분')
                str_cd_index = columns.index('strCd')
                columns.insert(str_cd_index + 1, '점구분')
                df = df[columns]
            
            # 컬럼명 변경 (영어 컬럼 + 특정 한글 컬럼)
            column_mapping = {
                # 기존 매핑 (영어 -> 한글)
                'slDt': '매출일자',
                'strCd': '지점코드', 
                'tayNm': '여행사',
                'brndNm': '브랜드',
                'prodNm': '상품명',
                'prdcd': '상품코드',
                'custNm': '고객명',
                'slQty': '판매수량',
                'wonTotSalamt': '총매출액(원)',
                'wonNsalamt': '순매출액(원)',
                
                # 새로 추가된 매핑
                'entshpTaycd': '여행사코드',
                'brndcd': '브랜드코드',
                'cateNm': '카테고리',
                'exchNo': '교환권번호',
                'gdeNm': '가이드',
                'gdecd': '가이드코드',
                'grpNo': '단체번호',
                'grpTypeNm': '단체유형',
                'imptLocalDvsCd': '수입/로컬',
                'psptno': '여권번호',
                'dlrTotSalamt': '총매출액(달러)',
                'dlrNsalamt': '순매출액(달러)',
                'dlrTotDcAmt': '할인액(달러)',
                'dlvrDvsCd': '배송구분코드',
                
                # 한글 컬럼 변경
                '지점명': '점구분',
                
                # 추가로 나올 수 있는 컬럼들
                'rcrtcustRgnCd': '고객지역코드',
                'typeCd': '유형코드',
                'imptLocalDvsNm': '수입/로컬구분',
                'grpTypeCd': '단체유형코드',
                'cateCd': '카테고리코드'
            }
            
            # 존재하는 컬럼들 변경 (영어 컬럼 + 지정된 한글 컬럼)
            existing_mappings = {}
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    # 영어 컬럼이거나 특별히 지정된 한글 컬럼('지점명') 변경
                    if not self._is_korean_column(old_col) or old_col == '지점명':
                        existing_mappings[old_col] = new_col
            
            df = df.rename(columns=existing_mappings)
            
            # 변경된 컬럼 정보 출력
            if existing_mappings:
                print(f"\n🔄 컬럼명 변경:")
                for old, new in existing_mappings.items():
                    print(f"   {old} → {new}")
            
            # 엑셀 저장
            df.to_excel(file_path, index=False, engine='openpyxl')
            
            # 운영체제 정보와 함께 저장 완료 메시지
            system_info = f"{platform.system()} {platform.release()}"
            print(f"✅ 엑셀 파일 저장 완료!")
            print(f"   💻 운영체제: {system_info}")
            print(f"   📁 저장 경로: {file_path}")
            print(f"   📄 파일 크기: {self._get_file_size(file_path)}")
            
            # 통계 정보 출력
            self._print_statistics(df)
            
            return str(file_path)
            
        except ImportError:
            print("❌ pandas가 설치되지 않았습니다.")
            print("   설치 명령어: pip install pandas openpyxl")
            return None
        except PermissionError:
            print(f"❌ 파일 저장 권한이 없습니다: {file_path}")
            print("   다른 프로그램에서 파일을 사용 중이거나 권한이 부족합니다.")
            return None
        except Exception as e:
            print(f"❌ 엑셀 저장 오류: {str(e)}")
            print(f"   시도한 경로: {file_path}")
            return None
    
    def _is_korean_column(self, column_name):
        """컬럼명이 한글인지 확인"""
        import re
        # 한글이 포함되어 있으면 True
        return bool(re.search(r'[가-힣]', str(column_name)))
    
    def _get_file_size(self, file_path):
        """파일 크기를 읽기 쉬운 형식으로 반환"""
        try:
            size_bytes = os.path.getsize(file_path)
            if size_bytes < 1024:
                return f"{size_bytes} bytes"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
        except:
            return "알 수 없음"
    
    def _print_statistics(self, df):
        """통계 정보 출력"""
        print(f"\n📊 데이터 통계:")
        print(f"   총 데이터 건수: {len(df)}건")
        
        # 지점별 데이터 개수
        if '점구분' in df.columns and '지점코드' in df.columns:
            print("\n📍 지점별 데이터 건수:")
            store_counts = df.groupby(['지점코드', '점구분']).size().reset_index(name='건수')
            for _, row in store_counts.iterrows():
                print(f"  {row['지점코드']} ({row['점구분']}): {row['건수']}건")
        
        # 브랜드별 데이터 개수 (상위 5개)
        if '브랜드' in df.columns:
            print("\n🏷️ 브랜드별 데이터 건수 (상위 5개):")
            brand_counts = df['브랜드'].value_counts().head(5)
            for brand, count in brand_counts.items():
                print(f"  {brand}: {count}건")
        
        print(f"\n📋 저장된 컬럼: {', '.join(df.columns.tolist())}")
    
    def check_product_info(self, sales_data):
        """상품 정보 포함 여부 확인"""
        if not sales_data:
            return False
        
        sample = sales_data[0]
        has_product_info = 'prdcd' in sample and 'prodNm' in sample
        
        if has_product_info:
            # 실제 값이 있는지 확인
            prdcd_value = sample.get('prdcd', '').strip()
            prodNm_value = sample.get('prodNm', '').strip()
            
            if prdcd_value and prodNm_value:
                print(f"✅ 상품정보 포함됨: {prdcd_value} - {prodNm_value}")
                return True
            else:
                print("⚠️ 상품정보 컬럼은 있지만 값이 비어있습니다.")
                return False
        else:
            print("❌ 상품정보가 포함되지 않았습니다.")
            return False
    
    def open_downloads_folder(self):
        """다운로드 폴더 열기"""
        downloads_folder = self.get_downloads_folder()
        
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(downloads_folder)
            elif system == "Darwin":  # macOS
                os.system(f"open '{downloads_folder}'")
            elif system == "Linux":
                os.system(f"xdg-open '{downloads_folder}'")
            
            print(f"📂 다운로드 폴더 열기: {downloads_folder}")
        except Exception as e:
            print(f"❌ 폴더 열기 실패: {e}")
            print(f"수동으로 열어주세요: {downloads_folder}")