from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import User
from billing.serializers import ChargeResponseSerializer, ChargeSerializer
from billing.services import create_charge_transaction, get_user_balance
from sms.serializers import ErrorResponseSerializer


class ChargeView(APIView):
    @extend_schema(
        request=ChargeSerializer,
        responses={
            200: ChargeResponseSerializer,
            400: OpenApiResponse(
                response=ErrorResponseSerializer, description="Invalid charge request"
            ),
            404: OpenApiResponse(response=ErrorResponseSerializer, description="User not found"),
        },
        description="Increase a user's balance and return the updated total.",
    )
    def post(self, request):
        serializer = ChargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data["user_id"]
        amount = serializer.validated_data["amount"]
        user = get_object_or_404(User, id=user_id)

        try:
            create_charge_transaction(user=user, amount=amount)
            total_balance = get_user_balance(user=user)
            return Response(
                {"user_id": user.id, "total_balance": total_balance},
                status=status.HTTP_200_OK,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
