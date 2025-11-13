from rest_framework import status
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import User
from billing.exceptions import InsufficientFundsError
from sms.filters import SMSReportFilterSet
from sms.models import SMS
from sms.serializers import SendSMSSerializer, SMSReportSerializer
from sms.services import create_sms_and_deduct_balance, send_sms


class SendSMSView(APIView):
    def post(self, request):
        serializer = SendSMSSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        user = get_object_or_404(User, id=validated_data["user_id"])
        try:
            sms = create_sms_and_deduct_balance(
                user=user,
                content=validated_data["content"],
                receiver=validated_data["receiver"],
                is_express=validated_data["is_express"],
            )
            task = send_sms(sms)
            response_payload = {
                "sms_id": sms.id,
                "task_id": task.id,
            }
            return Response(response_payload, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except InsufficientFundsError:
            return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)


class SMSReportView(ListAPIView):
    serializer_class = SMSReportSerializer
    queryset = SMS.objects.all()
    filterset_class = SMSReportFilterSet
