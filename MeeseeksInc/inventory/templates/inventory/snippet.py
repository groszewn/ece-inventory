class APIDenyBackfill(APIView):
    """
    Deny a backfill with optional notes.
    """
    permission_classes = (IsAdminOrManager,)
    serializer_class = BackfillAcceptDenySerializer
    
    def get_object(self, pk):
        try:
            return Loan.objects.get(loan_id=pk)
        except Loan.DoesNotExist:
            raise Http404
        
    def put(self, request, pk, format=None):
        loan = self.get_object(pk)
        if not loan.backfill_status=='Requested':
            return Response("Already approved or denied.", status=status.HTTP_400_BAD_REQUEST)
        serializer = BackfillAcceptDenySerializer(loan, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(backfill_status="Denied", backfill_time_requested=timezone.localtime(timezone.now()))
            Log.objects.create(request_id='', item_id=loan.item_name.item_id, item_name = loan.item_name.item_name, initiating_user=request.user, nature_of_event="Deny", 
                       affected_user=loan.user_name, change_occurred="Backfill denied")
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Backfill Request Denied'
            to = [User.objects.get(username=loan.user_name).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':loan.user_name,
                'reason':serializer.data['backfill_notes'],
            }
            for user in SubscribedUsers.objects.all():
                to.append(user.email)
            message=render_to_string('inventory/backfill_deny_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)