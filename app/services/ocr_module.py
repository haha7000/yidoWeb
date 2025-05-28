import AppKit
import os

try:
    from Vision import (
        VNRecognizeTextRequest,
        VNImageRequestHandler,
        VNRecognizedTextObservation,
        VNRequestTextRecognitionLevelAccurate
    )
    from Quartz import CIImage
    VISION_AVAILABLE = True
except ModuleNotFoundError:
    print("⚠️ macOS Vision 모듈이 없습니다. OCR 기능 비활성화됨.")
    VISION_AVAILABLE = False

def VisionOcr(image_path):
    if not VISION_AVAILABLE:
        raise RuntimeError("macOS Vision 프레임워크를 사용할 수 없습니다.")
    
    # 이미지 파일 검증
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
    
    if not image_path.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.tif')):
        raise ValueError(f"지원하지 않는 이미지 형식입니다: {image_path}")

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


if __name__ == "__main__":
    print(VisionOcr("/Users/gimdonghun/Downloads/asdqwe.png"))