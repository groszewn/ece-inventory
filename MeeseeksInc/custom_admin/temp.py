                    try:
                        prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                    except (ObjectDoesNotExist, IndexError) as e:
                        prepend = ''
                    subject = prepend + 'Direct Dispersal'
                    to = [User.objects.get(username=recipient).email]
                    from_email='noreply@duke.edu'
                    ctx = {
                        'user':recipient,
                        'item':item_to_disburse.item_name,
                        'quantity':item_to_disburse.quantity, # shouldn't this be quantity given? so int(request.data.get('total_quantity'))
                        'type': 'disbursed',
                    }
                    message=render_to_string('inventory/belowthreshold_email.txt', ctx)
                    EmailMessage(subject, message, bcc=to, from_email=from_email).send() 