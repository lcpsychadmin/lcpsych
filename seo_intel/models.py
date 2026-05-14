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
