import json
import numpy as np
from typing import List, Dict, Any, Tuple
from services.supabase_client import supabase_client
from services.clip_service import get_image_embedding
from services.session_cache import SessionCache
from PIL import Image
import os
import logging

logger = logging.getLogger(__name__)


class SimilarityFilterService:
    """유사도 기반 필터 검색 비즈니스 로직을 처리하는 서비스 클래스"""
    
    def __init__(self, session_cache: SessionCache):
        self.supabase_client = supabase_client
        self.session_cache = session_cache
    
    async def search_bags_with_similarity(self, session_id: str, categories: List[str], 
                                        colors: List[str], min_price: float, max_price: float, 
                                        page: int, limit: int) -> Tuple[List[Dict[str, Any]], int]:
        """
        세션의 크롭된 이미지와 유사도를 계산하여 필터 검색합니다.
        
        Args:
            session_id: 사용자 세션 ID
            categories: 선택된 카테고리 리스트
            colors: 선택된 색상 리스트
            min_price: 최소 가격
            max_price: 최대 가격
            page: 페이지 번호
            limit: 페이지당 아이템 수
            
        Returns:
            Tuple[검색 결과 리스트, 총 아이템 수]
        """
        try:
            # 1. 세션에서 크롭된 이미지 로드 및 임베딩 생성
            query_embedding = await self._get_session_embedding(session_id)
            
            # 2. 필터 조건으로 bags 테이블에서 데이터 조회
            bags_data = await self._get_filtered_bags(categories, colors, min_price, max_price)
            
            if not bags_data:
                return [], 0
            
            # 3. 각 bag_id에 대해 유사도 계산
            bags_with_similarity = await self._calculate_similarities(bags_data, query_embedding)
            
            # 4. 유사도 내림차순 정렬
            bags_with_similarity.sort(key=lambda x: x['similarity'], reverse=True)
            
            # 5. 페이지네이션 적용
            total_count = len(bags_with_similarity)
            start_index = (page - 1) * limit
            end_index = start_index + limit
            paginated_results = bags_with_similarity[start_index:end_index]
            
            return paginated_results, total_count
            
        except Exception as e:
            logger.exception("Similarity filter search error")
            raise e
    
    async def _get_session_embedding(self, session_id: str) -> List[float]:
        """세션에서 크롭된 이미지를 로드하고 임베딩을 생성합니다."""
        if self.session_cache is None:
            raise Exception("Session cache not initialized")
        
        sess = self.session_cache.get_session(session_id)
        if not sess:
            raise Exception("Session not found")
        
        # 세션에서 마스크 이미지 로드
        image_path = sess.get("image_path")
        if not image_path or not os.path.exists(image_path):
            raise Exception("Image not found")
        
        # 마스크 파일 경로 (세션에 저장된 최신 마스크 사용)
        mask_path = sess.get("last_mask_path")
        if not mask_path or not os.path.exists(mask_path):
            raise Exception("No mask found. Please segment the image first.")
        
        # 원본 이미지 + 마스크 로드
        original_img = Image.open(image_path).convert("RGB")
        mask_img = Image.open(mask_path).convert("L")  # grayscale
        
        # 마스크 영역 바운딩박스 추출 및 크롭
        mask_np = np.array(mask_img)
        coords = np.column_stack(np.where(mask_np > 0))  # (y, x) 좌표
        
        if len(coords) == 0:
            raise Exception("Mask is empty")
        
        y_min, x_min = coords.min(axis=0)
        y_max, x_max = coords.max(axis=0)
        
        # 크롭 (바운딩박스)
        cropped = original_img.crop((x_min, y_min, x_max + 1, y_max + 1))
        
        # 크롭된 마스크
        cropped_mask = mask_img.crop((x_min, y_min, x_max + 1, y_max + 1))
        cropped_mask_np = np.array(cropped_mask)
        
        # 마스크 외부를 흰색으로 채우기
        cropped_np = np.array(cropped)
        white_bg = np.ones_like(cropped_np) * 255
        mask_3ch = np.stack([cropped_mask_np] * 3, axis=-1) > 0
        final_np = np.where(mask_3ch, cropped_np, white_bg).astype(np.uint8)
        final_img = Image.fromarray(final_np)
        
        # CLIP 임베딩 생성
        query_embedding = get_image_embedding(final_img)
        return query_embedding
    
    async def _get_filtered_bags(self, categories: List[str], colors: List[str], 
                               min_price: float, max_price: float) -> List[Dict[str, Any]]:
        """필터 조건에 맞는 bags 데이터를 조회합니다."""
        query = self.supabase_client.table("bags").select("*")
        
        # 카테고리 필터링 (정확한 매칭)
        if categories:
            query = query.in_("category", categories)
        
        # 색상 필터링 (부분 매칭)
        if colors:
            color_conditions = []
            for color in colors:
                color_conditions.append(f"color.ilike.%{color}%")
            
            if color_conditions:
                query = query.or_(",".join(color_conditions))
        
        # 가격 범위 필터링
        if min_price > 0:
            query = query.gte("price", min_price)
        if max_price < 500000:
            query = query.lte("price", max_price)
        
        # 최대 50개로 제한
        query = query.limit(50)
        
        response = query.execute()
        return response.data if response.data else []
    
    async def _calculate_similarities(self, bags_data: List[Dict[str, Any]], 
                                    query_embedding: List[float]) -> List[Dict[str, Any]]:
        """각 가방에 대해 유사도를 계산합니다."""
        bags_with_similarity = []
        
        for bag in bags_data:
            bag_id = bag.get('bag_id')
            if not bag_id:
                continue
            
            try:
                # image_embeddings 테이블에서 해당 bag_id의 임베딩 조회
                embed_response = self.supabase_client.table("image_embeddings") \
                    .select("embed") \
                    .eq("bag_id", bag_id) \
                    .execute()
                
                if not embed_response.data:
                    # 임베딩이 없으면 기본 유사도 0
                    similarity = 0.0
                else:
                    embed_data = embed_response.data[0]
                    embed = embed_data.get('embed')
                    
                    # embed가 문자열이면 JSON 파싱
                    if isinstance(embed, str):
                        embed = json.loads(embed)
                    
                    # 코사인 유사도 계산
                    query_vec = np.array(query_embedding, dtype=np.float32)
                    db_vec = np.array(embed, dtype=np.float32)
                    similarity = np.dot(query_vec, db_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(db_vec))
                    similarity = float(similarity)
                
                # 결과에 유사도 추가
                bag_with_similarity = bag.copy()
                bag_with_similarity['similarity'] = similarity
                bags_with_similarity.append(bag_with_similarity)
                
            except Exception as e:
                logger.warning(f"Error calculating similarity for bag_id {bag_id}: {e}")
                # 에러 발생 시 기본 유사도 0
                bag_with_similarity = bag.copy()
                bag_with_similarity['similarity'] = 0.0
                bags_with_similarity.append(bag_with_similarity)
        
        return bags_with_similarity
    
    def calculate_total_pages(self, total_count: int, limit: int) -> int:
        """총 페이지 수 계산"""
        return (total_count + limit - 1) // limit
