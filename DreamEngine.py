import os
import json
from urllib.parse import urlparse
from openai import OpenAI
from bs4 import BeautifulSoup
from flask import Flask, render_template, session
import requests
import re

# Define a class to hold the result data
class Result:
    def __init__(self, title, snippet, url):
        self.Title = title
        self.Snippet = snippet
        self.URL = url

class DreamEngine:

    def __init__(self):
        self.client = OpenAI(base_url="http://localhost:1234/v1/", api_key="example")
        self.internet_db = dict()
        self.cache_dir = "cache"
        self.temperature = 2.1
        self.max_tokens = 8000
        self.system_prompt = (
            "You are an expert in creating realistic HTML webpages that could realistically exist on the internet, complete with substantial content, avoiding generating sample pages. "
            "Instead, you create webpages that are completely realistic and look as if they really existed on the web. "
            "Your responses should consist exclusively of HTML code, beginning with <!DOCTYPE html> and ending with </html>. "
            "When generating content such as articles, blog posts, etc., provide detailed and informative text rather than summaries or placeholders. "
            "You use few images in your HTML, CSS or JS, and when you do use an image it'll be linked from a real website instead and described with appropriate alt-text. "
            "Link to very few external resources, CSS and JS should ideally be internal in <style>/<script> tags and not linked from elsewhere. "
        )
        
        self.resultsList = []

        self.searxNGInstance = "https://searx.be/"

        # Ensure the cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _sanitize_summary(self, summary):
        """Remove hidden reasoning tags like <think>...</think> and similar artifacts."""
        if not summary:
            return summary

        banned_blocks = [
            r"<\s*think[^>]*>.*?<\s*/\s*think\s*>",
            r"<\s*reflection[^>]*>.*?<\s*/\s*reflection\s*>",
            r"<\s*reasoning[^>]*>.*?<\s*/\s*reasoning\s*>",
            r"<\s*analysis[^>]*>.*?<\s*/\s*analysis\s*>",
        ]

        cleaned_summary = summary
        for pattern in banned_blocks:
            cleaned_summary = re.sub(pattern, "", cleaned_summary, flags=re.IGNORECASE | re.DOTALL)

        # Remove any standalone opening/closing tags left behind from the banned list
        cleaned_summary = re.sub(r"</?\s*(think|reflection|reasoning|analysis)\s*>", "", cleaned_summary, flags=re.IGNORECASE)

        # Collapse excess whitespace
        cleaned_summary = re.sub(r"\s{2,}", " ", cleaned_summary).strip()

        return cleaned_summary or ""
    
    def _find_result_context(self, url, path):
        """Match the requested URL/path to the stored search results."""
        normalized_host = (url or "").lower().strip("/")
        normalized_path = path if path else "/"

        for result in self.resultsList:
            parsed = urlparse(result.URL)
            result_host = parsed.netloc.lower()
            result_path = parsed.path if parsed.path else "/"

            if result_host != normalized_host:
                continue

            if normalized_path == result_path or normalized_path.startswith(result_path.rstrip("/") + "/"):
                return {
                    "title": result.Title,
                    "snippet": result.Snippet,
                    "path": result_path
                }

        return None

    def getImageURL(self, searxNGURL, query):
        # Set a custom User-Agent string
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.1938.62 Safari/537.36 Edge/116.0.1938.62"
        }

        params = {
        'q': query,
        'categories': 'images'
        }

        try:
            response = requests.get(searxNGURL, params=params, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors

            #print(response.text)

            soup = BeautifulSoup(response.text, 'html.parser')
 
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.lower().endswith(".jpg"):
                    print(href)
                    return href
                
        except requests.RequestException as e:
            print(f"An error occurred: {e}")
            return None

    def _format_page(self, dirty_html):
        # Try to grab HTML from output with regex

        pattern = re.compile(
        r"(?:<!DOCTYPE html>\s*)?<html.*?</html>",
        re.DOTALL | re.IGNORECASE
        )
        match = pattern.search(dirty_html)

        if match:
            dirty_html = match.group(0)
        elif '<' in dirty_html and '>' in dirty_html: 
            # Fallback, just grab everything from < to >
            
            # Remove anything before the first '<' and after the last '>'
            start_index = dirty_html.find('<')
            end_index = dirty_html.rfind('>') + 1  # Include the '>'

            if start_index != -1 and end_index != -1:
                dirty_html = dirty_html[start_index:end_index]
        else:
            # If the output is not HTML, return it as is (let the browser sort it out)
            return dirty_html

        soup = BeautifulSoup(dirty_html, "html.parser")

        for a in soup.find_all("a"):
            try:
                # Do not modify "mailto:" links
                if a["href"].startswith("mailto:"):
                    continue

                # Remove HTTP and HTTPS
                a["href"] = a["href"].replace("http://", "").replace("https://", "")

                # Remove any non-alphanumeric characters from the beginning of the URL
                a["href"] = re.sub(r'^[^a-zA-Z0-9]+', '', a["href"])

                # Add a / (Make links relative)
                a["href"] = "/" + a["href"]
            except:
                continue

        for img in soup.find_all('img'):
            alt_text = img.get('alt', '')
            if alt_text:
                img['src'] = self.getImageURL(self.searxNGInstance, alt_text)

        return str(soup)

    def _cache_page(self, url, path, content):
        # Create site-specific cache directory
        site_cache_dir = os.path.join(self.cache_dir, url)
        os.makedirs(site_cache_dir, exist_ok=True)

        # Save the page in the cache
        page_path = os.path.join(site_cache_dir, path.lstrip("/").replace("/", "_") + ".html")
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _load_cached_page(self, url, path):
        # Load the cached page if it exists
        site_cache_dir = os.path.join(self.cache_dir, url)
        page_path = os.path.join(site_cache_dir, path.lstrip("/").replace("/", "_") + ".html")
        if os.path.exists(page_path):
            with open(page_path, "r", encoding="utf-8") as f:
                return f.read()
        return None
    
    def _summarize_page(self, html_content):
        """Summarize a generated HTML page including content, design, layout, and formatting."""
        # Parse the HTML
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Extract style information
        style_tags = soup.find_all('style')
        style_content = ' '.join([style.get_text()[:500] for style in style_tags])  # Limit style content
        
        # Get structural information
        has_header = soup.find('header') is not None or soup.find('h1') is not None
        has_nav = soup.find('nav') is not None
        has_sidebar = soup.find('aside') is not None or soup.find(class_=lambda x: x and 'sidebar' in x.lower()) is not None
        has_footer = soup.find('footer') is not None
        
        # Extract text content (without removing styles, we'll include them separately)
        text_soup = BeautifulSoup(html_content, "html.parser")
        for script_or_style in text_soup(["script", "style"]):
            script_or_style.decompose()
        
        text = text_soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Truncate if too long (to avoid token limits)
        if len(text) > 6000:
            text = text[:6000] + "..."
        
        # Build a comprehensive description for the LLM
        page_description = f"""PAGE CONTENT:
{text}

PAGE STRUCTURE:
- Has header: {has_header}
- Has navigation: {has_nav}
- Has sidebar: {has_sidebar}
- Has footer: {has_footer}

STYLING/CSS (sample):
{style_content[:800] if style_content else 'No inline styles detected'}"""
        
        # Ask the LLM to summarize both content and design
        summary_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes webpages including BOTH content AND design/layout. In 3-4 sentences, describe: 1) The main topic/content, 2) The visual design and color scheme, 3) The layout structure and key design elements."
                },
                {
                    "role": "user",
                    "content": f"Summarize this webpage's content, design, and layout:\n\n{page_description}"
                }
            ],
            model="",
            temperature=0.7,
            max_tokens=600
        )
        
        raw_summary = summary_completion.choices[0].message.content.strip()
        return self._sanitize_summary(raw_summary)
    
    def get_page(self, url, path):
        # Check the cache first
        cached_page = self._load_cached_page(url, path)
        if cached_page:
            # Even for cached pages, summarize and store for context
            summary = self._summarize_page(cached_page)
            session['last_page_summary'] = summary
            return cached_page

        # Normalize URL + path for downstream use
        path = path or "/"
        if not path.startswith("/"):
            path = "/" + path
        full_resource = f"{url}{path}"

        # Build context from search results and browsing history
        context_segments = []

        result_context = self._find_result_context(url, path)
        if result_context:
            context_segments.append(
                "Search Result Context: "
                f"Title: '{result_context['title']}'. "
                f"Description: '{result_context['snippet']}'. "
                f"Path: '{result_context['path']}'. "
                "Use all of these details when determining the site's purpose and structure."
            )

        # Get context from the last page summary if available
        last_summary = session.get('last_page_summary')
        if last_summary:
            clean_summary = self._sanitize_summary(last_summary)
            if clean_summary != last_summary:
                session['last_page_summary'] = clean_summary
            context_segments.append(
                "Browsing Continuity: "
                f"The previous page on this site was summarized as '{clean_summary}'. "
                f"The user has now navigated to {full_resource}; treat this URL+path as the primary signal. "
                "Assume this is a different part of the site (could be higher, lower, or lateral in the structure) that should feel connected yet distinct."
            )

        if not context_segments:
            context_segments.append(
                f"No stored metadata exists; rely on the domain '{url}' and requested path '{path}' to infer intent."
            )

        context_info = " ".join(context_segments)
        
        if result_context:
            print(f"Search result context matched for {full_resource}")
        else:
            print(f"No direct search context for {full_resource}")
        print(f"Context info: {context_info}")

        # Construct the prompt
        prompt = (
            f"Give me an HTML4/Geocities era webpage from the fictional site of '{url}' at the resource path of '{path}'. "
            "Attempt to comply with 2000s web standards. "
            #f"If links are generated to another resource on the current website, have the current url prepended ({url}) to them. "
            f"{url} must be included at the beginning of any link generated to another resource on the current website. "
            f"Ensure all links are absolute paths. Links to internal pages should start with the full URL, {url}, while external links should point directly to external resources. Do not use relative URLs or shorten paths. "
            "Make the page look nice, unique, and creative using internal inline CSS stylesheets; avoid generic and boring appearances. The use of CSS animation is also acceptable. "
            "If JavaScript is needed for interactivity (including but not limited to forms or pop-ups), include inline scripts that complement the page's functionality. "
            "The use of images should be limited, and when used, should be linked from external sources. Images must be described with appropriate alt-text. "
            "When generating site content, treat all provided context as information learned from previously visited pages on the same site, but let the requested URL plus path dictate hierarchy and focus. "
            "Maintain continuity and references, yet ensure this is a new page with distinct purpose, structure, and copy that plausibly follows from that context even if it sits above, below, or beside it in site structure. "
            "Do not copy prior wording verbatim; instead, expand upon or riff off it the way a different subpage would. "
            f"{context_info} "
            "If any contextual information conflicts, prioritize the meaning implied by the URL/domain and requested path."
        )

        # Generate the page
        generated_page_completion = self.client.chat.completions.create(messages=[
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ], model="", temperature=self.temperature, max_tokens=self.max_tokens)

        generated_page = generated_page_completion.choices[0].message.content
        formatted_page = self._format_page(generated_page)

        # Cache the page
        self._cache_page(url, path, formatted_page)

        # Summarize the page for use as context in the next generation
        summary = self._summarize_page(formatted_page)
        session['last_page_summary'] = summary
        print(f"Page summary saved: {summary}")

        return formatted_page
        
    def get_single_result(self, query):
        # Generate description
        resultCompletion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that strictly returns valid JSON with exactly three keys: "
                        "title, snippet, url. No extra text. "
                        "When generating a single search result, follow these guidelines:\n\n"
                        "1) Title: Create a short, engaging title (4 to 12 tokens) relevant to the query; titles should be creative and not too close to the query."
                        "It should feel authentic without revealing the website is fictitious.\n\n"
                        "2) Snippet: Provide a concise, single-paragraph description (3 to 5 sentences) that outlines the website’s content "
                        "as if from a search engine result. Avoid referencing real websites or indicating that the site is hypothetical.\n\n"
                        "3) URL: Provide a plausible URL in the format 'http://website.com/etc', "
                        "unique and relevant to the topic. Avoid referencing real websites or indicating that the site is hypothetical.\n\n"
                        "Return the result strictly in JSON with the keys 'title', 'snippet', and 'url'—in that order—"
                        "with no additional text or formatting."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate a single search result for '{query}'. "
                        "Return JSON with exactly three keys: title, snippet, url."
                    ),
                },
            ],
            model="",
            temperature=self.temperature,
            max_tokens=2000,
        )

        # Raw output from the LLM
        raw_output = resultCompletion.choices[0].message.content
        #print(raw_output)

        # Remove extra text from output, we just want the JSON string
        regex_pattern = r'(\{.*?\}|\[.*?\])'
        match = re.search(regex_pattern, raw_output, re.DOTALL)

        # Convert it to a Result object
        if match:
            json_str = match.group(1).strip()
            print("Result: " + json_str)
            try:
                data = json.loads(json_str)
                # Return a well-formed Result object
                return Result(
                    title=data["title"].strip(),
                    snippet=data["snippet"].strip(),
                    url=data["url"].strip()
                )
            except (json.JSONDecodeError, KeyError) as e:
                print(f"JSON parse error: {e}")
                pass

        return Result(
            title="Error",
            snippet="Error",
            url="http://error.com"
        )

    def get_search(self, query):
        # Clear list
        self.resultsList.clear()

        # Clear context data when starting a new search
        session.pop('last_page_summary', None)

        print("Starting new search - context cleared")

        # Get 5 results
        for _ in range(5):
            new_result = self.get_single_result(query)
            self.resultsList.append(new_result)
        
        # You can return resultsList or process it further
        return self._format_page(render_template("results.htm", title = query, searchResults = self.resultsList))