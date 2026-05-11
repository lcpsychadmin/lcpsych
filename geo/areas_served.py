"""
Single source of truth for all geographic areas served by L+C Psychological Services.

To add a new state, city, or county:
  1. Add an entry to the appropriate dict below.
  2. No code changes are needed — routes, metadata, schema, and sitemaps are all
     generated automatically from this file.

Structure
---------
AREAS_SERVED: dict[state_slug, StateConfig]

StateConfig keys
~~~~~~~~~~~~~~~~
  name          : str  — Display name, e.g. "Kentucky"
  abbreviation  : str  — Two-letter postal code, e.g. "KY"
  seo           : SeoConfig (optional overrides per location)
  content_blocks: list[ContentBlock]
  counties      : dict[county_slug, LocationConfig]
  cities        : dict[city_slug,   LocationConfig]

SeoConfig keys (all optional — sensible defaults are generated from name/state)
~~~~~~~~~~~~~~~
  title_template   : str — Full <title> tag value
  meta_description : str — Meta description (≤160 chars)
  hero_heading     : str — H1 text on the page
  hero_subheading  : str — Intro paragraph beneath the H1
  og_image_url     : str — Absolute URL to social share image

ContentBlock keys
~~~~~~~~~~~~~~~~~
  heading : str — H2 section heading
  body    : str — Paragraph text for that section
"""

from __future__ import annotations
from typing import TypedDict


class SeoConfig(TypedDict, total=False):
    title_template: str
    meta_description: str
    hero_heading: str
    hero_subheading: str
    og_image_url: str


class ContentBlock(TypedDict):
    heading: str
    body: str


class LocationConfig(TypedDict, total=False):
    name: str
    seo: SeoConfig
    content_blocks: list[ContentBlock]


class StateConfig(TypedDict, total=False):
    name: str
    abbreviation: str
    seo: SeoConfig
    content_blocks: list[ContentBlock]
    counties: dict[str, LocationConfig]
    cities: dict[str, LocationConfig]


AREAS_SERVED: dict[str, StateConfig] = {

    # =========================================================================
    # KENTUCKY — primary market (main office in Florence, KY)
    # =========================================================================
    "kentucky": {
        "name": "Kentucky",
        "abbreviation": "KY",
        "seo": {
            "title_template": "Therapists in Kentucky | L+C Psychological Services",
            "meta_description": (
                "Find compassionate therapists in Kentucky at L+C Psychological Services. "
                "We serve Florence, Covington, Lexington, and communities across the "
                "Bluegrass State via telehealth and in person."
            ),
            "hero_heading": "Therapy in Kentucky",
            "hero_subheading": (
                "L+C Psychological Services provides compassionate, evidence-based mental "
                "health care to clients across Kentucky — from our Northern Kentucky home "
                "base to communities statewide."
            ),
        },
        "content_blocks": [
            {
                "heading": "Mental Health Services Across Kentucky",
                "body": (
                    "Our Kentucky-licensed therapists provide individual therapy, couples "
                    "counseling, family therapy, and psychological assessment. Whether you "
                    "are in the Cincinnati metro, Lexington, or a rural community, we offer "
                    "flexible telehealth appointments so geography never stands between you "
                    "and quality care."
                ),
            },
            {
                "heading": "Who We Serve in Kentucky",
                "body": (
                    "We work with adults, teens, and children facing anxiety, depression, "
                    "trauma, relationship challenges, ADHD, and more. Our multilingual team "
                    "and inclusive approach means we welcome clients of all backgrounds, "
                    "identities, and lived experiences."
                ),
            },
            {
                "heading": "Insurance & Telehealth",
                "body": (
                    "L+C Psych accepts most major insurance plans accepted in Kentucky, "
                    "including Anthem, Humana, Aetna, and Cigna. Telehealth sessions are "
                    "conducted via our secure HIPAA-compliant platform from any device."
                ),
            },
        ],
        "counties": {
            "boone-county": {
                "name": "Boone County",
                "seo": {
                    "title_template": "Therapists in Boone County, KY | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services serves Boone County, KY including Florence, "
                        "Burlington, Union, and surrounding communities. Schedule telehealth or "
                        "in-person therapy today."
                    ),
                    "hero_heading": "Therapy in Boone County, Kentucky",
                    "hero_subheading": (
                        "Serving Florence, Burlington, Union, Walton, and the greater Boone County "
                        "community with compassionate, evidence-based mental health care."
                    ),
                },
                "content_blocks": [
                    {
                        "heading": "Mental Health Care in Boone County",
                        "body": (
                            "Boone County is home to L+C Psych's main office in Florence, "
                            "making us ideally positioned to serve the county's growing population. "
                            "We offer in-person and telehealth appointments for individuals, "
                            "couples, and families."
                        ),
                    },
                    {
                        "heading": "Convenient In-Person Access",
                        "body": (
                            "Our Florence office at 6900 Houston Rd. is centrally located within "
                            "Boone County, with easy access from I-75 and US-42. Ample parking "
                            "and flexible scheduling make fitting therapy into your life simple."
                        ),
                    },
                ],
            },
            "kenton-county": {
                "name": "Kenton County",
                "seo": {
                    "title_template": "Therapists in Kenton County, KY | L+C Psychological Services",
                    "meta_description": (
                        "Find licensed therapists in Kenton County, KY — including Covington, "
                        "Erlanger, Edgewood, and Ft. Mitchell — at L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Kenton County, Kentucky",
                    "hero_subheading": (
                        "Serving Covington, Erlanger, Edgewood, Fort Mitchell, and the full "
                        "Kenton County community with expert mental health support."
                    ),
                },
                "content_blocks": [
                    {
                        "heading": "Counseling Services Throughout Kenton County",
                        "body": (
                            "From Covington's vibrant riverfront neighborhood to Erlanger and "
                            "Edgewood, our therapists are ready to support Kenton County residents "
                            "with anxiety, depression, trauma, and relationship challenges."
                        ),
                    },
                ],
            },
            "campbell-county": {
                "name": "Campbell County",
                "seo": {
                    "title_template": "Therapists in Campbell County, KY | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services provides therapy in Campbell County, KY "
                        "including Newport, Fort Thomas, Cold Spring, and Alexandria."
                    ),
                    "hero_heading": "Therapy in Campbell County, Kentucky",
                    "hero_subheading": (
                        "Serving Newport, Fort Thomas, Cold Spring, Alexandria, and communities "
                        "throughout Campbell County with compassionate mental health care."
                    ),
                },
                "content_blocks": [
                    {
                        "heading": "Mental Health Support in Campbell County",
                        "body": (
                            "Campbell County residents have access to L+C Psych's full range of "
                            "mental health services, including individual therapy, couples "
                            "counseling, and child and adolescent care."
                        ),
                    },
                ],
            },
            "grant-county": {
                "name": "Grant County",
                "seo": {
                    "title_template": "Therapists in Grant County, KY | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Grant County, KY residents including Williamstown "
                        "and Dry Ridge from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Grant County, Kentucky",
                    "hero_subheading": (
                        "Bringing quality mental health care to Williamstown, Dry Ridge, and "
                        "Grant County through convenient telehealth sessions."
                    ),
                },
                "content_blocks": [],
            },
            "pendleton-county": {
                "name": "Pendleton County",
                "seo": {
                    "title_template": "Therapists in Pendleton County, KY | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Pendleton County, KY residents including Falmouth "
                        "from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Pendleton County, Kentucky",
                    "hero_subheading": (
                        "Reaching Falmouth and all of Pendleton County with evidence-based "
                        "telehealth mental health services."
                    ),
                },
                "content_blocks": [],
            },
            "scott-county": {
                "name": "Scott County",
                "seo": {
                    "title_template": "Therapists in Scott County, KY | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Scott County, KY including Georgetown from "
                        "L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Scott County, Kentucky",
                    "hero_subheading": (
                        "Connecting Georgetown and Scott County residents with compassionate "
                        "telehealth mental health services."
                    ),
                },
                "content_blocks": [],
            },
            "fayette-county": {
                "name": "Fayette County",
                "seo": {
                    "title_template": "Therapists in Fayette County, KY | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services offers telehealth therapy to Fayette County, "
                        "KY including Lexington."
                    ),
                    "hero_heading": "Therapy in Fayette County, Kentucky",
                    "hero_subheading": (
                        "Serving Lexington and Fayette County with expert telehealth mental "
                        "health care from L+C Psychological Services."
                    ),
                },
                "content_blocks": [],
            },
        },
        "cities": {
            "florence": {
                "name": "Florence",
                "seo": {
                    "title_template": "Therapists in Florence, KY | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services is located in Florence, KY. We offer "
                        "in-person and telehealth therapy for anxiety, depression, trauma, "
                        "and more. Same-week appointments available."
                    ),
                    "hero_heading": "Therapy in Florence, Kentucky",
                    "hero_subheading": (
                        "Our Florence, KY office makes quality mental health care accessible "
                        "to Boone County residents and the Greater Cincinnati area."
                    ),
                },
                "content_blocks": [
                    {
                        "heading": "In-Person & Telehealth Therapy in Florence",
                        "body": (
                            "L+C Psychological Services' main office is located in Florence, KY "
                            "at 6900 Houston Rd., Building 500, Suite 11. We welcome scheduled "
                            "appointments for individuals, couples, children, and families, and "
                            "offer telehealth for clients who prefer to meet from home."
                        ),
                    },
                    {
                        "heading": "What We Treat",
                        "body": (
                            "Our Florence-based clinicians specialize in anxiety disorders, "
                            "depression, ADHD, trauma and PTSD, OCD, grief, relationship "
                            "difficulties, life transitions, and more."
                        ),
                    },
                ],
            },
            "covington": {
                "name": "Covington",
                "seo": {
                    "title_template": "Therapists in Covington, KY | L+C Psychological Services",
                    "meta_description": (
                        "Find compassionate therapists serving Covington, KY at L+C Psychological "
                        "Services. Telehealth and in-person options available."
                    ),
                    "hero_heading": "Therapy in Covington, Kentucky",
                    "hero_subheading": (
                        "Serving Covington's MainStrasse and Licking Riverside neighborhoods "
                        "with flexible telehealth and in-person therapy."
                    ),
                },
                "content_blocks": [],
            },
            "newport": {
                "name": "Newport",
                "seo": {
                    "title_template": "Therapists in Newport, KY | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services provides therapy for Newport, KY residents. "
                        "Get matched with a licensed therapist today."
                    ),
                    "hero_heading": "Therapy in Newport, Kentucky",
                    "hero_subheading": (
                        "Compassionate mental health support for Newport, KY individuals, "
                        "couples, and families."
                    ),
                },
                "content_blocks": [],
            },
            "erlanger": {
                "name": "Erlanger",
                "seo": {
                    "title_template": "Therapists in Erlanger, KY | L+C Psychological Services",
                    "meta_description": (
                        "Therapy services for Erlanger, KY from L+C Psychological Services. "
                        "Telehealth and in-person appointments available."
                    ),
                    "hero_heading": "Therapy in Erlanger, Kentucky",
                    "hero_subheading": (
                        "Connecting Erlanger residents with experienced, compassionate "
                        "therapists near you."
                    ),
                },
                "content_blocks": [],
            },
            "fort-thomas": {
                "name": "Fort Thomas",
                "seo": {
                    "title_template": "Therapists in Fort Thomas, KY | L+C Psychological Services",
                    "meta_description": (
                        "Find licensed therapists in Fort Thomas, KY with L+C Psychological "
                        "Services. Flexible scheduling and most insurance accepted."
                    ),
                    "hero_heading": "Therapy in Fort Thomas, Kentucky",
                    "hero_subheading": (
                        "Dedicated mental health care for Fort Thomas, KY families, teens, "
                        "and individuals."
                    ),
                },
                "content_blocks": [],
            },
            "independence": {
                "name": "Independence",
                "seo": {
                    "title_template": "Therapists in Independence, KY | L+C Psychological Services",
                    "meta_description": (
                        "Therapy for Independence, KY residents with L+C Psychological Services. "
                        "Telehealth appointments available."
                    ),
                    "hero_heading": "Therapy in Independence, Kentucky",
                    "hero_subheading": (
                        "Bringing quality mental health services to Independence, KY and "
                        "surrounding Kenton County communities."
                    ),
                },
                "content_blocks": [],
            },
            "union": {
                "name": "Union",
                "seo": {
                    "title_template": "Therapists in Union, KY | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services serves Union, KY with telehealth and "
                        "in-person therapy options."
                    ),
                    "hero_heading": "Therapy in Union, Kentucky",
                    "hero_subheading": (
                        "Quality mental health care for Union, KY residents and families."
                    ),
                },
                "content_blocks": [],
            },
            "burlington": {
                "name": "Burlington",
                "seo": {
                    "title_template": "Therapists in Burlington, KY | L+C Psychological Services",
                    "meta_description": (
                        "Find therapists in Burlington, KY serving Boone County with "
                        "L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Burlington, Kentucky",
                    "hero_subheading": (
                        "Accessible, compassionate mental health services for Burlington "
                        "and greater Boone County."
                    ),
                },
                "content_blocks": [],
            },
            "crescent-springs": {
                "name": "Crescent Springs",
                "seo": {
                    "title_template": "Therapists in Crescent Springs, KY | L+C Psychological Services",
                    "meta_description": (
                        "Therapy for Crescent Springs, KY residents from L+C Psychological "
                        "Services. In-person and telehealth options available."
                    ),
                    "hero_heading": "Therapy in Crescent Springs, Kentucky",
                    "hero_subheading": (
                        "Expert mental health care close to home for Crescent Springs, KY "
                        "residents."
                    ),
                },
                "content_blocks": [],
            },
            "edgewood": {
                "name": "Edgewood",
                "seo": {
                    "title_template": "Therapists in Edgewood, KY | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services offers therapy to Edgewood, KY residents "
                        "via telehealth and in-person appointments."
                    ),
                    "hero_heading": "Therapy in Edgewood, Kentucky",
                    "hero_subheading": (
                        "Quality, compassionate mental health services for Edgewood, KY "
                        "individuals and families."
                    ),
                },
                "content_blocks": [],
            },
            "cold-spring": {
                "name": "Cold Spring",
                "seo": {
                    "title_template": "Therapists in Cold Spring, KY | L+C Psychological Services",
                    "meta_description": (
                        "Find licensed therapists serving Cold Spring, KY at L+C Psychological "
                        "Services. Flexible scheduling and most insurance plans accepted."
                    ),
                    "hero_heading": "Therapy in Cold Spring, Kentucky",
                    "hero_subheading": (
                        "Supporting Cold Spring, KY residents with evidence-based mental "
                        "health services."
                    ),
                },
                "content_blocks": [],
            },
            "lexington": {
                "name": "Lexington",
                "seo": {
                    "title_template": "Therapists in Lexington, KY | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services offers telehealth therapy to Lexington, "
                        "KY clients. Connect with a licensed therapist from home."
                    ),
                    "hero_heading": "Telehealth Therapy in Lexington, Kentucky",
                    "hero_subheading": (
                        "L+C Psych's telehealth platform connects Lexington residents with "
                        "experienced, compassionate therapists across Kentucky."
                    ),
                },
                "content_blocks": [
                    {
                        "heading": "Therapy From Anywhere in Lexington",
                        "body": (
                            "Our Lexington-area clients benefit from secure, HIPAA-compliant "
                            "telehealth sessions that fit any schedule. Morning, evening, and "
                            "weekend appointments are available."
                        ),
                    },
                ],
            },
            "georgetown": {
                "name": "Georgetown",
                "seo": {
                    "title_template": "Therapists in Georgetown, KY | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Georgetown, KY from L+C Psychological Services. "
                        "Get matched with a licensed therapist today."
                    ),
                    "hero_heading": "Therapy in Georgetown, Kentucky",
                    "hero_subheading": (
                        "Quality mental health services available to Georgetown, KY residents "
                        "through convenient telehealth appointments."
                    ),
                },
                "content_blocks": [],
            },
            "nicholasville": {
                "name": "Nicholasville",
                "seo": {
                    "title_template": "Therapists in Nicholasville, KY | L+C Psychological Services",
                    "meta_description": (
                        "Find licensed therapists for Nicholasville, KY at L+C Psychological "
                        "Services. Telehealth appointments available."
                    ),
                    "hero_heading": "Therapy in Nicholasville, Kentucky",
                    "hero_subheading": (
                        "Connecting Nicholasville residents with compassionate telehealth "
                        "mental health services."
                    ),
                },
                "content_blocks": [],
            },
        },
    },

    # =========================================================================
    # OHIO — secondary market (telehealth across OH; proximity to Cincinnati)
    # =========================================================================
    "ohio": {
        "name": "Ohio",
        "abbreviation": "OH",
        "seo": {
            "title_template": "Therapists in Ohio | L+C Psychological Services",
            "meta_description": (
                "L+C Psychological Services provides telehealth therapy to Ohio residents. "
                "Our licensed therapists serve Cincinnati, Dayton, Columbus, and communities "
                "throughout Ohio."
            ),
            "hero_heading": "Therapy in Ohio",
            "hero_subheading": (
                "Ohio residents can access L+C Psych's full range of mental health services "
                "via telehealth. Our Ohio-licensed therapists are ready to help."
            ),
        },
        "content_blocks": [
            {
                "heading": "Telehealth Therapy for Ohio Residents",
                "body": (
                    "L+C Psychological Services holds Ohio licenses and provides telehealth "
                    "mental health services to adults, teens, and children throughout the state. "
                    "No commute required — sessions are available evenings and weekends."
                ),
            },
            {
                "heading": "What We Treat",
                "body": (
                    "Our Ohio-licensed therapists specialize in anxiety, depression, trauma, "
                    "ADHD, OCD, relationship challenges, grief, and life transitions. We serve "
                    "individuals, couples, and families."
                ),
            },
        ],
        "counties": {
            "hamilton-county": {
                "name": "Hamilton County",
                "seo": {
                    "title_template": "Therapists in Hamilton County, OH | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Hamilton County, OH including Cincinnati, Blue Ash, "
                        "and Montgomery from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Hamilton County, Ohio",
                    "hero_subheading": (
                        "Serving Cincinnati and Hamilton County with expert telehealth mental "
                        "health services."
                    ),
                },
                "content_blocks": [],
            },
            "warren-county": {
                "name": "Warren County",
                "seo": {
                    "title_template": "Therapists in Warren County, OH | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Warren County, OH including Mason, Lebanon, and "
                        "Springboro from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Warren County, Ohio",
                    "hero_subheading": (
                        "Connecting Mason, Lebanon, Springboro, and Warren County residents "
                        "with quality mental health care."
                    ),
                },
                "content_blocks": [],
            },
            "butler-county": {
                "name": "Butler County",
                "seo": {
                    "title_template": "Therapists in Butler County, OH | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services offers telehealth therapy to Butler County, "
                        "OH including Hamilton, Fairfield, and Middletown."
                    ),
                    "hero_heading": "Therapy in Butler County, Ohio",
                    "hero_subheading": (
                        "Telehealth mental health services for Hamilton, Fairfield, Middletown, "
                        "and all of Butler County."
                    ),
                },
                "content_blocks": [],
            },
            "montgomery-county": {
                "name": "Montgomery County",
                "seo": {
                    "title_template": "Therapists in Montgomery County, OH | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Montgomery County, OH including Dayton, Kettering, "
                        "and Miamisburg from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Montgomery County, Ohio",
                    "hero_subheading": (
                        "Serving Dayton, Kettering, Miamisburg, and Montgomery County with "
                        "accessible telehealth mental health care."
                    ),
                },
                "content_blocks": [],
            },
            "clermont-county": {
                "name": "Clermont County",
                "seo": {
                    "title_template": "Therapists in Clermont County, OH | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Clermont County, OH including Milford and Batavia "
                        "from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Clermont County, Ohio",
                    "hero_subheading": (
                        "Serving Milford, Batavia, and Clermont County with telehealth mental "
                        "health services."
                    ),
                },
                "content_blocks": [],
            },
        },
        "cities": {
            "cincinnati": {
                "name": "Cincinnati",
                "seo": {
                    "title_template": "Therapists in Cincinnati, OH | L+C Psychological Services",
                    "meta_description": (
                        "Find licensed therapists serving Cincinnati, OH at L+C Psychological "
                        "Services. Telehealth appointments available for Ohio residents."
                    ),
                    "hero_heading": "Therapy in Cincinnati, Ohio",
                    "hero_subheading": (
                        "L+C Psych's telehealth platform connects Cincinnati residents with "
                        "compassionate, experienced therapists."
                    ),
                },
                "content_blocks": [
                    {
                        "heading": "Why Cincinnati Residents Choose L+C Psych",
                        "body": (
                            "Conveniently located just across the Ohio River in Florence, KY, "
                            "L+C Psych is a natural fit for Cincinnati-area clients. We offer "
                            "both telehealth and in-person sessions, making access easy whether "
                            "you live in Clifton, Hyde Park, or the suburbs."
                        ),
                    },
                ],
            },
            "dayton": {
                "name": "Dayton",
                "seo": {
                    "title_template": "Therapists in Dayton, OH | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services provides telehealth therapy to Dayton, OH "
                        "residents. Flexible scheduling and insurance accepted."
                    ),
                    "hero_heading": "Therapy in Dayton, Ohio",
                    "hero_subheading": (
                        "Connecting Dayton, OH residents with quality mental health services "
                        "through our secure telehealth platform."
                    ),
                },
                "content_blocks": [],
            },
            "mason": {
                "name": "Mason",
                "seo": {
                    "title_template": "Therapists in Mason, OH | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Mason, OH from L+C Psychological Services. "
                        "Get matched with a licensed therapist today."
                    ),
                    "hero_heading": "Therapy in Mason, Ohio",
                    "hero_subheading": (
                        "Quality mental health services for Mason, OH individuals and families."
                    ),
                },
                "content_blocks": [],
            },
            "west-chester": {
                "name": "West Chester",
                "seo": {
                    "title_template": "Therapists in West Chester, OH | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services offers telehealth therapy to West Chester, "
                        "OH residents."
                    ),
                    "hero_heading": "Therapy in West Chester, Ohio",
                    "hero_subheading": (
                        "Accessible, compassionate mental health care for West Chester, OH "
                        "residents."
                    ),
                },
                "content_blocks": [],
            },
            "fairfield": {
                "name": "Fairfield",
                "seo": {
                    "title_template": "Therapists in Fairfield, OH | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Fairfield, OH from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Fairfield, Ohio",
                    "hero_subheading": (
                        "Supporting Fairfield, OH with telehealth mental health services."
                    ),
                },
                "content_blocks": [],
            },
            "hamilton": {
                "name": "Hamilton",
                "seo": {
                    "title_template": "Therapists in Hamilton, OH | L+C Psychological Services",
                    "meta_description": (
                        "Find licensed therapists for Hamilton, OH at L+C Psychological Services. "
                        "Telehealth appointments available."
                    ),
                    "hero_heading": "Therapy in Hamilton, Ohio",
                    "hero_subheading": (
                        "Quality telehealth mental health care for Hamilton, OH residents."
                    ),
                },
                "content_blocks": [],
            },
            "middletown": {
                "name": "Middletown",
                "seo": {
                    "title_template": "Therapists in Middletown, OH | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services provides telehealth therapy to Middletown, "
                        "OH residents."
                    ),
                    "hero_heading": "Therapy in Middletown, Ohio",
                    "hero_subheading": (
                        "Compassionate telehealth mental health services for Middletown, OH "
                        "individuals and families."
                    ),
                },
                "content_blocks": [],
            },
            "springboro": {
                "name": "Springboro",
                "seo": {
                    "title_template": "Therapists in Springboro, OH | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Springboro, OH from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Springboro, Ohio",
                    "hero_subheading": (
                        "Connecting Springboro, OH residents with expert telehealth mental "
                        "health services."
                    ),
                },
                "content_blocks": [],
            },
            "kettering": {
                "name": "Kettering",
                "seo": {
                    "title_template": "Therapists in Kettering, OH | L+C Psychological Services",
                    "meta_description": (
                        "Find licensed therapists serving Kettering, OH at L+C Psychological "
                        "Services."
                    ),
                    "hero_heading": "Therapy in Kettering, Ohio",
                    "hero_subheading": (
                        "Quality telehealth mental health care for Kettering, OH residents."
                    ),
                },
                "content_blocks": [],
            },
        },
    },

    # =========================================================================
    # INDIANA — tertiary market (Southern Indiana / Louisville metro)
    # =========================================================================
    "indiana": {
        "name": "Indiana",
        "abbreviation": "IN",
        "seo": {
            "title_template": "Therapists in Indiana | L+C Psychological Services",
            "meta_description": (
                "L+C Psychological Services provides telehealth therapy to Indiana residents. "
                "Connect with a licensed therapist from anywhere in the state."
            ),
            "hero_heading": "Therapy in Indiana",
            "hero_subheading": (
                "Indiana residents can access L+C Psych's compassionate, evidence-based mental "
                "health services via telehealth."
            ),
        },
        "content_blocks": [
            {
                "heading": "Telehealth Therapy for Indiana Residents",
                "body": (
                    "Our Indiana-licensed therapists provide telehealth mental health services "
                    "throughout the state, including the Louisville metro area, Indianapolis, "
                    "and Southern Indiana communities."
                ),
            },
        ],
        "counties": {
            "clark-county": {
                "name": "Clark County",
                "seo": {
                    "title_template": "Therapists in Clark County, IN | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Clark County, IN including Jeffersonville and "
                        "Clarksville from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Clark County, Indiana",
                    "hero_subheading": (
                        "Serving Jeffersonville, Clarksville, and Clark County, IN with quality "
                        "telehealth mental health services."
                    ),
                },
                "content_blocks": [],
            },
            "floyd-county": {
                "name": "Floyd County",
                "seo": {
                    "title_template": "Therapists in Floyd County, IN | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Floyd County, IN including New Albany from "
                        "L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Floyd County, Indiana",
                    "hero_subheading": (
                        "Quality mental health services for New Albany and Floyd County, IN."
                    ),
                },
                "content_blocks": [],
            },
            "scott-county-in": {
                "name": "Scott County",
                "seo": {
                    "title_template": "Therapists in Scott County, IN | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Scott County, IN including Scottsburg from "
                        "L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Scott County, Indiana",
                    "hero_subheading": (
                        "Reaching Scottsburg and Scott County, IN with quality telehealth "
                        "mental health services."
                    ),
                },
                "content_blocks": [],
            },
        },
        "cities": {
            "jeffersonville": {
                "name": "Jeffersonville",
                "seo": {
                    "title_template": "Therapists in Jeffersonville, IN | L+C Psychological Services",
                    "meta_description": (
                        "L+C Psychological Services offers telehealth therapy to Jeffersonville, "
                        "IN residents."
                    ),
                    "hero_heading": "Therapy in Jeffersonville, Indiana",
                    "hero_subheading": (
                        "Telehealth mental health support for Jeffersonville, IN individuals "
                        "and families."
                    ),
                },
                "content_blocks": [],
            },
            "new-albany": {
                "name": "New Albany",
                "seo": {
                    "title_template": "Therapists in New Albany, IN | L+C Psychological Services",
                    "meta_description": (
                        "Find licensed therapists serving New Albany, IN at L+C Psychological "
                        "Services."
                    ),
                    "hero_heading": "Therapy in New Albany, Indiana",
                    "hero_subheading": (
                        "Compassionate mental health care for New Albany, IN residents and "
                        "families."
                    ),
                },
                "content_blocks": [],
            },
            "clarksville": {
                "name": "Clarksville",
                "seo": {
                    "title_template": "Therapists in Clarksville, IN | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Clarksville, IN from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Clarksville, Indiana",
                    "hero_subheading": (
                        "Quality telehealth mental health services for Clarksville, IN."
                    ),
                },
                "content_blocks": [],
            },
            "sellersburg": {
                "name": "Sellersburg",
                "seo": {
                    "title_template": "Therapists in Sellersburg, IN | L+C Psychological Services",
                    "meta_description": (
                        "Telehealth therapy for Sellersburg, IN from L+C Psychological Services."
                    ),
                    "hero_heading": "Therapy in Sellersburg, Indiana",
                    "hero_subheading": (
                        "Bringing quality mental health care to Sellersburg, IN via telehealth."
                    ),
                },
                "content_blocks": [],
            },
        },
    },
}
