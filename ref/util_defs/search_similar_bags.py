# search_similar_bags.py (시각화 강화 버전)

import os
from dotenv import load_dotenv
import supabase
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
import torch
import matplotlib.pyplot as plt
import requests
from io import BytesIO
import numpy as np # np.argsort 등을 위해 추가

# --- ( PNG 처리 함수) ---
def convert_png_to_rgb_with_white_bg(image):
    if image.mode == 'RGBA':
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        return background
    else:
        return image.convert("RGB")

# --- (새로운 시각화 함수 추가) ---
def display_results(query_img, results_data, top_k):
    """
    쿼리 이미지와 유사도 검색 결과를 함께 시각화합니다.
    """
    if not results_data:
        print("\n🤔 유사한 상품을 찾지 못했습니다.")
        return

    # 쿼리 이미지 1개 + 결과 이미지들 (최대 top_k개)
    num_display = min(len(results_data), top_k) + 1 
    
    fig, axes = plt.subplots(1, num_display, figsize=(3 * num_display, 4)) # figsize 조정
    
    # axes가 1개일 때 np.array로 감싸서 항상 배열처럼 다룰 수 있도록 합니다.
    # 결과가 0개가 아니기 때문에 이 부분은 안전합니다.
    axes_flat = axes.flatten() 

    # 쿼리 이미지 표시 (가장 왼쪽)
    axes_flat[0].imshow(query_img)
    axes_flat[0].set_title("Query Bag")
    axes_flat[0].axis('off')

    print("\n--- 🔍 최종 검색 결과 ---")
    for i, item in enumerate(results_data):
        if i >= top_k: # top_k까지만 표시
            break

        # 'thumbnail' 대신 'image_url'을 사용하고 싶다면 item['image_url']로 변경
        # 하지만 bags 테이블에는 'thumbnail' 컬럼이 더 적합합니다.
        image_to_display_url = item.get('thumbnail') 
        similarity_score = item['similarity'] * 100
        
        print(f"{i+1}순위: {item.get('bag_name', 'N/A')} by {item.get('brand', 'N/A')} (유사도: {similarity_score:.2f}%)")
        
        if image_to_display_url:
            try:
                # URL에서 이미지 로드
                res = requests.get(image_to_display_url, stream=True)
                res.raise_for_status() # HTTP 오류 발생 시 예외 발생
                img_from_url = Image.open(BytesIO(res.content))
                axes_flat[i+1].imshow(img_from_url)
                axes_flat[i+1].set_title(f"Rank {i+1}\n{item.get('bag_name', '')}", fontsize=8)
            except Exception as img_err:
                print(f"    - 🚨 오류: {image_to_display_url} 로드 실패: {img_err}")
                axes_flat[i+1].set_title(f"Rank {i+1}\nImage Load Error", fontsize=8)
        else:
            axes_flat[i+1].set_title(f"Rank {i+1}\nNo Image URL", fontsize=8)
        
        axes_flat[i+1].axis('off')

    plt.tight_layout()
    plt.show()


# --- 1. 초기화 ---
print("1. 모델 및 클라이언트를 초기화합니다...")
load_dotenv()
device = "cuda" if torch.cuda.is_available() else "cpu"

clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
client = supabase.create_client(supabase_url, supabase_key)
print("✅ 초기화 완료.")

# --- 2. 검색 실행 ---
# 👈 여기에 검색하고 싶은 이미지의 '로컬 경로'를 입력하세요.
# 참고: 이 이미지는 DB에 없는 새로운 이미지여도 됩니다.
query_image_path = "./embedding_test_Img/embedding_test_img.png"
top_k = 3 # 유사도 높은 상위 3개만 표시하도록 설정

try:
    print(f"\n--- 검색 시작: {query_image_path} ---")
    query_image = Image.open(query_image_path)
    query_image_rgb = convert_png_to_rgb_with_white_bg(query_image)

    # 쿼리 이미지 벡터화
    inputs = clip_processor(images=query_image_rgb, return_tensors="pt").to(device)
    with torch.no_grad():
        query_embedding = clip_model.get_image_features(**inputs).cpu().numpy().tolist()[0]

    # Supabase의 'search_similar_bags' 함수 호출
    response = client.rpc('search_similar_bags', {
        'query_embedding': query_embedding,
        'match_threshold': 0.7, 
        'match_count': top_k # top_k 개수만큼만 요청
    }).execute()
    
    results_data = response.data
    
    # --- 3. 결과 시각화 함수 호출 ---
    display_results(query_image_rgb, results_data, top_k)

except FileNotFoundError:
    print(f"🚨 오류: 쿼리 이미지를 찾을 수 없습니다: '{query_image_path}'")
except Exception as e:
    print(f"🚨 검색 중 오류 발생: {e}")