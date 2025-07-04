import os
import sys
import objc
from Cocoa import NSURL
from Quartz import CIImage
from Vision import (
    VNImageRequestHandler,
    VNDetectFaceRectanglesRequest
)


def detect_faces(image_path):
    # 이미지 로딩
    url = NSURL.fileURLWithPath_(image_path)
    ci_image = CIImage.imageWithContentsOfURL_(url)
    if ci_image is None:
        print("이미지를 불러올 수 없습니다.")
        return 0

    # 얼굴 인식 요청 설정
    face_detection_request = VNDetectFaceRectanglesRequest.alloc().init()
    handler = VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, None)

    # 요청 실행
    success, error = handler.performRequests_error_([face_detection_request], None)
    if not success:
        print("얼굴 인식 실패:", error)
        return 0

    # 결과 출력
    results = face_detection_request.results()
    print(f"총 얼굴 수: {len(results)}")
    for i, face_observation in enumerate(results):
        bbox = face_observation.boundingBox()
        print(f"얼굴 {i+1}: Bounding Box = {bbox}")
    return len(results)


# 폴더 내 이미지 일괄 처리 함수 추가
def process_images_in_folder(folder_path):
    valid_extensions = {".jpg", ".jpeg", ".png"}
    total_faces = 0
    for filename in os.listdir(folder_path):
        if any(filename.lower().endswith(ext) for ext in valid_extensions):
            image_path = os.path.join(folder_path, filename)
            print(f"\n처리 중: {image_path}")
            face_count = detect_faces(image_path)
            total_faces += face_count

            if face_count > 0:
                new_filename = f"얼굴인식완료_{filename}"
                new_path = os.path.join(folder_path, new_filename)
                # 파일명이 이미 원하는 형식인지 확인하여 중복 변경 방지
                if not filename.startswith("얼굴인식완료_"):
                    os.rename(image_path, new_path)
    print(f"\n전체 얼굴 수: {total_faces}")

# 테스트할 폴더 경로를 입력하세요
folder_path = "/Users/gimdonghun/Downloads/신라04"
process_images_in_folder(folder_path)