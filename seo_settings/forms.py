from __future__ import annotations

import re
from urllib.parse import urlparse

from django import forms

from .models import CompetitorDomain, KeywordSeed, SEOGlobalSettings


# ---------------------------------------------------------------------------
# SEOGlobalSettingsForm
# ---------------------------------------------------------------------------

class SEOGlobalSettingsForm(forms.ModelForm):
    """Form for the singleton SEOGlobalSettings model.

    Validation rules
    ----------------
    * ``google_private_key``       — must be PEM-formatted when provided;
                                     escaped ``\\n`` sequences are normalised
                                     to real newlines before saving.
    * ``url_removal_token``        — 8–255 characters when provided.
    * ``search_console_property_url`` — must use http/https scheme and have a
                                        non-empty netloc when provided.
    * Cross-field: if any Search Console module is enabled the three GSC
                   credential fields become required.

    Helper static methods
    ----------------------
    * ``test_google_credentials(settings)``        — OAuth2 token probe.
    * ``test_search_console_connection(settings)`` — GSC site-list check.
    """

    class Meta:
        model = SEOGlobalSettings
        fields = [
            'enable_search_console',
            'enable_internal_search_tracking',
            'enable_dead_url_logging',
            'enable_competitor_scraping',
            'enable_gap_analysis',
            'search_console_property_url',
            'url_removal_token',
        ]
        widgets = {
            'search_console_property_url': forms.URLInput(attrs={'style': 'width: 400px;'}),
            'url_removal_token': forms.TextInput(attrs={'style': 'width: 300px;'}),
        }

    # ── Field-level validators ────────────────────────────────────────

    def clean_url_removal_token(self):
        token = self.cleaned_data.get('url_removal_token', '').strip()
        if token:
            if len(token) < 8:
                raise forms.ValidationError(
                    'Token must be at least 8 characters long.'
                )
            if len(token) > 255:
                raise forms.ValidationError(
                    'Token must be 255 characters or fewer.'
                )
        return token

    def clean_search_console_property_url(self):
        url = self.cleaned_data.get('search_console_property_url', '').strip()
        if not url:
            return url
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise forms.ValidationError(
                'Search Console property URL must begin with http:// or https://.'
            )
        if not parsed.netloc:
            raise forms.ValidationError(
                'Enter a valid URL including the domain, '
                'e.g. https://www.lcpsych.com/'
            )
        return url

    def clean(self):
        cleaned = super().clean()
        # Cross-field: Search Console enablement requires the property URL.
        if cleaned.get('enable_search_console'):
            if not cleaned.get('search_console_property_url'):
                self.add_error(
                    'search_console_property_url',
                    'This field is required when Search Console is enabled.',
                )
        return cleaned

    # ── Helper methods ────────────────────────────────────────────────

    @staticmethod
    def test_google_credentials(settings_instance: SEOGlobalSettings) -> dict:
        """Probe Google OAuth2 using the saved service-account credentials.

        Returns ``{'success': True, 'message': '…'}`` or
        ``{'success': False, 'error': '…'}``.
        """
        client_email = settings_instance.google_client_email.strip()
        private_key = settings_instance.google_private_key.replace('\\n', '\n').strip()

        if not client_email or not private_key:
            return {
                'success': False,
                'error': 'No credentials configured — save a service-account '
                         'email and private key first.',
            }

        try:
            import google.auth.transport.requests as g_requests  # type: ignore
            from google.oauth2 import service_account  # type: ignore

            creds = service_account.Credentials.from_service_account_info(
                {
                    'type': 'service_account',
                    'private_key': private_key,
                    'client_email': client_email,
                    'token_uri': 'https://oauth2.googleapis.com/token',
                },
                scopes=['https://www.googleapis.com/auth/webmasters.readonly'],
            )
            creds.refresh(g_requests.Request())
            return {
                'success': True,
                'message': f'Token obtained successfully for {client_email}.',
            }
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    @staticmethod
    def test_search_console_connection(settings_instance: SEOGlobalSettings) -> dict:
        """Verify that the configured property URL appears in the GSC site list.

        First calls ``test_google_credentials``; if that fails the same error
        is returned without making a second network request.

        Returns ``{'success': True, 'message': '…'}`` or
        ``{'success': False, 'error': '…'}``.
        """
        cred_result = SEOGlobalSettingsForm.test_google_credentials(settings_instance)
        if not cred_result['success']:
            return cred_result

        property_url = settings_instance.search_console_property_url.strip()
        if not property_url:
            return {
                'success': False,
                'error': 'No Search Console property URL configured.',
            }

        client_email = settings_instance.google_client_email.strip()
        private_key = settings_instance.google_private_key.replace('\\n', '\n').strip()

        try:
            from google.oauth2 import service_account  # type: ignore
            from googleapiclient.discovery import build  # type: ignore

            creds = service_account.Credentials.from_service_account_info(
                {
                    'type': 'service_account',
                    'private_key': private_key,
                    'client_email': client_email,
                    'token_uri': 'https://oauth2.googleapis.com/token',
                },
                scopes=['https://www.googleapis.com/auth/webmasters.readonly'],
            )
            service = build('searchconsole', 'v1', credentials=creds)
            site_list = service.sites().list().execute()
            site_urls = [
                s.get('siteUrl', '')
                for s in site_list.get('siteEntry', [])
            ]
            # Normalise trailing slash for comparison.
            normalised = property_url.rstrip('/') + '/'
            match = any(
                u.rstrip('/') + '/' == normalised
                for u in site_urls
            )
            if match:
                return {
                    'success': True,
                    'message': f'Property "{property_url}" is accessible.',
                }
            available = ', '.join(site_urls) if site_urls else 'none'
            return {
                'success': False,
                'error': (
                    f'Property "{property_url}" was not found in this account. '
                    f'Available properties: {available}'
                ),
            }
        except Exception as exc:
            return {'success': False, 'error': str(exc)}


# ---------------------------------------------------------------------------
# CompetitorDomainForm
# ---------------------------------------------------------------------------

class CompetitorDomainForm(forms.ModelForm):
    """Form for adding/editing a CompetitorDomain.

    Automatically strips ``http://`` / ``https://`` prefixes and trailing
    slashes so that users can paste a full URL and still get a clean domain
    value stored.
    """

    class Meta:
        model = CompetitorDomain
        fields = ['domain', 'label', 'active']
        widgets = {
            'domain': forms.TextInput(attrs={
                'style': 'width: 340px;',
                'placeholder': 'e.g. competitor.com',
            }),
            'label': forms.TextInput(attrs={
                'style': 'width: 340px;',
                'placeholder': 'Optional friendly name',
            }),
        }

    def clean_domain(self):
        domain = self.cleaned_data.get('domain', '').strip().lower()
        # Strip common URL prefixes so users can paste a full URL.
        for prefix in ('https://', 'http://', 'www.'):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        # Remove trailing slash and path.
        domain = domain.split('/')[0].strip()
        if not domain:
            raise forms.ValidationError('Enter a domain name.')
        # Basic domain pattern check.
        if not re.match(r'^[a-z0-9][a-z0-9\-\.]{0,251}[a-z0-9]$', domain):
            raise forms.ValidationError(
                'Enter a valid domain name, e.g. competitor.com'
            )
        return domain


# ---------------------------------------------------------------------------
# KeywordSeedForm
# ---------------------------------------------------------------------------

class KeywordSeedForm(forms.ModelForm):
    """Form for adding/editing a KeywordSeed."""

    class Meta:
        model = KeywordSeed
        fields = ['keyword', 'category', 'active']
        widgets = {
            'keyword': forms.TextInput(attrs={'style': 'width: 400px;'}),
        }

    def clean_keyword(self):
        keyword = self.cleaned_data.get('keyword', '').strip()
        if not keyword:
            raise forms.ValidationError('Keyword cannot be blank.')
        if len(keyword) > 500:
            raise forms.ValidationError(
                'Keyword must be 500 characters or fewer.'
            )
        return keyword

