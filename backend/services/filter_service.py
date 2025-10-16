from typing import List, Dict, Any, Tuple
from services.query_builder import FilterQueryBuilder
from services.supabase_client import supabase_client
import logging

logger = logging.getLogger(__name__)


class FilterService:
    """필터 검색 비즈니스 로직을 처리하는 서비스 클래스"""
    
    def __init__(self):
        self.query_builder = FilterQueryBuilder(supabase_client)
    
    async def search_bags(self, categories: List[str], colors: List[str], 
                         min_price: float, max_price: float, 
                         page: int, limit: int) -> Tuple[List[Dict[str, Any]], int]:
        """
        필터 조건에 따라 가방을 검색합니다.
        
        Returns:
            Tuple[검색 결과 리스트, 총 아이템 수]
        """
        try:
            # 1. 기본 쿼리 생성
            base_query = self.query_builder.build_base_query()
            
            # 2. 필터 적용된 쿼리 생성
            filtered_query = self.query_builder.apply_filters(
                base_query, categories, colors, min_price, max_price, page, limit
            )
            
            # 3. 검색 실행
            response = filtered_query.execute()
            
            # 4. 총 개수 조회 (필터 적용된 상태에서)
            count_query = self.query_builder.build_count_query()
            count_query = self.query_builder.build_category_filter(count_query, categories)
            count_query = self.query_builder.build_color_filter(count_query, colors)
            count_query = self.query_builder.build_price_filter(count_query, min_price, max_price)
            
            count_response = count_query.execute()
            total_count = count_response.count if count_response.count else 0
            
            # 5. 결과 데이터 가공
            processed_results = self._process_results(response.data)
            
            return processed_results, total_count
            
        except Exception as e:
            logger.exception("Filter search error")
            raise e
    
    def _process_results(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """DB 결과를 프론트엔드에서 사용할 형태로 가공"""
        processed_results = []
        
        for item in raw_data:
            # color 문자열을 파싱하여 배열로 변환
            color_list = self._parse_colors(item.get('color', ''))
            
            processed_item = {
                'bag_id': item.get('bag_id', ''),
                'bag_name': item.get('bag_name', 'Unknown'),
                'brand': item.get('brand', 'Unknown'),
                'price': item.get('price', 0),
                'material': item.get('material', ''),
                'color': str(color_list),  # JSON 문자열로 변환
                'category': item.get('category', ''),
                'link': item.get('link', ''),
                'thumbnail': item.get('thumbnail', ''),
                'detail': item.get('detail', ''),
                'similarity': 0.85  # similarity 컬럼이 없으므로 고정값
            }
            processed_results.append(processed_item)
        
        return processed_results
    
    def _parse_colors(self, color_string: str) -> List[str]:
        """color 문자열을 파싱하여 색상 리스트로 변환"""
        if not color_string:
            return []
        
        try:
            # ['네이비', '화이트'] 형태의 문자열을 파싱
            import ast
            if color_string.startswith('[') and color_string.endswith(']'):
                return ast.literal_eval(color_string)
            else:
                # 단순 문자열인 경우 쉼표로 분리
                return [color.strip() for color in color_string.split(',')]
        except:
            # 파싱 실패 시 빈 리스트 반환
            return []
    
    def calculate_total_pages(self, total_count: int, limit: int) -> int:
        """총 페이지 수 계산"""
        return (total_count + limit - 1) // limit
