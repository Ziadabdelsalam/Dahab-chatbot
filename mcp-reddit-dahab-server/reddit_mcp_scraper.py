import asyncio
import json
import sys
import re
import pandas as pd
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from urllib.parse import urlparse

def extract_subreddit_name(url):
    """Extract subreddit name from URL"""
    if url.startswith('r/'):
        return url[2:]

    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')

    if 'r' in path_parts:
        r_index = path_parts.index('r')
        if r_index + 1 < len(path_parts):
            return path_parts[r_index + 1]

    return url

async def scrape_reddit_mcp(subreddit_url, post_limit=1000):
    """Scrape Reddit using MCP server"""

    subreddit_name = extract_subreddit_name(subreddit_url)
    print(f"Scraping subreddit: r/{subreddit_name}")

    # MCP server parameters
    server_params = StdioServerParameters(
        command="uvx",
        args=["mcp-server-reddit"],
        env=None
    )

    reddit_texts = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("Connected to Reddit MCP server")

            # Fetch hot posts
            print(f"Fetching hot posts from r/{subreddit_name}...")
            hot_posts_result = await session.call_tool(
                "get_subreddit_hot_posts",
                arguments={"subreddit_name": subreddit_name, "limit": min(post_limit, 100)}
            )

            # Handle MCP response format - extract post IDs from text response
            response_text = hot_posts_result.content[0].text if hot_posts_result.content else ""

            print(f"Response preview: {response_text[:300]}...")

            # Extract post IDs from URLs in the response
            post_id_matches = re.findall(r'/comments/([a-zA-Z0-9]+)/', response_text)
            post_ids = list(dict.fromkeys(post_id_matches))[:post_limit]  # Remove duplicates, limit count

            print(f"Found {len(post_ids)} post IDs to fetch")

            # Process each post by fetching full content
            for idx, post_id in enumerate(post_ids, 1):
                try:
                    print(f"Fetching post {idx}/{len(post_ids)} (ID: {post_id})...")

                    # Fetch full post content including title and body text
                    post_content_result = await session.call_tool(
                        "get_post_content",
                        arguments={"post_id": post_id}
                    )

                    if post_content_result.content:
                        post_full_text = post_content_result.content[0].text

                        # Skip if it's an error message
                        if "Error processing" in post_full_text:
                            print(f"  ⚠ MCP server returned an error, skipping post")
                            continue

                        # Try to parse as JSON first
                        try:
                            post_data = json.loads(post_full_text)

                            # Extract title
                            if 'title' in post_data:
                                title = post_data['title'].strip()
                                if title:
                                    reddit_texts.append(title)

                            # Extract body text (can be selftext, body, or text)
                            body_text = post_data.get('selftext') or post_data.get('body') or post_data.get('text', '')
                            if body_text and body_text.strip() and body_text.lower() not in ['none', 'n/a', '[deleted]', '[removed]', '']:
                                reddit_texts.append(body_text.strip())

                            print(f"  ✓ Post content added")

                        except json.JSONDecodeError as e:
                            print(f"  ⚠ Could not parse post JSON: {e}")
                            # Don't add raw text as fallback

                    # Fetch comments for this post
                    try:
                        print(f"  Fetching comments...")
                        comments_result = await session.call_tool(
                            "get_post_comments",
                            arguments={"post_id": post_id}
                        )

                        if comments_result.content:
                            comments_text = comments_result.content[0].text

                            # Skip if it's an error message
                            if "Error processing" not in comments_text:
                                # Parse comments JSON to extract only body text
                                def extract_comment_bodies(data):
                                    """Recursively extract comment body text from nested structure"""
                                    bodies = []
                                    if isinstance(data, dict):
                                        if 'body' in data:
                                            body = data['body'].strip()
                                            if body and body not in ['[deleted]', '[removed]', '']:
                                                bodies.append(body)
                                        if 'replies' in data and data['replies']:
                                            for reply in data['replies']:
                                                bodies.extend(extract_comment_bodies(reply))
                                    elif isinstance(data, list):
                                        for item in data:
                                            bodies.extend(extract_comment_bodies(item))
                                    return bodies

                                try:
                                    comments_data = json.loads(comments_text)
                                    comment_bodies = extract_comment_bodies(comments_data)

                                    for body in comment_bodies:
                                        if body.strip():  # Extra check to ensure it's not empty
                                            reddit_texts.append(body)

                                    print(f"  ✓ Added {len(comment_bodies)} comments")

                                except json.JSONDecodeError as e:
                                    print(f"  ⚠ Could not parse comments JSON: {e}")
                                    # Don't add raw text as fallback
                            else:
                                print(f"  ⚠ MCP server returned an error, skipping comments")

                    except Exception as e:
                        print(f"  ✗ Error fetching comments: {e}")

                    # Rate limiting
                    if idx % 10 == 0:
                        print(f"Progress: {idx}/{len(post_ids)} posts processed, {len(reddit_texts)} total entries")
                        await asyncio.sleep(1)

                except Exception as e:
                    print(f"  ✗ Error fetching post {post_id}: {e}")

            print(f"\nTotal scraped: {len(post_ids)} posts, {len(reddit_texts)} total entries")

    # Save to CSV
    df = pd.DataFrame({'reddit_text': reddit_texts})
    output_file = f'{subreddit_name}_reddit_data.csv'
    df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"Data saved to {output_file}")

    return output_file

def main():
    if len(sys.argv) < 2:
        print("Usage: python reddit_mcp_scraper.py <subreddit_url> [post_limit]")
        print("Example: python reddit_mcp_scraper.py https://www.reddit.com/r/python/ 500")
        sys.exit(1)

    subreddit_url = sys.argv[1]
    post_limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    asyncio.run(scrape_reddit_mcp(subreddit_url, post_limit))

if __name__ == "__main__":
    main()
