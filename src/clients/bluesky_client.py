# src/clients/bluesky_client.py
from atproto import Client, models
from src.core.config import settings

class BlueskyClient:
    def __init__(self):
        self.client = Client()
        self._profile = None

    def login(self):
        """Realiza o login na API do Bluesky usando as credenciais das configurações."""
        if self._profile:
            return self._profile
        try:
            self._profile = self.client.login(
                settings.BSKY_HANDLE, settings.BSKY_APP_PASSWORD
            )
            print(f"Login bem-sucedido como: {self._profile.display_name}")
            return self._profile
        except Exception as e:
            print(f"Erro no login: {e}")
            raise

    def fetch_posts_from_feed(self, feed_uri: str, limit: int = 10) -> list[models.AppBskyFeedDefs.FeedViewPost]:
        """Busca posts de um feed específico (pode ser instável se o feed mudar)."""
        if not self._profile:
            self.login()
        
        try:
            response = self.client.app.bsky.feed.get_feed(
                params=models.AppBskyFeedGetFeed.Params(feed=feed_uri, limit=limit)
            )
            return response.feed
        except Exception as e:
            print(f"Erro ao buscar o feed: {e}")
            return []

    def search_posts(self, query: str, limit: int = 50) -> list[models.AppBskyFeedDefs.PostView]:
        """
        Busca posts que contenham um termo de busca (query),
        lidando com paginação para buscar mais de 100 posts.
        """
        if not self._profile:
            self.login()
        
        all_posts = []
        cursor = None
        
        # O limite da API é 100 por chamada. Vamos fazer chamadas em loop.
        api_limit_per_call = 100

        try:
            while len(all_posts) < limit:
                remaining_needed = limit - len(all_posts)
                current_limit = min(remaining_needed, api_limit_per_call)

                if current_limit <= 0:
                    break

                response = self.client.app.bsky.feed.search_posts(
                    params=models.AppBskyFeedSearchPosts.Params(
                        q=query, 
                        limit=current_limit, 
                        cursor=cursor
                    )
                )
                
                if not response.posts:
                    # Não há mais posts para buscar
                    break
                
                all_posts.extend(response.posts)
                cursor = response.cursor

                if not cursor:
                    # Chegamos ao fim dos resultados
                    break
            
            # Retorna a quantidade exata de posts solicitada no limite
            return all_posts[:limit]

        except Exception as e:
            print(f"Erro ao buscar posts com o termo '{query}': {e}")
            return []