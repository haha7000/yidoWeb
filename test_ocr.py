#!/usr/bin/env python3
"""
OCR 기능 테스트 스크립트
EC2에서 Tesseract OCR이 정상 작동하는지 확인
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.ocr_module import VisionOcr, get_available_ocr_engines
import platform

def test_ocr_availability():
    """OCR 엔진 사용 가능성 테스트"""
    print("=" * 50)
    print("🔍 OCR 기능 테스트")
    print("=" * 50)
    
    print(f"🖥️  운영체제: {platform.system()}")
    print(f"🐍 Python 버전: {platform.python_version()}")
    print()
    
    engines = get_available_ocr_engines()
    if engines:
        print("✅ 사용 가능한 OCR 엔진:")
        for engine in engines:
            print(f"   - {engine}")
    else:
        print("❌ 사용 가능한 OCR 엔진이 없습니다!")
        return False
    
    return True

def test_tesseract_installation():
    """Tesseract 설치 상태 확인"""
    print("\n" + "=" * 50)
    print("🔧 Tesseract 설치 확인")
    print("=" * 50)
    
    try:
        import pytesseract
        print("✅ pytesseract 모듈 로드 성공")
        
        # Tesseract 버전 확인
        version = pytesseract.get_tesseract_version()
        print(f"📌 Tesseract 버전: {version}")
        
        # 사용 가능한 언어 확인
        langs = pytesseract.get_languages()
        print(f"🌍 지원 언어: {', '.join(langs)}")
        
        if 'kor' in langs:
            print("✅ 한글 언어팩 사용 가능")
        else:
            print("⚠️ 한글 언어팩이 없습니다. 다음 명령어로 설치하세요:")
            print("sudo apt install tesseract-ocr-kor")
            
        return True
        
    except Exception as e:
        print(f"❌ Tesseract 테스트 실패: {e}")
        return False

def create_test_image():
    """테스트용 이미지 생성"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import tempfile
        
        # 테스트 이미지 생성
        img = Image.new('RGB', (400, 200), color='white')
        draw = ImageDraw.Draw(img)
        
        # 텍스트 추가
        text = "Hello World\n안녕하세요\n123456"
        try:
            # 기본 폰트 사용
            font = ImageFont.load_default()
        except:
            font = None
            
        draw.text((50, 50), text, fill='black', font=font)
        
        # 임시 파일로 저장
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        img.save(temp_file.name)
        
        print(f"✅ 테스트 이미지 생성: {temp_file.name}")
        return temp_file.name
        
    except Exception as e:
        print(f"❌ 테스트 이미지 생성 실패: {e}")
        return None

def test_ocr_functionality():
    """실제 OCR 기능 테스트"""
    print("\n" + "=" * 50)
    print("🧪 OCR 기능 실행 테스트")
    print("=" * 50)
    
    # 테스트 이미지 생성
    test_image_path = create_test_image()
    if not test_image_path:
        print("❌ 테스트 이미지 생성 실패")
        return False
    
    try:
        # OCR 실행
        print("🔄 OCR 실행 중...")
        result = VisionOcr(test_image_path)
        
        if result.strip():
            print("✅ OCR 성공!")
            print("📝 인식된 텍스트:")
            print("-" * 30)
            print(result)
            print("-" * 30)
        else:
            print("⚠️ OCR 실행되었지만 텍스트를 인식하지 못했습니다.")
            
        # 임시 파일 정리
        os.unlink(test_image_path)
        return True
        
    except Exception as e:
        print(f"❌ OCR 실행 실패: {e}")
        
        # 임시 파일 정리
        if os.path.exists(test_image_path):
            os.unlink(test_image_path)
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 DbTest OCR 기능 종합 테스트 시작\n")
    
    success_count = 0
    total_tests = 3
    
    # 1. OCR 엔진 사용 가능성 확인
    if test_ocr_availability():
        success_count += 1
    
    # 2. Tesseract 설치 확인
    if test_tesseract_installation():
        success_count += 1
    
    # 3. 실제 OCR 기능 테스트
    if test_ocr_functionality():
        success_count += 1
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    print(f"✅ 성공: {success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("🎉 모든 테스트 통과! OCR 기능이 정상 작동합니다.")
        return True
    else:
        print("⚠️ 일부 테스트 실패. 설정을 확인해주세요.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 