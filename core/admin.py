from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django import forms
from django.conf import settings
from .models import Page, Post, Category, Tag, Service, PaymentFeeRow, FAQItem, JoinOurTeamSubmission
from ckeditor.widgets import CKEditorWidget
class PageAdminForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = [
            # SEO first
            'seo_title', 'seo_description', 'seo_keywords', 'seo_image_url',
            # Core
            'title', 'slug', 'path', 'status',
            # Content
            'excerpt_html', 'content_html',
        ]
        widgets = {
            'seo_description': forms.Textarea(attrs={'rows': 3}),
            'seo_keywords': forms.Textarea(attrs={'rows': 3}),
            'excerpt_html': CKEditorWidget(),
            'content_html': CKEditorWidget(),
        }



@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    form = PageAdminForm
    list_display = ("title", "path", "status", "published_at")
    search_fields = ("title", "path", "content_html", "seo_title", "seo_description", "seo_keywords")
    list_filter = ("status",)
    ordering = ("title",)
    fieldsets = (
        ("SEO", {
            'fields': ("seo_title", "seo_description", "seo_keywords", "seo_image_url", "excerpt_preview", "serp_preview")
        }),
        ("Page routing", {
            'fields': ("title", "slug", "path", "status")
        }),
        ("Content", {
            'fields': ("excerpt_html", "content_html"),
        }),
        ("Publishing", {
            'fields': ("published_at", "modified_at")
        }),
        ("Import metadata", {
            'classes': ('collapse',),
            'fields': ()
        }),
    )
    readonly_fields = ("serp_preview", "published_at", "modified_at", "excerpt_preview")

    class Media:
        css = {
            'all': ('admin/overrides.css',)
        }

    def serp_preview(self, obj: Page | None):
        base = (getattr(settings, 'BASE_URL', '') or '').rstrip('/')
        url = f"{base}/{obj.path}" if obj and getattr(obj, 'path', None) else f"{base}/"
        title = (getattr(obj, 'seo_title', '') or getattr(obj, 'title', '') or '') if obj else ''
        desc = (getattr(obj, 'seo_description', '') or getattr(obj, 'excerpt_html', '') or '') if obj else ''
        # basic trim for preview purposes
        title = (title[:60] + '…') if len(title) > 60 else title
        # naive strip tags for preview only
        import re
        desc_txt = re.sub(r"<[^>]+>", "", desc or '').strip()
        desc_txt = (desc_txt[:157] + '…') if len(desc_txt) > 158 else desc_txt
        return format_html(
            '<div style="border:1px solid #ddd;padding:8px;border-radius:6px">\n'
            '<div style="color:#1a0dab;font-size:18px;line-height:1.2">{}</div>\n'
            '<div style="color:#006621;font-size:14px">{}</div>\n'
            '<div style="color:#545454;font-size:13px">{}</div>\n'
            '</div>',
            title, url, desc_txt
        )
    serp_preview.short_description = "SERP preview"

    # ModelForm above controls widgets explicitly

    def excerpt_preview(self, obj: Page | None):
        import re
        if not obj:
            return ''
        source = getattr(obj, 'excerpt_html', '') or getattr(obj, 'content_html', '') or ''
        txt = re.sub(r"<[^>]+>", "", source).strip()
        return (txt[:157] + '…') if len(txt) > 158 else txt
    excerpt_preview.short_description = "Derived description preview"

    def save_model(self, request, obj: Page, form, change):
        from django.utils import timezone
        # Auto derive excerpt if missing
        if not obj.excerpt_html and obj.content_html:
            from django.utils.html import strip_tags
            txt = strip_tags(obj.content_html).strip()
            obj.excerpt_html = txt[:300]
        # Auto-generate content_html if empty
        if not obj.content_html:
            # Prefer seo_description or excerpt to build a simple hero block
            desc = (obj.seo_description or obj.excerpt_html or "").strip()
            body = f"<section class=\"hero\"><h1>{obj.title}</h1>" + (f"<p>{desc}</p>" if desc else "") + "</section>"
            obj.content_html = body
        # Auto-set published/modified timestamps
        now = timezone.now()
        from .models import PublishStatus
        if not obj.published_at and getattr(obj, 'status', '') == PublishStatus.PUBLISH:
            obj.published_at = now
        obj.modified_at = now
        super().save_model(request, obj, form, change)
class PostAdminForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = [
            # SEO first
            'seo_title', 'seo_description', 'seo_keywords', 'seo_image_url',
            # Core
            'title', 'slug', 'status', 'categories', 'tags',
        ]
        widgets = {
            'seo_description': forms.Textarea(attrs={'rows': 3}),
            'seo_keywords': forms.Textarea(attrs={'rows': 3}),
        }


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    form = PostAdminForm
    list_display = ("title", "published_at", "status")
    search_fields = ("title", "content_html", "seo_title", "seo_description", "seo_keywords")
    list_filter = ("status", "categories")
    fieldsets = (
        ("SEO", {
            'fields': ("seo_title", "seo_description", "seo_keywords", "seo_image_url", "excerpt_preview", "serp_preview")
        }),
        ("Post", {
            'fields': ("title", "slug", "status", "categories", "tags")
        }),
        ("Publishing", {
            'fields': ("published_at", "modified_at")
        }),
        ("Import metadata", {
            'classes': ('collapse',),
            'fields': ()
        }),
    )
    readonly_fields = ("serp_preview", "published_at", "modified_at", "excerpt_preview")

    class Media:
        css = {
            'all': ('admin/overrides.css',)
        }

    def serp_preview(self, obj: Post | None):
        base = (getattr(settings, 'BASE_URL', '') or '').rstrip('/')
        url = f"{base}/blog/{obj.slug}/" if obj and getattr(obj, 'slug', None) else base
        title = (getattr(obj, 'seo_title', '') or getattr(obj, 'title', '') or '') if obj else ''
        desc = (getattr(obj, 'seo_description', '') or getattr(obj, 'excerpt_html', '') or getattr(obj, 'content_html', '') or '') if obj else ''
        title = (title[:60] + '…') if len(title) > 60 else title
        import re
        desc_txt = re.sub(r"<[^>]+>", "", desc or '').strip()
        desc_txt = (desc_txt[:157] + '…') if len(desc_txt) > 158 else desc_txt
        return format_html(
            '<div style="border:1px solid #ddd;padding:8px;border-radius:6px">\n'
            '<div style="color:#1a0dab;font-size:18px;line-height:1.2">{}</div>\n'
            '<div style="color:#006621;font-size:14px">{}</div>\n'
            '<div style="color:#545454;font-size:13px">{}</div>\n'
            '</div>',
            title, url, desc_txt
        )
    serp_preview.short_description = "SERP preview"

    # ModelForm above controls widgets explicitly

    def excerpt_preview(self, obj: Post | None):
        import re
        if not obj:
            return ''
        source = getattr(obj, 'excerpt_html', '') or getattr(obj, 'content_html', '') or ''
        txt = re.sub(r"<[^>]+>", "", source).strip()
        return (txt[:157] + '…') if len(txt) > 158 else txt
    excerpt_preview.short_description = "Derived description preview"

    def save_model(self, request, obj: Post, form, change):
        from django.utils import timezone
        # Auto derive excerpt if missing
        if not obj.excerpt_html and obj.content_html:
            from django.utils.html import strip_tags
            txt = strip_tags(obj.content_html).strip()
            obj.excerpt_html = txt[:300]
        # Auto-generate content_html if empty
        if not obj.content_html:
            desc = (obj.seo_description or obj.excerpt_html or "").strip()
            body = f"<article class=\"post\"><h1>{obj.title}</h1>" + (f"<p>{desc}</p>" if desc else "") + "</article>"
            obj.content_html = body
        # Auto-set published/modified timestamps
        now = timezone.now()
        from .models import PublishStatus
        if not obj.published_at and getattr(obj, 'status', '') == PublishStatus.PUBLISH:
            obj.published_at = now
        obj.modified_at = now
        super().save_model(request, obj, form, change)


@admin.register(JoinOurTeamSubmission)
class JoinOurTeamSubmissionAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "created", "is_reviewed")
    list_filter = ("is_reviewed", "created")
    search_fields = ("first_name", "last_name", "email", "message")
    readonly_fields = ("created", "updated", "reviewed_at", "user_agent")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    class ServiceAdminForm(forms.ModelForm):
        class Meta:
            model = Service
            fields = ['title', 'slug', 'excerpt', 'image_url', 'page', 'order', 'status']
            widgets = {
                'excerpt': CKEditorWidget(),
            }

    form = ServiceAdminForm
    list_display = ("title", "slug", "order", "status", "linked_page")
    list_editable = ("order", "status")
    search_fields = ("title", "excerpt", "slug", "page__title", "page__path")
    list_filter = ("status",)
    ordering = ("order", "title")

    readonly_fields = ("linked_page", "page_edit_link", "page_excerpt_preview", "page_content_preview")
    fieldsets = (
        ("Service", {
            'fields': ("title", "slug", "status", "order", "image_url", "excerpt"),
        }),
        ("Linked Page", {
            'fields': ("page", "linked_page", "page_edit_link", "page_excerpt_preview", "page_content_preview"),
        }),
    )

    def linked_page(self, obj: Service):
        return f"/{obj.page.path}" if obj and obj.page else "—"
    linked_page.short_description = "Detail URL"

    def page_edit_link(self, obj: Service):
        if obj and getattr(obj, 'page_id', None):
            title = obj.page.title if obj.page else 'Page'
            return format_html('<a href="/admin/core/page/{}/change/" target="_blank">Edit Page “{}”</a>', obj.page_id, title)
        return "—"
    page_edit_link.short_description = "Edit linked Page"

    def page_excerpt_preview(self, obj: Service | None):
        """Plain-text preview derived from the linked Page's excerpt/content."""
        import re
        if not obj or not getattr(obj, 'page', None):
            return ''
        source = getattr(obj.page, 'excerpt_html', '') or getattr(obj.page, 'content_html', '') or ''
        txt = re.sub(r"<[^>]+>", "", source).strip()
        return (txt[:157] + '…') if len(txt) > 158 else txt
    page_excerpt_preview.short_description = "Derived description preview"

    def page_content_preview(self, obj: Service | None):
        """HTML preview of the linked Page content (scrollable box)."""
        if not obj or not getattr(obj, 'page', None):
            return ''
        html = getattr(obj.page, 'content_html', '') or ''
        if not html:
            return ''
        # Wrap in a scrollable container to avoid overlong admin pages
        container = '<div style="max-height:240px; overflow:auto; border:1px solid #ddd; padding:8px; border-radius:6px; background:#fff">{}</div>'
        return format_html(container, mark_safe(html))
    page_content_preview.short_description = "Page content preview"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "wp_id")
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "wp_id")
    search_fields = ("name",)


@admin.register(PaymentFeeRow)
class PaymentFeeRowAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "order", "doctoral_fee", "masters_fee", "supervised_fee")
    list_editable = ("order",)
    list_filter = ("category",)
    search_fields = ("name", "doctoral_fee", "masters_fee", "supervised_fee")
    ordering = ("category", "order", "name")


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
	list_display = ("question", "order", "is_active")
	list_editable = ("order", "is_active")
	list_filter = ("is_active",)
	search_fields = ("question", "answer")
	ordering = ("order", "id")

# NavItem admin removed; header uses static template markup
