# embed_bags_script.py

import os
from dotenv import load_dotenv
import supabase
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
import torch

def convert_png_to_rgb_with_white_bg(image):
    """
    PIL 이미지 객체를 받아 투명 배경(RGBA)을 흰색 배경(RGB)으로 바꿔줍니다.
    """
    if image.mode == 'RGBA':
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        return background
    else:
        return image.convert("RGB")

# ----------------------------------------------------
# 1. 초기화
# ----------------------------------------------------
print("1. 초기화를 시작합니다...")
load_dotenv()
device = "cuda" if torch.cuda.is_available() else "cpu"

# 모델 로드
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# Supabase 클라이언트 연결
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

try:
    client = supabase.create_client(supabase_url, supabase_key)
    print("✅ Supabase DB에 성공적으로 연결되었습니다.")
except Exception as e:
    print(f"🚨 Supabase 연결 실패: {e}")
    exit()

# ----------------------------------------------------
# 2. 모든 하위 폴더의 이미지 처리 및 두 테이블에 나눠서 저장
# ----------------------------------------------------
# 👈 8개의 카테고리 폴더가 들어있는 '최상위 폴더' 경로를 입력하세요.
base_folder_path = "./crop_img" 
bags_table_name = "bags"
embeddings_table_name = "image_embeddings"

print(f"\n2. '{base_folder_path}'의 모든 이미지 처리를 시작합니다...")

# os.walk로 모든 이미지 경로 수집
image_paths = []
for root, dirs, files in os.walk(base_folder_path):
    for file_name in files:
        if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_paths.append(os.path.join(root, file_name))

if not image_paths:
    print(f"🚨 오류: '{base_folder_path}'에서 처리할 이미지를 찾지 못했습니다.")
    exit()

print(f"✅ 총 {len(image_paths)}개의 이미지를 찾았습니다. 이제 임베딩 및 저장을 시작합니다.")

for image_path in image_paths:
    try:
        file_name = os.path.basename(image_path)
        # 파일 확장자를 제거하여 고유 ID로 사용
        bag_id = os.path.splitext(file_name)[0]
        
        # --- a. 이미지 처리 및 벡터화 ---
        image_obj = Image.open(image_path)
        image_rgb = convert_png_to_rgb_with_white_bg(image_obj)
        inputs = clip_processor(images=image_rgb, return_tensors="pt", padding=True).to(device)
        with torch.no_grad():
            embedding = clip_model.get_image_features(**inputs).cpu().numpy()[0]

        # --- b. `bags` 테이블에 저장할 메타데이터 레코드 생성 ---
        # 참고: 실제 프로젝트에서는 이 정보를 파일명이나 별도의 CSV 파일에서 가져와야 합니다.
        bag_record = {
            'bag_id': bag_id,
            'brand': 'Test Brand',
            'bag_name': bag_id.replace('_', ' ').replace('-', ' ').title(), # 파일명으로 가방 이름 생성
            'price': 150000, # 임시 가격
            'material': 'Canvas', # 임시 소재
            'color': 'Black', # 임시 색상
            'category': os.path.basename(os.path.dirname(image_path)), # 부모 폴더명을 카테고리로 사용
            'link': f'http://example.com/products/{bag_id}', # 임시 링크
            'thumbnail': 'http://example.com/thumb.jpg', # 임시 썸네일
            'detail': 'This is a sample bag description.' # 임시 설명
        }
        
        # --- c. `image_embeddings` 테이블에 저장할 임베딩 레코드 생성 ---
        embedding_record = {
            'bag_id': bag_id,
            'embed': embedding.tolist()
        }
        
        # --- d. 두 테이블에 데이터 저장 (Upsert 사용) ---
        client.table(bags_table_name).upsert(bag_record).execute()
        client.table(embeddings_table_name).upsert(embedding_record).execute()
        
        print(f"  - ✅ 성공: '{bag_id}' 데이터가 두 테이블에 저장/업데이트되었습니다.")

    except Exception as e:
        print(f"  - 🚨 오류: '{image_path}' 처리 중 문제 발생: {e}")

print("\n🎉 모든 이미지 처리가 완료되었습니다!")