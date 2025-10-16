from typing import List, Optional
from supabase import Client


class FilterQueryBuilder:
    """필터 조건을 Supabase 쿼리로 변환하는 빌더 클래스"""
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    def build_base_query(self):
        """기본 쿼리 생성"""
        return self.client.table("bags").select("*")
    
    def build_category_filter(self, query, categories: List[str]):
        """카테고리 필터링 (정확한 매칭)"""
        if categories:
            query = query.in_("category", categories)
        return query
    
    def build_color_filter(self, query, colors: List[str]):
        """색상 필터링 (부분 매칭)"""
        if colors:
            color_conditions = []
            for color in colors:
                # color 컬럼에서 해당 색상이 포함된 행 찾기
                color_conditions.append(f"color.ilike.%{color}%")
            
            if color_conditions:
                query = query.or_(",".join(color_conditions))
        return query
    
    def build_price_filter(self, query, min_price: float, max_price: float):
        """가격 범위 필터링"""
        if min_price > 4900:
            query = query.gte("price", min_price)
        if max_price < 1500000:
            query = query.lte("price", max_price)
        return query
    
    def build_pagination(self, query, page: int, limit: int):
        """페이지네이션 적용 (최대 50개로 제한)"""
        # 최대 50개로 제한
        max_limit = min(limit, 50)
        offset = (page - 1) * max_limit
        query = query.range(offset, offset + max_limit - 1)
        return query
    
    def build_sorting(self, query, sort_by: str = "bag_id"):
        """정렬 적용 (similarity 컬럼이 없으므로 bag_id로 정렬)"""
        query = query.order(sort_by, desc=False)
        return query
    
    def build_count_query(self):
        """총 개수 조회용 쿼리"""
        return self.client.table("bags").select("bag_id", count="exact")
    
    def apply_filters(self, query, categories: List[str], colors: List[str], 
                     min_price: float, max_price: float, page: int, limit: int):
        """모든 필터를 적용한 최종 쿼리 생성"""
        query = self.build_category_filter(query, categories)
        query = self.build_color_filter(query, colors)
        query = self.build_price_filter(query, min_price, max_price)
        query = self.build_sorting(query)
        query = self.build_pagination(query, page, limit)
        return query
