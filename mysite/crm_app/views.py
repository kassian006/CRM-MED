from rest_framework import viewsets, generics, status
from .serializers import *
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework import filters
from .filters import PatientFilter, ReportFilter, DoctorReportFilter, AllReportFilter
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.response import Response
from django.db.models import Sum, Q
from rest_framework.viewsets import ReadOnlyModelViewSet
from drf_yasg.utils import swagger_auto_schema
from .models import Report
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import ReportSerializer
from .models import EmailLoginCode
from rest_framework.decorators import api_view
from django.contrib.auth import authenticate, login
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
import random
from django.core.mail import send_mail
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import EmailLoginCode
from .serializers import SendLoginCodeSerializer, VerifyLoginCodeSerializer
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse
import openpyxl
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, F
from .models import Report
from django.utils.dateparse import parse_date
from openpyxl import Workbook
from django.db.models import Sum
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from django.db.models import Count, Q
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from datetime import timedelta, datetime
from collections import defaultdict


@api_view(['POST'])
def send_login_code_view(request):
    serializer = SendLoginCodeSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        code = str(random.randint(100000, 999999))

        # Сохраняем в БД
        EmailLoginCode.objects.create(email=email, code=code)

        # Отправляем на почту
        send_mail(
            'Код для сброса пароля',
            f'Ваш код для сброса пароля: {code}',
            'noreply@example.com',  # может быть EMAIL_HOST_USER
            [email],
            fail_silently=False,
        )

        return Response({'message': 'Код отправлен на почту'}, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def verify_login_code(request):
    serializer = VerifyLoginCodeSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        try:
            login_code = EmailLoginCode.objects.filter(email=email, code=code).latest('created_at')
        except EmailLoginCode.DoesNotExist:
            return Response({'error': 'Неверный код'}, status=status.HTTP_400_BAD_REQUEST)

        if not login_code.is_valid():
            return Response({'error': 'Код устарел'}, status=status.HTTP_400_BAD_REQUEST)

        # Если код валидный — можно теперь попросить ввести новый пароль (или сразу поменять)
        return Response({'message': 'Код подтвержден. Введите новый пароль.'}, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def reset_password_view(request):
    serializer = ResetPasswordSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        new_password = serializer.validated_data['new_password']

        try:
            login_code = EmailLoginCode.objects.filter(email=email, code=code).latest('created_at')
        except EmailLoginCode.DoesNotExist:
            return Response({'error': 'Неверный код'}, status=status.HTTP_400_BAD_REQUEST)

        if not login_code.is_valid():
            return Response({'error': 'Код устарел'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = UserProfile.objects.get(email=email)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Пользователь не найден'}, status=status.HTTP_404_NOT_FOUND)

        user.set_password(new_password)
        user.save()

        return Response({'message': 'Пароль успешно обновлён'}, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomLoginView(TokenObtainPairView):
    serializer_class = LoginSerializers

    def post(self, request, *args, **kwargs):
        serializer=self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            return Response({"detail: Неверные учетные данные"}, status=status.HTTP_401_UNAUTHORIZED)

        user=serializer.validated_data
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomAdminLoginView(TokenObtainPairView):
    serializer_class = LoginSerializers

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            return Response({"detail": "Неверные учетные данные"}, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.validated_data.get('user')

        if not user.is_staff and not user.is_superuser:
            return Response({"detail": "Доступ разрешен только администраторам"},
                            status=status.HTTP_403_FORBIDDEN)

        return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(generics.GenericAPIView):
    serializer_class = LogoutSerializer
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh токен отсутствует."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Вы вышли из системы."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"detail": "Ошибка обработки токена."}, status=status.HTTP_400_BAD_REQUEST)



class DoctorListAPIView(generics.ListAPIView):
    queryset = Doctor.objects.all()
    serializer_class = DoctorListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['department']
    search_fields = ['first_name', 'last_name']


class DoctorDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Doctor.objects.all()
    serializer_class = DoctorDetailSerializer


class DoctorCreateAPIView(generics.CreateAPIView):
    serializer_class = DoctorCreateSerializer
    parser_classes = (MultiPartParser, FormParser)

    @swagger_auto_schema(request_body=DoctorCreateSerializer)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


    # def create(self, request, *args, **kwargs):
    #     try:
    #         serializer = self.get_serializer(data=request.data)
    #         serializer.is_valid(raise_exception=True)
    #         doctor = serializer.save()
    #         return Response(serializer.data, status.HTTP_201_CREATED)
    #     except serializers.ValidationError as e:
    #         return Response({'detail': 'Маалымат туура эмес берилди'}, status.HTTP_400_BAD_REQUEST)
    #     except NameError as e:
    #         return Response({'detail': f'{e}, Ошибка в коде'}, status.HTTP_500_INTERNAL_SERVER_ERROR)
    #     except Exception:
    #         return Response({'detail': 'Сервер не работает'}, status.HTTP_500_INTERNAL_SERVER_ERROR)


class PatientAPIView(generics.CreateAPIView):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer


class PatientDesktopListAPIView(generics.ListAPIView):
    queryset = Patient.objects.all()
    serializer_class = PatientDesktopSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = PatientFilter
    search_fields = ['full_name']

class PatientDesktopDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer


class MakeAppointmentInfoPatientAPIView(generics.CreateAPIView):
    queryset = Patient.objects.select_related('reception', 'doctor', 'department', 'doctor_service').all()
    serializer_class = MakeAppointmentInfoPatientSerializer


class HistoryRecordInfoPatientAPIView(generics.ListAPIView):
    queryset = Patient.objects.all()
    serializer_class = HistoryRecordInfoPatientSerializer


class HistoryReceptionInfoPatientAPIView(generics.ListAPIView):
    queryset = Patient.objects.all()
    serializer_class = HistoryReceptionInfoPatientSerializer



class CalendarListAPIView(generics.ListAPIView):
    queryset = Patient.objects.all()
    serializer_class = CalendarSerializer


class CalendarDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Patient.objects.all()
    serializer_class = CalendarSerializer


class CalendarCreateAPIView(generics.CreateAPIView):
    serializer_class = CalendarCreateSerializer


class PaymentInfoPatientListAPIView(generics.ListAPIView):
    queryset = Patient.objects.all()
    serializer_class = PaymentInfoPatientSerializer


class PaymentInfoPatientDetailAPIView(generics.RetrieveUpdateAPIView):
    queryset = Patient.objects.all()
    serializer_class = PaymentInfoPatientSerializer


class InfoPatientAPIView(generics.ListAPIView):
    queryset = Patient.objects.all()
    serializer_class = InfoPatientSerializer


class CheckRecordListAPIView(generics.ListAPIView):
    queryset = CustomerRecord.objects.all()
    serializer_class = CheckRecordSerializer


class PriceListAPIView(generics.ListAPIView):
    queryset = PriceList.objects.all()
    serializer_class = PriceListSerializer


class PriceDetailAPIView(generics.RetrieveAPIView):
    queryset = PriceList.objects.all()
    serializer_class = PriceDetailSerializer


class ReportListAPIView(APIView):
    def get(self, request):
        queryset = Report.objects.select_related('doctor', 'patient', 'service__department', 'payment')

        # 🔍 Поиск
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(doctor__first_name__icontains=search) |
                Q(doctor__last_name__icontains=search) |
                Q(patient__full_name__icontains=search) |
                Q(service__doctor_service__icontains=search) |
                Q(service__department__department_name__icontains=search)
            )

        # 👨‍⚕️ Фильтр по врачу
        doctor_id = request.GET.get('doctor')
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)

        # 🏥 Фильтр по отделению
        department_id = request.GET.get('department')
        if department_id:
            queryset = queryset.filter(service__department_id=department_id)

        # 📅 Фильтр по датам
        date_from = request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)

        date_to = request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        # 💰 Подсчёты
        total_sum = queryset.aggregate(sum=Sum('service__price'))['sum'] or 0
        cash_sum = queryset.filter(payment__payment_type='cash').aggregate(sum=Sum('service__price'))['sum'] or 0
        card_sum = queryset.filter(payment__payment_type='card').aggregate(sum=Sum('service__price'))['sum'] or 0

        # ⚙️ Сериализация
        serializer = ReportSerializer(queryset, many=True)

        return Response({
            'count': queryset.count(),
            'total_sum': total_sum,
            'cash_sum': cash_sum,
            'card_sum': card_sum,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class PaymentInfoPatientSumAPIView(APIView):
    def get(self, request):
        data = Payment.get_count_sum()
        serializer = PaymentTypeNameSumSerializer(data)
        return Response(serializer.data)


class HistoryReceptionInfoPatientDefAPIView(generics.ListAPIView):
    queryset = Patient.objects.all()
    serializer_class = HistoryReceptionInfoPatientTotalSerializer


class HistoryRecordInfoPatientDefAPIView(generics.ListAPIView):
    queryset = Patient.objects.all()
    serializer_class = HistoryRecordInfoPatientTotalSerializer


class ReportExportExcelView(APIView):
    def get(self, request):
        reports = Report.objects.select_related('doctor', 'patient', 'service', 'payment').all()

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Reports"

        headers = ['ID', 'Date', 'Doctor', 'Patient', 'Service', 'Department', 'Payment Type', 'Price']
        sheet.append(headers)

        for report in reports:
            row = [
                report.id,
                report.date.strftime('%Y-%m-%d'),
                f"{report.doctor.first_name} {report.doctor.last_name}",
                report.patient.full_name,
                report.service.doctor_service,
                report.service.department.department_name,
                report.payment.get_payment_type_display(),
                float(report.service.price)
            ]
            sheet.append(row)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=report.xlsx'
        workbook.save(response)
        return response


class ReportDoctorsAPIViews(generics.ListAPIView):
    queryset = Report.objects.all()
    serializer_class = ReportDoctorsSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = DoctorReportFilter


class SummaryReportView(APIView):
    def get(self, request):
        reports = Report.objects.select_related('payment', 'service', 'doctor', 'patient', 'service__department')

        # 🔎 Search-поиск
        search = request.GET.get('search')
        if search:
            reports = reports.filter(
                Q(doctor__first_name__icontains=search) |
                Q(doctor__last_name__icontains=search) |
                Q(patient__full_name__icontains=search) |
                Q(service__doctor_service__icontains=search) |
                Q(service__department__department_name__icontains=search)
            )

        # 🧪 Применим фильтр дат (AllReportFilter)
        filterset = AllReportFilter(request.GET, queryset=reports)
        if filterset.is_valid():
            reports = filterset.qs
        else:
            return Response(filterset.errors, status=400)

        # 📊 Подсчёты
        total_services = reports.aggregate(sum=Sum('service__price'))['sum'] or 0
        cash_total = reports.filter(payment__payment_type='cash').aggregate(sum=Sum('service__price'))['sum'] or 0
        card_total = reports.filter(payment__payment_type='card').aggregate(sum=Sum('service__price'))['sum'] or 0
        doctor_salary_total = reports.aggregate(sum=Sum('service__salary_doctor'))['sum'] or 0
        doctor_salary_cash = reports.filter(payment__payment_type='cash').aggregate(sum=Sum('service__salary_doctor'))['sum'] or 0
        doctor_salary_card = reports.filter(payment__payment_type='card').aggregate(sum=Sum('service__salary_doctor'))['sum'] or 0
        clinic_cash = cash_total - doctor_salary_cash
        clinic_card = card_total - doctor_salary_card

        return Response({
            "cash_paid": cash_total,
            "card_paid": card_total,
            "total_services": total_services,
            "doctor_salary_total": doctor_salary_total,
            "doctor_salary_cash": doctor_salary_cash,
            "doctor_salary_card": doctor_salary_card,
            "clinic_cash": clinic_cash,
            "clinic_card": clinic_card,
        })


class SummaryReportExportExcelView(APIView):
    def get(self, request):
        reports = Report.objects.select_related('payment', 'service', 'doctor', 'patient', 'service__department')

        # 🔍 Фильтр по поиску
        search = request.GET.get('search')
        if search:
            reports = reports.filter(
                Q(doctor__first_name__icontains=search) |
                Q(doctor__last_name__icontains=search) |
                Q(patient__full_name__icontains=search) |
                Q(service__doctor_service__icontains=search) |
                Q(service__department__department_name__icontains=search)
            )

        # 📅 Фильтр по датам
        filterset = AllReportFilter(request.GET, queryset=reports)
        if filterset.is_valid():
            reports = filterset.qs
        else:
            return Response(filterset.errors, status=400)

        # 📊 Подсчёты
        total_services = reports.aggregate(sum=Sum('service__price'))['sum'] or 0
        cash_total = reports.filter(payment__payment_type='cash').aggregate(sum=Sum('service__price'))['sum'] or 0
        card_total = reports.filter(payment__payment_type='card').aggregate(sum=Sum('service__price'))['sum'] or 0
        doctor_salary_total = reports.aggregate(sum=Sum('service__salary_doctor'))['sum'] or 0
        doctor_salary_cash = reports.filter(payment__payment_type='cash').aggregate(sum=Sum('service__salary_doctor'))['sum'] or 0
        doctor_salary_card = reports.filter(payment__payment_type='card').aggregate(sum=Sum('service__salary_doctor'))['sum'] or 0
        clinic_cash = cash_total - doctor_salary_cash
        clinic_card = card_total - doctor_salary_card

        # 📁 Создаём Excel
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Summary Report"

        sheet.append([
            'Total Services', 'Cash Paid', 'Card Paid',
            'Doctor Salary (Total)', 'Doctor Salary (Cash)', 'Doctor Salary (Card)',
            'Clinic (Cash)', 'Clinic (Card)'
        ])

        sheet.append([
            total_services, cash_total, card_total,
            doctor_salary_total, doctor_salary_cash, doctor_salary_card,
            clinic_cash, clinic_card
        ])

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=summary_report.xlsx'
        workbook.save(response)
        return response


class AppointmentStatisticsAPIView(APIView):
    def get(self, request):
        period = request.query_params.get('period', 'weekly')
        today = timezone.now().date()

        if period == 'daily':
            start_date = today
            delta = timedelta(days=1)
        elif period == 'weekly':
            start_date = today - timedelta(days=6)
            delta = timedelta(days=1)
        elif period == 'monthly':
            start_date = today - timedelta(days=29)
            delta = timedelta(days=1)
        elif period == 'yearly':
            start_date = today - timedelta(days=364)
            delta = timedelta(days=30)
        else:
            return Response({"error": "Invalid period"}, status=400)

        chart_data = defaultdict(lambda: {"total": 0, "canceled": 0})

        patients = Patient.objects.filter(appointment_date__range=(start_date, today))

        for patient in patients:
            date_str = patient.appointment_date.strftime("%d %b")
            chart_data[date_str]["total"] += 1
            if patient.status_patient == "Отмененные":
                chart_data[date_str]["canceled"] += 1

        sorted_chart = [
            {"period": key, "total": value["total"], "canceled": value["canceled"]}
            for key, value in sorted(chart_data.items(), key=lambda x: datetime.strptime(x[0], "%d %b"))
        ]

        # Рост и падение
        previous_period_start = start_date - (today - start_date)
        previous_patients_count = Patient.objects.filter(
            appointment_date__range=(previous_period_start, start_date - timedelta(days=1))
        ).count()
        current_patients_count = patients.count()

        if previous_patients_count == 0:
            growth_percent = 100 if current_patients_count > 0 else 0
            decline_percent = 0
            trend = "up" if current_patients_count > 0 else "same"
        else:
            difference = current_patients_count - previous_patients_count
            percent_change = round(abs(difference) / previous_patients_count * 100)
            if difference > 0:
                growth_percent = percent_change
                decline_percent = 0
                trend = "up"
            elif difference < 0:
                growth_percent = 0
                decline_percent = percent_change
                trend = "down"
            else:
                growth_percent = 0
                decline_percent = 0
                trend = "same"

        total_doctors = Doctor.objects.count()
        total_clients = current_patients_count

        new_patients = patients.filter(status_patient='Живая очередь').count()
        repeated_patients = patients.exclude(status_patient='Живая очередь').count()
        total_patients = new_patients + repeated_patients

        new_percent = int(new_patients / total_patients * 100) if total_patients else 0
        repeated_percent = int(repeated_patients / total_patients * 100) if total_patients else 0

        return Response({
            "chart": sorted_chart,
            "total_doctors": total_doctors,
            "total_clients": total_clients,
            "new_percent": new_percent,
            "repeated_percent": repeated_percent,
            "growth_percent": growth_percent,
            "decline_percent": decline_percent,
            "trend": trend
        })