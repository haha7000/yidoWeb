from lotte_scraper import LotteDutyFreeSales

def main():
    """메인 실행 함수"""
    scraper = LotteDutyFreeSales()
    
    print("🚀 롯데면세점 매출 데이터 조회 시작")
    print("=" * 50)
    
    # 로그인
    print("🔐 로그인 중...")
    if not scraper.login('T301912', 'huixin210@@'):
        print("❌ 로그인 실패로 작업을 중단합니다.")
        return
    
    print("\n🔍 매출 데이터 조회 중...")
    
    # 1단계: 상품별 매출 데이터 조회 시도 (prdcd, prodNm 포함)
    print("\n📦 상품별 매출 데이터 조회 중...")
    sales_data = scraper.fetch_product_sales()
    
    if sales_data:
        print(f"✅ {len(sales_data)}건의 상품별 매출 데이터 조회 완료")
        
        # 엑셀 파일 저장
        print("\n💾 엑셀 파일 저장 중...")
        excel_file = scraper.save_to_excel(filename="상품별_매출데이터.xlsx")
        
        if excel_file:
            print(f"🎉 상품별 매출 데이터 엑셀 저장 완료!")
        else:
            print("❌ 엑셀 저장 실패")
    
    else:
        print("❌ 상품별 매출 데이터 조회 실패")
        
        # 2단계: 브랜드별 조회로 폴백
        print("\n🔄 브랜드별 조회로 폴백...")
        sales_data = scraper.fetch_brand_sales()
        
        if sales_data:
            print(f"✅ 브랜드별 데이터 {len(sales_data)}건 조회됨 (상품정보 제외)")
            
            # 엑셀 파일 저장
            print("\n💾 엑셀 파일 저장 중...")
            excel_file = scraper.save_to_excel(filename="브랜드별_매출데이터.xlsx")
            
            if excel_file:
                print(f"🎉 브랜드별 매출 데이터 엑셀 저장 완료!")
            else:
                print("❌ 엑셀 저장 실패")
        else:
            print("❌ 모든 매출 데이터 조회 실패")
    
    print("\n" + "=" * 50)
    print("✅ 작업 완료!")

def test_with_manual_cookies():
    """수동 쿠키로 테스트하는 함수"""
    scraper = LotteDutyFreeSales()
    
    print("🔧 수동 쿠키 설정 모드")
    print("브라우저에서 쿠키를 복사해서 사용합니다.")
    
    # 여기에 브라우저에서 복사한 쿠키 정보 입력
    cookie_string = "your_cookies_here"  # 실제 쿠키로 교체
    l_visitor = "x4tmffe57hll9d"  # 실제 L-VISITOR 값으로 교체
    gv_statustime = "1751006691755"  # 실제 timestamp로 교체
    
    scraper.manual_cookie_setup(cookie_string, l_visitor, gv_statustime)
    
    # 상품별 조회 테스트
    sales_data = scraper.fetch_product_sales()
    if sales_data:
        scraper.save_to_excel(filename="수동쿠키_매출데이터.xlsx")

if __name__ == "__main__":
    # 일반 로그인 방식
    main()
    
    # 수동 쿠키 방식이 필요한 경우 아래 주석 해제
    # test_with_manual_cookies()