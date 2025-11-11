from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.serializers import ChargeSerializer
from billing.services import create_charge_transaction, get_user_balance


class ChargeView(APIView):
    def post(self, request):
        serializer = ChargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        amount = serializer.validated_data["amount"]

        try:
            create_charge_transaction(user=user, amount=amount)
            total_balance = get_user_balance(user=user)
            return Response(
                {"user_id": user.id, "total_balance": total_balance},
                status=status.HTTP_200_OK,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
