import os
import platform

# macOS Vision Framework 시도
VISION_AVAILABLE = False
TESSERACT_AVAILABLE = False

if platform.system() == "Darwin":  # macOS
    try:
        import AppKit
        from Vision import (
            VNRecognizeTextRequest,
            VNImageRequestHandler,
            VNRecognizedTextObservation,
            VNRequestTextRecognitionLevelAccurate
        )
        from Quartz import CIImage
        VISION_AVAILABLE = True
        print("✅ macOS Vision 프레임워크 사용 가능")
    except ImportError as e:
        print(f"⚠️ macOS Vision 모듈 로드 실패: {e}")

# Tesseract OCR 시도 (Linux/Windows/macOS 공통)
try:
    import pytesseract
    from PIL import Image
    import cv2
    import numpy as np
    TESSERACT_AVAILABLE = True
    print("✅ Tesseract OCR 사용 가능")
except ImportError as e:
    print(f"⚠️ Tesseract 모듈 로드 실패: {e}")

def VisionOcr(image_path):
    """크로스 플랫폼 OCR 함수"""
    # 이미지 파일 검증
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
    
    if not image_path.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.tif')):
        raise ValueError(f"지원하지 않는 이미지 형식입니다: {image_path}")

    # macOS Vision Framework 우선 사용
    if VISION_AVAILABLE:
        return _vision_ocr_macos(image_path)
    
    # Linux/Windows에서는 Tesseract 사용
    elif TESSERACT_AVAILABLE:
        return _tesseract_ocr(image_path)
    
    else:
        raise RuntimeError("OCR 프레임워크를 사용할 수 없습니다. macOS Vision 또는 Tesseract가 필요합니다.")

def _vision_ocr_macos(image_path):
    """macOS Vision Framework OCR"""
    def handle_ocr_results(request):
        all_text = []
        observations = request.results()
        for observation in observations:
            if isinstance(observation, VNRecognizedTextObservation):
                candidate = observation.topCandidates_(1)[0]
                all_text.append(candidate.string())
        
        return '\n'.join(all_text)

    # 이미지 불러오기
    image = AppKit.NSImage.alloc().initWithContentsOfFile_(image_path)
    if image is None:
        raise ValueError(f"이미지를 로드할 수 없습니다: {image_path}")
        
    image_data = image.TIFFRepresentation()
    if image_data is None:
        raise ValueError(f"이미지 데이터를 변환할 수 없습니다: {image_path}")

    # CIImage 생성
    ci_image = CIImage.imageWithData_(image_data)

    # Vision 요청 핸들러 설정
    handler = VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, None)

    result_container = {}

    def completion_handler(request, error):
        result_container["text"] = handle_ocr_results(request)

    # OCR 요청 생성
    request = VNRecognizeTextRequest.alloc().initWithCompletionHandler_(completion_handler)
    request.setRecognitionLanguages_(["ko-KR", "en-US"])
    request.setRecognitionLevel_(VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    # OCR 실행
    success, error = handler.performRequests_error_([request], None)
    if error:
        print("❌ OCR 오류:", error)
    return result_container.get("text", "")

def _tesseract_ocr(image_path):
    """Tesseract OCR (Linux/Windows/macOS 공통)"""
    try:
        # 이미지 전처리
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"이미지를 로드할 수 없습니다: {image_path}")
        
        # 그레이스케일 변환
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 노이즈 제거 및 대비 향상
        gray = cv2.medianBlur(gray, 3)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # PIL Image로 변환
        pil_image = Image.fromarray(gray)
        
        # Tesseract 설정 (한글 + 영어)
        custom_config = r'--oem 3 --psm 6 -l kor+eng'
        
        # OCR 실행
        text = pytesseract.image_to_string(pil_image, config=custom_config)
        
        # 결과 정리
        text = text.strip()
        if not text:
            print("⚠️ OCR에서 텍스트를 인식하지 못했습니다.")
        
        return text
        
    except Exception as e:
        print(f"❌ Tesseract OCR 오류: {e}")
        return ""

# 호환성을 위한 별칭
def VisionOcrMacOS(image_path):
    """macOS 전용 OCR (하위 호환성)"""
    if VISION_AVAILABLE:
        return _vision_ocr_macos(image_path)
    else:
        raise RuntimeError("macOS Vision 프레임워크를 사용할 수 없습니다.")

def TesseractOcr(image_path):
    """Tesseract OCR 직접 호출"""
    if TESSERACT_AVAILABLE:
        return _tesseract_ocr(image_path)
    else:
        raise RuntimeError("Tesseract OCR을 사용할 수 없습니다.")

# 사용 가능한 OCR 엔진 정보
def get_available_ocr_engines():
    """사용 가능한 OCR 엔진 목록 반환"""
    engines = []
    if VISION_AVAILABLE:
        engines.append("macOS Vision Framework")
    if TESSERACT_AVAILABLE:
        engines.append("Tesseract OCR")
    return engines

# 초기화 시 정보 출력
print(f"🔍 사용 가능한 OCR 엔진: {', '.join(get_available_ocr_engines()) or '없음'}")
print(f"🖥️ 운영체제: {platform.system()}")