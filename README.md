# Dahab Reddit Scraper (MCP)

An async Python tool that collects text from a subreddit — hot posts, their bodies, and full comment threads — and writes it to a clean CSV. Built on the **Model Context Protocol (MCP)**: instead of calling the Reddit API directly, it drives the [`mcp-server-reddit`](https://pypi.org/project/mcp-server-reddit/) MCP server as a tool provider.

Originally built to gather **r/Dahab** discussion text as a training/retrieval corpus for a chatbot about Dahab, Egypt — this repo is the **data-collection stage** of that project.

## What it does

- Launches `mcp-server-reddit` over stdio (via `uvx`) and opens an MCP `ClientSession`.
- Calls three MCP tools in sequence:
  - `get_subreddit_hot_posts` → discover post IDs
  - `get_post_content` → post title + self-text
  - `get_post_comments` → full comment tree
- Recursively flattens nested comment threads into individual text entries.
- Filters `[deleted]` / `[removed]` / empty values, de-duplicates post IDs, and rate-limits every 10 posts.
- Saves one `reddit_text` column to `<subreddit>_reddit_data.csv`.

## Why MCP

Rather than hand-rolling Reddit auth and pagination, this reuses an existing MCP server as a composable tool layer — the same pattern used to give LLM agents tools. It's a compact demonstration of **writing an MCP client** and orchestrating remote tool calls.

## Stack

Python · `asyncio` · MCP (`mcp`) · `mcp-server-reddit` · `pandas` · `httpx`

## Usage

```bash
pip install -r requirements.txt          # needs `uvx` (from uv) available on PATH

python mcp-reddit-dahab-server/reddit_mcp_scraper.py <subreddit_url> [post_limit]

# example
python mcp-reddit-dahab-server/reddit_mcp_scraper.py https://www.reddit.com/r/dahab/ 500
```

Output → `dahab_reddit_data.csv`, one text entry per row:

| reddit_text |
|-------------|
| Best dive sites in Dahab? |
| The Blue Hole is a must, but go with a guide… |
| … |

## Notes

- Read-only scraping of **public** posts. Respect Reddit's terms of use and rate limits.
- `post_limit` caps posts fetched (hot-posts discovery is capped at 100 per MCP call).
- The produced CSV is the corpus later used for retrieval / fine-tuning downstream.
