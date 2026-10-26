# 필름캠 (FilmCam)

감성 필터를 실시간으로 적용해 촬영할 수 있는 안드로이드 카메라 앱 (Kotlin + CameraX).

## 필터
원본 · 필름 · 빈티지 · 몽환 · 노을 · 새벽 · 민트 · 폴라로이드 · 로모 · 흑백

- 색감(채도/대비/톤/페이드)과 비네팅은 촬영 전 프리뷰에도 실시간 반영
- 필름 입자(grain)는 저장되는 사진에만 적용
- 전/후면 카메라 전환, 갤러리(`Pictures/FilmCam`)에 JPEG 저장

## 실행
1. Android Studio(Koala 이상)에서 `film-cam/` 폴더 열기
2. 실기기(USB 디버깅) 또는 카메라 지원 에뮬레이터로 Run ▶
   - minSdk 29 (Android 10+)

## 필터 추가
`CameraFilter.kt`의 `CameraFilter.all` 리스트에 한 줄 추가하면 됩니다.

## 폰에 설치하기 (APK)
1. GitHub 저장소 → **Actions** → *Build FilmCam APK* → 최신 실행 → **Artifacts**의 `FilmCam-apk` 다운로드 (GitHub 로그인 필요 = 본인만 받을 수 있음)
2. zip을 풀고 `.apk`를 폰으로 옮긴 뒤 열기 → "이 출처의 앱 설치 허용"은 설치 후 **다시 꺼두기**
3. 첫 실행 시 카메라 권한만 허용 (그 외 권한 없음)
4. (선택) 설치 전 PC에서 `sha256sum -c *.sha256`로 파일 무결성 확인

> 서명 키: 기본은 빌드마다 임시 디버그 키라 **업데이트 시 기존 앱을 지우고 재설치**해야 합니다.
> 고정 키를 쓰려면 저장소 Secrets에 `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`를 등록하세요.
> (키 생성: `keytool -genkeypair -v -keystore release.jks -alias filmcam -keyalg RSA -keysize 4096 -validity 10000` → `base64 -w0 release.jks`)

## 보안 설계
- **INTERNET 권한 없음**: 사진이 기기 밖으로 나갈 수 없음 (빌드 시 자동 검증, 있으면 CI 실패)
- 권한은 `CAMERA` 하나뿐, 위치 정보(EXIF GPS)는 저장하지 않음
- 백업/기기 이전 비활성화, 디버깅 불가, 평문 통신 금지, R8 난독화·축소
- 외부 앱이 호출할 수 있는 컴포넌트는 런처 Activity뿐
- CI는 `contents: read` 최소 권한, 체크아웃 토큰 미보존
