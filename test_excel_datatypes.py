#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
엑셀 파일 데이터 타입 분석 테스트
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os

def analyze_excel_datatypes(file_path):
    """
    엑셀 파일의 각 컬럼 데이터 타입을 분석합니다.
    """
    print(f"📁 분석할 파일: {file_path}")
    print("=" * 80)
    
    try:
        # 파일 존재 확인
        if not os.path.exists(file_path):
            print(f"❌ 파일이 존재하지 않습니다: {file_path}")
            return
        
        # 파일 크기 확인
        file_size = os.path.getsize(file_path)
        print(f"📊 파일 크기: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
        
        # 엑셀 파일 읽기 시도 (여러 방법)
        df = None
        
        # 1. 기본 읽기 시도
        try:
            print("\n🔍 기본 읽기 시도...")
            df = pd.read_excel(file_path)
            print("✅ 기본 읽기 성공")
        except Exception as e:
            print(f"⚠️ 기본 읽기 실패: {e}")
            
            # 2. 멀티헤더 읽기 시도
            try:
                print("\n🔍 멀티헤더 읽기 시도...")
                df = pd.read_excel(file_path, header=[0, 1])
                print("✅ 멀티헤더 읽기 성공")
                
                # 멀티헤더를 단일 헤더로 변환
                df.columns = [f"{str(a).strip()}_{str(b).strip()}" if 'Unnamed' not in str(b) else str(a).strip()
                            for a, b in df.columns]
                print("✅ 멀티헤더를 단일 헤더로 변환 완료")
                
            except Exception as e2:
                print(f"⚠️ 멀티헤더 읽기도 실패: {e2}")
                
                # 3. dtype=str로 강제 읽기 시도
                try:
                    print("\n🔍 문자열 강제 읽기 시도...")
                    df = pd.read_excel(file_path, dtype=str)
                    print("✅ 문자열 강제 읽기 성공")
                except Exception as e3:
                    print(f"❌ 모든 읽기 방법 실패: {e3}")
                    return
        
        if df is None:
            print("❌ 데이터프레임을 읽을 수 없습니다.")
            return
        
        # 기본 정보 출력
        print(f"\n📋 기본 정보:")
        print(f"   - 행 수: {len(df):,}")
        print(f"   - 열 수: {len(df.columns)}")
        print(f"   - 메모리 사용량: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
        
        # 컬럼명 출력
        print(f"\n📝 컬럼명 목록:")
        for i, col in enumerate(df.columns, 1):
            print(f"   {i:2d}. {col}")
        
        # 각 컬럼별 상세 분석
        print(f"\n🔬 컬럼별 데이터 타입 분석:")
        print("-" * 80)
        
        column_analysis = []
        
        for i, col in enumerate(df.columns, 1):
            print(f"\n📊 컬럼 {i}: {col}")
            print(f"   {'─' * 50}")
            
            # 기본 정보
            dtype = df[col].dtype
            null_count = df[col].isnull().sum()
            non_null_count = len(df) - null_count
            unique_count = df[col].nunique()
            
            print(f"   • 데이터 타입: {dtype}")
            print(f"   • NULL 값: {null_count:,} ({null_count/len(df)*100:.1f}%)")
            print(f"   • 유효 값: {non_null_count:,} ({non_null_count/len(df)*100:.1f}%)")
            print(f"   • 고유 값: {unique_count:,}")
            
            # 샘플 데이터 출력
            non_null_data = df[col].dropna()
            if len(non_null_data) > 0:
                print(f"   • 샘플 데이터:")
                for j, sample in enumerate(non_null_data.head(5), 1):
                    print(f"     {j}. {repr(sample)} (타입: {type(sample).__name__})")
                
                if len(non_null_data) > 5:
                    print(f"     ... (총 {len(non_null_data)}개 중 5개만 표시)")
            
            # 데이터 타입 변환 시도
            print(f"   • 타입 변환 테스트:")
            
            # 숫자 변환 시도
            try:
                numeric_data = pd.to_numeric(df[col], errors='coerce')
                numeric_count = numeric_data.notna().sum()
                if numeric_count > 0:
                    print(f"     - 숫자 변환 가능: {numeric_count:,}개 ({numeric_count/len(df)*100:.1f}%)")
                    if numeric_count > 0:
                        print(f"       최소값: {numeric_data.min()}, 최대값: {numeric_data.max()}")
                else:
                    print(f"     - 숫자 변환 불가")
            except:
                print(f"     - 숫자 변환 실패")
            
            # 날짜 변환 시도
            try:
                date_data = pd.to_datetime(df[col], errors='coerce')
                date_count = date_data.notna().sum()
                if date_count > 0:
                    print(f"     - 날짜 변환 가능: {date_count:,}개 ({date_count/len(df)*100:.1f}%)")
                    if date_count > 0:
                        print(f"       최소값: {date_data.min()}, 최대값: {date_data.max()}")
                else:
                    print(f"     - 날짜 변환 불가")
            except:
                print(f"     - 날짜 변환 실패")
            
            # 분석 결과 저장
            column_analysis.append({
                'column_name': col,
                'dtype': str(dtype),
                'null_count': null_count,
                'non_null_count': non_null_count,
                'unique_count': unique_count,
                'sample_data': non_null_data.head(3).tolist() if len(non_null_data) > 0 else []
            })
        
        # 요약 리포트
        print(f"\n📋 요약 리포트:")
        print("=" * 80)
        
        print(f"\n🔢 숫자형 컬럼:")
        numeric_columns = [col for col in column_analysis if 'int' in col['dtype'] or 'float' in col['dtype']]
        for col in numeric_columns:
            print(f"   • {col['column_name']} ({col['dtype']})")
        
        print(f"\n📅 날짜형 컬럼:")
        date_columns = [col for col in column_analysis if 'datetime' in col['dtype']]
        for col in date_columns:
            print(f"   • {col['column_name']} ({col['dtype']})")
        
        print(f"\n📝 문자열형 컬럼:")
        string_columns = [col for col in column_analysis if 'object' in col['dtype']]
        for col in string_columns:
            print(f"   • {col['column_name']} ({col['dtype']})")
        
        print(f"\n❌ NULL 값이 많은 컬럼 (50% 이상):")
        high_null_columns = [col for col in column_analysis if col['null_count']/len(df) > 0.5]
        for col in high_null_columns:
            null_percent = col['null_count']/len(df)*100
            print(f"   • {col['column_name']} ({null_percent:.1f}% NULL)")
        
        # 권장사항
        print(f"\n💡 권장사항:")
        print("-" * 40)
        
        for col in column_analysis:
            col_name = col['column_name']
            null_percent = col['null_count']/len(df)*100
            
            if null_percent > 80:
                print(f"   • {col_name}: NULL 값이 {null_percent:.1f}%로 매우 많음 - 컬럼 제거 고려")
            elif null_percent > 50:
                print(f"   • {col_name}: NULL 값이 {null_percent:.1f}%로 많음 - nullable=True 설정 권장")
            
            # 특수문자가 포함된 컬럼명
            if any(char in col_name for char in ['(', ')', ' ', '/', '\\', '$', '￦']):
                print(f"   • {col_name}: 특수문자 포함 - DB 컬럼명 매핑 필요")
        
        return column_analysis
        
    except Exception as e:
        print(f"❌ 분석 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """메인 함수"""
    # 분석할 파일 경로
    file_path = "/Users/gimdonghun/Downloads/여행사매출상세내역조회_20250620163337.xlsx"
    
    print("🚀 엑셀 파일 데이터 타입 분석 시작")
    print("=" * 80)
    
    # 분석 실행
    result = analyze_excel_datatypes(file_path)
    
    if result:
        print(f"\n✅ 분석 완료! 총 {len(result)}개 컬럼 분석됨")
    else:
        print(f"\n❌ 분석 실패")

if __name__ == "__main__":
    main() 