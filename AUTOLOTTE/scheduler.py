import schedule
import time
import logging
import threading
import sys
from datetime import datetime
from lotte_scraper import LotteDutyFreeSales

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lotte_scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class LotteScheduler:
    def __init__(self):
        self.scraper = None
        self.schedule_times = []  # 여러 실행 시간 저장
        self.is_running = True
        self.login_credentials = {
            'user_id': 'T301912',
            'password': 'huixin210@@'
        }
    
    def run_daily_job(self):
        """매일 실행되는 작업"""
        try:
            current_time = datetime.now().strftime('%H:%M')
            logging.info("=" * 60)
            logging.info(f"🚀 롯데면세점 매출 데이터 자동 조회 시작 ({current_time})")
            logging.info("=" * 60)
            
            # 스크래퍼 초기화
            self.scraper = LotteDutyFreeSales()
            
            # 로그인
            logging.info("🔐 로그인 시도 중...")
            if not self.scraper.login(
                self.login_credentials['user_id'], 
                self.login_credentials['password']
            ):
                logging.error("❌ 로그인 실패 - 작업 중단")
                return False
            
            logging.info("✅ 로그인 성공")
            
            # 상품별 매출 데이터 조회
            logging.info("📦 상품별 매출 데이터 조회 중...")
            sales_data = self.scraper.fetch_product_sales()
            
            if sales_data:
                logging.info(f"✅ {len(sales_data)}건의 상품별 매출 데이터 조회 완료")
                
                # 파일명에 날짜와 시간 포함
                filename = f"상품별_매출데이터_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                
                # 엑셀 저장
                logging.info("💾 엑셀 파일 저장 중...")
                excel_file = self.scraper.save_to_excel(filename=filename)
                
                if excel_file:
                    logging.info(f"🎉 상품별 매출 데이터 저장 완료: {excel_file}")
                    return True
                else:
                    logging.error("❌ 엑셀 저장 실패")
                    return False
            
            else:
                logging.warning("❌ 상품별 매출 데이터 조회 실패 - 브랜드별 조회로 폴백")
                
                # 브랜드별 조회로 폴백
                sales_data = self.scraper.fetch_brand_sales()
                
                if sales_data:
                    logging.info(f"✅ 브랜드별 데이터 {len(sales_data)}건 조회됨")
                    
                    filename = f"브랜드별_매출데이터_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                    excel_file = self.scraper.save_to_excel(filename=filename)
                    
                    if excel_file:
                        logging.info(f"🎉 브랜드별 매출 데이터 저장 완료: {excel_file}")
                        return True
                    else:
                        logging.error("❌ 엑셀 저장 실패")
                        return False
                else:
                    logging.error("❌ 모든 매출 데이터 조회 실패")
                    return False
        
        except Exception as e:
            logging.error(f"❌ 작업 실행 중 오류 발생: {str(e)}")
            return False
        
        finally:
            logging.info("=" * 60)
            logging.info(f"작업 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info("=" * 60)
    
    def add_schedule_time(self, new_time):
        """새로운 스케줄 시간 추가"""
        try:
            # 시간 형식 검증
            datetime.strptime(new_time, "%H:%M")
            
            if new_time in self.schedule_times:
                print(f"⚠️ {new_time}는 이미 등록된 시간입니다.")
                return False
            
            # 새로운 스케줄 추가
            schedule.every().day.at(new_time).do(self.run_daily_job)
            self.schedule_times.append(new_time)
            self.schedule_times.sort()  # 시간 순으로 정렬
            
            logging.info(f"➕ 새로운 스케줄 시간 추가: {new_time}")
            print(f"✅ {new_time} 스케줄이 추가되었습니다")
            
            return True
        except ValueError:
            print("❌ 올바른 시간 형식이 아닙니다. HH:MM 형식으로 입력해주세요.")
            return False
        except Exception as e:
            logging.error(f"❌ 스케줄 시간 추가 실패: {str(e)}")
            print(f"❌ 스케줄 시간 추가 실패: {str(e)}")
            return False
    
    def remove_schedule_time(self, time_to_remove):
        """스케줄 시간 제거"""
        try:
            if time_to_remove not in self.schedule_times:
                print(f"⚠️ {time_to_remove}는 등록되지 않은 시간입니다.")
                return False
            
            # 해당 시간의 스케줄을 찾아서 제거
            schedule.clear()  # 모든 스케줄 삭제
            self.schedule_times.remove(time_to_remove)
            
            # 남은 시간들로 다시 스케줄 등록
            for time_str in self.schedule_times:
                schedule.every().day.at(time_str).do(self.run_daily_job)
            
            logging.info(f"➖ 스케줄 시간 제거: {time_to_remove}")
            print(f"✅ {time_to_remove} 스케줄이 제거되었습니다")
            
            return True
        except Exception as e:
            logging.error(f"❌ 스케줄 시간 제거 실패: {str(e)}")
            print(f"❌ 스케줄 시간 제거 실패: {str(e)}")
            return False
    
    def show_menu(self):
        """메뉴 표시"""
        print("\n" + "=" * 60)
        print("🤖 롯데면세점 스케줄러 제어 메뉴")
        print("=" * 60)
        if self.schedule_times:
            print(f"📅 등록된 스케줄 ({len(self.schedule_times)}개):")
            for i, time_str in enumerate(self.schedule_times, 1):
                print(f"   {i}. 매일 {time_str}")
        else:
            print("📅 등록된 스케줄이 없습니다")
        
        print(f"🕐 현재 시간: {datetime.now().strftime('%H:%M:%S')}")
        print("\n명령어:")
        print("  1. 'add' 또는 'a'    - 스케줄 시간 추가")
        print("  2. 'remove' 또는 'rm' - 스케줄 시간 제거")
        print("  3. 'list' 또는 'ls'  - 스케줄 목록 보기")
        print("  4. 'run' 또는 'r'    - 즉시 실행")
        print("  5. 'status' 또는 's' - 상태 확인")
        print("  6. 'clear' 또는 'c'  - 모든 스케줄 삭제")
        print("  7. 'quit' 또는 'q'   - 종료")
        print("  8. 'help' 또는 'h'   - 도움말")
        print("=" * 60)
    
    def handle_user_input(self):
        """사용자 입력 처리 (별도 스레드)"""
        while self.is_running:
            try:
                command = input("\n명령어를 입력하세요 (h:도움말): ").strip().lower()
                
                if command in ['add', 'a']:
                    while True:
                        try:
                            new_time = input("추가할 실행 시간을 입력하세요 (HH:MM): ").strip()
                            if new_time:
                                self.add_schedule_time(new_time)
                            break
                        except KeyboardInterrupt:
                            print("\n시간 추가가 취소되었습니다.")
                            break
                
                elif command in ['remove', 'rm']:
                    if not self.schedule_times:
                        print("❌ 제거할 스케줄이 없습니다.")
                        continue
                    
                    print("\n현재 등록된 스케줄:")
                    for i, time_str in enumerate(self.schedule_times, 1):
                        print(f"  {i}. {time_str}")
                    
                    try:
                        choice = input("제거할 시간을 입력하세요 (HH:MM 또는 번호): ").strip()
                        
                        # 번호로 입력한 경우
                        if choice.isdigit():
                            idx = int(choice) - 1
                            if 0 <= idx < len(self.schedule_times):
                                time_to_remove = self.schedule_times[idx]
                                self.remove_schedule_time(time_to_remove)
                            else:
                                print("❌ 잘못된 번호입니다.")
                        # 시간으로 입력한 경우
                        else:
                            self.remove_schedule_time(choice)
                    except KeyboardInterrupt:
                        print("\n시간 제거가 취소되었습니다.")
                
                elif command in ['list', 'ls']:
                    print(f"\n📅 등록된 스케줄 ({len(self.schedule_times)}개):")
                    if self.schedule_times:
                        for i, time_str in enumerate(self.schedule_times, 1):
                            print(f"  {i}. 매일 {time_str}")
                    else:
                        print("  등록된 스케줄이 없습니다.")
                
                elif command in ['r', 'run']:
                    print("🚀 즉시 실행합니다...")
                    threading.Thread(target=self.run_daily_job, daemon=True).start()
                
                elif command in ['s', 'status']:
                    print(f"\n📊 스케줄러 상태:")
                    print(f"   🕐 등록된 스케줄 수: {len(self.schedule_times)}개")
                    if self.schedule_times:
                        print(f"   📅 스케줄 시간: {', '.join(self.schedule_times)}")
                    print(f"   ⏰ 현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # 다음 실행 시간들 표시
                    next_runs = []
                    for job in schedule.jobs:
                        if job.next_run:
                            next_runs.append(job.next_run)
                    
                    if next_runs:
                        next_runs.sort()
                        print(f"   ⏭️  다음 실행들:")
                        for next_run in next_runs:
                            print(f"      - {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    print(f"   📊 등록된 작업 수: {len(schedule.jobs)}개")
                
                elif command in ['clear', 'c']:
                    confirm = input("⚠️ 모든 스케줄을 삭제하시겠습니까? (y/N): ").strip().lower()
                    if confirm in ['y', 'yes']:
                        schedule.clear()
                        self.schedule_times.clear()
                        print("✅ 모든 스케줄이 삭제되었습니다.")
                    else:
                        print("취소되었습니다.")
                
                elif command in ['h', 'help']:
                    self.show_menu()
                
                elif command in ['q', 'quit']:
                    print("👋 스케줄러를 종료합니다...")
                    self.is_running = False
                    break
                
                else:
                    print("❌ 알 수 없는 명령어입니다. 'h' 또는 'help'를 입력하세요.")
            
            except KeyboardInterrupt:
                print("\n👋 스케줄러를 종료합니다...")
                self.is_running = False
                break
            except Exception as e:
                print(f"❌ 입력 처리 오류: {str(e)}")
    
    def start_scheduler(self, initial_times=None):
        """스케줄러 시작"""
        if initial_times:
            self.schedule_times = initial_times.copy()
            for time_str in initial_times:
                schedule.every().day.at(time_str).do(self.run_daily_job)
            
            logging.info(f"🕐 스케줄러 시작 - {len(initial_times)}개 시간에 실행됩니다: {', '.join(initial_times)}")
        else:
            logging.info("🕐 스케줄러 시작 - 스케줄이 등록되지 않았습니다")
        
        # 즉시 한번 실행 여부 확인
        try:
            run_now = input("🧪 지금 바로 테스트 실행할까요? (y/N): ").strip().lower()
            if run_now in ['y', 'yes']:
                print("🧪 테스트로 즉시 한번 실행합니다...")
                self.run_daily_job()
        except KeyboardInterrupt:
            print("\n테스트 실행을 건너뜁니다.")
        
        # 메뉴 표시
        self.show_menu()
        
        # 사용자 입력 처리 스레드 시작
        input_thread = threading.Thread(target=self.handle_user_input, daemon=True)
        input_thread.start()
        
        # 스케줄러 실행
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 체크
        except KeyboardInterrupt:
            logging.info("\n👋 사용자가 스케줄러를 중단했습니다")
            self.is_running = False
        except Exception as e:
            logging.error(f"❌ 스케줄러 오류: {str(e)}")
            self.is_running = False

def get_initial_schedule_times():
    """초기 스케줄 시간들 입력받기"""
    times = []
    
    print("🕐 실행 시간을 설정합니다")
    print("여러 시간을 입력하려면 하나씩 입력하세요 (빈 값 입력시 완료)")
    print("예: 09:00, 14:30, 18:00")
    
    while True:
        try:
            if not times:
                time_input = input("첫 번째 실행 시간을 입력하세요 (HH:MM): ").strip()
            else:
                time_input = input(f"추가 실행 시간을 입력하세요 (현재 {len(times)}개, 엔터로 완료): ").strip()
            
            if not time_input:
                if times:
                    break
                else:
                    print("❌ 최소 하나의 실행 시간은 입력해야 합니다.")
                    continue
            
            # 시간 형식 검증
            datetime.strptime(time_input, "%H:%M")
            
            if time_input in times:
                print(f"⚠️ {time_input}는 이미 입력된 시간입니다.")
                continue
            
            times.append(time_input)
            times.sort()  # 시간 순으로 정렬
            
            print(f"✅ {time_input} 추가됨. 현재 등록된 시간: {', '.join(times)}")
            
        except ValueError:
            print("❌ 올바른 시간 형식이 아닙니다. HH:MM 형식으로 입력해주세요.")
        except KeyboardInterrupt:
            if times:
                print(f"\n현재까지 입력된 {len(times)}개 시간으로 진행합니다.")
                break
            else:
                print("\n👋 설정이 취소되었습니다.")
                return None
    
    return times

def main():
    """메인 함수"""
    print("🤖 롯데면세점 매출 데이터 자동 스케줄러")
    print("=" * 60)
    
    # 초기 실행 시간들 설정
    initial_times = get_initial_schedule_times()
    
    if not initial_times:
        return
    
    print(f"\n📅 설정된 실행 시간: {', '.join(initial_times)}")
    
    # 스케줄러 시작
    scheduler = LotteScheduler()
    scheduler.start_scheduler(initial_times)

if __name__ == "__main__":
    main()