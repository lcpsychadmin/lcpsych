from django.db import models


class SearchConsoleQuery(models.Model):
    """A single row from the GSC Search Analytics API (query × page × date)."""

    query = models.CharField(max_length=500)
    page = models.URLField(max_length=2000)
    date = models.DateField()
    clicks = models.IntegerField(default=0)
    impressions = models.IntegerField(default=0)
    ctr = models.FloatField(default=0.0)
    position = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-date', '-clicks']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['query']),
            models.Index(fields=['page']),
            models.Index(fields=['-clicks']),
        ]
        unique_together = [('query', 'page', 'date')]
        verbose_name = 'Search Console query'
        verbose_name_plural = 'Search Console queries'

    def __str__(self):
        return f'"{self.query}" — {self.date} ({self.clicks} clicks)'


class InternalSearchQuery(models.Model):
    """A search term entered in the site's own search box."""

    term = models.CharField(max_length=500)
    timestamp = models.DateTimeField()
    user_agent = models.CharField(max_length=500, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['term']),
        ]
        verbose_name = 'Internal search query'
        verbose_name_plural = 'Internal search queries'

    def __str__(self):
        return f'"{self.term}" at {self.timestamp:%Y-%m-%d %H:%M}'


class DeadURLHit(models.Model):
    """A 404 hit recorded with referrer and user-agent for dead-link analysis."""

    url = models.CharField(max_length=2000)
    referrer = models.CharField(max_length=2000, null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    timestamp = models.DateTimeField()

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['url']),
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = 'Dead URL hit'
        verbose_name_plural = 'Dead URL hits'

    def __str__(self):
        return f'{self.url} at {self.timestamp:%Y-%m-%d %H:%M}'


class CompetitorSERPResult(models.Model):
    """A competitor's SERP listing captured for a given keyword."""

    keyword = models.CharField(max_length=500)
    competitor_url = models.URLField(max_length=2000)
    title = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    rank = models.IntegerField()
    timestamp = models.DateTimeField()

    class Meta:
        ordering = ['-timestamp', 'rank']
        indexes = [
            models.Index(fields=['keyword']),
            models.Index(fields=['-timestamp']),
            models.Index(fields=['rank']),
        ]
        verbose_name = 'Competitor SERP result'
        verbose_name_plural = 'Competitor SERP results'

    def __str__(self):
        return f'#{self.rank} {self.competitor_url} for "{self.keyword}"'


class CompetitorHit(models.Model):
    """A competitor URL detected in a live SERP for a given keyword."""

    keyword = models.CharField(max_length=500)
    competitor_domain = models.CharField(max_length=253)
    url = models.URLField(max_length=2000)
    title = models.CharField(max_length=500, blank=True)
    rank = models.IntegerField()
    timestamp = models.DateTimeField()

    class Meta:
        ordering = ['-timestamp', 'rank']
        indexes = [
            models.Index(fields=['keyword']),
            models.Index(fields=['competitor_domain']),
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = 'Competitor hit'
        verbose_name_plural = 'Competitor hits'

    def __str__(self):
        return f'{self.competitor_domain} #{self.rank} for "{self.keyword}"'


class ContentGapRecord(models.Model):
    """A keyword gap: topics competitors rank for that LC Psych does not."""

    keyword = models.CharField(max_length=500)
    search_volume = models.IntegerField(default=0)
    competitor_presence = models.BooleanField(default=False)
    lcpsych_presence = models.BooleanField(default=False)
    recommended_action = models.TextField(blank=True)
    resolved = models.BooleanField(
        default=False,
        help_text="Mark when the recommended action has been taken.",
    )
    ignored = models.BooleanField(
        default=False,
        help_text="Dismiss this gap as not relevant.",
    )
    timestamp = models.DateTimeField()

    class Meta:
        ordering = ['-timestamp', '-search_volume']
        indexes = [
            models.Index(fields=['keyword']),
            models.Index(fields=['-search_volume']),
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = 'Content gap record'
        verbose_name_plural = 'Content gap records'

    def __str__(self):
        presence = 'gap' if not self.lcpsych_presence else 'covered'
        return f'"{self.keyword}" ({presence}, vol {self.search_volume})'


class SerpRawResult(models.Model):
    """Raw SerpApi JSON response stored per keyword run."""

    keyword = models.CharField(max_length=500)
    payload = models.JSONField(
        help_text="Full SerpApi response JSON for this keyword.",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['keyword']),
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = 'SERP raw result'
        verbose_name_plural = 'SERP raw results'

    def __str__(self):
        return f'"{self.keyword}" at {self.timestamp:%Y-%m-%d %H:%M}'


class LCPsychHit(models.Model):
    """A position where LC Psych itself appeared in a live SERP."""

    keyword = models.CharField(max_length=500)
    url = models.URLField(max_length=2000)
    title = models.CharField(max_length=500, blank=True)
    rank = models.IntegerField()
    timestamp = models.DateTimeField()

    class Meta:
        ordering = ['-timestamp', 'rank']
        indexes = [
            models.Index(fields=['keyword']),
            models.Index(fields=['-timestamp']),
            models.Index(fields=['rank']),
        ]
        verbose_name = 'LC Psych SERP hit'
        verbose_name_plural = 'LC Psych SERP hits'

    def __str__(self):
        return f'Rank #{self.rank} — {self.url} for "{self.keyword}"'


class KeywordSuggestion(models.Model):
    """
    A keyword phrase discovered from PAA or related searches during a SERP run.
    Candidates for promotion into active KeywordSeed records.
    """

    PAA = 'paa'
    RELATED = 'related'
    SOURCE_TYPE_CHOICES = [
        (PAA, 'People Also Ask'),
        (RELATED, 'Related Search'),
    ]

    source_keyword = models.CharField(max_length=500)
    suggestion = models.CharField(max_length=500, unique=True)
    source_type = models.CharField(
        max_length=10,
        choices=SOURCE_TYPE_CHOICES,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    used_as_seed = models.BooleanField(
        default=False,
        help_text='True once this suggestion has been promoted to a KeywordSeed.',
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['source_type']),
            models.Index(fields=['used_as_seed']),
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = 'Keyword suggestion'
        verbose_name_plural = 'Keyword suggestions'

    def __str__(self):
        return f'[{self.source_type}] {self.suggestion}'


class KeywordScore(models.Model):
    """
    Computed priority score for a keyword, updated each time
    ``score_keywords`` runs.  ``priority_score`` is 0–100.
    """

    keyword = models.CharField(max_length=500, unique=True)
    search_demand_score = models.IntegerField(default=0)
    competitor_pressure_score = models.IntegerField(default=0)
    lcpsych_presence_score = models.IntegerField(default=0)
    local_intent_score = models.IntegerField(default=0)
    commercial_intent_score = models.IntegerField(default=0)
    priority_score = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority_score']
        indexes = [
            models.Index(fields=['-priority_score']),
            models.Index(fields=['keyword']),
        ]
        verbose_name = 'Keyword score'
        verbose_name_plural = 'Keyword scores'

    def __str__(self):
        return f'"{self.keyword}" — priority {self.priority_score}'


class CompetitorCrawl(models.Model):
    """Persisted crawl snapshot for one competitor domain.

    One row per domain — updated in-place on each fresh crawl so the table
    stays small while always holding the most-recent data.
    """

    domain = models.CharField(max_length=253, unique=True, db_index=True)
    crawled_at = models.DateTimeField()
    page_count = models.IntegerField(default=0)
    pages = models.JSONField(default=list)

    class Meta:
        ordering = ['domain']
        verbose_name = 'Competitor crawl'
        verbose_name_plural = 'Competitor crawls'

    def __str__(self):
        return f'{self.domain} — {self.page_count} pages @ {self.crawled_at:%Y-%m-%d %H:%M}'


class DirectoryProfile(models.Model):
    """Scraped directory listing for one (domain, platform) pair.

    One row per (domain, platform) — upserted on each fresh scan so storage
    stays bounded. ``data`` holds all platform-specific scraped fields as JSON.
    """

    PLATFORM_GBP = 'gbp'
    PLATFORM_PT = 'psychology_today'
    PLATFORM_TD = 'therapyden'
    PLATFORM_ZD = 'zocdoc'
    PLATFORM_ALMA = 'alma'

    PLATFORM_CHOICES = [
        (PLATFORM_GBP,  'Google Business Profile'),
        (PLATFORM_PT,   'Psychology Today'),
        (PLATFORM_TD,   'TherapyDen'),
        (PLATFORM_ZD,   'ZocDoc'),
        (PLATFORM_ALMA, 'Alma'),
    ]

    competitor_domain = models.CharField(max_length=253, db_index=True)
    platform = models.CharField(max_length=30, choices=PLATFORM_CHOICES, db_index=True)
    data = models.JSONField(default=dict)
    crawled_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('competitor_domain', 'platform')]
        ordering = ['competitor_domain', 'platform']
        verbose_name = 'Directory profile'
        verbose_name_plural = 'Directory profiles'

    def __str__(self):
        return f'{self.competitor_domain} — {self.get_platform_display()}'


class SocialProfile(models.Model):
    """Scraped social media presence for one (domain, platform) pair.

    One row per (domain, platform) — upserted on each fresh scan.
    ``data`` holds all platform-specific scraped fields as JSON.
    """

    PLATFORM_FB = 'facebook'
    PLATFORM_IG = 'instagram'
    PLATFORM_TT = 'tiktok'
    PLATFORM_YT = 'youtube'

    PLATFORM_CHOICES = [
        (PLATFORM_FB, 'Facebook'),
        (PLATFORM_IG, 'Instagram'),
        (PLATFORM_TT, 'TikTok'),
        (PLATFORM_YT, 'YouTube'),
    ]

    competitor_domain = models.CharField(max_length=253, db_index=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, db_index=True)
    data = models.JSONField(default=dict)
    crawled_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('competitor_domain', 'platform')]
        ordering = ['competitor_domain', 'platform']
        verbose_name = 'Social profile'
        verbose_name_plural = 'Social profiles'

    def __str__(self):
        return f'{self.competitor_domain} — {self.get_platform_display()}'
