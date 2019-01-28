from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import MessageIncoming, MessageOutgoing, Blacklist, Attachment

MESSAGE_LIST_DISPLAY = ["date", "subj", "msg_envelope_sender", "msg_envelope_recipient"]
MESSAGE_FIELDS = [("msg_envelope_sender", "msg_from_email"),
        ("msg_envelope_recipient", "msg_date"), "msg_subject",
        "msg_text", "msg_html", "attachments"]

#===============================================================================
class MessageOutgoingAdmin(admin.ModelAdmin):
    list_display = MESSAGE_LIST_DISPLAY

    fields = MESSAGE_FIELDS + ["sent"]
            
    readonly_fields = ("msg_date", "sent")
    
    def response_change(self, request, obj):
        if "_send_email" in request.POST:
            obj._send()
            messages.add_message(request, messages.INFO, 'Message Sent')
        return super().response_change(request, obj)

#===============================================================================
class MessageIncomingAdmin(admin.ModelAdmin):
    list_display = MESSAGE_LIST_DISPLAY + ["forward_to"]
            
    fields = [("event_event_id", "event_timestamp", "event_esp_event")] + MESSAGE_FIELDS + [("forward_to", "forwarded")]
            
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def response_change(self, request, obj):
        if "_reply" in request.POST:
            # Clicking reply will only fill in the appropraite to/from, it will not copy the message over.
            return HttpResponseRedirect(
                    ("/admin/switchboard_operator/messageoutgoing/add/"
                    "?msg_envelope_sender=%s&msg_envelope_recipient=%s"
                    "&msg_from_email=%s&msg_subject=RE: %s")
                    %(obj.msg_envelope_recipient, obj.msg_envelope_sender, 
                    obj.msg_envelope_recipient, obj.msg_subject)
                    )
        return super().response_change(request, obj)

#===============================================================================
admin.site.register(MessageIncoming, MessageIncomingAdmin)
admin.site.register(MessageOutgoing, MessageOutgoingAdmin)
admin.site.register(Blacklist)
admin.site.register(Attachment)
