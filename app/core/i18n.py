# app/core/i18n.py - 다국어 지원 모듈
import json
import os
from typing import Dict, Any, Optional
from fastapi import Request
from app.core.config import settings

class I18n:
    def __init__(self):
        self.translations = {}
        self.default_lang = 'ko'
        self.supported_langs = ['ko', 'zh']
        self.load_translations()
    
    def load_translations(self):
        """번역 파일들을 로드합니다."""
        # 설정에서 translations 디렉토리 경로 가져오기
        translations_dir = settings.translations_dir
        
        for lang in self.supported_langs:
            file_path = os.path.join(translations_dir, f"{lang}.json")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translations[lang] = json.load(f)
                print(f"✅ {lang} 번역 파일 로드 완료")
            except FileNotFoundError:
                print(f"⚠️ 번역 파일을 찾을 수 없습니다: {file_path}")
                self.translations[lang] = {}
            except json.JSONDecodeError as e:
                print(f"❌ JSON 파싱 오류 in {file_path}: {e}")
                self.translations[lang] = {}
            except Exception as e:
                print(f"❌ 번역 파일 로드 오류 in {file_path}: {e}")
                self.translations[lang] = {}
    
    def get_user_language(self, request: Request) -> str:
        """사용자의 언어 설정을 가져옵니다."""
        # 1. 쿠키에서 언어 설정 확인
        lang = request.cookies.get('language')
        if lang in self.supported_langs:
            return lang
        
        # 2. Accept-Language 헤더에서 확인
        accept_language = request.headers.get('accept-language', '')
        if 'zh' in accept_language.lower():
            return 'zh'
        
        # 3. 기본값 반환
        return self.default_lang
    
    def t(self, key: str, lang: str = None, **kwargs) -> str:
        """번역된 텍스트를 반환합니다."""
        if lang is None:
            lang = self.default_lang
        
        if lang not in self.translations:
            lang = self.default_lang
        
        # 중첩된 키 지원 (예: "common.buttons.save")
        keys = key.split('.')
        value = self.translations.get(lang, {})
        
        try:
            for k in keys:
                value = value[k]
        except (KeyError, TypeError):
            # 번역이 없으면 키 자체를 반환
            return key
        
        # 문자열 포매팅 지원
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                return value
        
        return value

# 전역 i18n 인스턴스
i18n = I18n()