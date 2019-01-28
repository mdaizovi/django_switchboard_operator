Django Switchboard Operator
=====

Django Switchboard Operator is a simple Django app to receive, direct, send, and forward domain emails. 
It uses django-anymail to integrate with a selected Email Service Provider (ESP) such as SendGrid or Mailchimp.
You can then:

* receive emails
* auto-forward emails to designated email addresses
* send emails from your authenticated domain, using the django admin.
 
In other words, it's a way to send and receive *very basic* domain mail without paying for a G Suite or Zoho account. 
Please note, this app will allow you to send small attachments, and will forward them as well, but it will ignore inline attachments.
This package assumes you already have MEDIA_ROOT specified in your settings.

This package requires and assumes you have already installed django-anymail, and already have an account with a supported ESP.
It also requires django-cleanup, to delete files after attachments have been sent/forwarded.

This is my first pluggable django app that I made because I was tired of writing the same code in 3 of my own apps, 
but I make no promises re: your usage. In other words: Caveat Emptor. I have successfully used it with my django-anymail and my 
SendGrid account, with my 3 django apps running django 1.11.6, 2.0, and 2.0.1.

Quick start
-----------
1. Install `django-cleanup`, `django-anymail`, and get an account with a supported ESP, if you haven't already.

2. Clone or fork this repo

3. Edit your project's ``settings.py``:

   .. code-block:: python

        INSTALLED_APPS = [
            # ...
            "switchboard_operator"
            # ...
        ]

        # If you want to automatically forward emails to another address
        # *@domain.com will forward all for domain, 
        # a specific address will forward only emails to that address, for the domain.
        MAIL_FORWARD_MAP = {"*@example.com":"my_personal_address@gmail.com", 
            "only_this_email_address@example.com":"my_personal_address@gmail.com",
        }
        # Your authenticated email domains to send mail from
        SENDER_ADDRESSES =["my_emaill_address@example.com", "another_one@example.com"]      

4. Run ``python manage.py migrate`` to create the switchboard_operator models.


Troubleshooting
-----------
1. If the django admin does not have the "Send" button for MessageOutgoing object, ensure you have set APP_DIRS to True:

   .. code-block:: python

   TEMPLATES = [
       {
            # ...
           'APP_DIRS': True,
       },
   ]
