from django import template


register = template.Library()


@register.filter(name="has_group")
def has_group(user, group_name: str) -> bool:
    try:
        return bool(user.is_authenticated and user.groups.filter(name=group_name).exists())
    except Exception:
        return False


@register.filter(name="get_item")
def get_item(dictionary, key):
    """Allow dict[key] lookups in templates: {{ my_dict|get_item:key }}"""
    return dictionary.get(key, [])
