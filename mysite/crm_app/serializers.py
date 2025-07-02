from .models import *
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from django.http import HttpResponse
import openpyxl
from django.db.models import Sum
from .models import Report

class VerifyLoginCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)  # если код 6-значный


class SendLoginCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()


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

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True)

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['department_name']


class SpecialitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Speciality
        fields = ['speciality_title']


class ReceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reception
        fields = '__all__'

class PaymentTypeNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['payment_type']


class DoctorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ['first_name', 'last_name']

class NameReceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reception
        fields = ['first_name', 'last_name']


class DoctorListSerializer(serializers.ModelSerializer):
    department_name = DepartmentSerializer(source='department', read_only=True)
    class Meta:
        model = Doctor
        fields = ['id', 'first_name', 'last_name', 'cabinet', 'department_name', 'phone_number']


class DoctorDetailSerializer(serializers.ModelSerializer):
    department_name = DepartmentSerializer(source='department', read_only=True)
    speciality = SpecialitySerializer()
    class Meta:
        model = Doctor
        fields = ['image', 'first_name', 'last_name', 'email', 'phone_number', 'department_name', 'speciality', 'bonus']


class DoctorCreateSerializer(serializers.ModelSerializer):
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all())
    speciality = serializers.PrimaryKeyRelatedField(queryset=Speciality.objects.all())

    class Meta:
        model = Doctor
        fields = ['first_name', 'last_name', 'image', 'department', 'speciality', 'phone_number', 'email', 'bonus', 'cabinet']

    def create(self, validated_data):
        # Extract nested data
        department = validated_data.pop('department', None)  # Already a Department instance or None
        speciality = validated_data.pop('speciality', None)  # Already a Speciality instance

        # Validate speciality (since it's required)
        if not speciality:
            raise serializers.ValidationError({"speciality": "This field is required."})

        # Create Doctor instance
        doctor = Doctor.objects.create(
            department=department,  # Use the Department instance directly
            speciality=speciality,  # Use the Speciality instance directly
            **validated_data
        )
        return doctor


class DoctorNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ['first_name', 'cabinet']


class DoctorServicesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorServices
        fields = '__all__'


class DoctorServicePriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorServices
        fields = ['price']


class DoctorSalarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorServices
        fields = ['salary_doctor']


class DoctorNameServicesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorServices
        fields = ['doctor_service']


class NameDoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ['first_name', 'last_name']


class HistoryRecordInfoPatSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoryRecord
        fields = ['record']


class PatientSerializer(serializers.ModelSerializer):
    # Используем SlugRelatedField для поиска по именам
    doctor_service = serializers.SlugRelatedField(
        slug_field='doctor_service',
        queryset=DoctorServices.objects.all()
    )
    department = serializers.SlugRelatedField(
        slug_field='department_name',
        queryset=Department.objects.all()
    )

    # Для врача и регистратора сложнее, так как у них несколько полей имени
    # Оставляем как есть для отображения, но добавляем поля для создания
    reception_display = NameReceptionSerializer(source='reception', read_only=True)
    doctor_display = DoctorNameSerializer(source='doctor', read_only=True)

    # Поля для создания по именам
    reception_first_name = serializers.CharField(write_only=True)
    reception_last_name = serializers.CharField(write_only=True, required=False)
    doctor_first_name = serializers.CharField(write_only=True)
    doctor_last_name = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Patient
        fields = [
            'id', 'full_name', 'phone_number', 'doctor_service', 'birthday',
            'department', 'reception_display', 'started_time', 'end_time',
            'gender_patient', 'doctor_display', 'status_patient',
            'reception_first_name', 'reception_last_name',
            'doctor_first_name', 'doctor_last_name'
        ]

    def create(self, validated_data):
        # Извлекаем данные для поиска врача и регистратора
        reception_first = validated_data.pop('reception_first_name')
        reception_last = validated_data.pop('reception_last_name', '')
        doctor_first = validated_data.pop('doctor_first_name')
        doctor_last = validated_data.pop('doctor_last_name', '')

        try:
            # Находим регистратора
            if reception_last:
                reception = Reception.objects.get(
                    first_name=reception_first,
                    last_name=reception_last
                )
            else:
                reception = Reception.objects.get(first_name=reception_first)

            # Находим врача
            if doctor_last:
                doctor = Doctor.objects.get(
                    first_name=doctor_first,
                    last_name=doctor_last
                )
            else:
                doctor = Doctor.objects.get(first_name=doctor_first)

            # Создаем пациента
            patient = Patient.objects.create(
                reception=reception,
                doctor=doctor,
                **validated_data
            )
            return patient

        except (Reception.DoesNotExist, Doctor.DoesNotExist) as e:
            raise serializers.ValidationError(f"Объект не найден: {str(e)}")

class PatientDesktopSerializer(serializers.ModelSerializer):
    created_date = serializers.DateTimeField(format="%m %d, %H:%M")
    payment = PaymentTypeNameSerializer(read_only=True)
    doctor_service = DoctorServicePriceSerializer()
    doctor = NameDoctorSerializer()

    class Meta:
        model = Patient
        fields = ['id', 'created_date', 'full_name', 'doctor', 'payment', 'doctor_service']


class MakeDoctorServicesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorServices
        fields = ['doctor_service', 'price']


class Make1DoctorServicesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorServices
        fields = ['doctor_service']


class Make2DoctorServicesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorServices
        fields = ['doctor_service', 'price']


class PriceDocSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorServices
        fields = ['doctor_service', 'price', 'discount']


# class MakeAppointmentInfoPatientSerializer(serializers.ModelSerializer):
#     reception = NameReceptionSerializer()
#     doctor = NameDoctorSerializer()
#     department = DepartmentSerializer()
#     doctor_service = MakeDoctorServicesSerializer()
#     class Meta:
#         model = Patient
#         fields = ['full_name', 'reception', 'doctor', 'started_time', 'end_time', 'status_patient', 'department', 'doctor_service']

class MakeAppointmentInfoPatientSerializer(serializers.ModelSerializer):
    reception = NameReceptionSerializer(write_only=True)
    doctor = NameDoctorSerializer(write_only=True)
    department = DepartmentSerializer(write_only=True)
    doctor_service = MakeDoctorServicesSerializer(write_only=True)
    birthday = serializers.DateField(format="%d.%m.%Y", input_formats=['%d.%m.%Y', '%Y-%m-%d'])

    class Meta:
        model = Patient
        fields = ['full_name', 'reception', 'doctor', 'started_time', 'end_time', 'status_patient', 'department', 'doctor_service', 'birthday']
        extra_kwargs = {
            'full_name': {'required': True},
            'started_time': {'required': True},
            'end_time': {'required': True},
            'status_patient': {'required': True},
            'department': {'required': True},
            'doctor_service': {'required': True},
            'birthday': {'required': True},
        }

    def create(self, validated_data):
        reception_id = validated_data.pop('reception', None)
        doctor_id = validated_data.pop('doctor', None)
        department_id = validated_data.pop('department', None)
        doctor_service_id = validated_data.pop('doctor_service', None)
        birthday = validated_data.pop('birthday')

        if not department_id:
            raise serializers.ValidationError({"department": "This field is required."})

        reception = Reception.objects.get(id=reception_id) if reception_id else None
        doctor = Doctor.objects.get(id=doctor_id) if doctor_id else None
        department = Department.objects.get(id=department_id) if department_id else None
        doctor_service = DoctorServices.objects.get(id=doctor_service_id) if doctor_service_id else None

        patient = Patient.objects.create(
            full_name=validated_data.get('full_name', ''),
            started_time=validated_data.get('started_time'),
            end_time=validated_data.get('end_time'),
            status_patient=validated_data.get('status_patient', 'Предзапись'),
            reception=reception,
            doctor=doctor,
            department=department,
            doctor_service=doctor_service,
            birthday=birthday
        )
        return patient



class CalendarSerializer(serializers.ModelSerializer):
    doctor = NameDoctorSerializer(read_only=True)
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    service_label = serializers.CharField(source='doctor_service.service_label', read_only=True)

    class Meta:
        model = Patient
        fields = ['started_time', 'end_time', 'appointment_date', 'status_patient', 'doctor', 'department_name', 'service_label', 'appointment_time']


class CalendarCreateSerializer(serializers.ModelSerializer):
    doctor = NameDoctorSerializer(write_only=True)
    department_name = serializers.CharField(source='department.department_name', write_only=True)
    service_label = serializers.CharField(source='doctor_service.service_label', write_only=True)
    appointment_time = serializers.TimeField(format="%H:%M:%S", input_formats=["%H:%M:%S"], required=False)

    class Meta:
        model = Patient
        fields = ['started_time', 'end_time', 'appointment_date', 'status_patient', 'doctor', 'department_name', 'service_label', 'appointment_time']


class HistoryRecordInfoPatientSerializer(serializers.ModelSerializer):
    reception = NameReceptionSerializer(read_only=True)
    doctor = NameDoctorSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    doctor_service = Make1DoctorServicesSerializer(read_only=True)
    patient_history = HistoryRecordInfoPatSerializer(read_only=True, many=True)

    class Meta:
        model = Patient
        fields = ['full_name', 'reception', 'doctor', 'appointment_date', 'department',
                  'doctor_service', 'patient_history']  # Убрано дублирование count_record, count_record_history


    # def get_count_record_history(self, obj):
    #     return obj.get_count_record_history()


class HistoryReceptionInfoPatientSerializer(serializers.ModelSerializer):
    reception = NameReceptionSerializer(read_only=True)  # Исправлено
    doctor = NameDoctorSerializer(read_only=True)  # Исправлено
    department = DepartmentSerializer(read_only=True)  # Исправлено
    doctor_service = Make1DoctorServicesSerializer(read_only=True)
    # patient_history = HistoryRecordInfoPatSerializer(read_only=True, many=True)
    patient_history_filtered = serializers.SerializerMethodField()  # Новое поле с фильтром
    appointment_date = serializers.DateField(format="%d.%m.%Y")

    class Meta:
        model = Patient
        fields = ['full_name', 'reception', 'doctor', 'appointment_date', 'department',
                  'doctor_service', 'patient_history_filtered']

    def get_patient_history_filtered(self, obj):
        filtered_history = obj.patient_history.filter(record='был в приеме')
        return HistoryRecordInfoPatSerializer(filtered_history, many=True).data


class PatientNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['full_name', 'gender_patient']


class PatientCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['full_name']


class PaymentSerializer(serializers.ModelSerializer):
    patient_detail = PatientNameSerializer(source='patient', read_only=True)
    doctor_detail = DoctorProfileSerializer(source='doctor', read_only=True)
    service_detail = DoctorServicesSerializer(source='service', read_only=True)
    class Meta:
        model = Payment
        fields = ['patient_detail', 'doctor_detail', 'service_detail', 'payment_type']


class HistoryRecordInfoPatientTotalSerializer(serializers.ModelSerializer):
    count_record = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = ['count_record']

    def get_count_record(self, obj):
            return obj.get_count_record()


class HistoryReceptionInfoPatientTotalSerializer(serializers.ModelSerializer):
    count_reception = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = ['count_reception']

    def get_count_reception(self, obj):
            return obj.get_count_reception()


class PaymentTypeNameSumSerializer(serializers.Serializer):
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
    cash = serializers.DecimalField(max_digits=10, decimal_places=2)
    card = serializers.DecimalField(max_digits=10, decimal_places=2)


class CustomerRecordSerializer(serializers.ModelSerializer):
    reception_detail = ReceptionSerializer(source='reception', read_only=True)
    patient_detail = PatientSerializer(source='patient', read_only=True)
    doctor_detail = DoctorProfileSerializer(source='doctor', read_only=True)
    department_detail = DepartmentSerializer(source='department', read_only=True)
    service_detail = DoctorServicesSerializer(source='service', read_only=True)
    doctor_ser = PriceDocSerializer(source='service', read_only=True)

    class Meta:
        model = CustomerRecord
        fields = ['reception_detail', 'patient_detail', 'doctor_detail', 'service_detail', 'department_detail', 'doctor_ser', 'change',
                  'payment_type', 'created_date', 'phone_number']


class CustRecordSerializer(serializers.ModelSerializer):
    doctor_ser = PriceDocSerializer()
    class Meta:
        model = CustomerRecord
        fields = ['doctor_ser', 'payment_type', 'created_date']


class CheckRecordSerializer(serializers.ModelSerializer):
    patient_name = PatientCheckSerializer(source='patient', read_only=True)
    doctor_name = DoctorNameSerializer(source='doctor', read_only=True)
    doctor_ser = DoctorNameServicesSerializer(read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, source='doctor_ser.price', read_only=True)
    payment_type = PaymentTypeNameSerializer()

    class Meta:
        model = CustomerRecord
        fields = ['patient_name', 'doctor_name', 'doctor_ser', 'price', 'change', 'payment_type']


class PaymentInfoPatientSerializer(serializers.ModelSerializer):
    doctor = NameDoctorSerializer(read_only=True)  # Исправлено
    department = DepartmentSerializer(read_only=True)  # Исправлено
    doctor_service = Make2DoctorServicesSerializer(read_only=True)
    payment_customer = PaymentTypeNameSerializer(source='payment', read_only=True)
    class Meta:
        model = Patient
        fields = ['full_name', 'doctor', 'appointment_date', 'department', 'doctor_service', 'payment_customer']


class InfoPatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['full_name', 'phone_number', 'gender_patient']


class PriceListSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)

    class Meta:
        model = PriceList
        fields = ['id', 'department']


class PriceDetailSerializer(serializers.ModelSerializer):
    service = Make2DoctorServicesSerializer(read_only=True)

    class Meta:
        model = PriceList
        fields = ['service']


class ReportSerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    service_name = serializers.CharField(source='service.doctor_service', read_only=True)
    department_name = serializers.CharField(source='service.department.department_name', read_only=True)
    payment_type = serializers.CharField(source='payment.get_payment_type_display', read_only=True)
    service_price = serializers.DecimalField(source='service.price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Report
        fields = [
            'id',
            'date',
            'doctor_name',
            'patient_name',
            'service_name',
            'department_name',
            'payment_type',
            'service_price',
        ]

    def get_doctor_name(self, obj):
        return f"{obj.doctor.first_name} {obj.doctor.last_name}"


class ReportDoctorsSerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()
    doctor_salary = DoctorSalarySerializer(source='service')


    class Meta:
        model = Report
        fields = ['id', 'date', 'doctor_name', 'doctor_salary']

    def get_doctor_name(self, obj):
        return f"{obj.doctor.first_name} {obj.doctor.last_name}"


class ReportDoctorsExportExcelView(APIView):
    def get(self, request):
        reports = Report.objects.select_related('doctor', 'service', 'service__department').all()

        # 💡 Ручная фильтрация (аналог DoctorReportFilter)
        doctor_id = request.query_params.get('doctor')
        if doctor_id:
            reports = reports.filter(doctor_id=doctor_id)

        date_from = request.query_params.get('date_from')
        if date_from:
            reports = reports.filter(date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            reports = reports.filter(date__lte=date_to)

        # 📄 Создаём Excel
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Doctor Reports"

        # 🧠 Заголовки
        headers = ['ID', 'Дата', 'Врач', 'Оклад врача', 'Цена услуги', 'Отделение']
        sheet.append(headers)

        for report in reports:
            row = [
                report.id,
                report.date.strftime('%Y-%m-%d'),
                f"{report.doctor.first_name} {report.doctor.last_name}",
                float(report.service.salary_doctor) if report.service else 0,
                float(report.service.price) if report.service else 0,
                report.service.department.department_name if report.service and report.service.department else '',
            ]
            sheet.append(row)

        # 📦 Ответ
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=doctor_report.xlsx'
        workbook.save(response)
        return response
