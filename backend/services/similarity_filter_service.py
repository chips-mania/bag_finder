import json
import logging
from typing import Any, Dict, List, Tuple

import numpy as np

from services.session_cache import SessionCache
from services.supabase_client import supabase_client

logger = logging.getLogger(__name__)


class SimilarityFilterService:
    """유사도 기반 필터 검색. CLIP 벡터는 /search에서 세션에 저장한 값을 재사용합니다."""

    def __init__(self, session_cache: SessionCache):
        self.supabase_client = supabase_client
        self.session_cache = session_cache

    async def search_bags_with_similarity(
        self,
        session_id: str,
        categories: List[str],
        colors: List[str],
        min_price: float,
        max_price: float,
        page: int,
        limit: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        try:
            query_embedding = self._get_cached_embedding(session_id)
            bags_data = await self._get_filtered_bags(categories, colors, min_price, max_price)
            if not bags_data:
                return [], 0

            bags_with_similarity = self._calculate_similarities(bags_data, query_embedding)
            bags_with_similarity.sort(key=lambda x: x["similarity"], reverse=True)

            total_count = len(bags_with_similarity)
            start_index = (page - 1) * limit
            end_index = start_index + limit
            return bags_with_similarity[start_index:end_index], total_count
        except Exception:
            logger.exception("Similarity filter search error")
            raise

    def _get_cached_embedding(self, session_id: str) -> List[float]:
        sess = self.session_cache.get_session(session_id)
        if not sess:
            raise Exception("Session not found")
        embedding = sess.get("clip_embedding")
        if not embedding:
            raise Exception("No CLIP embedding. Run search before filter search.")
        return embedding

    async def _get_filtered_bags(
        self,
        categories: List[str],
        colors: List[str],
        min_price: float,
        max_price: float,
    ) -> List[Dict[str, Any]]:
        query = self.supabase_client.table("bags").select("*")

        if categories:
            query = query.in_("category", categories)

        if colors:
            color_conditions = [f"color.ilike.%{color}%" for color in colors]
            if color_conditions:
                query = query.or_(",".join(color_conditions))

        if min_price > 0:
            query = query.gte("price", min_price)
        if max_price < 500000:
            query = query.lte("price", max_price)

        query = query.limit(50)
        response = query.execute()
        return response.data if response.data else []

    def _calculate_similarities(
        self,
        bags_data: List[Dict[str, Any]],
        query_embedding: List[float],
    ) -> List[Dict[str, Any]]:
        bag_ids = [bag["bag_id"] for bag in bags_data if bag.get("bag_id")]
        embed_map: Dict[str, np.ndarray] = {}
        if bag_ids:
            embed_response = (
                self.supabase_client.table("image_embeddings")
                .select("bag_id, embed")
                .in_("bag_id", bag_ids)
                .execute()
            )
            for row in embed_response.data or []:
                embed = row.get("embed")
                if isinstance(embed, str):
                    embed = json.loads(embed)
                if embed is None:
                    continue
                embed_map[row["bag_id"]] = np.asarray(embed, dtype=np.float32)

        query_vec = np.asarray(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            query_norm = 1.0
        query_vec = query_vec / query_norm

        results: List[Dict[str, Any]] = []
        for bag in bags_data:
            bag_id = bag.get("bag_id")
            db_vec = embed_map.get(bag_id) if bag_id else None
            similarity = 0.0
            if db_vec is not None:
                db_norm = np.linalg.norm(db_vec)
                if db_norm > 0:
                    similarity = float(np.dot(query_vec, db_vec / db_norm))
            item = bag.copy()
            item["similarity"] = similarity
            results.append(item)
        return results

    def calculate_total_pages(self, total_count: int, limit: int) -> int:
        return (total_count + limit - 1) // limit if limit else 0
