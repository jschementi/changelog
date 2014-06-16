import sendgrid

SENDGRID_USERNAME=None
SENDGRID_PASSWORD=None

email_subject_prefix = ''

def set_config(username, password, subject_prefix):
    global SENDGRID_USERNAME
    global SENDGRID_PASSWORD
    global email_subject_prefix
    if username is not None:
        SENDGRID_USERNAME = username
    if password is not None:
        SENDGRID_PASSWORD = password
    if subject_prefix is not None:
        email_subject_prefix = subject_prefix

def send_email(subject, html, text, from_addr, to_addrs, cc_addrs=[], bcc_addrs=[]):
    sg = sendgrid.SendGridClient(SENDGRID_USERNAME, SENDGRID_PASSWORD, raise_errors=True)
    message = sendgrid.Mail()
    message.set_subject("%s%s" % (email_subject_prefix, subject))
    message.set_html(html)
    message.set_text(text)
    message.set_from(from_addr)
    for addr in to_addrs:
        message.add_to(addr)
    for addr in cc_addrs:
        message.add_cc(addr)
    for addr in bcc_addrs:
        message.add_bcc(addr)
    sg.send(message)
