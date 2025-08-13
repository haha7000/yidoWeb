
-- 수수료 설정 user_id 마이그레이션 롤백 스크립트
-- 주의: 이 스크립트 실행 시 사용자별 격리 설정이 해제됩니다!

BEGIN;

-- 1. 외래키 제약조건 제거
ALTER TABLE fee_settings DROP CONSTRAINT IF EXISTS fk_fee_settings_user_id;

-- 2. user_id 컬럼 제거
ALTER TABLE fee_settings DROP COLUMN IF EXISTS user_id;

COMMIT;

-- 롤백 완료 메시지
SELECT '롤백 완료: fee_settings에서 user_id 컬럼이 제거되었습니다.' as message;
