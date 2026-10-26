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
