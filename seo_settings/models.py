from django.db import models

KEYWORD_CATEGORY_CHOICES = [
    ('service', 'Service'),
    ('testing', 'Testing'),
    ('modality', 'Modality'),
    ('location', 'Location'),
]


class SEOGlobalSettings(models.Model):
    """Singleton model — only one row (pk=1) is ever created."""

    enable_search_console = models.BooleanField(
        default=False,
        verbose_name='Enable Search Console',
    )
    enable_internal_search_tracking = models.BooleanField(
        default=False,
        verbose_name='Enable internal search tracking',
    )
    enable_dead_url_logging = models.BooleanField(
        default=False,
        verbose_name='Enable dead URL / 404 logging',
    )
    enable_competitor_scraping = models.BooleanField(
        default=False,
        verbose_name='Enable competitor scraping',
    )
    enable_gap_analysis = models.BooleanField(
        default=False,
        verbose_name='Enable gap analysis',
    )
    search_console_property_url = models.URLField(
        blank=True,
        verbose_name='Search Console property URL',
        help_text='e.g. https://www.lcpsych.com/',
    )
    google_client_email = models.CharField(
        max_length=254,
        blank=True,
        verbose_name='Google service account email',
    )
    google_private_key = models.TextField(
        blank=True,
        verbose_name='Google private key (PEM)',
        help_text='Paste the full PEM-encoded private key from your service account JSON file.',
    )
    url_removal_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='URL removal token',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Last updated')

    class Meta:
        verbose_name = 'Global SEO settings'
        verbose_name_plural = 'Global SEO settings'

    def __str__(self):
        return 'Global SEO settings'

    def save(self, *args, **kwargs):
        # Enforce singleton: always use pk=1.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # Prevent deletion of the singleton row.

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CompetitorDomain(models.Model):
    domain = models.CharField(max_length=253, unique=True, verbose_name='Domain')
    label = models.CharField(max_length=200, blank=True, verbose_name='Label')
    active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        ordering = ['domain']
        verbose_name = 'Competitor domain'
        verbose_name_plural = 'Competitor domains'

    def __str__(self):
        return self.label or self.domain


class KeywordSeed(models.Model):
    keyword = models.CharField(max_length=500, verbose_name='Keyword')
    category = models.CharField(
        max_length=20,
        choices=KEYWORD_CATEGORY_CHOICES,
        verbose_name='Category',
    )
    active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        ordering = ['category', 'keyword']
        verbose_name = 'Keyword seed'
        verbose_name_plural = 'Keyword seeds'

    def __str__(self):
        return f'{self.keyword} ({self.get_category_display()})'


class SEOControlPanel(SEOGlobalSettings):
    """Proxy of SEOGlobalSettings used solely to create the 'Control Panel'
    admin menu entry under the SEO Intelligence section."""

    class Meta:
        proxy = True
        verbose_name = 'Control Panel'
        verbose_name_plural = 'Control Panel'


# ---------------------------------------------------------------------------
# Analytics dashboard proxy models — each creates one admin menu entry
# ---------------------------------------------------------------------------

class SearchConsoleDashboard(SEOGlobalSettings):
    class Meta:
        proxy = True
        verbose_name = 'Search Console'
        verbose_name_plural = 'Search Console'


class InternalSearchDashboard(SEOGlobalSettings):
    class Meta:
        proxy = True
        verbose_name = 'Internal Search'
        verbose_name_plural = 'Internal Search'


class DeadURLAnalytics(SEOGlobalSettings):
    class Meta:
        proxy = True
        verbose_name = 'Dead URL Analytics'
        verbose_name_plural = 'Dead URL Analytics'


class CompetitorSERPAnalytics(SEOGlobalSettings):
    class Meta:
        proxy = True
        verbose_name = 'Competitor SERP'
        verbose_name_plural = 'Competitor SERP'


class ContentGapAnalytics(SEOGlobalSettings):
    class Meta:
        proxy = True
        verbose_name = 'Content Gaps'
        verbose_name_plural = 'Content Gaps'
