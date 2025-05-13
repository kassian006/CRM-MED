from .models import *
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'


class UserProfileRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name', 'email', 'phone_number','password']
        extra_kwargs={'password':{'write_only':True}}

    def create(self, validated_data):
        user=UserProfile.objects.create_user(**validated_data)
        return user

    def to_representation(self, instance):
        refresh = RefreshToken.for_user(instance)
        return {
            'user': {
                'email': instance.email,
            },
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }



class ReceptionRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Reception
        fields = ['first_name', 'last_name', 'email', 'phone_number','password']

    def create(self, validated_data):
        validated_data['role'] = 'reception'
        user = Reception.objects.create_user(**validated_data)
        return user

    def to_representation(self, instance):
        refresh = RefreshToken.for_user(instance)
        return {
            'user': {
                'email': instance.email,
                'role': instance.role,
            },
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }


class DoctorRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Doctor
        fields = ['first_name', 'last_name','speciality', 'medical_license', 'email', 'phone_number', 'password']
        # ВНИМАНИЕ: department здесь нет, как ты просил 'phone_number',

    def create(self, validated_data):
        validated_data['role'] = 'doctor'
        user = Doctor.objects.create_user(**validated_data)
        return user

    def to_representation(self, instance):
        refresh = RefreshToken.for_user(instance)
        return {
            'user': {
                'email': instance.email,
                'role': instance.role,
            },
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }


class LoginSerializers(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(**data)
        if user and user.is_active:
            # 👇 ВОТ ЭТО главное: возвращаем словарь, а не просто user
            return {
                'user': user
            }
        raise serializers.ValidationError("Неверные учетные данные")

    def to_representation(self, validated_data):
        user = validated_data['user']  # теперь тут всё как надо
        refresh = RefreshToken.for_user(user)
        return {
            'user': {
                'email': user.email,
                'role': user.role,  # можно добавить больше инфы, если надо
            },
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, data):
        self.token = data['refresh']
        return data

    def save(self, **kwargs):
        try:
            token = RefreshToken(self.token)
            token.blacklist()
        except Exception as e:
            raise serializers.ValidationError({'detail': 'Недействительный или уже отозванный токен'})



class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'


class SpecialitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Speciality
        fields = '__all__'


class ReceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reception
        fields = '__all__'


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = '__all__'


class DoctorServicesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorServices
        fields = '__all__'


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = '__all__'


class CustomerRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerRecord
        fields = '__all__'


class HistoryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoryRecord
        fields = '__all__'


class PriceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceList
        fields = '__all__'


class AnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Analytics
        fields = '__all__'
