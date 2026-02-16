import os

import os
import sys
import django
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import urlopen

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lcpsych.settings")
django.setup()
from django.conf import settings
from blog.models import Post

images = {
    "cbt-practical-guide": {"url": "https://picsum.photos/id/1011/1200/800", "alt": "Therapist and client seated in a calm office"},
    "managing-anxiety-grounding": {"url": "https://picsum.photos/id/1018/1200/800", "alt": "Sunlit forest path for a calming scene"},
    "supporting-teen-therapy": {"url": "https://picsum.photos/id/1027/1200/800", "alt": "Parent and teen talking together"},
    "sleep-hygiene-reset": {"url": "https://picsum.photos/id/1067/1200/800", "alt": "Soft bedroom scene with warm light"},
    "first-therapy-session": {"url": "https://picsum.photos/id/1074/1200/800", "alt": "Inviting therapy office with chairs"},
}

media_root = Path(settings.MEDIA_ROOT) / "posts"
media_root.mkdir(parents=True, exist_ok=True)

for slug, data in images.items():
    try:
        with urlopen(data["url"], timeout=30) as resp:
            content = resp.read()
        img_path = media_root / f"{slug}.jpg"
        img_path.write_bytes(content)
        print(f"saved image for {slug} -> {img_path}")
    except Exception as exc:
        print(f"failed to fetch {slug}: {exc}")
        continue

    try:
        post = Post.objects.get(slug=slug)
    except Post.DoesNotExist:
        print(f"post missing for slug {slug}")
        continue

    img_html = (
        f"<figure><img src='/media/posts/{slug}.jpg' alt='{data['alt']}' "
        "style='width:100%;height:auto;border-radius:16px;margin-bottom:16px;'>"
        f"<figcaption style='color:#6b7280;font-size:0.95rem;margin-top:4px;'>{post.seo_title or post.title}</figcaption></figure>"
    )
    if f"/media/posts/{slug}.jpg" not in post.body:
        post.body = img_html + post.body
        post.save(update_fields=["body"])
        print(f"updated body with image for {slug}")
    else:
        print(f"image already present in body for {slug}")

print("done")
