from rest_framework import serializers


class ChargeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)


class ChargeResponseSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    total_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
