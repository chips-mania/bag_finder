import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import threading
import logging

logger = logging.getLogger(__name__)

class SessionCache:
    """세션 캐시 (메모리 기반).
    Ultralytics SAM 흐름에 맞춰 '임베딩' 대신 '이미지 경로/메타'를 저장합니다.
    구조 예:
      {
        session_id: {
          "image_path": "sessions/<id>.png",
          "width": 1024,
          "height": 768,
          "format": "PNG",
          "masks": [...],            # 선택: 예측된 마스크 히스토리
          "timestamp": datetime(...) # 마지막 접근/업데이트 시각
        }
      }
    """

    def __init__(self, ttl_minutes: int = 10):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_minutes = ttl_minutes
        self.lock = threading.RLock()
        self._start_cleanup_thread()

    # ──────────────────────────────────────────────────────────────────
    # 내부: 주기적 만료 정리
    # ──────────────────────────────────────────────────────────────────
    def _start_cleanup_thread(self):
        def cleanup():
            while True:
                try:
                    time.sleep(60)  # 1분마다 체크
                    self._cleanup_expired_sessions()
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")

        threading.Thread(target=cleanup, daemon=True).start()

    def _cleanup_expired_sessions(self):
        with self.lock:
            now = datetime.utcnow()
            expired = [
                sid for sid, data in self.cache.items()
                if now - data.get("timestamp", now) > timedelta(minutes=self.ttl_minutes)
            ]
            for sid in expired:
                del self.cache[sid]
                logger.info(f"Expired session removed: {sid}")

    # ──────────────────────────────────────────────────────────────────
    # 공개 API
    # ──────────────────────────────────────────────────────────────────
    def create_session(self, data: Dict[str, Any], session_id: Optional[str] = None) -> str:
        """세션 생성.
        data 예시: {"image_path": str, "width": int, "height": int, "format": str}
        session_id를 넘기지 않으면 자동 생성.
        """
        if not isinstance(data, dict):
            raise TypeError("data must be a dict containing image metadata (image_path, width, height, format)")

        required = ["image_path", "width", "height", "format"]
        for k in required:
            if k not in data:
                raise ValueError(f"data missing required key: {k}")

        with self.lock:
            sid = session_id or str(uuid.uuid4())
            self.cache[sid] = {
                "image_path": data["image_path"],
                "width": int(data["width"]),
                "height": int(data["height"]),
                "format": str(data["format"]),
                "masks": data.get("masks", []),
                "timestamp": datetime.utcnow(),
            }
            logger.info(f"New session created: {sid}")
            return sid

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 전체 데이터(dict) 반환. 접근 시각 갱신."""
        with self.lock:
            sess = self.cache.get(session_id)
            if sess:
                sess["timestamp"] = datetime.utcnow()
                return sess
            return None

    def update_session_masks(self, session_id: str, mask: Any) -> bool:
        """세션에 마스크(혹은 마스크 메타)를 추가."""
        with self.lock:
            sess = self.cache.get(session_id)
            if not sess:
                return False
            sess.setdefault("masks", []).append(mask)
            sess["timestamp"] = datetime.utcnow()
            return True

    def delete_session(self, session_id: str) -> bool:
        with self.lock:
            if session_id in self.cache:
                del self.cache[session_id]
                logger.info(f"Session deleted: {session_id}")
                return True
            return False

    def get_session_count(self) -> int:
        with self.lock:
            return len(self.cache)

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 요약 정보 반환(가능하면 이미지 메타 포함)."""
        with self.lock:
            sess = self.cache.get(session_id)
            if not sess:
                return None
            now = datetime.utcnow()
            info = {
                "session_id": session_id,
                "timestamp": sess.get("timestamp"),
                "mask_count": len(sess.get("masks", [])),
                "is_expired": (now - sess.get("timestamp", now)) > timedelta(minutes=self.ttl_minutes),
            }
            # 이미지 메타를 함께 주면 프론트 좌표 스케일링 등에 유용
            for k in ("image_path", "width", "height", "format"):
                if k in sess:
                    info[k] = sess[k]
            return info
