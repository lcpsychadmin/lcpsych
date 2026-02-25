from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import json
import os
import requests
from django.core.files.base import ContentFile
from django.utils.text import slugify
from urllib.parse import urlparse, quote_plus
import re
from datetime import date

from .forms import PostForm
from .models import Post


class ManagePostsView(LoginRequiredMixin, View):
    template_name = 'blog/manage_posts.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        q = (request.GET.get('q') or '').strip()
        per_page_raw = request.GET.get('per_page') or ''
        try:
            per_page = int(per_page_raw)
        except ValueError:
            per_page = 10
        if per_page not in (10, 25, 50):
            per_page = 10

        posts = Post.objects.all() if request.user.is_staff else Post.objects.filter(author=request.user)
        posts = posts.select_related('author', 'author__therapist_profile').prefetch_related('categories')
        if q:
            posts = posts.filter(
                Q(title__icontains=q)
                | Q(slug__icontains=q)
                | Q(body__icontains=q)
                | Q(seo_description__icontains=q)
            )
        posts = posts.order_by('-publish_at', '-created_at')

        paginator = Paginator(posts, per_page)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return render(
            request,
            self.template_name,
            {
                'posts': page_obj.object_list,
                'page_obj': page_obj,
                'paginator': paginator,
                'q': q,
                'per_page': per_page,
                'per_page_options': (10, 25, 50),
                'viewing_all': request.user.is_staff,
            },
        )


class PublicPostListView(View):
    template_name = 'blog/public_post_list.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        q = (request.GET.get('q') or '').strip()
        per_page_raw = request.GET.get('per_page') or ''
        try:
            per_page = int(per_page_raw)
        except ValueError:
            per_page = 10
        if per_page not in (10, 25, 50):
            per_page = 10

        posts = Post.published.select_related('author', 'author__therapist_profile').prefetch_related('categories')
        if q:
            posts = posts.filter(
                Q(title__icontains=q)
                | Q(slug__icontains=q)
                | Q(body__icontains=q)
                | Q(seo_description__icontains=q)
            )
        posts = posts.order_by('-publish_at', '-created_at')

        paginator = Paginator(posts, per_page)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return render(
            request,
            self.template_name,
            {
                'posts': page_obj.object_list,
                'page_obj': page_obj,
                'paginator': paginator,
                'q': q,
                'per_page': per_page,
                'per_page_options': (10, 25, 50),
            },
        )

class PostCreateView(LoginRequiredMixin, View):
    template_name = 'blog/post_form.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        form = PostForm()
        return render(request, self.template_name, {'form': form, 'editing': False})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()
            form.save_new_categories(post)
            attach_ai_image_if_needed(post, request.POST.get('ai_image_url'))
            messages.success(request, 'Blog post created.')
            return redirect('blog:manage')
        return render(request, self.template_name, {'form': form, 'editing': False})


class PostEditView(LoginRequiredMixin, View):
    template_name = 'blog/post_form.html'

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        lookup = {'pk': pk}
        if not request.user.is_staff:
            lookup['author'] = request.user
        post = get_object_or_404(Post, **lookup)
        form = PostForm(instance=post)
        return render(request, self.template_name, {'form': form, 'editing': True, 'post_obj': post})

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        lookup = {'pk': pk}
        if not request.user.is_staff:
            lookup['author'] = request.user
        post = get_object_or_404(Post, **lookup)
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.author = request.user
            updated.save()
            form.save_m2m()
            form.save_new_categories(updated)
            attach_ai_image_if_needed(updated, request.POST.get('ai_image_url'))
            messages.success(request, 'Blog post updated.')
            return redirect('blog:manage')
        return render(request, self.template_name, {'form': form, 'editing': True, 'post_obj': post})


class PostDetailView(View):
    template_name = 'blog/post_detail.html'

    def get(self, request: HttpRequest, slug: str) -> HttpResponse:
        post = get_object_or_404(Post, slug=slug)
        if post.status != Post.STATUS_PUBLISHED:
            if not request.user.is_authenticated or post.author != request.user:
                raise Http404()
        return render(request, self.template_name, {'post': post})


class PostDeleteView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        post = get_object_or_404(Post, pk=pk)
        if not request.user.is_staff and post.author != request.user:
            raise Http404()
        post.delete()
        messages.success(request, 'Blog post deleted.')
        return redirect('blog:manage')


class PostAIGenerateView(LoginRequiredMixin, View):
    """Generate a draft blog post using OpenAI."""

    def post(self, request: HttpRequest) -> JsonResponse:
        try:
            data = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload."}, status=400)

        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            return JsonResponse({"error": "Please provide a prompt."}, status=400)
        if len(prompt) > 600:
            return JsonResponse({"error": "Prompt is too long. Please keep it under 600 characters."}, status=400)

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return JsonResponse({"error": "OPENAI_API_KEY is not configured."}, status=400)

        existing = list(Post.objects.values_list("title", "slug")[:200])
        existing_titles = [t for t, _ in existing if t]
        existing_slugs = [s for _, s in existing if s]

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You draft concise blog posts. Respond with JSON ONLY (no prose, no code fences) "
                                "using keys: title, slug, seo_title, body_html, seo_description, image_url. "
                                "Use <p> and <h2>/<h3>/<ul> tags in body_html. "
                                "Slug must be a lowercase-kebab value under 60 chars. "
                                "seo_title should be under 60 chars; seo_description under 160 chars. "
                                "image_url must be a safe, royalty-free URL (1200x630 if possible) that visually matches the post topic (no logos, no identifiable patients; favor calming, therapeutic, or contextual imagery). Leave blank if unsure. "
                                "Focus on current, timely psychology/mental health trends and avoid duplicating any existing titles/slugs provided. "
                                f"Existing titles: {existing_titles[:50]}. Existing slugs: {existing_slugs[:50]}. "
                                "Limit body to about 500 words."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    "temperature": 0.65,
                    "max_tokens": 900,
                },
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:  # type: ignore
            return JsonResponse({"error": f"AI request failed: {exc}"}, status=502)

        try:
            completion = response.json()["choices"][0]["message"]["content"]
        except Exception:
            return JsonResponse({"error": "Unexpected AI response format."}, status=502)

        parsed = parse_ai_completion(completion)

        title = (parsed.get("title") or "").strip()
        slug_val = ensure_unique_slug(slugify(parsed.get("slug") or title)[:60])
        seo_title = (parsed.get("seo_title") or title)[:160]
        image_url = (parsed.get("image_url") or "").strip()
        if not image_url:
            image_url = build_topic_image_url(title or seo_title or slug_val)
        if not image_url and slug_val:
            image_url = f"https://picsum.photos/seed/{slug_val}/1200/630"

        return JsonResponse(
            {
                "title": title,
                "slug": slug_val,
                "seo_title": seo_title,
                "body_html": parsed.get("body_html", "").strip(),
                "seo_description": (parsed.get("seo_description") or "").strip(),
                "image_url": image_url,
            }
        )


class PostAITrendsView(LoginRequiredMixin, View):
    """Return trend-based blog ideas avoiding existing posts."""

    def get(self, request: HttpRequest) -> JsonResponse:
        limit = 6
        keyword = (request.GET.get("q") or "").strip()
        current_year = date.today().year
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return JsonResponse({"error": "OPENAI_API_KEY is not configured."}, status=400)

        existing = list(Post.objects.values_list("title", "slug")[:200])
        existing_titles = [t for t, _ in existing if t]
        existing_slugs = [s for _, s in existing if s]

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You suggest blog post ideas in psychology/mental health, timely and trend-focused. "
                                "Draw inspiration from reputable psychology publications (e.g., Psychology Today, APA Monitor, Harvard Health). "
                                "Return JSON array of short idea strings (max 140 chars each), no numbering or bullets. "
                                "Avoid outdated topics (ignore news or studies before "
                                f"{current_year - 1}). "
                                "Do NOT duplicate any existing titles/slugs provided."
                                f" Existing titles: {existing_titles[:60]}. Existing slugs: {existing_slugs[:60]}"
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Generate {limit} unique idea strings that are current, distinct, and relevant to "
                                f"{keyword or 'psychology and mental health'}. "
                                f"Keep them tied to reputable psychology sources and the {current_year} timeframe. "
                                "No numbering or bullets."
                            ),
                        },
                    ],
                    "temperature": 0.7,
                    "max_tokens": 400,
                },
                timeout=20,
            )
            response.raise_for_status()
        except requests.RequestException as exc:  # type: ignore
            return JsonResponse({"error": f"AI request failed: {exc}"}, status=502)

        try:
            completion = response.json()["choices"][0]["message"]["content"]
        except Exception:
            return JsonResponse({"error": "Unexpected AI response format."}, status=502)

        ideas = parse_ideas_array(completion)
        if not ideas:
            return JsonResponse({"error": "No ideas returned."}, status=502)

        return JsonResponse({"ideas": ideas[:limit]})


def attach_ai_image_if_needed(post: Post, url: str | None) -> None:
    """Attach downloaded image if post lacks one, using AI/manual URL or fallback."""
    if post.feature_image:
        return

    url = (url or '').strip()
    if not url:
        url = build_fallback_image_url(post)

    file_obj = fetch_image_from_url(url)
    if not file_obj:
        return

    filename = f"{slugify(post.slug or post.title or 'post')}.jpg"
    post.feature_image.save(filename, file_obj, save=True)
def fetch_image_from_url(url: str) -> ContentFile | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    try:
        resp = requests.get(
            url,
            timeout=10,
            stream=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; LCPsychBot/1.0)",
                "Accept": "image/*,*/*;q=0.8",
            },
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None

    content_type = resp.headers.get("Content-Type", "").lower()
    if not content_type.startswith("image/"):
        return None

    max_bytes = 5 * 1024 * 1024  # 5MB limit
    data = resp.content[:max_bytes + 1]
    if len(data) > max_bytes:
        return None

    return ContentFile(data)


def build_fallback_image_url(post: Post) -> str:
    seed = slugify(post.slug or post.title or 'post') or 'post'
    return f"https://picsum.photos/seed/{seed}/1200/630"


def build_topic_image_url(topic: str) -> str:
    """Return a topical placeholder image URL keyed to the topic/slug."""
    topic = (topic or '').strip() or 'psychology'
    keyword = quote_plus(slugify(topic) or topic)
    return f"https://source.unsplash.com/1200x630/?{keyword}"


def parse_ai_completion(raw: str) -> dict:
    text = (raw or '').strip()
    # Strip common code fences like ```json ... ```
    if text.startswith('```'):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*", '', text)
        text = re.sub(r"```$", '', text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to salvage embedded JSON within surrounding text
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass

    # Fallback: try to pull key/value pairs from a loosely formatted response
    fields = {
        "title": "",
        "slug": "",
        "seo_title": "",
        "body_html": "",
        "seo_description": "",
        "image_url": "",
    }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        lower = ln.lower()
        if lower.startswith(('title:', 'title-', 'title —', 'title –', 'title=')):
            fields["title"] = re.split(r"[:=\-\u2014\u2013]", ln, 1)[1].strip()
            continue
        if lower.startswith(('slug:', 'slug-', 'slug=', 'slug —', 'slug –')):
            fields["slug"] = re.split(r"[:=\-\u2014\u2013]", ln, 1)[1].strip()
            continue
        if lower.startswith(('seo title:', 'seo_title:', 'seo title -', 'seo_title -', 'seo title —', 'seo_title —', 'seo title –', 'seo_title –', 'seo title=', 'seo_title=')):
            fields["seo_title"] = re.split(r"[:=\-\u2014\u2013]", ln, 1)[1].strip()
            continue
        if lower.startswith(('seo description:', 'seo_description:', 'seo description -', 'seo_description -', 'seo description —', 'seo_description —', 'seo description –', 'seo_description –', 'seo description=', 'seo_description=')):
            fields["seo_description"] = re.split(r"[:=\-\u2014\u2013]", ln, 1)[1].strip()
            continue
        if lower.startswith(('image url:', 'image_url:', 'image url -', 'image_url -', 'image url —', 'image_url —', 'image url –', 'image_url –', 'image url=', 'image_url=')):
            fields["image_url"] = re.split(r"[:=\-\u2014\u2013]", ln, 1)[1].strip()
            continue

    # Whatever remains, treat as body if it looks like HTML or paragraphs
    if not fields["body_html"]:
        # Join non-key lines to form a body
        unmatched = []
        for ln in lines:
            lower = ln.lower()
            if any(lower.startswith(prefix) for prefix in (
                'title:', 'slug:', 'seo title:', 'seo_title:', 'seo description:', 'seo_description:', 'image url:', 'image_url:'
            )):
                continue
            unmatched.append(ln)
        if unmatched:
            fields["body_html"] = '\n'.join(unmatched)

    return fields


def ensure_unique_slug(base: str) -> str:
    base = base or "post"
    candidate = base
    suffix = 2
    while Post.objects.filter(slug__iexact=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
        if suffix > 50:  # avoid excessive loops
            break
    return candidate[:60]


def parse_ideas_array(raw: str) -> list[str]:
    text = (raw or '').strip()
    if text.startswith('```'):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*", '', text)
        text = re.sub(r"```$", '', text).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
    except json.JSONDecodeError:
        pass
    # fallback: split lines
    lines = [ln.strip('-•\t ')
             for ln in text.splitlines()
             if ln.strip('-•\t ')]
    return lines
