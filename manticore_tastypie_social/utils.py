from django.core.exceptions import ImproperlyConfigured
import requests
import urllib
import urllib2
from celery.task import task
from django.conf import settings
from twython import Twython
from manticore_tastypie_social.manticore_tastypie_social.resources import TagResource, FollowResource, \
    AirshipTokenResource, NotificationSettingResource, SocialProviderResource, FollowUserResource, \
    FollowingUsersResource, UserFollowersResource, FacebookFriendsResource, SocialSignUpResource, \
    UserSocialAuthenticationResource


# Registers this library's resources
def register_api(api):
    api.register(TagResource())
    api.register(FollowResource())
    api.register(FollowUserResource())
    api.register(FollowingUsersResource())
    api.register(UserFollowersResource())
    api.register(AirshipTokenResource())
    api.register(NotificationSettingResource())
    api.register(SocialProviderResource())
    api.register(FacebookFriendsResource())
    api.register(SocialSignUpResource())
    api.register(UserSocialAuthenticationResource())
    return api


def post_to_facebook(app_access_token, user_social_auth, message, link):
    url = "https://graph.facebook.com/%s/feed" % user_social_auth.uid

    params = {
        'access_token': app_access_token,
        'message': message,
        'link': link
    }

    req = urllib2.Request(url, urllib.urlencode(params))
    urllib2.urlopen(req)


def post_to_facebook_og(app_access_token, user_social_auth, obj):
    og_info = obj.facebook_og_info()

    url = "https://graph.facebook.com/{0}/{1}:{2}".format(
        user_social_auth.uid,
        settings.FACEBOOK_OG_NAMESPACE,
        og_info['action'],
    )

    params = {
        '{0}'.format(og_info['object']): '{0}'.format(og_info['url']),
        'access_token': app_access_token,
    }

    requests.post(url, params=params)


@task
def post_social_media(user_social_auth, social_obj_pk):
    obj = get_social_model().objects.get(pk=social_obj_pk)
    message = obj.create_social_message(user_social_auth.provider)
    link = obj.url()

    if user_social_auth.provider == 'facebook':
        if settings.USE_FACEBOOK_OG:
            social_model = get_social_model()
            social_object = social_model.objects.get(pk=obj.pk)
            post_to_facebook_og(settings.FACEBOOK_APP_ACCESS_TOKEN, user_social_auth, social_object)
        else:
            post_to_facebook(settings.FACEBOOK_APP_ACCESS_TOKEN, user_social_auth, message, link)
    elif user_social_auth.provider == 'twitter':
        twitter = Twython(
            app_key=settings.SOCIAL_AUTH_TWITTER_KEY,
            app_secret=settings.SOCIAL_AUTH_TWITTER_SECRET,
            oauth_token=user_social_auth.tokens['oauth_token'],
            oauth_token_secret=user_social_auth.tokens['oauth_token_secret']
        )

        full_message_url = "{0} {1}".format(message, link)

        # 140 characters minus the length of the link minus the space minus 3 characters for the ellipsis
        message_trunc = 140 - len(link) - 1 - 3

        # Truncate the message if the message + url is over 140
        safe_message = ("{0}... {1}".format(message[:message_trunc], link)) if len(full_message_url) > 140 else full_message_url
        twitter.update_status(status=safe_message, wrap_links=True)


def get_social_model():
    """
    Returns the social model that is active in this project.
    """
    from django.db.models import get_model

    try:
        app_label, model_name = settings.SOCIAL_MODEL.split('.')
    except ValueError:
        raise ImproperlyConfigured("SOCIAL_MODEL must be of the form 'app_label.model_name'")
    social_model = get_model(app_label, model_name)
    if social_model is None:
        raise ImproperlyConfigured("SOCIAL_MODEL refers to model '%s' that has not been installed" % settings.SOCIAL_MODEL)
    return social_model