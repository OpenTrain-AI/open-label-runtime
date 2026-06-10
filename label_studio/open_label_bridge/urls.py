from django.urls import path

from . import views

app_name = 'open_label_bridge'

urlpatterns = [
    path('open-label/launch', views.launch, name='open-label-launch'),
    path('open-label/bridge/projects', views.BridgeProjectCreateAPI.as_view(), name='open-label-bridge-projects'),
]
