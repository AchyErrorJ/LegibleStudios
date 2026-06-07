# vector_store.py - CORRECTED VERSION

# -*- coding: utf-8 -*-
import os
import logging
from typing import List, Dict

# Heavy, external imports are moved inside __init__ to prevent import crashes.

logger = logging.getLogger(__name__)

class FamilyKnowledgeBase:
    def __init__(self, db_path="qdrant_data", collection_name="revit_families"):
        """
        Initializes the Vector Database (Local Mode).
        """
        # --- DEFERRED IMPORTS (ACTION A) ---
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            # Only print error here, don't raise it to prevent server crash
            print(f"❌ FamilyKnowledgeBase dependency failure: {e}")
            raise RuntimeError("Missing Qdrant/SentenceTransformer dependencies.")

        self.collection_name = collection_name
        
        # 1. Initialize Qdrant (Local file storage)
        self.client = QdrantClient(path=db_path)
        
        # 2. Initialize Embedding Model
        print("⏳ Loading Embedding Model (this may take a moment)...")
        # NOTE: If this fails, the server will crash the worker process.
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Embedding Model Loaded.")

        # 3. Ensure Collection Exists
        self._ensure_collection()

    # ... (rest of the methods: _ensure_collection, add_families, search) ...

# NOTE: The rest of the methods remain unchanged (omitted for brevity)
    def _ensure_collection(self):
        collections = self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)
        
        if not exists:
            print(f"Creating new vector collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )

    def add_families(self, families: List[Dict]):
        """
        Embeds and stores a list of family dictionaries.
        """
        # ... (implementation omitted) ...
        points = []
        print(f"Encoding {len(families)} items...")
        
        # Generate text to embed
        texts = [f"{f.get('category', 'Generic')}: {f['name']}" for f in families]
        
        # Generate Vectors
        embeddings = self.model.encode(texts)

        # Create Qdrant Points
        for i, family in enumerate(families):
            point_id = i 
            
            points.append(PointStruct(
                id=point_id,
                vector=embeddings[i].tolist(),
                payload=family
            ))

        # Upload
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        print(f"✅ Automatically indexed {len(points)} families.")

    def search(self, query: str, limit: int = 5, category_filter: str = None) -> List[Dict]:
        """
        Semantically searches for families.
        """
        # 1. Convert query to vector
        query_vector = self.model.encode(query).tolist()
        
        # 2. Define Filter (Optional)
        query_filter = None
        if category_filter:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=category_filter)
                    )
                ]
            )

        # 3. Search (Using query_points instead of search for robustness)
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit
        )
        
        hits = response.points

        # 4. Format Results
        results = []
        for hit in hits:
            results.append({
                "name": hit.payload['name'],
                "path": hit.payload['path'],
                "category": hit.payload['category'],
                "score": hit.score
            })
            
        return results