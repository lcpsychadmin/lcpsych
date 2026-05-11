from django.db import models


class GeoState(models.Model):
    slug = models.SlugField(unique=True, help_text="URL-safe identifier, e.g. 'kentucky'")
    name = models.CharField(max_length=100, help_text="Display name, e.g. 'Kentucky'")
    abbreviation = models.CharField(max_length=2, help_text="Two-letter postal code, e.g. 'KY'")
    # SEO fields
    seo_title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Full <title> tag value. Leave blank for auto-generated default.",
    )
    seo_description = models.CharField(
        max_length=300,
        blank=True,
        help_text="Meta description (aim for ≤160 chars). Leave blank for auto-generated default.",
    )
    hero_heading = models.CharField(
        max_length=200,
        blank=True,
        help_text="H1 text displayed on the page. Leave blank to use the state name.",
    )
    hero_subheading = models.TextField(
        blank=True,
        help_text="Intro paragraph beneath the H1.",
    )
    og_image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Absolute URL to the Open Graph / social share image.",
    )
    hero_image = models.ImageField(
        upload_to="geo/states/",
        blank=True,
        null=True,
        help_text="Hero background image displayed on the state landing page.",
    )
    offers_in_office = models.BooleanField(
        default=True,
        help_text="In-office appointments are available in this state.",
    )
    offers_telehealth = models.BooleanField(
        default=True,
        help_text="Telehealth appointments are available in this state.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this state from the site without deleting it.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "State"
        verbose_name_plural = "States"

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


class GeoLocation(models.Model):
    CITY = "city"
    COUNTY = "county"
    LOCATION_TYPES = [(CITY, "City"), (COUNTY, "County")]

    state = models.ForeignKey(
        GeoState,
        on_delete=models.CASCADE,
        related_name="locations",
    )
    county = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cities",
        limit_choices_to={"location_type": "county"},
        help_text="The county this city belongs to (cities only).",
    )
    slug = models.SlugField(
        help_text="URL-safe identifier, e.g. 'florence' or 'boone-county'",
    )
    name = models.CharField(max_length=100, help_text="Display name, e.g. 'Florence' or 'Boone County'")
    location_type = models.CharField(
        max_length=10,
        choices=LOCATION_TYPES,
        help_text="Whether this entry is a city or a county.",
    )
    # SEO fields
    seo_title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Full <title> tag value. Leave blank for auto-generated default.",
    )
    seo_description = models.CharField(
        max_length=300,
        blank=True,
        help_text="Meta description (aim for ≤160 chars). Leave blank for auto-generated default.",
    )
    hero_heading = models.CharField(
        max_length=200,
        blank=True,
        help_text="H1 text displayed on the page. Leave blank for auto-generated default.",
    )
    hero_subheading = models.TextField(
        blank=True,
        help_text="Intro paragraph beneath the H1.",
    )
    og_image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Absolute URL to the Open Graph / social share image.",
    )
    hero_image = models.ImageField(
        upload_to="geo/locations/",
        blank=True,
        null=True,
        help_text="Hero background image displayed on this location's page.",
    )
    offers_in_office = models.BooleanField(
        default=True,
        help_text="In-office appointments are available in this location.",
    )
    offers_telehealth = models.BooleanField(
        default=True,
        help_text="Telehealth appointments are available in this location.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this location from the site without deleting it.",
    )

    class Meta:
        ordering = ["name"]
        unique_together = [("state", "slug")]
        verbose_name = "Location (City / County)"
        verbose_name_plural = "Locations (Cities / Counties)"

    def __str__(self):
        return f"{self.name}, {self.state.abbreviation} ({self.get_location_type_display()})"

    def get_url_path(self) -> str:
        """
        Returns the canonical URL path for this location.
        Cities assigned to a county use the 3-segment hierarchy:
          /<state>/<county>/<city>/
        All other locations (counties, unassigned cities) use:
          /<state>/<location>/
        """
        if self.location_type == self.CITY and self.county_id:
            return f"/{self.state.slug}/{self.county.slug}/{self.slug}/"
        return f"/{self.state.slug}/{self.slug}/"


class GeoRegion(models.Model):
    """
    A flexible grouping of states and/or locations that forms a named region
    (e.g. "Greater Cincinnati Area").  Regions are displayed as first-class
    geographic entities at /regions/<slug>/ and their sub-pages.

    Therapists/services available in a region are the union of availability
    across all associated states and locations.
    """

    slug = models.SlugField(
        unique=True,
        help_text="URL-safe identifier, e.g. 'greater-cincinnati'",
    )
    name = models.CharField(
        max_length=100,
        help_text="Display name, e.g. 'Greater Cincinnati Area'",
    )
    seo_title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Full <title> tag value. Leave blank for auto-generated default.",
    )
    seo_description = models.CharField(
        max_length=300,
        blank=True,
        help_text="Meta description (aim for ≤160 chars). Leave blank for auto-generated default.",
    )
    og_image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Absolute URL to the Open Graph / social share image.",
    )
    hero_image = models.ImageField(
        upload_to="geo/regions/",
        blank=True,
        null=True,
        help_text="Hero background image displayed on this region's page.",
    )
    states = models.ManyToManyField(
        GeoState,
        blank=True,
        related_name="regions",
        help_text="States that are part of this region.",
    )
    locations = models.ManyToManyField(
        GeoLocation,
        blank=True,
        related_name="regions",
        help_text="Cities and counties that are part of this region.",
    )
    offices = models.ManyToManyField(
        "core.OfficeLocation",
        blank=True,
        related_name="regions",
        help_text="Physical offices that serve this region.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this region from the site without deleting it.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Region"
        verbose_name_plural = "Regions"

    def __str__(self):
        return self.name

    def get_url_path(self) -> str:
        return f"/regions/{self.slug}/"


class GeoContentBlock(models.Model):
    """
    A single heading + body content block attached to either a state or a location.
    Use the 'order' field to control display sequence.
    """

    state = models.ForeignKey(
        GeoState,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="content_blocks",
    )
    location = models.ForeignKey(
        GeoLocation,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="content_blocks",
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Lower numbers appear first.",
    )
    heading = models.CharField(max_length=200, help_text="H2 section heading")
    body = models.TextField(help_text="Paragraph text for this section")

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.heading
