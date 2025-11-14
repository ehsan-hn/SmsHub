
## SmsHub – مستندات طراحی و راه‌اندازی

این مخزن، نمونه‌ای از یک درگاه پیامکی (SMS Gateway) مقیاس‌پذیر است که برای مدیریت ارسال روزانه صد میلیون پیامک با استفاده از Django، PostgreSQL، Redis، Celery و RabbitMQ طراحی شده است.

در این سند، معماری سیستم، مدل داده، جریان‌های کاری اصلی (Workflows)، APIها و نحوه راه‌اندازی پروژه توضیح داده شده است.

---

## نمای کلی معماری (Architecture Overview)

* **Gateway API (Django + DRF)**
    لایه REST API برای دریافت درخواست‌های «شارژ حساب»، «ارسال پیامک» و «گزارش‌گیری». تمام ورودی‌ها اعتبارسنجی شده و سپس به سرویس‌های لایه Domain ارسال می‌شوند.

* **PostgreSQL**
    پایگاه داده اصلی و منبع حقیقت (Source of Truth) برای نگهداری اطلاعات کاربران، پیامک‌ها و تراکنش‌های مالی. از ایندکس‌ها و قفل‌های ردیفی (Row Locks) برای حفظ یکپارچگی داده‌ها در ترافیک بالا استفاده می‌شود.

* **Redis**
    * کش کردن موجودی کاربران (`user_balance:{id}`) برای پاسخ‌دهی با **تأخیر پایین (Low Latency)**.
    * استفاده به عنوان Result Backend برای Celery و نگهداری داده‌های موقت.

* **RabbitMQ + Celery**
    دو صف (Queue) مجزا برای تفکیک وظایف:
    * `standard_sms_sender`: برای پیامک‌های معمولی و انبوه.
    * `express_sms_sender`: برای پیامک‌های فوری (مانند OTP، رمز پویا و ...).
    این تفکیک تضمین می‌کند که SLA (سطح توافق خدمات) پیامک‌های اکسپرس، مستقل از بار کاری پیامک‌های انبوه حفظ شود.

* **Workers & Provider Clients**
    ورکرهای Celery با دریافت پیام از صف، با ماژول‌های `sms.sms_provider_clients` (مانند کلاینت Magfa) ارتباط می‌گیرند. هر کلاینت، قابلیت جابجایی (Switch) سریع بین اپراتورها را فراهم می‌کند.

* **Flower / Observability**
    پنل Flower بر صف‌ها و وظایف (Tasks) نظارت می‌کند. رکوردهای تراکنش و لاگ‌ها امکان ممیزی (Auditing) و بررسی بلادرنگ (Real-time) را فراهم می‌سازند.

---

## جریان‌های کاری کلیدی (Key Workflows)

### ۱. شارژ حساب
1.  کلاینت، `POST /billing/v1/charge` را فراخوانی می‌کند.
2.  سرویس `billing.services.create_charge_transaction` با استفاده از `select_for_update` (قفل ردیفی) موجودی را افزایش می‌دهد.
3.  تراکنش با نوع `charge` ثبت شده و پس از Commit، کش Redis نیز همگام‌سازی (Sync) می‌شود.

### ۲. ارسال پیامک
1.  کلاینت `POST /sms/v1/send` را با پارامترهای `user_id`, `receiver`, `content`, `is_express` ارسال می‌کند.
2.  سرویس پیامک، هزینه را محاسبه و تراکنش `sms_deduction` را ثبت می‌کند؛ در صورت عدم وجود موجودی کافی، خطای `InsufficientFundsError` بازگردانده می‌شود.
3.  رکورد `SMS` ایجاد شده و `sms_id` به همراه `task_id` (شناسه وظیفه Celery) در پاسخ بازگردانده می‌شود.
4.  بسته به مقدار `is_express`، وظیفه در صف مناسب (standard یا express) قرار می‌گیرد. ورکر، پیام را به اپراتور ارسال کرده و وضعیت (Status) پیامک را به‌روزرسانی می‌کند.

### ۳. مدیریت وضعیت پیامک
* یک دستور مدیریتی (مانند `python manage.py checkstatus`) یا یک Cronjob متناظر، وضعیت پیامک‌های ارسال شده (`sent`) در ۲۴ ساعت گذشته را از اپراتورهای خاص استعلام می‌کند.
* پیامک‌هایی که وضعیت نهایی آن‌ها `failed` گزارش شود (یا پاسخی دریافت نکنند)، وضعیتشان به `failed` تغییر یافته و از طریق `create_refund_transaction` مبلغ کسر شده به حساب کاربر بازگشت داده می‌شود (Refund).

### ۴. گزارش‌گیری
* لیست پیامک‌ها با فیلترهای `user_id`, `status`, `receiver`, `start_date`, `end_date` از طریق `GET /sms/v1/report` قابل دریافت است. سیستم صفحه‌بندی (Paging) به‌صورت پیش‌فرض `PageNumberPagination` است.

---

## مدل داده (Data Model)

```text
User (account_user)
 ├─ username
 ├─ rate_limit_per_minute: نرخ مجاز ارسال در دقیقه (برای کنترل مشتریان پرمصرف)
 └─ balance: موجودی فعلی (واحد پولی: ریال)

SMS (sms_sms)
 ├─ user_id → User
 ├─ status: created/in_queue/sent/delivered/failed/...
 ├─ is_express: (boolean) تفکیک صف ارسال
 ├─ cost: هزینه کسر شده
 └─ message_id: شناسه بازگشتی از اپراتور (جهت رهگیری)

Transaction (billing_transaction)
 ├─ user_id → User
 ├─ sms_id → SMS (nullable، برای تراکنش‌های شارژ)
 ├─ type: charge/refund/sms_deduction
 ├─ amount: عدد مثبت برای شارژ (واریز) و منفی برای کسر (برداشت)
 └─ ایندکس‌ها: روی (user,type) و (created_at) برای گزارش‌گیری سریع
```

##  Tech Stack

-   **Backend**: Django 5.2 + Django REST Framework
    
-   **Docs**: drf-spectacular (ارائه Swagger & ReDoc)
    
-   **Cache & Rate Data**: Redis 7
    
-   **Queue & Async**: RabbitMQ 3.13 + Celery 5.3 (دو صف مجزا)
    
-   **Database**: PostgreSQL 15 (در محیط توسعه می‌توان از SQLite استفاده کرد)
    
-   **Containerization**: Docker & docker-compose
    
-   **Observability**: Flower 2.0 (روی پورت 5555)
## APIها

| مسیر | متد | توضیح | بدنه/پارامترهای مهم | پاسخ نمونه |
|------|-----|-------|---------------------|-------------|
| `/billing/v1/charge` | `POST` | شارژ حساب کاربر | `{ "user_id": 1, "amount": 100000 }` | `{ "user_id": 1, "total_balance": 250000 }` |
| `/sms/v1/send` | `POST` | ثبت پیامک و آغاز ارسال آسنکرون | `{ "user_id": 1, "receiver": "98912...", "content": "...", "is_express": false }` | `{ "sms_id": 345, "task_id": "e6b..." }` |
| `/sms/v1/report` | `GET` | گزارش پیامک با فیلتر | `?user_id=1&status=sent&start_date=2025-01-01` | صفحه‌بندی DRF از `SMSReportSerializer` |
| `/api/schema/` | `GET` | فایل OpenAPI (JSON) | - |‌ خروجی drf-spectacular |
| `/api/docs/` | `GET` | Swagger UI | - | مستند تعاملی |
| `/api/redoc/` | `GET` | ReDoc UI | - | مستند خوانا |

> برای مشاهده Swagger، پس از اجرای پروژه به آدرس `http://localhost:8000/api/docs/` مراجعه کنید.

## راهنمای اجرا (Docker Compose)

1.  فایل `.env` را بر اساس `env.docker.example` ایجاد کنید:
    
    Bash
    
    ```
    cp env.docker.example .env
    
    ```
    
2.  سرویس‌ها را با Docker Compose اجرا کنید:
    
    Bash
    
    ```
    docker compose up --build
    
    ```
    
3.  پس از اجرای کامل کانتینرها:
    
    -   API: `http://localhost:8000/`
        
    -   Swagger: `http://localhost:8000/api/docs/`
        
    -   Flower: `http://localhost:5555/` (با نام کاربری و رمز عبوری که در `.env` تعریف کرده‌اید)
        

----------

## سناریوهای مقیاس‌پذیری و اطمینان‌پذیری (Scalability & Reliability)

-   **تفکیک صف اکسپرس/عادی**: امکان می‌دهد ظرفیت سرورها (Worker) متناسب با SLA هر کانال تنظیم شود.
    
-   **Horizontally Scalable Workers**: هر دو صف می‌توانند Replicaهای متعددی داشته باشند. تنظیم `prefetch_multiplier` و `acks_late` تضمین می‌کند که در صورت Crash کردن ورکر، پیامک به صف بازگردد.
    
-   **قفل ردیفی هنگام کسر/شارژ**: تضمین می‌کند موجودی کاربر به‌صورت اتمیک (Atomic) مدیریت شده و از ارسال پیامک با موجودی منفی جلوگیری می‌شود.
    
-   **Refund خودکار**: بازگشت خودکار هزینه پیامک‌های ناموفق، تجربه کاربری بهتری فراهم کرده و اطمینان می‌دهد کاربر می‌تواند تمام موجودی خود را مصرف کند.
    
-   **ایندکس‌های گزارش‌گیری**: Queryهای پرترافیک (مانند جستجوی پیامک‌های یک کاربر خاص) با استفاده از ایندکس‌های مناسب (مانند `sms_user_idx`) تسریع می‌شوند.
    
-   **زیرساخت Rate Limiting**: فیلد `rate_limit_per_minute` در مدل `User`، زمینه را برای پیاده‌سازی محدودیت نرخ ارسال (Rate Limiting) به ازای هر مشتری (در لایه سرویس یا با Redis) فراهم می‌کند.
    

----------

## تست و کیفیت (Testing & Quality)

-   تست‌های واحد (Unit Tests) و API در مسیرهای `sms/tests` و `billing/tests` قرار دارند.
    
-   اجرای تست‌ها:
    
    Bash
    
    ```
    python manage.py test
    
    ```
    
-   ابزار Ruff برای آنالیز استاتیک کد (Linting) پیکربندی شده است (`pyproject.toml`).
    

----------

## مسیرهای توسعه آتی (Future Roadmap)

-   تکمیل ماژول Rate Limiting بلادرنگ برای کنترل دقیق مشتریان پرمصرف.
    
-   افزودن `Failover Provider Client` برای جابجایی (Switch) خودکار به اپراتور پشتیبان در صورت قطعی اپراتور اصلی.
    
-   اضافه کردن **متریک‌های (Metrics)** Prometheus و داشبورد Grafana.
    
-   اعمال Sharding یا Partitioning بر حسب `user_id` در جدول `SMS` برای مدیریت حجم‌های بسیار کلان داده.
    
-   پیاده‌سازی سیستم اعلان (Notification) مبتنی بر Webhook برای اطلاع‌رسانی وضعیت نهایی پیامک‌ها به مشتریان سازمانی.
