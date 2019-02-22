import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db import models
from django.dispatch import receiver
from django.template.defaultfilters import filesizeformat
from django.utils import timezone

from anymail.signals import inbound

def get_domain(email_address_str):
    addy_list = str(email_address_str).split("@")
    domain = addy_list[1]
    return domain

def get_wildcard_domains():
    wildcards = []
    recipient_domains = settings.MAIL_FORWARD_MAP.keys()
    for e in recipient_domains:
        addy_list = e.split("@")
        if addy_list[0] == "*":
            wildcards.append(addy_list[1])    
    return wildcards

try:
    SETTINGS_SENDER_ADDRESSES = settings.SENDER_ADDRESSES
except:
    SETTINGS_SENDER_ADDRESSES = []


#===============================================================================
class Blacklist(models.Model):
    """Blacklist of senders to ignore. We don't make MessageEvents from their messages.
    """
    email = models.EmailField(max_length=70, null=True, blank=True)
    domain = models.CharField(max_length=100, null=True, blank=True)

    #---------------------------------------------------------------------------
    def __str__(self):
        return (self.email or self.domain)

    #---------------------------------------------------------------------------
    def clean(self):
        if not self.email and not self.domain:
            raise ValidationError("Please supply an email or domain" )
        elif self.email and self.domain:
            raise ValidationError("Please supply an email OR domain; not both" )

    #---------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        self.full_clean()
        super(Blacklist, self).save(*args, **kwargs)

#===============================================================================
class Attachment(models.Model):
    """Attachments in emails, for sending and forwarding.
    After send, deletes.
    """
    name = models.CharField(max_length=100, blank=True)
    upload = models.FileField(upload_to='uploads/%Y/%m/%d/')

    #---------------------------------------------------------------------------
    def __str__(self):
        return (self.name)
        
    #---------------------------------------------------------------------------
    def clean(self):
        if self.upload.size > 26214400:
            raise ValidationError(('Please keep filesize under 25 Megabytes. Current filesize: %s'
                    % (filesizeformat(self.upload.size))))
        if not self.name:
            self.name = self.upload.name
        
    #---------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        self.full_clean()
        super(Attachment, self).save(*args, **kwargs)


#===============================================================================
class MessageEvent(models.Model):
    """Abstract Base Class that is later inherited by MessageOutgoing and MessageIncoming, 
    to receive and forward incoming mail from Anymail, 
    or send basic messages from the Django admin. 
    """

    msg_envelope_sender = models.EmailField(max_length=70)
    msg_envelope_recipient = models.EmailField(max_length=70)    
    
    msg_from_email = models.CharField(max_length=70)
    msg_from_email_addr_spec = models.EmailField(max_length=100, null=True, blank=True)
    msg_from_email_display_name = models.CharField(max_length=100, null=True, blank=True)
    msg_from_email_domain = models.CharField(max_length=100, null=True, blank=True)
    msg_from_email_username = models.CharField(max_length=100, null=True, blank=True)
    
    msg_subject = models.CharField(max_length=100, null=True, blank=True)
    msg_date = models.DateTimeField(null=True, blank=True)
    msg_text = models.TextField(null=True, blank=True)
    msg_html = models.TextField(null=True, blank=True)
    
    attachments = models.ManyToManyField(Attachment, blank=True)

    #---------------------------------------------------------------------------
    def __str__(self):
        return ("%s (%s to %s) %s" % (self.subj, 
                                self.msg_envelope_sender,
                                self.msg_envelope_recipient,
                                self.date.strftime('%c'))
                                )
        
    #---------------------------------------------------------------------------
    class Meta:
        ordering = ['-msg_date']
        abstract = True
            
    #---------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.msg_date:
            self.msg_date = timezone.now()
        super(MessageEvent, self).save(*args, **kwargs) 

    #---------------------------------------------------------------------------        
    @property
    def subj(self):
        if len(self.msg_subject) > 30:      
            short_subject = ("%s..." % (self.msg_subject[:30]))
        else:
            short_subject = self.msg_subject 
        return short_subject       
    
    #---------------------------------------------------------------------------
    def _send(self, **kwargs):
        """Sends MessageEvent Object."""
            
        if kwargs is not None:
            if "subject" in kwargs:
                subject = kwargs.get("subject")
            else:
                subject = self.msg_subject
            if "recipient" in kwargs:
                recipient = kwargs.get("recipient")
            else:
                recipient = str(self.msg_envelope_recipient)

        message_text = str(self.msg_text)
        if self.msg_html:    
            email = EmailMultiAlternatives(
                    subject=subject,
                    body=message_text,
                    to=[recipient],
                    from_email=str(self.msg_envelope_sender),
                    reply_to=[str(self.msg_envelope_sender)]
                    ) 
            email.attach_alternative(str(self.msg_html), "text/html")
        else: # no HTML, just text
            email = EmailMessage(
                    subject=subject,
                    body = message_text,
                    from_email=str(self.msg_envelope_sender),
                    to=[recipient],
                    reply_to=[str(self.msg_envelope_sender)]
                    )
                    
        if self.attachments.count() > 0:
            for a in self.attachments.all():
                path_list =  settings.BASE_DIR.split(os.sep)[1:] + a.upload.url.split(os.sep)[1:]
                file_full_url = os.path.join(os.sep, *path_list)
                email.attach_file(file_full_url) 

        email.send(fail_silently=False)
        
        if hasattr(self, "sent"):
            self.sent = timezone.now()
        else:
            self.forwarded = timezone.now()
        self.save()

        for a in self.attachments.all():
            a.delete()       
        
        return True
          
#-------------------------------------------------------------------------------
@receiver(inbound)
def handle_inbound(sender, event, esp_name, **kwargs):
    """Very basic mail forwarding. Passes on attachents, but ignores inline attachments."""
    
    event_message = event.message
    
    blacklisted_domains = Blacklist.objects.all().exclude(domain=None).values_list('domain', flat=True)
    blacklisted_emails = Blacklist.objects.all().exclude(email=None).values_list('email', flat=True)
    message_domain = get_domain(str(event_message.from_email))
    if (str(event_message.from_email) in blacklisted_emails) or (message_domain in blacklisted_domains):
        print("%s is Blacklisted."%(str(event_message.from_email)))
        return False
    elif not event_message.from_email or (str(event_message.from_email) == "":
        print("No from email provided. Dismissing email to " + str(event_message.envelope_recipient))
        return False        

    me, created =  MessageIncoming.objects.get_or_create(event_event_id=event.event_id, 
            event_timestamp=event.timestamp,
            event_esp_event=event.esp_event,
            msg_envelope_sender=str(event_message.envelope_sender),
            msg_envelope_recipient=str(event_message.envelope_recipient),
            msg_subject=str(event_message.subject),
            msg_text=event_message.text,
            msg_html=event_message.html)
    if event_message.date:
        me.msg_date = event_message.date
    else:
        me.msg_date = timezone.now()
    # Don't forward again if message already exists.
    if not created:
        return 
    
    me.msg_from_email = event_message.from_email
    if event_message.from_email:
        me.msg_from_email_addr_spec = event_message.from_email.addr_spec
        me.msg_from_email_display_name = event_message.from_email.display_name 
        me.msg_from_email_domain = event_message.from_email.domain
        me.msg_from_email_username = event_message.from_email.username

    # Attachment and file will be deleted after message is sent.
    for a in event_message.attachments:
        a_obj, __ = Attachment.objects.get_or_create(name=a.get_filename(), upload=a.as_uploaded_file())
        me.attachments.add(a_obj)
        
    me.forward_to = me.get_forwarding_email()
    if me.forward_to:
        me._forward()
    
    me.save()
    
    return True
    
#===============================================================================
class MessageOutgoing(MessageEvent):
    SENDER_ADDRESSES = SETTINGS_SENDER_ADDRESSES
    
    sent = models.DateTimeField(null=True, blank=True)            
    
    #---------------------------------------------------------------------------
    @property
    def date(self):
        date = self.sent or self.msg_date
        return date            
                
    #---------------------------------------------------------------------------
    @property
    def can_send(self):
        if self.pk and not self.sent:
            return True                               

    #---------------------------------------------------------------------------                
    def clean(self):
        if str(self.msg_envelope_sender) not in self.SENDER_ADDRESSES:
            raise ValidationError("You cannot send mail from this email address" )

    #---------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        self.full_clean()
        super(MessageOutgoing, self).save(*args, **kwargs)                
                
#===============================================================================
class MessageIncoming(MessageEvent):
    """Wrapper around Anymail's inbound events, for sending and forwarding messages.
    Assumes you've already installed anymail and ESP such as SendGrid.
    Ignores inline attachments.
    """    
    
    # event_... will only have values if was received by ESP, and even then, probably not.
    event_event_id = models.CharField(max_length=100, null=True, blank=True)
    event_timestamp = models.DateTimeField(null=True, blank=True)
    event_esp_event = models.CharField(max_length=100, null=True, blank=True)
    
    # Forward fields will only have data if it was received by inbound parse and then forwarded.
    forward_to = models.EmailField(max_length=70, null=True, blank=True)
    forwarded = models.DateTimeField(null=True, blank=True)

    #---------------------------------------------------------------------------
    @property
    def date(self):
        date = self.event_timestamp or self.forwarded or self.msg_date
        return date

    #---------------------------------------------------------------------------
    def get_forwarding_email(self):
        """Returms email to forward the message to, or None."""
        forward_to = None
        intended = str(self.msg_envelope_recipient)
        
        if self.forward_to:
            return self.forward_to
        else:
            WILDCARD_DOMAINS = get_wildcard_domains()
            domain = get_domain(intended)
            if domain in WILDCARD_DOMAINS:
                forward_to = settings.MAIL_FORWARD_MAP.get(("*@" + domain))
            elif intended in settings.MAIL_FORWARD_MAP.keys():
                forward_to = settings.MAIL_FORWARD_MAP.get((intended))   
        return forward_to

    #---------------------------------------------------------------------------
    def _forward(self, **kwargs):
        """Forwards MessageIncoming Object, if it hasn't been sent already."""
        if self.forwarded:
            print("MessageIncoming %s has already been forwarded"%(str(self.pk)))
            return
        elif not self.forward_to:
            print("MessageIncoming %s does not have a destination to be forwarded to"%(str(self.pk)))
            return            
        
        subject = ("FWD to %s: %s"%(str(self.msg_envelope_recipient), self.msg_subject))    
        self._send(subject=subject, recipient=str(self.forward_to))
