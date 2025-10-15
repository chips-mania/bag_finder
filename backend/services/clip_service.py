"""
CLIP 모델 서비스 (전역 싱글톤)
"""
import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import numpy as np
from typing import List

# 전역 변수로 모델/프로세서 로드 (서버 시작 시 1회만)
device = "cuda" if torch.cuda.is_available() else "cpu"
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

print(f"[CLIP Service] Model loaded on device: {device}")


def convert_png_to_rgb_with_white_bg(image: Image.Image) -> Image.Image:
    """
    PIL 이미지 객체를 받아 투명 배경(RGBA)을 흰색 배경(RGB)으로 변환합니다.
    """
    if image.mode == 'RGBA':
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        return background
    else:
        return image.convert("RGB")


def get_image_embedding(image: Image.Image) -> List[float]:
    """
    PIL 이미지를 받아 CLIP 임베딩 벡터(512차원)를 반환합니다.
    
    Args:
        image: PIL Image 객체
        
    Returns:
        512차원 리스트 (float)
    """
    image_rgb = convert_png_to_rgb_with_white_bg(image)
    inputs = clip_processor(images=image_rgb, return_tensors="pt", padding=True).to(device)
    
    with torch.no_grad():
        embedding = clip_model.get_image_features(**inputs).cpu().numpy()[0]
    
    return embedding.tolist()

