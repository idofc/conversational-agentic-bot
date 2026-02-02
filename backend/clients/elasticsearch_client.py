"""
Elasticsearch client for full-text search and analytics.
Optimized for conversation and message search at scale.
"""

import os
from typing import Optional, List, Dict, Any
from elasticsearch import Elasticsearch, helpers
from datetime import datetime

class ElasticsearchClient:
    """Elasticsearch client for indexing and searching conversations/messages."""
    
    def __init__(self):
        self.host = os.getenv("ELASTICSEARCH_HOST", "localhost")
        self.port = int(os.getenv("ELASTICSEARCH_PORT", "9200"))
        self.index_prefix = os.getenv("ELASTICSEARCH_INDEX_PREFIX", "conversational_bot")
        
        # Initialize client
        self.client = Elasticsearch(
            [f"http://{self.host}:{self.port}"],
            request_timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        
        # Index names
        self.messages_index = f"{self.index_prefix}_messages"
        self.conversations_index = f"{self.index_prefix}_conversations"
        
        # Initialize indexes
        self._create_indexes()
    
    def _create_indexes(self):
        """Create Elasticsearch indexes with optimized mappings."""
        
        # Messages index mapping
        messages_mapping = {
            "mappings": {
                "properties": {
                    "conversation_id": {"type": "integer"},
                    "use_case_id": {"type": "integer"},
                    "role": {"type": "keyword"},
                    "content": {
                        "type": "text",
                        "analyzer": "standard",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256}
                        }
                    },
                    "created_at": {"type": "date"},
                    "metadata": {"type": "object", "enabled": False}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "5s"
            }
        }
        
        # Conversations index mapping
        conversations_mapping = {
            "mappings": {
                "properties": {
                    "conversation_id": {"type": "integer"},
                    "use_case_id": {"type": "integer"},
                    "title": {
                        "type": "text",
                        "analyzer": "standard",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256},
                            "suggest": {
                                "type": "completion",
                                "analyzer": "simple"
                            }
                        }
                    },
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    "message_count": {"type": "integer"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            }
        }
        
        try:
            # Create messages index
            if not self.client.indices.exists(index=self.messages_index):
                self.client.indices.create(index=self.messages_index, body=messages_mapping)
                print(f"Created index: {self.messages_index}")
            
            # Create conversations index
            if not self.client.indices.exists(index=self.conversations_index):
                self.client.indices.create(index=self.conversations_index, body=conversations_mapping)
                print(f"Created index: {self.conversations_index}")
        
        except Exception as e:
            print(f"Error creating Elasticsearch indexes: {e}")
    
    def ping(self) -> bool:
        """Test Elasticsearch connection."""
        try:
            return self.client.ping()
        except Exception as e:
            print(f"Elasticsearch connection error: {e}")
            return False
    
    # ============================================
    # Message Indexing
    # ============================================
    
    def index_message(
        self,
        message_id: int,
        conversation_id: int,
        use_case_id: int,
        role: str,
        content: str,
        created_at: datetime,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Index a single message."""
        try:
            doc = {
                "conversation_id": conversation_id,
                "use_case_id": use_case_id,
                "role": role,
                "content": content,
                "created_at": created_at.isoformat(),
                "metadata": metadata or {}
            }
            
            self.client.index(
                index=self.messages_index,
                id=message_id,
                document=doc
            )
            return True
        
        except Exception as e:
            print(f"Error indexing message {message_id}: {e}")
            return False
    
    def bulk_index_messages(self, messages: List[Dict]) -> tuple[int, int]:
        """
        Bulk index multiple messages.
        Returns: (success_count, error_count)
        """
        if not messages:
            return 0, 0
        
        try:
            actions = []
            for msg in messages:
                action = {
                    "_index": self.messages_index,
                    "_id": msg["id"],
                    "_source": {
                        "conversation_id": msg["conversation_id"],
                        "use_case_id": msg["use_case_id"],
                        "role": msg["role"],
                        "content": msg["content"],
                        "created_at": msg["created_at"].isoformat() if isinstance(msg["created_at"], datetime) else msg["created_at"],
                        "metadata": msg.get("metadata", {})
                    }
                }
                actions.append(action)
            
            success, errors = helpers.bulk(self.client, actions, raise_on_error=False)
            return success, len(errors)
        
        except Exception as e:
            print(f"Error bulk indexing messages: {e}")
            return 0, len(messages)
    
    def delete_message(self, message_id: int) -> bool:
        """Delete a message from the index."""
        try:
            self.client.delete(index=self.messages_index, id=message_id)
            return True
        except Exception as e:
            print(f"Error deleting message {message_id}: {e}")
            return False
    
    # ============================================
    # Conversation Indexing
    # ============================================
    
    def index_conversation(
        self,
        conversation_id: int,
        use_case_id: int,
        title: str,
        created_at: datetime,
        updated_at: datetime,
        message_count: int
    ) -> bool:
        """Index or update a conversation."""
        try:
            doc = {
                "conversation_id": conversation_id,
                "use_case_id": use_case_id,
                "title": title,
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat(),
                "message_count": message_count
            }
            
            self.client.index(
                index=self.conversations_index,
                id=conversation_id,
                document=doc
            )
            return True
        
        except Exception as e:
            print(f"Error indexing conversation {conversation_id}: {e}")
            return False
    
    def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation and all its messages from the index."""
        try:
            # Delete conversation
            self.client.delete(index=self.conversations_index, id=conversation_id, ignore=[404])
            
            # Delete all messages in conversation
            query = {"query": {"term": {"conversation_id": conversation_id}}}
            self.client.delete_by_query(index=self.messages_index, body=query)
            
            return True
        except Exception as e:
            print(f"Error deleting conversation {conversation_id}: {e}")
            return False
    
    # ============================================
    # Search Operations
    # ============================================
    
    def search_messages(
        self,
        query: str,
        use_case_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        role: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        size: int = 20,
        from_: int = 0
    ) -> Dict[str, Any]:
        """
        Search messages with multiple filters.
        Returns: {total: int, hits: List[Dict]}
        """
        try:
            # Build query
            must_clauses = []
            filter_clauses = []
            
            # Full-text search on content
            if query:
                must_clauses.append({
                    "multi_match": {
                        "query": query,
                        "fields": ["content^2"],  # Boost content field
                        "fuzziness": "AUTO",
                        "operator": "or"
                    }
                })
            
            # Filters
            if use_case_id:
                filter_clauses.append({"term": {"use_case_id": use_case_id}})
            
            if conversation_id:
                filter_clauses.append({"term": {"conversation_id": conversation_id}})
            
            if role:
                filter_clauses.append({"term": {"role": role}})
            
            # Date range filter
            if from_date or to_date:
                date_range = {}
                if from_date:
                    date_range["gte"] = from_date
                if to_date:
                    date_range["lte"] = to_date
                filter_clauses.append({"range": {"created_at": date_range}})
            
            # Construct final query
            search_body = {
                "query": {
                    "bool": {
                        "must": must_clauses if must_clauses else [{"match_all": {}}],
                        "filter": filter_clauses
                    }
                },
                "sort": [{"created_at": {"order": "desc"}}],
                "size": size,
                "from": from_,
                "highlight": {
                    "fields": {
                        "content": {
                            "pre_tags": ["<mark>"],
                            "post_tags": ["</mark>"],
                            "fragment_size": 150,
                            "number_of_fragments": 3
                        }
                    }
                }
            }
            
            # Execute search
            response = self.client.search(index=self.messages_index, body=search_body)
            
            # Format results
            hits = []
            for hit in response["hits"]["hits"]:
                result = {
                    "id": hit["_id"],
                    "score": hit["_score"],
                    **hit["_source"]
                }
                
                # Add highlights if available
                if "highlight" in hit:
                    result["highlight"] = hit["highlight"]
                
                hits.append(result)
            
            return {
                "total": response["hits"]["total"]["value"],
                "hits": hits
            }
        
        except Exception as e:
            print(f"Error searching messages: {e}")
            return {"total": 0, "hits": []}
    
    def search_conversations(
        self,
        query: str,
        use_case_id: Optional[int] = None,
        size: int = 20
    ) -> Dict[str, Any]:
        """
        Search conversations by title.
        Returns: {total: int, hits: List[Dict]}
        """
        try:
            must_clauses = [
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^3"],
                        "fuzziness": "AUTO"
                    }
                }
            ]
            
            filter_clauses = []
            if use_case_id:
                filter_clauses.append({"term": {"use_case_id": use_case_id}})
            
            search_body = {
                "query": {
                    "bool": {
                        "must": must_clauses,
                        "filter": filter_clauses
                    }
                },
                "sort": [{"updated_at": {"order": "desc"}}],
                "size": size
            }
            
            response = self.client.search(index=self.conversations_index, body=search_body)
            
            hits = [
                {"id": hit["_id"], "score": hit["_score"], **hit["_source"]}
                for hit in response["hits"]["hits"]
            ]
            
            return {
                "total": response["hits"]["total"]["value"],
                "hits": hits
            }
        
        except Exception as e:
            print(f"Error searching conversations: {e}")
            return {"total": 0, "hits": []}
    
    def suggest_conversations(self, prefix: str, use_case_id: Optional[int] = None, size: int = 5) -> List[str]:
        """Get conversation title suggestions for autocomplete."""
        try:
            search_body = {
                "suggest": {
                    "conversation-suggest": {
                        "prefix": prefix,
                        "completion": {
                            "field": "title.suggest",
                            "size": size,
                            "skip_duplicates": True
                        }
                    }
                }
            }
            
            response = self.client.search(index=self.conversations_index, body=search_body)
            suggestions = response["suggest"]["conversation-suggest"][0]["options"]
            
            return [option["text"] for option in suggestions]
        
        except Exception as e:
            print(f"Error getting suggestions: {e}")
            return []
    
    # ============================================
    # Analytics
    # ============================================
    
    def get_message_stats(self, use_case_id: Optional[int] = None) -> Dict[str, Any]:
        """Get message statistics."""
        try:
            filter_clause = []
            if use_case_id:
                filter_clause.append({"term": {"use_case_id": use_case_id}})
            
            search_body = {
                "query": {
                    "bool": {
                        "filter": filter_clause
                    }
                } if filter_clause else {"match_all": {}},
                "size": 0,
                "aggs": {
                    "messages_per_day": {
                        "date_histogram": {
                            "field": "created_at",
                            "calendar_interval": "day"
                        }
                    },
                    "messages_by_role": {
                        "terms": {"field": "role"}
                    },
                    "total_conversations": {
                        "cardinality": {"field": "conversation_id"}
                    }
                }
            }
            
            response = self.client.search(index=self.messages_index, body=search_body)
            
            return {
                "total_messages": response["hits"]["total"]["value"],
                "messages_per_day": response["aggregations"]["messages_per_day"]["buckets"],
                "messages_by_role": response["aggregations"]["messages_by_role"]["buckets"],
                "total_conversations": response["aggregations"]["total_conversations"]["value"]
            }
        
        except Exception as e:
            print(f"Error getting message stats: {e}")
            return {}
    
    # ============================================
    # Maintenance
    # ============================================
    
    def refresh_indexes(self):
        """Force refresh of all indexes."""
        try:
            self.client.indices.refresh(index=f"{self.index_prefix}_*")
        except Exception as e:
            print(f"Error refreshing indexes: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Elasticsearch cluster and index statistics."""
        try:
            cluster_health = self.client.cluster.health()
            messages_stats = self.client.indices.stats(index=self.messages_index)
            conversations_stats = self.client.indices.stats(index=self.conversations_index)
            
            return {
                "connected": True,
                "cluster_status": cluster_health["status"],
                "messages_count": messages_stats["_all"]["primaries"]["docs"]["count"],
                "messages_size": messages_stats["_all"]["primaries"]["store"]["size_in_bytes"],
                "conversations_count": conversations_stats["_all"]["primaries"]["docs"]["count"],
                "conversations_size": conversations_stats["_all"]["primaries"]["store"]["size_in_bytes"]
            }
        except Exception as e:
            print(f"Error getting Elasticsearch stats: {e}")
            return {"connected": False, "error": str(e)}
    
    def close(self):
        """Close Elasticsearch connection."""
        try:
            self.client.close()
        except Exception as e:
            print(f"Error closing Elasticsearch connection: {e}")


# Global Elasticsearch client instance
es_client = ElasticsearchClient()
