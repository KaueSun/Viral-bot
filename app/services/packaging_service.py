class PackagingService:
    def make_title(self, creator_name: str, hook_text: str) -> str:
        base = hook_text.strip().capitalize()
        if len(base) > 70:
            base = base[:67] + "..."
        return f"{creator_name}: {base}"

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