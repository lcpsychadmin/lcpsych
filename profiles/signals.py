from django.contrib.auth import get_user_model
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from blog.models import Post
from profiles.models import TherapistProfile


@receiver(pre_delete, sender=TherapistProfile)
def handle_therapist_delete(sender, instance: TherapistProfile, **kwargs):
    """
    When deleting a therapist profile, delete the associated user account and
    reassign that user's blog posts to a fallback author to avoid data loss.
    Fallback strategy:
      1) First user who is in both "admin" and "therapist" groups (excluding the user being deleted)
      2) Any superuser (excluding the user being deleted)
      3) Any staff user (excluding the user being deleted)
    If no fallback is found, the user is left intact to avoid deleting posts.
    """

    user = getattr(instance, "user", None)
    if not user:
        return

    User = get_user_model()

    fallback = (
        User.objects.exclude(pk=user.pk)
        .filter(groups__name="admin")
        .filter(groups__name="therapist")
        .first()
        or User.objects.exclude(pk=user.pk).filter(is_superuser=True).first()
        or User.objects.exclude(pk=user.pk).filter(is_staff=True).first()
    )

    if fallback:
        Post.objects.filter(author=user).update(author=fallback)
        user.delete()
    # If no fallback exists, keep the user so blog posts remain intact.
