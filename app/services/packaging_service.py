class PackagingService:
    def make_title(self, creator_name: str, hook_text: str) -> str:
        base = hook_text.strip().capitalize()
        if len(base) > 70:
            base = base[:67] + "..."
        return f"{creator_name}: {base}"

    def make_compilation_title(
        self,
        creator_name: str,
        source_title: str,
        cut_style: str,
        clip_count: int,
    ) -> str:
        style_labels = {
            "viral": "melhores momentos virais",
            "engracado": "melhores momentos engracados",
            "chocante": "momentos mais chocantes",
            "informativo": "melhores momentos informativos",
        }
        style_text = style_labels.get(cut_style, "melhores momentos")
        base_title = source_title.strip() if source_title else creator_name
        title = f"{style_text} de {base_title} ({clip_count} momentos)"
        if len(title) > 90:
            title = title[:87] + "..."
        return title

    def make_hashtags(self, creator_name: str) -> list[str]:
        safe_name = creator_name.lower().replace(" ", "")
        return [
            f"#{safe_name}",
            "#cortes",
            "#viral",
            "#foryou",
            "#tiktokbr",
        ]

    def make_caption(self, title: str, hashtags: list[str]) -> str:
        return f"{title}\n\n" + " ".join(hashtags)
