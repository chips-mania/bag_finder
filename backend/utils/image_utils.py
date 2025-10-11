import io
from PIL import Image
import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

def validate_image_file(file_content: bytes, max_size_mb: int = 15) -> bool:
    """이미지 파일의 유효성을 검사합니다"""
    try:
        # 파일 크기 검사
        if len(file_content) > max_size_mb * 1024 * 1024:
            logger.warning(f"File too large: {len(file_content)} bytes")
            return False
        
        # 이미지 형식 검사
        image = Image.open(io.BytesIO(file_content))
        
        # 지원하는 형식인지 확인
        if image.format not in ['JPEG', 'PNG', 'WEBP']:
            logger.warning(f"Unsupported image format: {image.format}")
            return False
        
        # 이미지가 실제로 로드 가능한지 확인
        image.verify()
        
        return True
        
    except Exception as e:
        logger.error(f"Image validation failed: {e}")
        return False

def resize_image(image: Image.Image, max_size: int = 1024) -> Image.Image:
    """이미지를 지정된 최대 크기로 리사이즈합니다"""
    w, h = image.size
    
    # 이미 최대 크기 이하인 경우 그대로 반환
    if max(w, h) <= max_size:
        return image
    
    # 비율을 유지하면서 리사이즈
    if w > h:
        new_w = max_size
        new_h = int(h * max_size / w)
    else:
        new_h = max_size
        new_w = int(w * max_size / h)
    
    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)

def get_image_info(image: Image.Image) -> dict:
    """이미지 정보를 반환합니다"""
    return {
        'width': image.width,
        'height': image.height,
        'format': image.format,
        'mode': image.mode,
        'size_bytes': len(image.tobytes())
    }

def convert_to_rgb(image: Image.Image) -> Image.Image:
    """이미지를 RGB 형식으로 변환합니다"""
    if image.mode == 'RGBA':
        # 투명 배경을 흰색으로 변환
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])  # 알파 채널을 마스크로 사용
        return background
    elif image.mode == 'L':
        # 그레이스케일을 RGB로 변환
        return image.convert('RGB')
    elif image.mode == 'RGB':
        return image
    else:
        # 기타 형식을 RGB로 변환
        return image.convert('RGB')

def resize_mask(mask: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
    """
    마스크를 지정된 크기로 리사이즈합니다 (Nearest Neighbor 사용)
    
    Args:
        mask: 이진 마스크 (H, W) uint8
        target_size: (width, height) 목표 크기
        
    Returns:
        리사이즈된 마스크 (H, W) uint8
    """
    if mask.shape == (target_size[1], target_size[0]):
        return mask
    
    mask_pil = Image.fromarray(mask)
    mask_resized = mask_pil.resize(target_size, Image.NEAREST)
    return np.array(mask_resized)

def ensure_mask_size(mask: np.ndarray, reference_image: Image.Image) -> np.ndarray:
    """
    마스크 크기를 참조 이미지와 동일하게 맞춥니다
    
    Args:
        mask: 이진 마스크 (H, W) uint8
        reference_image: 참조 이미지 (PIL Image)
        
    Returns:
        크기가 맞춰진 마스크 (H, W) uint8
    """
    target_size = (reference_image.width, reference_image.height)
    return resize_mask(mask, target_size)
