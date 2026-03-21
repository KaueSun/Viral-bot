class PublishService:
    def publish(self, clip_path: str, title: str, caption: str, mode: str = "draft") -> dict:
        """
        Placeholder para integração real com a API de publicação.
        mode='draft' simula envio como rascunho.
        mode='publish' simula publicação direta.
        """
        return {
            "ok": True,
            "mode": mode,
            "clip_path": clip_path,
            "title": title,
            "caption": caption,
            "message": "Integração simulada com sucesso. Substitua este método pela API real.",
        }