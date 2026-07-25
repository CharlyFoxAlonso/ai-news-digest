from ai_news.sources.base import FeedSource

# Verified on 2026-07-25 with HTTP 200, parseable XML, absolute links and dated entries.
FEED_SOURCES: tuple[FeedSource, ...] = (
    FeedSource("OpenAI", "https://openai.com/news/rss.xml", 100),
    FeedSource("Google AI", "https://blog.google/innovation-and-ai/technology/ai/rss/", 98),
    FeedSource("Hugging Face", "https://huggingface.co/blog/feed.xml", 92),
    FeedSource("NVIDIA", "https://blogs.nvidia.com/feed/", 96),
    FeedSource("NVIDIA Developer", "https://developer.nvidia.com/blog/feed/", 94),
    FeedSource("AMD", "https://ir.amd.com/news-events/press-releases/rss", 90),
    FeedSource("Intel", "https://newsroom.intel.com/feed", 90),
    FeedSource("Apple Machine Learning", "https://machinelearning.apple.com/rss.xml", 94),
    FeedSource("The Decoder", "https://the-decoder.com/feed/", 75, is_official=False),
)
